#!/usr/bin/python2.5
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'argent@google.com (Evan Anderson), nakajima@google.com(Takahiro Nakajima)'

import datetime
import logging
import random
import simplejson
import sys
import urllib

import indexing
import model
import utils
from google.appengine.api import urlfetch


def fetch_with_load_balancing(path, backend_list,
                              fetch_timeout=1.0, total_timeout=5.0):
    """Attempt to fetch a url at path from one or more backends.

    Args:
        path: The url-path that should be fetched
        backend_list: A list of backend hosts from which content may be
                      fetched.  This may be iterated over several times
                      if needed.
        fetch_timeout: The time in seconds to allow one request to wait before
                       retrying.
        total_timeout: The total time in seconds to allow for all requests
                       before giving up.
    Returns:
        A urlfetch.Response object, or None if the timeout has been exceeded.
    """
    end_time = (
        datetime.datetime.now() + datetime.timedelta(seconds=total_timeout))
    shuffled_backend_list = backend_list[:]
    random.shuffle(shuffled_backend_list)
    for backend in shuffled_backend_list:
        if datetime.datetime.now() >= end_time:
            return None
        attempt_url = 'http://%s%s' % (backend, path)
        logging.debug('Balancing to %s', attempt_url)
        try:
            page = urlfetch.fetch(attempt_url, deadline=fetch_timeout)
            if page.status_code != 200:
                logging.info('Bad status code: %d' % page.status_code)
                return None
            return page
        except:
            logging.info('Failed to fetch %s: %s', attempt_url,
                         str(sys.exc_info()[1]))
    return None


def dict_to_person(subdomain, d):
    """Convert a dictionary representing a person returned from a backend to a
    Person model instance."""
    # Convert unicode keys to string keys.
    d = dict([(key.encode('utf-8'), value) for key, value in d.iteritems()])
    d['source_date'] = utils.validate_datetime(d['source_date'])
    d['entry_date'] = utils.validate_datetime(d['entry_date'])
    return model.Person.create_original_with_record_id(
        subdomain, d['person_record_id'], **d)


def search(subdomain, query_obj, max_results, backends):
    """Search persons using external search backends.

    Args:
        subdomain: PF's subdomain from which the query was sent.
        query_obj: TextQuery instance representing the input query.
        max_results: Maximum number of entries to return.
        backends: List of backend IPs or hostnames to access.
    Returns:
        List of Persons that are returned from an external search backend.
    """
    query = query_obj.query.encode('utf-8')
    path = '/pf_access.cgi?query=' + urllib.quote_plus(query)
    page = fetch_with_load_balancing(
        path, backends, fetch_timeout=0.9, total_timeout=0.1)
    if page:
        try:
            data = simplejson.loads(page.content)
        except simplejson.decoder.JSONDecodeError:
            logging.warn('Fetched content is broken.')
            return None
        name_entries = [dict_to_person(subdomain, entry)
                        for entry in data['name_entries']]
        all_entries = [dict_to_person(subdomain, entry)
                       for entry in data['all_entries']]
        name_entries.sort(indexing.CmpResults(query_obj))
        return (name_entries + all_entries)[:max_results]
    return None
