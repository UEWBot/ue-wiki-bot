# -*- coding: utf-8 -*-
"""
This family file was auto-generated by $Id: 185033971c163ea46b2b1904773b8c407069a4d0 $
Configuration parameters:
  url = http://underworld-empire.wikia.com/
  name = uew

Please do not commit this to the Git repository!
"""

from pywikibot import family

class Family(family.Family):
    def __init__(self):
        family.Family.__init__(self)
        self.name = 'uew'
        self.langs = {
            'en': 'underworld-empire.wikia.com',
        }



    def scriptpath(self, code):
        return {
            'en': '',
        }[code]

    def version(self, code):
        return {
            'en': u'1.19.20',
        }[code]
