#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#


import os, sys
import argparse

class Gmailieer:
  def __init__ (self):
    pass

  def main (self):
    parser = argparse.ArgumentParser ('Gmailieer')

    parser.add_argument ('action', choices = ['fetch', 'push-tags'],
        help = 'fetch: get new e-mail and remote tag-changes, push-tags: push local tag-changes')

    parser.add_argument ('-d', '--dry-run',  action='store_true', default = False,
        help = 'do not make any changes')

    args = parser.parse_args (sys.argv[1:])

    self.action  = args.action
    self.dry_run = args.dry_run

    print ("action:  ", self.action)
    print ("dry-run: ", self.dry_run)

