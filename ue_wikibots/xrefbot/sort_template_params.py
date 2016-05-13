# Copyright (C) 2015 Chris Brand
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
Script to sort a subset of template parameters on Underworld Empire Wiki
"""

import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
import re
import difflib

# Summary message when using this module as a stand-alone script
summary = u'Robot: Sort Lab/Lt template parameters'

# RE to match a parameter for the form "root_n[_leaf] = value"
NUM_PARAM_RE = re.compile(ur'(?P<root>[a-zA-Z]+)_(?P<num>\d+)(?P<leaf>[^=\s]*)\s*=\s*(?P<value>.*)')

LT_ROOT_ORDERING = [
    u'image',
    u'atk',
    u'def',
    u'pwr',
    u'item',
]

def lt_sort_key(param):
    """
    Return a sort key tuple from a parameter
    """
    m = NUM_PARAM_RE.match(param)
    if m:
        num = int(m.group('num'))
        root = m.group('root')
        if root == u'item':
            # Sort all items after all levels
            num += 20
        elif root == u'image' or root == u'skin':
            # Sort skin images in with the un-numbered part
            return (0, param)
        return (num, LT_ROOT_ORDERING.index(root), m.group('leaf'))
    else:
        # Sort all unnumbered ones before all numbered ones
        return (0, param)

def next_template_end(text, start, end):
    """
    Returns the index of the next u'{{' or u'}}' in text[start:end].
    Raises ValueError if neither are present.
    """
    left = text.find(u'{{', start, end)
    if left == -1:
        return text.index(u'}}', start, end)
    right = text.find(u'}}', start, end)
    if left < right or right == -1:
        return left
    return right

def template_bounds(text, template):
    """
    Finds the specified template in the text. Returns a 2-tuple of
    (start_index, end_index) such that text[start_index:end_index]
    starts and ends with the {{...}}.
    """
    # Find the start of the template of interest,
    # and the end of the last template in text
    start = text.index(u'{{%s' % template)
    end = text.rindex(u'}}')

    # Go through the text between start and end, finding
    # all the start and end template markers.
    start_2 = start
    braces = []
    while True:
        try:
            pos = next_template_end(text, start_2 + 2, end)
        except ValueError:
            # We've found all the starts and ends
            break
        # Add this one to the list
        braces.append((text[pos:pos+2], pos))
        # Continue checking after this one
        start_2 = pos
    # Now we can go through the list pairing up braces
    # We know the list is sorted by position
    # We started inside the template of interest
    nesting = 1
    for brace in braces:
        if brace[0] == u'}}':
            # This is the end of the current template
            nesting -= 1
            if nesting == 0:
                # Current template is the template of interest
                end = brace[1]
                break
        else:
            # Start of a nested template
            nesting += 1

    # Include the start and end template markers
    return (start, end+2)

def sort_lt_params(text, template, params):
    """
    Return text with the specified parameters sorted into a more reasonable order
    """
    start, end = template_bounds(text, template)
    new_text = u'{{%s\n|' % template + u'\n|'.join(sorted(params,
                                                          key=lt_sort_key)) + u'\n}}'
    return text[:start] + new_text + text[end:]

def lab_sort_key(param):
    """
    Return a sort key tuple from a parameter
    """
    m = NUM_PARAM_RE.match(param)
    if m:
        return (m.group('num'), m.group('root'), m.group('leaf'))
    else:
        # Sort all unnumbered ones before all numbered ones
        return (0, param)

def sort_lab_params(text, template, params):
    """
    Return text with the specified parameters sorted into a more reasonable order
    """
    start, end = template_bounds(text, template)
    new_text = u'{{%s\n|' % template + u'\n|'.join(sorted(params,
                                                          key=lab_sort_key)) + u'\n}}'
    return text[:start] + new_text + text[end:]

class ItemBot:
    def __init__(self, acceptall = False):
        self.acceptall = acceptall

    def update_or_create_page(self, old_page, new_text):
        """
        Read the current text of page old_page,
        compare it with new_text, prompt the user,
        and upload the page
        """
        # Read the original content
        old_text = old_page.get()
        # Give the user some context
        if old_text != new_text:
            pywikibot.output(new_text)
        pywikibot.showDiff(old_text, new_text)
        # Get a decision
        prompt = u'Modify this page ?'
        # Did anything change ?
        if old_text == new_text:
            pywikibot.output(u'No changes necessary to %s' % old_page.title());
        else:
            if not self.acceptall:
                choice = pywikibot.input_choice(u'Do you want to accept these changes?',
                                                [('Yes', 'Y'),
                                                 ('No', 'n'),
                                                 ('All', 'a')],
                                                'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text, summary)

    def update_lts_and_lab_items(self):
        """
        Create or update each page in the Lieutenants and Epic Research Items
        categories.
        """
        # All the pages we're interested in are in these two categories
        # TODO If this list grows, it may be better to find pages that
        #      reference the templates we're interested in
        cat1 = pywikibot.Category(pywikibot.Site(), u'Lieutenants')
        cat2 = pywikibot.Category(pywikibot.Site(), u'Epic Research Items')
        # Only process each page once
        pages = set(cat1.articles(recurse=False)) | set(cat2.articles(recurse=False))

        for page in pages:
            text = page.get()
            for t,p in page.templatesWithParams():
                title = t.title(withNamespace=False)
                # We only care about a few templates
                # but some pages use more than one of them
                if u'Lieutenant' in title:
                    text = sort_lt_params(text, title, p);
                if title.startswith(u'Lab'):
                    text = sort_lab_params(text, title, p)
            # Update the page
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            self.update_or_create_page(page, text);

    def run(self):
        self.update_lts_and_lab_items()

def main():
    bot = ItemBot()
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

