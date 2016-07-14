# Copyright (C) 2013-2015 Chris Brand
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
Create/update useful tables on Underworld Empire Wiki.

Run with no arguments.

Generate the following tables:
- Rifles Table
- Handguns Table
- Melee Weapons Table
- Heavy Weapons Table
- Vehicles Table
- Gear Table
- Lieutenants Table
- Lieutenants Faction Rarity Table
- Properties Table
- Jobs Table
- Challenge Jobs Table
- Area Gear Table
- Insignias Table
- Bosses Table
"""

import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
from pywikibot import pagegenerators
import re
import difflib
import utils
import argparse

# Summary message when using this module as a stand-alone script
summary = u'Robot: Create/update item summary tables'

# Handy regular expressions
ITEM_TEMPLATES = re.compile(u'.*\WItem')
PROPERTY_TEMPLATES = re.compile(u'.*\WProperty')
JOB_TEMPLATES = re.compile(u'.*Job')
LIEUTENANT_TEMPLATES = re.compile(u'Lieutenant\W(.*)')
SECRET_COUNT_RE_1 = re.compile(ur'an additional (\w+) \[\[\w*#Secret')
SECRET_COUNT_RE_2 = re.compile(ur'(\w+) additional \[\[\w*#Secret')
SECRET_JOBS_RE = re.compile(ur'==\w*Secret Jobs')
JOB_STARS_RE = re.compile(ur'Silver and gold .* were enabled')

class Error(Exception):
    pass

class IrrelevantRowError(Error):
    pass

def name_to_link(name):
    """
    Return name as a wiki link string.

    name -- wiki page name to be linked to

    Take the name of a page and return wiki markup for a link,
    converting disambiguated pages.
    e.g. "Dog (pet)" -> "[[Dog (pet)|Dog]]".
    """
    paren = name.find('(')
    if paren == -1:
        page = name
    else:
        page = name + u'|' + name[0:paren-1]
    return u'[[' + page + u']]'

def lt_faction_rarity_header(factions):
    """
    Return a summary table down to the first row of data.

    factions -- list of all the factions. Used for column headers.
    """
    # Warn editors that the page was generated
    text = u'<!-- This page was generated/modified by software -->\n'
    # No WYSIWYG editor
    text += u'__NOWYSIWYG__\n'
    text += u'This page is auto-generated from the rest of the wiki. If something is wrong, please fix it in the Lt page\n'
    text += u'{| border="1" class="wikitable"\n'
    text += u'!span="col" | \n'
    for faction in factions:
        text += u'!span="col" | [[%s]]\n' % faction
    return text

def lt_faction_rarity_row(factions, rarity, lieutenants_by_faction):
    """
    Return a row for the specified rarity.

    factions -- list of all the factions. Order must match column headers.
    rarity -- String identifying the rarity of interest.
    lieutenants_by_faction -- dict, indexed by faction, of lists of lt names.
    """
    text = u'|-\n'
    text += u'!scope=row | {{%s}}\n' % rarity
    for faction in factions:
        text += u'|'
        if faction in lieutenants_by_faction:
            text += u'<br/>'.join(map(name_to_link,
                                      lieutenants_by_faction[faction]))
        else:
            text += u'None'
        text += u'\n'
    return text
 
def summary_header(row_template):
    """
    Return a summary table page down to the first row of data.

    row_template -- Name of the template to be used for each data row.
                    One of 'Item Row', 'Property Row', 'Job Row', 'Area Row',
                    'Challenge Job Row', 'Secret Job Row', or 'Lieutenant Row'.
    """
    # Warn editors that the page was generated
    text = u'<!-- This page was generated/modified by software -->\n'
    # No WYSIWYG editor
    text += u'__NOWYSIWYG__\n'
    text += u'This page is auto-generated from the rest of the wiki. If something is wrong, please fix it in the page for the row\n'
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
        text += u'!span="col" data-sort-type="number" | Total Energy (Bronze)\n'
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
    elif row_template == u'Insignia Row':
        # Insignia Type column
        text += u'!span="col" rowspan="2" | Type\n'
        # Main stat(s) column
        text += u'!span="col" rowspan="2" | Main Stat\n'
        # Sub-stats columns (checkboxes)
        text += u'!colspan="10" class="unsortable" | Sub-stats\n'
        text += u'|-\n'
        text += u'!span="col" | Lt [[Attack|Atk]]\n'
        text += u'!span="col" | Lt [[Attack|Atk]]%\n'
        text += u'!span="col" | Lt [[Attack|Def]]\n'
        text += u'!span="col" | Lt [[Attack|Def]]%\n'
        text += u'!span="col" | [[Health]]\n'
        text += u'!span="col" | [[Health]]%\n'
        text += u'!span="col" | [[Damage|Dmg]] %\n'
        text += u'!span="col" | Shield %\n'
        text += u'!span="col" | [[Critical Hit|Crit]] %\n'
        text += u'!span="col" | [[Critical Hit|Crit]] dmg %\n'
    elif row_template == u'Boss Row':
        # Name column
        text += u'!span="col" | Name\n'
        # Threshold 1 column
        text += u'!span="col" data-sort-type="number" | 1 Epic Threshold\n'
        # Threshold 2 column
        text += u'!span="col" data-sort-type="number" | 2 Epic Threshold\n'
        # Threshold 3 column
        text += u'!span="col" data-sort-type="number" | 3 Epic Threshold\n'
    elif row_template == u'Secret Job Row':
        # Area column
        text += u'!span="col" | Area\n'
        # Job count
        text += u'!span="col" | Job count\n'
        # Date added
        text += u'!span="col" | Date added\n'
    elif row_template == u'Area Row':
        # Area column
        text += u'!span="col" | Area\n'
        # energy cost for 5 stars
        text += u'!span="col" data-sort-type="number" | [[Energy]] to 5[[Star (Job)|*]]\n'
        # Number of skill points obtained
        text += u'!span="col" data-sort-type="number" | [[Skill Point]]s\n'
        # Energy per skill point
        text += u'!span="col" data-sort-type="number" | Energy/Skill point\n'
        # Is the row accurate ?
        text += u'!span="col" | Underestimate\n'
    else:
        pywikibot.output("Unexpected row template %s" % row_template)

    return text

def summary_footer(row_template):
    """
    Return the rest of a summary table, after the last row of data.
    """
    note = u''
    if row_template == u'Area Row':
        note = u'"Underestimate" is Yes if the total energy for one or more jobs is unknown\n'

    return u'|}\n%s[[Category:Summary Tables]]' % note

def cost_ratios():
    """
    Return the cost ratios table for all the original properties.

    Return value is a dict, indexed by level, of real numbers.
    """
    cost_ratios = {}
    for level in range(1,21):
        cost_ratios[level] = 1.0 + (level-1)/10.0
    return cost_ratios

def prop_cost(base_cost, level, cost_ratios):
    """
    Return the cost for the specified level of a property.

    base_cost -- cost for level 1 of the property.
    level -- property level of interest.
    cost_ratios -- a dict, indexed by level, of the ratio of the cost to the level 1 cost

    Return 0 if the cost cannot be calulcated.
    """
    if level in cost_ratios:
        return cost_ratios[level] * base_cost
    return 0

def property_row(name, d, count, high_cost_ratios):
    """
    Return a property row line for the specified property.

    name -- the name of the property.
    d -- a dict of template parameters.
    count -- the level of the property.
    high_cost_ratios -- a dict, indexed by level, of the ratio of the cost to the level 1 cost,
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
            if u'high_cost' in d:
                time = str(count * int(time))
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
        if unlock:
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
    Return a list of rows for Properties Table for the Safe House page.

    name -- Name of the Safe House wiki page.
    text -- Text of the Safe House wiki page.
    row_template -- Template to use for the row.
    """
    rows = []
    # Find the info we need - income, unlock criteria, cost
    # Look for an "Income" line
    match = re.search(ur'Income: (.*)', text)
    if match is None:
        pywikibot.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
        # We only want the numbers
        income = re.sub(r'\D+', u'', income)
        if income == u'':
            income = u'None'
    # Look for an "Unlock" line
    match = re.search(ur'Unlocked when (.*)', text)
    if match is None:
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
    Return a dict parsing the cost and pre-requisite table on the page.

    text -- text of the Fortress wiki page.

    Dict returned is indexed by Fortress level, and contains a 3-tuple of
    (cost, pre-requisite name, pre-requisite level).
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
    Return the cost ratios table for Fortress.

    the_dict -- a dict parsed from the Fortress page.
                Dict is indexed by Fortress level, and contains a 3-tuple of
                (cost, pre-requisite name, pre-requisite level).

    Return a list, indexed by level, of ratio of cost to base cost.
    """
    costs = {}
    base_cost = float(the_dict[1][0])
    for (count, (cost, prop, lvl)) in the_dict.items():
        costs[count] = float(cost) / base_cost
    return costs

def fortress_rows(name, text, row_template, the_dict):
    """
    Return a list of rows for Properties Table for the Fortress page.

    name -- the name of the Fortress page.
    text -- the text of the Fortress page.
    row_template -- the name of the template to use.
    the_dict -- a dict from the table on the Fortress page.
                Dict is indexed by Fortress level, and contains a 3-tuple of
                (cost, pre-requisite name, pre-requisite level).
    """
    rows = []
    # Find the info we need - income, unlock criteria, cost
    # Look for an "Income" line
    match = re.search(ur'Income: (.*)', text)
    if match is None:
        pywikibot.output("Failed to find Income for %s" % name)
        income = u'Unknown'
    else:
        income = match.group(1)
    # Look for a "Build Time" line
    match = re.search(ur'Build Time: (.*)hrs per level', text)
    if match is None:
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

def secret_job_dates(areas):
    """
    Parse the history page to determine the dates when secret jobs in
    different areas were released.
    Returns a dict, keyed by area name, of dates.
    """
    retval = {}
    page = pywikibot.Page(pywikibot.Site(), u'History')
    text = page.get()
    # Split it at dates (some entries span multiple lines)
    #DATE_RE = re.compile(ur'([-0-9]* [A-Z][a-z]{2} 20[1-9][0-9])', re.MULTILINE)
    DATE_RE = re.compile(ur'([-0-9]* [A-Z][a-z]{2} 20[1-9][0-9])')
    split_text = DATE_RE.split(text)
    for i in range(len(split_text)):
        if u'ecret' in split_text[i]:
            # Which area is this for ?
            for area in areas:
                if area in split_text[i]:
                    # Previous entry in the list is the date, unless we're at the start
                    if i > 0:
                        retval[area] = split_text[i-1]
                    break
    return retval

def page_to_secret_row(page, template, dates):
    """
    Create a secret job row from an area page.
    """
    name = page.title()
    text = page.get()
    # Set count by parsing the page
    m = SECRET_COUNT_RE_1.search(text)
    if not m:
        m = SECRET_COUNT_RE_2.search(text)
    if m:
        count = m.group(1)
    else:
        print "Unable to find secret job count for %s" % name
        count = u'Unknown'
    try:
        release_date = dates[name]
    except KeyError:
        release_date = u'Not yet released'
    return u'{{%s|area=%s|count=%s|date=%s}}' % (template, name,
                                                 count, release_date)

def page_to_areas_rows(page, template):
    """
    Create one or more areas rows from an area page.
    """
    name = page.title()
    text = page.get()

    # Find where secret jobs appear on the page
    m = SECRET_JOBS_RE.search(text)
    if m:
        secrets_start = m.start()
    else:
        secrets_start = len(text)

    # Determine whether silver and gold stars are enabled or not
    just_bronze = True
    m = JOB_STARS_RE.search(text)
    if m:
        just_bronze = False

    main = {'count': 0, 'energy': 0, 'complete': True}
    secrets = {'count': 0, 'energy': 0, 'complete': True}
    # This will toggle to secrets when we get to the first secret job
    jobs = main

    templatesWithParams = page.templatesWithParams()
    for (t, params) in templatesWithParams:
        template_name = t.title(withNamespace=False)
        # We're only interested in Jobs
        if template_name == u'Job':
            if not jobs == secrets:
                # Check whether this is the first secret job
                job_name = utils.param_from_params(params,
                                                   u'name')
                m = re.search(ur'name=%s' % job_name, text)
                if m:
                    if m.start() > secrets_start:
                        jobs = secrets

            p = utils.param_from_params(params,
                                        u'total_energy')
            if p:
                total_energy = int(p)
            else:
                # This is actually "don't know"
                total_energy = 0
                jobs['complete'] = False

            jobs['count'] += 1
            jobs['energy'] += total_energy

    # Now we need to return a list with 1, 2, 3, or 6 entries
    line = u'{{%s|name=[[%s]] %s|jobs=%d|jobs_energy=%d}}'
    retval = []
    levels = [u'Bronze']
    if not just_bronze:
        levels += [u'Silver', u'Gold']
    for level in levels:
        main_line = line % (template, name, level, main['count'], main['energy'])
        if (level == levels[0]) and not main['complete']:
            main_line = main_line.replace(u'}}', u'|missing_data=true}}')
        retval.append(main_line)
        # Add a secrets line if secret jobs are open
        if secrets['count'] > 0:
            secrets_line = line % (template, name, u'Secret %s' % level, secrets['count'], secrets['energy'])
            if (level == levels[0]) and not secrets['complete']:
                secrets_line = secrets_line.replace(u'}}', u'|missing_data=true}}')
            retval.append(secrets_line)
        # Next level costs twice the energy
        main['energy'] *= 2
        secrets['energy'] *= 2
    return retval

def swap_lts(row, idx1, idx2):
    """
    Return the row with the two specified Lts swapped.

    row -- the text for the row.
    idx1, idx2 -- Numbers of the Lts to swap.
    """
    row = row.replace('|lt_%d' % idx1, '|lt_9')
    row = row.replace('|lt_%d' % idx2, '|lt_%d' % idx1)
    row = row.replace('|lt_9', '|lt_%d' % idx2)
    return row

def sort_lts(row, area):
    """
    Return row with the Lts sorted by rarity.

    row -- the text of the Challenge Job Row line.
    area -- name of the Area the row corresponds to.
    """
    # First find the rarities of the 4 LTs
    rarities = {}
    for i in range(1,5):
        m = re.search(ur'\|lt_%d_rarity\s*=\s*(?P<rarity>[^|\s]*)' % i, row)
	if m:
		rarities[i] = m.group('rarity')
	else:
		pywikibot.output("Unable to find rarity for Lt %d" % i)
    if len(rarities) < 4:
        #m = re.search(ur'\|district=(?P<area>[^|\s]*)', row)
        ## As we put this parameter in, it should always be present
        #area = m.group('area')
        pywikibot.output("Missing Lts - not sorting %s\n" % area)
        return row
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

def gear_needed(page):
    """
    Return a dict representing the gear required for the area page.

    page -- Area Page object.

    Return a a dict, keyed by item or property,
    of 2-tuples containing the number of each item/property required to
    complete all the jobs in that area, and the image for the item/property.
    """
    needed = {}
    templatesWithParams = page.templatesWithParams()
    for (template, params) in templatesWithParams:
        template_name = template.title(withNamespace=False)
        # We're only interested in certain templates
        if template_name == u'Job':
            d = utils.params_to_dict(params)
            g = d.get(u'gear', u'None')
            if g != u'None':
                # There shouldn't be any of these
                print "Found %s in gear parameter in %s" % (g, page.title())
            for i in range(1,5):
                key = u'gear_%d' % i
                try:
                    g = d[key]
                    try:
                        n = int(d[key + u'_count'])
                    except ValueError:
                        # Use -1 as a placeholder - any real number is greater
                        n = -1
                    img = d[key + u'_img']
                except KeyError:
                    pass
                else:
                    # Store the largest number of each type of gear
                    if g not in needed or n > needed[g][0]:
                        needed[g] = (n, img)
    return needed

def boss_page_to_row(page, row_template):
    """
    Return a table row for the boss described in page.

    page -- Page to parse.
    row_template -- template to use in the generated row text.
                    Must be 'Boss Row'.
    """
    POINTS_RE = re.compile(ur'#\s*({{formatnum:)?\s*(?P<points>[\d,. ]*)(}})?')
    name = page.title()
    text = page.get()
    # Extract the epic thresholds section from the page text
    (start, end) = utils.find_specific_section(text, u'{{Epic}} Thresholds')
    if start == -1:
        pywikibot.output("Skipping %s as it has no Epic Thresholds section" % name)
        raise IrrelevantRowError
    section = text[start:end]
    # Extract the actual thresholds
    thresholds = {}
    for param in range(1, 1+section.count(u'#')):
        i = section.index(u'#')
        m = POINTS_RE.search(section)
        # Skip entries without a value
        if m and m.start() == i:
            # Clean the value to a raw number
            val = m.group(u'points')
            val = val.rstrip()
            val = val.replace(u',', u'')
            val = val.replace(u'.', u'')
            val = val.replace(u' ', u'')
            if len(val):
                thresholds[param] = val
            # Remove (some of) this entry from the start
            section = section[i+1:]
    text = u'{{%s|name=%s' % (row_template, name)
    for i in sorted(thresholds.keys()):
        text += u'|epic_%d=%s' % (i, thresholds[i])
    text += u'}}'
    return text

def page_to_row(page, row_template):
    """
    Return a table row for the item or challenge job described in page.

    page -- Page to parse.
    row_template -- template to use in the generated row text.
                    One of 'Challenge Job Row', 'Lieutenant Row', 'Item Row',
                    or 'Boss Row'.
    """
    # Where to put the page name
    mapping = {u'Challenge Job Row': u'district',
               u'Lieutenant Row' : u'name',
               u'Item Row' : u'name',
               u'Insignia Row' : u'type'}
    ignore_cost_param = {u'Special Item',
                         u'Gift Item',
                         u'Faction Item'}
    templates_of_interest = [u'Challenge Job',
                             u'Insignia Type']
    # Boss pages don't have a main template (maybe they should...)
    if row_template == u'Boss Row':
        return boss_page_to_row(page, row_template);
    found_template = False
    templatesWithParams = page.templatesWithParams()
    name = page.title()
    row = u'{{%s|%s=%s' % (row_template, mapping[row_template], name)
    for (template, params) in templatesWithParams:
        template_name = template.title(withNamespace=False)
        # We're only interested in certain templates
        if ITEM_TEMPLATES.search(template_name) or template_name in templates_of_interest:
            found_template = True
            # Pass all the item template parameters
            if template_name in ignore_cost_param:
                # We only have a real cost for Basic Items
                row += u'|cost=N/A'
            for param in params:
                if not param.startswith(u'cost') or (template_name not in ignore_cost_param):
                    row += u'|%s' % param
        else:
            match = LIEUTENANT_TEMPLATES.search(template_name)
            if match:
                found_template = True
                # Construct a rarity parameter from the template name
                row += u'|rarity=%s' % match.group(1)
                # Pass all the lieutenant template parameters
                for param in params:
                    row += u'|%s' % param
    if not found_template:
        raise IrrelevantRowError
    row += u'}}'
    if row_template == u'Challenge Job Row':
        row = sort_lts(row, name)
    return row

def page_to_rows(page, row_template, high_cost_ratios={}):
    """
    Return a list of table rows for the jobs or property described in page.

    page -- text of the page to parse.
    row_template -- template to use in the resulting row.
    high_cost_ratios -- a dict from the table on the Fortress page (optional).
                Dict is indexed by Fortress level, and contains a 3-tuple of
                (cost, pre-requisite name, pre-requisite level).
    """
    templatesWithParams = page.templatesWithParams()
    rows = []
    for (template, params) in templatesWithParams:
        template_name = template.title(withNamespace=False)
        # We're only interested in certain templates
        if JOB_TEMPLATES.search(template_name):
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
        elif PROPERTY_TEMPLATES.search(template_name):
            d = utils.params_to_dict(params)
            # Figure out how many rows we need
            if u'max' in d:
                # Explicit max has priority
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
                rows.append(property_row(page.title(),
                                         d,
                                         count,
                                         high_cost_ratios))
    return rows

def rarities():
    """
    Return an ordered list of rarities.
    """
    # TODO Dynamically create the list from the rarity page
    rarities = []
    page = pywikibot.Page(pywikibot.Site(), u'Rarity')
    return [u'Common', u'Uncommon', u'Rare', u'Epic', u'Legendary']

def prop_row_key(text):
    """
    Return the sort key for a property table row.

    text -- text of the row to be sorted.
    """
    # Content is always name paramater then count parameter
    # We return a turple with the name parameter and integer count
    loc = text.find('count=')
    num_part = text[loc+6:]
    while not num_part.isdigit():
        num_part = num_part[:-1]
    return (text[1:loc], int(num_part))

def areas_in_order():
    """Return a list of Area pages in in=game order."""
    # Utils provides a function that does most of the work
    jobs_page = pywikibot.Page(pywikibot.Site(), u'Jobs')
    return utils.areas_in_order(jobs_page.get())


class XrefBot:
    """Class to create/update pages summarising sets of pages on the wiki."""

    def __init__(self, pages, acceptall = False):
        """
        Instantiate the class.

        pages      -- list of pages to create/update
        accept_all -- Pass True to not ask the user whether to create/update
                      pages.
        """
        self.acceptall = acceptall
        self.pages = pages
        self.areas = areas_in_order()

    def _update_or_create_page(self, old_page, new_text):
        """
        If the page needs changing, upload with user permission.

        old_page -- Page to be checked.
        new_text -- Text the page should contain.

        Retrieve the existing page, if any, and compare the content.
        If the content differs, prompt the user whether to upload the
        new version, and obey their response.
        """
        # Show the title of the page we're working on.
        # Highlight the title in purple.
        pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % old_page.title())
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
                choice = pywikibot.input_choice(u'Do you want to accept these changes?',
                                                [('Yes', 'Y'),
                                                 ('No', 'n'),
                                                 ('All', 'a')],
                                                'N')
                if choice == 'a':
                    self.acceptall = True
            if self.acceptall or choice == 'y':
                # Write out the new version
                old_page.put(new_text, summary)

    def update_properties_table(self):
        """
        Create or update page Properties Table.

        Read every page in the Properties category and create/update the summary
        page accordingly.
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
            title = page.title()
            if new_rows:
                rows += new_rows
            elif title == u'Fortress':
                # Use the cached page text
                rows += fortress_rows(title,
                                      fortress_text,
                                      row_template,
                                      fortress_dict)
            elif title == u'Safe House':
                rows += safe_house_rows(title, page.get(), row_template)
            elif title == u'The Cayman Islands':
                rows += safe_house_rows(title, page.get(), row_template)
            else:
                pywikibot.output("Unexpected non-template property page %s" % title)

        # Start the new page text
        new_text = summary_header(row_template)
        # Sort rows into a sensible order
        for row in sorted(rows, key=prop_row_key):
            new_text += row + u'\n'
        # Finish with a footer
        new_text += summary_footer(row_template)
        # Upload it
        self._update_or_create_page(old_page, new_text);

    def _area_key(self, page):
        """Return the sort key for a Page for an Area."""
        try:
            return self.areas.index(page.title())
        except ValueError:
            # Put any we don't know about at the end
            return 10000

    def _dict_to_gear_page(self, gear_dict):
        """
        Return the text of the Area Gear Table page.

        gear_dict -- a dict, indexed by area Page, of dicts,
                     indexed by item/property name, of 2-tuples containing the
                     number of that item/property required and its image.
        """
        text = u'<!-- This page was generated/modified by software -->\n'
        text += u'This page lists the gear required to complete all the jobs in each area (including secret jobs). Details are pulled from the individual [[:Category:Areas|Area]] pages, so any errors or omissions there will be reflected here.\n'
        for area in sorted(gear_dict.keys(), key=self._area_key):
            text += u'==[[%s]]==\n' % area.title()
            the_gear = gear_dict[area]
            for gear in sorted(the_gear.keys()):
                (n, img) = the_gear[gear]
                # Check for special placeholder indicating "some number"
                if n == -1:
                   num = u'?'
                else:
                   num = str(n)
                text += u'*%s [[File:%s||100px]] [[%s]]\n' % (num, img, gear)
        text += u'[[Category:Summary Tables]]'
        return text

    def update_jobs_tables(self):
        """
        Create or update the job summary pages.

        Read every page in the Areas category and create/update pages
        Jobs Table, Challenge Jobs Table, Secret Jobs Table, Areas Table, and
        Area Gear Table accordingly.
        """
        # Templates to use
        job_row_template = u'Job Row'
        dice_row_template = u'Challenge Job Row'
        secret_row_template = u'Secret Job Row'
        area_row_template = u'Area Row'

        job_rows = []
        dice_rows = []
        secret_rows = []
        areas_rows = []
        gear_dict = {}

        cat = pywikibot.Category(pywikibot.Site(), u'Areas')

        secret_dates = secret_job_dates(self.areas)

        # Go through the area pages in in-game order
        for page in sorted(cat.articles(), key=self._area_key):
            # One row per use of the template on a page in category
            job_rows += page_to_rows(page, job_row_template)
            dice_rows.append(page_to_row(page, dice_row_template))
            secret_rows.append(page_to_secret_row(page,
                                                  secret_row_template,
                                                  secret_dates))
            areas_rows += page_to_areas_rows(page, area_row_template)
            # Add an entry to gear_dict for this page
            gear_dict.update({page: gear_needed(page)})

        # Start the new page text
        new_job_text = summary_header(job_row_template)
        new_dice_text = summary_header(dice_row_template)
        new_areas_text = summary_header(area_row_template)
        new_secret_text = summary_header(secret_row_template)

        for row in job_rows:
            new_job_text += row + u'\n'
        for row in dice_rows:
            new_dice_text += row + u'\n'
        for row in areas_rows:
            new_areas_text += row + u'\n'
        for row in secret_rows:
            new_secret_text += row + u'\n'

        # Finish with a footer
        new_job_text += summary_footer(job_row_template)
        new_dice_text += summary_footer(dice_row_template)
        new_areas_text += summary_footer(area_row_template)
        new_secret_text += summary_footer(secret_row_template)

        # Generate the area gear page from the dict
        if u'Area Gear Table' in self.pages:
            new_gear_text = self._dict_to_gear_page(gear_dict)

        # Upload the new pages
        if u'Jobs Table' in self.pages:
            job_page = pywikibot.Page(pywikibot.Site(), u'Jobs Table')
            self._update_or_create_page(job_page, new_job_text);
        if u'Challenge Jobs Table' in self.pages:
            dice_job_page = pywikibot.Page(pywikibot.Site(),
                                           u'Challenge Jobs Table')
            self._update_or_create_page(dice_job_page, new_dice_text);
        if u'Secret Jobs Table' in self.pages:
            secret_job_page = pywikibot.Page(pywikibot.Site(),
                                             u'Secret Jobs Table')
            self._update_or_create_page(secret_job_page, new_secret_text);
        if u'Areas Table' in self.pages:
            areas_page = pywikibot.Page(pywikibot.Site(),
                                        u'Areas Table')
            self._update_or_create_page(areas_page, new_areas_text);
        if u'Area Gear Table' in self.pages:
            area_gear_page = pywikibot.Page(pywikibot.Site(),
                                            u'Area Gear Table')
            self._update_or_create_page(area_gear_page, new_gear_text);

    def update_lt_rarity_table(self):
        """
        Create or update page Lieutenants Faction Rarity Table.

        Read every page in the Lieutenants category and create/update the
        summary page accordingly.
        """
        old_page = pywikibot.Page(pywikibot.Site(),
                                  u'Lieutenants Faction Rarity Table')
        factions = []
        cat = pywikibot.Category(pywikibot.Site(), u'Factions')
        for faction in list(cat.articles()):
            factions.append(faction.title())
        new_text = lt_faction_rarity_header(factions)
        for rarity in rarities():
            lieutenants = {}
	    lt_cat = pywikibot.Category(pywikibot.Site(),
                                        u'%s Lieutenants' % rarity)
            for lt in list(lt_cat.articles()):
                name = lt.title()
                templatesWithParams = lt.templatesWithParams()
                for (template, params) in templatesWithParams:
                    template_name = template.title(withNamespace=False)
                    match = LIEUTENANT_TEMPLATES.search(template_name)
                    if match:
                        faction = utils.param_from_params(params,
                                                          u'faction')
                        lieutenants.setdefault(faction, []).append(name)
            if lieutenants:
                new_text += lt_faction_rarity_row(factions, rarity, lieutenants)
        new_text += summary_footer(None)
        # Upload it
        self._update_or_create_page(old_page, new_text);

    def update_most_tables(self):
        """
        Create or update most summary pages.

        Read every page in the categories listed below and create/update the
        corresponding summary page:
        Rifles - Rifles Table
        Handguns - Handguns Table
        Melee Weapons - Melee Weapons Tale
        Heavy Weapons - Heavy Weapons Table
        Vehicles - Vehicles Table
        Gear - Gear Table
        Lieutenants - Lieutenants Table
        Insignias - Insignias Table
        Job Bosses, Tech Lab Bosses, Legend Bosses - Bosses Table
        """
        # Categories we're interested in and row template to use for each category
        cat_to_templ = {u'Rifles': ('Item Row', []),
                        u'Handguns': ('Item Row', []),
                        u'Melee Weapons': ('Item Row', []),
                        u'Heavy Weapons': ('Item Row', []),
                        u'Vehicles': ('Item Row', []),
                        u'Gear': ('Item Row', []),
                        u'Lieutenants': ('Lieutenant Row', []),
                        u'Insignias' : (u'Insignia Row', []),
                        u'Bosses' : (u'Boss Row', [u'Tech Lab Bosses',
                                                   u'Legend Bosses',
                                                   u'Job Bosses'])}

        # Go through cat_to_templ, and create/update summary page for each one
        for name, (template, cat_list) in cat_to_templ.iteritems():
            # The current summary table page for this category
            page_name = u'%s Table' % name
            # Skip pages the user isn't interested in
            if page_name not in self.pages:
                continue
            old_page = pywikibot.Page(pywikibot.Site(), page_name)
            # The category of interest
            if len(cat_list) > 0:
                articles = []
                for name in cat_list:
                    cat = pywikibot.Category(pywikibot.Site(),
                                             u'Category:%s' % name)
                    articles.extend(list(cat.articles()))
            else:
                cat = pywikibot.Category(pywikibot.Site(),
                                         u'Category:%s' % name)
                articles = list(cat.articles())
            # Create one row for each page in the category
            rows = {}
            for page in articles:
                try:
                    rows[page.title()] = page_to_row(page, template)
                except IrrelevantRowError:
                    pass
            # Start the new page text
            new_text = summary_header(template)
            # Sort rows by item (page) name, and append each one
            for key in sorted(rows.keys()):
                new_text += rows[key] + u'\n'
            # Finish with a footer
            new_text += summary_footer(template)
            # Upload it
            self._update_or_create_page(old_page, new_text);

    def run(self):
        """Create/update all the summary pages."""
        self.update_most_tables()
        if u'Properties Table' in self.pages:
            self.update_properties_table()
        if ((u'Jobs Table' in self.pages) or
            (u'Challenge Jobs Table' in self.pages) or
            (u'Secret Jobs Table' in self.pages) or
            (u'Areas Table' in self.pages) or
            (u'Area Gear Table' in self.pages)):
            self.update_jobs_tables()
        if u'Lieutenants Faction Rarity Table' in self.pages:
            self.update_lt_rarity_table()

def main(pages):
    bot = XrefBot(pages)
    bot.run()

if __name__ == "__main__":
    arguments = {'--rifles'     : u'Rifles Table',
                 '--guns'       : u'Handguns Table',
                 '--melee'      : u'Melee Weapons Table',
                 '--heavy'      : u'Heavy Weapons Table',
                 '--vehicles'   : u'Vehicles Table',
                 '--gear'       : u'Gear Table',
                 '--lts'        : u'Lieutenants Table',
                 '--insignias'  : u'Insignias Table',
                 '--properties' : u'Properties Table',
                 '--jobs'       : u'Jobs Table',
                 '--dice_jobs'  : u'Challenge Jobs Table',
                 '--areas'      : u'Areas Table',
                 '--area_gear'  : u'Area Gear Table',
                 '--bosses'     : u'Bosses Table',
                 '--secret'     : u'Secret Jobs Table',
                 '--lt_rarities': u'Lieutenants Faction Rarity Table'}

    parser = argparse.ArgumentParser(description='Create/update summary pages.', epilog='With no options, create/update all summary pages.')
    for a in sorted(arguments.iterkeys()):
        s = arguments[a]
        parser.add_argument(a, help="Create/update the %s page" % s, dest='pages', action='append_const', const=s)
    args = parser.parse_args()

    # Default to "all" if no specific pages listed
    pages = args.pages
    if not pages:
        pages = arguments.values()
    try:
        main(pages)
    finally:
        pywikibot.stopme()

