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
Script to use the BossStage template in all Bosses
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import re
import pywikibot
import difflib
import utils

# Summary message when using this module as a stand-alone script
summary = u'Robot: Use BossStage template'

class DropBot:

    """Class to insert the BossStage template on every page."""

    def __init__(self, acceptall = False):
        """
        Class constructor.

        acceptall -- pass True to not ask for user confirmation before
                     updating pages.
        """
        self.acceptall = acceptall

    def treat(self, page):
        """
        Check the page, and update if necessary.

        page -- Page to check.
        """
        MINION_RE = r'\* ?(?P<name>.*) \(\{\{Class Img\|(?P<class>.*)\|\|?20px\}\}\)'
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            text = page.get()
            old_text = text
            for stage in range(1,12):
                (first, last) = utils.find_specific_section(text, u'Stage %d' % stage)
                if (first != -1):
                    minions = []
                    # First try with HP values
                    for m in re.finditer(r'%s \((?P<hp>.*)HP\)' % MINION_RE, text[first:last]):
                        minions.append({u'name': m.group(u'name'), u'class': m.group(u'class'), u'hp': m.group(u'hp')})
                    # If we didn't find any, try without
                    if len(minions) == 0:
                        for m in re.finditer(MINION_RE, text[first:last]):
                            minions.append({u'name': m.group(u'name'), u'class': m.group(u'class')})
                    # Now create a new section using the template
                    new_sect = u'\n{{BossStage'
                    count = 1
                    for m in minions:
                        new_sect += u'|Name_0%d=%s|Class_0%d=%s' % (count, m[u'name'], count, m[u'class'])
                        try:
                            new_sect += u'|Minion_0%d_HP=%s' % (count, m[u'hp'])
                        except KeyError:
                            pass
                        count += 1
                    new_sect += u'}}\n'
                    # If we have something worthwhile, insert it in place of the old section
                    if (new_sect != u'\n{{BossStage}}\n'):
                        text = u'%s%s%s' % (text[:first], new_sect, text[last:])
            # Give the user some context
            pywikibot.showDiff(old_text, text)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing text with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(),
                                          text.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = pywikibot.input_choice(u'Do you want to accept these changes?',
                                                    [('Yes', 'Y'),
                                                     ('No', 'n'),
                                                     ('All', 'a')],
                                                    'N')
                    if choice == 'a':
                        self.acceptall = True
                if self.acceptall or choice == 'y':
                    page.put(text, summary)
            else:
                pywikibot.output('No changes were necessary in %s' % page.title())
        except pywikibot.NoPage:
            pywikibot.output("Page %s does not exist?!" % page.title(asLink=True))
        except pywikibot.IsRedirectPage:
            pywikibot.output("Page %s is a redirect; skipping." % page.title(asLink=True))
        except pywikibot.LockedPage:
            pywikibot.output("Page %s is locked?!" % page.title(asLink=True))

    def run(self):
        """Call treat() for every Boss page."""
        cat = pywikibot.Category(pywikibot.Site(),
                                 u'Category:Bosses')
        #all_cats = set(c.title(withNamespace=False) for c in cat.subcategories(recurse=True))
        #all_cats.append(cat)
        pages = cat.articles(recurse=True)
        for page in pages:
            self.treat(page)

def main():
    bot = DropBot()
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

