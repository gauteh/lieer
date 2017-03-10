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

1. get an [api key](https://console.developers.google.com/flows/enableapi?apiid=gmail) for a CLI application and store the client_secret.json file
   somewhere safe, this is needed when authenticating (`auth -c`).

2. make a directory for the gmailieer storage and state files

```sh
$ cd    ~/.mail
$ mkdir account.gmail
$ cd    account.gmail/
```

3. ignore the `.json` files in notmuch:

```
[new]
ignore=*.json;
```

4. initialize the mail storage:

```sh
$ gmi auth -c path/to/client_secrets.json
$ gmi init -a your.email@gmail.com
```

if you haven't done `gmi auth` already, your browser will open and you have to
give gmailieer some access to your e-mail.

5. you're now set up, and you can do the initial pull.

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
$ gmi push
$ gmi pull
```

any conflicts detected in `gmi push` will not be pushed. After the next `gmi
pull` has been run the conflicts should be resolved, effectively overwriting
the local changes with the remote changes. You can force the local changes to
overwrite the remote changes by using `gmi push -f`.

