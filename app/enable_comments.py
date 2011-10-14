#!/usr/bin/python2.5
# Copyright 2010 Google Inc.
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

import reveal

import model
import utils
from model import db

from django.utils.translation import ugettext as _

def send_enable_comments_email(handler, person):
    """Send the author an email to confirm disabling comments of record."""
    if not person.author_email:
        return handler.error(400,
                             'No author email for record %r' % self.params.id)

    # i18n: Subject line of an e-mail message notifying a user
    # i18n: that a person record has been deleted
    subject = _(
        '[Person Finder] Please confirm enable comments for record '
        '"%(first_name)s %(last_name)s"'
        ) % {'first_name': person.first_name, 'last_name': person.last_name}

    # send e-mail to record author confirming the lock of this record.
    template_name = 'enable_comments_email.txt'
    handler.send_mail(
        subject=subject,
        to=person.author_email,
        body=handler.render_to_string(
            template_name,
            author_name=person.author_name,
            first_name=person.first_name,
            last_name=person.last_name,
            site_url=handler.get_url('/'),
            enable_comments_url=get_enable_comments_url(handler, person)
        )
    )

def get_enable_comments_url(handler, person, ttl=3*24*3600):
    """Returns a URL to be used for disabling comments to a person record."""
    key_name = person.key().name()
    data = 'enable_comments:%s' % key_name
    token = reveal.sign(data, ttl)
    return handler.get_url('/confirm_enable_comments',
                           token=token, id=key_name)


class EnableComments(utils.Handler):
    """Handles an author request to disable comments to a person record."""

    def get(self):
        """Prompts the user with a CAPTCHA before proceeding the request."""
        person = model.Person.get(self.subdomain, self.params.id)
        if not person:
            return self.error(400, 'No person with ID: %r' % self.params.id)

        self.render('templates/enable_comments.html',
                    person=person,
                    view_url=self.get_url('/view', id=self.params.id),
                    captcha_html=self.get_captcha_html())

    def post(self):
        """If the user passed the CAPTCHA, send the confirmation email."""
        person = model.Person.get(self.subdomain, self.params.id)
        if not person:
            return self.error(400, 'No person with ID: %r' % self.params.id)

        captcha_response = self.get_captcha_response()
        if self.is_test_mode() or captcha_response.is_valid:
            send_enable_comments_email(self, person)

            return self.info(200, _('Your request is successfully processed. '
                                    'If you are the author of this record, '
                                    'please check your inbox and confirm '
                                    'that you want to enable future '
                                    'commenting to this record by following '
                                    'the url embedded in the email we will '
                                    'shortly send out.'))
        else:
            captcha_html = self.get_captcha_html(captcha_response.error_code)
            self.render('templates/enable_comments.html', person=person,
                        view_url=self.get_url('/view', id=self.params.id),
                        captcha_html=captcha_html)


if __name__ == '__main__':
    utils.run(('/enable_comments', EnableComments))
