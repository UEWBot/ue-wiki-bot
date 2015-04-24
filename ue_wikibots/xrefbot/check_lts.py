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

from utils import param_from_params

c = pywikibot.Category(pywikibot.Site(), u'Category:Areas')

for d in c.articles():
    for t,p in d.templatesWithParams():
        t_name = t.title(withNamespace=False)
        if t_name == u'Job':
            lt = param_from_params(p, u'lieutenant')
            f = param_from_params(p, u'faction')
            if lt != None and f != None:
                pg = pywikibot.Page(pywikibot.Site(), lt)
                for t1,p1 in pg.templatesWithParams():
                    t1_name = t1.title(withNamespace=False)
                    if u'Lieutenant' in t1_name:
                        fact = param_from_params(p1, u'faction')
                        job = param_from_params(p, u'name')
                        if f != fact and f != u'None':
                            print "Job %s in area %s has lt %s and faction %s. Lt has faction %s" % (job, d.title(withNamespace=False), lt, f, fact)
