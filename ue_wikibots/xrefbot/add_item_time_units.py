# Copyright (C) 2014 Chris Brand
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
Script to add units to the 'time' parameter of uses of the Basic Item template
"""

from __future__ import absolute_import
import sys
import os
import operator
from six.moves import range
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
from pywikibot import pagegenerators
import re
import difflib

import utils

# Summary message when using this module as a stand-alone script
summary = u'Robot: Add units to the time parameter'

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

    def update_basic_items(self):
        """
        Updates each page in the Basic Items category.
        """
        # Update every page in the Basic Items category
        cat = pywikibot.Category(pywikibot.Site(), u'Basic Items')

        for page in list(cat.articles(recurse=False)):
            text = page.get()
            for t,params in page.templatesWithParams():
                template = t.title(withNamespace=False)
                if template == u'Basic Item':
                    for p in params:
                        if p.startswith(u'time'):
                            # Hack - all of the pages have spaces here
                            p1 = p.replace(u'=', u' = ')
                            text = text.replace(p1, p + u'hrs')
            # Update the page
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            self.update_or_create_page(page, text);

    def run(self):
        self.update_basic_items()

def main():
    bot = ItemBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

