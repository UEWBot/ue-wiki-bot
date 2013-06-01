# -*- coding: utf-8 -*-
import wikia_family

class Family(wikia_family.Family):
    def __init__(self):
        wikia_family.Family.__init__(self)
        self.name = u'uew'
        self.langs = {'en': u'underworld-empire.wikia.com'}

    def path(self, code):
        return '/index.php'
       
    def hostname(self, code):
        return self.langs[code]

