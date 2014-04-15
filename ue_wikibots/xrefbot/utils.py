#! /usr/bin/python

"""
Utility functions for UEW wikibots
"""

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

