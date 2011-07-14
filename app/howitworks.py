from google.appengine.api import datastore_errors

from model import *
from utils import *


class Howitworks(Handler):
    subdomain_required = False
    
        
    def get(self):
        try:
            text=get_page_text("howItWorks", self.env.lang)
        except datastore_errors.NeedIndexError:
            text=get_page_text("howItWorks",'en')
        
        return self.render('templates/howitworks.html',
                           text=text)

if __name__ == '__main__':
    run(('/howitworks', Howitworks))
