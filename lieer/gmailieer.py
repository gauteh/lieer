#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#


import  os, sys
import  argparse
from    oauth2client import tools

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

    args        = parser.parse_args (sys.argv[1:])
    self.args   = args

    self.action           = args.action
    self.dry_run          = args.dry_run
    self.credentials_file = args.credentials
    self.list_labels      = args.list_labels
    self.account          = args.account
    self.force            = args.force

    self.dry_run = True # during early dev

    print ("action:  ", self.action)
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
      for l in self.remote.get_labels ():
        print (l)

      return

    self.local.load_repository ()

    if self.local.state.last_historyId == 0:
      print ("full synchronization (no previous synchronization state)")
      self.full_pull ()

    else:
      print ("partial synchronization.. (hid: %d)" % self.local.state.last_historyId)
      self.partial_pull ()


  def full_pull (self):
    total = 9e9
    LIMIT = 1000

    bar = tqdm (leave = True, total = total)
    bar.set_description ('fetching messages ')

    message_ids = []

    for mset in self.remote.all_messages ():
      (total, mids) = mset

      bar.total = total
      bar.update (len(mids))

      for m in mids:
        message_ids.append (m['id'])

      if len(message_ids) > LIMIT:
        break

    bar.close ()

    self.get_content (message_ids)

  def get_content (self, msgids):
    """
    Get the full email source of the messages that we do not already have
    """

    need_content = []
    for m in msgids:
      if not self.local.has (m):
        need_content.append (m)

    if len (need_content) > 0:

      bar = tqdm (leave = True, total = len(need_content))
      bar.set_description ('receiving messages')

      def _got_msg (rid, resp, excep):
        bar.update (1)
        self.local.store (resp)

      self.remote.get_content (need_content, _got_msg)

      bar.close ()

    else:
      print ("all messages have content")



