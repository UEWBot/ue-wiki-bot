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

from __future__ import absolute_import
from __future__ import print_function
import sys
import os
#import operator
sys.path.append(os.environ['HOME'] + '/ue/ue_wikibots/core')

import pywikibot

from utils import param_from_params

NULLS = ['.',
         '',
         'No Description.',
         'No description.',
         'No description',
         'No Description'
        ]

CAT = '[[Category:No In-game Description]]'
summary = 'Robot: Added category No In-game Description'

def fix_category(cat):
    c = pywikibot.Category(pywikibot.Site(), cat)

    for d in c.articles():
        for t,p in d.templatesWithParams():
            t_name = t.title(withNamespace=False)
            #if 'Lieutenant' in t_name:
            desc = param_from_params(p, u'description', verbatim=True)
            if desc != None:
                # We have a description, but does it indicate that there isn't one?
                if desc in NULLS:
                    print("Description for %s is '%s'" % (d.title(), desc))
                    # Check if the category is already present
                    text = d.get()
                    if CAT not in text:
                        print("Appending category")
                        text += CAT
                        d.put(text, summary)

fix_category(u'Category:Lieutenants')
fix_category(u'Category:Special Items')

