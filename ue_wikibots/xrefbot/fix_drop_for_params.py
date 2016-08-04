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
Script to linkify the for parameter of Drop template uses.

Mostly because we now have items that are "for" multiple recipes,
so we need to change the Drop template to not add the '[[...]]'
to its for parameters, and must instead get the users to supply it.
"""

from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
import difflib
import utils

# Summary message when using this module as a stand-alone script
summary = u'Robot: Modify Drop template for parameter'

class DropBot:

    """Class to update the Drop template for parameter on every page."""

    def __init__(self, acceptall = False):
        """
        Class constructor.

        acceptall -- pass True to not ask for user confirmation before
                     updating pages.
        """
        self.acceptall = acceptall
        self.the_template = u'Template:Drop'

    def _fix_for_param(self, text, params):
        """
        Return text with the specified for parameter (if any) fixed.

        text -- current text of the page.
        params -- list of parameters to the Drop template.
        """
        bad_pages_to_link_to = [u"Enzo's Medallion",
                                u"King's Medallion",
                                u"Diablo's Medallion",
                                u"Raven's Medallion"]
        for_param = utils.param_from_params(params, u'for')
        if for_param:
            try:
                pywikibot.Page(pywikibot.Site(), for_param).get()
            except (pywikibot.NoPage, pywikibot.InvalidTitle):
                # Don't create links to most non-existent pages
                if for_param not in bad_pages_to_link_to:
                    print(("Not linking to non-existent or invalid page '%s'\n" %
                              for_param))
                    return text
            except pywikibot.IsRedirectPage:
                pass
            old_text = text
            text = text.replace(u'|for=%s' % for_param,
                                u'|for=[[%s]]' % for_param,
                                1)
            if text == old_text:
                text = text.replace(u'|for = %s' % for_param,
                                    u'|for=[[%s]]' % for_param,
                                    1)
                if text == old_text:
                    print(("Failed to replace '%s' in:\n%s\n" %
                              (for_param, params)))
        return text

    def treat(self, page):
        """
        Check the page, and update if necessary.

        page -- Page to check.
        """
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            text = page.get()
            old_text = text
            for t,p in page.templatesWithParams():
                if t.title() == self.the_template:
                    text = self._fix_for_param(text, p)
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
        """Call treat() for every page that uses the Drop template."""
        t = pywikibot.Page(pywikibot.Site(), self.the_template)
        for page in t.getReferences(onlyTemplateInclusion=True):
            self.treat(page)

def main():
    bot = DropBot()
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

