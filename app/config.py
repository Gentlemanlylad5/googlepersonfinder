#!/usr/bin/python2.5
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Storage for configuration settings.  Settings can be global or specific
to a subdomain, and their values can be of any JSON-encodable type."""

from google.appengine.ext import db
from google.appengine.api import memcache

import UserDict, model, random, simplejson


class ConfigEntry(db.Model):
    """An application configuration setting, identified by its key_name."""
    value = db.TextProperty(default='')


def get(name, default=None):
    """Gets a configuration setting."""
    config = ConfigEntry.get_by_key_name(name)
    if config:
        return simplejson.loads(config.value)
    return default


def get_or_generate(name):
    """Gets a configuration setting, or sets it to a random 32-byte value
    encoded in hexadecimal if it doesn't exist.  Use this function when you
    need a persistent cryptographic secret unique to the application."""
    random_hex = ''.join('%02x' % random.randrange(256) for i in range(32))
    ConfigEntry.get_or_insert(key_name=name, value=simplejson.dumps(random_hex))
    return get(name)


def set(**kwargs):
    """Sets configuration settings."""
    db.put(ConfigEntry(key_name=name, value=simplejson.dumps(value))
           for name, value in kwargs.items())


def get_for_subdomain(subdomain, name, default=None):
    """Gets a configuration setting for a particular subdomain.  Looks for a
    setting specific to the subdomain, then falls back to a global setting."""
    value = get(subdomain + ':' + name)
    if value is not None:
        return value
    return get(name, default)


def set_for_subdomain(subdomain, **kwargs):
    """Sets configuration settings for a particular subdomain.  When used
    with get_for_subdomain, has the effect of overriding global settings."""
    
    # Invalidating memcache entry
    if not memcache.delete(subdomain): 
        logging.error("Unable to invalidate memcache entry. Might output stale data for sometime")
        
    subdomain = str(subdomain)  # need an 8-bit string, not Unicode
    set(**dict((subdomain + ':' + key, value) for key, value in kwargs.items()))

def get_for_subdomain_with_memcache(subdomain, name, default=None):
    """ Gets the configuration setting for a subdomain. Looks at 
        memcache first. If entry not available, get from database.
        Memcache entry uses the subdomain name as the key """
    
    config_data = memcache.get(subdomain)
    
    if config_data is None:
        # Fetching from database; adding to memcache
        config_entries = model.filter_by_prefix( ConfigEntry.all(), subdomain + ':')
        config_data = dict([(e.key().name().split(':', 1)[1], e) for e in config_entries])  
        memcache.add(subdomain, config_data, 600)
        
    config_element = config_data.get(name, None)
    
    if config_element is not None:
        return simplejson.loads(config_element.value)
    else :
        # Config is not available for key - returning default value
        return default

def get_for_global(name, default=None):
    """ Retrieve global configurations from memcache, if available. Otherwise
        get from database. Memcache entry uses the configuration's name as the key """
    
    config_element = memcache.get(name)
    
    if config_element is None:
        config_element = ConfigEntry.get_by_key_name(name)
        memcache.add(name, config_element, 600)
    
    if config_element is not None:
        return simplejson.loads(config_element.value)
    else :
        return default
    


class Configuration(UserDict.DictMixin):
    def __init__(self, subdomain):
        self.subdomain = subdomain

    def __nonzero__(self):
        return True

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, name):
        """Gets a configuration setting for this subdomain.  Looks for a
        subdomain-specific setting, then falls back to a global setting."""
#        value = get_for_subdomain_with_memcache(self.subdomain, name) 
#        if value is None:
#           return get_for_global(name)
#        return value

        return get_for_subdomain(self.subdomain, name)
        
    def keys(self):
        entries = model.filter_by_prefix(
            ConfigEntry.all(), self.subdomain + ':')
        return [entry.key().name().split(':', 1)[1] for entry in entries]
