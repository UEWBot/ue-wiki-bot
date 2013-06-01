#! /usr//bin/python

"""
Script to create useful tables on Underworld Empire Wiki
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
    'en': u'Robot: Create/update item summary tables',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; create/update item summary tables',
}

# Categories we're interested in
cat_list = [u'Rifles', u'Handguns', u'Melee Weapons', u'Heavy Weapons', u'Vehicles', u'Gear']

def summary_header(name):
    """
    Returns a summary table page down to the first row of data.
    """
    # Sortable table with borders
    text = u'{| border="1" class="sortable"\n'
    # Name row
    text += u'!span="col" | Name\n'
    # Attack row
    text += u'!span="col" | Attack\n'
    # Defense row
    text += u'!span="col" | Defense\n'
    # Cost row, sorted as currency
    text += u'!span="col" data-sort-type="currency" | Cost\n'
    # Rarity row
    text += u'!span="col" | Rarity\n'

    return text

def summary_footer(name):
    """
    Returns the rest of a summary table, after the last row of data.
    """
    return u'|}'

def page_to_row(page):
    """
    Creates a table row for the item described in page.
    """
    templatesWithParams = page.templatesWithParams()
    row = u'{{Item Row|name=%s' % page.title()
    for (template, params) in templatesWithParams:
        # Ignore the template for now - hopefully there's just the one!
        for param in params:
            # TODO maybe filter out some parameters (description, type, for example)
            row += u'|%s' % param
    row += u'}}'
    # wikipedia.output(u'Row is "%s"' % row)
    return row

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))

    def run(self):
        # Go through cat_list, and create/update summary page for each one
        for name in cat_list:
            # The current summary table page for this category
            old_page = wikipedia.Page(wikipedia.getSite(), u'%s Table' % name)
            # The category of interest
            cat = catlib.Category(wikipedia.getSite(), 'Category:%s' % name)
            # Create one row for each page in the category
            rows = {}
            for page in cat.articlesList():
                rows[page.title()] = page_to_row(page)
            # Start the new page text
            new_text = summary_header(name)
            # Sort rows by item (page) name, and append each one
            for key in sorted(rows.keys()):
                new_text += rows[key] + u'\n'
            # Finish with a footer
            new_text += summary_footer(name)

            wikipedia.output(new_text + u'\n')
            # Read the original content
            try:
                old_text = old_page.get()
                prompt = u'Modify this summary page ?'
            except wikipedia.NoPage:
                old_text = u''
                wikipedia.output("Page %s does not exist" % old_page.title())
                prompt = u'Create this summary page ?'
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

def main():
    #logging.basicConfig()
    bot = XrefBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

