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

# Handy regular expressions
item_templates = re.compile(u'.*\WItem')
property_templates = re.compile(u'.*\WProperty')
job_templates = re.compile(u'.*Job')
lieutenant_templates = re.compile(u'Lieutenant\W(.*)')

def summary_header(row_template):
    """
    Returns a summary table page down to the first row of data.
    """
    # Warn editors that the page was generated
    text = u'<!-- This page was generated/modified by software -->\n'
    # No WYSIWYG editor
    text += u'__NOWYSIWYG__\n'
    # Sortable table with borders
    text += u'{| border="1" class="sortable"\n'
    if row_template == u'Item Row':
        # Name column
        text += u'!span="col" | Name\n'
        # Attack column
        text += u'!span="col" | Attack\n'
        # Defense column
        text += u'!span="col" | Defense\n'
        # Cost column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Cost\n'
        # Rarity column
        text += u'!span="col" | Rarity\n'
    elif row_template == u'Property Rows':
        # Number column
        text += u'!span="col" | #\n'
        # Name column
        text += u'!span="col" | Name\n'
        # Cost column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Cost\n'
        # Income column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Income\n'
        # Time to recoup cost column
        text += u'!span="col" | Hrs to recoup\n'
    elif row_template == u'Job Row':
        # District column
        text += u'!span="col" rowspan="2" | District\n'
        # Job name column
        text += u'!span="col" rowspan="2" | Job\n'
        # Faction column
        text += u'!span="col" rowspan="2" | Faction\n'
        # Energy column
        text += u'!span="col" rowspan="2" | Energy\n'
        # Cash columns
        text += u'!colspan="2" class="unsortable" | Cash\n'
        # XP columns
        text += u'!colspan="2" class="unsortable" | XP\n'
        # Cash/energy column
        text += u'!span="col" rowspan="2" data-sort-type="currency" | Cash/energy\n'
        # XP/energy Column
        text += u'!span="col" rowspan="2" | XP/energy\n'
        text += u'|-\n'
        # Min Cash column
        text += u'!span="col" data-sort-type="currency" | Min\n'
        # Max Cash column
        text += u'!span="col" data-sort-type="currency" | Max\n'
        # Min XP column
        text += u'!span="col" | Min\n'
        # Max XP column
        text += u'!span="col" | Max\n'
    else: # Lieutenant Row
        # Name column
        text += u'!span="col" rowspan="2" | Name\n'
        # Faction column
        text += u'!span="col" rowspan="2" | Faction\n'
        # Rarity column
        text += u'!span="col" rowspan="2" | Rarity\n'
        # Atk & Def for each number of stars
        for stars in range(1,10):
            text += u'!colspan="3" class="unsortable" | %d Star\n' % stars
        text += u'|-\n'
        for stars in range(1,10):
            text += u'!span="col" | Atk\n'
            text += u'!span="col" | Def\n'
            text += u'!span="col" class="unsortable" | Power\n'

    return text

def summary_footer(row_template):
    """
    Returns the rest of a summary table, after the last row of data.
    """
    return u'|}'

def page_to_row(page, row_template):
    """
    Creates a table row for the item described in page.
    """
    templatesWithParams = page.templatesWithParams()
    row = u'{{%s|name=%s' % (row_template, page.title())
    for (template, params) in templatesWithParams:
        # We're only interested in certain templates
        if item_templates.search(template) or property_templates.search(template):
            # Use all the item and property template parameters for now
            for param in params:
                row += u'|%s' % param
        else:
            match = lieutenant_templates.search(template)
            if match:
                # Construct a rarity parameter from the template name
                row += u'|rarity=%s' % match.group(1)
                # Use all the item template parameters for now
                for param in params:
                    row += u'|%s' % param
    row += u'}}'
    # wikipedia.output(u'Row is "%s"' % row)
    return row

def page_to_rows(page, row_template):
    # TODO Look at combining this function and page_to_row().
    """
    Creates a table row for each job described in page.
    """
    row_stub = u'{{%s|district=%s' % (row_template, page.title())
    templatesWithParams = page.templatesWithParams()
    rows = []
    for (template, params) in templatesWithParams:
        # We're only interested in certain templates
        if job_templates.search(template):
            # Create a new row
            row = row_stub
            # Use all the item, property, and job template parameters for now
            for param in params:
                row += u'|%s' % param
            row += u'}}'
            # wikipedia.output(u'Row is "%s"' % row)
            # Add the new row to the list
            rows.append(row)
    return rows

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))

    def update_or_create_page(self, old_page, new_text):
        """
        Reads the current text of page old_page,
        compare it with new_text, prompts the user,
        and uploads the page
        """
        # Read the original content
        try:
            old_text = old_page.get()
            wikipedia.showDiff(old_text, new_text)
            prompt = u'Modify this summary page ?'
        except wikipedia.NoPage:
            old_text = u''
            wikipedia.output("Page %s does not exist" % old_page.title())
            wikipedia.output(new_text)
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

    def update_properties_table(self):
        """
        Creates or updates page Properties Table from the
        content of the Income Properties and Upgrade Properties
        categories.
        """
        # Categories we're interested in
        cats = {u'Income Properties', u'Upgrade Properties'}
        row_template = u'Property Rows'

        old_page = wikipedia.Page(wikipedia.getSite(), u'Properties Table')
        rows = []
        for name in cats:
            cat = catlib.Category(wikipedia.getSite(), u'Category:%s' % name)
            # One row per page in category
            for page in cat.articlesList():
                rows.append(page_to_row(page, row_template))
        # Start the new page text
        new_text = summary_header(row_template)
        # TODO: Sort rows into some sensible order
        for row in rows:
            new_text += row + u'\n'
        # Finish with a footer
        new_text += summary_footer(row_template)
        # Upload it
        self.update_or_create_page(old_page, new_text);

    def update_jobs_table(self):
        """
        Creates or updates page Jobs Table from the
        content of the Districts category.
        """
        # Categories we're interested in
        row_template = u'Job Row'

        old_page = wikipedia.Page(wikipedia.getSite(), u'Jobs Table')
        rows = []
        cat = catlib.Category(wikipedia.getSite(), u'Districts')
        # One row per use of the template on a page in category
        for page in cat.articlesList():
            rows += page_to_rows(page, row_template)
        # Start the new page text
        new_text = summary_header(row_template)
        # TODO: Sort rows into some sensible order
        for row in rows:
            new_text += row + u'\n'
        # Finish with a footer
        new_text += summary_footer(row_template)
        # Upload it
        self.update_or_create_page(old_page, new_text);

    def update_most_tables(self):
        """
        Creates or updates these pages from the corresponding categories:
        Rifles Table
        Handguns Table
        Melee Wepaons Tale
        Heavy Weapons Table
        Vehicles Table
        Gear Table
        Lieutenants Table
        """
        # Categories we're interested in and row template to use for each category
        cat_to_templ = { u'Rifles': 'Item Row', u'Handguns': 'Item Row', u'Melee Weapons': 'Item Row', u'Heavy Weapons': 'Item Row', u'Vehicles': 'Item Row', u'Gear': 'Item Row', u'Lieutenants': 'Lieutenant Row'}

        # Go through cat_to_templ, and create/update summary page for each one
        for name, template in cat_to_templ.iteritems():
            # The current summary table page for this category
            old_page = wikipedia.Page(wikipedia.getSite(), u'%s Table' % name)
            # The category of interest
            cat = catlib.Category(wikipedia.getSite(), u'Category:%s' % name)
            # Create one row for each page in the category
            rows = {}
            for page in cat.articlesList():
                rows[page.title()] = page_to_row(page, template)
            # Start the new page text
            new_text = summary_header(template)
            # Sort rows by item (page) name, and append each one
            for key in sorted(rows.keys()):
                new_text += rows[key] + u'\n'
            # Finish with a footer
            new_text += summary_footer(template)
            # Upload it
            self.update_or_create_page(old_page, new_text);

    def run(self):
        self.update_most_tables()
        self.update_properties_table()
        self.update_jobs_table()

def main():
    #logging.basicConfig()
    bot = XrefBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

