#!/usr/bin/env python
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import re

def iterate(query, cb=lambda x: x, batch_size=1000, status=True):
    start = time.time()
    count = 0
    results = query.fetch(batch_size)
    while results:
        rstart = time.time()
        for row in results:
            output = cb(row)
            if output:
                print output
            count += 1
        if status:
            print '%s rows processed in %.1fs' % (count, time.time() - rstart)
        results = query.with_cursor(query.cursor()).fetch(batch_size)
        
    print 'total time in %.1fs' % (time.time() - start)
    cb()


photo_regex = re.compile('http://.*\.person-finder.appspot.com/photo\?id=(.*)')

class PhotoFilter(object):
    MAX_PPL_COUNT = 1000
    
    def __init(self)__:
        self.ppl = []
        self.ppl_count = 0

    def save_person(self, person):
        if person:
            self.ppl.append(person)
            sefl.ppl_count += 1
        if not person or len(self.ppl) >= MAX_PPL_COUNT:
            if self.ppl:
                db.put(self.ppl)
            self.ppl = []
    
    def filter_photo_url(self, p):
        if not p:
            self.save_person()
            return
        if p.photo_url:
            match = photo_regex.match(p.photo_url)
            if match: 
                try:
                    photo_id = int(m.group(1))
                    k = db.Key('Photo', photo_id)
                    p.photo = k
                    save_person(p)
                except Exception:
                    pass


def dangling_pic(pic):
  ppl = pic.person_set.fetch(100)
  if not ppl:
    return pic.key().id()

ids = []
def dangling_pic_list(pic):
  if pic and not pic.person_set.count():
    ids.append(pic.key().id())
    
