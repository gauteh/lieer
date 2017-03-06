#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#


import  os, sys
import  argparse
from    oauth2client import tools

from tqdm import tqdm

from .remote import *
from .local  import *

class Gmailieer:
  def __init__ (self):
    xdg_data_home = os.getenv ('XDG_DATA_HOME', os.path.expanduser ('~/.local/share'))
    self.home = os.path.join (xdg_data_home, 'gmailieer')

  def main (self):
    parser = argparse.ArgumentParser ('Gmailieer', parents = [tools.argparser])
    self.parser = parser

    parser.add_argument ('action', choices = ['pull', 'push', 'auth'],
        help = 'pull: get new e-mail and remote tag-changes, push: push local tag-changes, auth: authorize gmailieer with account')

    parser.add_argument ('-c', '--credentials', type = str, default = 'client_secret.json',
        help = 'credentials file for google api (default: client_secret.json)')

    parser.add_argument ('-d', '--dry-run', action='store_true', default = False,
        help = 'do not make any changes')

    parser.add_argument ('-t', '--list-labels', action='store_true', default = False,
        help = 'list all remote labels')

    parser.add_argument ('-a', '--account', type = str, default = 'me',
        help = 'GMail account to use (default: me, currently logged in user)')

    parser.add_argument ('-f', '--force', action = 'store_true', default = False,
        help = 'Force action')

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

    self.remote = Remote (self)

    if self.action == 'pull':
      self.pull ()

    elif self.action == 'auth':
      print ("authorizing..")
      self.remote.authorize (self.force)

    elif self.action == 'push':
      raise NotImplmentedError ()




  def pull (self):
    if self.list_labels:
      for l in self.remote.get_labels ():
        print (l)

      return

    msgs = self.remote.get_messages ()
    for m in msgs:
      print (m['id'])



