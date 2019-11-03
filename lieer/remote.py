import os
import time
import httplib2
import googleapiclient
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from pathlib import Path

class Remote:
  SCOPES = 'https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/gmail.modify'
  APPLICATION_NAME   = 'Lieer'
  CLIENT_SECRET_FILE = None
  authorized         = False

  # nothing to see here, move along..
  #
  # no seriously: this is not dangerous to keep here, in order to gain
  # access to an users account the access_token and/or refresh_token must be
  # compromised. these are stored locally.
  #
  # * https://github.com/gauteh/lieer/pull/9
  # * https://stackoverflow.com/questions/25957027/oauth-2-installed-application-client-secret-considerationsgoogle-api/43061998#43061998
  # * https://stackoverflow.com/questions/19615372/client-secret-in-oauth-2-0?rq=1
  #
  OAUTH2_CLIENT_SECRET = {
        "client_id":"753933720722-ju82fu305lii0v9rdo6mf9hj40l5juv0.apps.googleusercontent.com",
        "project_id":"capable-pixel-160614",
        "auth_uri":"https://accounts.google.com/o/oauth2/auth",
        "token_uri":"https://accounts.google.com/o/oauth2/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_secret":"8oudEG0Tvb7YI2V0ykp2Pzz9",
        "redirect_uris":["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
    }

  # Not used, here for documentation purposes
  special_labels = [  'INBOX',
                      'SPAM',
                      'TRASH',
                      'UNREAD',
                      'STARRED',
                      'IMPORTANT',
                      'SENT',
                      'DRAFT',
                      'CHAT',
                      'CATEGORY_PERSONAL',
                      'CATEGORY_SOCIAL',
                      'CATEGORY_PROMOTIONS',
                      'CATEGORY_UPDATES',
                      'CATEGORY_FORUMS'
                    ]

  # these cannot be changed manually
  read_only_labels = set(['SENT', 'DRAFT'])
  read_only_tags   = set(['sent', 'draft'])

  DEFAULT_IGNORE_LABELS = [ 'CATEGORY_PERSONAL',
                            'CATEGORY_SOCIAL',
                            'CATEGORY_PROMOTIONS',
                            'CATEGORY_UPDATES',
                            'CATEGORY_FORUMS',
                          ]

  ignore_labels = set()

  # query to use
  query = '-in:chats'

  not_sync = set (['CHAT'])

  # used to indicate whether all messages that should be updated where updated
  all_updated = True

  # Handle exponential back-offs in non-batch requests.
  _delay     = 0
  _delay_ok  = 0
  MAX_DELAY  = 100
  MAX_CONNECTION_ERRORS = 20

  ## Batch requests should generally be of size 50, and at most 100. Best overall
  ## performance is likely to be at 50 since we will not be throttled.
  ##
  ## * https://developers.google.com/gmail/api/guides/batch
  ## * https://developers.google.com/gmail/api/v1/reference/quota
  BATCH_REQUEST_SIZE     = 50
  MIN_BATCH_REQUEST_SIZE = 1

  class BatchException (Exception):
    pass

  class UserRateException (Exception):
    pass

  class GenericException (Exception):
    pass

  class NoHistoryException (Exception):
    pass

  def __init__ (self, g):
    self.gmailieer = g

    assert g.local.loaded, "local repository must be loaded!"

    self.CLIENT_SECRET_FILE = g.credentials_file
    self.account = g.local.config.account
    self.dry_run = g.dry_run

    self.ignore_labels = self.gmailieer.local.config.ignore_remote_labels

  def __require_auth__ (func):
    def func_wrap (self, *args, **kwargs):
      if not self.authorized:
        self.authorize ()
      return func (self, *args, **kwargs)
    return func_wrap

  def __wait_delay__ (self):
    if self._delay:
      time.sleep (self._delay)

  def __request_done__ (self, success):
    if success:
      if self._delay:
        if self._delay_ok > 10:
          # after 10 good requests, reduce request delay
          self._delay    = self._delay // 2
          self._delay_ok = 0
        else:
          self._delay_ok += 1
    else:
      self._delay    = self._delay * 2 + 1
      self._delay_ok = 0
      if self._delay <= self.MAX_DELAY:
        print ("remote: request failed, increasing delay between requests to: %d s" % self._delay)
      else:
        print ("remote: increased delay to more than maximum of %d s." % self.MAX_DELAY)
        raise Remote.GenericException ("cannot increase delay more to more than maximum %d s" % self.MAX_DELAY)



  @__require_auth__
  def get_labels (self):
    results = self.service.users ().labels ().list (userId = self.account).execute ()
    labels = results.get ('labels', [])

    self.labels     = {}
    self.invlabels  = {}
    for l in labels:
      self.labels[l['id']]      = l['name']
      self.invlabels[l['name']] = l['id']

    return self.labels

  @__require_auth__
  def get_current_history_id (self, start):
    """
    Get the current history id of the mailbox
    """
    try:
      results = self.service.users ().history ().list (userId = self.account, startHistoryId = start).execute ()
      if 'historyId' in results:
        return int(results['historyId'])
      else:
        raise Remote.GenericException ("no historyId field returned")

    except googleapiclient.errors.HttpError:
      # this happens if the original historyId is too old,
      # try to get last message and the historyId from it.
      for mset in self.all_messages (1):
        (total, mset) = mset
        m     = mset[0]
        msg   = self.get_message (m['id'])
        return int(msg['historyId'])

  @__require_auth__
  def get_history_since (self, start):
    """
    Get all changes since start historyId
    """
    self.__wait_delay__ ()
    results = self.service.users ().history ().list (userId = self.account, startHistoryId = start).execute ()
    if 'history' in results:
      self.__request_done__ (True)
      yield results['history']

    # no history field means that there is no history

    while 'nextPageToken' in results:
      pt = results['nextPageToken']

      self.__wait_delay__ ()
      _results = self.service.users ().history ().list (userId = self.account, startHistoryId = start, pageToken = pt).execute ()

      if 'history' in _results:
        self.__request_done__ (True)
        results = _results
        yield results['history']
      else:
        print ("remote: no 'history' when more pages were indicated.")
        if not self.gmailieer.local.config.ignore_empty_history:
          self.__request_done__ (False)
          print ("You can ignore this error with: gmi set --ignore-empty-history (https://github.com/gauteh/lieer/issues/120)")
          raise Remote.NoHistoryException ()
        else:
          self.__request_done__ (True)

  @__require_auth__
  def all_messages (self, limit = None):
    """
    Get a list of all messages
    """

    self.__wait_delay__ ()
    results = self.service.users ().messages ().list (userId = self.account, q = self.query, maxResults = limit, includeSpamTrash = True).execute ()

    if 'messages' in results:
      self.__request_done__ (True)
      yield (results['resultSizeEstimate'], results['messages'])

    # no messages field presumably means no messages

    while 'nextPageToken' in results:
      pt = results['nextPageToken']
      _results = self.service.users ().messages ().list (userId = self.account, pageToken = pt, q = self.query, maxResults = limit, includeSpamTrash = True).execute ()

      if 'messages' in _results:
        self.__request_done__ (True)
        results = _results
        yield (results['resultSizeEstimate'], results['messages'])
      else:
        self.__request_done__ (True)
        print ("remote: warning: no messages when several pages were indicated.")
        break

  @__require_auth__
  def get_messages (self, gids, cb, format):
    """
    Get the messages
    """

    max_req = self.BATCH_REQUEST_SIZE
    req_ok  = 0
    N       = len (gids)
    i       = 0
    j       = 0

    # How much to wait before contacting the remote.
    user_rate_delay     = 0
    # How many requests with the current delay returned ok.
    user_rate_ok        = 0

    conn_errors         = 0

    msg_batch = [] # queue up received batch and send in one go to content / db routine

    def _cb (rid, resp, excep):
      nonlocal j, msg_batch
      if excep is not None:
        if type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 404:
          # message could not be found this is probably a deleted message, spam or draft
          # message since these are not included in the messages.get() query by default.
          print ("remote: could not find remote message: %s!" % gids[j])
          j += 1
          return

        elif type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 400:
          # message id invalid, probably caused by stray files in the mail repo
          print ("remote: message id: %s is invalid! are there any non-lieer files created in the lieer repository?" % gids[j])
          j += 1
          return

        elif type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 403:
          raise Remote.UserRateException (excep)

        else:
          raise Remote.BatchException(excep)
      else:
        j += 1

      msg_batch.append (resp)

    while i < N:
      n = 0
      j = i
      batch = self.service.new_batch_http_request  (callback = _cb)

      while n < max_req and i < N:
        gid = gids[i]
        batch.add (self.service.users ().messages ().get (userId = self.account,
          id = gid, format = format))
        n += 1
        i += 1

      # we wait if there is a user_rate_delay
      if user_rate_delay:
        print ("remote: waiting %.1f seconds.." % user_rate_delay)
        time.sleep (user_rate_delay)

      try:
        batch.execute (http = self.http)

        # gradually reduce user delay if we had 10 ok batches
        user_rate_ok += 1
        if user_rate_delay > 0 and user_rate_ok > 10:
          user_rate_delay = user_rate_delay // 2
          print ("remote: decreasing delay to %s" % user_rate_delay)
          user_rate_ok    = 0

        # gradually increase batch request size if we had 10 ok requests
        req_ok += 1
        if max_req < self.BATCH_REQUEST_SIZE and req_ok > 10:
          max_req = min (max_req * 2, self.BATCH_REQUEST_SIZE)
          print ("remote: increasing batch request size to: %d" % max_req)
          req_ok  = 0

        conn_errors = 0

      except Remote.UserRateException as ex:
        user_rate_delay = user_rate_delay * 2 + 1
        print ("remote: user rate error, increasing delay to %s" % user_rate_delay)
        user_rate_ok = 0

        i = j # reset

      except Remote.BatchException as ex:
        max_req = max_req // 2
        req_ok  = 0

        if max_req >= self.MIN_BATCH_REQUEST_SIZE:
          i = j # reset
          print ("remote: reducing batch request size to: %d" % max_req)
        else:
          max_req = self.MIN_BATCH_REQUEST_SIZE
          raise Remote.BatchException ("cannot reduce request any further")

      except ConnectionError as ex:
        print ("connection failed, re-trying:", ex)
        i = j # reset
        conn_errors += 1

        time.sleep (1)

        if conn_errors > self.MAX_CONNECTION_ERRORS:
          print ("too many connection errors")
          raise

      finally:
        # handle batch
        if len(msg_batch) > 0:
          cb (msg_batch)
          msg_batch.clear ()

  @__require_auth__
  def get_message (self, gid, format = 'minimal'):
    """
    Get a single message
    """
    self.__wait_delay__ ()
    try:
      result = self.service.users ().messages ().get (userId = self.account,
          id = gid, format = format).execute ()

    except googleapiclient.errors.HttpError as excep:
      if excep.resp.status == 403 or excep.resp.status == 500:
        self.__request_done__ (False)
        return self.get_message (gid, format)
      else:
        raise

    self.__request_done__ (True)

    return result

  def authorize (self, reauth = False):
    if reauth:
      credential_path = self.gmailieer.local.credentials_f
      if os.path.exists (credential_path):
        print ("reauthorizing..")
        os.unlink (credential_path)

    self.credentials = self.__get_credentials__ ()

    timeout = self.gmailieer.local.config.timeout
    if timeout == 0: timeout = None

    self.http = self.credentials.authorize (httplib2.Http(timeout = timeout))
    self.service = discovery.build ('gmail', 'v1', http = self.http)
    self.authorized = True

  def __get_credentials__ (self):
    """
    Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    credential_path = self.gmailieer.local.credentials_f


    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
      if self.CLIENT_SECRET_FILE is not None:
        # use user-provided client_secret
        print ("auth: using user-provided api id and secret")
        if not os.path.exists (self.CLIENT_SECRET_FILE):
          raise Remote.GenericException ("error: no secret client API key file found for authentication at: %s" % self.CLIENT_SECRET_FILE)

        flow = client.flow_from_clientsecrets(self.CLIENT_SECRET_FILE, self.SCOPES)
        flow.user_agent = self.APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags = self.gmailieer.args)

      else:
        # use default id and secret
        client_id     = self.OAUTH2_CLIENT_SECRET['client_id']
        client_secret = self.OAUTH2_CLIENT_SECRET['client_secret']
        redirect_uri  = self.OAUTH2_CLIENT_SECRET['redirect_uris']
        user_agent    = self.APPLICATION_NAME
        auth_uri      = self.OAUTH2_CLIENT_SECRET['auth_uri']
        token_uri     = self.OAUTH2_CLIENT_SECRET['token_uri']

        flow = client.OAuth2WebServerFlow(client_id, client_secret, self.SCOPES,
                                       redirect_uri=redirect_uri,
                                       user_agent=user_agent,
                                       auth_uri=auth_uri,
                                       token_uri=token_uri)
        credentials = tools.run_flow(flow, store, flags = self.gmailieer.args)

      print('credentials stored in ' + credential_path)
    return credentials

  @__require_auth__
  def update (self, gmsg, nmsg, last_hist, force):
    """
    Gets a message and checks which labels it should add and which to delete, returns a
    operation which can be submitted in a batch.
    """

    # DUPLICATES:
    #
    # there might be duplicate messages across gmail accounts with the same
    # message id, messages outside the repository are skipped. if there are
    # duplicate messages in the same account they are all updated. if one of
    # them is changed remotely it will not be updated, any changes on it will
    # then be pulled back on next pull overwriting the changes that might have
    # been pushed on another duplicate. this will again trigger a change on the
    # next push for the other duplicates. after the 2nd pull things should
    # settle unless there's been any local changes.
    #

    gid    = gmsg['id']

    found = False
    for f in nmsg.get_filenames ():
      if gid in f:
        found = True

    # this can happen if a draft is edited remotely and is synced before it is sent. we'll
    # just skip it and it should be resolved on the next pull.
    if not found:
      print ("update: gid does not match any file name of message, probably a draft, skipping: %s" % gid)
      return None

    glabels = gmsg.get('labelIds', [])

    # translate labels. Remote.get_labels () must have been called first
    labels = []
    for l in glabels:
      ll = self.labels.get(l, None)

      if ll is None and not self.gmailieer.local.config.drop_non_existing_label:
        err = "error: GMail supplied a label that there exists no record for! You can `gmi set --drop-non-existing-labels` to work around the issue (https://github.com/gauteh/lieer/issues/48)"
        print (err)
        raise Remote.GenericException (err)
      elif ll is None:
        pass # drop
      else:
        labels.append (ll)

    # remove ignored labels
    labels = set(labels)
    labels = labels - self.ignore_labels

    # translate to notmuch tags
    labels = [self.gmailieer.local.translate_labels.get (l, l) for l in labels]

    # this is my weirdness
    if self.gmailieer.local.config.replace_slash_with_dot:
      labels = [l.replace ('/', '.') for l in labels]

    labels = set(labels)

    # current tags
    tags = set(nmsg.get_tags ())

    # remove special notmuch tags
    tags = tags - self.gmailieer.local.ignore_labels

    add = list((tags - labels) - self.read_only_tags)
    rem = list((labels - tags) - self.read_only_tags)

    # translate back to gmail labels
    add = [self.gmailieer.local.labels_translate.get (k, k) for k in add]
    rem = [self.gmailieer.local.labels_translate.get (k, k) for k in rem]

    if self.gmailieer.local.config.replace_slash_with_dot:
      add = [a.replace ('.', '/') for a in add]
      rem = [r.replace ('.', '/') for r in rem]

    if len(add) > 0 or len(rem) > 0:
      # check if this message has been changed remotely since last pull
      hist_id = int(gmsg['historyId'])
      if hist_id > last_hist:
        if not force:
          print ("update: remote has changed, will not update: %s (add: %s, rem: %s) (%d > %d)" % (gid, add, rem, hist_id, last_hist))
          self.all_updated = False
          return None

      if 'TRASH' in add:
        if 'SPAM' in add:
          print ("update: %s: Trying to add both TRASH and SPAM, dropping SPAM (add: %s, rem: %s)" % (gid, add, rem))
          add.remove('SPAM')
        if 'INBOX' in add:
          print ("update: %s: Trying to add both TRASH and INBOX, dropping INBOX (add: %s, rem: %s)" % (gid, add, rem))
          add.remove('INBOX')
      elif 'SPAM' in add:
        if 'INBOX' in add:
          print ("update: %s: Trying to add both SPAM and INBOX, dropping INBOX (add: %s, rem: %s)" % (gid, add, rem))
          add.remove('INBOX')

      if self.dry_run:
        print ("(dry-run) gid: %s: add: %s, remove: %s" % (gid, str(add), str(rem)))
        return None
      else:
        return self.__push_tags__ (gid, add, rem)

    else:
      return None

  @__require_auth__
  def __push_tags__ (self, gid, add, rem):
    """
    Push message changes
    """

    _add = []
    for a in add:
      _a = self.invlabels.get (a, None)
      if _a is None:
        # label does not exist
        (lid, ll) = self.__create_label__ (a)
        self.labels[lid]   = ll
        self.invlabels[ll] = lid
        _add.append (lid)
      else:
        _add.append (_a)

    _rem = [self.invlabels[r] for r in rem]

    body = { 'addLabelIds'    : _add,
             'removeLabelIds' : _rem }

    return self.service.users ().messages ().modify (userId = self.account,
          id = gid, body = body)

  @__require_auth__
  def push_changes (self, actions, cb):
    """
    Push label changes
    """
    max_req = self.BATCH_REQUEST_SIZE
    N       = len (actions)
    i       = 0
    j       = 0

    # How much to wait before contacting the remote.
    user_rate_delay     = 0
    # How many requests with the current delay returned ok.
    user_rate_ok        = 0

    def _cb (rid, resp, excep):
      nonlocal j
      if excep is not None:
        if type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 404:
          # message could not be found this is probably a deleted message, spam or draft
          # message since these are not included in the messages.get() query by default.
          print ("remote: could not find remote message: %s!" % gids[j])
          j += 1
          return

        elif type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 400:
          # message id invalid, probably caused by stray files in the mail repo
          print ("remote: message id: %s is invalid! are there any non-lieer files created in the lieer repository?" % gids[j])
          j += 1
          return

        elif type(excep) is googleapiclient.errors.HttpError and excep.resp.status == 403:
          raise Remote.UserRateException (excep)

        else:
          raise Remote.BatchException(excep)
      else:
        j += 1

      cb (resp)

    while i < N:
      n = 0
      j = i
      batch = self.service.new_batch_http_request  (callback = _cb)

      while n < max_req and i < N:
        a = actions[i]
        batch.add (a)
        n += 1
        i += 1

      # we wait if there is a user_rate_delay
      if user_rate_delay:
        print ("remote: waiting %.1f seconds.." % user_rate_delay)
        time.sleep (user_rate_delay)

      try:
        batch.execute (http = self.http)

        # gradually reduce if we had 10 ok batches
        user_rate_ok += 1
        if user_rate_ok > 10:
          user_rate_delay = user_rate_delay // 2
          user_rate_ok    = 0

      except Remote.UserRateException as ex:
        user_rate_delay = user_rate_delay * 2 + 1
        print ("remote: user rate error, increasing delay to %s" % user_rate_delay)
        user_rate_ok = 0

        i = j # reset

      except Remote.BatchException as ex:
        if max_req > self.MIN_BATCH_REQUEST_SIZE:
          max_req = max_req / 2
          i = j # reset
          print ("reducing batch request size to: %d" % max_req)
        else:
          raise Remote.BatchException ("cannot reduce request any further")

  @__require_auth__
  def __create_label__ (self, l):
    """
    Creates a new label

    Returns:

      (labelId, label)

    """

    print ("push: creating label: %s.." % l)

    label  = { 'messageListVisibility' : 'show',
               'name' : l,
               'labelListVisibility' : 'labelShow',
               }

    if not self.dry_run:
      self.__wait_delay__ ()
      try:
        lr = self.service.users ().labels ().create (userId = self.account, body = label).execute ()

        return (lr['id'], l)

      except googleapiclient.errors.HttpError as excep:
        if excep.resp.status == 403 or excep.resp.status == 500:
          self.__request_done__ (False)
          return self.__create_label__ (l)
        else:
          raise

      self.__request_done__ (True)

    else:
      return (None, None)


