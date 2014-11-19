#! /usr/bin/python

"""
Script to split the item parameter on Lieutenants pages on Underworld Empire Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')

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
msg_standalone = {
    'en': u'Robot: Split item parameter into separate items and counts',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; split item parameter',
}

# Set of REs to replace, from 3 items down to 1
# TODO Can probably construct these in a similar way to replacement, below
itemRe = [re.compile(ur'\|\W*items=.*$\n^\*\s*\[\[(?P<item_1>[^|\]\n]*).*?\]\]\W+(?P<effect_1>.*)$\n^\*\s*\[\[(?P<item_2>[^|\]\n]*).*?\]\]\W+(?P<effect_2>.*)$\n^\*\s*\[\[(?P<item_3>[^|\]\n]*).*?\]\]\W+(?P<effect_3>.*)', re.MULTILINE),
          re.compile(ur'\|\W*items=.*$\n^\*\s*\[\[(?P<item_1>[^|\]\n]*).*?\]\]\W+(?P<effect_1>.*)$\n^\*\s*\[\[(?P<item_2>[^|\]\n]*).*?\]\]\W+(?P<effect_2>.*)', re.MULTILINE),
          re.compile(ur'\|\W*items=\s*\[\[(?P<item_1>[^|\]\n]*).*?\]\]\W+(?P<effect_1>.*)')]

# String to use to replace one item
one_item = ur'|item_%d=\g<item_%d>\n|item_%d_pwr=\g<effect_%d>'

class ItemBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        pywikibot.setAction(pywikibot.translate(pywikibot.getSite(), msg_standalone))
        # Set of replacement strings, from 4 items down to 1
        self.replacement = []
        for n in range(1,4):
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
            pywikibot.output(new_text)
        pywikibot.showDiff(old_text, new_text)
        # Get a decision
        prompt = u'Modify this page ?'
        # Did anything change ?
        if old_text == new_text:
            pywikibot.output(u'No changes necessary to %s' % old_page.title());
        else:
            if not self.acceptall:
                choice = pywikibot.inputChoice(prompt, ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text)

    def update_lts(self):
        """
        Creates or updates each page in the Lieutenants category.
        """
        # Update every page in the Lieutenants category
        cat = pywikibot.Category(pywikibot.getSite(), u'Lieutenants')

        for page in cat.articlesList(recurse=False):
            text = page.get()
            for n in range(len(itemRe)):
                pywikibot.output("Checking for %d item(s)\n" % (3-n))
                m = itemRe[n].search(text)
                if m is not None:
                    pywikibot.output("Found a match. item_1=%s, effect_1=%s" % (m.group(u'item_1'), m.group(u'effect_1')))
                text = itemRe[n].sub(self.replacement[n], text)
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

