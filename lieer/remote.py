import os
import httplib2
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

class Remote:
  SCOPES = 'https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.labels'
  APPLICATION_NAME   = 'Gmailieer'
  CLIENT_SECRET_FILE = None
  authorized         = False

  special_labels = [  'INBOX',
                      'SPAM',
                      'TRASH',
                      'UNREAD',
                      'STARRED',
                      'IMPORTANT',
                      'SENT',
                      'DRAFT',
                      'CATEGORY_PERSONAL',
                      'CATEGORY_SOCIAL',
                      'CATEGORY_PROMOTIONS',
                      'CATEGORY_UPDATES',
                      'CATEGORY_FORUMS'
                    ]

  # these cannot be changed manually
  read_only_labels = [ 'SENT', 'DRAFT' ]

  class BatchException:
    pass

  def __init__ (self, g):
    self.gmailieer = g
    self.CLIENT_SECRET_FILE = g.credentials_file
    self.account = g.account

  def __require_auth__ (func):
    def func_wrap (self, *args, **kwargs):
      if not self.authorized:
        self.authorize ()
      return func (self, *args, **kwargs)
    return func_wrap

  @__require_auth__
  def get_labels (self):
    results = self.service.users ().labels ().list (userId = self.account).execute ()
    labels = results.get ('labels', [])

    return [l['name'] for l in labels]

  @__require_auth__
  def all_messages (self):
    """
    Get a list of all messages
    """
    results = self.service.users ().messages ().list (userId = self.account).execute ()
    if 'messages' in results:
      yield (results['resultSizeEstimate'], results['messages'])

    while 'nextPageToken' in results:
      pt = results['nextPageToken']
      results = self.service.users ().messages ().list (userId = self.account, pageToken = pt).execute ()

      yield (results['resultSizeEstimate'], results['messages'])

  @__require_auth__
  def get_content (self, mids, cb):
    """
    Get the content for all mids
    """

    def _cb (rid, resp, excep):
      if excep is not None:
        raise Remote.BatchException (excep)

      cb (resp)

    # TODO: limit to 1000 requests
    max_req = 10
    N       = len (mids)
    i       = 0

    while i < N:
      n = 0
      batch = self.service.new_batch_http_request  (callback = _cb)

      while n < max_req and i < N:
        mid = mids[i]
        batch.add (self.service.users ().messages ().get (userId = self.account,
          id = mid, format = 'raw'))
        n += 1
        i += 1

      batch.execute (http = self.http)


  def authorize (self, reauth = False):
    if reauth:
      credential_dir = os.path.join(self.gmailieer.home, 'credentials')
      credential_path = os.path.join(credential_dir,
          'gmailieer.json')
      if os.path.exists (credential_path):
        print ("reauthorizing..")
        os.unlink (credential_path)

    self.credentials = self.__get_credentials__ ()
    self.http = self.credentials.authorize (httplib2.Http())
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
    credential_dir = os.path.join(self.gmailieer.home, 'credentials')
    if not os.path.exists(credential_dir):
      os.makedirs(credential_dir)

    credential_path = os.path.join(credential_dir,
        'gmailieer.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
      flow = client.flow_from_clientsecrets(self.CLIENT_SECRET_FILE, self.SCOPES)
      flow.user_agent = self.APPLICATION_NAME
      credentials = tools.run_flow(flow, store, flags = self.gmailieer.args)
      print('Storing credentials to ' + credential_path)
    return credentials

