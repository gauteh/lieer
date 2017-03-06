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


  def __init__ (self, g):
    self.gmailieer = g
    self.CLIENT_SECRET_FILE = g.credentials_file

  def __require_auth__ (func):
    def func_wrap (self, *args, **kwargs):
      if not self.authorized:
        self.authorize ()
      return func (self, *args, **kwargs)
    return func_wrap

  @__require_auth__
  def get_labels (self):
    results = self.service.users ().labels ().list (userId = 'me').execute ()
    labels = results.get ('labels', [])

    return [l['name'] for l in labels]

  @__require_auth__
  def get_messages (self):
    results = self.service.users ().messages ().list (userId = 'me').execute ()
    msgs = results.get ('messages', [])

    return msgs

  def authorize (self):
    self.credentials = self.__get_credentials__ ()
    http = self.credentials.authorize (httplib2.Http())
    self.service = discovery.build ('gmail', 'v1', http = http)
    self.authorized = True

  def __get_credentials__ (self):
    """
    Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir       = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
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

