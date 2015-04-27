# Copyright (C) 2013-2015 Chris Brand
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#! /usr/bin/python

"""
Utility functions and classes for UEW wikibots.
"""

import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
import re

# Separate the name and value for a template parameter
_RE_PARAM = re.compile(ur'\s*(?P<name>[^\s=]+)\s*=\s*(?P<value>.*)', re.DOTALL)

def escape_str(string):
    """
    Return text with any |, +, (, ), [, or ] characters preceded with \ characters.

    string -- text to be escaped.

    Useful if you want to include it in a regex.
    """
    string = re.sub(ur'\|', u'\|', string)
    string = re.sub(ur'\(', u'\(', string)
    string = re.sub(ur'\)', u'\)', string)
    string = re.sub(ur'\[', u'\[', string)
    string = re.sub(ur'\+', u'\+', string)
    return re.sub(ur'\]', u'\]', string)

def param_from_params(params, param):
    """
    Return the value for 'param' in 'params', or None if it isn't present.

    params -- list of template parameter values.
    param -- parameter to find the value for.
    """
    for p in params:
        m = _RE_PARAM.match(p)
        if m is not None and m.group('name') == param:
            val = m.group('value')
            # People sometimes provide the parameters,
            # even though we don't know the value
            if val != u'' and val != u'?':
                return val
    return None

def params_to_dict(params):
    """
    Return the template parameters as a dict.

    params -- list of template parameters.

    Return a dict, indexed by parameter name, of parameter values.
    """
    result = {}
    for param in params:
        m = _RE_PARAM.match(param)
        if m is not None:
            result[m.group('name')] = m.group('value')
    return result

def find_specific_section(text, section):
    """
    Find the specified section in text.

    text -- page text to search.
    section -- name of the section to locate.

    Search for a header for the specified section.
    If found, search forward for a header, template, or category that
    marks the end of the section.

    Return a 2-tuple containing the start and end indices of the seciion,
    or (-1, -1) if the section isn't found.
    """
    # Does the page have a section header ?
    header = re.search(ur'==\s*%s\W*==' % section, text)
    if header:
        list_start = header.start()
        # List ends at a template, header or category
        # Skip the header for the section of interest itself
        match = re.search(r'{{|==.*==|\[\[Category', text[list_start+2:])
        if match:
            list_end = list_start+2+match.start()
        else:
            list_end = len(text)
        # Shift list_end back to exactly the end of the list
        while text[list_end-1] in u'\n\r':
            list_end -= 1
        return (list_start, list_end)
    return (-1, -1)


class ImageMap:
    """
    Cache class for the image filenames for items, properties, and ingredients.
    """

    _IMG_RE = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')
    _IMG_2_RE = re.compile(ur'\[\[File:(?P<image>.*\.png)\|.*\]\]')

    def __init__(self):
        """Instantiate the class."""
        # Populate image_map
        self.mapping = {}

    def image_for(self, name):
        """
        Return the image for the specified item, property, or ingredient.

        name -- name of the item, property, or ingredient.
        """
        if name not in self.mapping:
            pg = pywikibot.Page(pywikibot.Site(), name)
            # Retrieve the text of the specified page
            try:
                m = None
                text = pg.get(get_redirect=True)
                # Extract the image parameter
                m = self._IMG_RE.search(text)
                if m is None:
                    m = self._IMG_2_RE.search(text)
            except pywikibot.NoPage:
                pass
            if m is None:
                print("Unable to find image for %s" % name)
                return None
            self.mapping[name] = m.group('image')
        return self.mapping[name]


class CategoryRefs:
    """
    Cache class for pages that reference category pages.
    """

    def __init__(self):
        """Instantiate the class."""
        self.mapping = {}

    def refs_for(self, category):
        """
        Return a list of pages that reference the specified category page.

        category -- name of the category of interest.
        """
        try:
            return self.mapping[category]
        except KeyError:
            pass
        page = pywikibot.Page(pywikibot.Site(), u'Category:%s' % category)
        refs = list(page.getReferences())
        self.mapping[category] = refs
        return refs


class RecipeCache:
    """
    Cache class for Tech Lab recipes.
    """

    def __init__(self):
        """Instantiate the class."""
        # Note that we defer actually reading the wiki until we know
        # that we need to.
        self._initialised = False

    def _read_pages(self):
        """Read and parse all Tech Lab pages."""
        page_names = [u'Tech Lab', u'Tech Lab - Historic']
        self._recipes = {}
        for p in page_names:
            page = pywikibot.Page(pywikibot.Site(), p)
            for template, params in page.templatesWithParams():
                template_name = template.title(withNamespace=False)
                if template_name.find(u'Recipe') != -1:
                    item = param_from_params(params, u'name')
                    self._recipes[item] = params

    def _init_if_needed(self):
        """Initialise instance attributes if necessary."""
        if not self._initialised:
            self._read_pages()
            self._initialised = True

    def recipes(self):
        """Return a list of items that have recipes."""
        self._init_if_needed()
        return self._recipes.keys()

    def recipe_for(self, item):
        """
        Return the parameters to the Recipe template for the
        specified item.

        item -- item of interest.
        """
        self._init_if_needed()
        return self._recipes[item]
