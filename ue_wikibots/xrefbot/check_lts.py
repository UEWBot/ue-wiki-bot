#! /usr/bin/python

import sys, os, operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core/pywikibot')
import pywikibot
import re

Rparam = re.compile(ur'\s*(?P<name>\S+)\s*=\s*(?P<value>.*)', re.DOTALL)

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

c = pywikibot.Category(pywikibot.Site(), u'Category:Areas')

for d in c.articles():
 for t,p in d.templatesWithParams():
  t_name = t.title(withNamespace=False)
  if t_name == u'Job':
   lt = paramFromParams(p,u'lieutenant')
   f = paramFromParams(p,u'faction')
   if lt != None and f != None:
    pg = pywikibot.Page(pywikibot.Site(), lt)
    for t1,p1 in pg.templatesWithParams():
     t1_name = t1.title(withNamespace=False)
     if u'Lieutenant' in t1_name:
      fact = paramFromParams(p1,u'faction')
      job = paramFromParams(p,u'name')
      if f != fact and f != u'None':
       print "Job %s in area %s has lt %s and faction %s. Lt has faction %s" % (job, d.title(withNamespace=False), lt, f, fact)
