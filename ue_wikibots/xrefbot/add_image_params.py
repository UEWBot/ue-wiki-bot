#! /usr/bin/python

"""
Script to insert image parameters to pages on UE Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia, pagegenerators, catlib
import re, difflib
import utils

# Stuff for the wikipedia help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
msg_standalone = {
    'en': u'Robot: Insert image parameters',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; insert image parameters',
}

imgRe = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')

params = [u'gear_1', u'gear_2', u'gear_3', u'gear_4']

class ImgBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))
        # Populate image_map
        self.image_map = {}
        # Loop through every item, property, and ingredient
        cats = [u'Items', u'Properties', u'Ingredients']
        for c in cats:
            cat = catlib.Category(wikipedia.getSite(), u'Category:%s' % c)
            for pg in cat.articles(recurse=True):
                key = pg.titleWithoutNamespace()
                if not key in self.image_map:
                    wikipedia.output("Looking up image for %s" % key)
                    # Retrieve the text of page 'key'
                    text = pg.get()

                    # Extract the image parameter
                    m = imgRe.search(text)
                    if m != None:
                        self.image_map[key] = m.group('image')

    def add_img_param(self, text, param, new_param=None):
        # TODO Don't add it if the image parameter is already there
        strRe = re.compile(ur'\|(?P<prefix>\W*%s\W*=\W*)(?P<value>[^\r]*)' % param)

        # If new_param not provided, use old_param plus "_img"
        if new_param == None:
            new_param = param + u'_img'

        offset = 0
        old_text = text

        for m in strRe.finditer(old_text):
            # Full string we matched
            key = m.group('value')
            old_param = ur'%s%s' % (m.group('prefix'), key)
            wikipedia.output("Adding image for %s" % old_param)
            # New string to insert
            new_str = u'\n|%s=%s' % (new_param, self.image_map[key])
            # Replace the old with old+new, just where we found the match
            # Need to allow for the fact that these additions move other matches
            start = m.start() + offset
            end = m.end() + offset
            offset += len(new_str)
            before = text[:start] 
            after = text[end:]
            middle = re.sub(utils.escapeStr(old_param), u'%s%s' % (old_param, new_str), old_middle)
            text = before + middle + after

        return text

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            # TODO parameter to search for should be passed to the script
            text = page.get()
            old_text = text
            for param in params:
                text = self.add_img_param(text, param)
            # Give the user some context
            if old_text != text:
                wikipedia.output(text)
            wikipedia.showDiff(old_text, text)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing text with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(), text.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = wikipedia.inputChoice(u'Do you want to accept these changes?',  ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                    if choice == 'a':
                        self.acceptall = True
                if self.acceptall or choice == 'y':
                    page.put(text)
            else:
                wikipedia.output('No changes were necessary in %s' % page.title())
        except wikipedia.NoPage:
            wikipedia.output("Page %s does not exist?!" % page.aslink())
        except wikipedia.IsRedirectPage:
            wikipedia.output("Page %s is a redirect; skipping." % page.aslink())
        except wikipedia.LockedPage:
            wikipedia.output("Page %s is locked?!" % page.aslink())

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

    for arg in wikipedia.handleArgs():
        generator = genFactory.handleArg(arg)
        if generator:
            gen = generator
        else:
            pageTitle.append(arg)

    if pageTitle:
        page = wikipedia.Page(wikipedia.getSite(), ' '.join(pageTitle))
        gen = iter([page])
    if not gen:
        wikipedia.showHelp()
    else:
        preloadingGen = pagegenerators.PreloadingGenerator(gen)
        bot = ImgBot(preloadingGen)
        bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

