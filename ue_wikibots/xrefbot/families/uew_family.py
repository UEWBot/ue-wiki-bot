# -*- coding: utf-8 -*-
import wikia_family

class Family(wikia_family.Family):
    def __init__(self):
        wikia_family.Family.__init__(self)
        self.name = u'uew'
        self.langs = {'en': u'underworld-empire.wikia.com'}
        self.namespaces[4] = { '_default': 'Underworld Empire Wiki', }
        self.namespaces[5] = { '_default': 'Underworld Empire Wiki talk', }
        del(self.namespaces[100]['_default'])
        del(self.namespaces[101]['_default'])
        self.namespaces[110] = { '_default': u'Forum', }
        self.namespaces[111] = { '_default': u'Forum talk', }
        del(self.namespaces[112]['_default'])
        del(self.namespaces[113]['_default'])
        self.namespaces[500] = { '_default': u'User blog', }
        self.namespaces[501] = { '_default': u'User blog comment', }
        self.namespaces[502] = { '_default': u'Blog', }
        self.namespaces[503] = { '_default': u'Blog talk', }
        self.namespaces[700] = { '_default': u'Top 10 list', }
        self.namespaces[701] = { '_default': u'Top 10 list talk', }
        self.namespaces[828] = { '_default': u'Module', }
        self.namespaces[829] = { '_default': u'Module talk', }
        self.namespaces[1200] = { '_default': u'Message Wall', }
        self.namespaces[1201] = { '_default': u'Thread', }
        self.namespaces[1202] = { '_default': u'Message Wall Greeting', }

    def path(self, code):
        return '/index.php'
       
    def version(self, code):
        return "1.19.6"

    def hostname(self, code):
        return self.langs[code]

