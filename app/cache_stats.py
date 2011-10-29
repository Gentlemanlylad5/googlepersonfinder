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

"""Display for configuration settings.  This should live in config.py, but that
creates dependency loops with utils."""

import random, simplejson
import utils
import config

class CacheStats(utils.Handler):
    """Handler for cache management and stats."""
    # cache is global
    subdomain_required = False
    
    def get(self):
        """Handler that renders the cache stats or optionally spits out json."""
        stats = config.cache.get_stats()
        if self.params.operation == 'json':
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(simplejson.dumps(stats))
            self.terminate_response()
        else:
            self.render('templates/cache_stats.html', data=stats)

if __name__ == '__main__':
    utils.run(('/admin/cachestats', CacheStats))
