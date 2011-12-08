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

"""Initialize Django and its internationalization machinery.

In any file that uses django modules, always import django_setup first.

To localize strings in Python files, import either gettext_lazy or ugettext
from this module as _, then use _('foo') to mark the strings to be translated.
Use gettext_lazy for strings that are declared before a language has been
selected; ugettext for those after (ugettext is safe to use in all Handlers)."""

__author__ = 'kpy@google.com (Ka-Ping Yee)'

from google.appengine.dist import use_library
use_library('django', '1.2')

import django.conf
import os

ROOT = os.path.abspath(os.path.dirname(__file__))
LANGUAGE_CODE = 'en'
LANGUAGES_BIDI = ['ar', 'he', 'fa', 'iw', 'ur']

if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    # See http://code.google.com/p/googleappengine/issues/detail?id=985
    import urllib
    urllib.getproxies_macosx_sysconf = lambda: {}

try:
    django.conf.settings.configure()
except:
    pass
django.conf.settings.LANGUAGE_CODE = LANGUAGE_CODE
django.conf.settings.USE_I18N = True
django.conf.settings.LOCALE_PATHS = (os.path.join(ROOT, 'locale'),)
django.conf.settings.LANGUAGES_BIDI = LANGUAGES_BIDI

from django.utils.translation import activate, gettext_lazy, ugettext
