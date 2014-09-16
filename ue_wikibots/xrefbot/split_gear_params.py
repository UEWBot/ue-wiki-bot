#! /usr//bin/python

"""
Script to split the gear parameter on Areas pages on Underworld Empire Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia, pagegenerators, catlib
import re, difflib
import logging

# Stuff for the wikipedia help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
msg_standalone = {
    'en': u'Robot: Split gear parameter into separate items and counts',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; split gear parameter',
}

# Set of REs to replace, from 4 items down to 1
# TODO Can probably construct these in a similar way to replacement, below
# TODO This converts e.g. "gear=2 [[Condo]]s" to "gear_1_count=2|gear_1=Condos" with an extra "s"
gearRe = [re.compile(ur'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_3>[<0-9]+)\s+\[\[(?P<item_3>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_4>[<0-9]+)\s+\[\[(?P<item_4>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(ur'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_3>[<0-9]+)\s+\[\[(?P<item_3>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(ur'\|\W*gear=.*$\n^\*\s*(?P<count_1>[<0-9]+)\s+\[\[(?P<item_1>[^|\]\n]*).*\]\]\W*$\n^\*\s*(?P<count_2>[<0-9]+)\s+\[\[(?P<item_2>[^|\]\n]*).*\]\]', re.MULTILINE),
          re.compile(ur'\|\W*gear=\s*(?P<count_1>[<0-9]+)\W+\[\[(?P<item_1>[^|\]\n]*)\]\]')]

# String to use to replace one item
one_item = ur'|gear_%d_count=\g<count_%d>\n|gear_%d=\g<item_%d>'

class GearBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))
        # Set of replacement strings, from 4 items down to 1
        self.replacement = []
        for n in range(1,5):
            new_str = one_item % (n, n, n, n)
            try:
                new_str = self.replacement[n-2] + ur'\n' + new_str
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
            wikipedia.output(new_text)
        wikipedia.showDiff(old_text, new_text)
        # Get a decision
        prompt = u'Modify this page ?'
        # Did anything change ?
        if old_text == new_text:
            wikipedia.output(u'No changes necessary to %s' % old_page.title());
        else:
            if not self.acceptall:
                choice = wikipedia.inputChoice(prompt, ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text)

    def update_areas(self):
        """
        Creates or updates each page in the Areas category.
        """
        # Update every page in the Areas category
        cat = catlib.Category(wikipedia.getSite(), u'Areas')

        #for page in cat.articlesList(recurse=True):
        for page in cat.articlesList(recurse=False):
            text = page.get()
            for n in range(len(gearRe)):
                text = gearRe[n].sub(self.replacement[n], text)
            # Update the page
            wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            self.update_or_create_page(page, text);

    def run(self):
        self.update_areas()

def main():
    #logging.basicConfig()
    bot = GearBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

