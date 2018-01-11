import imaplib
import base64

class Gimap:
  """
  * https://github.com/google/gmail-oauth2-tools/blob/master/python/oauth2.py#L255
  * https://developers.google.com/gmail/imap/imap-extensions
  """

  remote = None
  conn   = None

  class GimapException (Exception):
    pass

  def __init__(self, remote):
    self.remote = remote

  def generate_xoauth (self):
    """
    user is email
    """

    username = self.remote.gmailieer.local.state.account

    if username == 'me':
      raise GimapException ("account must be specified, cannot use 'me'")

    access_token = self.remote.credentials.access_token

    auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
    return auth_string

  def connect (self):
    auth_str = self.generate_xoauth ()

    self.conn = imaplib.IMAP4_SSL ('imap.gmail.com')
    # self.conn.debug = 4
    self.conn.authenticate ('XOAUTH2', lambda x: auth_str)

  def disconnect (self):
    if self.conn is not None:
      self.conn.close ()

  def get_messages (self, messages, msg_cb):
    # get name of all e-mail folder
    typ, lst = self.conn.list()

    for l in lst:
      if b'\All' in l:
        ri = l.rfind (b'"[Gmail]/')
        alle = l[ri:]

    self.conn.select(alle)

    for m in messages:
      # get UID
      typ, msgnums = self.conn.search(None, 'X-GM-MSGID %d' % int(m, 16))

      if typ != 'OK':
        raise GimapException ('Failed to get GM-MSGID: %s' % m)

      # fetch message
      for num in msgnums[0].split():
        typ, data = self.conn.fetch (num, '(RFC822)')

        if typ != 'OK':
          raise GimapException ('Failed to fetch message GM-MSGID: %s' % m)

        msg_cb (data[0][1], m)



