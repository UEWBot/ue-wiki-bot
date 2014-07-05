#! /usr/bin/python

"""
Utility functions for UEW wikibots
"""

import sys, os
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/pywikipedia')

import wikipedia
import re

# Separate the name and value for a template parameter
Rparam = re.compile(ur'\s*(?P<name>\S+)\s*=\s*(?P<value>.*)', re.DOTALL)

def escapeStr(string):
    """
    Returns text with any |, +, (, ), [, or ] characters preceded with \ characters.
    Useful if you want to include it in a regex.
    """
    string = re.sub(ur'\|', u'\|', string)
    string = re.sub(ur'\(', u'\(', string)
    string = re.sub(ur'\)', u'\)', string)
    string = re.sub(ur'\[', u'\[', string)
    string = re.sub(ur'\+', u'\+', string)
    return re.sub(ur'\]', u'\]', string)

def paramFromParams(params, param):
    """
    Returns the value for 'param' in 'params', or None if it isn't present.
    """
    for p in params:
        m = Rparam.match(p)
        if m != None and m.group('name') == param:
            val = m.group('value')
            # People sometimes provide the parameters, even though we don't know the value
            if val != u'' and val != u'?':
                return val
    return None

def paramsToDict(params):
    """
    Takes the list of parameters to a template and returns them as a dict.
    """
    result = {}
    for param in params:
        m = Rparam.match(param)
        if m != None:
            result[m.group('name')] = m.group('value')
    return result

# TODO It seems possible to have a generic cache class, with these as sub-classes
class ImageMap:
    imgRe = re.compile(ur'\|W*image\W*=\W*(?P<image>.*)')

    def __init__(self):
        # Populate image_map
        self.mapping = {}

    def image_for(self, name):
        """
        Returns the image for the specified item, property, or ingredient.
        Caches results for speed.
        """
        if name not in self.mapping:
            pg = wikipedia.Page(wikipedia.getSite(), name)
            # Retrieve the text of the specified page
            text = pg.get()
            # Extract the image parameter
            m = self.imgRe.search(text)
            if m != None:
                self.mapping[name] = m.group('image')
        return self.mapping[name]

class FactionLtRefs:
    def __init__(self):
        self.mapping = {}

    def refs_for(self, faction):
        """
        Returns a list of pages that reference the category page for lts
        in the specified faction.
        Caches the result, and returns from the cache in preference.
        """
        try:
            return self.mapping[faction]
        except KeyError:
            pass
        factionPage = wikipedia.Page(wikipedia.getSite(), u'Category:%s Lieutenants' % faction)
        refs = list(factionPage.getReferences())
        self.mapping[faction] = refs
        return refs
