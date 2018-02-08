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
* `tqdm`
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

2. Ignore the `.json` files in notmuch and use `new` for [new tags](https://notmuchmail.org/initial_tagging/). Set up a `post-new` hook as [described](https://notmuchmail.org/initial_tagging/) to process mail and remove the `new` tag afterwards. The `new` tag is not synchronized with the remote by `gmailieer`.

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

# label translation

gmailieer enables bidirectional label to tag translation between
GMail's labels and Notmuch tags, and, in addition to that, it enables
pattern-based filtering of local Notmuch tags when syncing to GMail.

By default, gmailieer translate GMail's sysetm labels (`INBOX`, `Sent`
etc.) into lower-case tags of the same name. However, the user can
define custom translation of GMail's system labels, as well as custom
translation of arbitrary labels.

For example, the user can define that GMail's `TRASH` label will be
translated into `deleted`, and that a GMail's label `remote-label` will
be translated into the local `local-tag` tag.

The tag-filtering option allows the user to define which of the local
Notmuch tags will not be synced to GMail. For example, the user might
be using a local tag `new` to mark newly-arrived messages, but would
not like this tag to be synced to GMail. In another scenario, the user
might be using gmailieer to sync several GMail account to the same
Notmuch database, and would like to tag local messages with a tag
indicating their source GMail account. Obviously, it would be
meaningless to have such tags in the GMail accounts.

Another feature of gmailieer is replacement of "label separator". The
label separator is the character (or string) that is used to separate
labels and sublabels. In GMail, the label separate is `/` (Slash). For
example, if the user have, in GMail, a label "parent", that has a
sublabel "child", what actually happens is that there is a label
"parent", and another label "parent/child". When using gmailieer to
sync these labels, a local label "parent/child" would be created.

However, gmailieer enables the user to define a different string for
the local label separator. If, for example, a user prefers the local
label separator to be '::' (double colon), then GMail's label
"parent/child" will be translated to the local tag "parent::child".

## label translation and filtering configuration

To enable label translation and filtering, the user has to provide a
configuration file that describe the actions to take, and to setup
gmailieer to use it.

The label translation file should be named `.label-trans.json` (note
the dot at the beginning of the file name) and it should be placed in
the directory of the corresponding GMail account (see the `usage`
section above).

Following is an example of a custom translation file:

```
{
    "labels_map": {
        "TRASH": "deleted",
        "my-remote": "my-local"
    },
    "ignore_patterns": [
        "new",
        "par.*"
    ],
    "label_sep": "::"
}
```

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

### technical details

The label translation and filtering file should be a JSON file having
the following structure:

```
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
```

Where:

* "label_map" is a mapping between remote labels and local tags.

* "ignore_patterns" is a list of regular expressions; local tags
  matching any of these patterns will not be synced to Gmail.

* "label_sep" is a string that will replace, in local tags, the slash
  used by Gmail as a label/sublabel separator.


A sample file is provided in the `doc/examples` directory.

## setting up gmailieer to use translation and filtering

After creating this file, one needs to tell gmailieer to use it. This
can be done either during initialization, or later using the gmailieer
`set` command:

```sh
$ gmi init --user-label-translation
```

or

```sh
$ gmi set --user-label-translation
```

To disable label translation use:

```sh
$ gmi set --no-user-label-translation
```

Note: once you sync with gmailieer, with or without specifying label
translation, specific translation is set—either the default or
custom translation. Changing the state at a later stage, from default
to custom translation or vice versa, might cause the labels and tags
to get out of sync. If you decide to do that, make sure you know what
you are doing.


## obtain translation and filtering informatoin

gmailieer can display detailed informatoin regarding the translation
and filtering settings.

The general command for obtaining this information is

```sh
$ gmi show-label-translation [-d | -f MAP_FROM_FILE]
```

The different variants of this command are described below.

```sh
$ gmi show-label-translation
```

When run without any switch gmailieer will load the default
translation configuration file and print the following data:

1. The complete label translation map, including both the system
   default translation and the user's custom translation, if it
   exists.

2. The label separates information.

3. The tag ignoring patterns, if there are any.

4. The actual tags (read from Notmuch database) that would be ignored
   when syncing to GMail.

This data describes how gmailieer will actually will behave when
running it.

```sh
$ gmi show-label-translation -d
```

When run with the `-d` switch, gmailieer will print only the default
label to tag translation map.

```sh
$ gmi show-label-translation -f MAP_FROM_FILE
```

When run with the `-f` switch followed by a file name (relative or
full path), gmailieer will load the given translation configuration
file, and print the same data as if this is the default configuration
file, described above.

This method might be useful for testing your configuration file before
making it the default.

## using your own API key

gmailieer ships with an API key that is shared openly, this key shares API quota, but [cannot be used to access data](https://github.com/gauteh/gmailieer/pull/9) unless access is gained to your private `access_token` or `refresh_token`.

You can get an [api key](https://console.developers.google.com/flows/enableapi?apiid=gmail) for a CLI application to use for yourself. Store the `client_secret.json` file somewhere safe and specify it to `gmi auth -c`. You can do this on a repository that is already initialized.


# caveats

* The GMail API does not let you sync `muted` messages. Until [this Google
bug](https://issuetracker.google.com/issues/36759067) is fixed, the `mute` and `muted` tags are not synchronized with the remote.

* The [`todo`](https://github.com/gauteh/gmailieer/issues/52) label seems to be reserved and will be ignored. The same is true for `Trash` (capital `T`), use `trash` (lowercase, see below) to bin messages remotely.

* [Only one of the tags](https://github.com/gauteh/gmailieer/issues/26) `inbox`, `spam`, and `trash` may be added to an email. For
the time being, `trash` will be prefered over `spam`, and `spam` over inbox.

* Sometimes GMail provides a label identifier on a message for a label that does not exist. If you encounter this [issue](https://github.com/gauteh/gmailieer/issues/48) you can get around it by using `gmi set --drop-non-existing-labels` and re-try to pull. The labels will now be ignored, and if this message is ever synced back up the unmapped label ID will be removed. You can list labels with `gmi pull -t`.

* You [cannot add any new files](https://github.com/gauteh/gmailieer/issues/54) (files starting with `.` will be ignored) to the gmailieer repository. Gmailieer uses the directory content an index of local files. Gmailieer does not push new messages to your account (note that if you send messages with GMail, GMail automatically adds the message to your mailbox).

