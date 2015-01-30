# Copyright (C) 2013-2014 Chris Brand
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
Script to create useful tables on Underworld Empire Wiki
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')

import pywikibot, pagegenerators
import re, difflib
import logging
import utils

# Stuff for the pywikibot help system
parameterHelp = pagegenerators.parameterHelp + """\
"""

docuReplacements = {
    '&params;': parameterHelp
}

# Summary message when using this module as a stand-alone script
summary = u'Robot: Create/update item summary tables'

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
        text += u'!span="col" data-sort-type="currency" | Cost (with no discount)\n'
        # Income column, sorted as currency
        text += u'!span="col" data-sort-type="currency" | Income\n'
        # Time to recoup cost column
        text += u'!span="col" data-sort-type="number" | Hrs to recoup\n'
        # Unlock criteria
        text += u'!span="col" | Prerequisite(s)\n'
        # Build Time
        text += u'!span="col" | Build Time\n'
    elif row_template == u'Job Row':
        # Area column
        text += u'!span="col" | Area\n'
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
        text += u'!span="col" data-sort-type="currency" | Cash/ energy\n'
        # XP/energy Column
        text += u'!span="col" data-sort-type="number" | XP/ energy\n'
        # Penelope XP columns
        text += u'!span="col" data-sort-type="number" | Min XP with [[Penelope]]\n'
        text += u'!span="col" data-sort-type="number" | Max XP with [[Penelope]]\n'
        # Penelope XP/energy Column
        text += u'!span="col" data-sort-type="number" | XP/energy with [[Penelope]]\n'
    elif row_template == u'Challenge Job Row':
        # Area column
        text += u'!span="col" | Area\n'
        # Job name column
        text += u'!span="col" | Job\n'
        # Energy columns
        text += u'!span="col" data-sort-type="number" | Energy\n'
        text += u'!span="col" data-sort-type="number" | Total Energy\n'
        # Lieutenants
        text += u'!span="col" | Lt 1\n'
        text += u'!span="col" | Lt 2\n'
        text += u'!span="col" | Lt 3\n'
        text += u'!span="col" | Lt 4\n'
        # Recombinator
        text += u'!span="col" | Recombinator\n'
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
        pywikibot.output("Unexpected row template %s" % row_template)

    return text

def summary_footer(row_template):
    """
    Returns the rest of a summary table, after the last row of data.
    """
    return u'|}\n[[Category:Summary Tables]]'

def cost_ratios():
    """
    Calculates the cost ratios table for all the original properties
    """
    cost_ratios = {}
    for level in range(1,21):
        cost_ratios[level] = 1.0 + (level-1)/10.0
    return cost_ratios

def prop_cost(base_cost, level, cost_ratios):
    """
    Calculates the cost for the specified level of a property.
    cost_ratios is a dict, indexed by level, of the ratio of the cost to the level 1 cost
    """
    if level in cost_ratios:
        return cost_ratios[level] * base_cost
    return 0

def property_row(name, d, count, high_cost_ratios):
    """
    Returns a property row line for the specified property.
    name is the name of the property.
    d is a dict of template parameters.
    count is the level of the property.
    high_cost_ratios is a dict, indexed by level, of the ratio of the cost to the level 1 cost,
    for high-cost properties (the later additions)
    """
    low_cost_ratios = cost_ratios()
    # We need to provide count, name, cost, income, and unlock
    # We have name and count.
    row = u'{{Property Row|name=%s|count=%d' % (name, count)
    # Income comes straight from the corresponding parameter, if present.
    if u'income' in d:
        row += u'|income=%s' % d[u'income']
    else:
        row += u'|income=1000'
    # Add in the build time parameter
    if u'time' in d:
        time = d[u'time']
        # If no units, assume hours
        if time.isdigit():
            time += u'hr'
            if time != u'1hr':
                time += u's'
        row += u'|time=%s' % time
    else:
        row += u'|time=Unknown'
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
        ratios = high_cost_ratios
    else:
        ratios = low_cost_ratios
    row += u'|cost=%d}}' % prop_cost(base_cost, count, ratios)
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
        pywikibot.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
    # Look for an "Unlock" line
    match = re.search(ur'Unlocked when (.*)', text)
    if match == None:
        pywikibot.output("Failed to find Unlock criteria for %s" % name)
        unlock = u'Unknown'
    else:
        unlock = match.group(1)
    # Find a table of costs
    for match in re.finditer(ur'\|\s*(?P<count>\d+)\s*\|\|[\s$]*(?P<cost>.*?)\s*\|\|[\s$]*(?P<max>.*?)\s*\|\|[ \t]*(?P<time>.*)',
                             text):
        d = match.groupdict()
        count = int(d['count'])
        if 'time' in d:
            time = d['time']
            if time == u'':
                time = u'Unknown'
        else:
            time = u'Unknown'
        # This assumes that rows are in numerical order, which should be true
        if count > 1:
            unlock = u'Level %d [[%s]]' % (count-1, name)
        # Don't bother with the "level 0" one
        if count > 0:
            row = u'{{%s|name=%s|count=%d|income=%s|unlock=%s|cost=%s|time=%s}}' % (row_template, name, count, income, unlock, d['cost'], time)
            rows.append(row)
    
    return rows

def parsed_fortress_table(text):
    """
    Parse the cost and pre-requisite table on the page into a dict
    Dict is indexed by Fortress level, and contains a (cost, pre-requisite name, pre-requisite level)
    tuple.
    """
    fortress_table_full_re = re.compile(ur'\|\W*(?P<count>\d+)\W*\|\|\D*(?P<cost>\d+)\D*\|\|\W*\[\[(?P<prop>.*)\]\]\D*(?P<lvl>\d+)')
    fortress_table_part_re = re.compile(ur'\|\W*(?P<count>\d+)\W*\|\|\W*\|\|\W*\[\[(?P<prop>.*)\]\]\D*(?P<lvl>\d+)')
    result = {}
    for match in fortress_table_part_re.finditer(text, re.IGNORECASE):
        d = match.groupdict()
        count = int(d['count'])
        prop = d['prop']
        lvl = int(d['lvl'])
        result[count] = (0, prop, lvl)
    for match in fortress_table_full_re.finditer(text, re.IGNORECASE):
        d = match.groupdict()
        count = int(d['count'])
        cost = int(d['cost'])
        prop = d['prop']
        lvl = int(d['lvl'])
        result[count] = (cost, prop, lvl)
    return result

def fortress_cost_ratios(the_dict):
    """
    Determines the cost ratios table for Fortress, from a dict parsed from the Fortress page.
    Dict is indexed by Fortress level, and contains a (cost, pre-requisite name, pre-requisite level)
    tuple.
    """
    costs = {}
    base_cost = float(the_dict[1][0])
    for (count, (cost, prop, lvl)) in the_dict.items():
        costs[count] = float(cost) / base_cost
    return costs

def fortress_rows(name, text, row_template, the_dict):
    """
    Returns rows for Properties Table for the Fortress page
    name is the name of the Fortress page.
    text is the text of the Fortress page.
    row_template is the name of the template to use.
    the_dict is a dict from the table on the Fortress page.
    Dict is indexed by Fortress level, and contains a (cost, pre-requisite name, pre-requisite level)
    tuple.
    """
    rows = []
    # Find the info we need - income, unlock criteria, cost
    # Look for an "Income" line
    match = re.search(ur'Income: (.*)', text)
    if match == None:
        pywikibot.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
    # Look for a "Build Time" line
    match = re.search(ur'Build Time: (.*)hrs per level', text)
    if match == None:
        pywikibot.output("Failed to find Build Time for %s" % name)
        time = 0
    else:
        time = int(match.group(1))
    # Work through the table of cost and unlock criteria dict
    for (count, (cost, prop, lvl)) in the_dict.items():
        unlock = u'level %d [[%s]]' % (lvl, prop)
        if count > 1:
            unlock = u'Level %d [[%s]] and ' % (count-1, name) + unlock
        row = u'{{%s|name=%s|count=%d|income=%s|unlock=%s|cost=%d|time=%shrs}}' % (row_template, name, count, income, unlock, cost, time*count)
        rows.append(row)
    #rows.sort()
    return rows

def swap_lts(row, idx1, idx2):
    """
    Swaps the two specified lts in the row.
    Returns the modified row.
    """
    row = row.replace('|lt_%d' % idx1, '|lt_9')
    row = row.replace('|lt_%d' % idx2, '|lt_%d' % idx1)
    row = row.replace('|lt_9', '|lt_%d' % idx2)
    return row

def sort_lts(row):
    """
    Sorts the Lts in a Challenge Job Row line by rarity.
    Returns the modified row text.
    """
    # First find the rarities of the 4 LTs
    rarities = {}
    for i in range(1,5):
        m = re.search(ur'\|lt_%d_rarity\s*=\s*(?P<rarity>[^|\s]*)' % i, row)
	if m:
		rarities[i] = m.group('rarity')
	else:
		pywikibot.output("Unable to find rarity for Lt %d" % i)
    # Because we know we only have a max of three rarities, we can take shortcuts
    # First move all Commons to the start
    for i in range(1,4):
        if rarities[i] != u'Common':
            for j in range(i+1,5):
                if rarities[j] == u'Common':
                    row = swap_lts(row, i, j)
                    rarities[j] = rarities[i]
                    rarities[i] = u'Common'
    # Then move all Rare to the end
    for i in range(4,1,-1):
        if rarities[i] != u'Rare':
            for j in range(i-1,0,-1):
                if rarities[j] == u'Rare':
                    row = swap_lts(row, i, j)
                    rarities[j] = rarities[i]
                    rarities[i] = u'Rare'
    return row

def page_to_row(page, row_template):
    """
    Creates a table row for the item or challenge job described in page.
    """
    # Where to put the page name
    mapping = {u'Challenge Job Row': u'district',
               u'Lieutenant Row' : u'name',
               u'Item Row' : u'name'}
    templatesWithParams = page.templatesWithParams()
    row = u'{{%s|%s=%s' % (row_template, mapping[row_template], page.title())
    for (template, params) in templatesWithParams:
        template_name = template.title(withNamespace=False)
        # We're only interested in certain templates
        if item_templates.search(template_name) or template_name == u'Challenge Job':
            # Pass all the item template parameters
            for param in params:
                row += u'|%s' % param
        else:
            match = lieutenant_templates.search(template_name)
            if match:
                # Construct a rarity parameter from the template name
                row += u'|rarity=%s' % match.group(1)
                # Pass all the lieutenant template parameters
                for param in params:
                    row += u'|%s' % param
    row += u'}}'
    if row_template == u'Challenge Job Row':
        row = sort_lts(row)
    return row

def page_to_rows(page, row_template, high_cost_ratios={}):
    # TODO Look at combining this function and page_to_row().
    """
    Returns a list of table rows for the jobs or property described in page.
    """
    templatesWithParams = page.templatesWithParams()
    rows = []
    for (template, params) in templatesWithParams:
        template_name = template.title(withNamespace=False)
        # We're only interested in certain templates
        if job_templates.search(template_name):
            row_stub = u'{{%s|district=%s' % (row_template, page.title())
            # Create a new row
            row = row_stub
            # Use all the item, property, and job template parameters for now
            for param in params:
                row += u'|%s' % param
            row += u'}}'
            # pywikibot.output(u'Row is "%s"' % row)
            # Add the new row to the list
            rows.append(row)
        elif property_templates.search(template_name):
            d = utils.paramsToDict(params)
            # Figure out how many rows we need
            if u'max' in d:
                # Exlplicit max has priority
                max = int(d[u'max'])
            elif u'fp_prop'in d:
                # All FP properties so far you just get 5 of
                max = 5
            elif template_name == u'Income Property':
                # Can get 20 of income properties with Fortress level 10
                max = 20
            else:
                # Upgrade properties (and Safe House) are limited to 10
                max = 10
            for count in range(1, max + 1):
                rows.append(property_row(page.title(), d, count, high_cost_ratios))
    return rows

def rarities():
    """
    Returns an ordered list of rarities.
    """
    # TODO Dynamically create the list from the rarity page
    rarities = []
    page = pywikibot.Page(pywikibot.Site(), u'Rarity')
    return [u'Common', u'Uncommon', u'Rare', u'Epic', u'Legendary']

def prop_row_key(text):
    """
    Returns the sort key for a property table row.
    """
    # Content is always name paramater then count parameter
    # We return a turple with the name parameter and integer count
    loc = text.find('count=')
    num_part = text[loc+6:]
    while not num_part.isdigit():
        num_part = num_part[:-1]
    return (text[1:loc], int(num_part))

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall

    def update_or_create_page(self, old_page, new_text):
        """
        Reads the current text of page old_page,
        compare it with new_text, prompts the user,
        and uploads the page
        """
        # Read the original content
        try:
            old_text = old_page.get()
            pywikibot.showDiff(old_text, new_text)
            prompt = u'Modify this summary page ?'
        except pywikibot.NoPage:
            old_text = u''
            pywikibot.output("Page %s does not exist" % old_page.title())
            pywikibot.output(new_text)
            prompt = u'Create this summary page ?'
        # Did anything change ?
        if old_text == new_text:
            pywikibot.output(u'No changes necessary to %s' % old_page.title());
        else:
            if not self.acceptall:
                choice = pywikibot.input_choice(u'Do you want to accept these changes?',  [('Yes', 'Y'), ('No', 'n'), ('All', 'a')], 'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text, summary)

    def update_properties_table(self):
        """
        Creates or updates page Properties Table from the
        content of the Properties category.
        """
        # Extract cost ratio table from the Fortress page
        fortress_page = pywikibot.Page(pywikibot.Site(), u'Fortress')
        fortress_text = fortress_page.get()
        fortress_dict = parsed_fortress_table(fortress_text)
        lvl_to_ratio = fortress_cost_ratios(fortress_dict)
        # Categories we're interested in
        the_cat = u'Properties'
        # Template we're going to use
        row_template = u'Property Row'

        old_page = pywikibot.Page(pywikibot.Site(), u'Properties Table')

        rows = []
        cat = pywikibot.Category(pywikibot.Site(), the_cat)
        for page in set(cat.articles(recurse=True)):
            new_rows = page_to_rows(page, row_template, lvl_to_ratio)
            if len(new_rows):
                rows += new_rows
            elif page.title() == u'Fortress':
                # Use the cached page text
                rows += fortress_rows(page.title(), fortress_text, row_template, fortress_dict)
            elif page.title() == u'Safe House':
                rows += safe_house_rows(page.title(), page.get(), row_template)
            else:
                pywikibot.output("Unexpected non-template property page %s" % page.title())

        # Start the new page text
        new_text = summary_header(row_template)
        # Sort rows into a sensible order
        for row in sorted(rows, key=prop_row_key):
            new_text += row + u'\n'
        # Finish with a footer
        new_text += summary_footer(row_template)
        # Upload it
        self.update_or_create_page(old_page, new_text);

    def update_jobs_tables(self):
        """
        Creates or updates page Jobs Table and Callenge Jobs Table from the
        content of the Areas category.
        """
        # Templates to use
        job_row_template = u'Job Row'
        dice_row_template = u'Challenge Job Row'

        job_page = pywikibot.Page(pywikibot.Site(), u'Jobs Table')
        dice_job_page = pywikibot.Page(pywikibot.Site(), u'Challenge Jobs Table')
        job_rows = []
        dice_rows = []
        cat = pywikibot.Category(pywikibot.Site(), u'Areas')
        # One row per use of the template on a page in category
        for page in list(cat.articles()):
            job_rows += page_to_rows(page, job_row_template)
            dice_rows.append(page_to_row(page, dice_row_template))
        # Start the new page text
        new_job_text = summary_header(job_row_template)
        new_dice_text = summary_header(dice_row_template)
        # TODO: Sort rows into some sensible order
        for row in job_rows:
            new_job_text += row + u'\n'
        for row in dice_rows:
            new_dice_text += row + u'\n'
        # Finish with a footer
        new_job_text += summary_footer(job_row_template)
        new_dice_text += summary_footer(dice_row_template)
        # Upload it
        self.update_or_create_page(job_page, new_job_text);
        self.update_or_create_page(dice_job_page, new_dice_text);

    def update_lt_rarity_table(self):
        """
        Creates or updates page Lieutenants Faction Rarity Table
        from the content of the Lieutenants category.
        """
        old_page = pywikibot.Page(pywikibot.Site(), u'Lieutenants Faction Rarity Table')
        factions = []
        cat = pywikibot.Category(pywikibot.Site(), u'Factions')
        for faction in list(cat.articles()):
            factions.append(faction.title())
        new_text = lt_faction_rarity_header(factions)
        for rarity in rarities():
            lieutenants = {}
	    lt_cat = pywikibot.Category(pywikibot.Site(), u'%s Lieutenants' % rarity)
            for lt in list(lt_cat.articles()):
                name = lt.title()
                templatesWithParams = lt.templatesWithParams()
                for (template, params) in templatesWithParams:
                    template_name = template.title(withNamespace=False)
                    match = lieutenant_templates.search(template_name)
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
            old_page = pywikibot.Page(pywikibot.Site(), u'%s Table' % name)
            # The category of interest
            cat = pywikibot.Category(pywikibot.Site(), u'Category:%s' % name)
            # Create one row for each page in the category
            rows = {}
            for page in list(cat.articles()):
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
        self.update_jobs_tables()
        self.update_lt_rarity_table()

def main():
    #logging.basicConfig()
    bot = XrefBot(None)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

