# gmailieer

This program can pull email and labels (and changes to labels) from your GMail
account and store them locally in a maildir with the labels synchronized with a
[notmuch](https://notmuchmail.org/) database. The changes to tags in the
notmuch database may be pushed back remotely to your GMail account.

It will and can not:
* Add or delete messages on your remote account
* Modify messages other than their labels

# disclaimer

This does not modify or delete your email remotely, but it can modify the
message labels remotely. So those may be lost if all goes wrong. Also, whether
you will actually get all your email is not proven. **In short: No
warranties.**

# usage

this assumes your root mail folder is in `~/.mail`, all `gmailieer` commands
should be run from the `gmailieer` storage unless otherwise specified.

1. get an api key for a CLI application and store the client_secret.json file
   somewhere gmailieer can find it (most likely in the current directory).

1. make a directory for the gmailieer storage and state files

```sh
$ cd ~/.mail
$ mkdir gmailieer
$ cd gmailieer/
```

1. make sure this directory is ignored by `notmuch new` as the messages will be
   handled by `gmailieer`, in .notmuch-config:

```
[new]
ignore=gmailieer;
```

1. initialize the mail storage:

```sh
$ gmailieer init
```

if you haven't done `gmailieer auth` already, your browser will open and you have to
give gmailieer access to the necessary permissions.

you're now set up, and you can do the initial pull.

# pull

will pull down all remote changes since last time, overwriting any local tag
changes of the affected messages.

```sh
$ gmailieer pull
```

# push

will push up all changes since last push, overwriting any remote changes since
the previous pull of the affected messages.

```sh
$ gmailieer push
```

