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
Script to add a new area page to the UE Wiki.

Arguments:
name of the new area
boss name
name of the area it comes after
"""

from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import operator
from six.moves import range
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import argparse
import pywikibot
import parse
import difflib
import utils

# Summary message when using this module as a stand-alone script
summary = u'Robot: Insert new area'

number_map = {
    1: u'first',
    2: u'second',
    3: u'third',
    4: u'fourth',
    5: u'fifth',
    6: u'sixth',
    7: u'seventh',
    8: u'eighth',
    9: u'ninth',
    10: u'tenth',
    11: u'eleventh',
    12: u'twelfth',
    13: u'thirteenth',
    14: u'fourteenth',
    15: u'fifteenth',
    16: u'sixteenth',
    17: u'seventeenth',
    18: u'eighteenth',
    19: u'nineteenth',
    20: u'twentieth',
}

stub_area_page = u"""
__NOWYSIWYG__
[[File:district_%s.jpg|thumb|400px|Map of the %s area]]
''<intro text>''

This is the %s [[:Category:Areas|area]] in the game, u%s %s

There are some number of jobs in this area, including the [[#Challenge Job|challenge job]], plus an additional 16 [[#Secret Jobs - 1|secret jobs]] (not yet available).

Completing some job makes the [[%s]] boss available.

==Main Jobs==
{{Job
}}

==Challenge Job==
The challenge job becomes available when you have completed some job.
{{Challenge Job
}}

==Secret Jobs - 1==
The secret jobs area(s) cannot currently be accessed, but will presumably unlock when all regular jobs have been completed to five [[Stars (Job)|stars]]. Secret jobs within one secret area have to be completed in sequence. The next one becomes available when the previous one has been completed to 5 stars. It contains the following jobs:

==Secret Jobs - 2==
The secret jobs area(s) cannot currently be accessed, but will presumably unlock when all regular jobs have been completed to five [[Stars (Job)|stars]]. Secret jobs within one secret area have to be completed in sequence. The next one becomes available when the previous one has been completed to 5 stars. It contains the following jobs:

[[Category:Areas]]
[[Category:Needs Information]]
"""

stub_boss_page = """
__NOWYSIWYG__
[[File:boss_%s.png|right|300px]]
''%s'' is available when you have completed some job in the [[%s]] [[:Category:Areas|area]], giving you some item.
==Basic Information==
Up to some number of people may participate in the fight.

You have some number of hours to complete the fight.
==Speed Kills==
:1 Star :
:2 Star :
:3 Star :
==Stages==

==Recommended Class==

==[[Boss Drops|Rewards]]==
==={{Epic}} Thresholds===
# points
# points
# points
==={{Epic}} Rewards===
{{drop}}
==={{Rare}} Rewards===
{{drop}}
==={{Uncommon}} Rewards===
{{drop}}
==={{Common}} Rewards===
{{drop}}
==Completion Dialogue==
[[Category:Job Bosses]]
[[Category:Needs Information]]
"""

class AreaBot:

    """Class to deal with adding a new area page to the UE wiki."""

    def __init__(self, area_name, after, boss_name, acceptall = False):
        self.area_name = area_name
        self.after = after
        self.boss_name = boss_name
        self.acceptall = acceptall
        self.area_cat = pywikibot.Category(pywikibot.Site(), u'Areas')
        self.jobs_page = pywikibot.Page(pywikibot.Site(), u'Jobs')
        self.jobs_page_text = self.jobs_page.get()
        self.areas_list = utils.areas_in_order(self.jobs_page_text)
        self.new_number = self.areas_list.index(self.after) + 1

    def _area_image_name(self):
        """Return the area image string filename."""
        return u'district %s.png' % self.area_name.lower()

    def _boss_image_name(self):
        """Return the boss image string filename."""
        return u'boss %s.png' % self.boss_name.lower()

    def _add_to_jobs_page(self):
        """Add the new area to the Jobs page."""
        areas = len(self.areas_list)
        new_line = u'#[[%s]] ([[%s]] boss)\n' % (self.area_name, self.boss_name)
        text = self.jobs_page_text.replace(u'There are currently %d [[' % areas,
                                           u'There are currently %d [[' % (areas + 1))
        if self.new_number in self.areas_list:
            # TODO This doesn't work if there's whitespace in the following line
            line_after = u'#[[%s]] ' % self.areas_list[self.new_number]
        else:
            line_after = u'[[Category:Content]]'
        text = text.replace(line_after, new_line + line_after)
        self._update_page(self.jobs_page, self.jobs_page_text, text)

    def _add_to_bosses_page(self):
        areas = len(self.areas_list)
        new_line = u'*[[File:%s|100px]] [[%s]] in the [[%s]] area' % (self._boss_image_name(),
                                                                      self.boss_name,
                                                                      self.area_name)
        page = pywikibot.Page(pywikibot.Site(), u'Bosses')
        text = old_text = page.get()
        intro = u'There are currently %s bosses in the game, %s'
        bosses = parse.search(intro % (u'{:d}', u''), text).fixed[0]
        line_before = u' in the [[%s]] area' % self.after
        intro = intro % (u'%d', u'%d')
        text = text.replace(intro % (bosses, areas),
                            intro % ((bosses + 1, areas + 1)))
        text = text.replace(line_before,
                            line_before + u'\n' + new_line)
        self._update_page(page, old_text, text)

    def _update_area_numbers(self):
        """Update the number of every later area page."""
        for i in range(self.new_number + 1, len(self.areas_list)):
            page = pywikibot.Page(pywikibot.Site(), self.areas_list[i])
            old_text = page.get()
            text = old_text.replace(number_map[i + 1], number_map[i + 2])
            self._update_page(page, old_text, text)

    def _update_achievements(self):
        """Update the "5-star an area" achievements."""
        # This doesn't add any new achievements
        page = pywikibot.Page(pywikibot.Site(), u'Achievements')
        text = old_text = page.get()
        # We don't insert an achievement for the new area
        # TODO When inserting the new area at the end,
        #      this wrongly updates the number of the last existing area
        for i in range(self.new_number, len(self.areas_list) + 1):
            name = self.areas_list[i - 1]
            print(u'[[%s|Area %d]]' % (name, i))
            print(u'[[%s|Area %d]]' % (name, i + 1))
            text = text.replace(u'[[%s|Area %d]]' % (name, i),
                                u'[[%s|Area %d]]' % (name, i + 1))
        # We also don't add any achievements for the new boss
        self._update_page(page, old_text, text)

    def _update_previous_area(self):
        """Update the area before the new one."""
        page = pywikibot.Page(pywikibot.Site(), self.after)
        old_text = page.get()
        link = u'Completing %s job unlocks the [[%s]] area.'
        if self.new_number in self.areas_list:
            job = parse.search(link % (u'{}', self.areas_list[self.new_number]),
                               old_text).fixed[0]
            link = link % (job, u'%s')
            text = old_text.replace(link % self.areas_list[self.new_number],
                                    link % self.area_name)
        else:
            final = u'It is currently the final area.'
            text = old_text.replace(final, link % (u'some', self.area_name))
        self._update_page(page, old_text, text)

    def _update_next_area(self):
        """
        Update the area after the new one.

        Return the unlock link for the new area.
        """
        # Some have this phrase in it's own sentence, others don't
        link = u'nlocked once you have completed %s in [[%s]].'
        if self.new_number not in self.areas_list:
            # New area is the last one
            return link % (u'some job', self.after)
        page = pywikibot.Page(pywikibot.Site(),
                              self.areas_list[self.new_number])
        old_text = page.get()
        # Also replace the area number while we're there
        i = self.new_number + 1
        text = old_text.replace(number_map[i], number_map[i+1])
        job = parse.search(link % (u'{}', self.after),
                           old_text).fixed[0]
        old_link = link % (job, self.after)
        text = text.replace(old_link,
                            link % (u'some job', self.area_name))
        self._update_page(page, old_text, text)
        # Return the link so it can go in the new page
        return old_link

    def _add_new_area_page(self, link):
        """
        Add the actual area page itself.

        link -- text to use to link to the following area page.
        """
        page = pywikibot.Page(pywikibot.Site(), self.area_name)
        if self.new_number in self.areas_list:
            next_area = u'Completing some job unlocks the [[%s]] area.' % self.areas_list[self.new_number]
        else:
            next_area = u'It is currently the final area.'
        text = stub_area_page % (self.area_name.lower(),
                                 self.area_name,
                                 number_map[self.new_number],
                                 link,
                                 next_area,
                                 self.boss_name)
        self._update_page(page, u'', text)

    def _add_new_boss_page(self):
        """Add the new boss page."""
        page = pywikibot.Page(pywikibot.Site(), self.boss_name)
        text = stub_boss_page % (self.boss_name.lower(),
                                 self.boss_name,
                                 self.area_name)
        self._update_page(page, u'', text)

    def _add_area(self):
        """
        Adds the new area.
        """
        # Find and modify the link from the preceding area
        self._update_previous_area()
        # Find and modify the link from the subsequent area
        link = self._update_next_area()
        # Change the ordinal of all subsequent areas
        self._update_area_numbers()
        # Update the list on the Jobs page
        self._add_to_jobs_page()
        # Update the list on the Bosses page
        self._add_to_bosses_page()
        # Update Achievements page
        self._update_achievements()
        # Insert the new area page
        self._add_new_area_page(link)
        # Insert the new boss page
        self._add_new_boss_page()

    def _update_page(self, page, old_text, new_text):
        """
        Update the specified page.

        page -- page to update.
        old_text -- original page text.
        new_text -- new text for the page.
        """
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            pywikibot.showDiff(old_text, new_text)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing text with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(old_text.splitlines(),
                                          new_text.splitlines()):
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
                    page.put(new_text, summary)
            else:
                pywikibot.output('No changes were necessary in %s' % page.title())
        except pywikibot.NoPage:
            pywikibot.output("Page %s does not exist?!" % page.title(asLink=True))
        except pywikibot.IsRedirectPage:
            pywikibot.output("Page %s is a redirect; skipping." % page.title(asLink=True))
        except pywikibot.LockedPage:
            pywikibot.output("Page %s is locked?!" % page.title(asLink=True))

    def run(self):
        self._add_area()

def main(area_name, after, boss_name):
    bot = AreaBot(area_name, after, boss_name)
    bot.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add an area page to the wiki')
    parser.add_argument('area_name', help="Name of the new area")
    parser.add_argument('after', help="Name of the area before the new one")
    parser.add_argument('boss_name', help="Name of the new boss")
    args = parser.parse_args()
    try:
        main(args.area_name, args.after, args.boss_name)
    finally:
        pywikibot.stopme()

