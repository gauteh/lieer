# gmailieer

<img src="doc/demo.png">

This program can pull email and labels (and changes to labels) from your GMail
account and store them locally in a maildir with the labels synchronized with a
[notmuch](https://notmuchmail.org/) database. The changes to tags in the
notmuch database may be pushed back remotely to your GMail account.

## disclaimer

Gmailieer will not and can not:

* Add or delete messages on your remote account (except syncing the `trash` or `spam` label to messages, and those messages will eventually be [deleted](https://support.google.com/mail/answer/7401?co=GENIE.Platform%3DDesktop&hl=en))
* Modify messages other than their labels

While Gmailieer has been used to successfully synchronize millions of messages and tags by now, it comes with **NO WARRANTIES**.

## requirements

* Python 3
* `tqdm` (optional - for progress bar)
* `google_api_python_client` (sometimes `google-api-python-client`)
* `oauth2client`
* `notmuch` python bindings: latest from [git://notmuchmail.org/git/notmuch](https://git.notmuchmail.org/git/notmuch) or `>= 0.25` (when released)

## installation

After cloning this repository, symlink `gmi` to somewhere on your path, or use `python setup.py`.

# usage

This assumes your root mail folder is in `~/.mail`, all commands
should be run from the local mail repository unless otherwise specified.


1. Make a directory for the gmailieer storage and state files

```sh
$ cd    ~/.mail
$ mkdir account.gmail
$ cd    account.gmail/
```

2. Ignore the `.json` files in notmuch. Any tags listed in `new.tags` will be added to newly pulled messages. Process tags on new messages directly after running gmi, or run `notmuch new` to trigger the `post-new` hook for [initial tagging](https://notmuchmail.org/initial_tagging/). Remove the `new` tag afterwards. You can prevent custom tags from being pushed to the remote by using e.g. `gmi set --ignore-tags new`.

```
[new]
tags=new
ignore=*.json;
```

3. Initialize the mail storage:

```sh
$ gmi init your.email@gmail.com
```

`gmi init` will now open your browser and request limited access to your e-mail.

> The access token is stored in `.credentials.gmailieer.json` in the local mail repository. If you wish, you can specify [your own api key](#using-your-own-api-key) that should be used.

4. You're now set up, and you can do the initial pull.

> Use `gmi -h` or `gmi command -h` to get more usage information.

# pull

will pull down all remote changes since last time, overwriting any local tag
changes of the affected messages.

```sh
$ gmi pull
```

the first time you do this, or if a full synchronization is needed it will take longer.

# push

will push up all changes since last push, conflicting changes will be ignored
unless `-f` is specified. these will be overwritten with the remote changes at
the next `pull`.

```sh
$ gmi push
```

# normal synchronization routine

```sh
$ cd ~/.mail/account.gmail
$ gmi sync
```

This effectively does a `push` followed by a `pull`. Any conflicts detected
with the remote in `push` will not be pushed. After the next `pull` has been
run the conflicts should be resolved, overwriting the local changes with the
remote changes. You can force the local changes to overwrite the remote changes
by using `push -f`.

> Note: If changes are being made on the remote, while `gmaileer` is running, on a message that is currentely being synced. These changes may be overwritten or merged in weird ways on the remote.

See below for more [caveats](#caveats).

## using your own API key

gmailieer ships with an API key that is shared openly, this key shares API quota, but [cannot be used to access data](https://github.com/gauteh/gmailieer/pull/9) unless access is gained to your private `access_token` or `refresh_token`.

You can get an [api key](https://console.developers.google.com/flows/enableapi?apiid=gmail) for a CLI application to use for yourself. Store the `client_secret.json` file somewhere safe and specify it to `gmi auth -c`. You can do this on a repository that is already initialized.


# caveats

* The GMail API does not let you sync `muted` messages. Until [this Google
bug](https://issuetracker.google.com/issues/36759067) is fixed, the `mute` and `muted` tags are not synchronized with the remote.

* The [`todo`](https://github.com/gauteh/gmailieer/issues/52) and [`voicemail`](https://github.com/gauteh/gmailieer/issues/74) labels seem to be reserved and will be ignored.

* The `draft` and `sent` labels are read only: They are synced from GMail to local notmuch tags, but not back (if you change them via notmuch).

* [Only one of the tags](https://github.com/gauteh/gmailieer/issues/26) `inbox`, `spam`, and `trash` may be added to an email. For
the time being, `trash` will be prefered over `spam`, and `spam` over inbox.

* `Trash` (capital `T`) is reserved and not allowed, use `trash` (lowercase, see above) to bin messages remotely.

* Sometimes GMail provides a label identifier on a message for a label that does not exist. If you encounter this [issue](https://github.com/gauteh/gmailieer/issues/48) you can get around it by using `gmi set --drop-non-existing-labels` and re-try to pull. The labels will now be ignored, and if this message is ever synced back up the unmapped label ID will be removed. You can list labels with `gmi pull -t`.

* You [cannot add any new files](https://github.com/gauteh/gmailieer/issues/54) (files starting with `.` will be ignored) to the gmailieer repository. Gmailieer uses the directory content an index of local files. Gmailieer does not push new messages to your account (note that if you send messages with GMail, GMail automatically adds the message to your mailbox).

