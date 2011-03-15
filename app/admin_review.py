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

import logging

from google.appengine.ext import db

import model
import utils

NOTES_PER_PAGE = 25
STATUS_CODES = {
  None: 'u',
  '': 'u',
  'information_sought': 's',
  'believed_alive': 'a',
  'believed_missing': 'm',
  'believed_dead': 'd',
  'is_note_author': 'i',
}


class Review(utils.Handler):
    def get(self):
        status = self.request.get('status') or 'all'

        # Make the navigation links.
        nav_html = ''
        for option in [
            'all', 'unspecified', 'information_sought', 'is_note_author',
            'believed_alive', 'believed_missing', 'believed_dead']:
            if option == status:
                nav_html += '<b>%s</b>&nbsp; ' % option
            else:
                nav_html += '<a href="%s">%s</a>&nbsp; ' % (
                    self.get_url('/admin/review', status=option), option)

        # Construct the query for notes.
        query = model.Note.all_in_subdomain(self.subdomain
                         ).filter('reviewed =', False
                         ).order('-entry_date')
        if status == 'unspecified':
            query.filter('status =', '')
        elif status != 'all':
            query.filter('status =', status)

        notes = query.fetch(NOTES_PER_PAGE)
        for note in notes:
            # Copy in the fields of the associated Person.
            person = model.Person.get(self.subdomain, note.person_record_id)
            for name in person.properties():
                setattr(note, 'person_' + name, getattr(person, name))
            # Get the statuses of the other notes on this Person.
            status_codes = ''
            for other_note in person.get_notes():
                code = STATUS_CODES[other_note.status]
                if other_note.note_record_id == note.note_record_id:
                    code = code.upper()
                status_codes += code
            note.person_status_codes = status_codes

        return self.render('templates/admin_review.html',
                           notes=notes, nav_html=nav_html)

    def post(self):
        notes = []
        for name, value in self.request.params.items():
            if name.startswith('note.'):
                note = model.Note.get(self.subdomain, name[5:])
                if note:
                    if value in ['accept', 'flag']:
                        note.reviewed = True
                    if value == 'flag':
                        note.hidden = True
                    notes.append(note)
        db.put(notes)
        self.redirect('/admin/review', status=self.params.status)
        


if __name__ == '__main__':
    utils.run(('/admin/review', Review))
