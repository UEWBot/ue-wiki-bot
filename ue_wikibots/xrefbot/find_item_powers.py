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

import sys
import os
import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot
import re

from utils import param_from_params

c = pywikibot.Category(pywikibot.Site(), u'Category:Special Items')

for d in c.articles():
    for t,p in d.templatesWithParams():
        t_name = t.title(withNamespace=False)
        if t_name == u'Special Item':
            power = param_from_params(p, u'power')
            if power is not None:
                print "%s: %s" % (d.title(), power)
