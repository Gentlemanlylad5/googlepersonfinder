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

"""Handler for retrieving uploaded photos for display."""

import os

import model
import utils


def get_photo_url(photo, handler):
    """Returns the URL where this app is serving a hosted Photo object."""
    port = int(os.environ.get('SERVER_PORT', '80'))
    if port < 1024:
        # Assume that serving on a privileged port means we're in production.
        # We use HTTPS for production URLs so that they don't trigger content
        # warnings when photos are embedded in HTTPS pages.
        scheme = 'https'
    else:
        # The development server only serves HTTP, not HTTPS.
        scheme = 'http'
    id = photo.key().name().split(':')[1]
    return handler.get_url('/photo', scheme=scheme, id=id)


class Handler(utils.BaseHandler):
    repo_required = False  # photos are not partitioned by repository

    def get(self):
        try:
            id = int(self.params.id)
        except:
            return self.error(404, 'Photo id is unspecified or invalid.')
        photo = model.Photo.get(self.repo, id)
        if not photo:
            return self.error(404, 'There is no photo for the specified id.')
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(photo.image_data)
