# Copyright © 2020  Gaute Hope <eg@gaute.vetsj.com>
#
# This file is part of Lieer.
#
# Lieer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import fcntl
import json
import base64
from pathlib import Path
import tempfile

import notmuch2
from .remote import Remote


class Local:
    wd = None
    loaded = False

    # NOTE: Update README when changing this map.
    translate_labels_default = {
        "INBOX": "inbox",
        "SPAM": "spam",
        "TRASH": "trash",
        "UNREAD": "unread",
        "STARRED": "flagged",
        "IMPORTANT": "important",
        "SENT": "sent",
        "DRAFT": "draft",
        "CHAT": "chat",
        "CATEGORY_PERSONAL": "personal",
        "CATEGORY_SOCIAL": "social",
        "CATEGORY_PROMOTIONS": "promotions",
        "CATEGORY_UPDATES": "updates",
        "CATEGORY_FORUMS": "forums",
    }

    labels_translate_default = {v: k for k, v in translate_labels_default.items()}

    ignore_labels = set(
        [
            "archive",
            "arxiv",
            "attachment",
            "encrypted",
            "signed",
            "passed",
            "replied",
            "muted",
            "mute",
            "todo",
            "Trash",
            "voicemail",
        ]
    )

    def update_translation(self, remote, local):
        """
        Convenience function to ensure both maps (remote -> local and local -> remote)
        get updated when you update a translation.
        """
        # Did you reverse the parameters?
        assert remote in self.translate_labels
        self.translate_labels[remote] = local
        self.labels_translate = {v: k for k, v in self.translate_labels.items()}

    def update_translation_list_with_overlay(self, translation_list_overlay):
        """
        Takes a list with an even number of items. The list is interpreted as a list of pairs
        of (remote, local), where each member of each pair is a string. Each pair is added to the
        translation, overwriting the translation if one already exists (in either direction).
        If either the remote or the local labels are non-unique, the later items in the list will
        overwrite the earlier ones in the direction in which the source is non-unique (for example,
        ["a", "1", "b", 2", "a", "3"] will yield {'a': 3, 'b': 2} in one direction and {1: 'a', 2: 'b', 3: 'a'}
        in the other).
        """

        if len(translation_list_overlay) % 2 != 0:
            raise Exception(
                f"Translation list overlay must have an even number of items: {translation_list_overlay}"
            )

        for i in range(0, len(translation_list_overlay), 2):
            (remote, local) = (
                translation_list_overlay[i],
                translation_list_overlay[i + 1],
            )
            self.translate_labels[remote] = local
            self.labels_translate[local] = remote

    class RepositoryException(Exception):
        pass

    class Config:
        replace_slash_with_dot = False
        account = None
        timeout = 10 * 60
        drop_non_existing_label = False
        ignore_empty_history = False
        ignore_tags = None
        ignore_remote_labels = None
        remove_local_messages = True
        file_extension = None
        local_trash_tag = "trash"
        translation_list_overlay = None

        def __init__(self, config_f):
            self.config_f = config_f

            if os.path.exists(self.config_f):
                try:
                    with open(self.config_f, "r") as fd:
                        self.json = json.load(fd)
                except json.decoder.JSONDecodeError:
                    print("Failed to decode config file `{}`.".format(self.config_f))
                    raise
            else:
                self.json = {}

            self.replace_slash_with_dot = self.json.get("replace_slash_with_dot", False)
            self.account = self.json.get("account", "me")
            self.timeout = self.json.get("timeout", 10 * 60)
            self.drop_non_existing_label = self.json.get(
                "drop_non_existing_label", False
            )
            self.ignore_empty_history = self.json.get("ignore_empty_history", False)
            self.remove_local_messages = self.json.get("remove_local_messages", True)
            self.ignore_tags = set(self.json.get("ignore_tags", []))
            self.ignore_remote_labels = set(
                self.json.get("ignore_remote_labels", Remote.DEFAULT_IGNORE_LABELS)
            )
            self.file_extension = self.json.get("file_extension", "")
            self.local_trash_tag = self.json.get("local_trash_tag", "trash")
            self.translation_list_overlay = self.json.get(
                "translation_list_overlay", []
            )

        def write(self):
            self.json = {}

            self.json["replace_slash_with_dot"] = self.replace_slash_with_dot
            self.json["account"] = self.account
            self.json["timeout"] = self.timeout
            self.json["drop_non_existing_label"] = self.drop_non_existing_label
            self.json["ignore_empty_history"] = self.ignore_empty_history
            self.json["ignore_tags"] = list(self.ignore_tags)
            self.json["ignore_remote_labels"] = list(self.ignore_remote_labels)
            self.json["remove_local_messages"] = self.remove_local_messages
            self.json["file_extension"] = self.file_extension
            self.json["local_trash_tag"] = self.local_trash_tag
            self.json["translation_list_overlay"] = self.translation_list_overlay

            if os.path.exists(self.config_f):
                shutil.copyfile(self.config_f, self.config_f + ".bak")

            with tempfile.NamedTemporaryFile(
                mode="w+", dir=os.path.dirname(self.config_f), delete=False
            ) as fd:
                json.dump(self.json, fd)
                os.rename(fd.name, self.config_f)

        def set_account(self, a):
            self.account = a
            self.write()

        def set_timeout(self, t):
            self.timeout = t
            self.write()

        def set_replace_slash_with_dot(self, r):
            self.replace_slash_with_dot = r
            self.write()

        def set_drop_non_existing_label(self, r):
            self.drop_non_existing_label = r
            self.write()

        def set_ignore_empty_history(self, r):
            self.ignore_empty_history = r
            self.write()

        def set_remove_local_messages(self, r):
            self.remove_local_messages = r
            self.write()

        def set_ignore_tags(self, t):
            if len(t.strip()) == 0:
                self.ignore_tags = set()
            else:
                self.ignore_tags = set([tt.strip() for tt in t.split(",")])

            self.write()

        def set_ignore_remote_labels(self, t):
            if len(t.strip()) == 0:
                self.ignore_remote_labels = set()
            else:
                self.ignore_remote_labels = set([tt.strip() for tt in t.split(",")])

            self.write()

        def set_file_extension(self, t):
            try:
                with tempfile.NamedTemporaryFile(
                    dir=os.path.dirname(self.config_f), suffix=t
                ) as _:
                    pass

                self.file_extension = t.strip()
                self.write()
            except OSError:
                print(
                    "Failed creating test file with file extension: " + t + ", not set."
                )
                raise

        def set_local_trash_tag(self, t):
            if "," in t:
                print(
                    "The local_trash_tag must be a single tag, not a list.  Commas are not allowed."
                )
                raise ValueError()
            self.local_trash_tag = t.strip() or "trash"
            self.write()

        def set_translation_list_overlay(self, t):
            if len(t.strip()) == 0:
                self.translation_list_overlay = []
            else:
                self.translation_list_overlay = [tt.strip() for tt in t.split(",")]
            if len(self.translation_list_overlay) % 2 != 0:
                raise Exception(
                    f"Translation list overlay must have an even number of items: {self.translation_list_overlay}"
                )
            self.write()

    class State:
        # last historyid of last synchronized message, anything that has happened
        # remotely after this needs to be synchronized. gmail may return a 404 error
        # if the history records have been deleted, in which case we have to do a full
        # sync.
        last_historyId = 0

        # this is the last modification id of the notmuch db when the previous push was completed.
        lastmod = 0

        def __init__(self, state_f, config):
            self.state_f = state_f

            # True if config file contains state keys and should be migrated.
            # We will write both state and config after load if true.
            migrate_from_config = False

            if os.path.exists(self.state_f):
                try:
                    with open(self.state_f, "r") as fd:
                        self.json = json.load(fd)
                except json.decoder.JSONDecodeError:
                    print("Failed to decode state file `{}`.".format(self.state_f))
                    raise

            elif os.path.exists(config.config_f):
                try:
                    with open(config.config_f, "r") as fd:
                        self.json = json.load(fd)
                except json.decoder.JSONDecodeError:
                    print("Failed to decode config file `{}`.".format(config.config_f))
                    raise
                if any(k in self.json.keys() for k in ["last_historyId", "lastmod"]):
                    migrate_from_config = True
            else:
                self.json = {}

            self.last_historyId = self.json.get("last_historyId", 0)
            self.lastmod = self.json.get("lastmod", 0)

            if migrate_from_config:
                self.write()
                config.write()

        def write(self):
            self.json = {}

            self.json["last_historyId"] = self.last_historyId
            self.json["lastmod"] = self.lastmod

            if os.path.exists(self.state_f):
                shutil.copyfile(self.state_f, self.state_f + ".bak")

            with tempfile.NamedTemporaryFile(
                mode="w+", dir=os.path.dirname(self.state_f), delete=False
            ) as fd:
                json.dump(self.json, fd)
                os.rename(fd.name, self.state_f)

        def set_last_history_id(self, hid):
            self.last_historyId = hid
            self.write()

        def set_lastmod(self, m):
            self.lastmod = m
            self.write()

    # we are in the class "Local"; this is the Local instance constructor
    def __init__(self, g):
        self.gmailieer = g
        self.wd = os.getcwd()
        self.dry_run = g.dry_run
        self.verbose = g.verbose

        # config and state files for local repository
        self.config_f = os.path.join(self.wd, ".gmailieer.json")
        self.state_f = os.path.join(self.wd, ".state.gmailieer.json")
        self.credentials_f = os.path.join(self.wd, ".credentials.gmailieer.json")

        # mail store
        self.md = os.path.join(self.wd, "mail")

        # initialize label translation instance variables
        self.translate_labels = Local.translate_labels_default.copy()
        self.labels_translate = Local.labels_translate_default.copy()

    def load_repository(self, block=False):
        """
        Loads the current local repository

        block (boolean): if repository is in use, wait for lock to be freed (default: False)
        """

        if not os.path.exists(self.config_f):
            raise Local.RepositoryException(
                "local repository not initialized: could not find config file"
            )

        if any(
            [
                not os.path.exists(os.path.join(self.md, mail_dir))
                for mail_dir in ("cur", "new", "tmp")
            ]
        ):
            raise Local.RepositoryException(
                "local repository not initialized: could not find mail dir structure"
            )

        ## Check if we are in the notmuch db
        with notmuch2.Database() as db:
            try:
                self.nm_relative = str(Path(self.md).relative_to(db.path))
            except ValueError:
                raise Local.RepositoryException(
                    "local mail repository not in notmuch db"
                )
            self.nm_dir = str(Path(self.md).resolve())

        ## Lock repository
        try:
            self.lckf = open(".lock", "w")
            if block:
                fcntl.lockf(self.lckf, fcntl.LOCK_EX)
            else:
                fcntl.lockf(self.lckf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Local.RepositoryException(
                "failed to lock repository (probably in use by another gmi instance)"
            )

        self.config = Local.Config(self.config_f)
        self.state = Local.State(self.state_f, self.config)

        self.ignore_labels = self.ignore_labels | self.config.ignore_tags
        self.update_translation("TRASH", self.config.local_trash_tag)
        self.update_translation_list_with_overlay(self.config.translation_list_overlay)

        self.__load_cache__()

        # load notmuch config
        with notmuch2.Database() as db:
            self.new_tags = db.config.get("new.tags", "").split(";")
        self.new_tags = [t.strip() for t in self.new_tags if len(t.strip()) > 0]

        self.loaded = True

    def __load_cache__(self):
        ## The Cache:
        ##
        ## this cache is used to know which messages we have a physical copy of.
        ## hopefully this won't grow too gigantic with lots of messages.
        self.files = []
        for _, _, fnames in os.walk(os.path.join(self.md, "cur")):
            _fnames = ("cur/" + f for f in fnames)
            self.files.extend(_fnames)
            break

        for _, _, fnames in os.walk(os.path.join(self.md, "new")):
            _fnames = ("new/" + f for f in fnames)
            self.files.extend(_fnames)
            break

        # exclude files that are unlikely to be real message files
        self.files = [f for f in self.files if os.path.basename(f)[0] != "."]

        self.gids = {}
        for f in self.files:
            m = self.__filename_to_gid__(os.path.basename(f))
            self.gids[m] = f

    def initialize_repository(self, replace_slash_with_dot, account):
        """
        Sets up a local repository
        """
        print("initializing repository in: %s.." % self.wd)

        # check if there is a repository here already or if there is anything that will conflict with setting up one
        if os.path.exists(self.config_f):
            raise Local.RepositoryException(
                "'.gmailieer.json' exists: this repository seems to already be set up!"
            )

        if os.path.exists(self.md):
            raise Local.RepositoryException(
                "'mail' exists: this repository seems to already be set up!"
            )

        self.config = Local.Config(self.config_f)
        self.config.replace_slash_with_dot = replace_slash_with_dot
        self.config.account = account
        self.config.write()
        os.makedirs(os.path.join(self.md, "cur"))
        os.makedirs(os.path.join(self.md, "new"))
        os.makedirs(os.path.join(self.md, "tmp"))

    def has(self, m):
        """Check whether we have message id"""
        return m in self.gids

    def contains(self, fname):
        """Check whether message file exists is in repository"""
        return Path(self.md) in Path(fname).parents

    def __update_cache__(self, nmsg, old=None):
        """
        Update cache with filenames from nmsg, removing the old:

          nmsg - notmuch2.Message
          old  - tuple of old gid and old fname
        """

        # remove old file from cache
        if old is not None:
            (old_gid, old_f) = old

            old_f = Path(old_f)
            self.files.remove(os.path.join(old_f.parent.name, old_f.name))
            self.gids.pop(old_gid)

        # add message to cache
        fname_iter = nmsg.filenames()
        for _f in fname_iter:
            if self.contains(_f):
                new_f = Path(_f)

                # there might be more GIDs (and files) for each NotmuchMessage, if so,
                # the last matching file will be used in the gids map.

                _m = self.__filename_to_gid__(new_f.name)
                self.gids[_m] = os.path.join(new_f.parent.name, new_f.name)
                self.files.append(os.path.join(new_f.parent.name, new_f.name))

    def messages_to_gids(self, msgs):
        """
        Gets GIDs from a list of NotmuchMessages, the returned list of tuples may contain
        the same NotmuchMessage several times for each matching file. Files outside the
        repository are filtered out.
        """
        gids = []
        messages = []

        for m in msgs:
            for fname in m.filenames():
                if self.contains(fname):
                    # get gmail id
                    gid = self.__filename_to_gid__(os.path.basename(fname))
                    if gid:
                        gids.append(gid)
                        messages.append(m)

        return (messages, gids)

    def __filename_to_gid__(self, fname):
        ext = ""
        if self.config.file_extension:
            ext = "." + self.config.file_extension
        ext += ":2,"

        f = fname.rfind(ext)
        if f > 5:
            return fname[:f]
        else:
            print(
                "'%s' does not contain valid maildir delimiter, correct file name extension, or does not seem to have a valid GID, ignoring."
                % fname
            )
            return None

    def __make_maildir_name__(self, m, labels):
        # https://cr.yp.to/proto/maildir.html
        ext = ""
        if self.config.file_extension:
            ext = "." + self.config.file_extension

        p = m + ext + ":"
        info = "2,"

        # must be ascii sorted
        if "DRAFT" in labels:
            info += "D"

        if "STARRED" in labels:
            info += "F"

        ## notmuch does not add 'T', so it will only be removed at the next
        ## maildir sync flags anyway.

        # if 'TRASH' in labels:
        #   info += 'T'

        if "UNREAD" not in labels:
            info += "S"

        return p + info

    def remove(self, gid, db):
        """
        Remove message from local store
        """
        assert (
            self.config.remove_local_messages
        ), "tried to remove message when 'remove_local_messages' was set to False"

        fname = self.gids.get(gid, None)
        ffname = fname

        if fname is None:
            print("remove: message does not exist in store: %s" % gid)
            return

        fname = os.path.join(self.md, fname)
        try:
            nmsg = db.get(fname)
        except LookupError:
            nmsg = None

        self.print_changes("deleting %s: %s." % (gid, fname))

        if not self.dry_run:
            if nmsg is not None:
                db.remove(fname)
            os.unlink(fname)

            self.files.remove(ffname)
            self.gids.pop(gid)

    def store(self, m, db):
        """
        Store message in local store
        """

        gid = m["id"]
        msg_str = base64.urlsafe_b64decode(m["raw"].encode("ASCII"))

        # messages from GMail have windows line endings
        if os.linesep == "\n":
            msg_str = msg_str.replace(b"\r\n", b"\n")

        labels = m.get("labelIds", [])

        bname = self.__make_maildir_name__(gid, labels)

        # add to cache
        self.files.append(os.path.join("cur", bname))
        self.gids[gid] = os.path.join("cur", bname)

        p = os.path.join(self.md, "cur", bname)
        tmp_p = os.path.join(self.md, "tmp", bname)

        if os.path.exists(p):
            raise Local.RepositoryException("local file already exists: %s" % p)

        if os.path.exists(tmp_p):
            raise Local.RepositoryException(
                "local temporary file already exists: %s" % tmp_p
            )

        if not self.dry_run:
            with open(tmp_p, "wb") as fd:
                fd.write(msg_str)

            # Set atime and mtime of the message file to Gmail receive date
            internalDate = int(m["internalDate"]) / 1000  # ms to s
            os.utime(tmp_p, (internalDate, internalDate))

            os.rename(tmp_p, p)

        # add to notmuch
        self.update_tags(m, p, db)

    def update_tags(self, m, fname, db):
        # make sure notmuch tags reflect gmail labels
        gid = m["id"]
        glabels = m.get("labelIds", [])

        # translate labels. Remote.get_labels () must have been called first
        labels = []
        for l in glabels:
            ll = self.gmailieer.remote.labels.get(l, None)

            if ll is None and not self.config.drop_non_existing_label:
                err = "error: GMail supplied a label that there exists no record for! You can `gmi set --drop-non-existing-labels` to work around the issue (https://github.com/gauteh/lieer/issues/48)"
                print(err)
                raise Local.RepositoryException(err)
            elif ll is None:
                pass  # drop
            else:
                labels.append(ll)

        # remove ignored labels
        labels = set(labels)
        labels = list(labels - self.gmailieer.remote.ignore_labels)

        # translate to notmuch tags
        labels = [self.translate_labels.get(l, l) for l in labels]

        # this is my weirdness
        if self.config.replace_slash_with_dot:
            labels = [l.replace("/", ".") for l in labels]

        if fname is None:
            # this file hopefully already exists and just needs it tags updated,
            # let's try to find its name in the gid to fname table.
            fname = os.path.join(self.md, self.gids[gid])

        else:
            # new file
            fname = os.path.join(self.md, "cur", fname)

        if not os.path.exists(fname):
            if not self.dry_run:
                print(
                    "missing file: reloading cache to check for changes..",
                    end="",
                    flush=True,
                )
                self.__load_cache__()
                fname = os.path.join(self.md, self.gids[gid])
                print("done.")

                if not os.path.exists(fname):
                    raise Local.RepositoryException(
                        "tried to update tags on non-existent file: %s" % fname
                    )

            self.print_changes("tried to update tags on non-existent file: %s" % fname)

        try:
            nmsg = db.get(fname)
        except LookupError:
            nmsg = None

        if nmsg is None:
            self.print_changes(
                "adding message: %s: %s, with tags: %s" % (gid, fname, str(labels))
            )
            if not self.dry_run:
                try:
                    (nmsg, _) = db.add(fname, sync_flags=True)
                except notmuch2.FileNotEmailError:
                    print("%s is not an email" % fname)
                    return True

                # adding initial tags
                with nmsg.frozen():
                    for t in labels:
                        nmsg.tags.add(t)

                    for t in self.new_tags:
                        nmsg.tags.add(t)

                nmsg.tags.to_maildir_flags()
                self.__update_cache__(nmsg)

            return True

        else:
            # message is already in db, set local tags to match remote tags
            otags = nmsg.tags
            igntags = otags & self.ignore_labels
            otags = otags - self.ignore_labels  # remove ignored tags while checking
            if otags != set(labels):
                labels.extend(igntags)  # add back local ignored tags before adding
                if not self.dry_run:
                    with nmsg.frozen():
                        nmsg.tags.clear()
                        for t in labels:
                            nmsg.tags.add(t)
                    nmsg.tags.to_maildir_flags()
                    self.__update_cache__(nmsg, (gid, fname))

                self.print_changes(
                    "changing tags on message: %s from: %s to: %s"
                    % (gid, str(otags), str(labels))
                )

                return True
            else:
                return False

    def print_changes(self, changes):
        if self.dry_run:
            print("(dry-run) " + changes)
        elif self.verbose:
            print(changes)
