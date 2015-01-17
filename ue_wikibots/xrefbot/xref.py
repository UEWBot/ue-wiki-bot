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
Script to fix up categories and cross-references between pages on UE Wiki.
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
summary = u'Robot: Fix cross-references and/or categories'

# Copied from pywikibot.py
Rtemplate = re.compile(ur'{{(msg:)?(?P<name>[^{\|]+?)(\|(?P<params>[^{]+?))?}}')
# Modified from the above
namedtemplate = (ur'{{(msg:)?(%s[^{\|]+?)(\|(?P<params>[^{]+?))?}}')

# Headers
# This doesn't match level 1 headers, but they're rare...
Rheader = re.compile(ur'(={2,})\s*(?P<title>[^=]+)\s*\1')

# List items on gift page
Rgift = re.compile(ur'<li value=(?P<level>.*)>\[\[(?P<item>.*)\]\]</li>')

# List items on faction page
Rfaction = re.compile(ur'\*\s*(?P<points>\S*)>\s*points - \[\[(?P<item>.*)\]\]')

# Any link
Rlink = re.compile(ur'\[\[\s*(?P<page>[^\|\]]*)\s*.*\]\]')

# Ingredient, with source
Ringredient = re.compile(ur'\[\[\s*(?P<ingredient>.*)\s*.*\]\].*from\s*\[\[\s*(?P<source>[^\|\]]*)\s*.*\]\]')

# String used for category REs
category_re = ur'\[\[\s*Category:\s*%s\s*\]\]'
Rcategory = re.compile(ur'\[\[\s*Category:[^]]*\]\]')

# Regexes used for item powers
noStackRe = re.compile(ur'\[no \[\[stack\]\]\]')
# Separators are with, for, and to
sepRe = re.compile(ur' with | for | to ')
# Some follow a completely patterns
allRe = re.compile(ur'[Aa]ll (.*) (count as .*)')
whenRe = re.compile(ur'(.*) when (.*)')

# Cache to speed up fixLieutenant()
cat_refs_map = utils.CategoryRefs()

# Cache to speed up finding recipes
recipe_cache = utils.RecipeCache()

# Image cache
image_map = utils.ImageMap()

def dropParamsMatch(param1, param2):
    """
    Compares two drop parameters.
    Ignores case of first character, matches spaces with underscores,
    and reports a match if one is a link and the other isn't.
    """
    # Direct match first
    if param1 == param2:
        return True
    # Convert spaces to underscores in both
    param1 = param1.replace(' ', '_')
    param2 = param2.replace(' ', '_')
    # Match link with non-link equivalent
    if param1[0:2] == u'[[':
        param1 = param1[2:-2]
    if param2[0:2] == u'[[':
        param2 = param2[2:-2]
    # Match with mismatched case of first character
    if param1[1:] == param2[1:]:
        return param1[0].lower() == param2[0].lower()
    return False

def timeParamsMatch(param1, param2):
    """
    Compares two time parameters.
    Matches "days" with "d" and "hours" with hrs".
    """
    # Direct match first
    if param1 == param2:
        return True
    # Split into number and units
    Rvalue = re.compile(ur'(?P<value>\d*)\s*(?P<unit>\w*)')
    g1 = Rvalue.match(param1)
    g2 = Rvalue.match(param2)
    #pywikibot.output("%s %s" % (g1.group('value'), g1.group('unit')))
    #pywikibot.output("%s %s" % (g2.group('value'), g2.group('unit')))
    if g1.group('value') != g2.group('value'):
        return False
    if g1.group('unit') == 'd' and 'day' in g2.group('unit'):
        return True
    if g2.group('unit') == 'd' and 'day' in g1.group('unit'):
        return True
    if 'hr' in g1.group('unit') and 'hour' in g2.group('unit'):
        return True
    if 'hr' in g2.group('unit') and 'hour' in g1.group('unit'):
        return True
    return False

def missingParams(all_params, mandatory_list):
    """
    Returns the set of all the parameters in mandatory_list that are not represented in all_params.
    """
    ret = set(mandatory_list)
    for p in all_params:
        m = utils.Rparam.match(p)
        if m is not None and m.group('name') in ret:
            ret.remove(m.group('name'))
    return ret

def oneCap(string):
    """
    Returns the string with the first letter capitalised and the rest left alone.
    """
    return string[0].upper() + string[1:]

class XrefToolkit:

    def __init__(self, site, specificNeeds, debug = False):
        self.site = site
        self.specificNeeds = specificNeeds
        self.debug = debug

    def change(self, text, page):
        """
        Given a wiki source code text, returns the cleaned up version.
        """
        titleWithoutNamespace = page.title(withNamespace=False)
        # Leave template pages alone
        # TODO Better to match title or category ?
        if page.title().startswith(u'Template:'):
            pywikibot.output("Not touching template page %s" % titleWithoutNamespace)
            return text
        # Note that this only gets explicit categories written into the page text,
        # not those added by templates.
        categories = page.categories()
        tmp = page.templatesWithParams()
        templatesWithParams = [(t.title(withNamespace=False),p) for (t,p) in tmp]
        # Don't do anything to stub pages
        for template,params in templatesWithParams:
            if template == u'Stub':
                pywikibot.output("Not touching stub page %s" % titleWithoutNamespace)
                return text
        refs = list(page.getReferences())
        oldText = text
        #pywikibot.output("******\nIn text:\n%s" % text)
        # Note that these are effectively independent. Although the text gets changed,
        # the categories, templates, and parameters are not re-generated after each call
        text = self.fixEventBoss(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixBoss(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixItem(titleWithoutNamespace, text, categories, templatesWithParams, refs)
        text = self.fixLieutenant(titleWithoutNamespace, text, categories, templatesWithParams, refs)
        text = self.fixProperty(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixExecutionMethod(text, categories, templatesWithParams)
        text = self.fixClass(text, categories, templatesWithParams)
        text = self.fixTechLab(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixArea(titleWithoutNamespace, text, categories, templatesWithParams)
        #pywikibot.output("******\nOld text:\n%s" % oldText)
        #pywikibot.output("******\nIn text:\n%s" % text)
        # Just comparing oldText with text wasn't sufficient
        changes = False
        for diffline in difflib.ndiff(oldText.splitlines(), text.splitlines()):
            if not diffline.startswith(u'  '):
                changes = True
                break
        if changes:
            print
            pywikibot.output(text)
        if self.debug:
            print
            pywikibot.showDiff(oldText, text)
        return text

    # Now a load of utility methods

    def prependNowysiwygIfNeeded(self, text):
        """
        Returns text with __NOWYSISYG__ prepended if it isn't already in the page.
        """
        keyword = u'__NOWYSIWYG__'
        if keyword in text:
            return text
        return keyword + u'\n' + text

    def appendCategory(self, text, category):
        """
        Returns text with the appropriate category string appended.
        category should be the name of the category itself.
        This function will do all the wiki markup and return the new text.
        """
        str = u'\n[[Category:%s]]' % category
        if str in text:
            # Don't add it if it's already there
            return text
        return text + str

    def removeCategory(self, text, category):
        """
        Returns the text with the appropriate category removed.
        category should be the name of the category itself.
        """
        Rcat = re.compile(category_re % category)
        # Remove the category
        return Rcat.sub('', text)

    def fixNeedsCats(self, text, missing_params, categories, param_cat_map):
        """
        Returns the text with need categories added or removed as appropriate.
        param_cat_map is a dict, indexed by parameter, of Needs categories.
        missing_params is a set of parameters that are missing from the page.
        """
        cats_needed = set()
        for (p,c) in param_cat_map.items():
            if p in missing_params:
                cats_needed.add(c)
        for c in cats_needed:
            if not self.catInCategories(c, categories):
                text = self.appendCategory(text, c)
        for c in set(param_cat_map.values()):
            if self.catInCategories(c, categories) and c not in cats_needed:
                # Only remove specific needs categories, not more general ones
                if c in self.specificNeeds:
                    text = self.removeCategory(text, c)
        return text

    def fixNeedsCategories(self, text, params, categories, param_cat_map):
        """
        Returns the text with need categories added or removed as appropriate.
        param_cat_map is a dict, indexed by parameter, of Needs categories.
        """
        missing_params = missingParams(params, param_cat_map.keys())
        return self.fixNeedsCats(text, missing_params, categories, param_cat_map)

    def findTemplate(self, text, name=None):
        """
        Find a template in text.
        If name is specified, find the named template.
        Returns a tuple - (template name (or None), index where the template starts, index where the template ends)
        Buggy - doesn't work with nested templates
        """
        # Does the page use any templates ?
        for match in Rtemplate.finditer(text):
            found_name = match.expand(r'\g<name>')
            if (name == None) or (found_name == name):
                return (found_name, match.start(), match.end())
        return (None, -1, -1)

    def findSpecificSection(self, text, section):
        """
        Find the specified section in text, starting with a header,
        and ending with a header, template, or category.
        Returns a tuple - (index where the section starts, index where the section ends)
        or (-1, -1) if the section isn't found.
        """
        # Does the page have a section header ?
        header = re.search(ur'==\s*%s\W*==' % section, text)
        if header:
            list_start = header.start()
            # List ends at a template, header or category
            # Skip the header for the section of interest itself
            match = re.search(r'{{|==.*==|\[\[Category', text[list_start+2:])
            if match:
                list_end = list_start+2+match.start()
            else:
                list_end = len(text)
            # Shift list_end back to exactly the end of the list
            while text[list_end-1] in u'\n\r':
                list_end -= 1
            return (list_start, list_end)
        return (-1, -1)

    def findSection(self, text, title=u'',level=-1):
        """
        Find a section in text, starting with a header,
        and ending with a header at the same level, a template, or category.
        Returns a tuple - (section name (or u''), index where the section starts, index where the section ends, level)
        If title is provided, only look for the specified section.
        If level is -1 or not specified, match any level. Otherwise, only match the specified level.
        """
        headers = []
        iterator = Rheader.finditer(text)
        for m in iterator:
            hdr_lvl = len(m.group(1))
            headers.append({'level':hdr_lvl, 'title':m.group(u'title'), 'from':m.start(), 'to':m.end()})
        section_name = u''
        start = -1
        end = -1
        for hdr in headers:
            if (level == -1) or (hdr['level'] == level):
                if start == -1:
                    if (title == u'') or (hdr['title'] == title):
                        # This is our start point
                        section_name = hdr['title']
                        start = hdr['to'] + 1
                        # The end will be the start of the next section at this level
                        level = hdr['level']
                else:
                    # This is our end point
                    end = hdr['from'] - 1
                    break
        if end == -1:
            # Exclude any categories
            m = Rcategory.search(text[start:end])
            if m:
                end = start + m.start() - 1
        return (section_name, start, end, level)

    def catInCategories(self, category, categories):
        """
        Checks whether the specified category is in the list of categories,
        where category is a unicode string and categories is a list of category pages.
        Returns True or False.
        """
        # Is it in the specified category ?
        for this_category in categories:
            if re.search(category_re % category, this_category.title(asLink=True)):
                return True
        return False

    def imageForItemOrIngredient(self, itemName):
        """
        Finds the image for the specified item.
        """
        return image_map.image_for(itemName)

    def checkItemParams(self, text, source, drop_params):
        """
        Checks that the parameters for a drop match the item page.
        params is a dictionary of the drop's parameters.
        Also checks that the drop lists the source.
        Returns modified text with missing parameters added.
        """
        paramless_items = [u'Steel Beam',
                           u'Concrete Block',
                           u'Bronze Shadow Token',
                           u'Silver Shadow Token',
                           u'Laundered Donation Money (I)',
                           u'Laundered Donation Money (II)',
                           u'Laundered Donation Money (III)']
        item_name = drop_params[u'name']
        item = pywikibot.Page(pywikibot.Site(), item_name)
        templatesWithParams = item.templatesWithParams()
        for (temp, params) in templatesWithParams:
            template = temp.title(withNamespace=False)
            #pywikibot.output("Template %s" % template)
            # TODO Clean this code up
            if (u'Item' in template) or (template == u'Ingredient'):
                item_params = utils.paramsToDict(params)
                # Check the drop parameters we do have
                for key in drop_params.keys():
                    if (key == u'name'):
                        continue
                    elif (key == u'creator'):
                        continue
                    elif not dropParamsMatch(drop_params[key], item_params[key]):
                        # TODO Should be able to fix some of them at least...
                        pywikibot.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, item_name, item_params[key], drop_params[key]))
                # Then check for any that may be missing
                for key in [u'name', u'image', u'atk', u'def', u'type']:
                    if key not in drop_params and key in item_params:
                        text = text.replace(ur'name=%s' % item_name, u'name=%s|%s=%s' % (item_name, key, item_params[key]))
                key = u'for'
                if key not in drop_params and key in item_params:
                    # "for" parameter only needed where the item is a Tech Lab ingredient
                    # TODO This isn't quite right. The Drop template treats its "for"
                    #      parameter differently than the Item and Ingredient templates.
                    #      It's probably the Drop template that needs to change, though...
                    # TODO There should be a better way to do this...
                    if item_name not in paramless_items and not self.catInCategories(u'Recombinators', item.categories()):
                        text = text.replace(ur'name=%s' % item_name, u'name=%s|%s=%s' % (item_name, key, item_params[key]))
                if source not in item_params['from']:
                    pywikibot.output("Boss claims to drop %s, but is not listed on that page" % item_name)
            elif u'Lieutenant' in template:
                item_params = utils.paramsToDict(params)
                for key in drop_params.keys():
                    dp = drop_params[key]
                    if key == u'name':
                        continue
                    elif key == u'type':
                        ip = u'Lieutenants'
                    elif key == u'atk':
                        ip = item_params[u'atk_1']
                    elif key == u'def':
                        ip = item_params[u'def_1']
                    else:
                        ip = item_params[key]
                    if not dropParamsMatch(dp, ip):
                        pywikibot.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, item_name, dp, ip))
                if source not in item_params['from']:
                    pywikibot.output("Boss claims to drop %s, but is not listed on that page" % item_name)
            elif (template != u'Job Link') and (template != u'For') and (template != u'Sic'):
                pywikibot.output("Ignoring template %s" % template)
        return text

    def fixEventBoss(self, name, text, categories, templatesWithParams):
        """
        If the page is in both the Bosses and Events categories:
        Ensures that __NOWYSIWYG__ is present.
        Checks each drop's image, type, attack, and defence.
        """
        boss = self.catInCategories(u'Bosses', categories)
        event = self.catInCategories(u'Events', categories)
        # Drop out early if not an event boss page
        # TODO Is there a better test ?
        if not boss or not event:
            return text

        drop_params = [u'image', u'type', u'atk', u'def']

        # __NOWYSISYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check each drop
        for (template, params) in templatesWithParams:
            if template == u'Drop':
                drop_params = utils.paramsToDict(params)
                text = self.checkItemParams(text, name, drop_params)

        return text

    def fixBoss(self, name, text, categories, templatesWithParams):
        """
        If the page is in either the 'Job Bosses' or 'Tech Lab Bosses' categories:
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page is in one of the Job Bosses or Tech Lab Bosses categories.
        Checks each drop's image, type, attack, and defence.
        Checks whether the categories Needs Completion Dialogue, Needs Rewards,
        Needs Stages, and Needs Time Limit are used correctly.
        """
        job_boss = self.catInCategories(u'Job Bosses', categories)
        tl_boss = self.catInCategories(u'Tech Lab Bosses', categories)
        legend_boss = self.catInCategories(u'Legend Bosses', categories)
        # Drop out early if not a boss page
        # TODO Is there a better test ?
        if not job_boss and not tl_boss and not legend_boss:
            return text

        drop_params = [u'image', u'type', u'atk', u'def']

        # __NOWYSISYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check core category
        cat_count = 0
        if job_boss:
            cat_count += 1
        if tl_boss:
            cat_count += 1
        if legend_boss:
            cat_count += 1
        if cat_count > 1:
            pywikibot.output("Boss is in more than one category of Job Bosses, Tech Lab Bosses, and Legend Bosses")

        # Check each drop
        for (template, params) in templatesWithParams:
            if template == u'Drop':
                drop_params = utils.paramsToDict(params)
                text = self.checkItemParams(text, name, drop_params)

        # Check Needs categories
        (dummy, start, end, level) = self.findSection(text, u'Completion Dialogue')
        length = len(text[start:end])
        if self.catInCategories(u'Needs Completion Dialogue', categories):
            if tl_boss or legend_boss:
                pywikibot.output("Tech Lab and Legend bosses should never be categorised Needs Completion Dialogue")
                text = self.removeCategory(text, u'Needs Completion Dialogue')
            elif (start != -1) and (length > 0):
                pywikibot.output("Non-empty completion dialogue section found despite Needs Completion Dialogue category")
                text = self.removeCategory(text, u'Needs Completion Dialogue')
        elif (start == -1) or (length == 0):
            # Section not present or empty
            if job_boss:
                text = self.appendCategory(text, u'Needs Completion Dialogue')

        # We should find a section called Rewards that links to the Boss Drops page
        (dummy, start, end, level) = self.findSection(text, u'[[Boss Drops|Rewards]]')
        # If we don't find one, maybe there's just a 'Rewards' section...
        if (start == -1):
            (dummy, start, end, level) = self.findSection(text, u'Rewards')
            # Replace the header
            text = text.replace(u'=Rewards=', u'=[[Boss Drops|Rewards]]=')
            (dummy, start, end, level) = self.findSection(text, u'[[Boss Drops|Rewards]]')
        if self.catInCategories(u'Needs Rewards', categories):
            if start != -1:
                # There is a Rewards section
                # TODO Check for actual content - may just have sub-headers
                pywikibot.output("Non-empty Rewards section found despite Needs Rewards category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Rewards')

        (dummy, start, end, level) = self.findSection(text, u'Stages')
        if self.catInCategories(u'Needs Stages', categories):
            if start != -1:
                # There is a Stages section
                # TODO Check for actual content - may just have sub-headers
                pywikibot.output("Non-empty Stages section found despite Needs Stages category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Stages')

        (dummy, start, end, level) = self.findSection(text, u'Basic Information')
        if self.catInCategories(u'Needs Time Limit', categories):
            if start != -1:
                # There is a Basic Information section
                # TODO Check for the actual time limit line
                pywikibot.output("Non-empty Basic Information section found despite Needs Time Limit category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Time Limit')

        return text

    def fixArea(self, name, text, categories, templatesWithParams):
        """
        Fixes an Area page.
        Ensures that __NOWYSIWYG__ is present.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        # Drop out if it isn't an area page
        if not self.catInCategories(u'Areas', categories):
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check each template
        common_param_map = {u'name': u'Needs Information', #u'Needs Job Name',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'description': u'Needs Information', #u'Needs Job Description',
                            u'energy': u'Needs Information', #u'Needs Job Energy',
                            u'total_energy': u'Needs Total Energy',
                            u'cash_min': u'Needs Information', #u'Needs Job Cash',
                            u'cash_max': u'Needs Information'} #u'Needs Job Cash'}
        job_param_map = {u'lieutenant': u'Needs Information', #u'Needs Job Lieutenant',
                         # Special code for XP below
                         u'xp': u'Needs Information', #u'Needs Job XP',
                         u'gear_1': u'Needs Item Requirements',
                         u'gear_1_img': u'Needs Information',
                         u'gear_2': u'Needs Item Requirements',
                         u'gear_2_img': u'Needs Information',
                         u'gear_3': u'Needs Item Requirements',
                         u'gear_3_img': u'Needs Information',
                         u'gear_4': u'Needs Item Requirements',
                         u'gear_4_img': u'Needs Information',
                         u'faction': u'Needs Job Faction'}
        xp_pair_param_map = {u'xp_min': u'Needs Information', #u'Needs Job XP',
                             u'xp_max': u'Needs Information'} #u'Needs Job XP'}
        challenge_param_map = {u'lt_1': u'Needs Information',
                               u'lt_1_rarity': u'Needs Information',
                               u'lt_2': u'Needs Information',
                               u'lt_2_rarity': u'Needs Information',
                               u'lt_3': u'Needs Information',
                               u'lt_3_rarity': u'Needs Information',
                               u'lt_4': u'Needs Information',
                               u'lt_4_rarity': u'Needs Information',
                               u'recombinator': u'Needs Information'}
        missing_params = set()
        for template, params in templatesWithParams:
            if template == u'Job':
                missing_params |= missingParams(params, common_param_map.keys() + job_param_map.keys())
                # xp_min and xp_max will do instead of xp
                if u'xp' in missing_params:
                    missing_params.remove(u'xp')
                    missing_params |= missingParams(params, xp_pair_param_map.keys())
                # Special case for missing gear_n and gear_n_img parameters
                got_gear = False
                for i in range(4,0,-1):
                    root = u'gear_%d' % i
                    if root in missing_params:
                        # Shouldn't have higher number without lower
                        if not got_gear:
                            missing_params.remove(root)
                            img_param = root + u'_img'
                            if img_param in missing_params:
                                missing_params.remove(img_param)
                    else:
                        got_gear = True
            elif template == u'Challenge Job':
                missing_params |= missingParams(params, common_param_map.keys() + xp_pair_param_map.keys() + challenge_param_map.keys())
                # TODO Check the LT rarities
        pywikibot.output("Set of missing job parameters is %s" % missing_params)
        # Ensure the Needs categories are correct
        text = self.fixNeedsCats(text, missing_params, categories, dict(common_param_map.items() + job_param_map.items() + challenge_param_map.items()))

        return text

    def fixTechLab(self, name, text, categories, templatesWithParams):
        """
        Fixes the Tech Lab and Tech Lab - Historic pages.
        Ensures that __NOWYSIWYG__ is present.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        if u'Tech Lab' not in name:
            return text

        # Is this a historic recipe ?
        is_old = False
        if u'Historic' in name:
            is_old = True

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check each recipe
        recipe_param_map = {u'name': u'Needs Information', #u'Needs Item Name',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'atk': u'Needs Stats',
                            u'def': u'Needs Stats',
                            u'time': u'Needs Build Time',
                            u'part_1': u'Needs Information'} #u'Needs Ingredient'}
        old_recipe_map = {u'available' : u'Needs Information'}
        missing_params = set()
        for template, params in templatesWithParams:
            if u'Recipe' in template:
                missing_params |= missingParams(params, recipe_param_map.keys())
                # Find this item on the page
                name = utils.paramFromParams(params, u'name')
                # This can take a while, so reassure the user
                pywikibot.output("Checking %s" % name)
                recipe_start = text.find(name)
                if is_old:
                    missing_params |= missingParams(params, old_recipe_map.keys())
                # TODO Cross-reference against item page
                # Check images for ingredients
                n = 0
                while True:
                    n += 1
                    part_str = u'part_%s' % n
                    part = utils.paramFromParams(params, part_str)
                    if part is None:
                        break
                    part_img_str = part_str + u'_img'
                    part_img = utils.paramFromParams(params, part_img_str)
                    image = self.imageForItemOrIngredient(part)
                    if image is not None:
                        if part_img == None:
                            # Insert an appropriate part_img parameter
                            new_part = re.sub(ur'(\|\W*%s\W*=\W*%s)' % (part_str, utils.escapeStr(part)),
                                              ur'\1\n|%s=%s' % (part_img_str, image),
                                              text[recipe_start:],
                                              1)
                            text = text[:recipe_start] + new_part
                        elif image != part_img:
                            # TODO Replace the image with the one from the ingredient page
                            pywikibot.output("Image mismatch. %s has %s, %s has %s" % (name, part_img, part, image))
        pywikibot.output("Set of missing recipe parameters is %s" % missing_params)
        # Ensure the Needs categories are correct
        text = self.fixNeedsCats(text, missing_params, categories, recipe_param_map)

        return text

    def fixClass(self, text, categories, templatesWithParams):
        """
        If the page uses the template 'Class':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        Checks for mandatory template parameters or corresponding Needs category.
        Checks for increasing skill levels.
        """
        # Does the page use the Class template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Class':
                the_template = template
                the_params = params

        # Drop out early if not a class page
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check mandatory parameters of the Class template
        class_param_map = {u'description': u'Needs Description',
                           u'short_description': u'Needs Information', #u'Needs Short Description',
                           u'image': u'Needs Improvement', #u'Needs Image',
                           u'weapons': u'Needs Information', #u'Needs Weapons',
                           u'strength': u'Needs Information', #u'Needs Strength',
                           u'special_atk_name': u'Needs Information', #u'Needs Special Attack Name',
                           u'special_atk_effect': u'Needs Information', #u'Needs Special Attack Effect',
                           u'help_text': u'Needs Information'} #u'Needs Help Text'}
 
        text = self.fixNeedsCategories(text, the_params, categories, class_param_map)

        skill_param_map = {u'level': u'Needs Information', #u'Needs Skill Level',
                           u'effect': u'Needs Information', #u'Needs Skill Effect',
                           u'cost': u'Needs Information', #u'Needs Skill Cost',
                           u'time': u'Needs Information'} #u'Needs Skill Time'}
        # Check each use of the Skill template
        missing_params = set()
        old_level = 0
        for template,params in templatesWithParams:
            if template == u'Skill':
                level = utils.paramFromParams(params, u'level')
                if level is not None:
                    if (level == old_level) and (level != u'1'):
                        pywikibot.output("copy-paste error for skill level %s (%s) ?" % (level, params))
                    old_level = level
                missing_params |= missingParams(params, skill_param_map.keys())
        # Ensure the Needs categories are correct
        text = self.fixNeedsCats(text, missing_params, categories, skill_param_map)

        return text

    def fixExecutionMethod(self, text, categories, templatesWithParams):
        """
        If the page uses the template 'Execution Method':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        # Does the page use the execution method template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Execution Method':
                the_template = template
                the_params = params

        # Drop out early if not an execution method page
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check mandatory parameters
        method_param_map = {u'cost': u'Needs Stamina Cost',
                            u'success': u'Needs Initial Success',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'chance': u'Needs Information', #u'Needs Bonus Chance',
                            u'bonus': u'Needs Information', #u'Needs Bonus',
                            u'need': u'Needs Information'} #u'Needs Prerequisite'}
 
        text = self.fixNeedsCategories(text, the_params, categories, method_param_map)

        return text

    def fixSafeHouse(self, text, categories):
        """
        Checks that the page includes appropriate information (like Upgrade properties).
        Checks that the cost table matches the template for upgrade properties.
        """
        # TODO implement this function
        return text

    def fixFortress(self, text, categories):
        """
        Checks that the page includes appropriate information (like Upgrade properties).
        Checks that the cost table matches the template for upgrade properties.
        """
        # TODO implement this function
        # First, retrieve the expected cost ratios from the template
        Rrow = re.compile(ur'\|\s*(?P<level>\d+).*cost}}}\*(?P<ratio>[\d.]+)')
        table_page = pywikibot.Page(pywikibot.Site(), u'Template:Property Cost Table')
        table_text = table_page.get()
        iterator = Rrow.finditer(table_text)
        ratios = {1:1.0}
        for m in iterator:
            level = m.group('level')
            ratio = m.group('ratio')
            ratios[int(level)] = float(ratio)
        # Now we can check the cost table
        Rrow2 = re.compile(ur'\|\s*(?P<level>\d+).*formatnum:\s*(?P<cost>\d+)')
        iterator = Rrow2.finditer(text)
        costs = {}
        for m in iterator:
            level = int(m.group('level'))
            cost = int(m.group('cost'))
            costs[level] = cost
        base_cost = costs[1]
        for level,cost in costs.iteritems():
            expected_cost = base_cost * ratios[level]
            if cost != expected_cost:
                pywikibot.output("Level %d cost of %d != expected %d" % (level, cost, expected_cost))
        return text

    def fixProperty(self, name, text, categories, templatesWithParams):
        """
        If the page uses either of the templates 'Income Property' or 'Upgrade Property':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        # Does the page use a property template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Income Property':
                the_template = template
                the_params = params
            elif template == u'Upgrade Property':
                the_template = template
                the_params = params

        # Fortress and Safe House are special
        if name ==u'Safe House':
            return self.fixSafeHouse(text, categories)
        elif name ==u'Fortress':
            return self.fixFortress(text, categories)

        # Drop out early if not a property page
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check mandatory parameters
        prop_param_map = {u'description': u'Needs Description',
                          u'cost': u'Needs Initial Cost',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
        if the_template == u'Upgrade Property':
            prop_param_map[u'power'] = u'Needs Power'
        else:
            prop_param_map[u'income'] = u'Needs Income'

        # Build time is required for non-FP properties only
        fp_prop = utils.paramFromParams(the_params, u'fp_prop')
        if fp_prop:
            build_time = utils.paramFromParams(the_params, u'time')
            if build_time:
                pywikibot.output("FP property has build time!")
        else:
            prop_param_map[u'time'] = u'Needs Build Time'
 
        text = self.fixNeedsCategories(text, the_params, categories, prop_param_map)

        return text

    def fixLtSources(self, name, text, categories, the_params, refs):
        """
        Fix the list of sources on a Lieutenant page.
        Returns the modified text parameter.
        """
        fromParam = utils.paramFromParams(the_params, u'from')
        # Check where the Lt can be obtained from
        # TODO Ones that can be bought are listed on [[Category:Lieutenants]]
        sources = []
        for r in refs:
            if self.catInCategories(u'Crates', r.categories()):
                sources.append(u'[[%s]]' % r.title(withNamespace=False))
                # Check that it's in Crate Lieutenants
                c = u'Crate Lieutenants'
                if not self.catInCategories(c, categories):
                    text = self.appendCategory(text, c)
            elif self.catInCategories(u'Events', r.categories()):
                sources.append(u'[[%s]]' % r.title(withNamespace=False))
                # Check that it's in Event Lieutenants
                c = u'Event Lieutenants'
                if not self.catInCategories(c, categories):
                    text = self.appendCategory(text, c)
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if template == u'Challenge Job':
                    area = r.title(withNamespace=False)
                    job = utils.paramFromParams(params, u'name')
                    for p in params:
                        if p.startswith(u'lt_') and name in p:
                            sources.append(u'{{Job Link|district=%s|job=%s}}' % (area, job))
                elif template == u'FP Item Row':
                    if name == utils.paramFromParams(params, u'lieutenant'):
                        sources.append(u'[[Black Market]]')
                        c = u'Favor Point Lieutenants'
                        # Check that it's in Favor Point Lieutenants
                        if not self.catInCategories(c, categories):
                            text = self.appendCategory(text, c)
        for s in sources:
            if s not in fromParam:
                pywikibot.output("***Need to add %s" % s)
                # First convert a single item to a list
                if not u'\n' in fromParam:
                    text = text.replace(fromParam, u'<br/>\n*' + fromParam)
                text = text.replace(fromParam, fromParam + u'\n*%s' % s)
        # TODO Also check for wrongly-listed sources

        return text

    def itemsInRefs(self, refs):
        """
        Returns a dict with an entry for each item page in refs.
        Key is the item name. Value is a (power, image) tuple.
        """
        refItems = {}
        for r in refs:
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if u'Item' in template:
                    powerParam = utils.paramFromParams(params, u'power')
                    imageParam = utils.paramFromParams(params, u'image')
                    refItems[r.title(withNamespace=False)] = (powerParam, imageParam)
        return refItems

    def affectsLt(self, lt, rarity, faction, beneficiary):
        """
        Returns True if the specified Lt matches the criteria in beneficiary.
        """
        # If the LT's name appears, that's an easy one
        if lt in beneficiary:
            return True

        parseRe = re.compile(ur'\[\[\s*:(Category:[^]\|]*)(|[^]]*)\]\]')

        # What categories of Lt does the item help ?
        cats = parseRe.findall(beneficiary)
        print("%s: %s" % (beneficiary, cats))

        if len(cats) == 0:
            return False

        catStr = u'Category:%s Lieutenants'
        lCat = u'Category:Lieutenants'
        rCat = catStr % rarity
        fCat = catStr % faction

        # For this Lt to benefit, it must be in all the listed categories
        for c in cats:
            if lCat != c[0] and rCat != c[0] and fCat != c[0]:
                return False
        return True

    def splitPower(self, power):
        """
        Returns a (effect, beneficiary, multiplier, stack) tuple for the power,
        where multiplier may be None, and stack is a boolean.
        """
        # Does the power stack ?
        stack = (None == noStackRe.search(power))
        # Remove any "no stack" string
        power = noStackRe.sub('', power)

        # Try the "all" pattern
        res = allRe.match(power)
        if res is not None:
            return (res.group(2), res.group(1), None, stack)

        # And the "when" pattern
        res = whenRe.match(power)
        if res is not None:
            return (res.group(1), res.group(2), None, stack)

        # Split at our separators
        res = sepRe.split(power)
        if len(res) == 2:
            return (res[0], res[1], None, stack)
        elif len(res) == 3:
            return (res[0], res[1], res[2], stack)
        return (power, None, None, stack)

    def fixLtItems(self, name, text, the_template, the_params, refs):
        """
        Checks the list of items that affect this Lt.
        Returns the modified text parameter.
        """
        # Validate items parameters, if present
        # Check for items that affect every Lt
        refs = cat_refs_map.refs_for(u'Lieutenants')
        refItems = self.itemsInRefs(refs)

        # Check for any items that have a power that affects this Lt
        refItems2 = self.itemsInRefs(refs)
        # Does the item have a power that affects this Lt ?
        x = {k: v for k, v in refItems2.iteritems() if v[0] is not None and name in v[0]}
        refItems.update(x)

        # Check for items that affect all Lts of this rarity
        rarity = the_template.split()[1]
        refs = cat_refs_map.refs_for(u'%s Lieutenants' % rarity)
        refItems.update(self.itemsInRefs(refs))

        # Check for items that affect the entire faction
        faction = utils.paramFromParams(the_params, u'faction')
        refs = cat_refs_map.refs_for(u'%s Lieutenants' % faction)
        refItems.update(self.itemsInRefs(refs))

        # TODO Filter out any items that don't affect this Lt
        refItems = {k: v for k, v in refItems.iteritems() if self.affectsLt(name, rarity, faction, self.splitPower(v[0])[1])}

        items = {}
        i = 0
        while True:
            i += 1
            name_str = u'item_%d' % i
            power_str = u'item_%d_pwr' % i
            image_str = u'item_%d_img' % i
            nameParam = utils.paramFromParams(the_params, name_str)
            powerParam = utils.paramFromParams(the_params, power_str)
            imageParam = utils.paramFromParams(the_params, image_str)
            if nameParam:
                items[nameParam] = (powerParam, imageParam)
            else:
                break
        i = len(items)
        # compare the two lists and address any mismatches
        for key in refItems.keys():
            if key in items:
                # Compare the details
                if refItems[key][0] != items[key][0]:
                    pywikibot.output("Mismatch in power for %s - %s vs %s" % (key, refItems[key][0], items[key][0]))
                    pattern = utils.escapeStr(items[key][0])
                    text = re.sub(pattern, refItems[key][0], text)
                if refItems[key][1] != items[key][1]:
                    pywikibot.output("Mismatch in image for %s - %s vs %s" % (key, refItems[key][1], items[key][1]))
                    pattern = utils.escapeStr(items[key][1])
                    text = re.sub(pattern, refItems[key][1], text)
            else:
                pywikibot.output("Missing item %s which gives %s" % (key, refItems[key][0]))
                # Add the item. No way to determine which item should be which
                i += 1
                #(temp, start, end) = self.findTemplate(text, the_template)
                #assert temp != None, "Unable to find template %s in page" % the_template
                # TODO There must be a better way to do this...
                the_tuple = (i, key, i, refItems[key][0], i, refItems[key][1])
                new_params = u'|item_%d=%s\n|item_%d_pwr=%s\n|item_%d_img=%s' % the_tuple
                text = re.sub(the_template, u'%s\n%s' % (the_template, new_params), text)
        # TODO Deal with any that are in the items list but not in refItems
        pass
        return text

    def fixLtNeedsParams(self, text, the_params, categories, is_tech_lab_item):
        """
        Fix the "Needs" parameters on a Lieutenant page.
        Returns modified version of text parameter.
        """
        # Check mandatory parameters
        lt_param_map = {u'description': u'Needs Description',
                        u'quote': u'Needs Quote',
                        u'ability': u'Needs Powers',
                        u'image': u'Needs Improvement', #u'Needs Image',
                        u'faction': u'Needs Information'} #u'Needs Faction'}
        # Needs Powers is used for both ability and pwr_1..10
        for i in range(1,10):
            lt_param_map[u'pwr_%d' % i] = u'Needs Powers'
        # Check for atk_1..10 and def_1..10
        for i in range(1,10):
            lt_param_map[u'atk_%d' % i] = u'Needs Stats'
            lt_param_map[u'def_%d' % i] = u'Needs Stats'

        # If it's a tech lab lieutenant, don't bother checking what it's made from.
        # That will be done in fixTechLabItem.
        if not is_tech_lab_item:
            lt_param_map[u'from'] = u'Needs Source'
 
        return self.fixNeedsCategories(text, the_params, categories, lt_param_map)

    def fixLieutenant(self, name, text, categories, templatesWithParams, refs):
        """
        If the page uses any of the templates 'Lieutenant Common', 'Lieutenant Uncommon',
        'Lieutenant Rare, or 'Lieutenant Epic':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        Removes any empty stat or power parameters, and any (old) item parameters.
        Adds missing sources.
        Checks items and adds missing ones.
        """
        # Does the page use a lieutenant template ?
        the_params = None
        ingredients = None
        is_tech_lab_item = name in recipe_cache.recipes()
        for template,params in templatesWithParams:
            # Find the templates we're interested in
            if template == u'Lieutenant':
                pywikibot.output("Directly uses Lieutenant template")

            if u'Lab' in template:
                is_tech_lab_item = True
                ingredients = params

            if template == u'Lieutenant Common':
                the_template = template
                the_params = params
            elif template == u'Lieutenant Uncommon':
                the_template = template
                the_params = params
            elif template == u'Lieutenant Rare':
                the_template = template
                the_params = params
            elif template == u'Lieutenant Epic':
                the_template = template
                the_params = params

        # Drop out early if not a lieutenant page
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Now nuke any empty stat or power parameters, and any items parameters
        to_nuke = []
        for param in the_params:
            p = param.rstrip()
            if p[-1] == u'=':
                if u'atk_' in p or u'def_' in p or u'pwr_' in p:
                    pywikibot.output("Nuking empty parameter %s" % param)
                    text = text.replace(u'|%s' % p, '')
                    to_nuke.append(param)
            elif p.startswith(u'items'):
                pywikibot.output("Page has an items parameter")
                pywikibot.output("%s" % (u'|%s' % p))
                text = text.replace(u'|%s' % p, '')
                to_nuke.append(param)
        for i in to_nuke:
            the_params.remove(i)

        text = self.fixLtNeedsParams(text, the_params, categories, is_tech_lab_item)

        if not is_tech_lab_item:
            text = self.fixLtSources(name, text, categories, the_params, refs)

        # Do special checks for any Epic Research Items
        if is_tech_lab_item:
            text = self.fixTechLabItem(name, text, the_params, categories, ingredients, False)

        # Validate items parameters, if present
        text = self.fixLtItems(name, text, the_template, the_params, refs)

        return text

    def fixItem(self, name, text, categories, templatesWithParams, refs):
        """
        If the page uses any of the templates 'Item', 'Gift Item', 'Mystery Gift Item', 
        'Faction Item', 'Special Item', 'Basic Item', 'Battle Rank Item', or 'Ingredient':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        Checks that the item is listed everywhere it says it can be obtained.
        Checks whether the categories Needs Cost and Needs Type are used correctly.
        Calls the appropriate fix function for the specific type of item.
        """
        # All these categories should be added by the various templates
        # Note that Daily Rewards also logically belongs here, but we do clever stuff for that one
        implicit_categories = [u'Items',
                               u'Common Items',
                               u'Uncommon Items',
                               u'Rare Items',
                               u'Epic Items',
                               u'Legendary Items',
                               u'Special Items',
                               u'Basic Items',
                               u'Battle Rank Items',
                               u'Ingredients',
                               u'Gear',
                               u'Vehicles',
                               u'Weapons',
                               u'Rifle',
                               u'Heavy Weapons',
                               u'Handguns',
                               u'Melee Weapons',
                               u'Gift Items',
                               u'Faction Items',
                               u'Dragon Syndicate Items',
                               u'Street Items',
                               u'The Cartel Items',
                               u'The Mafia Items',
                               u'Epic Research Items',
                               u'Needs Type',
                               u'Classes',
                               u'Income Properties',
                               u'Upgrade Properties',
                               u'Execution Methods',
                               u'Lieutenants',
                               u'Common Lieutenants',
                               u'Uncommon Lieutenants',
                               u'Rare Lieutenants',
                               u'Epic Lieutenants',
                               u'Dragon Syndicate Lieutenants',
                               u'Street Lieutenants',
                               u'The Cartel Lieutenants',
                               u'The Mafia Lieutenants']

        # Does the page use an item template ?
        the_params = None
        ingredients = None
        is_tech_lab_item = name in recipe_cache.recipes()
        for template,params in templatesWithParams:
            # Find the templates we're interested in
            if template == u'Item':
                pywikibot.output("Directly uses Item template")

            if u'Lab' in template:
                is_tech_lab_item = True
                ingredients = params

            if template == u'Gift Item':
                the_template = template
                the_params = params
            elif template == u'Mystery Gift Item':
                the_template = template
                the_params = params
            elif template == u'Faction Item':
                the_template = template
                the_params = params
            elif template == u'Special Item':
                the_template = template
                the_params = params
            elif template == u'Basic Item':
                the_template = template
                the_params = params
            elif template == u'Battle Rank Item':
                the_template = template
                the_params = params
            elif template == u'Ingredient':
                the_template = template
                the_params = params

        # Drop out early if not an item page
        # This ignores Stamina Pack and Energy Pack, but that's probably fine
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # Check for explicit categories that should be implicit
        for cat in implicit_categories:
            if self.catInCategories(cat, categories):
                text = self.removeCategory(text, cat)

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # If the item comes from somewhere special (other than tech lab), do cross-ref check
        # (Mystery) Gift Item template uses from with a different meaning
        if template != u'Gift Item' and template != u'Mystery Gift Item' and not is_tech_lab_item:
            from_param = utils.paramFromParams(the_params, u'from')
            if from_param is not None:
                text = self.fixDrop(name, text, from_param, refs)

        # Do more detailed checks for specific sub-types
        if the_template == u'Gift Item':
            text = self.fixGiftItem(name, text, the_params, categories)
        elif the_template == u'Mystery Gift Item':
            text = self.fixMysteryGiftItem(name, text, the_params, categories)
        elif the_template == u'Faction Item':
            text = self.fixFactionItem(name, text, the_params, categories)
        elif the_template == u'Special Item':
            text = self.fixSpecialItem(text, the_params, categories, is_tech_lab_item)
        elif the_template == u'Basic Item':
            text = self.fixBasicItem(text, the_params, categories)
        elif the_template == u'Battle Rank Item':
            text = self.fixBattleItem(name, text, the_params, categories)
        elif the_template == u'Ingredient':
            text = self.fixIngredient(name, text, the_params, categories, is_tech_lab_item)

        # Do special checks for any Epic Research Items
        if is_tech_lab_item:
            text = self.fixTechLabItem(name, text, the_params, categories, ingredients)

        return text

    def fixDrop(self, name, text, from_param, refs):
        """
        Check that the page lists the right places it can be obtained from.
        Adds any that are missing
        """
        # First, find pages that list this item as a drop
        # Starting with the list of pages that link here
        source_set = set()
        for r in refs:
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if template == u'Drop':
                    if utils.paramFromParams(params, u'name') == name:
                        source_set.add(r.title(withNamespace=False))
                elif template == u'Mystery Gift Item':
                    gift_params = utils.paramsToDict(params)
                    if name in gift_params.values():
                        source_set.add(r.title(withNamespace=False))
                elif template == u'Execution Method':
                    if name in utils.paramFromParams(params, u'bonus'):
                        source_set.add(r.title(withNamespace=False))
            # Assume any page liked to from the Favor Point page is available from the Black Market
            if r.title(withNamespace=False) == u'Favor Point':
                source_set.add(u'Black Market')
            # Don't call r.categories() for redirects
            elif r.isRedirectPage():
                pass
            # If it's linked to from an event page, assume it's an event reward
            elif self.catInCategories(u'Events', r.categories()):
                source_set.add(r.title(withNamespace=False))
        # Then, find the places listed as sources in this page
        # Remove any that match from the source list, leaving missing sources
        # Count the number of sources already in the list as we go
        src_count = 0
        iterator = Rlink.finditer(from_param)
        for m in iterator:
            src_count += 1
            src = m.group('page')
            # Find the end of that line
            start = m.end('page')
            eol = from_param.find('\n', start)
            if src in source_set:
                source_set.remove(src)
            elif u'before' in from_param[start:eol]:
                # We don't expect the item to be present on that page any more
                pass
            elif src == u':Category:Crates':
                # Ignore items that list the original crate as a source
                pass
            elif src == u'Bosses':
                # "all bosses" is a valid source, even if item is not listed there
                pass
            elif src == u'Jobs':
                # "all jobs" is a valid source, even if item is not listed there
                pass
            else:
                # Note that this is not necessarily an error, but is worth investigating
                pywikibot.output("Page lists %s as a source, but that page doesn't list it as a drop" % src)
        # Convert from single source to a list if necessary
        if len(source_set) > 0 and src_count == 1:
            text = text.replace(from_param, u'<br/>\n*' + from_param)
        # Add missing sources to the page
        for src in source_set:
            text = text.replace(from_param, from_param + u'\n*[[%s]]' % src)
        return text

    def fixItemType(self, text, params, categories):
        """
        Checks the type parameter.
        Adds or removes the Needs Type category.
        """
        types = [u'Gear',
                 u'Vehicles',
                 u'Melee Weapons',
                 u'Rifles',
                 u'Handguns',
                 u'Heavy Weapons',
                 u'Needs Type']
        cat = u'Needs Type'

        type_param = utils.paramFromParams(params, u'type')
        if type_param == None:
            # Add a type parameter, with value Needs Type
            # Note that this just finds the first instance of params...
            start = text.find(params[0])
            if start != -1:
                text = text[0:start] + u'type=' + cat + u'\n|' + text[start:]
            else:
                assert 0, "Failed to find params %s" % params
        else:
            # Check that the type is one we expect
            if oneCap(type_param) not in types:
                pywikibot.output("Unexpected type '%s'" % type_param)
                # Change it to Needs Type
                # Note that this replaces every instance of the text in type_param...
                text.replace(type_param, cat)

        return text

    def fixGiftLevel(self, name, text, params, categories):
        """
        Checks the from parameter.
        Adds or removes Needs Minimum Level category.
        Warns if the from parameter differs from what the Gift page says.
        """
        from_param = utils.paramFromParams(params, u'from')
        if from_param == None:
            if not self.catInCategories(u'Needs Minimum Level', categories):
                text = self.appendCategory(text, u'Needs Minimum Level')
        else:
            if self.catInCategories(u'Needs Minimum Level', categories):
                text = self.removeCategory(u'Needs Minimum Level')
            gift_page = pywikibot.Page(pywikibot.Site(), u'Gift')
            iterator = Rgift.finditer(gift_page.get())
            for m in iterator:
                if m.group('item') == name:
                    if m.group('level') != from_param:
                        pywikibot.output("Minimum level mismatch - Gift page says %s, this page says %s" % (m.group('level'), from_param))
        return text

    def fixGiftItem(self, name, text, params, categories):
        """
        Ensures that gift items have description, image, atk, def, cost, rarity, and from
        parameters, or appropriate "Needs" category.
        Trusts that type param will be checked elsewhere.
        Checks that the minimum level is specified, and that it matches what the Gift page says.
        Assumes that that page uses the Gift Item template.
        """
        # Check mandatory parameters
        gift_param_map = {u'description': u'Needs Description',
                          u'atk': u'Needs Stats',
                          u'def': u'Needs Stats',
                          u'cost': u'Needs Cost',
                          u'rarity': u'Needs Rarity',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, gift_param_map)

        # Check from parameter against the Gift page
        text = self.fixGiftLevel(name, text, params, categories)

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixMysteryGiftItem(self, name, text, params, categories):
        """
        Ensures that mystery gift items have image, from, item_1, and item_2
        parameters, or appropriate "Needs" category.
        Checks that the minimum level is specified, and that it matches what the Gift page says.
        Assumes that that page uses the Mystery Gift Item template.
        """
        # Check mandatory parameters
        gift_param_map = {u'item_1': u'Needs Information', #u'Needs Item',
                          u'item_2': u'Needs Information', #u'Needs Item',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, gift_param_map)

        # Check from parameter against the Gift page
        text = self.fixGiftLevel(name, text, params, categories)

        return text

    def fixFactionItem(self, name, text, params, categories):
        """
        Ensures that faction items have description, image, atk, def, cost, rarity params
        or appropriate "Needs" category.
        Checks that the faction is specified, and that the item is listed on that page, and
        that the points param is right.
        Assumes that the page uses the Faction Item template.
        """
        # Check mandatory parameters
        faction_param_map = {u'description': u'Needs Description',
                             u'atk': u'Needs Stats',
                             u'def': u'Needs Stats',
                             u'cost': u'Needs Cost',
                             u'rarity': u'Needs Rarity',
                             u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, faction_param_map)

        # Check points against corresponding faction page
        faction_param = utils.paramFromParams(params, u'faction')
        points_param = utils.paramFromParams(params, u'points')
        if faction_param == None:
            if not self.catInCategories(u'Needs Information', categories):
                text = self.appendCategory(text, u'Needs Information') # u'Needs Faction'
        elif points_param == None:
            if not self.catInCategories(u'Needs Unlock Criterion', categories):
                text = self.appendCategory(text, u'Needs Unlock Criterion')
        else:
            faction_page = pywikibot.Page(pywikibot.Site(), faction_param)
            iterator = Rfaction.finditer(faction_page.get())
            for m in iterator:
                if m.group('item') == name:
                    if points_param != m.group('points'):
                        # Change the value
                        # Note that this replaces every instance of the text in points_param...
                        text.replace(points_param, m.group('points'))

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixSpecialItem(self, text, params, categories, is_tech_lab_item):
        """
        Ensures that special items have description, image, atk, def, cost, rarity, type
        and from params or appropriate "Needs" category.
        Assumes that the page uses the Special Item template.
        """
        # Check mandatory parameters
        special_param_map = {u'description': u'Needs Description',
                             u'atk': u'Needs Stats',
                             u'def': u'Needs Stats',
                             u'cost': u'Needs Cost',
                             u'rarity': u'Needs Rarity',
                             u'image': u'Needs Improvement'} #u'Needs Image'}
        # If it's a tech lab item, don't bother checking what it's made from.
        # That will be done in fixTechLabItem.
        if not is_tech_lab_item:
            special_param_map[u'from'] = u'Needs Source'
 
        text = self.fixNeedsCategories(text, params, categories, special_param_map)

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixBasicItem(self, text, params, categories):
        """
        Ensures that basic items have description, image, atk, def, cost, rarity, quote
        and time params or appropriate "Needs" category.
        Checks that either level or area is specified.
        Checks that it not explicitly in Daily Rewards category.
        Assumes that the page uses the Basic Item template.
        """
        # Check mandatory parameters
        basic_param_map = {u'description': u'Needs Description',
                           u'atk': u'Needs Stats',
                           u'def': u'Needs Stats',
                           u'cost': u'Needs Cost',
                           u'rarity': u'Needs Rarity',
                           u'quote': u'Needs Quote',
                           u'time': u'Needs Build Time',
                           u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, basic_param_map)

        # Check that we have either level or district but not both
        level_param = utils.paramFromParams(params, u'level')
        area_param = utils.paramFromParams(params, u'district')
        if level_param == None:
            if area_param == None:
                pywikibot.output("Missing both level and district parameters")
                if not self.catInCategories(u'Needs Unlock Criterion', categories):
                    text = self.appendCategory(text, u'Needs Unlock Criterion')
        else:
            if area_param is not None:
                pywikibot.output("Both level and district parameters are present")

        # Ensure that daily items are specified with parameter, not explicit category
        cat = u'Daily Rewards'
        if self.catInCategories(cat, categories):
            text = self.removeCategory(text, cat)
            # Add a daily parameter, with value yes if not already present
            daily_param = utils.paramFromParams(params, u'daily')
            if daily_param == None:
                # Note that this just finds the first instance of params[0]...
                start = text.find(params[0])
                if start != -1:
                    text = text[0:start] + u'daily=yes|' + text[start:]
                else:
                    assert 0, "Failed to find params %s" % params

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixBattleItem(self, name, text, params, categories):
        """
        Ensures that battle rank items have description, image, atk, def, cost, rarity params
        or appropriate "Needs" category.
        Checks that the battle rank is specified, and that it matches what the Battle Rank page says.
        Assumes that the page uses the Battle Rank Item template.
        """
        # Check mandatory parameters
        battle_param_map = {u'description': u'Needs Description',
                            u'atk': u'Needs Stats',
                            u'def': u'Needs Stats',
                            u'cost': u'Needs Cost',
                            u'rarity': u'Needs Rarity',
                            u'time': u'Needs Build Time',
                            u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, battle_param_map)

        # Check rank parameter against Battle Rank page
        rank_param = utils.paramFromParams(params, u'rank')
        if rank_param == None:
            if not self.catInCategories(u'Needs Unlock Criterion', categories):
                text = self.appendCategory(text, u'Needs Unlock Criterion')
        else:
            rank_page = pywikibot.Page(pywikibot.Site(), u'Battle Rank')
            templatesWithParams = rank_page.templatesWithParams()
            for tmp,p in templatesWithParams:
                t = tmp.title(withNamespace=False)
                if t == u'Battle Rank List':
                    rank = utils.paramFromParams(u'number',p)
                    item = utils.paramFromParams(u'reward',p)
                    if item == u'[[%s]]' % name and rank != rank_param:
                        pywikibot.output("Minimum battle rank mismatch - Battle Rank page says %s, this page says %s" % (rank, rank_param))

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixIngredient(self, name, text, params, categories, is_tech_lab_item):
        """
        Ensures that ingredient items have image, rarity, from and for params
        or appropriate "Needs" category.
        Checks that the item is listed on the from and for pages.
        Assumes that the page uses the Ingredient template.
        """
        # Check mandatory parameters
        ingr_param_map = {u'rarity': u'Needs Rarity',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
 
        # If it's a tech lab item, from parameter will be misleading
        if not is_tech_lab_item:
            ingr_param_map[u'from'] = u'Needs Source'

        text = self.fixNeedsCategories(text, params, categories, ingr_param_map)

        for_param = utils.paramFromParams(params, u'for')
        if for_param == None:
            if not self.catInCategories(u'Needs Information', categories):
                text = self.appendCategory(text, u'Needs Information') # u'Needs Purpose'
        else:
            #TODO Check item is listed as an ingredient where appropriate
            pass

        return text

    def fixTechLabItem(self, name, text, params, categories, lab_params, check_image=True):
        """
        Check that it is listed as made in the same way on its page and the Tech Lab page.
        Check that atk and def match what the Tech Lab page says.
        If check_image is True, also check that the image matches the one on the Tech Lab page.
        """
        # Find this recipe on one of the tech lab pages
        recipe_dict = utils.paramsToDict(recipe_cache.recipe_for(name))

        # Now we can cross-check between the two
        # Page template has atk, def, image, and description
        # Lab template has time, num_parts, part_1..part_n
        # Recipe template has time, atk, def, description, image, part_1..part_n
        # Recipe description is not expected to match item description
        if lab_params is None:
            lab_dict = {}
            # Create an empty Lab template inclusion to add params to
            # TODO May actually want Lab Four of a Kind or Lab Full House
            if u'|from=' in text:
                text = text.replace(u'|from=', u'|from=<br\\>\n*{{Lab|in_list=yes}}\n*', 1)
            else:
                text = text.replace(u'|image=', u'|from={{Lab}}\n|image=', 1)
        else:
            lab_dict = utils.paramsToDict(lab_params)

        # Compare image
        if check_image:
            img_param = utils.paramFromParams(params, u'image')
            # TODO Insert missing image
            if img_param is not None and img_param != recipe_dict[u'image']:
                pywikibot.output("Image parameter mismatch - %s in page, %s on Tech Lab page" % (img_param, recipe_dict[u'image']))

        # TODO Add Needs Build Time category if appropriate

        # Compare atk
        atk_param = utils.paramFromParams(params, u'atk')
        if atk_param is not None and atk_param != recipe_dict[u'atk']:
            pywikibot.output("Attack parameter mismatch - %s in page, %s on Tech Lab page" % (atk_param, recipe_dict[u'atk']))

        # Compare def
        def_param = utils.paramFromParams(params, u'def')
        if def_param is not None and def_param != recipe_dict[u'def']:
            pywikibot.output("Defence parameter mismatch - %s in page, %s on Tech Lab page" % (def_param, recipe_dict[u'def']))

        # Check that num_parts is right, if present
        # For some Lab templates, num_parts is optional. Those should all have 5 parts
        try:
            num_parts = int(lab_dict[u'num_parts'])
        except KeyError, TypeError:
            num_parts = 5
        total = 0
        i = 0
        while True:
            i += 1
            part_str = u'part_%d' % i
            if part_str not in lab_dict:
                break
            part = lab_dict[part_str]
            num_str = part_str + u'_count'
            if num_str in lab_dict:
                part_num = int(lab_dict[num_str])
            else:
                part_num = 1
            total += part_num
        if total != num_parts:
            # TODO Fix num_parts, if present, else flag missing ingredient(s)
            pywikibot.output("Calculated %d parts. num_parts is %d" % (total, num_parts))

        # Check the Lab parameters against the Recipe parameters
        lab_keys = set(lab_dict.keys())
        lab_keys -= {u'in_list', u'num_parts'}
        recipe_keys = set(recipe_dict.keys())
        recipe_keys -= {u'description', u'image', u'atk', u'def', u'name'}
        for key in recipe_keys:
            if key in lab_keys:
                if recipe_dict[key] != lab_dict[key]:
                    # Fix up this page to match Tech Lab, because recipes are found there
                    text = re.sub(ur'(\|\W*%s\W*=\W*)%s' % (key, utils.escapeStr(lab_dict[key])),
                                  ur'\g<1>%s' % recipe_dict[key],
                                  text)
            else:
                # Insert the missing parameter
                pywikibot.output("Missing param - %s" % recipe_dict[key])
                # TODO this doesn't work for Lab Four of a Kind or Lab Full House
                text = text.replace(u'Lab', u'Lab\n|%s=%s' % (key, recipe_dict[key]), 1)

        # Check any Lab "from" parameters are correct
        for i in range(1,i):
            part_str = u'part_%d' % i
            from_str = part_str + u'_from'
            part = lab_dict[part_str]
            try:
                part_pg = pywikibot.Page(pywikibot.Site(), part)
            except pywikibot.NoPage:
                # No idea where it's from, so that's fine
                continue
            tmp = part_pg.templatesWithParams()
            templatesWithParams = [(t.title(withNamespace=False),p) for (t,p) in tmp]
            src_param = None
            for t,p in templatesWithParams:
                src_param = utils.paramFromParams(p, u'from')
            if not src_param:
                # Ingredient page doesn't say where to get it
                continue
            # Map it to a more suitable format
            src_param = self.one_line(src_param)
            try:
                src = lab_dict[from_str]
                # Compare with src_param
                if src != src_param:
                    pywikibot.output("Source mismatch for %s - this page says %s, item page says %s\n" % (part, src, src_param))
            except KeyError:
                # Add from parameter to this page
                new_param = u'|%s=%s' % (from_str, src_param)
                text = text.replace(ur'|%s' % part_str, u'%s\n|%s' % (new_param, part_str), 1)

        return text

    def one_line(self, src_list):
        """
        Converts a possibly mutli-line block of text listing sources for an item
        into a single line.
        """
        labre = re.compile(ur'{{Lab[^}]*}}', re.MULTILINE | re.DOTALL)
        text = src_list.replace(u'<br/>\n', u'')
        text = text.replace(ur'*', u'')
        # Convert any use of a Lab template to a link to the Tech Lab page
        text = labre.sub(u'made in [[Tech Lab]]', text)
        text = text.replace(u'\n', u', ')
        return text

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Find all the sub-categories of Needs Information
        cat = pywikibot.Category(pywikibot.Site(), u'Category:Needs Information')
        self.specificNeeds = set(c.title(withNamespace=False) for c in cat.subcategories(recurse=True))

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            xrToolkit = XrefToolkit(page.site, self.specificNeeds, debug = True)
            changedText = xrToolkit.change(page.get(), page)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing changedText with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(), changedText.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = pywikibot.input_choice(u'Do you want to accept these changes?',  [('Yes', 'Y'), ('No', 'n'), ('All', 'a')], 'N')
                    if choice == 'a':
                        self.acceptall = True
                if self.acceptall or choice == 'y':
                    page.put(changedText, summary)
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
        bot = XrefBot(preloadingGen)
        bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()

