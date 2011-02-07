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

"""Tests for model.py."""

from datetime import datetime
from google.appengine.ext import db
import unittest
import model
from utils import get_utcnow, set_utcnow_for_test

class ModelTests(unittest.TestCase):
    '''Test the loose odds and ends.'''

    def setUp(self):
        set_utcnow_for_test(datetime(2010,1,1))
        self.p1 = model.Person.create_original(
            'haiti',
            first_name='John',
            last_name='Smith',
            home_street='Washington St.',
            home_city='Los Angeles',
            home_state='California',
            home_postal_code='11111',
            home_neighborhood='Good Neighborhood',
            author_name='Alice Smith',
            author_phone='111-111-1111',
            author_email='alice.smith@gmail.com',
            source_url='https://www.source.com',
            source_date=datetime(2010, 1, 1),
            source_name='Source Name',
            entry_date=datetime(2010, 1, 1),
            expiry_date=datetime(2010, 2, 1),
            other='')
        self.p2 = model.Person.create_original(
            'haiti',
            first_name='Tzvika',
            last_name='Hartman',
            home_street='Herzl St.',
            home_city='Tel Aviv',
            home_state='Israel',
            entry_date=datetime(2010, 1, 1),
            expiry_date=datetime(2010, 3, 1),
            other='')
        self.key_p1 = db.put(self.p1)
        self.key_p2 = db.put(self.p2)

        self.n1_1 = model.Note.create_original(
            'haiti',
            person_record_id=self.p1.record_id,
            linked_person_record_id=self.p2.record_id,
            status=u'believed_missing',
            found=False,
            entry_date=get_utcnow(),
            source_date=datetime(2000, 1, 1))
        self.n1_2 = model.Note.create_original(
            'haiti',
            person_record_id=self.p1.record_id,
            found=True,
            entry_date=get_utcnow(),
            source_date=datetime(2000, 2, 2))
        self.key_n1_1 = db.put(self.n1_1)
        self.key_n1_2 = db.put(self.n1_2)

        # Update the Person entity according to the Note.
        self.p1.update_from_note(self.n1_1)
        self.p1.update_from_note(self.n1_2)
        db.put(self.p1)

    def tearDown(self):
        db.delete([self.key_p1, self.key_p2, self.key_n1_1, self.key_n1_2])

    def test_person(self):
        assert self.p1.first_name == 'John'
        assert self.p1.photo_url == ''
        assert self.p1.is_clone() == False
        assert model.Person.get('haiti', self.p1.record_id).record_id == \
            self.p1.record_id
        assert model.Person.get('haiti', self.p2.record_id).record_id == \
            self.p2.record_id
        assert model.Person.get('haiti', self.p1.record_id).record_id != \
            self.p2.record_id

        # Testing prefix properties
        assert hasattr(self.p1, 'first_name_n_')
        assert hasattr(self.p1, 'home_street_n1_')
        assert hasattr(self.p1, 'home_postal_code_n2_')


    def test_note(self):
        assert self.n1_1.is_clone() == False

        assert self.p1.get_notes()[0].record_id == self.n1_1.record_id
        assert self.p1.get_notes()[1].record_id == self.n1_2.record_id
        assert self.p1.get_linked_persons()[0].record_id == self.p2.record_id
        assert self.p2.get_linked_persons() == []

        assert model.Note.get('haiti', self.n1_1.record_id).record_id == \
            self.n1_1.record_id
        assert model.Note.get('haiti', self.n1_2.record_id).record_id == \
            self.n1_2.record_id

    def test_subscription(self):
        sd = 'haiti'
        email1 = 'one@example.com'
        email2 = 'two@example.com'
        s1 = model.Subscription.create(sd, self.p1.record_id, email1, 'fr')
        s2 = model.Subscription.create(sd, self.p1.record_id, email2, 'en')
        key_s1 = db.put(s1)
        key_s2 = db.put(s2)

        assert model.Subscription.get(sd, self.p1.record_id, email1) is not None
        assert model.Subscription.get(sd, self.p1.record_id, email2) is not None
        assert model.Subscription.get(sd, self.p2.record_id, email1) is None
        assert model.Subscription.get(sd, self.p2.record_id, email2) is None
        assert len(self.p1.get_subscriptions()) == 2
        assert len(self.p2.get_subscriptions()) == 0

        s3 = model.Subscription.create(sd, self.p1.record_id, email2, 'ar')
        key_s3 = db.put(s3)
        assert len(self.p1.get_subscriptions()) == 2
        assert model.Subscription.get(
            sd, self.p1.record_id, email2).language == 'ar'
        db.delete([key_s1, key_s2, key_s3])

if __name__ == '__main__':
    unittest.main()
