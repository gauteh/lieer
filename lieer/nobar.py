#! /usr/bin/env python3
#
# Regular non-TTY drop-in replacement for tqdm
#
# Copyright © 2020  Gaute Hope <eg@gaute.vetsj.com>
#
# This file is part of Lieer.
#
# Lieer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import time
from   math import floor

class tqdm:
  def __init__ (self, iterable = None, leave = True, total = None, desc = '', *args, **kwargs):
    self.desc = desc
    self.args = args
    self.kwargs = kwargs

    if total is not None:
      print (desc, '(%d)' % total, '...', end = '', flush = True)
    else:
      print (desc, '...', end = '', flush = True)

    self.start = time.perf_counter ()
    self.it    = 0

    if iterable is not None:
      self.iterable = (i for i in iterable)

  def __next__ (self):
    if self.iterable is not None:
      self.update (1)

      try:
        return next(self.iterable)
      except StopIteration:
        self.close ()
        raise
    else:
      raise StopIteration

  def __iter__ (self):
    return self

  def update (self, n, *args):
    self.it += n

    INTERVAL = 10

    if (self.it % INTERVAL == 0):
      print ('.', end = '', flush = True)

  def set_description (self, *args, **kwargs):
    pass

  def close (self):
    self.end = time.perf_counter ()
    print ('done:', self.it, 'its in', self.pp_duration (self.end - self.start))

  def pp_duration (self, d = None):
    dys = floor (d / (24 * 60 * 60))
    d   = d - (dys * 24 * 60 * 60)

    h = floor (d / (60 * 60))
    d = d - (h * 60 * 60)

    m = floor (d / 60)
    d = d - (m * 60)

    s = d

    o = ''
    above = False
    if dys > 0:
      o = '%dd-' % dys
      above = True

    if above or h > 0:
      o = o + '%02dh:' % h
      above = True

    if above or m > 0:
      o = o + '%02dm:' % m
      above = True

    o = o + '%06.3fs' % s

    return o


