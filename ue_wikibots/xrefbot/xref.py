#! /usr/bin/python

"""
Script to fix up categories and cross-references between pages on UE Wiki.
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
    'en': u'Robot: Fix cross-references and/or categories',
}

# Summary message  that will be appended to the normal message when
# cosmetic changes are made on the fly
msg_append = {
    'en': u'; fix cross-references and/or categories',
}

# Copied from wikipedia.py
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
#TODO fix this so it doesn't coalesce multiple categories
Rcategory = re.compile(ur'\[\[\s*Category:.*\]\]')

def listFromSection(text, section_name, whole_lines=False):
    """
    Extract a list from a section of text.
    section_name specifies the section to find.
    Returns a tuple - (section found boolean, list of content, index where the section starts, index where the section ends)
    where content is the first link on the line if whole_lines is False,
    or everything after '[[' to the end of the line if whole_lines is True.
    """
    # Does the page have the specified section ?
    section_present = False
    item_list = []
    list_start = list_end = -1
    match = re.search(r'==\s*%s' % section_name.lower(), text.lower())
    if match:
        list_start = match.start()
        section_present = True
        # List ends at a template, header or category
        # Skip the start of the header for the section of interest itself
        match = re.search(r'{{|==.*==|\[\[Category', text[list_start+2:])
        if match:
            list_end = list_start+2+match.start()
        else:
            list_end = len(text)
        # Shift list_end back to exactly the end of the list
        while text[list_end-1] in u'\n\r':
            list_end -= 1
        list_text = text[list_start:list_end]
        # If so, what items are listed ?
        if whole_lines:
            reItem = re.compile(r'\[\[\s*(.*)')
        else:
            reItem = re.compile(r'\[\[\s*([^|\]]*?)(\|.*)?\]\]')
        for match in reItem.finditer(list_text):
            item_list.append(match.expand(r'\1'))
            list_text = list_text[match.end():]
    return (section_present, item_list, list_start, list_end)

def dropParamsMatch(param1, param2):
    """
    Compares two drop parameters.
    Ignores case of first character, and reports a match if one is a link
    and the other isn't.
    """
    # Direct match first
    if param1 == param2:
        return True
    # Match link with non-link equivalent
    if param1[0:2] == u'[[':
        return param1[2:-2] == param2
    if param2[0:2] == u'[[':
        return param1 == param2[2:-2]
    # Match with mismatched case of first character
    if param1[1:] == param2[1:]:
        return param1[0].lower() == param2[0].lower()
    # TODO Match link with nonlink with mismatched first character
    return False

def missingParams(all_params, mandatory_list):
    """
    Returns the set of all the parameters in mandatory_list that are not represented in all_params.
    """
    ret = set(mandatory_list)
    for p in all_params:
        m = utils.Rparam.match(p)
        if m != None and m.group('name') in ret:
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
        titleWithoutNamespace = page.titleWithoutNamespace()
        # Leave template pages alone
        # TODO Better to match title or category ?
        if titleWithoutNamespace.find(u'Template') != -1:
            wikipedia.output("Not touching template page %s" % titleWithoutNamespace)
            return text
        # Note that this only gets explicit categories written into the page text,
        # not those added by templates.
        categories = page.categories()
        templatesWithParams = page.templatesWithParams()
        # Don't do anything to stub pages
        for template,params in templatesWithParams:
            if template == u'Stub':
                wikipedia.output("Not touching stub page %s" % titleWithoutNamespace)
                return text
        refs = page.getReferences()
        oldText = text
        #wikipedia.output("******\nIn text:\n%s" % text)
        # TODO There's probably a sensible order for these...
        text = self.fixBoss(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixItem(titleWithoutNamespace, text, categories, templatesWithParams, refs)
        text = self.fixLieutenant(titleWithoutNamespace, text, categories, templatesWithParams, refs)
        text = self.fixProperty(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixExecutionMethod(text, categories, templatesWithParams)
        text = self.fixClass(text, categories, templatesWithParams)
        text = self.fixTechLab(titleWithoutNamespace, text, categories, templatesWithParams)
        text = self.fixDistrict(titleWithoutNamespace, text, categories, templatesWithParams)
        #wikipedia.output("******\nOld text:\n%s" % oldText)
        #wikipedia.output("******\nIn text:\n%s" % text)
        # Just comparing oldText with text wasn't sufficient
        changes = False
        for diffline in difflib.ndiff(oldText.splitlines(), text.splitlines()):
            if not diffline.startswith(u'  '):
                changes = True
                break
        if changes:
            print
            wikipedia.output(text)
        if self.debug:
            print
            wikipedia.showDiff(oldText, text)
        return text

    # Now a load of utility methods

    def escapeParentheses(self, text):
        """
        Returns text with every ( and ) preceeded by a \.
        """
        retval = re.sub(r'\(', r'\(', text)
        retval = re.sub(r'\)', r'\)', retval)
        return retval

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
        return text + u'\n[[Category:%s]]' % category

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

    def templateParam(self, templatesWithParams, template, param):
        """
        If the specified template is present, and gives a value for
        the specified param, return that value.
        Otherwise, return an empty string.
        """
        for (the_template, got_params) in templatesWithParams:
            if template == the_template:
                for the_param in got_params:
                    match = re.search(r'\s*%s\s*=([^\|]*)' % param, the_param, re.MULTILINE)
                    if match:
                        return match.expand(r'\1')
        return u''

    def templateParamMissing(self, templatesWithParams, template, params):
        """
        If the specified template is present, and doesn't give a value for any
        of the specified params, return True.
        """
        for (the_template, got_params) in templatesWithParams:
            if template == the_template:
                params_present = []
                for param in got_params:
                    for match in re.finditer(r'([^=,]+)', param):
                        params_present.append(match.expand(r'\1') .strip())
                for param in params:
                    if param not in params_present:
                        print "Param %s missing from template %s" % (param, template)
                        return True
        return False

    def listFromParam(self, params, param_name, whole_lines=False):
        """
        Extract a list from the parameter of a template
        param_name specifies the param to find.
        Returns a list of content,
        where content is the first link on the line if whole_lines is False,
        or everything after '[[' to the end of the line if whole_lines is True.
        """
        item_list = []
        # Does the template have the specified param ?
        for param in params:
            if param_name in param:
                # what items are listed ?
                if whole_lines:
                    reItem = re.compile(r'\[\[\s*(.*)')
                else:
                    reItem = re.compile(r'\[\[\s*([^|\]]*?)(\|.*)?\]\]')
                for match in reItem.finditer(param):
                    item_list.append(match.expand(r'\1'))
        return item_list

    def listFromParamOfTemplate(self, templatesWithParams, template_name, param_name, whole_lines=False):
        """
        Extract a list from the parameter of a template
        template_name specifies the template to find.
        param_name specifies the param to find.
        Returns a tuple - (list of content, param found boolean),
        where content is the first link on the line if whole_lines is False,
        or everything after '[[' to the end of the line if whole_lines is True.
        """
        for (template, params) in templatesWithParams:
            if template == template_name:
                return (self.listFromParam(params, param_name, whole_lines), True)
        return ([], False)

    def findTemplate(self, text, name=None):
        """
        Find a template in text.
        If name is specified, find the named template.
        Returns a tuple - (template name (or None), index where the template starts, index where the template ends)
        """
        # Does the page use any templates ?
        for match in Rtemplate.finditer(text):
            found_name = match.expand(r'\g<name>')
            if (name == None) or (found_name.find(name) != -1):
                return (found_name, match.start(), match.end())
        return (None, -1, -1)

    def parametersFromTemplate(self, templateText):
        """
        Returns the list of parameters in templateText.
        This is copied extensively from wikipedia's templateWithParams()
        """
        params = []
        match = Rtemplate.search(templateText)
        if match:
            paramString = match.group('params')
            if paramString:
                Rlink = re.compile(ur'\[\[[^\]]+\]\]')
                marker2 = wikipedia.findmarker(templateText,  u'##', u'#')
                Rmarker2 = re.compile(ur'%s(\d+)%s' % (marker2, marker2))
                # Replace links to markers
                links = {}
                count2 = 0
                for m2 in Rlink.finditer(paramString):
                    count2 += 1
                    text = m2.group()
                    paramString = paramString.replace(text,
                                    '%s%d%s' % (marker2, count2, marker2))
                    links[count2] = text
                # Parse string
                markedParams = paramString.split('|')
                # Replace markers
                for param in markedParams:
                    for m2 in Rmarker2.finditer(param):
                        param = param.replace(m2.group(),
                                              links[int(m2.group(1))])
                    params.append(param)
        return params

    def findTemplateParam(self, text, template, param):
        """
        Find the specified parameter of the specified template in text.
        Returns a tuple - (index where the parameter starts, index where the parameter ends) such that
        removing text[start:end] would result in no value specified for the specified template.
        Returns (-1,-1) if the template or the param of the template isn't found.
        """
        # First, find the template
        (name, start, end) = self.findTemplate(text, template)
        if start != -1:
            # Now find the parameter within that block
            params = self.parametersFromTemplate(text[start:end])
            for p in params:
                match = re.search(r'(\s*%s\s*)=' % param, p)
                if match:
                    intro = match.group(1)
                    length = len(p) - len(intro)
            match = re.search(intro, text[start:end])
            assert match, "Unable to find intro '%s' in template text" % intro
            return (start + match.end(), start + match.end() + length)
        return (-1,-1)

    def addBlockAtEnd(self, text, block):
        """
        Adds the new block of text at the very end of text, but before any categories.
        Returns the new text (text + block).
        """
        categoryR = re.compile(r'\[\[Category:.*', re.MULTILINE|re.DOTALL)
        match = categoryR.search(text)
        if match:
            wikipedia.output("Adding block before categories")
            # Page has categories, so add the Uses template before they start
            text = text[:match.start()] + block + u'\n' + text[match.start():]
        else:
            wikipedia.output("Adding block at end of page")
            # Page has no categories, so just add Uses template to the end
            text += block
        return text

    def matchCatToTemplate(self, text, categories, templatesWithParams, template, category):
        """
        Check that pages in category category use template template and vice versa.
        Adds or removes the category in the event of a mismatch.
        Note that template is used as a re to match against each template used on the page.
        """
        Rcat = re.compile(category_re % category)
        # Does the page use one of the recipe templates ?
        template_matches = False
        for (test_template, params) in templatesWithParams:
            if re.match(template, test_template):
                template_matches = True
        # Is it in the specified category ?
        cat_matches = self.catInCategories(category, categories)
        # Do the two agree ?
        if template_matches and (not cat_matches):
            wikipedia.output("Page uses a %s template but isn't in category %s" % (template, category))
            # This is easy - just append a category line
            text = self.appendCategory(text, category)
        elif (not template_matches) and cat_matches:
            wikipedia.output("Page does not use a %s template but is in category %s" % (template, category))
            # Remove the category
            text = Rcat.sub('', text)
        return text

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

    def findSectionOld(self, text):
        """
        Find a section in text, starting with a header,
        and ending with a header, template, or category.
        Returns a tuple - (section name (or u''), index where the section starts, index where the section ends)
        """
        # Does the page have a section header ?
        header = re.search(ur'==(.+)==', text)
        if header:
            section = header.expand(r'\1').strip()
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
            return (section, list_start, list_end)
        return (u'', -1, -1)

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
            if re.search(category_re % category, this_category.aslink()):
                return True
        return False

    def imageForItem(self, itemName):
        """
        Finds the image for the specified item.
        """
        # Retrieve the item page
        item = wikipedia.Page(wikipedia.getSite(), itemName)
        templatesWithParams = item.templatesWithParams()
        for (template, params) in templatesWithParams:
            if template.find(u'Item') != -1:
                for param in params:
                    match = re.search(r'image\s*=\s*\[\[\s*(.*?)\s*\]\]', param)
                    if match:
                        return match.expand(r'\1')
        return u''

    def replaceImageInTemplate(self, text, template, param, new_image):
        """
        Find the specified template in text, and replace the image in the specified parameter.
        Returns the new text
        """
        # TODO Can we use findTemplate() or findTemplateParam() ?
        # First find the specified template
        for match in Rtemplate.finditer(text):
            if template in match.expand(r'\g<name>'):
                # Then the specified parameter
                start = match.start()
                end = match.end()
                match = re.search(r'%s\s*=\s*\[\[\s*(.*?)\s*\]\]' % param, text[start:end])
                assert match, "Failed to find param %s in template %s" % (param, template)
                # Do the substitution
                end = start + match.end(1)
                start += match.start(1)
                text = text[:start] + new_image + text[end:]
                return text
        assert 0, "Failed to find template %s" % template

    def checkItemParams(self, source, drop_params):
        """
        Checks that the parameters for a drop match the item page.
        params is a dictionary of the drop's parameters.
        Also checks that the drop lists the source.
        """
        item = wikipedia.Page(wikipedia.getSite(), drop_params[u'name'])
        templatesWithParams = item.templatesWithParams()
        for (template, params) in templatesWithParams:
            #wikipedia.output("Template %s" % template)
            # TODO Clean this code up
            if (template.find(u'Item') != -1) or (template == u'Ingredient'):
                item_params = utils.paramsToDict(params)
                # Check the drop parameters we do have
                for key in drop_params.keys():
                    if (key == u'name'):
                        continue
                    elif (key == u'creator'):
                        continue
                    elif not dropParamsMatch(drop_params[key], item_params[key]):
                        # TODO Should be able to fix some of them at least...
                        wikipedia.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, drop_params[u'name'], item_params[key], drop_params[key]))
                # Then check for any that may be missing
                # TODO This is too strict - "for" parameter should only list Epic Research Items
                for key in [u'name', u'image', u'atk', u'def', u'type', u'for']:
                    if key not in drop_params and key in item_params:
                        wikipedia.output("Drop parameter %s not provided for %s, but should be %s" % (key, drop_params[u'name'], item_params[key]))
                if source not in item_params['from']:
                    wikipedia.output("Boss claims to drop %s, but is not listed on that page" % drop_params['name'])
            elif template.find(u'Lieutenant') != -1:
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
                        wikipedia.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, drop_params[u'name'], dp, ip))
                if source not in item_params['from']:
                    wikipedia.output("Boss claims to drop %s, but is not listed on that page" % drop_params['name'])
            elif (template != u'Job Link') and (template != u'For') and (template != u'Sic'):
                wikipedia.output("Ignoring template %s" % template)

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
        # Drop out early if not a boss page
        # TODO Is there a better test ?
        if not job_boss and not tl_boss:
            return text

        drop_params = [u'image', u'type', u'atk', u'def']

        # __NOWYSISYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check core category
        if job_boss == tl_boss:
            wikipedia.output("Boss isn't in exactly one category of Job Bosses and Tech Lab Bosses")

        # Check each drop
        for (template, params) in templatesWithParams:
            if template == u'Drop':
                drop_params = utils.paramsToDict(params)
                self.checkItemParams(name, drop_params)

        # Check Needs categories
        (dummy, start, end, level) = self.findSection(text, u'Completion Dialogue')
        length = len(text[start:end])
        if self.catInCategories(u'Needs Completion Dialogue', categories):
            if tl_boss:
                wikipedia.output("Tech Lab bosses should never be categorised Needs Completion Dialogue")
                text = self.removeCategory(text, u'Needs Completion Dialogue')
            elif (start != -1) and (length > 0):
                wikipedia.output("Non-empty completion dialogue section found despite Needs Completion Dialogue category")
                text = self.removeCategory(text, u'Needs Completion Dialogue')
        elif (start == -1) or (length == 0):
            # Section not present or empty
            if not tl_boss:
                text = self.appendCategory(text, u'Needs Completion Dialogue')

        (dummy, start, end, level) = self.findSection(text, u'Rewards')
        if self.catInCategories(u'Needs Rewards', categories):
            if start != -1:
                # There is a Rewards section
                # TODO Check for actual content - may just have sub-headers
                wikipedia.output("Non-empty Rewards section found despite Needs Rewards category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Rewards')

        (dummy, start, end, level) = self.findSection(text, u'Stages')
        if self.catInCategories(u'Needs Stages', categories):
            if start != -1:
                # There is a Stages section
                # TODO Check for actual content - may just have sub-headers
                wikipedia.output("Non-empty Stages section found despite Needs Stages category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Stages')

        (dummy, start, end, level) = self.findSection(text, u'Basic Information')
        if self.catInCategories(u'Needs Time Limit', categories):
            if start != -1:
                # There is a Basic Information section
                # TODO Check for the actual time limit line
                wikipedia.output("Non-empty Basic Information section found despite Needs Time Limit category")
        elif start == -1:
            # Section not present
            text = self.appendCategory(text, u'Needs Time Limit')

        return text

    def fixDistrict(self, name, text, categories, templatesWithParams):
        """
        Fixes a District page.
        Ensures that __NOWYSIWYG__ is present.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        # Drop out if it isn't a district page
        if not self.catInCategories(u'Districts', categories):
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check each template
        common_param_map = {u'name': u'Needs Information', #u'Needs Job Name',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'description': u'Needs Information', #u'Needs Job Description',
                            u'energy': u'Needs Information', #u'Needs Job Energy',
                            u'total_energy': u'Needs Information', #u'Needs Job Total Energy',
                            u'cash_min': u'Needs Information', #u'Needs Job Cash',
                            u'cash_max': u'Needs Information'} #u'Needs Job Cash'}
        job_param_map = {u'lieutenant': u'Needs Information', #u'Needs Job Lieutenant',
                         u'gear': u'Needs Information', #u'Needs Job Gear',
                         # Special code for XP below
                         u'xp': u'Needs Information', #u'Needs Job XP',
                         u'faction': u'Needs Information'} #u'Needs Job Faction'}
        xp_pair_param_map = {u'xp_min': u'Needs Information', #u'Needs Job XP',
                             u'xp_max': u'Needs Information'} #u'Needs Job XP'}
        challenge_param_map = dict(xp_pair_param_map.items() + [(u'rewards', u'Needs Information')]) #u'Needs Job Rewards'}
        missing_params = set()
        for template, params in templatesWithParams:
            if template == u'Job':
                missing_params |= missingParams(params, common_param_map.keys() + job_param_map.keys())
                if u'xp' in missing_params:
                    # xp_min and xp_max will do instead
                    missing_params.remove(u'xp')
                    missing_params |= missingParams(params, xp_pair_param_map.keys())
            elif template == u'Challenge Job':
                missing_params |= missingParams(params, common_param_map.keys() + challenge_param_map.keys())
        wikipedia.output("Set of missing job parameters is %s" % missing_params)
        # Ensure the Needs categories are correct
        text = self.fixNeedsCats(text, missing_params, categories, dict(common_param_map.items() + job_param_map.items() + challenge_param_map.items()))

        return text

    def fixTechLab(self, name, text, categories, templatesWithParams):
        """
        Fixes the Tech Lab page.
        Ensures that __NOWYSIWYG__ is present.
        Checks for mandatory template parameters or corresponding Needs category.
        """
        if name != u'Tech Lab':
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Find the start of the Historical section
        start, end = self.findSpecificSection(text, u'Historical Items')

        # Check each recipe
        recipe_param_map = {u'name': u'Needs Information', #u'Needs Item Name',
                            u'image': u'Needs Improvement', #u'Needs Image',
                            u'atk': u'Needs Stats',
                            u'def': u'Needs Stats',
                            u'time': u'Needs Build Time',
                            u'part_1': u'Needs Information', #u'Needs Ingredient',
                            u'part_2': u'Needs Information'} #u'Needs Ingredient'}
        old_recipe_map = {u'available' : u'Needs Information'}
        missing_params = set()
        for template, params in templatesWithParams:
            if template == u'Recipe':
                missing_params |= missingParams(params, recipe_param_map.keys())
                # Find this item on the page
                name = utils.paramFromParams(params, u'name')
                # Is it a historical recipe ?
                if text.find(name) > start:
                    missing_params |= missingParams(params, old_recipe_map.keys())
                # TODO Cross-reference against item page
        wikipedia.output("Set of missing recipe parameters is %s" % missing_params)
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

        skill_param_map = { u'level': u'Needs Information', #u'Needs Skill Level',
                           u'effect': u'Needs Information', #u'Needs Skill Effect',
                           u'cost': u'Needs Information', #u'Needs Skill Cost',
                           u'time': u'Needs Information'} #u'Needs Skill Time'}
        # Check each use of the Skill template
        missing_params = set()
        old_level = 0
        for template,params in templatesWithParams:
            if template == u'Skill':
                level = utils.paramFromParams(params, u'level')
                if level != None:
                    if level == old_level and level != 1:
                        wikipedia.output("copy-paste error for skill level %s ?" % level)
                    old_level = level
                missing_params |= missingParams(params, skill_param_map.keys())
        wikipedia.output("Set of missing skill parameters is %s" % missing_params)
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

        # TODO Check Safe House

        # Drop out early if not a property page
        # TODO Is there a better test ?
        if the_params == None:
            return text

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # Check mandatory parameters
        prop_param_map = {u'description': u'Needs Description',
                          u'cost': u'Needs Initial Cost',
                          u'time': u'Needs Build Time',
                          u'image': u'Needs Improvement', #u'Needs Image',
                          u'unlock': u'Needs Unlock Criterion'}
        if the_template == u'Upgrade Property':
            prop_param_map[u'power'] = u'Needs Power'
            prop_param_map[u'max'] = u'Needs Max Number'
        else:
            prop_param_map[u'income'] = u'Needs Income'
 
        text = self.fixNeedsCategories(text, the_params, categories, prop_param_map)

        return text

    def fixLieutenant(self, name, text, categories, templatesWithParams, refs):
        """
        If the page uses any of the templates 'Lieutenant Common', 'Lieutenant Uncommon',
        'Lieutenant Rare, or 'Lieutenant Epic':
        Ensures that __NOWYSIWYG__ is present.
        Checks that the page doesn't explictly list any categories that should be
        assigned by the template.
        """
        # Does the page use a lieutenant template ?
        the_params = None
        is_tech_lab_item = False
        for template,params in templatesWithParams:
            # Find the templates we're interested in
            if template == u'Lieutenant':
                wikipedia.output("Directly uses Lieutenant template")

            if template == u'Lab':
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
 
        text = self.fixNeedsCategories(text, the_params, categories, lt_param_map)

        # Do special checks for any Epic Research Items
        if is_tech_lab_item:
            text = self.fixTechLabItem(name, text, the_params, categories, ingredients)

        # Validate items parameter, if present
        items_param = utils.paramFromParams(the_params, u'items')
        # Check for any items that have a power that affects this Lt
        itemList = []
        for r in refs:
            for template,params in r.templatesWithParams():
                powerParam = utils.paramFromParams(params, u'power')
                if powerParam != None and name in powerParam:
                    powerText = "[[%s]] gives %s" % (r.titleWithoutNamespace(), powerParam)
                    itemList.append(powerText)
        if len(itemList) > 0:
            if items_param == None:
                # Create new items param from scratch
                itemsText = '|items='
                if len(itemList) > 1:
                    itemsText += u'<br\>\n*'
                itemsText += u'\n*'.join(itemList)
                text = text.replace(the_template, the_template + '\n' + itemsText, 1)
            else:
                # TODO check that it contains all the items it should
                pass
        elif items_param != None:
            wikipedia.output("Page claims item bonus of %s, but no items found that give bonusus" % items_param)

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
        is_tech_lab_item = False
        for template,params in templatesWithParams:
            # Find the templates we're interested in
            if template == u'Item':
                wikipedia.output("Directly uses Item template")

            if template == u'Lab':
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
                wikipedia.output("Explictly in implicit category %s" % cat)
                text = self.removeCategory(text, cat)

        # __NOWYSIWYG__
        text = self.prependNowysiwygIfNeeded(text)

        # If the item comes from somewhere special (other than tech lab), do cross-ref check
        # (Mystery) Gift Item template uses from with a different meaning
        if template != u'Gift Item' and template != u'Mystery Gift Item' and not is_tech_lab_item:
            from_param = utils.paramFromParams(the_params, u'from')
            if from_param != None:
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
        source_list = []
        for r in refs:
            for template,params in r.templatesWithParams():
                if template == u'Drop':
                    if utils.paramFromParams(params, u'name') == name:
                        source_list.append(r.titleWithoutNamespace())
        # Then, find the places listed as sources in this page
        # Remove any that match from the source list, leaving missing sources
        # Count the number of sources already in the list as we go
        src_count = 0
        iterator = Rlink.finditer(from_param)
        for m in iterator:
            src_count += 1
            src = m.group('page')
            if src in source_list:
                source_list.remove(src)
            else:
                # Note that this is not necessarily an error
                # many items can be obtained from places other than Bosses
                #TODO Should be able to validate Black Market, Crates, and Events
                wikipedia.output("Page lists %s as a source, but that page doesn't list it as a drop" % src)
        # Convert from single source to a list if necessary
        if len(source_list) > 0 and src_count == 1:
            text = text.replace(from_param, u'<br/>\n*' + from_param)
        # Add missing sources to the page
        for src in source_list:
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
            start = text.find(params)
            if start != -1:
                text = text[0:start] + u'|type=' + cat + text[start:]
            else:
                assert 0, "Failed to find params %s" % params
        else:
            # Check that the type is one we expect
            if oneCap(type_param) not in types:
                wikipedia.output("Unexpected type '%s'" % type_param)
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
            gift_page = wikipedia.Page(wikipedia.getSite(), u'Gift')
            iterator = Rgift.finditer(gift_page.get())
            for m in iterator:
                if m.group('item') == name:
                    if m.group('level') != from_param:
                        wikipedia.output("Minimum level mismatch - Gift page says %s, this page says %s" % (m.group('level'), from_param))
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
            faction_page = wikipedia.Page(wikipedia.getSite(), faction_param)
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
        Checks that either level or district is specified.
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
        district_param = utils.paramFromParams(params, u'district')
        if level_param == None:
            if district_param == None:
                wikipedia.output("Missing both level and district parameters")
                if not self.catInCategories(u'Needs Unlock Criterion', categories):
                    text = self.appendCategory(text, u'Needs Unlock Criterion')
        else:
            if district_param != None:
                wikipedia.output("Both level and district parameters are present")

        # Ensure that daily items are specified with parameter, not explicit category
        cat = u'Daily Rewards'
        if self.catInCategories(cat, categories):
            wikipedia.output("Explictly in implicit category %s" % cat)
            text = self.removeCategory(text, cat)
            # Add a daily parameter, with value yes
            # Note that this just finds the first instance of params...
            start = text.find(params)
            if start != -1:
                text = text[0:start] + u'|daily=yes' + text[start:]
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
                            u'image': u'Needs Improvement'} #u'Needs Image'}
 
        text = self.fixNeedsCategories(text, params, categories, battle_param_map)

        # Check rank parameter against Battle Rank page
        rank_param = utils.paramFromParams(params, u'rank')
        if rank_param == None:
            if not self.catInCategories(u'Needs Unlock Criterion', categories):
                text = self.appendCategory(text, u'Needs Unlock Criterion')
        else:
            rank_page = wikipedia.Page(wikipedia.getSite(), u'Battle Rank')
            templatesWithParams = rank_page.templatesWithParams()
            for t,p in templatesWithParams:
                if t == u'Battle Rank List':
                    rank = utils.paramFromParams(u'number',p)
                    item = utils.paramFromParams(u'reward',p)
                    if item == u'[[%s]]' % name and rank != rank_param:
                        wikipedia.output("Minimum battle rank mismatch - Battle Rank page says %s, this page says %s" % (rank, rank_param))

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
        no_desc = [u"Boss Frank's Cell Phone",
                   u"Boss Twins' Cell Phone",
                   u"Boss Victor's Cell Phone",
                   u"Corrupt Cop's Cell Phone",
                   u"Street Rival's Cell Phone"]
        # Check mandatory parameters
        ingr_param_map = {u'rarity': u'Needs Rarity',
                          u'image': u'Needs Improvement'} #u'Needs Image'}
        # Most ingredients have a description, too
        if not name in no_desc:
            ingr_param_map[u'description'] = u'Needs Description'
 
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

    def checkIngredient(self, name, i, lab_param, recipe_param):
        """
        Compare one ingredient listed on an item page with the corresponding one on the Tech Lab page.
        Check that the ingredient does drop where the page claims it does (and nowhere else).
        Check that the ingredient lists this item as something it is "for".
        """
        # Check that the ingredients match
        # Lab ingredients are links, and often say where they drop
        # Recipe ingredients are just the item name
        # TODO This doesn't work when multiple sources are listed e.g. Apache: Gun
        r = Ringredient.search(lab_param)
        if r:
            item = r.group('ingredient')
            source = r.group('source')
        else:
            r = Rlink.search(lab_param)
            item = r.group('page')
            source = None
        if item != recipe_param:
            wikipedia.output("part_%d parameter mismatch - %s in page, %s on Tech Lab page" % (i, item, recipe_param))
        #wikipedia.output("%s from %s." % (item, source))

        # Check that the part lists this item as "for"
        page = wikipedia.Page(wikipedia.getSite(), item)
        templatesWithParams = page.templatesWithParams()
        for template,params in templatesWithParams:
            for_param = utils.paramFromParams(params, u'for')
            if for_param != None:
                if name not in for_param:
                    wikipedia.output("%s is an ingredient, but doesn't list this page as somethign it is for" % item)

        # Check drop location for the part
        # TODO Some of this should be in fixBoss, where we can fix it
        if source != None:
            found = False
            page = wikipedia.Page(wikipedia.getSite(), source)
            templatesWithParams = page.templatesWithParams()
            for template,params in templatesWithParams:
                if template == u'Drop':
                    name_param = utils.paramFromParams(params, u'name')
                    if name_param == item:
                        for_param = utils.paramFromParams(params, u'for')
                        found = True
                        break
            if not found:
                wikipedia.output("Ingredient %s is listed as dropping from %s, but that page disagrees" % (item, source))
            elif for_param == None:
                wikipedia.output("Ingredient %s drops from %s, but that page doesn't say that it makes %s" % (item, source, name))
            elif for_param != name:
                wikipedia.output("Ingredient %s drops from %s, but that page says that it makes %s" % (item, source, for_param))

    def fixTechLabItem(self, name, text, params, categories, lab_params):
        """
        Check that it is listed as made in the same way on its page and the Tech Lab page.
        Check that the parts drop where its page says they drop.
        """
        # Find the recipe on the Tech Lab page
        found = False
        tl_page = wikipedia.Page(wikipedia.getSite(), u'Tech Lab')
        templatesWithParams = tl_page.templatesWithParams()
        for template,params in templatesWithParams:
            if template == u'Recipe':
                recipe_params = utils.paramsToDict(params)
                if recipe_params[u'name'] == name:
                    # This is the one we're interested in
                    found = True
                    break
        if not found:
            wikipedia.output("Tech Lab item not on the Tech Lab page")

        # Now we can cross-check between the two
        # Lab template has time, num_parts, part_1..part_n
        # Recipe template has time, atk, def, description, image, part_1..part_n
        # Note that recipe description may differ from item description
        img_param = utils.paramFromParams(params, u'image')
        if img_param != None and img_param != recipe_params[u'image']:
            wikipedia.output("Image parameter mismatch - %s in page, %s on Tech Lab page" % (img_param, recipe_params[u'image']))
        time_param = utils.paramFromParams(lab_params, u'time')
        if time_param == None:
            if not self.catInCategories(u'Needs Build Time', categories):
                text = self.appendCategory(text, u'Needs Build Time')
            if recipe_params[u'time'] != None:
                # Add a time parameter, with appropriate value
                # Note that this just finds the first instance of params...
                start = text.find(lab_params)
                if start != -1:
                    text = text[0:start] + u'|time=' + recipe_params[u'time'] + text[start:]
                else:
                    assert 0, "Failed to find params %s" % lab_params
        else:
            if time_param != recipe_params[u'time']:
                wikipedia.output("Time parameter mismatch - %s in page, %s on Tech Lab page" % (time_param, recipe_params[u'time']))
        # Compare atk
        atk_param = utils.paramFromParams(params, u'atk')
        if atk_param != None and atk_param != recipe_params[u'atk']:
            wikipedia.output("Attack parameter mismatch - %s in page, %s on Tech Lab page" % (atk_param, recipe_params[u'atk']))
        # Compare def
        def_param = utils.paramFromParams(params, u'def')
        if def_param != None and def_param != recipe_params[u'def']:
            wikipedia.output("Defence parameter mismatch - %s in page, %s on Tech Lab page" % (def_param, recipe_params[u'atk']))
        # Check that num_parts is right
        num_parts = utils.paramFromParams(lab_params, u'num_parts')
        for i in range(1,7):
            part_param = utils.paramFromParams(lab_params, u'part_%d' % i)
            if i <= int(num_parts):
                # Check part_n
                if part_param == None:
                    wikipedia.output("num_parts is %s, but part_%d param is missing" % (num_parts, i))
                else:
                    recipe_param = recipe_params[u'part_%d' % i]
                    self.checkIngredient(name, i, part_param, recipe_param)
            elif i > int(num_parts) and part_param != None:
                wikipedia.output("num_parts is %s, but part_%d param is present" % (num_parts, i))

        return text

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))
        # Find all the sub-categories of Needs Information
        cat = catlib.Category(wikipedia.getSite(), u'Category:Needs Information')
        self.specificNeeds = set(c.titleWithoutNamespace() for c in cat.subcategories(recurse=True))

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            xrToolkit = XrefToolkit(page.site(), self.specificNeeds, debug = True)
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
                    choice = wikipedia.inputChoice(u'Do you want to accept these changes?',  ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                    if choice == 'a':
                        self.acceptall = True
                if self.acceptall or choice == 'y':
                    page.put(changedText)
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
        bot = XrefBot(preloadingGen)
        bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

