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

params = [u'gear_1', u'gear_2', u'gear_3', u'gear_4', u'item_1', u'item_2', u'item_3', u'item_4', u'item_5']

class ImgBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))
        # Populate image_map
        self.image_map = {}
        # Don't populate it now - do it on-demand
        return
        # Loop through every item, property, and ingredient
        cats = [u'Items', u'Properties', u'Ingredients']
        for c in cats:
            cat = catlib.Category(wikipedia.getSite(), u'Category:%s' % c)
            for pg in cat.articles(recurse=True):
                self.image_for(pg.titleWithoutNamespace())

    def image_for(self, name):
        """
        Returns the image for the specified item, property, or ingredient.
        Caches results for speed.
        """
        if name not in self.image_map:
            pg = wikipedia.Page(wikipedia.getSite(), name)
            # Retrieve the text of the specified page
            text = pg.get()
            # Extract the image parameter
            m = imgRe.search(text)
            if m != None:
                self.image_map[name] = m.group('image')
        return self.image_map[name]

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
            wikipedia.output("Adding image for %s" % old_param)
            try:
                # New string to insert
                new_str = u'\n|%s=%s' % (new_param, self.image_for(key))
                # Replace the old with old+new, just where we found the match
                # Need to allow for the fact that these additions move other matches
                start = m.start() + offset
                end = m.end() + offset
                offset += len(new_str)
                before = text[:start] 
                after = text[end:]
                middle = re.sub(utils.escapeStr(old_param), u'%s%s' % (old_param, new_str), text[start:end])
                text = before + middle + after
            except wikipedia.NoPage:
                wikipedia.output("Page %s does not exist?!" % key)
            except wikipedia.LockedPage:
                wikipedia.output("Page %s is locked?!" % key)

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

