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

import os

from recaptcha.client import captcha 
from google.appengine.ext import db

import config
import model
import utils
from utils import datetime


class FlagNote(utils.Handler):
    """Marks a specified note as hidden [spam], and tracks it in the
    FlagNote table."""
    def get(self):
        note = model.Note.get(self.subdomain, self.params.id)
        if not note:
            return self.error(400, 'No note with ID: %r' % self.params.id)
        captcha_html = note.hidden and utils.get_captcha_html() or ''

        self.render('templates/confirmation.html',
                    note=note, captcha_html=captcha_html)

    def post(self):
        note = model.Note.get(self.subdomain, self.params.id)
        if not note:
            return self.error(400, 'No note with ID: %r' % self.params.id)

        if note.hidden:
            challenge = self.request.get('recaptcha_challenge_field')
            response = self.request.get('recaptcha_response_field')
            remote_ip = os.environ['REMOTE_ADDR']
            captcha_response = captcha.submit(
                challenge, response, config.get('captcha_private_key'),
                remote_ip)

        is_test_mode = utils.validate_yes(self.request.get('test_mode', ''))
        if not note.hidden or captcha_response.is_valid or is_test_mode:
            # Mark the appropriate changes
            note.hidden = not note.hidden
            db.put(note)

            # Track change in FlagNote table
            model.NoteFlag(subdomain=self.subdomain,
                           note_record_id=self.params.id,
                           time=datetime.now(), spam=note.hidden).put()
            self.redirect(self.get_url('/view', id=note.person_record_id))
        elif not captcha_response.is_valid:
            captcha_html = utils.get_captcha_html(captcha_response.error_code)
            self.render('templates/confirmation.html',
                        note=note, captcha_html=captcha_html)


if __name__ == '__main__':
    utils.run(('/flag_note', FlagNote))
