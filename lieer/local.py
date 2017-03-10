import os
import json
import base64

import notmuch

class Local:
  wd      = None
  loaded  = False


  translate_labels = {
                      'INBOX' : 'inbox',
                      'SPAM' : 'spam',
                      'TRASH' : 'trash',
                      'UNREAD' : 'unread',
                      'STARRED' : 'flagged',
                      'IMPORTANT' : 'important',
                      'SENT' : 'sent',
                      'DRAFT' : 'draft',
                      'CHAT'  : 'chat'
                      }

  labels_translate = { v: k for k, v in translate_labels.items () }

  ignore_labels = set ([
                        'attachment',
                        'encrypted',
                        'signed',
                        'new',
                        'passed',
                        'replied',
                        ])

  class RepositoryException (Exception):
    pass

  class State:
    # last historyid of last synchronized message, anything that has happened
    # remotely after this needs to be synchronized. gmail may return a 404 error
    # if the history records have been deleted, in which case we have to do a full
    # sync.
    last_historyId = 0

    # this is the last modification id of the notmuch db when the previous push was completed.
    lastmod = 0

    replace_slash_with_dot = False
    account = None
    timeout = 5

    def __init__ (self, state_f):
      self.state_f = state_f

      if os.path.exists (self.state_f):
        with open (self.state_f, 'r') as fd:
          self.json = json.load (fd)
      else:
        self.json = {}

      self.last_historyId = self.json.get ('last_historyId', 0)
      self.lastmod = self.json.get ('lastmod', 0)
      self.replace_slash_with_dot = self.json.get ('replace_slash_with_dot', False)
      self.account = self.json.get ('account', 'me')
      self.timeout = self.json.get ('timeout', 5)

    def write (self):
      self.json = {}

      self.json['last_historyId'] = self.last_historyId
      self.json['lastmod'] = self.lastmod
      self.json['replace_slash_with_dot'] = self.replace_slash_with_dot
      self.json['account'] = self.account
      self.json['timeout'] = self.timeout

      with open (self.state_f, 'w') as fd:
        json.dump (self.json, fd)

    def set_last_history_id (self, hid):
      self.last_historyId = hid
      self.write ()

    def set_lastmod (self, m):
      self.lastmod = m
      self.write ()

    def set_account (self, a):
      self.account = a
      self.write ()

    def set_timeout (self, t):
      self.timeout = t
      self.write ()

  def __init__ (self, g):
    self.gmailieer = g
    self.wd = os.getcwd ()
    self.dry_run = g.dry_run

    # state file for local repository
    self.state_f = os.path.join (self.wd, '.gmailieer.json')
    self.credentials_f = os.path.join (self.wd, '.credentials.gmailieer.json')

    # mail store
    self.md = os.path.join (self.wd, 'mail', 'cur')

  def load_repository (self):
    """
    Loads the current local repository
    """

    if not os.path.exists (self.state_f):
      raise Local.RepositoryException ('local repository not initialized: could not find state file')

    if not os.path.exists (self.md):
      raise Local.RepositoryException ('local repository not initialized: could not find mail dir')

    self.state = Local.State (self.state_f)

    # NOTE:
    # this list is used for .has () to figure out what messages we have
    # hopefully this won't grow to gigantic with lots of messages.
    self.files = []
    for (dp, dirnames, fnames) in os.walk (self.md):
      self.files.extend (fnames)
      break

    self.mids = {}
    for f in self.files:
      m = f.split (':')[0]
      self.mids[m] = f

    ## Check if we are in the notmuch db
    with notmuch.Database () as db:
      try:
        self.nm_dir  = db.get_directory (os.path.abspath(os.path.join (self.md, '..')))
        if self.nm_dir is not None:
          self.nm_dir = self.nm_dir.path
        else:
          # probably empty dir
          self.nm_dir = os.path.abspath (os.path.join (self.md, '..'))

        self.nm_relative = self.nm_dir[len(db.get_path ())+1:]

      except notmuch.errors.FileError:
        raise Local.RepositoryException ("local mail repository not in notmuch db")

    self.loaded = True


  def initialize_repository (self, replace_slash_with_dot, account):
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
    self.state.replace_slash_with_dot = replace_slash_with_dot
    self.state.account = account
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

    if 'STARRED' in labels:
      info += 'F'

    if 'TRASH' in labels:
      info += 'T'

    if not 'UNREAD' in labels:
      info += 'S'

    return p + info

  def remove (self, mid, db):
    """
    Remove message from local store
    """
    fname = self.mids.get (mid, None)

    if fname is None:
      print ("remove: message does not exist in store: %s" % mid)
      return

    fname = os.path.join (self.md, fname)
    nmsg  = db.find_message_by_filename (fname)

    if self.dry_run:
      print ("(dry-run) deleting %s: %s." % (mid, fname))
    else:
      if nmsg is not None:
        db.remove_message (fname)
      os.unlink (fname)

    f = self.mids[mid]
    self.files.remove (f)
    self.mids.pop (mid)

  def store (self, m, db):
    """
    Store message in local store
    """

    mid     = m['id']
    msg_str = base64.urlsafe_b64decode(m['raw'].encode ('ASCII'))

    labels  = m.get('labelIds', [])

    bname = self.__make_maildir_name__(mid, labels)
    self.files.append (bname)
    self.mids[mid] = bname

    p = os.path.join (self.md, bname)
    if os.path.exists (p):
      raise Local.RepositoryException ("local file already exists: %s" % p)

    if not self.dry_run:
      with open (p, 'wb') as fd:
        fd.write (msg_str)

    # add to notmuch
    self.update_tags (m, p, db)

  def update_tags (self, m, fname, db):
    # make sure notmuch tags reflect gmail labels
    mid = m['id']
    labels = m.get('labelIds', [])

    # translate labels. Remote.get_labels () must have been called first
    labels = [self.gmailieer.remote.labels[l] for l in labels]

    labels = set(labels)

    # remove ignored labels
    labels = list(labels - self.gmailieer.remote.ignore_labels)

    # translate to notmuch tags
    labels = [self.translate_labels.get (l, l) for l in labels]

    # this is my weirdness
    if self.state.replace_slash_with_dot:
      labels = [l.replace ('/', '.') for l in labels]

    if fname is None:
      # this file hopefully already exists and just needs it tags updated,
      # let's try to find its name in the mid to fname table.
      fname = self.mids[mid]

    fname = os.path.join (self.md, fname)
    nmsg  = db.find_message_by_filename (fname)

    if not os.path.exists (fname):
      if not self.dry_run:
        raise Local.RepositoryException ("tried to update tags on non-existant file: %s" % fname)
      else:
        print ("(dry-run) tried to update tags on non-existant file: %s" % fname)

    if nmsg is None:
      if self.dry_run:
        print ("(dry-run) adding message: %s: %s, with tags: %s" % (mid, fname, str(labels)))
      else:
        (nmsg, stat) = db.add_message (fname, True)
        nmsg.freeze ()

        # adding initial tags
        for t in labels:
          nmsg.add_tag (t, True)

        nmsg.thaw ()

      return True

    else:
      # message is already in db, set local tags to match remote tags
      otags   = set(nmsg.get_tags ())
      igntags = otags & self.ignore_labels
      otags   = otags - self.ignore_labels # remove ignored tags while checking
      if otags != set (labels):
        labels.extend (igntags) # add back local ignored tags before adding
        if not self.dry_run:
          nmsg.freeze ()
          nmsg.remove_all_tags ()
          for t in labels:
            nmsg.add_tag (t, False)
          nmsg.thaw ()
          nmsg.tags_to_maildir_flags ()
        else:
          print ("(dry-run) changing tags on message: %s from: %s to: %s" % (mid, str(otags), str(labels)))

        return True
      else:
        return False



