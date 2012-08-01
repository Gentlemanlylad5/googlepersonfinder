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

from google.appengine.api import datastore_errors

from model import *
from utils import *
from detect_spam import SpamDetector
import extend
import prefix
import reveal
import subscribe

from django.utils.translation import ugettext as _
from urlparse import urlparse

# how many days left before we warn about imminent expiration.
# Make this at least 1.
EXPIRY_WARNING_THRESHOLD = 7

class Handler(BaseHandler):

    def get(self):
        redirect_url = self.maybe_redirect_jp_tier2_mobile()
        if redirect_url:
            return self.redirect(redirect_url)

        # Check the request parameters.
        if not self.params.id:
            return self.error(404, 'No person id was specified.')
        try:
            person = Person.get(self.repo, self.params.id)
        except ValueError:
            return self.error(404,
                _("This person's entry does not exist or has been deleted."))
        if not person:
            return self.error(404,
                _("This person's entry does not exist or has been deleted."))
        standalone = self.request.get('standalone')

        # Check if private info should be revealed.
        content_id = 'view:' + self.params.id
        reveal_url = reveal.make_reveal_url(self, content_id)
        show_private_info = reveal.verify(content_id, self.params.signature)

        # Compute the local times for the date fields on the person.
        person.source_date_local = self.to_local_time(person.source_date)
        person.expiry_date_local = self.to_local_time(
            person.get_effective_expiry_date())

        # Get the notes and duplicate links.
        try:
            notes = person.get_notes()
        except datastore_errors.NeedIndexError:
            notes = []
        person.sex_text = get_person_sex_text(person)
        for note in notes:
            note.status_text = get_note_status_text(note)
            note.linked_person_url = \
                self.get_url('/view', id=note.linked_person_record_id)
            note.flag_spam_url = \
                self.get_url('/flag_note', id=note.note_record_id,
                             hide=(not note.hidden) and 'yes' or 'no',
                             signature=self.params.signature)
            note.source_date_local = self.to_local_time(note.source_date)
        try:
            linked_persons = person.get_all_linked_persons()
        except datastore_errors.NeedIndexError:
            linked_persons = []
        linked_person_info = [
            dict(id=p.record_id,
                 name="%s %s" % (p.given_name, p.family_name),
                 view_url=self.get_url('/view', id=p.record_id))
            for p in linked_persons]

        # Render the page.
        dupe_notes_url = self.get_url(
            '/view', id=self.params.id, dupe_notes='yes')
        results_url = self.get_url(
            '/results',
            role=self.params.role,
            query=self.params.query,
            given_name=self.params.given_name,
            family_name=self.params.family_name)
        feed_url = self.get_url(
            '/feeds/note',
            person_record_id=self.params.id,
            repo=self.repo)
        subscribe_url = self.get_url('/subscribe', id=self.params.id)
        delete_url = self.get_url('/delete', id=self.params.id)
        disable_notes_url = self.get_url('/disable_notes', id=self.params.id)
        enable_notes_url = self.get_url('/enable_notes', id=self.params.id)
        extend_url = None
        extension_days = 0
        expiration_days = None
        expiry_date = person.get_effective_expiry_date()
        if expiry_date and not person.is_clone():
            expiration_delta = expiry_date - get_utcnow()
            extend_url =  self.get_url('/extend', id=self.params.id)
            extension_days = extend.get_extension_days(self)
            if expiration_delta.days < EXPIRY_WARNING_THRESHOLD:
                # round 0 up to 1, to make the msg read better.
                expiration_days = expiration_delta.days + 1

        if person.is_clone():
            person.provider_name = person.get_original_domain()
        person.full_name = get_person_full_name(person, self.config)

        sanitize_urls(person)

        self.render('view.html',
                    person=person,
                    notes=notes,
                    linked_person_info=linked_person_info,
                    standalone=standalone,
                    onload_function='view_page_loaded()',
                    show_private_info=show_private_info,
                    admin=users.is_current_user_admin(),
                    dupe_notes_url=dupe_notes_url,
                    results_url=results_url,
                    reveal_url=reveal_url,
                    feed_url=feed_url,
                    subscribe_url=subscribe_url,
                    delete_url=delete_url,
                    disable_notes_url=disable_notes_url,
                    enable_notes_url=enable_notes_url,
                    extend_url=extend_url,
                    extension_days=extension_days,
                    expiration_days=expiration_days)

    def post(self):
        if not self.params.text:
            return self.error(
                200, _('Message is required. Please go back and try again.'))

        if not self.params.author_name:
            return self.error(
                200, _('Your name is required in the "About you" section.  '
                       'Please go back and try again.'))

        if (self.params.status == 'is_note_author' and
            not self.params.author_made_contact):
            return self.error(
                200, _('Please check that you have been in contact with '
                       'the person after the earthquake, or change the '
                       '"Status of this person" field.'))

        if (self.params.status == 'believed_dead' and
            not self.config.allow_believed_dead_via_ui):
            return self.error(
                200, _('Not authorized to post notes with the status '
                       '"believed_dead".'))

        person = Person.get(self.repo, self.params.id)
        if person.notes_disabled:
            return self.error(
                200, _('The author has disabled status updates '
                       'on this record.'))

        # If a photo was uploaded, create and store a new Photo entry and get
        # the URL where it's served; otherwise, use the note_photo_url provided.
        photo, photo_url = (None, self.params.note_photo_url)
        if self.params.note_photo is not None:
            try:
                photo, photo_url = create_photo(self.params.note_photo, self)
            except PhotoError, e:
                return self.error(400, e.message)
            photo.put()

        spam_detector = SpamDetector(self.config.bad_words)
        spam_score = spam_detector.estimate_spam_score(self.params.text)

        if (spam_score > 0):
            note = NoteWithBadWords.create_original(
                self.repo,
                entry_date=get_utcnow(),
                person_record_id=self.params.id,
                author_name=self.params.author_name,
                author_email=self.params.author_email,
                author_phone=self.params.author_phone,
                source_date=get_utcnow(),
                author_made_contact=bool(self.params.author_made_contact),
                status=self.params.status,
                email_of_found_person=self.params.email_of_found_person,
                phone_of_found_person=self.params.phone_of_found_person,
                last_known_location=self.params.last_known_location,
                text=self.params.text,
                spam_score=spam_score,
                confirmed=False)
            # Write the new NoteWithBadWords to the datastore
            db.put(note)
            # When the note is detected as spam, we do not update person record
            # or log action. We ask the note author for confirmation first.
            return self.redirect('/post_flagged_note', id=note.get_record_id(),
                                 author_email=note.author_email,
                                 repo=self.repo)
        else:
            note = Note.create_original(
                self.repo,
                entry_date=get_utcnow(),
                person_record_id=self.params.id,
                author_name=self.params.author_name,
                author_email=self.params.author_email,
                author_phone=self.params.author_phone,
                source_date=get_utcnow(),
                author_made_contact=bool(self.params.author_made_contact),
                status=self.params.status,
                email_of_found_person=self.params.email_of_found_person,
                phone_of_found_person=self.params.phone_of_found_person,
                last_known_location=self.params.last_known_location,
                text=self.params.text)
            # Write the new regular Note to the datastore
            db.put(note)

        # Specially log 'believed_dead'.
        if note.status == 'believed_dead':
            detail = person.given_name + ' ' + person.family_name
            UserActionLog.put_new(
                'mark_dead', note, detail, self.request.remote_addr)

        # Specially log a switch to an alive status.
        if (note.status in ['believed_alive', 'is_note_author'] and
            person.latest_status not in ['believed_alive', 'is_note_author']):
            detail = person.given_name + ' ' + person.family_name
            UserActionLog.put_new('mark_alive', note, detail)

        # Update the Person based on the Note.
        if person:
            person.update_from_note(note)
            # Send notification to all people
            # who subscribed to updates on this person
            subscribe.send_notifications(self, person, [note])
            # write the updated person record to datastore
            db.put(person)

        # If user wants to subscribe to updates, redirect to the subscribe page
        if self.params.subscribe:
            return self.redirect('/subscribe', id=person.record_id,
                                 subscribe_email=self.params.author_email)

        # Redirect to this page so the browser's back button works properly.
        self.redirect('/view', id=self.params.id, query=self.params.query)
