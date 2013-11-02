#! /usr/bin/python

"""
Script to fix up categories and cross-references between pages on UE Wiki.
"""

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia, pagegenerators, catlib
import re, difflib

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

# Separate the name and value for a template parameter
Rparam = re.compile(ur'\s*(?P<name>\S+)\s*=\s*(?P<value>.*)', re.DOTALL)

# Headers
# This doesn't match level 1 headers, but they're rare...
Rheader = re.compile(ur'(={2,})\s*(?P<title>[^=]+)\s*\1')

# List items on gift page
Rgift = re.compile(ur'<li value=(?P<level>.*)>\[\[(?P<item>.*)\]\]</li>')

# List items on faction page
Rfaction = re.compile(ur'\*\s*(?P<points>\S*)>\s*points - \[\[(?P<item>.*)\]\]')

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

def paramFromParams(params, param):
    """
    Returns the value for 'param' in 'params', or None if it isn't present.
    """
    for p in params:
        m = Rparam.match(p)
        if m.group('name') == param:
            val = m.group('value')
            # People sometimes provide the parameters, even though we don't know the value
            if val != u'' and val != u'?':
                return val
    return None

class XrefToolkit:
    def __init__(self, site, debug = False):
        self.site = site
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
                item_params = {}
                for param in params:
                    m = Rparam.match(param)
                    item_params[m.group('name')] = m.group('value')
                for key in drop_params.keys():
                    if (key == u'name'):
                        continue
                    elif (key == u'creator'):
                        continue
                    elif not dropParamsMatch(drop_params[key], item_params[key]):
                        wikipedia.output("Drop parameter mismatch for %s parameter of item %s (%s vs %s)" % (key, drop_params[u'name'], item_params[key], drop_params[key]))
                if source not in item_params['from']:
                    wikipedia.output("Boss claims to drop %s, but is not listed on that page" % drop_params['name'])
            elif template.find(u'Lieutenant') != -1:
                item_params = {}
                for param in params:
                    m = Rparam.match(param)
                    item_params[m.group('name')] = m.group('value')
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

    def fixNeedsCategory(self, text, params, categories, cat, param):
        """
        Adds or removes a "Needs" category based on whether the paameter 'param'
        is present in the text 'params' and whether the category 'cat' is
        present in the list 'categories'.
        """
        val = paramFromParams(params, param)
        present = (val != None)
        if self.catInCategories(cat, categories):
            if present:
                wikipedia.output("In %s category, but %s specified as %s." % (cat, param, val));
                text = self.removeCategory(text, cat)
        else:
            if not present:
                wikipedia.output("Not in %s category, but %s param not specified." % (cat, param));
                text = self.appendCategory(text, cat)
        return text

    def fixNeedsStats(self, text, params, categories):
        """
        Similar to fixNeedsCategory(), except checks for atk and def parameters,
        and uses Needs Stats category.
        """
        cat = u'Needs Stats'
        attack = paramFromParams(params, u'atk')
        defence = paramFromParams(params, u'def')
        present = (attack != None) and (defence != None)
        if self.catInCategories(cat, categories):
            if present:
                wikipedia.output("In %s category, but atk=%s and def=%s." % (cat, attack, defence));
                text = self.removeCategory(text, cat)
        else:
            if not present:
                if attack == None:
                    wikipedia.output("Not in %s category, but atk param not specified." % cat);
                if defence == None:
                    wikipedia.output("Not in %s category, but def param not specified." % cat);
                text = self.appendCategory(text, cat)
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
                drop_params = {}
                for param in params:
                    m = Rparam.match(param)
                    drop_params[m.group('name')] = m.group('value')
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
        # All these categories should be added by the template
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
                               u'Needs Type']

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

        # TODO Look at all these special cases, and consider moving some checks
        # into the type-specific item fixing methods, even if there is some
        # duplication (can put the code in a separate method, called in several places)

        # from parameter
        if the_template == u'Gift Item' or the_template == u'Mystery Gift Item':
            # from has a different meaning for gifts
            # but we always know where they come from
            from_present = True
        elif the_template == u'Basic Item' or the_template == u'Battle Rank Item':
            # Basic items and Battle Rank Items are always from the shop
            from_present = True
        elif the_template == u'Faction Item':
            # These are awarded when you accumulate enough Affiliation Points
            from_present = True
        elif is_tech_lab_item:
            # The "from={{Lab ...}} confuses the parser. We know "from" is there
            from_present = True
        else:
            from_param = paramFromParams(the_params, u'from')
            from_present = (from_param != None)
            if from_present:
                # TODO Actually check the parameter content
                wikipedia.output("From %s" % from_param)
                wikipedia.output(list(refs))

        # Check Needs categories
        if self.catInCategories(u'Needs Source', categories):
            if from_present:
                wikipedia.output("In Needs Source category, but from parameter is present")
                text = self.removeCategory(text, u'Needs Source')
        else:
            if not from_present:
                text = self.appendCategory(text, u'Needs Source')

        # Ingredients and Mystery Gift Items never have costs
        if the_template != u'Ingredient' and the_template != u'Mystery Gift Item':
            text = self.fixNeedsCategory(text, the_params, categories, u'Needs Cost', u'cost')
        # Some ingredients (cellphones) don't have descriptions
        # TODO check the ones that should
        # Mystery Gift Items never have costs
        if the_template != u'Ingredient' and the_template != u'Mystery Gift Item':
            text = self.fixNeedsCategory(text, the_params, categories, u'Needs Description', u'description')
        # Mystery Gift Items don't have rarities, either
        if the_template != u'Mystery Gift Item':
            text = self.fixNeedsCategory(text, the_params, categories, u'Needs Rarity', u'rarity')

        # Do more detailed checks for specific sub-types
        if the_template == u'Gift Item':
            text = self.fixGiftItem(name, text, the_params, categories)
        elif the_template == u'Mystery Gift Item':
            text = self.fixMysteryGiftItem(name, text, the_params, categories)
        elif the_template == u'Faction Item':
            text = self.fixFactionItem(name, text, the_params, categories)
        elif the_template == u'Special Item':
            text = self.fixSpecialItem(text)
        elif the_template == u'Basic Item':
            text = self.fixBasicItem(text, the_params, categories)
        elif the_template == u'Battle Rank Item':
            text = self.fixBattleItem(name, text, the_params, categories)
        elif the_template == u'Ingredient':
            text = self.fixIngredient(text)

        if is_tech_lab_item:
            text = self.fixTechLabItem(text)

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
                 u'Heavy Weapons']
        cat = u'Needs Type'
        if self.catInCategories(cat, categories):
            wikipedia.output("Explictly in implicit category %s" % cat)
            text = self.removeCategory(text, cat)
        type_param = paramFromParams(params, u'type')
        if type_param == None:
            # TODO Add "|from=Needs Type"
            pass
        else:
            # Check that the type is one we expect
            if type_param not in types:
                wikipedia.output("Unexpected type '%s'" % type_param)
                # TODO Change it to Needs Type

        return text

    def fixGiftLevel(self, name, text, params, categories):
        """
        Checks the from parameter.
        Adds or removes Needs Minimum Level category.
        Warns if the from parameter differs from what the Gift page says.
        """
        from_param = paramFromParams(params, u'from')
        if from_param == None:
            text = self.appendCategory(u'Needs Minimum Level')
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
        # Check all the parameters
        text = self.fixNeedsCategory(text, params, categories, u'Needs Description', u'description')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Image', u'image')
        text = self.fixNeedsStats(text, params, categories)
        text = self.fixNeedsCategory(text, params, categories, u'Needs Cost', u'cost')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Rarity', u'rarity')

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
        # Check all the parameters
        text = self.fixNeedsCategory(text, params, categories, u'Needs Image', u'image')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Information', u'item_1')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Information', u'item_2')

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
        # Check simple parameters
        text = self.fixNeedsCategory(text, params, categories, u'Needs Description', u'description')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Image', u'image')
        text = self.fixNeedsStats(text, params, categories)
        text = self.fixNeedsCategory(text, params, categories, u'Needs Cost', u'cost')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Rarity', u'rarity')

        # Check points against corresponding faction page
        faction_param = paramFromParams(params, u'faction')
        points_param = paramFromParams(params, u'points')
        if faction_param == None or points_param == None:
            text = self.appendCategory(u'Needs Information')
        else:
            faction_page = wikipedia.Page(wikipedia.getSite(), faction_param)
            iterator = Rfaction.finditer(faction_page.get())
            for m in iterator:
                if m.group('item') == name:
                    if points_param != m.group('points'):
                        wikipedia.output("Faction points mismatch - %s page says %s, this page says %s" % (faction_param, m.group('points'), points_param))
                        # TODO Can probably fix item page here

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixSpecialItem(self, text):
        # TODO Implement
        return text

    def fixBasicItem(self, text, params, categories):
        """
        Ensures that basic items have description, image, atk, def, cost, rarity, quote
        and time params or appopriate "Needs" category.
        Checks that either level or district is specified.
        Checks that it not explcitly in Daily Rewards category.
        Assumes that the page uses the Basic Item template.
        """
        # Check simple parameters
        text = self.fixNeedsCategory(text, params, categories, u'Needs Description', u'description')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Image', u'image')
        text = self.fixNeedsStats(text, params, categories)
        text = self.fixNeedsCategory(text, params, categories, u'Needs Cost', u'cost')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Rarity', u'rarity')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Quote', u'quote')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Build Time', u'time')

        # Check that we have either level or district but not both
        level_param = paramFromParams(params, u'level')
        district_param = paramFromParams(params, u'district')
        if level_param == None:
            if district_param == None:
                wikipedia.output("Missing both level and district parameters")
                text = self.appendCategory(text, u'Needs Information')
        else:
            if district_param != None:
                wikipedia.output("Both level and district parameters are present")

        # Ensure that daily items are specified with parameter, not explicit category
        cat = u'Daily Rewards'
        if self.catInCategories(cat, categories):
            wikipedia.output("Explictly in implicit category %s" % cat)
            text = self.removeCategory(text, cat)
            # TODO Add "daily=yes" to Basic Item parameters

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixBattleItem(self, name, text, params, categories):
        """
        Ensures that battle rank items have description, image, atk, def, cost, rarity params
        or appopriate "Needs" category.
        Checks that the battle rank is specified, and that it matches what the Battle Rank page says.
        Assumes that the page uses the Battle Rank Item template.
        """
        # Check simple parameters
        text = self.fixNeedsCategory(text, params, categories, u'Needs Description', u'description')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Image', u'image')
        text = self.fixNeedsStats(text, params, categories)
        text = self.fixNeedsCategory(text, params, categories, u'Needs Cost', u'cost')
        text = self.fixNeedsCategory(text, params, categories, u'Needs Rarity', u'rarity')

        # Check rank parameter against Battle Rank page
        rank_param = paramFromParams(params, u'rank')
        if rank_param == None:
            text = self.appendCategory(u'Needs Information')
        else:
            rank_page = wikipedia.Page(wikipedia.getSite(), u'Battle Rank')
            templatesWithParams = rank_page.templatesWithParams()
            for t,p in templatesWithParams:
                if t == u'Battle Rank List':
                    rank = paramFromParams(u'number',p)
                    item = paramFromParams(u'reward',p)
                    if item == u'[[%s]]' % name and rank != rank_param:
                        wikipedia.output("Minimum battle rank mismatch - Battle Rank page says %s, this page says %s" % (rank, rank_param))

        # Check type param
        text = self.fixItemType(text, params, categories)

        return text

    def fixIngredient(self, text):
        # TODO Implement
        return text

    def fixTechLabItem(self, text):
        # TODO Implement
        return text

class XrefBot:
    def __init__(self, generator, acceptall = False):
        self.generator = generator
        self.acceptall = acceptall
        # Load default summary message.
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), msg_standalone))

    def treat(self, page):
        try:
            # Show the title of the page we're working on.
            # Highlight the title in purple.
            wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" % page.title())
            xrToolkit = XrefToolkit(page.site(), debug = True)
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

