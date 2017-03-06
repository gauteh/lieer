import os
import json
import mailbox
import base64

class Local:
  wd = None

  class RepositoryException (Exception):
    pass

  class State:
    # last historyid of last synchronized message, anything that has happened
    # remotely after this needs to be synchronized. gmail may return a 404 error
    # if the history records have been deleted, in which case we have to do a full
    # sync.
    last_historyId = 0

    def __init__ (self, state_f):
      self.state_f = state_f

      if os.path.exists (self.state_f):
        with open (self.state_f, 'r') as fd:
          self.json = json.load (fd)
      else:
        self.json = {}

      self.last_historyId = self.json.get ('last_historyId', 0)

    def write (self):
      self.json = {}

      self.json['last_historyId'] = self.historyId

      with open (self.state_f, 'w') as fd:
        json.dump (self.json, fd)

    def set_last_history_id (self, hid):
      self.last_historyId = hid
      self.write ()

  def __init__ (self, g):
    self.gmailieer = g
    self.wd = os.getcwd ()

    # state file for local repository
    self.state_f = os.path.join (self.wd, '.gmailieer.json')

    # mail store
    self.md = os.path.join (self.wd, 'mail')

  def load_repository (self):
    """
    Loads the current local repository
    """

    if not os.path.exists (self.state_f):
      raise Local.RepositoryException ('could not find state file')

    if not os.path.exists (self.md):
      raise Local.RepositoryException ('could not find mail dir')

    self.state = Local.State (self.state_f)

  def initialize_repository (self):
    """
    Sets up a local repository
    """
    print ("initializing repository in: %s.." % self.wd)

    # check if there is a repository here already or if there is anything that will conflict with setting up one
    if os.path.exists (self.state_f):
      raise Local.RepositoryException ("'.gmailieer.json' exists: this repository seems to already be set up!")

    if os.path.exists (self.md):
      raise Local.RepositoryException ("'mail' exists: this repository seems to already be set up!")

    self.state = Local.State (self.state_f)
    self.state.write ()
    os.makedirs (self.md)

  def has (self, m):
    return os.path.exists (os.path.join (self.md, m))

  def store (self, m):
    """
    Store message in local store
    """

    mid     = m['id']
    msg_str = base64.urlsafe_b64decode(m['raw'].encode ('ASCII'))

    p = os.path.join (self.md, mid)
    if os.path.exists (p):
      raise Local.RepositoryException ("local file already exists: %s" % p)

    with open (p, 'wb') as fd:
      fd.write (msg_str)

