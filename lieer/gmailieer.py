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
    pass

  def main (self):
    parser = argparse.ArgumentParser ('Gmailieer', parents = [tools.argparser])
    self.parser = parser

    parser.add_argument ('action', choices = ['fetch', 'push-tags'],
        help = 'fetch: get new e-mail and remote tag-changes, push-tags: push local tag-changes')

    parser.add_argument ('-c', '--credentials', type = str, default = 'client_secret.json',
        help = 'credentials file for google api (default: client_secret.json)')

    parser.add_argument ('-d', '--dry-run', action='store_true', default = False,
        help = 'do not make any changes')

    parser.add_argument ('-l', '--list-labels', action='store_true', default = False,
        help = 'list all labels')

    args = parser.parse_args (sys.argv[1:])
    self.args = args

    self.action  = args.action
    self.dry_run = args.dry_run
    self.credentials_file = args.credentials
    self.list_labels = args.list_labels

    print ("action:  ", self.action)
    if self.dry_run:
      print ("dry-run: ", self.dry_run)

    self.remote = Remote (self)

    if self.action == 'fetch':
      self.fetch ()


  def fetch (self):
    if self.list_labels:
      print ("labels:")
      print ("-------")
      for l in self.remote.get_labels ():
        print (l)

      return

    msgs = self.remote.get_messages ()
    for m in msgs:
      print (m['id'])



