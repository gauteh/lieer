import os
import json
import mailbox

class Local:
  wd = None

  class RepositoryException (Exception):
    pass

  class State:
    def __init__ (self, state_f):
      self.state_f = state_f

      if os.path.exists (self.state_f):
        with open (self.state_f, 'r') as fd:
          self.json = json.load (fd)
      else:
        self.json = {}

    def write (self):
      with open (self.state_f, 'w') as fd:
        json.dump (self.json, fd)

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

