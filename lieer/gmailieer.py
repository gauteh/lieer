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

    subparsers = parser.add_subparsers (help = 'actions', dest = 'action')
    subparsers.required = True

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
        default = False, help = 'Remove files locally when they have been deleted remotely (forces full sync)')

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

    # sync
    parser_sync = subparsers.add_parser ('sync', parents = [common],
        description = 'sync',
        help = 'sync changes (flags have same meaning as for push and pull)')

    parser_sync.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to sync, note that this may upset the tally of synchronized messages.')

    parser_sync.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_sync.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Push even when there has been remote changes, and force a full remote-to-local synchronization')

    parser_sync.add_argument ('-r', '--remove', action = 'store_true',
        default = False, help = 'Remove files locally when they have been deleted remotely (forces full sync)')

    parser_sync.set_defaults (func = self.sync)

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
        help = 'initialize local e-mail repository and authorize')

    parser_init.add_argument ('--replace-slash-with-dot', action = 'store_true', default = False,
        help = 'This will replace \'/\' with \'.\' in gmail labels (make sure you realize the implications)')

    parser_init.add_argument ('--no-auth', action = 'store_true', default = False,
        help = 'Do not immediately authorize as well (you will need to run \'auth\' afterwards)')

    parser_init.add_argument ('account', type = str, help = 'GMail account to use')

    parser_init.set_defaults (func = self.initialize)


    # set option
    parser_set = subparsers.add_parser ('set',
        description = 'set option',
        help = 'set options for repository')

    parser_set.add_argument ('-t', '--timeout', type = float,
        default = None, help = 'Set HTTP timeout in seconds (0 means system timeout)')

    parser_set.add_argument ('--replace-slash-with-dot', action = 'store_true', default = False,
        help = 'This will replace \'/\' with \'.\' in gmail labels (make sure you realize the implications)')

    parser_set.set_defaults (func = self.set)


    args        = parser.parse_args (sys.argv[1:])
    self.args   = args

    args.func (args)

  def initialize (self, args):
    self.setup (args, False)
    self.local.initialize_repository (args.replace_slash_with_dot, args.account)

    if not args.no_auth:
      self.local.load_repository ()
      self.remote = Remote (self)

      try:
        self.remote.authorize ()
      except:
        print ("")
        print ("")
        print ("init: repository is set up, but authorization failed. re-run 'gmi auth' with proper parameters to complete authorization")
        print ("")
        print ("")
        print ("")
        print ("")
        raise

  def authorize (self, args):
    print ("authorizing..")
    self.setup (args, False, True)
    self.remote.authorize (args.force)

  def setup (self, args, dry_run = False, load = False):
    # common options
    self.dry_run          = dry_run
    self.credentials_file = args.credentials

    if self.dry_run:
      print ("dry-run: ", self.dry_run)

    self.local  = Local (self)
    if load:
      self.local.load_repository ()
      self.remote = Remote (self)

  def sync (self, args):
    self.setup (args, args.dry_run, True)
    self.force            = args.force
    self.limit            = args.limit
    self.list_labels      = False

    self.remote.get_labels ()

    # will try to push local changes, this operation should not make
    # any changes to the local store or any of the file names.
    self.push (args, True)

    # will pull in remote changes, overwriting local changes and effectively
    # resolving any conflicts.
    self.pull (args, True)

  def push (self, args, setup = False):
    if not setup:
      self.setup (args, args.dry_run, True)

      self.force            = args.force
      self.limit            = args.limit

      self.remote.get_labels ()

    # loading local changes
    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

      if rev == self.local.state.lastmod:
        print ("push: everything is up-to-date.")
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
        r = self.remote.update (m, self.local.state.last_historyId, self.force)
        if r:
          changed += 1
          bar.set_description ('pushing, %d changed' % changed)
        bar.update (1)

      bar.close ()

    if not self.remote.all_updated:
      # will not set last_mod, this forces messages to be pushed again at next push
      print ("push: not all changes could be pushed, will re-try at next push.")
    else:
      # TODO: Once I get more confident we might set the last history Id here to
      # avoid pulling back in the changes we just pushed. Currently there's a race
      # if something is modified remotely (new email, changed tags), so this might
      # not really be possible.
      pass

    if not self.dry_run and self.remote.all_updated:
      self.local.state.set_lastmod (rev)

    print ("remote historyId: %d" % self.remote.get_current_history_id (self.local.state.last_historyId))

  def pull (self, args, setup = False):
    if not setup:
      self.setup (args, args.dry_run, True)

      self.list_labels      = args.list_labels
      self.force            = args.force
      self.limit            = args.limit

      self.remote.get_labels () # to make sure label map is initialized

    self.remove           = args.remove

    if self.list_labels:
      if self.remove or self.force or self.limit:
        raise argparse.ArgumentError ("-t cannot be specified together with -f, -r or --limit")
      for l in self.remote.labels.values ():
        print (l)
      return

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
    history     = []
    last_id     = self.remote.get_current_history_id (self.local.state.last_historyId)

    try:
      for hist in self.remote.get_history_since (self.local.state.last_historyId):
        history.extend (hist)

        if bar is None:
          bar = tqdm (leave = True, desc = 'fetching changes')

        bar.update (len(hist))

        if self.limit is not None and len(history) >= self.limit:
          break

    except googleapiclient.errors.HttpError:
      if bar is not None: bar.close ()
      print ("pull: historyId is too old, full sync required.")
      self.full_pull ()
      return

    if bar is not None: bar.close ()

    # figure out which changes need to be applied
    added_messages   = [] # added messages, if they are later deleted they will be
                          # removed from this list

    deleted_messages = [] # deleted messages, if they are later added they will be
                          # removed from this list

    labels_changed   = [] # list of messages which have had their label changed
                          # the entry will be the last and most recent one in case
                          # of multiple changes. if the message is either deleted
                          # or added after the label change it will be removed from
                          # this list.

    def remove_from_all (m):
      nonlocal added_messages, deleted_messages, labels_changed
      remove_from_list (deleted_messages, m)
      remove_from_list (labels_changed, m)
      remove_from_list (added_messages, m)

    def remove_from_list (lst, m):
      e = next ((e for e in lst if e['id'] ==  m['id']), None)
      if e is not None:
        lst.remove (e)
        return True
      return False

    if len(history) > 0:
      bar = tqdm (total = len(history), leave = True, desc = 'resolving changes')
    else:
      bar = None

    for h in history:
      if 'messagesAdded' in h:
        for m in h['messagesAdded']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            remove_from_all (mm)
            added_messages.append (mm)

      if 'messagesDeleted' in h:
        for m in h['messagesDeleted']:
          mm = m['message']
          # might silently fail to delete this
          remove_from_all (mm)
          if self.local.has (mm['id']):
            deleted_messages.append (mm)

      # messages that are subsequently deleted by a later action will be removed
      # from either labels_changed or added_messages.
      if 'labelsAdded' in h:
        for m in h['labelsAdded']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            new = remove_from_list (added_messages, mm) or not self.local.has (mm['id'])
            remove_from_list (labels_changed, mm)
            if new:
              added_messages.append (mm) # needs to fetched
            else:
              labels_changed.append (mm)
          else:
            # in case a not_sync tag has been added to a scheduled message
            remove_from_list (added_messages, mm)
            remove_from_list (labels_changed, mm)

            if self.local.has (mm['id']):
              remove_from_list (deleted_messages, mm)
              deleted_messages.append (mm)

      if 'labelsRemoved' in h:
        for m in h['labelsRemoved']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            new = remove_from_list (added_messages, mm) or not self.local.has (mm['id'])
            remove_from_list (labels_changed, mm)
            if new:
              added_messages.append (mm) # needs to fetched
            else:
              labels_changed.append (mm)
          else:
            # in case a not_sync tag has been added
            remove_from_list (added_messages, mm)
            remove_from_list (labels_changed, mm)

            if self.local.has (mm['id']):
              remove_from_list (deleted_messages, mm)
              deleted_messages.append (mm)

      bar.update (1)

    if bar: bar.close ()

    changed = False
    # fetching new messages
    if len (added_messages) > 0:
      message_ids = [m['id'] for m in added_messages]
      updated     = self.get_content (message_ids)

      # updated labels for the messages that already existed
      needs_update_mid = list(set(message_ids) - set(updated))
      needs_update = [m for m in added_messages if m['id'] in needs_update_mid]
      labels_changed.extend (needs_update)

      changed = True

    if len (deleted_messages) > 0:
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        for m in tqdm (deleted_messages, leave = True, desc = 'removing messages'):
          self.local.remove (m['id'], db)

      changed = True

    if len (labels_changed) > 0:
      lchanged = 0
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        bar = tqdm (total = len(labels_changed), leave = True, desc = 'updating tags (0Δ)')
        for m in labels_changed:
          r = self.local.update_tags (m, None, db)
          if r:
            lchanged += 1
            bar.set_description ('updating tags (%dΔ)' % lchanged)

          bar.update (1)
        bar.close ()


      changed = True

    if not changed:
      print ("pull: everything is up-to-date.")

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
      print ("pull: no messages.")

    # set notmuch lastmod time, since we have now synced everything from remote
    # to local
    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

    if not self.dry_run:
      self.local.state.set_lastmod (rev)
      self.local.state.set_last_history_id (last_id)

    print ('current historyId: %d, current revision: %d' % (last_id, rev))

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

  def set (self, args):
    args.credentials = '' # for setup()
    self.setup (args, False, True)

    if args.timeout is not None:
      self.local.state.set_timeout (args.timeout)

    if args.replace_slash_with_dot:
      self.local.state.set_replace_slash_with_dot (args.replace_slash_with_dot)

    print ("Repository info:")
    print ("Account ...........: %s" % self.local.state.account)
    print ("Timeout ...........: %f" % self.local.state.timeout)
    print ("historyId .........: %d" % self.local.state.last_historyId)
    print ("lastmod ...........: %d" % self.local.state.lastmod)
    print ("replace . with / ..:", self.local.state.replace_slash_with_dot)



