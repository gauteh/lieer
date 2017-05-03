# gmailieer

<img src="doc/demo.png">

This program can pull email and labels (and changes to labels) from your GMail
account and store them locally in a maildir with the labels synchronized with a
[notmuch](https://notmuchmail.org/) database. The changes to tags in the
notmuch database may be pushed back remotely to your GMail account.

It will and can not:
* Add or delete messages on your remote account
* Modify messages other than their labels

## disclaimer

This does not modify or delete your email remotely, but it can modify the
message labels remotely. So those may be lost if all goes wrong. Also, whether
you will actually get all your email is not proven. **In short: No
warranties.**

## requirements

* Python 3
* `tqdm`
* `google_api_python_client` (sometimes `google-api-python-client`)
* `oauth2client`

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

## using your own API key

gmailieer ships with an API key that is shared openly, this key shares API quota, but [cannot be used to access data](https://github.com/gauteh/gmailieer/pull/9) unless access is gained to your private `access_token` or `refresh_token`.

You can get an [api key](https://console.developers.google.com/flows/enableapi?apiid=gmail) for a CLI application to use for yourself. Store the `client_secret.json` file somewhere safe and specify it to `gmi auth -c`. You can do this on a repository that is already initialized.


# caveats

The GMail API doesn't let you sync `muted` messages. Until the Google bug is fixed (https://issuetracker.google.com/issues/36759067), muting is local-only.
