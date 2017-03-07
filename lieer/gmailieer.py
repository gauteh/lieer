#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#


import  os, sys
import  argparse
from    oauth2client import tools
import  googleapiclient
import  notmuch

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

    common = argparse.ArgumentParser (add_help = False)
    common.add_argument ('-c', '--credentials', type = str, default = 'client_secret.json',
        help = 'credentials file for google api (default: client_secret.json)')

    common.add_argument ('-a', '--account', type = str, default = 'me',
        help = 'GMail account to use (default: \'me\' which resolves to currently logged in user)')

    subparsers = parser.add_subparsers (help = 'actions', dest = 'action')

    # pull
    parser_pull = subparsers.add_parser ('pull',
        help = 'pull new e-mail and remote tag-changes',
        description = 'pull',
        parents = [common]
        )

    parser_pull.add_argument ('-t', '--list-labels', action='store_true', default = False,
        help = 'list all remote labels (pull)')

    parser_pull.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to pull (soft limit, GMail may return more), note that this may upset the tally of synchronized messages.')


    parser_pull.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_pull.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Force a full synchronization to be performed')

    parser_pull.add_argument ('-r', '--remove', action = 'store_true',
        default = False, help = 'Remove files locally when they have been deleted remotely')

    parser_pull.set_defaults (func = self.pull)

    # push
    parser_push = subparsers.add_parser ('push', parents = [common],
        description = 'push',
        help = 'push local tag-changes')

    parser_push.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to push, note that this may upset the tally of synchronized messages.')

    parser_push.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_push.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Push even when there has been remote changes (might overwrite remote tag-changes)')

    parser_push.set_defaults (func = self.push)

    # auth
    parser_auth = subparsers.add_parser ('auth', parents = [common],
        description = 'authorize',
        help = 'authorize gmailieer with your GMail account')

    parser_auth.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Re-authorize')

    parser_auth.set_defaults (func = self.authorize)

    # init
    parser_init = subparsers.add_parser ('init', parents = [common],
        description = 'initialize',
        help = 'initialize local e-mail repository')

    parser_init.add_argument ('--replace-slash-with-dot', action = 'store_true', default = False,
        help = 'This will replace \'/\' with \'.\' in gmail labels (make sure you realize the implications)')

    parser_init.set_defaults (func = self.initialize)


    args        = parser.parse_args (sys.argv[1:])
    self.args   = args

    args.func (args)

  def initialize (self, args):
    self.setup (args, False)
    self.local.initialize_repository (args.replace_slash_with_dot)

  def authorize (self, args):
    print ("authorizing..")
    self.setup (args, False)
    self.local.load_repository ()
    self.remote.authorize (args.force)

  def setup (self, args, dry_run = False):
    # common options
    self.dry_run          = dry_run
    self.credentials_file = args.credentials
    self.account          = args.account

    if self.dry_run:
      print ("dry-run: ", self.dry_run)

    self.local  = Local (self)
    self.remote = Remote (self)

  def push (self, args):
    self.setup (args, args.dry_run)

    self.force            = args.force
    self.limit            = args.limit

    self.remote.get_labels ()
    self.local.load_repository ()

    # check if remote repository has changed
    try:
      cur_hist = self.remote.get_current_history_id (self.local.state.last_historyId)
    except googleapiclient.errors.HttpError:
      print ("historyId is too old, full pull required.")
      return

    if cur_hist > self.local.state.last_historyId or cur_hist == -1:
      print ("push: remote has changed, changes may be overwritten (%d > %d)" % (cur_hist, self.local.state.last_historyId))
      if not self.force:
        return

    # loading local changes
    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

      if rev == self.local.state.lastmod:
        print ("everything is up-to-date.")
        return

      qry = "path:%s/** and lastmod:%d..%d" % (self.local.nm_relative, self.local.state.lastmod, rev)

      # print ("collecting changes..: %s" % qry)
      query = notmuch.Query (db, qry)
      total = query.count_messages () # might be destructive here as well
      query = notmuch.Query (db, qry)

      messages = list(query.search_messages ())
      if self.limit is not None and len(messages) > self.limit:
        messages = messages[:self.limit]

      # push changes
      bar = tqdm (leave = True, total = len(messages), desc = 'pushing, 0 changed')
      changed = 0
      for m in messages:
        if self.remote.update (m): changed += 1
        bar.set_description ('pushing, %d changed' % changed)
        bar.update (1)

      bar.close ()

    if not self.dry_run:
      self.local.state.set_lastmod (rev)

  def pull (self, args):
    self.setup (args, args.dry_run)

    self.list_labels      = args.list_labels
    self.force            = args.force
    self.limit            = args.limit
    self.remove           = args.remove

    if self.list_labels:
      if self.remove or self.force or self.limit:
        raise argparse.ArgumentError ("-t cannot be specified together with -f, -r or --limit")
      for l in self.remote.get_labels ().values ():
        print (l)
      return

    self.remote.get_labels () # to make sure label map is initialized
    self.local.load_repository ()

    if self.force:
      print ("pull: full synchronization (forced)")
      self.full_pull ()

    elif self.local.state.last_historyId == 0:
      print ("pull: full synchronization (no previous synchronization state)")
      self.full_pull ()

    elif self.remove:
      print ("pull: full synchronization (removing deleted messages)")
      self.full_pull ()

    else:
      print ("pull: partial synchronization.. (hid: %d)" % self.local.state.last_historyId)
      self.partial_pull ()

  def partial_pull (self):
    # get history
    bar         = None
    message_ids = []
    last_id     = self.remote.get_current_history_id (self.local.state.last_historyId)

    try:
      for mset in self.remote.get_messages_since (self.local.state.last_historyId):
        msgs = mset

        if bar is None:
          bar = tqdm (leave = True, desc = 'fetching changes')

        bar.update (len(msgs))

        for m in msgs:
          labels = m.get('labelIds', [])
          if not 'CHAT' in labels:
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
      # get content for new messages
      updated = self.get_content (message_ids)

      # get updated labels for the rest
      needs_update = list(set(message_ids) - set(updated))
      self.get_meta (needs_update)
    else:
      print ("everything is up-to-date.")

    if not self.dry_run:
      self.local.state.set_last_history_id (last_id)

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
    last_id     = self.remote.get_current_history_id (self.local.state.last_historyId)

    for mset in self.remote.all_messages ():
      (total, mids) = mset

      bar.total = total
      bar.update (len(mids))

      for m in mids:
        message_ids.append (m['id'])

      if self.limit is not None and len(message_ids) >= self.limit:
        break

    bar.close ()

    if self.remove:
      if self.limit and not self.dry_run:
        raise argparse.ArgumentError ('--limit with --remove will cause lots of messages to be deleted')

      # removing files that have been deleted remotely
      all_remote = set (message_ids)
      all_local  = set (self.local.mids.keys ())
      remove     = list(all_local - all_remote)
      bar = tqdm (leave = True, total = len(remove), desc = 'removing deleted')
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        for m in remove:
          self.local.remove (m, db)
          bar.update (1)

      bar.close ()

    if len(message_ids) > 0:
      # get content for new messages
      updated = self.get_content (message_ids)

      # get updated labels for the rest
      needs_update = list(set(message_ids) - set(updated))
      self.get_meta (needs_update)
    else:
      print ("no messages.")

    # set notmuch lastmod time, since we have now synced everything from remote
    # to local

    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

    if not self.dry_run:
      self.local.state.set_lastmod (rev)

    print ('current historyId: %d, current revision: ' % (last_id, rev))

  def get_meta (self, msgids):
    """
    Only gets the minimal message objects in order to check if labels are up-to-date.
    """

    if len (msgids) > 0:

      bar = tqdm (leave = True, total = len(msgids), desc = 'receiving metadata')

      # opening db for whole metadata sync
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        def _got_msg (m):
          nonlocal db
          bar.update (1)
          self.local.update_tags (m, None, db)

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

      bar = tqdm (leave = True, total = len(need_content), desc = 'receiving content ')

      def _got_msg (m):
        bar.update (1)
        # opening db per message since it takes some time to download each one
        with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
          self.local.store (m, db)

      self.remote.get_messages (need_content, _got_msg, 'raw')

      bar.close ()

    else:
      print ("receiving content: everything up-to-date.")

    return need_content



