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
Script to split the gear parameter on Areas pages on Underworld Empire Wiki
"""

from __future__ import absolute_import
from __future__ import unicode_literals
import sys
import os
import operator
from six.moves import range
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
from pywikibot import pagegenerators
import re
import difflib

# Summary message when using this module as a stand-alone script
summary = u'Robot: Split gear parameter into separate items and counts'

# Set of REs to replace, from 4 items down to 1
# TODO Can probably construct these in a similar way to replacement, below
# TODO This converts e.g. "gear=2 [[Condo]]s" to "gear_1_count=2|gear_1=Condos" with an extra "s"
gearRe = [re.compile(r'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_3>[<0-9]+)\s+\[\[(?P<item_3>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_4>[<0-9]+)\s+\[\[(?P<item_4>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(r'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_3>[<0-9]+)\s+\[\[(?P<item_3>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(r'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(r'\|\W*gear=\s*(?P<count_1>[<0-9]+)\W+\[\[(?P<item_1>[^|\]\n]*)\]\]')]

# String to use to replace one item
one_item = r'|gear_%d_count=\g<count_%d>\n|gear_%d=\g<item_%d>'

class GearBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Set of replacement strings, from 4 items down to 1
        self.replacement = []
        for n in range(1,5):
            new_str = one_item % (n, n, n, n)
            try:
                new_str = self.replacement[n-2] + r'\n' + new_str
            except IndexError:
                pass
            self.replacement.append(new_str)
        self.replacement.reverse()

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

    def update_areas(self):
        """
        Creates or updates each page in the Areas category.
        """
        # Update every page in the Areas category
        cat = pywikibot.Category(pywikibot.Site(), u'Areas')

        #for page in list(cat.articles(recurse=True)):
        for page in list(cat.articles(recurse=False)):
            text = page.get()
            for n in range(len(gearRe)):
                text = gearRe[n].sub(self.replacement[n], text)
            # Update the page
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            self.update_or_create_page(page, text);

    def run(self):
        self.update_areas()

def main():
    bot = GearBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

