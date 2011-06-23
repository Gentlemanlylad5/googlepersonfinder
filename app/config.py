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
import UserDict, model, random, simplejson
import logging
import datetime
import utils
from datetime import timedelta

config_cache = {}
config_cache_expiry_time = {} 
config_cache_miss_count=0
config_cache_hit_count=0
config_cache_evict_count=0
config_cache_items_count=0

def config_cache_flush():
    config_cache.clear()
    config_cache_expiry_time.clear()
    config_cache_items_count=0

    
def config_cache_delete(key):
    """Deletes the entry with given key from config_cache """
    global config_cache_items_count
    if key in config_cache:
        config_cache_expiry_time.pop(key)
        config_cache.pop(key)
        config_cache_items_count = config_cache_items_count - 1 

def config_cache_add(key, value, time_to_live_in_seconds):
    """ Adds the key/value pair to cache and updates the expiry time.
        If key already exists, its value and expiry are updated """
    global config_cache_items_count        
    config_cache[key] = value
    config_cache_expiry_time[key] = utils.get_utcnow() + timedelta(seconds=time_to_live_in_seconds)
    config_cache_items_count = config_cache_items_count + 1

def config_cache_retrieve(key):
    """ Gets the value corresponding to the key from cache. If cache entry
        has expired, it is deleted from the cache and None is returned.
        If the cache entry for that key does not exist, it returns a string
        'key-not-present' instead of python object None. This is because 
        some attributes could actually have the value None which has to be
        differentiated from a non-existant key. """
    global config_cache_hit_count
    global config_cache_miss_count
    global config_cache_items_count
    global config_cache_evict_count
    
    value = config_cache.get(key, None)
    if value is None :
        config_cache_miss_count = config_cache_miss_count+1
        return None
    
    now = utils.get_utcnow()
    if ( config_cache_expiry_time.get(key,0) > now) :
        config_cache_hit_count = config_cache_hit_count+1
        return value
    else:
        # Stale cache entry. Evicting from cache
        config_cache_delete(key)
        config_cache_evict_count = config_cache_evict_count + 1
        config_cache_miss_count = config_cache_miss_count + 1
        return None


def config_cache_stats():
    global config_cache_hit_count
    global config_cache_miss_count
    global config_cache_items_count
    
    print "Hit Count - " + str(config_cache_hit_count)
    print "Miss Count - " + str(config_cache_miss_count)
    print "Items Count - " + str(config_cache_items_count)
    print "Eviction Count - " + str(config_cache_evict_count)
    
        
class ConfigEntry(db.Model):
    """An application configuration setting, identified by its key_name."""
    value = db.TextProperty(default='')


def get_config_from_cache(subdomain, name):
    config_dict = config_cache_retrieve(subdomain)
    if config_dict is None:
        # Cache miss
        entries = model.filter_by_prefix( ConfigEntry.all(), subdomain + ':')
        if entries is None:
            return None
        logging.debug("Adding Subdomain `" + str(subdomain) + "` to config_cache")
        config_dict = dict([(e.key().name().split(':', 1)[1], e.value) for e in entries])  
        config_cache_add(subdomain, config_dict, 600)

    element = config_dict.get(name)
    if element is None:
        return None
    else:
        return simplejson.loads(element)
        

def get(name, default=None):
    """Gets a configuration setting."""
#    config = ConfigEntry.get_by_key_name(name)
#    if config:
#        return simplejson.loads(config.value)
#    return default
    config = get_config_from_cache('*', name)
    if config is not None:
        return config
    return default
        
def set(subdomain=None, **kwargs):
    """Sets configuration settings."""
    if subdomain is None:
        subdomain = '*'
    db.put(ConfigEntry(key_name=subdomain +':'+ name, value=simplejson.dumps(value))
           for name, value in kwargs.items())
    config_cache_delete(subdomain)
    
    
def get_for_subdomain(subdomain, name, default=None):
    """Gets a configuration setting for a particular subdomain.  Looks for a
    setting specific to the subdomain, then falls back to a global setting."""
#    value = get(subdomain + ':' + name)
#    if value is not None:
#        return value
#    return get('*' + ':' + name, default)
    value = get_config_from_cache(subdomain, name)
    if value is not None:
        return value
    return get( name)

def set_for_subdomain(subdomain, **kwargs):
    """Sets configuration settings for a particular subdomain.  When used
    with get_for_subdomain, has the effect of overriding global settings."""
    subdomain = str(subdomain)  # need an 8-bit string, not Unicode
    set(subdomain, **kwargs)

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
        return get_for_subdomain(self.subdomain, name)

    def keys(self):
        entries = model.filter_by_prefix(
            ConfigEntry.all(), self.subdomain + ':')
        return [entry.key().name().split(':', 1)[1] for entry in entries]

