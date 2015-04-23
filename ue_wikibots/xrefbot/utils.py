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
Utility functions for UEW wikibots
"""

import sys, os
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')

import pywikibot
import re

# Separate the name and value for a template parameter
Rparam = re.compile(ur'\s*(?P<name>[^\s=]+)\s*=\s*(?P<value>.*)', re.DOTALL)

def escapeStr(string):
    """
    Returns text with any |, +, (, ), [, or ] characters preceded with \ characters.
    Useful if you want to include it in a regex.
    """
    string = re.sub(ur'\|', u'\|', string)
    string = re.sub(ur'\(', u'\(', string)
    string = re.sub(ur'\)', u'\)', string)
    string = re.sub(ur'\[', u'\[', string)
    string = re.sub(ur'\+', u'\+', string)
    return re.sub(ur'\]', u'\]', string)

def paramFromParams(params, param):
    """
    Returns the value for 'param' in 'params', or None if it isn't present.
    """
    for p in params:
        m = Rparam.match(p)
        if m != None and m.group('name') == param:
            val = m.group('value')
            # People sometimes provide the parameters, even though we don't know the value
            if val != u'' and val != u'?':
                return val
    return None

def paramsToDict(params):
    """
    Takes the list of parameters to a template and returns them as a dict.
    """
    result = {}
    for param in params:
        m = Rparam.match(param)
        if m != None:
            result[m.group('name')] = m.group('value')
    return result

def findSpecificSection(text, section):
    """
    Find the specified section in text, starting with a header,
    and ending with a header, template, or category.
    Returns a tuple - (index where the section starts, index where the section ends)
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
    imgRe = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')
    img2Re = re.compile(ur'\[\[File:(?P<image>.*\.png)\|.*\]\]')

    def __init__(self):
        # Populate image_map
        self.mapping = {}

    def image_for(self, name):
        """
        Returns the image for the specified item, property, or ingredient.
        Caches results for speed.
        """
        if name not in self.mapping:
            pg = pywikibot.Page(pywikibot.Site(), name)
            # Retrieve the text of the specified page
            try:
                m = None
                text = pg.get(get_redirect=True)
                # Extract the image parameter
                m = self.imgRe.search(text)
                if m is None:
                    m = self.img2Re.search(text)
            except pywikibot.NoPage:
                pass
            if m is None:
                print("Unable to find image for %s" % name)
                return None
            self.mapping[name] = m.group('image')
        return self.mapping[name]

class CategoryRefs:
    def __init__(self):
        self.mapping = {}

    def refs_for(self, category):
        """
        Returns a list of pages that reference the specified category page.
        Caches the result, and returns from the cache in preference.
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
    def __init__(self):
        self._initialised = False

    def _read_pages(self):
        page_names = [u'Tech Lab', u'Tech Lab - Historic']
        self._recipes = {}
        for p in page_names:
            page = pywikibot.Page(pywikibot.Site(), p)
            for template, params in page.templatesWithParams():
                template_name = template.title(withNamespace=False)
                if template_name.find(u'Recipe') != -1:
                    item = paramFromParams(params, u'name')
                    self._recipes[item] = params

    def _init_if_needed(self):
        if not self._initialised:
            self._read_pages()
            self._initialised = True

    def recipes(self):
        """
        Returns a list of items with recipes.
        """
        self._init_if_needed()
        return self._recipes.keys()

    def recipe_for(self, item):
        """
        Returns the parameters to the Recipe template for the
        specified item.
        Caches results for speed.
        """
        self._init_if_needed()
        return self._recipes[item]
