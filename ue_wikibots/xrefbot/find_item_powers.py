# Copyright (C) 2014 Chris Brand
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

c = pywikibot.Category(pywikibot.Site(), u'Category:Special Items')

for d in c.articles():
 for t,p in d.templatesWithParams():
  t_name = t.title(withNamespace=False)
  if t_name == u'Special Item':
   power = paramFromParams(p,u'power')
   if power != None:
    print "%s: %s" % (d.title(withNamespace=False), power)
