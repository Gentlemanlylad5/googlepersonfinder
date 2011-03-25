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

"""Basic API for reading/writing small numbers of records."""

__author__ = 'kpy@google.com (Ka-Ping Yee)'

from datetime import datetime
import atom
from config import Configuration
import model
import importer
import indexing
import pfif
import subscribe
import sys
import utils
from model import Person, Note, Subdomain, ApiKeyLog
from text_query import TextQuery

HARD_MAX_RESULTS = 200  # Clients can ask for more, but won't get more.

class ApiAction(utils.Handler):
    """Common base for api actions."""
    
    def log_action(self, action, person_records, note_records,
                   people_skipped, notes_skipped):
        log = self.config and self.config.api_key_logging
        if log:
            write_perm = self.auth and self.auth.domain_write_permission
            ApiKeyLog.record_action(
                self.subdomain, self.params.key,
                self.params.version, action,
                person_records, note_records,
                people_skipped, notes_skipped,
                self.request.headers.get('User-Agent'),
                '', # TODO(lschumacher): figure out IP addr header.
                self.request.url, write_perm)


class Read(ApiAction):
    https_required = True

    def get(self):
        if self.config.read_auth_key_required and not (
            self.auth and self.auth.read_permission):
            self.response.set_status(403)
            self.write('Missing or invalid authorization key\n')
            return

        pfif_version = pfif.PFIF_VERSIONS.get(self.params.version)

        # Note that self.request.get can handle multiple IDs at once; we
        # can consider adding support for multiple records later.
        record_id = self.request.get('id')
        if not record_id:
            return self.error(400, 'Missing id parameter')
        person = model.Person.get(self.subdomain, record_id)
        if not person:
            return self.error(404, 'No person record with ID %s' % record_id)
        notes = model.Note.get_by_person_record_id(self.subdomain, record_id)
        notes = [note for note in notes if not note.hidden]

        self.response.headers['Content-Type'] = 'application/xml'
        records = [pfif_version.person_to_dict(person)]
        note_records = map(pfif_version.note_to_dict, notes)
        utils.optionally_filter_sensitive_fields(records, self.auth)
        utils.optionally_filter_sensitive_fields(note_records, self.auth)
        pfif_version.write_file(
            self.response.out, records, lambda p: note_records)
        self.log_action(ApiKeyLog.READ, len(records), 
                        len(notes), 0, 0)


class Write(ApiAction):
    https_required = True

    def post(self):
        if not (self.auth and self.auth.domain_write_permission):
            self.response.set_status(403)
            self.write('Missing or invalid authorization key\n')
            return

        source_domain = self.auth.domain_write_permission
        try:
            person_records, note_records = \
                pfif.parse_file(self.request.body_file)
        except Exception, e:
            self.response.set_status(400)
            self.write('Invalid XML: %s\n' % e)
            return

        self.response.headers['Content-Type'] = 'application/xml'
        self.write('<?xml version="1.0"?>\n')
        self.write('<status:status>\n')

        create_person = importer.create_person
        people_written, people_skipped, total = importer.import_records(
            self.subdomain, source_domain, create_person, person_records)
        self.write_status(
            'person', people_written, people_skipped, total, 'person_record_id')

        create_note = importer.create_note
        notes_written, notes_skipped, total = importer.import_records(
            self.subdomain, source_domain, create_note, note_records, self)
        self.write_status(
            'note', notes_written, notes_skipped, total, 'note_record_id')

        self.write('</status:status>\n')
        self.log_action(ApiKeyLog.WRITE, 
                        people_written, notes_written,
                        len(people_skipped), notes_skipped)

    def write_status(self, type, written, skipped, total, id_field):
        """Emit status information about the results of an attempted write."""
        skipped_records = []
        for error, record in skipped:
            skipped_records.append(
                '      <pfif:%s>%s</pfif:%s>\n' %
                (id_field, record.get(id_field, ''), id_field))
            skipped_records.append(
                '      <status:error>%s</status:error>\n' % error)

        self.write('''
  <status:write>
    <status:record_type>pfif:%s</status:record_type>
    <status:parsed>%d</status:parsed>
    <status:written>%d</status:written>
    <status:skipped>
%s
    </status:skipped>
  </status:write>
''' % (type, total, written, ''.join(skipped_records).rstrip()))

class Search(ApiAction):
    https_required = False
    
    def get(self):
        if self.config.search_auth_key_required and not (
            self.auth and self.auth.search_permission):
            return self.error(403, 'Missing or invalid authorization key\n')

        pfif_version = pfif.PFIF_VERSIONS.get(self.params.version)

        # Retrieve parameters and do some sanity checks on them.
        query_string = self.request.get("q")
        subdomain = self.request.get("subdomain")        
        max_results = min(self.params.max_results or 100, HARD_MAX_RESULTS)

        if not query_string:
            return self.error(400, 'Missing q parameter')
        if not subdomain:
            return self.error(400, 'Missing subdomain parameter')
   
        # Perform the search.
        results = indexing.search(
            subdomain, TextQuery(query_string), max_results)

        records = [pfif_version.person_to_dict(result) for result in results]
        utils.optionally_filter_sensitive_fields(records, self.auth)

        # Define the function to retrieve notes for a person.
        def get_notes_for_person(person):
            notes = model.Note.get_by_person_record_id(
                self.subdomain, person['person_record_id'])
            notes = [note for note in notes if not note.hidden]
            records = map(pfif_version.note_to_dict, notes)
            utils.optionally_filter_sensitive_fields(records, self.auth)
            return records

        self.response.headers['Content-Type'] = 'application/xml'        
        pfif_version.write_file(
            self.response.out, records, get_notes_for_person)
        

class Subscribe(ApiAction):
    https_required = True

    def post(self):
        if not (self.auth and self.auth.subscribe_permission):
            return self.error(403, 'Missing or invalid authorization key')

        if not subscribe.is_email_valid(self.params.subscribe_email):
            return self.error(400, 'Invalid email address')

        person = model.Person.get(self.subdomain, self.params.id)
        if not person:
            return self.error(400, 'Invalid person_record_id')

        subscription = subscribe.subscribe_to(self, self.subdomain, person,
                                              self.params.subscribe_email,
                                              self.params.lang)
        self.log_action(ApiKeyLog.SUBSCRIBE, 0, 0, 0, 0)
        if not subscription:
            return self.info(200, 'Already subscribed')
        return self.info(200, 'Successfully subscribed')


class Unsubscribe(ApiAction):
    https_required = True

    def post(self):
        if not (self.auth and self.auth.subscribe_permission):
            return self.error(403, 'Missing or invalid authorization key')

        subscription = model.Subscription.get(self.subdomain, self.params.id,
                                              self.params.subscribe_email)
        self.response.set_status(200)
        self.log_action(ApiKeyLog.UNSUBSCRIBE, 0, 0, 0, 0)
        if subscription:
            subscription.delete()
            return self.info(200, 'Successfully unsubscribed')
        return self.info(200, 'Not subscribed')


if __name__ == '__main__':
    utils.run(('/api/read', Read),
              ('/api/write', Write),
              ('/api/search', Search),
              ('/api/subscribe', Subscribe),
              ('/api/unsubscribe', Unsubscribe))
