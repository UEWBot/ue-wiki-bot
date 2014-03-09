#! /usr//bin/python

"""
Script to create useful tables on Underworld Empire Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia, pagegenerators, catlib
import re, difflib
import logging
import utils

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

def name_to_link(name):
    """
    Takes the name of a page and returns wiki markup for a link,
    converting disambiguated pages.
    e.g. "Dog (pet)" -> "[[Dog (pet)|Dog]]".
    """
    paren = name.find('(')
    if paren == -1:
        page = name
    else:
        page = name + u'|' + name[0:paren-1]
    return u'[[' + page + u']]'

def oneParam(params, the_param):
    """
    Takes the list of parameters for a template, and returns
    the value (if any) for the specified parameter.
    Returns an empty string if the parameter is not present.
    """
    for one_param in params:
        match = re.search(r'\s*%s\s*=([^\|]*)' % the_param, one_param, re.MULTILINE)
        if match:
            return match.expand(r'\1')
    return u''

def lt_faction_rarity_header(factions):
    """
    Returns a summary table down to the first row of data.
    """
    # Warn editors that the page was generated
    text = u'<!-- This page was generated/modified by software -->\n'
    # No WYSIWYG editor
    text += u'__NOWYSIWYG__\n'
    text += u'{| border="1" class="wikitable"\n'
    text += u'!span="col" | \n'
    for faction in factions:
        text += u'!span="col" | [[%s]]\n' % faction
    return text

def lt_faction_rarity_row(factions, rarity, lieutenants_by_faction):
    """
    Returns a row for the specified rarity.
    """
    text = u'|-\n'
    text += u'!scope=row | {{%s}}\n' % rarity
    for faction in factions:
        text += u'|'
        if faction in lieutenants_by_faction:
            text += u'<br/>'.join(map(name_to_link,lieutenants_by_faction[faction]))
        else:
            text += u'None'
        text += u'\n'
    return text
 
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
        text += u'!span="col" data-sort-type="number" | Attack\n'
        # Defense column
        text += u'!span="col" data-sort-type="number" | Defense\n'
        # Cost column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Cost\n'
        # Rarity column
        text += u'!span="col" | Rarity\n'
        # Three summary stats columns
        text += u'!span="col" data-sort-type="number" | Atk+Def\n'
        text += u'!span="col" data-sort-type="number" | Atk+70% of Def\n'
        text += u'!span="col" data-sort-type="number" | 70% of Atk + Def\n'
    elif row_template == u'Property Row':
        # Number column
        text += u'!span="col" data-sort-type="number" | Level\n'
        # Name column
        text += u'!span="col" | Name\n'
        # Cost column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Cost\n'
        # Income column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Income\n'
        # Time to recoup cost column
        text += u'!span="col" data-sort-type="number" | Hrs to recoup\n'
        # Unlock criteria
        text += u'!span="col" | Prerequisite(s)\n'
    elif row_template == u'Job Row':
        # District column
        text += u'!span="col" | District\n'
        # Job name column
        text += u'!span="col" | Job\n'
        # Faction column
        text += u'!span="col" | Faction\n'
        # Energy columns
        text += u'!span="col" data-sort-type="number" | Energy\n'
        text += u'!span="col" data-sort-type="number" | Total Energy\n'
        # Cash columns
        text += u'!span="col" data-sort-type="currency" | Min Cash\n'
        text += u'!span="col" data-sort-type="currency" | Max Cash\n'
        # XP columns
        text += u'!span="col" data-sort-type="number" | Min XP\n'
        text += u'!span="col" data-sort-type="number" | Max XP\n'
        # Cash/energy column
        text += u'!span="col" data-sort-type="currency" | Cash/energy\n'
        # XP/energy Column
        text += u'!span="col" data-sort-type="number" | XP/energy\n'
    elif row_template == u'Lieutenant Row':
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
            text += u'!span="col" data-sort-type="number" | Atk\n'
            text += u'!span="col" data-sort-type="number" | Def\n'
            text += u'!span="col" class="unsortable" | Power\n'
    else:
        wikipedia.output("Unexpected row template %s" % row_template)

    return text

def summary_footer(row_template):
    """
    Returns the rest of a summary table, after the last row of data.
    """
    return u'|}\n[[Category:Summary Tables]]'

def prop_cost_basic(base_cost, level):
    """
    Calculates the cost for the specified level of a property.
    """
    return base_cost * (1 + (level-1)/10.0)

def prop_cost_high(base_cost, level):
    """
    Calculates the cost for the specified level of a property.
    """
    #TODO: Extract this table from the Fortress page
    lvl_to_ratio = {1: 1.0,
                    2: 1.25,
                    3: 1.5,
                    4: 2.0,
                    5: 2.5,
                    6: 3.2}
    if level in lvl_to_ratio:
        return lvl_to_ratio[level] * base_cost
    return 0

def prop_cost(base_cost, level, high_cost=False):
    """
    Calculates the cost for the specified level of a property.
    """
    if high_cost:
        return prop_cost_high(base_cost, level)
    return prop_cost_basic(base_cost, level)

def property_row(name, d, count):
    """
    Returns a property row line for the specified property.
    name is the name of the property.
    d is a dict of template parameters.
    count is the level of the property.
    """
    # We need to provide count, name, cost, income, and unlock
    # We have name and count.
    row = u'{{Property Row|name=%s|count=%d' % (name, count)
    # Income comes straight from the corresponding parameter, if present.
    if u'income' in d:
        row += u'|income=%s' % d[u'income']
    else:
        row += u'|income=1000'
    # Unlock we need to construct from a number of things
    unlock = u''
    if count == 1 and u'unlock_area' in d:
        unlock += u'[[%s]] open' % d[u'unlock_area']
    if u'unlock_prop' in d:
        if u'plus_one' in d:
            if count > 1:
                unlock += 'level %d [[%s]]' % (count - 1, d[u'unlock_prop'])
        else:
            unlock += u'level %d [[%s]]' % (count, d[u'unlock_prop'])
    if count > 10:
        unlock += u'level %d [[%s]]' % (count - 10, u'Fortress')
    if count > 1:
        if len(unlock) > 0:
            unlock += u' and '
        unlock += u'level %d [[%s]]' % (count - 1, name)
    if u'fp_prop'in d:
        # Override the unlock string we've created
        unlock = u'Buy [[Favor Point]]s during promo in %s' % d[u'fp_prop']
    row += u'|unlock=%s' % unlock
    # We derive cost from the template cost, count, and whether it is "high_cost" or not.
    if u'cost' in d:
        base_cost = float(d[u'cost'].replace(u',',u''))
    else:
        base_cost = 0.0
    if u'high_cost' in d:
        high_cost=True
    else:
        high_cost=False
    row += u'|cost=%d}}' % prop_cost(base_cost, count, high_cost)
    return row

def safe_house_rows(name, text, row_template):
    """
    Returns rows for Properties Table for the Safe House page
    """
    rows = []
    # Find the info we need - income, unlock criteria, cost
    # Look for an "Income" line
    match = re.search(ur'Income: (.*)', text)
    if match == None:
        wikipedia.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
    # Look for an "Unlock" line
    match = re.search(ur'Unlocked when (.*)', text)
    if match == None:
        wikipedia.output("Failed to find Unlock criteria for %s" % name)
        unlock = u'Unknown'
    else:
        unlock = match.group(1)
    # Find a table of costs
    for match in re.finditer(ur'\|\W*(?P<count>\d+)\W*\|\|\W*(?P<cost>.*)\W*\|\|.*\|\|',
                             text, re.IGNORECASE):
        d = match.groupdict()
        count = int(d['count'])
        # This assumes that rows are in numerical order, which should be true
        if count > 1:
            unlock = u'Level %d [[%s]]' % (count-1, name)
        # Don't bother with the "level 0" one
        if count > 0:
            row = u'{{%s|name=%s|count=%d|income=%s|unlock=%s|cost=%s}}' % (row_template, name, count, income, unlock, d['cost'])
            rows.append(row)
    
    return rows

def fortress_rows(name, text, row_template):
    """
    Returns rows for Properties Table for the Fortress page
    """
    rows = []
    # Find the info we need - income, unlock criteria, cost
    # Look for an "Income" line
    match = re.search(ur'Income: (.*)', text)
    if match == None:
        wikipedia.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
    # Find a table of unlock criteria
    match = re.search(ur'\|\W*1\W*\|\|\D*(?P<cost>\d+)\D*\|\|.*', text)
    if match == None:
        wikipedia.output("Failed to find level 1 cost for %s" % name)
        cost = 0.0
    else:
        cost = float(match.group(1))
    for match in re.finditer(ur'\|\W*(?P<count>\d+)\W*\|\|.*\|\|\W*\[\[(?P<prop>.*)\]\]\D*(?P<lvl>\d+)',
                             text, re.IGNORECASE):
        d = match.groupdict()
        count = int(d['count'])
        unlock = u'level %s [[%s]]' % (d['lvl'], d['prop'])
        if count > 1:
            unlock = u'Level %d [[%s]] and ' % (count-1, name) + unlock
        row = u'{{%s|name=%s|count=%d|income=%s|unlock=%s|cost=%d}}' % (row_template, name, count, income, unlock, prop_cost_high(cost, count))
        rows.append(row)
    # Add extra rows for unknown prerequisites
    for c in range(count+1,11):
        row = u'{{%s|name=%s|count=%d|income=%s|unlock=%s|cost=%d}}' % (row_template, name, c, income, u'Unknown', prop_cost_high(cost, c))
        rows.append(row)
    
    return rows

def page_to_row(page, row_template):
    """
    Creates a table row for the item described in page.
    """
    templatesWithParams = page.templatesWithParams()
    row = u'{{%s|name=%s' % (row_template, page.title())
    for (template, params) in templatesWithParams:
        # We're only interested in certain templates
        if item_templates.search(template):
            # Pass all the item template parameters
            for param in params:
                row += u'|%s' % param
        else:
            match = lieutenant_templates.search(template)
            if match:
                # Construct a rarity parameter from the template name
                row += u'|rarity=%s' % match.group(1)
                # Pass all the lieutenant template parameters
                for param in params:
                    row += u'|%s' % param
    row += u'}}'
    # wikipedia.output(u'Row is "%s"' % row)
    return row

def page_to_rows(page, row_template):
    # TODO Look at combining this function and page_to_row().
    """
    Returns a list of table rows for the jobs or property described in page.
    """
    templatesWithParams = page.templatesWithParams()
    rows = []
    for (template, params) in templatesWithParams:
        # We're only interested in certain templates
        if job_templates.search(template):
            row_stub = u'{{%s|district=%s' % (row_template, page.title())
            # Create a new row
            row = row_stub
            # Use all the item, property, and job template parameters for now
            for param in params:
                row += u'|%s' % param
            row += u'}}'
            # wikipedia.output(u'Row is "%s"' % row)
            # Add the new row to the list
            rows.append(row)
        elif property_templates.search(template):
            d = utils.paramsToDict(params)
            # Figure out how many rows we need
            if u'fp_prop'in d:
                max = 5
            elif template == u'Income Property':
                max = 20
            else:
                max = 10
            for count in range(1, max + 1):
                rows.append(property_row(page.title(), d, count))
    return rows

def rarities():
    """
    Returns an ordered list of rarities.
    """
    # TODO Dynamically create the list from the rarity page
    rarities = []
    page = wikipedia.Page(wikipedia.getSite(), u'Rarity')
    return [u'Common', u'Uncommon', u'Rare', u'Epic', u'Legendary']

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
        content of the Properties category.
        """
        # Categories we're interested in
        the_cat = u'Properties'
        # Template we're going to use
        row_template = u'Property Row'

        old_page = wikipedia.Page(wikipedia.getSite(), u'Properties Table')

        rows = []
        cat = catlib.Category(wikipedia.getSite(), the_cat)
        for page in cat.articlesList(recurse=True):
            new_rows = page_to_rows(page, row_template)
            if len(new_rows):
                rows += new_rows
            elif page.title() == u'Fortress':
                rows += fortress_rows(page.title(), page.get(), row_template)
            elif page.title() == u'Safe House':
                rows += safe_house_rows(page.title(), page.get(), row_template)
            else:
                wikipedia.output("Unexpected non-template property page %s" % page.title())

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

    def update_lt_rarity_table(self):
        """
        Creates or updates page Lieutenants Faction Rarity Table
        from the content of the Lieutenants category.
        """
        old_page = wikipedia.Page(wikipedia.getSite(), u'Lieutenants Faction Rarity Table')
        factions = []
        cat = catlib.Category(wikipedia.getSite(), u'Factions')
        for faction in cat.articlesList():
            factions.append(faction.title())
        new_text = lt_faction_rarity_header(factions)
        for rarity in rarities():
            lieutenants = {}
	    lt_cat = catlib.Category(wikipedia.getSite(), u'%s Lieutenants' % rarity)
            for lt in lt_cat.articlesList():
                name = lt.title()
                templatesWithParams = lt.templatesWithParams()
                for (template, params) in templatesWithParams:
                    match = lieutenant_templates.search(template)
                    if match:
                        faction = oneParam(params, u'faction')
                        if faction not in lieutenants:
                            lieutenants[faction] = []
                        lieutenants[faction].append(name)
            if len(lieutenants) > 0:
                new_text += lt_faction_rarity_row(factions, rarity, lieutenants)
        new_text += summary_footer(None)
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
        cat_to_templ = {u'Rifles': 'Item Row',
                        u'Handguns': 'Item Row',
                        u'Melee Weapons': 'Item Row',
                        u'Heavy Weapons': 'Item Row',
                        u'Vehicles': 'Item Row',
                        u'Gear': 'Item Row',
                        u'Lieutenants': 'Lieutenant Row'}

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
        self.update_lt_rarity_table()

def main():
    #logging.basicConfig()
    bot = XrefBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

