# queue.py --- a simple mail queue for Lieer
#
# Copyright © 2020  Stefan Kangas <stefan@marxist.se>
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

from __future__ import print_function
import errno
import fcntl
import os
import time
import uuid

class Queue:

  TIMEOUT=30

  def __init__ (self, path, lockfile):
    self._path = os.path.join (path)
    self._lock = os.path.join (self._path, lockfile)
    self._lockfile = lockfile

  def add (self, msg, source):
    """
    Add an email to the queue.
    """
    with Flock(self._lock, self.TIMEOUT):
      destination = os.path.join (self._path, str (uuid.uuid4 ()))
      with open (destination, 'wb') as dest:
        dest.write(msg)

  def dir_create (self):
    if not self.dir_exists ():
      os.makedirs (self._path)

  def dir_exists (self):
    return os.path.exists (self._path)

  def files (self):
    """
    Return a list of all files in queue.
    """
    return [f for f in os.listdir (self._path)
            if os.path.isfile (os.path.join (self._path, f))
               and f != self._lockfile ]

  def list(self):
    """
    Print a listing of all files in the mail queue.
    """
    files = self.files ()
    if len (files) > 0:
      n = 0
      print ("total %d" % len (files))
      for f in files:
        n = n + 1
        print ("   %-5d %s" % (n, f))

  def run(self):
    """
    Run (flush) the mail queue.
    """
    with Flock(self._lock, self.TIMEOUT):
      pass

  def purge_all(self):
    """
    Purge all mails in queue queue.
    """
    with Flock(self._lock, self.TIMEOUT):
      for f in self.files ():
        os.unlink (os.path.join (self._path, f))


class Flock:
  """
  Provide an interface to flock-based file locking. Intended for use with the
  `with` syntax. It will create/truncate/delete the lock file as necessary.
  """

  def __init__(self, path, timeout = None):
    self._path = path
    self._timeout = timeout
    self._fd = None

  def __enter__(self):
    self._fd = os.open(self._path, os.O_CREAT)
    start_lock_search = time.time()
    while True:
      try:
        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Lock acquired!
        return
      except (OSError, IOError) as ex:
        if ex.errno != errno.EAGAIN: # Resource temporarily unavailable
          raise
        elif self._timeout is not None and time.time() > (start_lock_search + self._timeout):
          raise         # Timeout
      time.sleep(0.1)

  def __exit__(self, *args):
     fcntl.flock(self._fd, fcntl.LOCK_UN)
     os.close(self._fd)
     self._fd = None

     # Try to remove the lock file, but don't try too hard because it is
     # unnecessary. This is mostly to help the user see whether a lock
     # exists by examining the filesystem.
     try:
       os.unlink(self._path)
     except:
       pass
