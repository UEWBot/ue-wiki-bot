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
Script to fix up categories and cross-references between pages on UE Wiki.

Arguments:
&params;
"""

from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import operator
import six
from six.moves import range
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')
from itertools import chain

import pywikibot
from pywikibot import pagegenerators
import re
import difflib
import utils

# Stuff for the pywikibot help system
docuReplacements = {
    '&params;': pagegenerators.parameterHelp
}

# Summary message when using this module as a stand-alone script
summary = u'Robot: Fix cross-references and/or categories'

# Headers
# This doesn't match level 1 headers, but they're rare...
HEADER_RE = re.compile(ur'(={2,})\s*(?P<title>[^=]+)\s*\1')

# List items on gift page
GIFT_RE = re.compile(ur'<li value=(?P<level>.*)>\[\[(?P<item>.*)\]\]</li>')

# List items on faction page
FACTION_RE = re.compile(ur'\*\s*(?P<points>\S*)>\s*points - \[\[(?P<item>.*)\]\]')

# Any link
LINK_RE = re.compile(ur'\[\[\s*(?P<page>[^\|\]]*)\s*.*\]\]')

# String used for category REs
CATEGORY_RE_STR = ur'\[\[\s*Category:\s*%s\s*\]\]'
CATEGORY_RE = re.compile(ur'\[\[\s*Category:[^]]*\]\]')

# Regexes used for item powers
NO_STACK_RE = re.compile(ur'\[no \[\[stack\]\]\]')
NO_STACK_RE_2 = re.compile(ur'{{No Stack}}')
# Separators are with, for, and to
SEP_RE = re.compile(ur' with | for | to ')
# Some follow completely different patterns
# Note that here we deliberately avoid matching the powers of the four Medallions
ALL_RE = re.compile(ur'[Aa]ll (.*) (count as \d.*)')
WHEN_RE = re.compile(ur'(.*) when (.*)')

# Cache to speed up _fix_lieutenant()
cat_refs_map = utils.CategoryRefs()

# Cache to speed up finding recipes
recipe_cache = utils.RecipeCache()

# Image cache
image_map = utils.ImageMap()

# Parsed Achievements page
ach = utils.Achievements()

def drop_params_match(param1, param2):
    """
    Compare two drop parameters.

    param1, param2 -- parameters to compare.

    Ignores case of first character, matches spaces with underscores,
    and reports a match if one is a link and the other isn't.

    Return True if they match, False otherwise.
    """
    # Direct match first
    if param1 == param2:
        return True
    if not param1:
        return False
    if not param2:
        return False
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

def time_params_match(param1, param2):
    """
    Compare two time parameters.

    param1, param2 -- parameters to compare.

    Matches "days" with "d" and "hours" with hrs".

    Return True if they match, False otherwise.
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

def missing_params(all_params, mandatory_list):
    """
    Return a set of all missing mandatory parameter names.

    all_params -- list of template parameters.
    mandatory_list -- list of mandatory template parameter names.

    Return a set of parameter names.
    """
    ret = set(mandatory_list)
    param_dict = utils.params_to_dict(all_params)
    for k in param_dict.keys():
        ret.discard(k)
    return ret

def one_cap(string):
    """
    Return string with the first letter capitalised and the rest left alone.
    """
    return string[0].upper() + string[1:]

def achievement_text(ach_list):
    """
    Return the list of achievements in text form.

    ach_list -- list of 2-tuple (description, section) achievements

    Return a string suitable for inclusion in an item page.
    """
    # We assume that the achievements are all in the same section
    sect = ach_list[0][1]
    if len(ach_list) == 1:
        retval = u'There is an [[Achievements#%s|Achievement]] for ' % sect
    else:
        retval = u'There are [[Achievements#%s|Achievements]] for ' % sect
    retval += ', '.join([a[0] for a in ach_list])
    if retval[-1] != u'.':
        retval += u'.'
    # fix capitalisation and tense
    retval = retval.replace(u'Own', u'owning')
    retval = retval.replace(u'Craft', u'crafting')
    return retval

class XrefToolkit:

    """Ugly catch-all class with tools to manipulate wiki pages."""

    def __init__(self, specific_needs, debug = False):
        """
        Instantiate the class.

        specific_needs -- list of sub-categories of Needs Information.
        debug -- boolean indicating whether to provide debug info.
        """
        self.specific_needs = specific_needs
        self.debug = debug

    def change(self, text, page):
        """
        Return a cleaned-up version of the page's text.

        text -- text of the page.
        page -- Page object.

        Return update text.
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
        text = self._fix_page(titleWithoutNamespace,
                              text,
                              categories,
                              templatesWithParams,
                              refs)
        #pywikibot.output("******\nOld text:\n%s" % oldText)
        #pywikibot.output("******\nIn text:\n%s" % text)
        # Just comparing oldText with text wasn't sufficient
        changes = False
        for diffline in difflib.ndiff(oldText.splitlines(), text.splitlines()):
            if not diffline.startswith(u'  '):
                changes = True
                break
        if changes:
            print()
            pywikibot.output(text)
        if self.debug:
            print()
            pywikibot.showDiff(oldText, text)
        return text

    def _fix_page(self,
                  titleWithoutNamespace,
                  text,
                  categories,
                  templatesWithParams,
                  refs):
        """
        Modify text to fix any inconsistencies in the page.

        titleWithoutNamespace -- page title, without namespace.
        text -- current page text.
        categories -- a list of category Pages the page is current in.
        templatesWithParams -- list of templates used and corresponding parameters.
        refs -- list of pages that link to the page.

        Return updated text.
        """
        # Note that these are effectively independent. Although the text gets changed,
        # the categories, templates, and parameters are not re-generated after each call
        text = self._fix_boss(titleWithoutNamespace,
                              text,
                              categories,
                              templatesWithParams)
        text = self._fix_item(titleWithoutNamespace,
                              text,
                              categories,
                              templatesWithParams,
                              refs)
        text = self._fix_insignia(titleWithoutNamespace,
                                  text,
                                  templatesWithParams,
                                  refs)
        text = self._fix_lieutenant(titleWithoutNamespace,
                                    text,
                                    templatesWithParams,
                                    refs)
        text = self._fix_skin(titleWithoutNamespace,
                              text,
                              templatesWithParams,
                              refs)
        text = self._fix_property(titleWithoutNamespace,
                                  text,
                                  templatesWithParams)
        text = self._fix_execution_method(text, templatesWithParams)
        text = self._fix_class(text, templatesWithParams)
        text = self._fix_tech_lab(titleWithoutNamespace,
                                  text,
                                  templatesWithParams)
        text = self._fix_area(titleWithoutNamespace,
                              text,
                              categories,
                              templatesWithParams)
        text = self._fix_crate(text, categories, templatesWithParams)
        return text

    # Now a load of utility methods
    # First ones that are used by multiple types of pages

    def _prepend_NOWYSIWYG_if_needed(self, text):
        """
        Return text with __NOWYSISYG__ at the start.

        text -- current page text.

        Return text, amended if necessary.
        """
        keyword = u'__NOWYSIWYG__'
        if keyword in text:
            return text
        return keyword + u'\n' + text

    def _remove_implicit_categories(self, text, template=None):
        """
        Return text with any implicit categories removed.

        text -- current page text.
        template -- name of template to remove categories for.
                    If no template is provided, remove categories added
                    by any template.

        "Implicit categories" are those that are automatically added to
        a page by a template.

        Return text, amended if necessary.
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
                               u'The Mafia Lieutenants',
                               u'Skins',
                               u'Insignias']

        if template != None:
            pywikibot.output("Unsupported template %s" % template)

        for cat in implicit_categories:
            text = self._remove_category(text, cat)

        return text

    def _append_category(self, text, category):
        """
        Return text with the appropriate category string appended.

        text -- current page text.
        category -- the name of the category itself.

        Return the new page text.
        """
        str = u'\n[[Category:%s]]' % category
        if str in text:
            # Don't add it if it's already there
            return text
        return text + str

    def _remove_category(self, text, category):
        """
        Return the text with the appropriate category removed.

        text -- current page text.
        category -- the name of the category itself.

        Return the new page text.
        """
        Rcat = re.compile(CATEGORY_RE_STR % category)
        # Remove the category
        return Rcat.sub('', text)

    def _fix_needs_cats(self, text, missed_params, param_cat_map):
        """
        Return the text with need categories added or removed as appropriate.

        text -- current page text.
        missed_params -- a set of parameters that are missing from the page.
        param_cat_map -- a dict, indexed by parameter, of Needs categories.

        Return the new page text.
        """
        cats_needed = set()
        for (p,c) in param_cat_map.items():
            if p in missed_params:
                cats_needed.add(c)
        for c in cats_needed:
            text = self._append_category(text, c)
        for c in set(param_cat_map.values()):
            if c not in cats_needed:
                # Only remove specific needs categories, not more general ones
                if c in self.specific_needs:
                    text = self._remove_category(text, c)
        return text

    def _fix_needs_categories(self, text, params, param_cat_map):
        """
        Return the text with need categories added or removed as appropriate.

        text -- current page text.
        params -- list of template parameters.
        param_cat_map is a dict, indexed by parameter, of Needs categories.

        Return the new page text.
        """
        missed_params = missing_params(params, list(param_cat_map.keys()))
        return self._fix_needs_cats(text,
                                    missed_params,
                                    param_cat_map)

    def _find_section(self, text, title):
        """
        Find a specific section in a page's text.

        text -- Current page text.
        title -- name of the section to look for.

        Return a 2-tuple containing the start and end indices.

        End point is a header at the same level, a template, or category.
        """
        # TODO Merge into utils.find_specific_section()
        headers = []
        iterator = HEADER_RE.finditer(text)
        for m in iterator:
            hdr_lvl = len(m.group(1))
            headers.append({'level':hdr_lvl,
                            'title':m.group(u'title').strip(),
                            'from':m.start(),
                            'to':m.end()})

        start = -1
        end = -1
        level = -1
        for hdr in headers:
            if (level == -1) or (hdr['level'] == level):
                if start == -1:
                    if hdr['title'] == title:
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
            m = CATEGORY_RE.search(text[start:end])
            if m:
                end = start + m.start() - 1
        return (start, end)

    def _cat_in_categories(self, category, categories):
        """
        Return whether the specified category is in the list of categories.

        category -- a unicode string.
        categories -- a list of category Pages.

        Return True or False.
        """
        # Is it in the specified category ?
        for this_category in categories:
            if re.search(CATEGORY_RE_STR % category,
                         this_category.title(asLink=True)):
                return True
        return False

    def _one_line(self, src_list):
        """
        Convert a possibly multi-line block of text into a single line.

        src_list -- text string to convert.
        """
        labre = re.compile(ur'{{Lab[^}]*}}', re.MULTILINE | re.DOTALL)
        text = src_list.replace(u'<br/>\n', u'')
        text = text.replace(u'<br />\n', u'')
        text = text.replace(ur'*', u'')
        # Convert any use of a Lab template to a link to the Tech Lab page
        text = labre.sub(u'made in [[Tech Lab]]', text)
        text = text.replace(u'\n', u', ')
        return text

    # The next few are each specific to one type of page

    def _fix_tech_lab(self, name, text, templatesWithParams):
        """
        Fix the Tech Lab and Tech Lab - Historic pages.

        name -- page title.
        text -- current text of the page.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        Ensure that __NOWYSIWYG__ is present.
        Check for mandatory template parameters or corresponding Needs category.
        """
        if u'Tech Lab' not in name:
            return text

        # Is this a historic recipe ?
        is_old = (u'Historic' in name)

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check each recipe
        recipe_param_map = {u'name': u'Needs Information', #u'Needs Item Name',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'atk': u'Needs Stats',
                            u'def': u'Needs Stats',
                            u'time': u'Needs Build Time',
                            u'part_1': u'Needs Information'} #u'Needs Ingredient'}
        old_recipe_map = {u'available' : u'Needs Information'}
        missed_params = set()
        for template, params in templatesWithParams:
            if u'Recipe' not in template:
                continue
            missed_params |= missing_params(params, list(recipe_param_map.keys()))
            # Find this item on the page
            param_dict = utils.params_to_dict(params)
            name = param_dict[u'name']
            # This can take a while, so reassure the user
            pywikibot.output("Checking %s" % name)
            recipe_start = text.find(name)
            if is_old:
                missed_params |= missing_params(params, list(old_recipe_map.keys()))
            # TODO Cross-reference against item page
            # Check images for ingredients
            n = 0
            while True:
                n += 1
                part_str = u'part_%s' % n
                try:
                    part = param_dict[part_str]
                except KeyError:
                    # Ran out of parts
                    break
                part_img_str = part_str + u'_img'
                part_img = param_dict[part_img_str]
                image = image_map.image_for(part)
                if image is not None:
                    if part_img is None:
                        # Insert an appropriate part_img parameter
                        new_part = re.sub(ur'(\|\W*%s\W*=\W*%s)' % (part_str,
                                                                    utils.escape_str(part)),
                                          ur'\1\n|%s=%s' % (part_img_str,
                                                            image),
                                          text[recipe_start:],
                                          1)
                        text = text[:recipe_start] + new_part
                    elif image != part_img:
                        # TODO Replace the image with the one from the ingredient page
                        pywikibot.output("Image mismatch. %s has %s, %s has %s" % (name, part_img, part, image))
        pywikibot.output("Set of missing recipe parameters is %s" % missed_params)
        # Ensure the Needs categories are correct
        text = self._fix_needs_cats(text,
                                    missed_params,
                                    recipe_param_map)

        return text

    def _fix_class(self, text, templatesWithParams):
        """
        Fix a class page.

        text -- current text of the page.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        If the page uses the template 'Class':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check for mandatory template parameters or corresponding Needs category.
        Check for increasing skill levels.
        """
        # Does the page use the Class template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Class':
                the_template = template
                the_params = params

        # Drop out early if not a class page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check mandatory parameters of the Class template
        class_param_map = {u'description': u'Needs Description',
                           u'image': u'Needs Improvement', #u'Needs Image',
                           u'weapons': u'Needs Information', #u'Needs Weapons',
                           u'help_text': u'Needs Information'} #u'Needs Help Text'}
        initial_param_map = {u'strength': u'Needs Information', #u'Needs Strength',
                             u'short_description': u'Needs Information', #u'Needs Short Description',
                             u'special_atk_name': u'Needs Information', #u'Needs Special Attack Name',
                             u'special_atk_effect': u'Needs Information'} #u'Needs Special Attack Effect',

        # More parameters are mandatory for classes that are always available
        if utils.param_from_params(the_params, u'unlock_class') is None:
            class_param_map.update(initial_param_map)

        text = self._fix_needs_categories(text,
                                          the_params,
                                          class_param_map)

        skill_param_map = {u'level': u'Needs Information', #u'Needs Skill Level',
                           u'effect': u'Needs Information', #u'Needs Skill Effect',
                           u'cost': u'Needs Information', #u'Needs Skill Cost',
                           u'unlock': u'Needs Information', #u'Needs Skill Unlock',
                           u'time': u'Needs Information'} #u'Needs Skill Time'}
        # Check each use of the Skill template
        missed_params = set()
        old_level = u'0'
        old_start = 0
        for template,params in templatesWithParams:
            if template == u'Skill':
                param_dict = utils.params_to_dict(params)
                # Check for the same level as the previous level of the same skill
                try:
                    effect = param_dict[u'effect']
                    start = text.find(effect)
                    # Is there a section header between the last skill and this one ?
                    if u'===' in text[old_start:start]:
                        old_level = u'0'
                    level = param_dict[u'level']
                    if (level == old_level):
                        pywikibot.output("copy-paste error for skill level %s (%s) ?" % (level, params))
                    elif (int(level) != int(old_level)+1):
                        pywikibot.output("missing skill level %d (%s) ?" % (int(old_level)+1, params))
                    old_level = level
                    old_start = start
                except KeyError:
                    pass
                missed_params |= missing_params(params, list(skill_param_map.keys()))
        # Ensure the Needs categories are correct
        text = self._fix_needs_cats(text,
                                    missed_params,
                                    skill_param_map)

        return text

    def _fix_execution_method(self, text, templatesWithParams):
        """
        Fix an execution method page.

        text -- current text of the page.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        If the page uses the template 'Execution Method':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check for mandatory template parameters or corresponding Needs category.
        """
        # Does the page use the execution method template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Execution Method':
                the_template = template
                the_params = params

        # Drop out early if not an execution method page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check mandatory parameters
        method_param_map = {u'cost': u'Needs Stamina Cost',
                            u'success': u'Needs Initial Success',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'chance': u'Needs Information', #u'Needs Bonus Chance',
                            u'bonus': u'Needs Information', #u'Needs Bonus',
                            u'need': u'Needs Information'} #u'Needs Prerequisite'}

        text = self._fix_needs_categories(text,
                                          the_params,
                                          method_param_map)

        return text

    def _fix_insignia(self, name, text, templatesWithParams, refs):
        """
        Fix an Insignia page.

        name -- name of the Insignia (page title).
        text -- current page text.
        templatesWithParams -- list of templates used and corresponding parameters.
        refs -- list of pages that link to the page.

        Return updated text.

        If the page uses the template 'Insignia':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check that the item is listed everywhere it says it can be obtained.
        """
        # Does the page use the Class template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Insignia':
                the_template = template
                the_params = params

        # Drop out early if not an insignia page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # Check for explicit categories that should be implicit
        text = self._remove_implicit_categories(text)

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # If the item comes from somewhere special, do cross-ref check
        from_param = utils.param_from_params(the_params, u'from')
        text = self._fix_drop(name, text, from_param, refs)

        return text

    # The next few methods are only used on Area pages

    def _lt_rarity(self, name):
        """Return the rarity of the specified Lt."""
        page = pywikibot.Page(pywikibot.Site(), name)
        for template,params in page.templatesWithParams():
            title = template.title(withNamespace=False)
            if title.startswith(u'Lieutenant '):
                return title.split()[1]

    def _fix_crate(self, text, categories, templatesWithParams):
        """
        Fix a Crate page.

        text - current text of the page.
        categories -- list of categories the page belongs to.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        Ensure that __NOWYSIWYG__ is present.
        Check that the correct image is supplied for each reward.
        """
        # Drop out if it isn't a Crate page
        if not self._cat_in_categories(u'Crates', categories):
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # First figure out what sections we have
        sections = []
        rarities = utils.rarities_in_order()
        for m in HEADER_RE.finditer(text):
            for r in rarities:
                if r in m.group(u'title'):
                    sections.append((r, m.start(), [], m.end()))

        # Check each template
        for template, params in templatesWithParams:
            if template == u'Crate Reward':
                param_dict = utils.params_to_dict(params)
                name = param_dict[u'name']
                image = image_map.image_for(name)
                if not drop_params_match(param_dict[u'image'], image):
                    # We'll fix the image when we re-generate the text for the page
                    if image:
                        print("Wrong image for %s - %s rather than %s.\n" % (name, param_dict[u'image'], image))
                    else:
                        # TODO If we don't know the right image, let's trust the one that's currently there
                        pass
                # Which section is this one in ?
                start = text.index(name)
                for s in sections:
                    if start > s[1]:
                        rarity = s[0]
                for s in sections:
                    if rarity == s[0]:
                        # Add the Lt to the list for that section
                        s[2].append(name)
                # Check that the rarity is correct
                r = image_map.rarity_for(name)
                if r != rarity:
                    # TODO Make allowance for the expected special cases here
                    # For those cases, we want to append some additional text
                    if r:
                        print("Wrong rarity for %s - %s rather than %s." % (name, rarity, r))

        # Re-create the expected layout of the page.
        # We should have a section for each rarity,
        # with 2 Lts per row within each section
        # First the general description of the crate
        new_text = text[0:sections[0][1]]
        for s in sections:
            # Section header
            new_text += text[s[1]:s[3]]
            new_text += u'\n'
            # Table start
            new_text += u'{|\n'
            i = 0
            lts = s[2]
            while i < len(lts):
                # 2 Lts per row
                name = lts[i]
                # TODO it's annoying when this causes changes due to the case of the first letter or underscores versus spaces
                image = image_map.image_for(name)
                new_text += u'{{Crate Reward|name=%s|image=%s}}\n' % (name, image)
                i += 1
                if i < len(lts):
                    name = lts[i]
                    image = image_map.image_for(name)
                    new_text += u'{{Crate Reward|name=%s|image=%s}}\n' % (name, image)
                    i += 1
                    if i < len(lts):
                        new_text += u'|-\n'
            # Table end
            new_text += u'|}\n'
        new_text += u'\n[[Category:Crates]]'
        text = new_text

        return text

    def _fix_area(self, name, text, categories, templatesWithParams):
        """
        Fix an Area page.

        name -- page title.
        text -- current text of the page.
        categories -- list of categories the page belongs to.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        Ensure that __NOWYSIWYG__ is present.
        Check for mandatory template parameters or corresponding Needs category.
        """
        # Drop out if it isn't an area page
        if not self._cat_in_categories(u'Areas', categories):
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

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
        missed_params = set()
        for template, params in templatesWithParams:
            if template == u'Job':
                mp = missing_params(params,
                                    list(common_param_map.keys()) +
                                        list(job_param_map.keys()))
                # xp_min and xp_max will do instead of xp
                if u'xp' in mp:
                    mp.remove(u'xp')
                    mp |= missing_params(params, list(xp_pair_param_map.keys()))
                param_dict = utils.params_to_dict(params)
                # Check gear
                got_gear = False
                for i in range(4,0,-1):
                    root = u'gear_%d' % i
                    img_param = root + u'_img'
                    if root in mp:
                        # Shouldn't have higher number without lower
                        if not got_gear:
                            mp.remove(root)
                            mp.discard(img_param)
                    else:
                        got_gear = True
                    # If we have this gear param, check the corresponding image
                    if root in param_dict:
                        image = image_map.image_for(param_dict[root])
                        try:
                            img = param_dict[img_param]
                            if not drop_params_match(img, image):
                                # TODO Fix the image
                                print("Wrong image for %s - %s rather than %s.\n" % (param_dict[root], img, image));
                        except KeyError:
                            # TODO Add the image
                            print("Missing %s=%s" % (img_param, image))
                missed_params |= mp
            elif template == u'Challenge Job':
                mp = missing_params(params,
                                    list(common_param_map.keys()) +
                                        list(xp_pair_param_map.keys()) +
                                        list(challenge_param_map.keys()))
                # Look up any missing Lt rarities
                for i in range(1,5):
                    root = u'lt_%d' % i
                    rare_param = root + u'_rarity'
                    if root not in mp and rare_param in mp:
                        rarity = self._lt_rarity(utils.param_from_params(params,
                                                                         root))
                        text = self._add_param(text,
                                               params,
                                               rare_param + u'=%s' % rarity)
                        mp.discard(rare_param)
                missed_params |= mp
        # Ensure the Needs categories are correct
        text = self._fix_needs_cats(text,
                                    missed_params,
                                    dict(list(common_param_map.items()) +
                                             list(job_param_map.items()) +
                                             list(challenge_param_map.items())))

        return text

    # The next few methods are only used on Boss pages

    def _check_item_params(self, text, source, drop_params):
        """
        Return text with corrected parameters for the drop.

        text -- Current page text.
        source -- the title of the page listing the drop.
        drop_params -- a dictionary of the Drop template's parameters.

        Return modified text with missing parameters added.

        Print a warning if source is not listed as a source for this drop.
        """
        paramless_items = [u'Steel Beam',
                           u'Concrete Block',
                           u'Bronze Shadow Token',
                           u'Silver Shadow Token',
                           u'Laundered Donation Money (I)',
                           u'Laundered Donation Money (II)',
                           u'Laundered Donation Money (III)']
        templates_to_ignore = [u'Job Link',
                               u'For',
                               u'Sic',
                               u'No Stack',
                               u'Legendary',
                               u'Epic',
                               u'Rare',
                               u'Uncommon',
                               u'Common',
                               u'Lab',
                               u'Lab Four Of A Kind',
                               u'Lab Full House']
        try:
            item_name = drop_params[u'name']
        except KeyError:
            return text
        item = pywikibot.Page(pywikibot.Site(), item_name)
        templatesWithParams = item.templatesWithParams()
        for (temp, params) in templatesWithParams:
            template = temp.title(withNamespace=False)
            #pywikibot.output("Template %s" % template)
            # TODO Clean this code up
            if (u'Item' in template) or (template == u'Ingredient') or (template == u'Insignia'):
                item_params = utils.params_to_dict(params)
                if template == u'Ingredient':
                    item_params[u'type'] = u'Ingredients'
                elif template == u'Insignia':
                    item_params[u'type'] = u'Insignias'
                key = u'for'
                try:
                    # Should be a single line in the drop template
                    item_params[key] = self._one_line(item_params[key])
                except KeyError:
                    pass
                # Check the drop parameters we do have
                for key in drop_params.keys():
                    if (key == u'name'):
                        continue
                    elif (key == u'creator'):
                        continue
                    elif key in item_params and not drop_params_match(drop_params[key],
                                                                      item_params[key]):
                        # TODO Should be able to fix some of them at least...
                        pywikibot.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, item_name, item_params[key], drop_params[key]))
                # Then check for any that may be missing
                for key in [u'name', u'image', u'atk', u'def', u'type']:
                    if key not in drop_params and key in item_params:
                        if (key == u'type') and (u'for' in drop_params):
                            # We want either for or type for Ingredients
                            continue
                        text = text.replace(ur'name=%s' % item_name,
                                            u'name=%s|%s=%s' % (item_name,
                                                                key,
                                                                item_params[key]))
                key = u'for'
                if key not in drop_params and key in item_params:
                    # "for" parameter only needed where the item is a Tech Lab ingredient
                    # TODO There should be a better way to do this...
                    if item_name not in paramless_items and not self._cat_in_categories(u'Recombinators', item.categories()):
                        # TODO Need to also remove type=Ingredients
                        text = re.sub(ur'name\s*=\s*%s\s*\|' % item_name,
                                      u'name=%s|%s=%s|' % (item_name,
                                                           key,
                                                           item_params[key]),
                                      text)
                if source not in item_params['from']:
                    pywikibot.output("Boss claims to drop %s, but is not listed on that page" % item_name)
            elif u'Lieutenant' in template:
                item_params = utils.params_to_dict(params)
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
                    if not drop_params_match(dp, ip):
                        pywikibot.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, item_name, dp, ip))
                if source not in item_params['from']:
                    pywikibot.output("Boss claims to drop %s, but is not listed on that page" % item_name)
            elif template not in templates_to_ignore:
                # Report unexpected templates we don't know how to handle
                pywikibot.output("Ignoring template %s" % template)
        return text

    def _fix_boss(self, name, text, categories, templatesWithParams):
        """
        Fix a Boss page.

        name -- page title.
        text -- current text of the page.
        categories -- list of categories the page belongs to.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        If the page is in any of the five boss categories:
        Ensure that __NOWYSIWYG__ is present.
        Check that the page is in exactly one of the five boss categories.
        Check each drop's image, type, attack, and defence.
        Check that the categories Needs Completion Dialogue, Needs Rewards,
        Needs Stages, and Needs Time Limit are used correctly.
        """
        boss_categories = [u'Job Bosses',
                           u'Tech Lab Bosses',
                           u'Legend Bosses',
                           u'Event Bosses',
                           u'Retired Bosses',
                           u'Bosses'] # War Hounds is here for now...
        # Check core category
        the_cats = []
        for cat in boss_categories:
            if self._cat_in_categories(cat, categories):
                the_cats.append(cat)

        # Drop out early if not a boss page
        # TODO Is there a better test ?
        if not the_cats:
            return text
        elif len(the_cats) > 1:
            pywikibot.output("Boss should be in just one of the %s categories"
                             % ', '.join(the_cats))

        # __NOWYSISYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check each drop
        for (template, params) in templatesWithParams:
            if template == u'Drop':
                print("*** %s still uses 'Drop' template rather than 'BossDrop'" % name)
                drop_params = utils.params_to_dict(params)
                text = self._check_item_params(text, name, drop_params)
            elif template == u'BossDrop':
                drop_params = utils.params_to_dict(params)
                text = self._check_item_params(text, name, drop_params)

        # Event Bosses are structured very differently
        if u'Event Bosses' in the_cats:
            # Should also be in the 'Events' category
            cat = u'Events'
            text = self._append_category(text, cat)
            # Don't check other 'Needs' categories
            return text

        # Check Needs categories
        cat = u'Needs Completion Dialogue'
        if u'Job Bosses' in the_cats:
            # Not all bosses in this category have a completion dialogue
            pass
            #text = self._check_needs_section(text,
            #                                 categories,
            #                                 u'Completion Dialogue',
            #                                 cat)
        else:
            #Non-Job bosses should never be in this category
            text = self._remove_category(text, cat)

        # We should find a section called Rewards that links to the Boss Drops page
        sect = u'Rewards'
        sect_str = u'[[Boss Drops|Rewards]]'
        cat = u'Needs Rewards'
        (start, end) = self._find_section(text, sect_str)
        # If we don't find one, maybe there's just a 'Rewards' section...
        if (start == -1):
            (start, end) = self._find_section(text, sect)
            # Replace the header
            text = re.sub(ur'=\s*%s\s*=' % sect, u'=%s=' % sect_str, text)

        text = self._check_needs_section(text,
                                         categories,
                                         sect,
                                         cat,
                                         sect_str)

        text = self._check_needs_section(text,
                                         categories,
                                         u'Stages',
                                         u'Needs Stages')

        # Check the new boss-related templates
        for (template, params) in templatesWithParams:
            if template == u'BossInfo':
                # high_aggro? is a simple True/False
                text = self._fix_needs_categories(text,
                                                  params,
                                                  {u'participants':              u'Needs Participant Limit',
                                                   u'fight_time':                u'Needs Fight Time',
                                                   u'collect_time':              u'Needs Collect Time',
                                                   u'recommended_class':         u'Needs Recommended Class',
                                                   u'minimum_collect_threshold': u'Needs Min Collect Threshold',
                                                   u'total_health':              u'Needs Total Health',
                                                   u'max_empire_points':         u'Needs Max Empire Points',
                                                  })
            elif template == u'BossSpeedkill':
                text = self._fix_needs_categories(text,
                                                  params,
                                                  {u'1 Star:':  u'Needs Speed Kill Time',
                                                   u'2 Stars:': u'Needs Speed Kill Time',
                                                   u'3 Stars:': u'Needs Speed Kill Time',
                                                  })
            elif template == u'BossStage':
                text = self._fix_needs_categories(text,
                                                  params,
                                                  {u'Name_01':  u'Needs Stages',
                                                   u'Class_01': u'Needs Information',
                                                   u'Minion_01_HP': u'Needs Information',
                                                  })
            elif template == u'BossEpicThresholds':
                text = self._fix_needs_categories(text,
                                                  params,
                                                  {u'1 Epic:':  u'Needs Epic Threshold',
                                                   u'2 Epics:': u'Needs Epic Threshold',
                                                   u'3 Epics:': u'Needs Epic Threshold',
                                                  })

        text = self._check_needs_section(text,
                                         categories,
                                         u'Basic Information',
                                         u'Needs Time Limit')

        return text

    def _check_needs_section(self,
                             text,
                             categories,
                             sect,
                             cat,
                             sect_str=None):
        """
        Return text with specified category added or removed if appropriate.

        text -- current page text.
        categories -- list of categories the page belongs to.
        sect -- name of the section to check for.
        cat -- category that needs to be present if the section isn't,
               and vice-versa.
        sec_str -- optional section string to check for. Otherwise
                   look for sect.

        Return updated text.

        Check whether the specified section is present in the page.
        If it is, check that the specified category is not in categories.
        If it isn't, check that the specified category is in categories
        and appends it to the page text if needed.
        """
        if not sect_str:
            sect_str = sect
        (start, end) = self._find_section(text, sect_str)
        length = len(text[start:end])
        if self._cat_in_categories(cat, categories):
            if (start != -1) and (length > 0):
                # Section is present
                # TODO Check for actual content
                pywikibot.output("Non-empty %s section found despite %s category" % (sect, cat))
        elif start == -1:
            # Section not present
            text = self._append_category(text, cat)
        return text

    # The next few methods are only used on Property pages

    def _fix_safe_house(self, text):
        """
        Fix Safe House or The Cayman Islands page.

        text -- current text of the page.

        Return updated text.

        Check that the page includes appropriate information (like Upgrade properties).
        Check that the cost table matches the template for upgrade properties.
        """
        # TODO implement this function
        return text

    def _fix_fortress(self, text):
        """
        Fix the Fortress page.

        text -- current text of the page.

        Return updated text.

        Check that the page includes appropriate information (like Upgrade properties).
        Check that the cost table matches the template for upgrade properties.
        """
        # TODO implement the rest of this function
        # First, retrieve the expected cost ratios from the template
        Rrow = re.compile(ur'\|\s*(?P<level>\d+).*cost}}}\*(?P<ratio>[\d.]+)')
        table_page = pywikibot.Page(pywikibot.Site(),
                                    u'Template:Property Cost Table')
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
        for level,cost in six.iteritems(costs):
            expected_cost = base_cost * ratios[level]
            if cost != expected_cost:
                pywikibot.output("Level %d cost of %d != expected %d" % (level,
                                                                         cost,
                                                                         expected_cost))
        return text

    def _fix_property(self, name, text, templatesWithParams):
        """
        Fix a property page.

        name -- page title.
        text -- current text of the page.
        templatesWithParams -- list of 2-tuples containing template Page
                               and list of parameters.

        Return updated text.

        If the page uses either of the templates 'Income Property'
        or 'Upgrade Property':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check for mandatory template parameters or corresponding Needs category.
        """
        # Does the page use a property template ?
        the_params = None
        for template,params in templatesWithParams:
            if template in [u'Income Property',
                            u'Upgrade Property']:
                the_template = template
                the_params = params

        # Fortress, Safe House and The Cayman Islands are special
        if name == u'Safe House':
            return self._fix_safe_house(text)
        elif name == u'Fortress':
            return self._fix_fortress(text)
        elif name == u'The Cayman Islands':
            # Very similar to Safe House
            return self._fix_safe_house(text)

        # Drop out early if not a property page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check mandatory parameters
        prop_param_map = {u'description': u'Needs Description',
                          u'cost': u'Needs Initial Cost',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
        if the_template == u'Upgrade Property':
            prop_param_map[u'power'] = u'Needs Power'
        else:
            prop_param_map[u'income'] = u'Needs Income'

        # Build time is required for non-FP properties only
        param_dict = utils.params_to_dict(the_params)
        if u'fp_prop' in param_dict:
            if u'time' in param_dict:
                pywikibot.output("FP property has build time!")
        else:
            prop_param_map[u'time'] = u'Needs Build Time'

        text = self._fix_needs_categories(text,
                                          the_params,
                                          prop_param_map)

        return text

    # The next few methods are only used on Lieutenant pages

    def _lt_was_event_reward(self, lt_name, event_name):
        """
        Check whether a Lieutenant was a reward in the specified event.

        lt_name -- title of the Lt page
        event_name -- Title of the event page

        Return True or False
        """
        page = pywikibot.Page(pywikibot.Site(), event_name)
        # Lt rewards in events always specify how many of the Lt you get
        if re.search(ur'\d\s*x?\s*\[\[\s*%s' % lt_name, page.get()):
            return True
        return False

    def _fix_lt_sources(self, name, text, the_params, refs):
        """
        Fix the list of sources on a Lieutenant page.

        name -- page title.
        text -- current text of the page.
        the_params -- list of parameters to the lieutenant template.
        refs -- list of pages that link to the page to be fixed.

        Return the modified text parameter.
        """
        fromParam = utils.param_from_params(the_params, u'from')
        # Check where the Lt can be obtained from
        # TODO Ones that can be bought are listed on [[Category:Lieutenants]]
        sources = []
        for r in refs:
            if self._cat_in_categories(u'Crates', r.categories()):
                sources.append(u'[[%s]]' % r.title())
                # Ensure that it's in Crate Lieutenants
                c = u'Crate Lieutenants'
                text = self._append_category(text, c)
            elif self._cat_in_categories(u'Giveaways', r.categories()):
                sources.append(u'[[%s]]' % r.title())
                # Ensure that it's in Event Lieutenants
                c = u'Event Lieutenants'
                text = self._append_category(text, c)
            elif self._cat_in_categories(u'Events', r.categories()):
                # ensure that the Lt was a reward rather than an opponent
                if self._lt_was_event_reward(name, r.title()):
                    sources.append(u'[[%s]]' % r.title())
                    # Ensure that it's in Event Lieutenants
                    c = u'Event Lieutenants'
                    text = self._append_category(text, c)
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if template == u'Challenge Job':
                    area = r.title()
                    job = utils.param_from_params(params, u'name')
                    for p in params:
                        if p.startswith(u'lt_') and name in p:
                            sources.append(u'{{Job Link|district=%s|job=%s}}' % (area,
                                                                                 job))
                elif template == u'FP Item Row':
                    if name == utils.param_from_params(params, u'lieutenant'):
                        sources.append(u'[[Black Market]]')
                        c = u'Favor Point Lieutenants'
                        # Ensure that it's in Favor Point Lieutenants
                        text = self._append_category(text, c)
        for s in sources:
            # TODO This block doesn't work properly if the are multiple missing sources
            if not fromParam:
                text = text.replace(u'|', u'|from=%s\n|' % s, 1)
            elif s not in fromParam:
                pywikibot.output("***Need to add %s" % s)
                # First convert a single item to a list
                if not u'\n' in fromParam:
                    text = text.replace(fromParam, u'<br/>\n*' + fromParam)
                text = text.replace(fromParam, fromParam + u'\n*%s' % s)
        # TODO Also check for wrongly-listed sources

        return text

    def _items_in_refs(self, refs):
        """
        Return a dict with an entry for each item page in refs.

        refs -- list of pages that link to the page to be fixed.

        Key is the item name. Value is a 2-tuple containing power
        and image
        """
        refItems = {}
        for r in refs:
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if u'Item' in template and not template == u'FP Item Row':
                    param_dict = utils.params_to_dict(params)
                    try:
                        powerParam = param_dict[u'power']
                        imageParam = param_dict[u'image']
                    except KeyError:
                        # If it doesn't have a power, we're not interested
                        # If it is just missing an image, let's report that to the user
                        if u'power' in param_dict:
                            print('Missing image in %s' % r.title())
                        continue
                    else:
                        refItems[r.title()] = (powerParam,
                                               imageParam)
        return refItems

    def _affects_lt(self, lt, rarity, faction, beneficiary):
        """
        Return whether an item benefits the specified Lt.

        lt -- name of the lieutenant of interest.
        rarity -- rarity of the Lt of interest.
        faction -- faction of the Lt of interest.
        beneficiary -- text specifying who the item helps.

        Return True if the specified Lt matches the criteria in beneficiary.
        """
        # Some items don't directly benefit any LT
        if not beneficiary:
            return False

        # If the word "per" appears, we need to look deeper
        if u' per ' in beneficiary:
           # The actual beneficary is the part before the "per"
           beneficiary = beneficiary.split(u' per ')[0]

        # All the "X Lts count as Y" items don't appear on any Lt page
        if u' count as ' in beneficiary:
            return False

        # If the LT's name appears, that's an easy one
        if lt in beneficiary:
            return True

        parseRe = re.compile(ur'\[\[\s*:(Category:[^]\|]*)(|[^]]*)\]\]')

        # What categories of Lt does the item help ?
        cats = parseRe.findall(beneficiary)

        if not cats:
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

    def _split_power(self, power):
        """
        Split the text of a power into its components parts.

        power -- item power string.

        Return a 4-tuple containing:
            effect of the item (str)
            beneficiaries (str)
            multiplier (str or None)
            stack (True/False)
        """
        # Does the power stack ?
        stack = (NO_STACK_RE.search(power) is None)
        # Remove any "no stack" string
        power = NO_STACK_RE.sub('', power)
        if stack:
            stack = (NO_STACK_RE_2.search(power) is None)
            # Remove any "no stack" string
            power = NO_STACK_RE_2.sub('', power)

        # Try the "all" pattern
        res = ALL_RE.match(power)
        if res is not None:
            return (res.group(2), res.group(1), None, stack)

        # Don't split a "count as" power that doesn't match ALL_RE
        if u' count as ' in power:
            return (power, None, None, stack)

        # And the "when" pattern
        res = WHEN_RE.match(power)
        if res is not None:
            return (res.group(1), res.group(2), None, stack)

        # Split at our separators
        res = SEP_RE.split(power)
        if len(res) == 2:
            return (res[0], res[1], None, stack)
        elif len(res) == 3:
            return (res[0], res[1], res[2], stack)
        return (power, None, None, stack)

    def _fix_lt_items(self, name, text, the_template, the_params, refs):
        """
        Check the list of items that affect this Lt.

        name -- page title.
        text -- current text of the page.
        the_template -- name of the primary template used on the page.
        the_params -- list of parameters to the template.
        refs -- list of pages that link to the page.

        Return the modified text parameter.
        """
        # Validate items parameters, if present
        # Check for items that affect every Lt
        lt_refs = cat_refs_map.refs_for(u'Lieutenants')
        refItems = self._items_in_refs(lt_refs)

        # Check for any items that have a power that affects this Lt
        refItems2 = self._items_in_refs(refs)
        # Does the item have a power that affects this Lt ?
        x = {k: v for k, v in six.iteritems(refItems2) if v[0] is not None and name in v[0]}
        refItems.update(x)

        # Check for items that affect all Lts of this rarity
        rarity = the_template.split()[1]
        rarity_refs = cat_refs_map.refs_for(u'%s Lieutenants' % rarity)
        refItems.update(self._items_in_refs(rarity_refs))

        # Check for items that affect the entire faction
        param_dict = utils.params_to_dict(the_params)
        try:
            faction = param_dict[u'faction']
            faction_refs = cat_refs_map.refs_for(u'%s Lieutenants' % faction)
            refItems.update(self._items_in_refs(faction_refs))
        except KeyError:
            # We don't know the faction, so just ignore it
            faction = None

        # Filter out any items that don't affect this Lt
        refItems = {k: v for k, v in six.iteritems(refItems) if self._affects_lt(name,
                                                                              rarity,
                                                                              faction,
                                                                              self._split_power(v[0])[1])}

        items = {}
        i = 0
        while True:
            i += 1
            name_str = u'item_%d' % i
            power_str = u'item_%d_pwr' % i
            image_str = u'item_%d_img' % i
            try:
                nameParam = param_dict[name_str]
            except KeyError:
                # Ran out of items
		# TODO There have been cases of Lts skipping item numbers...
                break
            powerParam = param_dict.get(power_str)
            imageParam = param_dict.get(image_str)
            items[nameParam] = (powerParam, imageParam, i)
        i = len(items)
        # compare the two lists and address any mismatches
        for key in refItems.keys():
            if key in items:
                # Compare the details
                if refItems[key][0] != items[key][0]:
                    pywikibot.output("Mismatch in power for %s - %s vs %s" % (key,
                                                                              refItems[key][0],
                                                                              items[key][0]))
                    if items[key][0]:
                        # This regex assumes that the parameter has a line to itself
                        text = re.sub(ur'item_%d_pwr\s*=\s*.*' % items[key][2],
                                      u'item_%d_pwr=%s\n' % (items[key][2],
                                                             refItems[key][0]),
                                      text)
                    else:
                        text = re.sub(ur'item_%d\s*=' % items[key][2],
                                      u'item_%d_pwr=%s\n|item_%d=' % (items[key][2],
                                                                      refItems[key][0],
                                                                      items[key][2]),
                                      text)
                if refItems[key][1] != items[key][1]:
                    pywikibot.output("Mismatch in image for %s - %s vs %s" % (key,
                                                                              refItems[key][1],
                                                                              items[key][1]))
                    if items[key][1]:
                        # This regex assumes that the parameter has a line to itself
                        text = re.sub(ur'item_%d_img\s*=\s*.*' % items[key][2],
                                      u'item_%d_img=%s\n' % (items[key][2],
                                                             refItems[key][1]),
                                      text)
                    else:
                        text = re.sub(ur'item_%d\s*=' % items[key][2],
                                      u'item_%d_img=%s\n|item_%d=' % (items[key][2],
                                                                      refItems[key][1],
                                                                      items[key][2]),
                                      text)
            else:
                pywikibot.output("Missing item %s which gives %s" % (key,
                                                                     refItems[key][0]))
                # Add the item. No way to determine which item should be which
                i += 1
                # TODO There must be a better way to do this...
                the_tuple = (i, key, i, refItems[key][0], i, refItems[key][1])
                new_params = u'|item_%d=%s\n|item_%d_pwr=%s\n|item_%d_img=%s' % the_tuple
                text = re.sub(the_template, u'%s\n%s' % (the_template, new_params), text)
        # TODO Deal with any that are in the items list but not in refItems
        pass
        return text

    def _fix_lt_needs_params(self,
                             text,
                             the_params,
                             is_tech_lab_item):
        """
        Fix the "Needs" categories on a Lieutenant page.

        text -- current text of the page.
        the_params -- list of parameters to the primary template.
        is_tech_lab_item -- True if the Lt has a Tech Lab recipe.

        Return modified version of text parameter.
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
        # That will be done in _fix_tech_lab_item.
        if not is_tech_lab_item:
            lt_param_map[u'from'] = u'Needs Source'

        return self._fix_needs_categories(text,
                                          the_params,
                                          lt_param_map)

    def _fix_skin(self, name, text, templatesWithParams, refs):
        """
        Fix a Lieutenant Skin page.

        name -- name of the Skin (page title).
        text -- current page text.
        templatesWithParams -- list of templates used and corresponding parameters.
        refs -- list of pages that link to the page.

        Return updated text.

        If the page uses the 'Skin' template:
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check that all parameters are present, or that tha page is in the 'Needs Information' category.
        """
        # Does the page use the skin template ?
        the_params = None
        for template,params in templatesWithParams:
            if template == u'Skin':
                the_template = template
                the_params = params
            elif template == u'Skinned Lieutenant':
                print("*** %s page uses old 'Skinned Lieutenant' template" % name)

        # Drop out early if not a skin page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Check for explicit categories that should be implicit
        text = self._remove_implicit_categories(text)

        # Check mandatory parameters
        skin_param_map = {u'lt': u'Needs Information',
                          u'skinned_lt': u'Needs Information',
                          u'unlock': u'Needs Information',
                          u'image': u'Needs Improvement'} #u'Needs Image'}

        text = self._fix_needs_categories(text,
                                          params,
                                          skin_param_map)

        return text

    def _fix_lieutenant(self,
                        name,
                        text,
                        templatesWithParams,
                        refs):
        """
        Fix a Lieutenant page.

        name -- name of the Lieutenant (page title).
        text -- current page text.
        templatesWithParams -- list of templates used and corresponding parameters.
        refs -- list of pages that link to the page.

        Return updated text.

        If the page uses any of the templates 'Lieutenant Common',
        'Lieutenant Uncommon', 'Lieutenant Rare, or 'Lieutenant Epic':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Remove any empty stat or power parameters, and any (old) item parameters.
        Add any missing sources.
        Check items and add missing ones.
        """
        # Does the page use a lieutenant template ?
        the_params = None
        ingredients = None
        is_tech_lab_item = name in recipe_cache.recipes()
        for template,params in templatesWithParams:
            # Find the templates we're interested in
            if template == u'Lieutenant':
                pywikibot.output("Directly uses Lieutenant template")

            elif u'Lab' in template:
                is_tech_lab_item = True
                ingredients = params

            elif template == u'Lieutenant Row':
                # Break this one out from the next "elif"
                pass

            elif template.startswith(u'Lieutenant '):
                the_template = template
                the_params = params

        # Drop out early if not a lieutenant page
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # Now nuke any empty stat or power parameters, and any items parameters
        to_nuke = []
        for param in the_params:
            p = param.rstrip()
            if p == u'':
                to_nuke.append(param)
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

        text = self._fix_lt_needs_params(text,
                                         the_params,
                                         is_tech_lab_item)

        text = self._fix_lt_sources(name,
                                    text,
                                    the_params,
                                    refs)

        # Do special checks for any Epic Research Items
        if is_tech_lab_item:
            text = self._fix_tech_lab_item(name,
                                           text,
                                           the_params,
                                           ingredients,
                                           False)

        # Validate items parameters, if present
        text = self._fix_lt_items(name, text, the_template, the_params, refs)

        return text

    # The next few methods are only used on Item pages

    def _fix_item(self, name, text, categories, templatesWithParams, refs):
        """
        Fix an Item page.

        name -- name of the Item (page title).
        text -- current page text.
        categories -- a list of category Pages the page is current in.
        templatesWithParams -- list of templates used and corresponding parameters.
        refs -- list of pages that link to the page.

        Return updated text.

        If the page uses any of the templates 'Item', 'Gift Item',
        'Mystery Gift Item', 'Faction Item', 'Special Item', 'Basic Item',
        'Battle Rank Item', or 'Ingredient':
        Ensure that __NOWYSIWYG__ is present.
        Check that the page doesn't explictly list any categories that should be
        assigned by the template.
        Check that the item is listed everywhere it says it can be obtained.
        Check whether the categories Needs Cost and Needs Type are used correctly.
        Call the appropriate fix function for the specific type of item.
        """
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

            if template in [u'Gift Item',
                            u'Mystery Gift Item',
                            u'Faction Item',
                            u'Special Item',
                            u'Basic Item',
                            u'Battle Rank Item',
                            u'Ingredient']:
                the_template = template
                the_params = params

        # Drop out early if not an item page
        # This ignores Stamina Pack and Energy Pack, but that's probably fine
        # TODO Is there a better test ?
        if the_params is None:
            return text

        # Check for explicit categories that should be implicit
        text = self._remove_implicit_categories(text)

        # __NOWYSIWYG__
        text = self._prepend_NOWYSIWYG_if_needed(text)

        # If the item comes from somewhere special, do cross-ref check
        # (Mystery) Gift Item template uses from with a different meaning
        if template != u'Gift Item' and template != u'Mystery Gift Item':
            from_param = utils.param_from_params(the_params, u'from')
            text = self._fix_drop(name, text, from_param, refs)

        # Do more detailed checks for specific sub-types
        if the_template == u'Gift Item':
            text = self._fix_gift_item(name, text, the_params)
        elif the_template == u'Mystery Gift Item':
            text = self._fix_mystery_gift_item(name,
                                               text,
                                               the_params)
        elif the_template == u'Faction Item':
            text = self._fix_faction_item(name, text, the_params)
        elif the_template == u'Special Item':
            text = self._fix_special_item(name,
                                          text,
                                          the_params,
                                          is_tech_lab_item)
        elif the_template == u'Basic Item':
            text = self._fix_basic_item(text, the_params, categories)
        elif the_template == u'Battle Rank Item':
            text = self._fix_battle_item(name, text, the_params)
        elif the_template == u'Ingredient':
            text = self._fix_ingredient(name,
                                        text,
                                        the_params,
                                        is_tech_lab_item)

        # Do special checks for any Epic Research Items
        if is_tech_lab_item:
            text = self._fix_tech_lab_item(name,
                                           text,
                                           the_params,
                                           ingredients)

        achievements = ach.rewards_for(name)
        if len(achievements):
            ach_str = achievement_text(achievements)
            # Assume all item pages use a template,
            # Achievement text goes after the last one
            start = text.rindex(u'}}')
            try:
                end = text.index(u'\n', start)
            except ValueError:
                end = len(text)
            text = text[:start] + text[start:].replace(text[start:end],
                                                       u'}}' + ach_str)
        elif u'Achievements' in [r.title() for r in refs]:
            pywikibot.output("Page links to Achievements, but there isn't a related achievement")

        return text

    def _fix_drop(self, name, text, from_param, refs):
        """
        Check that the page lists the right places it can be obtained from.

        name -- item name.
        text -- current text of the page.
        from_param -- value of the "from" template parameter (or None).
        refs -- list of pages that link to this one.

        Return text with any missing sources added.
        """
        # First, find pages that list this item as a drop
        # Starting with the list of pages that link here
        source_set = set()
        for r in refs:
            for temp,params in r.templatesWithParams():
                template = temp.title(withNamespace=False)
                if (template == u'Drop') or (template == u'BossDrop'):
                    if utils.param_from_params(params, u'name') == name:
                        # TODO If it has creator=true, need to ensure that's reflected on this page
                        source_set.add(r.title())
                elif template == u'Mystery Gift Item':
                    gift_params = utils.params_to_dict(params)
                    if name in list(gift_params.values()):
                        source_set.add(r.title())
                elif template == u'Execution Method':
                    if name in utils.param_from_params(params, u'bonus'):
                        source_set.add(r.title())
                elif template == u'Challenge Job' and u'Recombinator' in name:
                    # Challenge Jobs drop Recombinators
                    if utils.param_from_params(params, u'recombinator') in name:
                        source_set.add(u'{{Job Link|district=%s|job=%s}}' %
                                           (r.title(),
                                            utils.param_from_params(params, u'name')))
            # TODO Pages referenced from HQ can either be requirements
            # to build improvements, or drops after Wars with Shadow Broker.
            # Assume any page linked to from the Favor Point page is available from the Black Market
            if r.title() == u'Favor Point':
                source_set.add(u'Black Market')
            # Don't call r.categories() for redirects
            elif r.isRedirectPage():
                pass
            # If it's linked to from a giveaways page, assume it was given away
            elif self._cat_in_categories(u'Giveaways', r.categories()):
                source_set.add(r.title())
            # If it's linked from an event page, check whether it's in a list
            # All rewards are in lists, although the converse may not be true
            elif self._cat_in_categories(u'Events', r.categories()):
                m = re.search(u'\*.*%s' % name, r.get())
                if m:
                    source_set.add(r.title())
        # Check whether it's a daily achievement reward
        if ach.is_daily_reward(name):
            source_set.add(u'Achievements#Daily')
        # Then, find the places listed as sources in this page
        # Remove any that match from the source list, leaving missing sources
        # Count the number of sources already in the list as we go
        src_count = 0
        if from_param:
            m = re.search(ur'{{Lab.*}}', from_param, re.MULTILINE | re.DOTALL)
            if m:
                src_count += 1
                # Need to avoid matches within the Lab template part
                from_str = from_param[:m.start()] + from_param[m.end():]
            else:
                from_str = from_param
            iterator = chain(LINK_RE.finditer(from_str),
                             re.finditer(ur'(?P<page>{{.*}})', from_str))
        else:
            iterator = []
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
        # Are any changes needed ?
        if source_set:
            # Add a from parameter if necessary
            if src_count == 0:
                if len(source_set) == 1:
                    from_param = u'|from='
                else:
                    from_param = u'|from=<br/>'
                text = text.replace(u'|image', u'%s|image' % from_param, 1)
            # Convert from single source to a list if necessary
            if src_count == 1:
                text = text.replace(from_param, u'<br/>\n*' + from_param)
        # Add missing sources to the page
        if (src_count == 0) and (len(source_set) == 1):
            # Add the single source on the same line
            new_str = u''
        else:
            # Each new source gets its own list entry
            new_str = u'\n*'
        for src in source_set:
            if src == u'Achievements#Daily':
                src = u'Achievements#Daily|Daily Achievements'
            if src.startswith(u'{{'):
                # Assume templates will include square brackets
                base = u'%s%s'
            else:
                base = u'%s[[%s]]'
            text = text.replace(from_param,
                                from_param + base % (new_str, src))
        return text

    def _fix_item_type(self, text, params):
        """
        Check the type parameter.

        text -- current page text.
        params -- list of parameters to the primary template.

        Return updated text.

        Add or remove the Needs Type category.
        """
        types = [u'Gear',
                 u'Vehicles',
                 u'Melee Weapons',
                 u'Rifles',
                 u'Handguns',
                 u'Heavy Weapons',
                 u'Needs Type']
        cat = u'Needs Type'

        type_param = utils.param_from_params(params, u'type')
        if type_param is None:
            # Add a type parameter, with value Needs Type
            text = self._add_param(text, params, u'type=' + cat + u'\n')
        else:
            # Check that the type is one we expect
            if one_cap(type_param) not in types:
                pywikibot.output("Unexpected type '%s'" % type_param)
                # Change it to Needs Type
                # Note that this replaces every instance of the text in type_param...
                text = text.replace(type_param, cat)

        return text

    def _fix_gift_level(self, name, text, params):
        """
        Fix the minimum level for a gift item.

        name -- name of the gift item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.

        Return updated text.

        Check the from parameter.
        Add or remove Needs Minimum Level category.
        Warn if the from parameter differs from what the Gift page says.
        """
        from_param = utils.param_from_params(params, u'from')
        if from_param is None:
            text = self._append_category(text, u'Needs Minimum Level')
        else:
            text = self._remove_category(text, u'Needs Minimum Level')
            gift_page = pywikibot.Page(pywikibot.Site(), u'Gift')
            iterator = GIFT_RE.finditer(gift_page.get())
            for m in iterator:
                if m.group('item') == name:
                    if m.group('level') != from_param:
                        pywikibot.output("Minimum level mismatch - Gift page says %s, this page says %s" % (m.group('level'), from_param))
        return text

    def _fix_gift_item(self, name, text, params):
        """
        Fix a gift item page.

        name -- name of the gift item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.

        Return updated text.

        Ensure that gift items have description, image, atk, def, cost,
        rarity, and from parameters, or appropriate "Needs" category.
        Trust that type param will be checked elsewhere.
        Check that the minimum level is specified, and that it matches what the Gift page says.
        Assume that that page uses the Gift Item template.
        """
        # Check mandatory parameters
        gift_param_map = {u'description': u'Needs Description',
                          u'atk': u'Needs Stats',
                          u'def': u'Needs Stats',
                          u'cost': u'Needs Cost',
                          u'rarity': u'Needs Rarity',
                          u'image': u'Needs Improvement'} #u'Needs Image'}

        text = self._fix_needs_categories(text,
                                          params,
                                          gift_param_map)

        # Check from parameter against the Gift page
        text = self._fix_gift_level(name, text, params)

        # Check type param
        text = self._fix_item_type(text, params)

        return text

    def _fix_mystery_gift_item(self, name, text, params):
        """
        Fix a mystery gift item page.

        name -- name of the mystery gift item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.

        Return updated text.

        Ensure that mystery gift items have image, from, item_1, and item_2
        parameters, or appropriate "Needs" category.
        Check that the minimum level is specified, and that it matches what the Gift page says.
        Assume that that page uses the Mystery Gift Item template.
        """
        # Check mandatory parameters
        gift_param_map = {u'item_1': u'Needs Information', #u'Needs Item',
                          u'item_2': u'Needs Information', #u'Needs Item',
                          u'image': u'Needs Improvement'} #u'Needs Image'}

        text = self._fix_needs_categories(text,
                                          params,
                                          gift_param_map)

        # Check from parameter against the Gift page
        text = self._fix_gift_level(name, text, params)

        return text

    def _fix_faction_item(self, name, text, params):
        """
        Fix a faction item page.

        name -- name of the faction item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.

        Return updated text.

        Ensure that faction items have description, image, atk, def, cost,
        rarity params or appropriate "Needs" category.
        Check that the faction is specified, and that the item is listed on
        that page, and that the points param is right.
        Assume that the page uses the Faction Item template.
        """
        # Check mandatory parameters
        faction_param_map = {u'description': u'Needs Description',
                             u'atk': u'Needs Stats',
                             u'def': u'Needs Stats',
                             u'cost': u'Needs Cost',
                             u'rarity': u'Needs Rarity',
                             u'image': u'Needs Improvement'} #u'Needs Image'}

        text = self._fix_needs_categories(text,
                                          params,
                                          faction_param_map)

        # Check points against corresponding faction page
        param_dict = utils.params_to_dict(params)
        try:
            faction_param = param_dict[u'faction']
            try:
                points_param = param_dict[u'points']
            except KeyError:
                text = self._append_category(text,
                                             u'Needs Unlock Criterion')
            else:
                faction_page = pywikibot.Page(pywikibot.Site(), faction_param)
                iterator = FACTION_RE.finditer(faction_page.get())
                for m in iterator:
                    if m.group('item') == name:
                        if points_param != m.group('points'):
                            # Change the value
                            # Note that this replaces every instance of the text in points_param...
                            text = text.replace(points_param, m.group('points'))
        except KeyError:
            text = self._append_category(text,
                                         u'Needs Information') # u'Needs Faction'

        # Check type param
        text = self._fix_item_type(text, params)

        return text

    def _recipes_using(self, name):
        """
        Return a set of item names that this item is an ingredient for.

        name -- name of the item of interest.

        Only checks recipe_cache (i.e. Tech Lab pages).
        """
        retval = set()
        for r in recipe_cache.recipes():
            for p in recipe_cache.recipe_for(r):
                # This assumes no space between the = and the parameter value
                if p.startswith(u'part_') and p.endswith(u'=' + name):
                    retval.add(r)

        return retval

    def _add_param(self, text, params, new_param):
        """
        Add a parameter to the parameters of a template.

        text -- current page content.
        params -- list of template parameters to add to.
        new_param -- item to add. Should take the form u'<name>=<value>'.

        Return the modified page text.
        """
        # Note that this just finds the first instance of params[0]...
        start = text.find(params[0])
        if start != -1:
            text = text[0:start] + new_param + u'|' + text[start:]
        else:
            assert 0, "Failed to find params %s" % params

        return text

    def _fix_possible_ingredient(self,
                                 name,
                                 text,
                                 params,
                                 for_mandatory=False):
        """
        Fix an item that may be an ingredient in Tech Lab recipes.

        name -- name of the item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.
        for_mandatory -- pass True to indicate that there must be a "for"
                         parameter.

        Return updated page text.

        Check any for parameter. Modify it or add a category as needed.
        If for_mandatory is True, a Needs category will be added if no for
        parameter is present and one can't be derived.
        """
        recipes = self._recipes_using(name)
        for_param = utils.param_from_params(params, u'for')

        if for_param is None:
            if len(recipes) > 1:
                # Add a for parameter listing the recipes
                new_param = u'for=<br/>\n*[[' + u']]\n*[['.join(recipes) + u']]\n'
                text = self._add_param(text, params, new_param)
            elif recipes:
                # Add a for parameter listing the recipe
                new_param = u'for=[[' + u']], [['.join(recipes) + u']]\n'
                text = self._add_param(text, params, new_param)
            elif for_mandatory:
                # It should be for something, but we don't know what
                text = self._append_category(text,
                                             u'Needs Information') # u'Needs Purpose'
        else:
            # Check that all the recipes we found are listed in the for parameter
            for r in recipes:
                if r not in for_param:
                    text = text.replace(u'|for=<br/>', u'|for=<br/>\n*[[%s]]' % r)
                    # If that did nothing, need to turn "for" into a list
                    if r not in text:
                        text = text.replace(u'|for=', u'|for=<br/>\n*[[%s]]\n*' % r)
            pass

        return text

    def _fix_special_item(self,
                          name,
                          text,
                          params,
                          is_tech_lab_item):
        """
        Fix a special item page.

        name -- name of the special item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.
        is_tech_lab_item -- pass True if the item has or had a recipe in
                            the Tech Lab.

        Returns updated text.

        Ensure that special items have description, image, atk, def, cost,
        rarity, type and from params or appropriate "Needs" category.
        Assume that the page uses the Special Item template.
        """
        # Check mandatory parameters
        special_param_map = {u'description': u'Needs Description',
                             u'atk': u'Needs Stats',
                             u'def': u'Needs Stats',
                             u'rarity': u'Needs Rarity',
                             u'image': u'Needs Improvement'} #u'Needs Image'}
        # If it's a tech lab item, don't bother checking what it's made from.
        # That will be done in _fix_tech_lab_item.
        if not is_tech_lab_item:
            special_param_map[u'from'] = u'Needs Source'

        text = self._fix_needs_categories(text,
                                          params,
                                          special_param_map)

        # Check type param
        text = self._fix_item_type(text, params)

        text = self._fix_possible_ingredient(name, text, params)

        return text

    def _fix_basic_item(self, text, params, categories):
        """
        Fix a basic item page.

        text -- current text of the page.
        params -- list of parameters to the primary template.
        categories -- list of categories the page belongs to.

        Returns updated text.

        Ensure that basic items have description, image, atk, def, cost,
        rarity, quote and time params or appropriate "Needs" category.
        Check that either level or area is specified.
        Check that it not explicitly in Daily Rewards category.
        Assume that the page uses the Basic Item template.
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

        text = self._fix_needs_categories(text,
                                          params,
                                          basic_param_map)

        # Check that we have either level or district but not both
        param_dict = utils.params_to_dict(params)
        level_param = param_dict.get(u'level')
        area_param = param_dict.get(u'district')
        if level_param is None:
            if area_param is None:
                pywikibot.output("Missing both level and district parameters")
                text = self._append_category(text,
                                             u'Needs Unlock Criterion')
        else:
            if area_param is not None:
                pywikibot.output("Both level and district parameters are present")

        # Ensure that daily items are specified with parameter, not explicit category
        cat = u'Daily Rewards'
        if self._cat_in_categories(cat, categories):
            text = self._remove_category(text, cat)
            # Add a daily parameter, with value yes, if not already present
            if u'daily' not in param_dict:
                text = self._add_param(text, params, u'daily=yes')

        # Check type param
        text = self._fix_item_type(text, params)

        return text

    def _fix_battle_item(self, name, text, params):
        """
        Fix a battle rank item page.

        name -- name of the battle rank item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.

        Returns updated text.

        Ensure that battle rank items have description, image, atk, def,
        cost, rarity params or appropriate "Needs" category.
        Check that the battle rank is specified, and that it matches what
        the Battle Rank page says.
        Assume that the page uses the Battle Rank Item template.
        """
        # Check mandatory parameters
        battle_param_map = {u'description': u'Needs Description',
                            u'atk': u'Needs Stats',
                            u'def': u'Needs Stats',
                            u'cost': u'Needs Cost',
                            u'rarity': u'Needs Rarity',
                            u'time': u'Needs Build Time',
                            u'image': u'Needs Improvement'} #u'Needs Image'}

        text = self._fix_needs_categories(text,
                                          params,
                                          battle_param_map)

        # Check rank parameter against Battle Rank page
        rank_param = utils.param_from_params(params, u'rank')
        if rank_param is None:
            text = self._append_category(text, u'Needs Unlock Criterion')
        else:
            rank_page = pywikibot.Page(pywikibot.Site(), u'Battle Rank')
            templatesWithParams = rank_page.templatesWithParams()
            for tmp,p in templatesWithParams:
                t = tmp.title(withNamespace=False)
                if t == u'Battle Rank List':
                    param_dict = utils.params_to_dict(p)
                    rank = param_dict[u'number']
                    item = param_dict[u'reward']
                    if item == u'[[%s]]' % name and rank != rank_param:
                        pywikibot.output("Minimum battle rank mismatch - Battle Rank page says %s, this page says %s" % (rank, rank_param))

        # Check type param
        text = self._fix_item_type(text, params)

        return text

    def _fix_ingredient(self,
                        name,
                        text,
                        params,
                        is_tech_lab_item):
        """
        Fix an ingredient page.

        name -- name of the special item (page title).
        text -- current text of the page.
        params -- list of parameters to the primary template.
        is_tech_lab_item -- pass True if the item has or had a recipe in
                            the Tech Lab.

        Returns updated text.

        Ensure that ingredient items have image, rarity, from and for params
        or appropriate "Needs" category.
        Check that the item is listed on the from and for pages.
        Assume that the page uses the Ingredient template.
        """
        # Check mandatory parameters
        ingr_param_map = {u'rarity': u'Needs Rarity',
                          u'image': u'Needs Improvement'} #u'Needs Image'}

        # If it's a tech lab item, from parameter will be misleading
        if not is_tech_lab_item:
            ingr_param_map[u'from'] = u'Needs Source'

        text = self._fix_needs_categories(text,
                                          params,
                                          ingr_param_map)

        text = self._fix_possible_ingredient(name,
                                             text,
                                             params,
                                             True)

        return text

    # The remaining methods are used on both Lieutenant and Item pages

    def _fix_tech_lab_item(self,
                           name,
                           text,
                           params,
                           lab_params,
                           check_image=True):
        """
        Fix the page of something that has or had a tech lab recipe.

        name -- name of the item or lt.
        text -- current text of the page.
        params -- list of parameters to the primary template.
        lab_params -- list of parameters to the Lab template, or None.
        check_image -- pass True to check that the image matches the one
                       on the Tech Lab page.

        Returns updated text.

        Check that it is listed as made in the same way on its page and
        the Tech Lab page.
        Check that atk and def match what the Tech Lab page says.
        """
        # Find this recipe on one of the tech lab pages
        recipe_dict = utils.params_to_dict(recipe_cache.recipe_for(name))
        param_dict = utils.params_to_dict(params)

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
                text = text.replace(u'|from=',
                                    u'|from=<br/>\n*{{Lab|in_list=yes}}\n*',
                                    1)
            else:
                text = text.replace(u'|image=',
                                    u'|from={{Lab}}\n|image=',
                                    1)
        else:
            lab_dict = utils.params_to_dict(lab_params)

        # Compare image
        if check_image:
            try:
                img_param = param_dict[u'image']
            except KeyError:
                # TODO Insert missing image
                pass
            else:
                if img_param != recipe_dict[u'image']:
                    pywikibot.output("Image parameter mismatch - %s in page, %s on Tech Lab page" % (img_param, recipe_dict[u'image']))

        # TODO Add Needs Build Time category if appropriate

        # Compare atk and def
        for p in [u'atk', u'def']:
            try:
                the_param = param_dict[p]
            except KeyError:
                pass
            else:
                if the_param != recipe_dict[p]:
                    pywikibot.output("%s parameter mismatch - %s in page, %s on Tech Lab page" % (p, the_param, recipe_dict[p]))

        # Check that num_parts is right, if present
        # For some Lab templates, num_parts is optional. Those should all have 5 parts
        try:
            num_parts = int(lab_dict[u'num_parts'])
        except (KeyError, TypeError):
            num_parts = 5
        # Count number of parts in the Tech Lab recipe
        total = self._parts_count(recipe_dict)
        if total != num_parts:
            # Fix num_parts, if present, else flag missing ingredient(s)
            # TODO This assumes no spaces in the parameter setting
            text = text.replace(u'num_parts=%d' % num_parts,
                                u'num_parts=%d' % total)
            if u'num_parts' not in text:
                # Add num_parts if not already present
                text = text.replace(u'Lab', u'Lab|num_parts=%d' % total)

        # Check the Lab parameters against the Recipe parameters
        lab_keys = set(lab_dict.keys())
        lab_keys -= {u'in_list', u'num_parts'}
        recipe_keys = set(recipe_dict.keys())
        recipe_keys -= {u'description', u'image', u'atk', u'def', u'name'}
        for key in recipe_keys:
            if key in lab_keys:
                if recipe_dict[key] != lab_dict[key]:
                    # Fix up this page to match Tech Lab, because recipes are found there
                    text = re.sub(ur'(\|\W*%s\W*=\W*)%s' % (key,
                                                            utils.escape_str(lab_dict[key])),
                                  ur'\g<1>%s' % recipe_dict[key],
                                  text)
            else:
                # Insert the missing parameter
                pywikibot.output("Missing param - %s" % recipe_dict[key])
                # TODO this doesn't work for Lab Four of a Kind or Lab Full House
                text = text.replace(u'Lab',
                                    u'Lab\n|%s=%s' % (key, recipe_dict[key]),
                                    1)

        # Check any Lab "from" parameters are correct
        text = self._fix_TL_item_source(text, lab_dict)

        return text

    def _fix_TL_item_source(self, text, lab_dict):
        """
        Check that the sources listed for ingredients are correct.

        text -- current text of the page.
        lab_dict -- dictionary of parameters to the Lab template.

        Return updated text.
        """
        i = 0
        while True:
            i += 1
            part_str = u'part_%d' % i
            try:
                part = lab_dict[part_str]
            except KeyError:
                break
            from_str = part_str + u'_from'
            try:
                part_pg = pywikibot.Page(pywikibot.Site(), part)
            except pywikibot.NoPage:
                # No idea where it's from, so that's fine
                continue
            tmp = part_pg.templatesWithParams()
            templatesWithParams = [(t.title(withNamespace=False),p) for (t,p) in tmp]
            src_param = None
            for t,p in templatesWithParams:
                src_param = utils.param_from_params(p, u'from')
            if not src_param:
                # Ingredient page doesn't say where to get it
                continue
            # Map it to a more suitable format
            src_param = self._one_line(src_param)
            try:
                src = lab_dict[from_str]
            except KeyError:
                # Add from parameter to this page
                new_param = u'|%s=%s' % (from_str, src_param)
                text = text.replace(ur'|%s' % part_str,
                                    u'%s\n|%s' % (new_param, part_str),
                                    1)
            else:
                # Compare with src_param
                if src != src_param:
                    if src in src_param:
                        # New source(s) have been added to the item page
                        # TODO This assumes no whitespace
                        text = text.replace(u'|%s=%s' % (from_str, src),
                                            u'|%s=%s' % (from_str, src_param),
                                            1)
                    else:
                        pywikibot.output("Source mismatch for %s - this page says %s, item page says %s\n" % (part, src, src_param))
        return text

    def _parts_count(self, lab_dict):
        """
        Return the total number of parts.

        lab_dict -- dictionary of parameters to the Lab template.
        """
        total = 0
        i = 0
        while True:
            i += 1
            part_str = u'part_%d' % i
            try:
                part = lab_dict[part_str]
            except KeyError:
                break
            num_str = part_str + u'_count'
            if num_str in lab_dict:
                part_num = int(lab_dict[num_str])
            else:
                part_num = 1
            total += part_num
        return total

class XrefBot:

    """Main Xref WikiBot class."""

    def __init__(self, generator, acceptall = False):
        """
        Class constructor.

        generator -- iterator to generate Pages to process.
        acceptall -- pass True to not prompt the user whether to accept
                     changes, but to go ahead and apply all changes.
        """
        self.generator = generator
        self.acceptall = acceptall
        # Find all the sub-categories of Needs Information
        cat = pywikibot.Category(pywikibot.Site(),
                                 u'Category:Needs Information')
        self.specific_needs = set(c.title(withNamespace=False) for c in cat.subcategories(recurse=True))

    def treat(self, page):
        """
        Check and update a single page.

        page -- Page object to be checked and possibly updated.
        """
        try:
            # Drop out quickly for namespaces that we don't deal with
            ns = page.namespace()
            if ns == "File" or ns == "Talk" or ns == "User" or ns == "Thread":
                pywikibot.output(u"Skipping %s because it's in the %s namespace" % (page.title(), ns))
                return
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            pywikibot.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            xrToolkit = XrefToolkit(self.specific_needs, debug = True)
            changedText = xrToolkit.change(page.get(), page)
            # TODO Modify to treat just whitespace as unchanged
            # Just comparing changedText with page.get() wasn't sufficient
            changes = False
            for diffline in difflib.ndiff(page.get().splitlines(),
                                          changedText.splitlines()):
                if not diffline.startswith(u'  '):
                    changes = True
                    break
            if changes:
                if not self.acceptall:
                    choice = pywikibot.input_choice(u'Do you want to accept these changes?',
                                                    [('Yes', 'Y'),
                                                     ('No', 'n'),
                                                     ('All', 'a')],
                                                    'N')
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
        """Process each Page in turn."""
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

