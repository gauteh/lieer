"""Methods for translation between Gmail labels and Notmuch tags.

This module defines the class LabelTranslator that provide the
following services:

- Providing default translation of Gmail's 'system labels' (e.g. INBOX
  and SENT) to Notmuch lower case tags.

- Enabling the user to define a translation map to translate between
  Gmail labels and Notmuch tags;

- Translation of a single Gmail label or a list of Gmail labels to their
  corresponding Notmuch tag or list of tags, respectively;

- Translation a Notmuch tag or list of tags to their corresponding
  single Gmail label or a list of Gmail labels, respectively;

- Enabling the user to define a list of python regex patterns by which
  to filter out local Notmuch tags: tags that match any of the
  patterns will be 'local-only' and will not be synced to Gmail;

- Filtering a list of Notmuch tag, thus obtaining a list of only tags
  that should by synced to Gmail;

- Printing detailed information regarding label translation and
  filtering;

Usage:

After creating an instance of LabelTranslator, it is necessary to call
the instance's `load_user_translation` method with an argument that is
a path of a file containing a translation map and filter patterns
definitions.

This file should be a JSON file having the following structure:

{
    "labels_map": {
        "<remote label>" : "<local tag>",
        "<remote label>" : "<local tag>",
        .
        .
        .
    },
    "ignore_patterns": [
        "<pattern>",
        "<pattern>",
        .
        .
        .
    ],
    "label_sep": "<label separator>"
}

Where:

* "label_map" is a mapping between remote labels and local tags.

* "ignore_patterns" is a list of regular expressions; local tags
  matching any of these patterns will not be synced to Gmail.

* "label_sep" is a string that will replace, in local tags, the slash
  used by Gmail as a label/sublabel separator.

For example. a custom translation file might look like this:

{
    "labels_map": {
        "TRASH"     : "deleted",
        "my-remote": "my-local"
    },
    "ignore_patterns": [
        "new",
        "par.*"
    ],
    "label_sep": "::"
}

Using this file will have the following effects:

1. Gmail's 'TRASH' label will be translated to the local tag
   'deleted' and vice versa;

2. Gmail's label 'my-remote' will be translated to the local
   tag 'my-local' and vice versa;

3. The local tag 'new' will not be synced to Gmail;

4. Any local tag matching the regular expression 'par.*' (i.e., any
   tag that starts with 'par') will not be synced to Gmail;

5. The '/' character that separates label/sublabel in Gmail will be
   replaced, in local tags, with the string '::'. For example, a
   Gmail 'foo/bar' label will be translated to the local tag 'foo::bar'.
"""

import os
import json
import re
import notmuch

class LabelTranslator:
    """Translation between Gmail labels and Notmuch tags."""
    
    # the default separator between parent/child labels in Gmail
    GMAIL_LABEL_SEP = '/'

    # the default tranlation of label names between the local
    # (notmuch) system and the remote (Gmail) system. This translation
    # map can be overridden by a user's custom map.
    DEFAULT_REMOTE_TO_LOCAL_MAP = {
        'INBOX'     : 'inbox',
        'SPAM'      : 'spam',
        'TRASH'     : 'trash',
        'UNREAD'    : 'unread',
        'STARRED'   : 'flagged',
        'IMPORTANT' : 'important',
        'SENT'      : 'sent',
        'DRAFT'     : 'draft',
        'CHAT'      : 'chat'
    }

    # set of Gmail's system labels that should not be created by gmi.
    # the labels in this set should be written in all lower case letters.
    SYSTEM_IGNORED_LABELS = {
        'attachment',
        'encrypted',
        'signed',
        # 'new',
        'passed',
        'replied',
        'muted',
        'mute',
        'todo',
        'trash',
        'bin',
        'archive'
    }

    # Note: some tests against Gmail (done by amitramon) show that not
    # all of the labels above are rejected by Gmail.
    #
    # 'attachment', 'encrypted', 'signed', 'passed' and 'replied' seem
    # to be okay.
    #
    # 'mute', 'muted', 'archive' and 'bin' are rejected (in any
    # letter-case). 'bin' is the displayed name for the trash when the
    # language of Gmail web interface is set to UK English, perhaps
    # this is the reason for its rejection.
    #
    # 'new' seems not to be a Gmail reserved label, but I guess is
    # here because of its part in the 'standard' Notmuch workflow. If
    # that is indeed the case, it would be better to leave the
    # decision whether to ignore it or not to the end user.
    #
    # Last but not least, 'trash' is a special case. Gmail accepts
    # 'TRASH' in all upper-case letters, but rejects it in lower or
    # mixed case. This is handled by the code bellow as a special case.

    @staticmethod
    def is_system_ignored_label(label):
        """Test if label should be ignored by the system rules."""
        return label != 'TRASH' \
                        and label.lower() in LabelTranslator.SYSTEM_IGNORED_LABELS

    @staticmethod
    def print_label_translation(label_translation):
        """Pretty print the Gmail-Notmuch translation map."""
        print("Mapping between local tags and remote labels:")
        print('{0:20}        {1:20}'.format('<Remote>', '<Local>'))
        for r,l in label_translation.items():
            print('{0:20} <-->   {1:20}'.format(r, l))

    @staticmethod
    def print_default_translation():
        """Pretty print the default class' Gmail-Notmuch translation map."""
        LabelTranslator.print_label_translation(
            LabelTranslator.DEFAULT_REMOTE_TO_LOCAL_MAP)

    def __init__ (self):
        """Initialize instance."""
        self._label_separator = None
        self._has_user_map = None
        self._remote_to_local_map = dict(LabelTranslator.DEFAULT_REMOTE_TO_LOCAL_MAP)
        self._update_local_to_remote_map()
        self._label_ignore_regex = []

    def _update_local_to_remote_map(self):
        """Update the remote-to-local label translation map."""
        self._local_to_remote_map = {
            v: k for k, v in self._remote_to_local_map.items()}

    def print_info(self):
        """Pretty print detailed information of the Gmail-Notmuch translation.

        The printed information includes:
        - The full translation map between Gmail labels and Notmuch tags;
        - The local label separator (which replaces the Gmail's / separator;
        - The patterns for tags that should not be synced to Gmail;
        - The list of tags that match the above patterns (and hence will not be synced);
        """
        if self.has_user_map:
            print("* User map loaded")
        else:
            print("* No user map loaded, default map will be used")

        LabelTranslator.print_label_translation(self.remote_to_local_map)
        print("")

        if self.label_separator and \
           self.label_separator != LabelTranslator.GMAIL_LABEL_SEP:
            print("Label separator will be modified")
            print('* Local label separator: {}'.format(self.label_separator))
        else:
            print("Label separator will not be modified")

        print("")
        if self.has_label_ignore_regex:
            print("Local notmuch tags matching any of the following user's patterns\n"
                  "will be ignored and won't be synced to your Gmail account:")
            for regex in self.label_ignore_regex:
                print("{}".format(regex.pattern))
        else:
            print("No user's ignore patterns are defined.")

        print("")

        with notmuch.Database() as db:
            ignored_tags = [tag for tag in db.get_all_tags() if self.is_label_ignored(tag)]
            if ignored_tags:
                print("The following local tags will not be synced to your Gmail account:")
                for tag in ignored_tags:
                    print(tag)
            else:
                print("All of your local tags will be synced to your Gmail account")

    def load_user_translation(self, labels_map_fname):
        """Load user translation map form file."""
        with open(labels_map_fname, 'r') as fd:
            user_map = json.load(fd)
            labels_map = user_map.get('labels_map', {})
            if labels_map:
                self._remote_to_local_map.update(labels_map)
                self._has_user_map = True
                
            self._label_separator = user_map.get('label_sep', None)
            ignore_patterns = user_map.get('ignore_patterns', [])
            self._label_ignore_regex = [re.compile(pattern) for pattern in ignore_patterns]

        self._update_local_to_remote_map()

    def local_label_to_remote(self, label):
        """Translate local label to the remote value."""
        label = self._local_to_remote_map.get(label, label)
        if self.label_separator:
            label = label.replace(self.label_separator,
                                  LabelTranslator.GMAIL_LABEL_SEP)

        return label

    def remote_label_to_local(self, label):
        """Translate remote label to the local value."""
        label = self._remote_to_local_map.get(label, label)
        if self.label_separator:
            label = label.replace(LabelTranslator.GMAIL_LABEL_SEP,
                                  self.label_separator)

        return label

    def local_labels_to_remote(self, labels):
        """Translate local labels to their remote values."""
        return [self.local_label_to_remote(label) for label in labels]

    def remote_labels_to_local(self, labels):
        """Translate remote labels to their local values."""
        return [self.remote_label_to_local(label) for label in labels]
         
    def filter_out_tags(self, tags):
        """Remove from 'tags' tags that should not be synced to Gmail.

        Tags should not be synced to Gmail due to either of the following reasons:
        1. the user want them to exist only locally (in notmuch database)
        2. they would get translated into tags that Gmail does not allowed to create
        """
        # filter out non-remote-valid tags (tags that are local-only)
        return [tag for tag in tags if not self.is_label_ignored(tag)]

    def is_label_user_ignored(self, label):
        """Test if a local label should be ignored due to user's pattern.

        Return True if the local `label` should not be synced to Gmail,
        otherwise return False.
        """
        for regex in self._label_ignore_regex:
            if regex.fullmatch(label):
                return True
        return False
    
    def is_label_ignored(self, label):
        """Test if label should be ignored and not synced to Gmail."""
        return self.is_label_user_ignored(label) or \
            LabelTranslator.is_system_ignored_label(self.local_label_to_remote(label))

    @property
    def label_separator(self):
        """Return the label separator."""
        return self._label_separator

    @label_separator.setter
    def label_separator(self, sep):
        """Set the label separator."""
        self._label_separator = sep

    @property
    def has_user_map(self):
        """Test if user map was loaded."""
        return self._has_user_map
    
    @property
    def remote_to_local_map(self):
        """Return the remote to local label translated map."""
        return self._remote_to_local_map

    @property
    def label_ignore_regex(self):
        """Return the label ignore regex list."""
        return self._label_ignore_regex

    @property
    def has_label_ignore_regex(self):
        """Test if a label ignore regex list exists."""
        return bool(self._label_ignore_regex)
