import os
import json
import base64

class Local:
  wd = None


  translate_labels = {
                      'INBOX' : 'inbox',
                      'SPAM' : 'spam',
                      'TRASH' : 'trash',
                      'UNREAD' : 'unread',
                      'STARRED' : 'flagged',
                      'IMPORTANT' : 'important',
                      'SENT' : 'sent',
                      'DRAFT' : 'draft',
                      }

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

      self.json['last_historyId'] = self.last_historyId

      with open (self.state_f, 'w') as fd:
        json.dump (self.json, fd)

    def set_last_history_id (self, hid):
      self.last_historyId = hid
      self.write ()

  def __init__ (self, g):
    self.gmailieer = g
    self.wd = os.getcwd ()
    self.dry_run = g.dry_run

    # state file for local repository
    self.state_f = os.path.join (self.wd, '.gmailieer.json')

    # mail store
    self.md = os.path.join (self.wd, 'mail', 'cur')

  def load_repository (self):
    """
    Loads the current local repository
    """

    if not os.path.exists (self.state_f):
      raise Local.RepositoryException ('could not find state file')

    if not os.path.exists (self.md):
      raise Local.RepositoryException ('could not find mail dir')

    self.state = Local.State (self.state_f)

    # NOTE:
    # this list is used for .has () to figure out what messages we have
    # hopefully this won't grow to gigantic with lots of messages.
    self.files = []
    for (dp, dirnames, fnames) in os.walk (self.md):
      self.files.extend (fnames)
      break

    self.mids  = [f.split(':')[0] for f in self.files]

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
    os.makedirs (os.path.join (self.md, '../new'))
    os.makedirs (os.path.join (self.md, '../tmp'))

  def has (self, m):
    return m in self.mids

  def __make_maildir_name__ (self, m, labels):
    # http://cr.yp.to/proto/maildir.html
    p = m + ':'
    info = '2,'

    # must be ascii sorted
    if 'DRAFT' in labels:
      info += 'D'

    if 'IMPORTANT' in labels:
      info += 'F'

    if 'TRASH' in labels:
      info += 'T'

    if not 'UNREAD' in labels:
      info += 'S'

    return p + info

  def store (self, m):
    """
    Store message in local store
    """

    mid     = m['id']
    msg_str = base64.urlsafe_b64decode(m['raw'].encode ('ASCII'))

    labels  = m['labelIds']

    bname = self.__make_maildir_name__(mid, labels)
    self.files.append (bname)
    self.mids.append (mid)

    p = os.path.join (self.md, bname)
    if os.path.exists (p):
      raise Local.RepositoryException ("local file already exists: %s" % p)

    if not self.dry_run:
      with open (p, 'wb') as fd:
        fd.write (msg_str)


    # add to notmuch
    self.update_tags (m)

  def update_tags (self, m):
    # make sure notmuch tags reflect gmail labels
    labels = m['labelIds']

    # translate labels. Remote.get_labels () must have been called first
    labels = [self.gmailieer.remote.labels[l] for l in labels]

    labels = set(labels)

    # remove ignored labels
    ignore_labels = set (self.gmailieer.remote.ignore_labels)
    labels = list(labels - ignore_labels)

    # translate to notmuch tags
    labels = [self.translate_labels.get (l, l) for l in labels]

    # this is my weirdness
    labels = [l.replace ('/', '.') for l in labels]

    print (labels)

