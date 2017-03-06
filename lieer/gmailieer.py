#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#


import  os, sys
import  argparse
from    oauth2client import tools
import  googleapiclient

from tqdm import tqdm, tqdm_gui

from .remote import *
from .local  import *

class Gmailieer:
  def __init__ (self):
    xdg_data_home = os.getenv ('XDG_DATA_HOME', os.path.expanduser ('~/.local/share'))
    self.home = os.path.join (xdg_data_home, 'gmailieer')

  def main (self):
    parser = argparse.ArgumentParser ('Gmailieer', parents = [tools.argparser])
    self.parser = parser

    parser.add_argument ('action', choices = ['pull', 'push', 'auth', 'init'],
        help = 'pull: get new e-mail and remote tag-changes, push: push local tag-changes, auth: authorize gmailieer with account, init: initialize local repository')

    parser.add_argument ('-c', '--credentials', type = str, default = 'client_secret.json',
        help = 'credentials file for google api (default: client_secret.json)')

    parser.add_argument ('-d', '--dry-run', action='store_true', default = False,
        help = 'do not make any changes')

    parser.add_argument ('-t', '--list-labels', action='store_true', default = False,
        help = 'list all remote labels (pull)')

    parser.add_argument ('-a', '--account', type = str, default = 'me',
        help = 'GMail account to use (default: me, currently logged in user)')

    parser.add_argument ('-f', '--force', action = 'store_true', default = False,
        help = 'Force action (auth)')

    parser.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to synchronize')

    args        = parser.parse_args (sys.argv[1:])
    self.args   = args

    self.action           = args.action
    self.dry_run          = args.dry_run
    self.credentials_file = args.credentials
    self.list_labels      = args.list_labels
    self.account          = args.account
    self.force            = args.force
    self.limit            = args.limit

    if self.dry_run:
      print ("dry-run: ", self.dry_run)

    self.local  = Local (self)
    self.remote = Remote (self)

    if self.action == 'pull':
      self.pull ()

    elif self.action == 'auth':
      print ("authorizing..")
      self.remote.authorize (self.force)

    elif self.action == 'push':
      raise NotImplmentedError ()

    elif self.action == 'init':
      self.local.initialize_repository ()



  def pull (self):
    if self.list_labels:
      for l in self.remote.get_labels ().values ():
        print (l)
      return

    self.remote.get_labels () # to make sure label map is initialized
    self.local.load_repository ()

    if self.force:
      print ("pull: full synchronizatoin (forced)")
      self.full_pull ()

    elif self.local.state.last_historyId == 0:
      print ("pull: full synchronization (no previous synchronization state)")
      self.full_pull ()

    else:
      print ("pull: partial synchronization.. (hid: %d)" % self.local.state.last_historyId)
      self.partial_pull ()

  def partial_pull (self):
    # get history
    bar         = None
    message_ids = []
    last_id     = 0

    try:
      for mset in self.remote.get_messages_since (self.local.state.last_historyId):
        msgs = mset

        if bar is None:
          bar = tqdm (leave = True, desc = 'fetching changes')

        bar.update (len(msgs))

        for m in msgs:
          message_ids.append (m['id'])

        if self.limit is not None and len(message_ids) >= self.limit:
          break

    except googleapiclient.errors.HttpError:
      if bar is not None: bar.close ()
      print ("historyId is too old, full sync required.")
      self.full_pull ()
      return


    if bar is not None: bar.close ()

    message_ids = list(set(message_ids)) # make unique

    if len(message_ids) > 0:
      # get historyId
      mm = self.remote.get_message (message_ids[0])
      last_id = int(mm['historyId'])
      self.local.state.set_last_history_id (last_id)

      # get content for new messages
      updated = self.get_content (message_ids)

      # get updated labels for the rest
      needs_update = list(set(message_ids) - set(updated))
      self.get_meta (needs_update)
    else:
      print ("everything is up-to-date.")

    if (last_id > 0):
      print ('current historyId: %d' % last_id)

  def full_pull (self):
    total = 1

    bar = tqdm (leave = True, total = total, desc = 'fetching messages')

    # NOTE:
    # this list might grow gigantic for large quantities of e-mail, not really sure
    # about how much memory this will take. this is just a list of some
    # simple metadata like message ids.
    message_ids = []
    last_id     = 0

    for mset in self.remote.all_messages ():
      (total, mids) = mset

      bar.total = total
      bar.update (len(mids))

      for m in mids:
        message_ids.append (m['id'])

      if self.limit is not None and len(message_ids) >= self.limit:
        break

    bar.close ()

    if len(message_ids) > 0:
      # get historyId
      mm = self.remote.get_message (message_ids[0])
      last_id = int(mm['historyId'])
      self.local.state.set_last_history_id (last_id)

      # get content for new messages
      updated = self.get_content (message_ids)

      # get updated labels for the rest
      needs_update = list(set(message_ids) - set(updated))
      self.get_meta (needs_update)
    else:
      print ("no messages.")

    print ('current historyId: %d' % last_id)

  def get_meta (self, msgids):
    """
    Only gets the minimal message objects in order to check if labels are up-to-date.
    """

    if len (msgids) > 0:

      bar = tqdm (leave = True, total = len(msgids), desc = 'receiving metadata')

      def _got_msg (m):
        bar.update (1)
        self.local.update_tags (m)

      self.remote.get_messages (msgids, _got_msg, 'minimal')

      bar.close ()

    else:
      print ("receiving metadata: everything up-to-date.")


  def get_content (self, msgids):
    """
    Get the full email source of the messages that we do not already have

    Returns:
      list of messages which were updated, these have also been updated in Notmuch and
      does not need to be partially upated.

    """

    need_content = []
    for m in msgids:
      if not self.local.has (m):
        need_content.append (m)

    if len (need_content) > 0:

      bar = tqdm (leave = True, total = len(need_content), desc = 'receiving content')

      def _got_msg (m):
        bar.update (1)
        self.local.store (m)

      self.remote.get_messages (need_content, _got_msg, 'raw')

      bar.close ()

    else:
      print ("receiving content: everything up-to-date.")

    return need_content



