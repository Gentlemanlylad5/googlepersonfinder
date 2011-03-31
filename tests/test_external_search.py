#!/usr/bin/python2.5
# Copyright 2011 Google Inc.
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

"""Unittest for external_search.py module."""

__author__ = 'ryok@google.com (Ryo Kawaguchi)'

import datetime
import logging
import mox
import random
import simplejson
import sys
import unittest

import external_search
import model
import text_query
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors


class MockPerson:
    """Mock Person with minimal attributes."""
    def __init__(self, subdomain, record_id, first_name, last_name):
        self.subdomain = subdomain
        self.record_id = record_id
        self.key_name = '%s:%s' % (subdomain, record_id)
        self.first_name = first_name
        self.last_name = last_name
        self.alternate_first_names = self.alternate_last_names = ''
        self.names_prefixes = text_query.TextQuery(
            '%s %s' % (first_name, last_name)).query_words

    @staticmethod
    def get_by_key_name(key_names):
        person_dict = dict([(p.key_name, p) for p in MOCK_PERSONS])
        return [person_dict.get(key_name, None) for key_name in key_names]

MOCK_PERSONS = [
    MockPerson('japan', 'test/1', '', 'Mori'),
    # missing test/2
    MockPerson('japan', 'test/3', 'Ogai', 'Mori'),
    MockPerson('japan', 'test/4', 'Ogai', 'Mori'),
    MockPerson('japan', 'test/5', 'Natsume', 'Souseki'),
]


class MockUrlFetchResponse:
    """Mock response object returned from urlfetch.fetch."""
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = simplejson.dumps(content)


class MockLoggingHandler(logging.Handler):
    """Mock logging handler to check for expected logs."""
    def __init__(self, *args, **kwargs):
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        self.messages = {
            'debug': [],
            'info': [],
            'warning': [],
            'error': [],
            'critical': [],
        }


class ExternalSearchTests(unittest.TestCase):
    def setUp(self):
        self.base_datetime = datetime.datetime(2011, 1, 1)

        self.mox = mox.Mox()
        self.mox.StubOutWithMock(urlfetch, 'fetch')
        self.mox.StubOutWithMock(datetime, 'datetime')
        self.mox.StubOutWithMock(random, 'shuffle')
        random.shuffle(mox.IsA(list))

        self.orig_person = model.Person
        model.Person = MockPerson

        self.mock_logging_handler = MockLoggingHandler()
        logging.getLogger().addHandler(self.mock_logging_handler)

        # The first two calls of datetime.datetime.now are almost simultaneous.
        # Line 48 and line 52 in external_search.py.
        self.next_datetime_now(0)
        self.next_datetime_now(0)

    def tearDown(self):
        self.mox.UnsetStubs()
        model.Person = self.orig_person
        logging.getLogger().removeHandler(self.mock_logging_handler)

    def next_datetime_now(self, seconds=0):
        datetime.datetime.now().AndReturn(
            self.base_datetime + datetime.timedelta(seconds=seconds))

    def test_search_missing_entries(self):
        response = MockUrlFetchResponse(200, {
            'name_entries': [
                {'person_record_id': 'test/1'},
                {'person_record_id': 'test/2'},
                {'person_record_id': 'test/3'},
                {'person_record_id': 'test/4'},
            ],
            'all_entries': []
        })
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100, ['test_backend'])
        self.assertEquals(3, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals('test/3', results[1].record_id)
        self.assertEquals('test/4', results[2].record_id)
        self.mox.VerifyAll()

    def test_search_broken_content(self):
        response = MockUrlFetchResponse(200, '')
        response.content = 'broken'
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100, ['test_backend'])
        self.assertEquals(None, results)
        self.assertEquals(['Fetched content is broken.'],
                          self.mock_logging_handler.messages['warning'])
        self.mox.VerifyAll()

    def test_search_missing_entries(self):
        response = MockUrlFetchResponse(200, {
            'name_entries': [
                {'person_record_id': 'test/1'},
                {'person_record_id': 'test/2'},
                {'person_record_id': 'test/3'},
                {'person_record_id': 'test/4'},
            ],
            'all_entries': []
        })
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100, ['test_backend'])
        self.assertEquals(3, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals('test/3', results[1].record_id)
        self.assertEquals('test/4', results[2].record_id)
        self.mox.VerifyAll()

    def test_search_max_results(self):
        response = MockUrlFetchResponse(200, {
            'name_entries': [
                {'person_record_id': 'test/1'},
                {'person_record_id': 'test/2'},
                {'person_record_id': 'test/3'},
            ],
            'all_entries': [
                {'person_record_id': 'test/3'},
                {'person_record_id': 'test/4'},
                {'person_record_id': 'test/5'},
            ],
        })
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 1, ['test_backend'])
        self.assertEquals(1, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.mox.VerifyAll()

    def test_search_with_address_matches(self):
        response = MockUrlFetchResponse(200, {
            'name_entries': [
                {'person_record_id': 'test/1'},
                {'person_record_id': 'test/2'},
            ],
            'all_entries': [
                {'person_record_id': 'test/3'},
                {'person_record_id': 'test/4'},
                {'person_record_id': 'test/5'},
            ],
        })
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100, ['test_backend'])
        self.assertEquals(3, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals('test/3', results[1].record_id)
        self.assertEquals('test/4', results[2].record_id)
        self.assertTrue(results[1].address_match_begins)
        self.mox.VerifyAll()

    def test_search_remove_non_name_matches(self):
        response = MockUrlFetchResponse(200, {
            'name_entries': [],
            'all_entries': [
                {'person_record_id': 'test/1'},
                {'person_record_id': 'test/2'},
                {'person_record_id': 'test/3'},
                {'person_record_id': 'test/4'},
                {'person_record_id': 'test/5'},
            ],
        })
        urlfetch.fetch('http://test_backend/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(response)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100, ['test_backend'])
        self.assertEquals(3, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals('test/3', results[1].record_id)
        self.assertEquals('test/4', results[2].record_id)
        self.assertTrue(results[0].address_match_begins)
        self.mox.VerifyAll()

    def test_search_shuffle_backends(self):
        bad_response = MockUrlFetchResponse(500, '')
        urlfetch.fetch('http://backend1/pf_access.cgi?query=mori',
                       deadline=0.9).InAnyOrder().AndReturn(bad_response)
        urlfetch.fetch('http://backend2/pf_access.cgi?query=mori',
                       deadline=0.9).InAnyOrder().AndReturn(bad_response)
        urlfetch.fetch('http://backend3/pf_access.cgi?query=mori',
                       deadline=0.9).InAnyOrder().AndReturn(bad_response)
        self.next_datetime_now(0)
        self.next_datetime_now(0)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100,
            ['backend1', 'backend2', 'backend3'])
        self.assertEquals(None, results)
        self.mox.VerifyAll()

    def test_search_recover_from_bad_response(self):
        good_response = MockUrlFetchResponse(200, {
            'name_entries': [{'person_record_id': 'test/1'}],
            'all_entries': [],
        })
        bad_response = MockUrlFetchResponse(500, '')
        urlfetch.fetch('http://backend1/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(bad_response)
        urlfetch.fetch('http://backend2/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(bad_response)
        urlfetch.fetch('http://backend3/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(good_response)
        self.next_datetime_now(0)
        self.next_datetime_now(0)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100,
            ['backend1', 'backend2', 'backend3'])
        self.assertEquals(1, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals(['Bad status code: 500', 'Bad status code: 500'],
                          self.mock_logging_handler.messages['info'])
        self.mox.VerifyAll()

    def test_search_recover_from_fetch_failure(self):
        good_response = MockUrlFetchResponse(200, {
            'name_entries': [{'person_record_id': 'test/1'}],
            'all_entries': [],
        })
        urlfetch.fetch('http://backend1/pf_access.cgi?query=mori',
                       deadline=0.9).AndRaise(urlfetch_errors.Error('bad'))
        urlfetch.fetch('http://backend2/pf_access.cgi?query=mori',
                       deadline=0.9).AndRaise(urlfetch_errors.Error('bad'))
        urlfetch.fetch('http://backend3/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(good_response)
        self.next_datetime_now(0)
        self.next_datetime_now(0)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100,
            ['backend1', 'backend2', 'backend3'])
        self.assertEquals(1, len(results))
        self.assertEquals('test/1', results[0].record_id)
        self.assertEquals(['Failed to fetch: bad', 'Failed to fetch: bad'],
                          self.mock_logging_handler.messages['info'])
        self.mox.VerifyAll()

    def test_search_retry_time_out(self):
        good_response = MockUrlFetchResponse(200, {
            'name_entries': [{'person_record_id': 'test/1'}],
            'all_entries': [],
        })
        bad_response = MockUrlFetchResponse(500, '')
        urlfetch.fetch('http://backend1/pf_access.cgi?query=mori',
                       deadline=0.9).AndReturn(bad_response)
        urlfetch.fetch('http://backend2/pf_access.cgi?query=mori',
                       deadline=0.9).AndRaise(urlfetch_errors.Error('bad'))
        self.next_datetime_now(0.09)
        self.next_datetime_now(0.2)
        self.mox.ReplayAll()
        results = external_search.search(
            'japan', text_query.TextQuery('mori'), 100,
            ['backend1', 'backend2', 'backend3'])
        self.assertEquals(None, results)
        self.assertEquals(['Bad status code: 500', 'Failed to fetch: bad',
                           'Fetch retry timed out.'],
                          self.mock_logging_handler.messages['info'])
        self.mox.VerifyAll()

# To run this test independently:
# pushd tools; source common.sh; popd
# python2.5 tests/test_external_search.py
if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    unittest.main()