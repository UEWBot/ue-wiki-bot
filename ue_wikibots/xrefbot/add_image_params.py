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
Script to insert image parameters to pages on UE Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')

import pywikibot, pagegenerators
import re, difflib
import utils

# Stuff for the pywikibot help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
summary = u'Robot: Insert image parameters'

imgRe = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')

params = [u'gear_1', u'gear_2', u'gear_3', u'gear_4', u'item_1', u'item_2', u'item_3', u'item_4', u'item_5']

image_map = utils.ImageMap()

class ImgBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall

    def add_img_param(self, text, param, new_param=None):
        """
        Adds a new image parameter for the specified parameter.
        """
        # TODO Don't add it if the image parameter is already there
        strRe = re.compile(ur'\|(?P<prefix>\W*%s\W*=\s*)(?P<value>[^\r]*)' % param)

        # If new_param not provided, use old_param plus "_img"
        if new_param == None:
            new_param = param + u'_img'

        offset = 0
        old_text = text

        for m in strRe.finditer(old_text):
            # Full string we matched
            key = m.group('value')
            old_param = ur'%s%s' % (m.group('prefix'), key)
            pywikibot.output("Adding image for %s" % old_param)
            try:
                # New string to insert
                new_str = u'\n|%s=%s' % (new_param, image_map.image_for(key))
                # Replace the old with old+new, just where we found the match
                # Need to allow for the fact that these additions move other matches
                start = m.start() + offset
                end = m.end() + offset
                offset += len(new_str)
                before = text[:start] 
                after = text[end:]
                middle = re.sub(utils.escapeStr(old_param), u'%s%s' % (old_param, new_str), text[start:end])
                text = before + middle + after
            except pywikibot.NoPage:
                pywikibot.output("Page %s does not exist?!" % key)
            except pywikibot.LockedPage:
                pywikibot.output("Page %s is locked?!" % key)

        return text

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            # TODO parameter to search for should be passed to the script
            text = page.get()
            old_text = text
            for param in params:
                text = self.add_img_param(text, param)
            # Give the user some context
            if old_text != text:
                pywikibot.output(text)
            pywikibot.showDiff(old_text, text)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing text with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(), text.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = pywikibot.input_choice(u'Do you want to accept these changes?',  [('Yes', 'Y'), ('No', 'n'), ('All', 'a')], 'N')
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
        for page in self.generator:
            self.treat(page)

def main():
    #page generator
    gen = None
    pageTitle = []
    # This factory is responsible for processing command line arguments
    # that are also used by other scripts and that determine on which pages
    # to work on.
    genFactory = pagegenerators.GeneratorFactory()

    for arg in pywikibot.handleArgs():
        if not genFactory.handleArg(arg):
            pageTitle.append(arg)

    gen = genFactory.getCombinedGenerator()

    if pageTitle:
        page = pywikibot.Page(pywikibot.Site(), ' '.join(pageTitle))
        gen = iter([page])
    if not gen:
        pywikibot.showHelp()
    else:
        preloadingGen = pagegenerators.PreloadingGenerator(gen)
        bot = ImgBot(preloadingGen)
        bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

