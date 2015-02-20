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

import sys, os, operator
#sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')
sys.path.append(os.environ['HOME'] + '/ue-wiki-bot/ue_wikibots/core')
sys.path.append(os.environ['HOME'] + '/ue-wiki-bot/ue_wikibots/core/pywikibot')

import pywikibot, pagegenerators
import re, difflib
import logging

# Stuff for the pywikibot help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
summary = u'Robot: Sort template parameters'

# RE to match a parameter for the form "root_n[_leaf] = value"
numParamRe = re.compile(ur'(?P<root>[a-zA-Z]+)_(?P<num>\d+)(?P<leaf>[^=\s]*)\s*=\s*(?P<value>.*)')

lt_root_ordering = [
    u'image',
    u'atk',
    u'def',
    u'pwr',
    u'item',
]

def lt_sort_key(param):
    """
    Returns a sort key tuple from a parameter
    """
    m = numParamRe.match(param)
    if m:
        num = int(m.group('num'))
        root = m.group('root')
        if root == u'item':
            # Sort all items after all levels
            num += 20
        elif root == u'image':
            # Sort skin images in with the un-numbered part
            num = 0
        return (num, lt_root_ordering.index(root), m.group('leaf'))
    else:
        # Sort all unnumbered ones before all numbered ones
        return (0, param)

def sort_lt_params(text, params):
    """
    Returns text with the specified parameters sorted into a more reasonable order
    """
    print sorted(params, key=lt_sort_key)
    
    return text

def lab_sort_key(param):
    """
    Returns a sort key tuple from a parameter
    """
    m = numParamRe.match(param)
    if m:
        return (m.group('num'), m.group('root'), m.group('leaf'))
    else:
        # Sort all unnumbered ones before all numbered ones
        return (0, param)

def sort_lab_params(text, params):
    """
    Returns text with the specified parameters sorted into a more reasonable order
    """
    print sorted(params, key=lab_sort_key)
    
    return text

class ItemBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall

    def update_or_create_page(self, old_page, new_text):
        """
        Reads the current text of page old_page,
        compare it with new_text, prompts the user,
        and uploads the page
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
                choice = pywikibot.input_choice(u'Do you want to accept these changes?',  [('Yes', 'Y'), ('No', 'n'), ('All', 'a')], 'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text, summary)

    def update_lts(self):
        """
        Creates or updates each page in the Lieutenants category.
        """
        # All the pages we're interested in are in these two categories
        # TODO If this list grwos, it may be better to find pages that
        #      reference the templates we're interested in
        cat1 = pywikibot.Category(pywikibot.Site(), u'Lieutenants')
        cat2 = pywikibot.Category(pywikibot.Site(), u'Epic Research Items')
        # Only process each page once
        pages = set(cat1.articles(recurse=False)) | set(cat2.articles(recurse=False))
        print pages

        for page in pages:
            text = page.get()
            for t,p in page.templatesWithParams():
                title = t.title(withNamespace=False)
                # We only care about a few templates
                if u'Lieutenant' in title:
                    text = sort_lt_params(text, p);
                elif title.startswith(u'Lab'):
                    text = sort_lab_params(text, p)
            # Update the page
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            self.update_or_create_page(page, text);

    def run(self):
        self.update_lts()

def main():
    #logging.basicConfig()
    bot = ItemBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

