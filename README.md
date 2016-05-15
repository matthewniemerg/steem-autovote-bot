# STEEM Autovote Bot

Introduction
=====================

[STEEM Autovote](https://github.com/matthewniemerg/python-steem-autovote) is a simple autovoting solution for [STEEM](https://steemit.com/) users.  Features include :

* Simple, customizable [YAML](http://www.yaml.org) configuration file.
* Allows users to monitor multiple accounts and autovote posts (not comments)
* Multiple accounts can autovote any monitored account
* Monitored accounts can be autovoted immediately or within a random time frame for each voting account
* Monitored accounts can be autovoted with a prescribed frequency for each voting account
* Upvotes only

Dependencies
=====================

STEEM Autovote has only two dependencies: [PyYaml](http://pyyaml.org/) and
[Requests](http://docs.python-requests.org/).
On [Ubuntu](http://www.ubuntu.com/), these dependencies
can be installed with the following command:

```
sudo apt-get install python-yaml python-requests
```

Configuration
=====================

Example configuration files are provided in the `Examples` directory as `example1.yaml` and `example2.yaml`.
The configuration file is specified when calling the `autovote-bot.py` script:

```
python autovote-bot.py /home/username/autovote/autovote.yaml
```

Editting the yaml file may be difficult at first, but the rules are quite easy to remember.

* Do not allow for tabbed spaces, only single character white spaces and hard carriage returns.
* New accounts to monitor are added in the monitor section.
* Allow for two additional white spaces for each sub-list.
* The outermost list is the account to monitor.
* Voting ccounts of a monitored account are items in the sub-list of a monitored account.
* Two entries are required in the sub-list for each voting account: random_wait and frequency.


Example Configuration File
======================

```
settings :
  wallet_password : walletpword
  rpc_ip : "127.0.0.1"
  rpc_port : 8091
  rpc_user : "rpcuser"
  rpc_password : "rpcpassword"
  log_file : "autoupvote.log"
  debug : true
  monitor :
    complexring :
      your_account_name :
        random_wait : 0 # random wait time, anytime from 0 to 0 seconds
        frequency : 1 # probability that a vote will occur
      your_sock_puppet_account :
        random_wait : 100 # random wait time, anytime from 0 to 100 seconds
        frequency : .1 # probability that a vote will occur
    your_account_name :
      your_account_name :
        random_wait : 0 # random wait time, anytime from 0 to 0 seconds
        frequency : 1 # probability that a vote will occur
      your_sock_puppet_account :
        random_wait : 60 # random wait time, anytime from 0 to 60 seconds
        frequency : .5 # probability that a vote will occur
    your_sock_puppet_account :
      your_account_name :
        random_wait : 1200 # random wait time, anytime from 0 to 1200 seconds
        frequency : .333 # probability that a vote will occur
      your_sock_puppet_account :
        random_wait : 0 # random wait time, anytime from 0 to 0 seconds
        frequency : 1 # probability that a vote will occur
```

Random Settings
===================

The block_id hash of the post of a monitored account is used as a seed in python's Mersennes Twister Pseudo Random Number Generator.  This seed gets updated for each new post of any monitored account.


Running STEEM Autovote Bot
===================

Running the autovote-bot script requires an open wallet, an instance of `cli_wallet` must be run as a daemon process, listening on an RPC port.  On Ubuntu,
this is best achieved using [Upstart](http://upstart.ubuntu.com/) services.

Please see [this guide](https://github.com/steemed/steem-price-feed/) for starting an upstart service for your cli_wallet.

Alternatively, you can run `cli_wallet` in an instance of a screen.

After installing `screen` type

`screen`

and then once you return to the shell, navigate to the cli_wallet directory and then type

```./cli_wallet -u user -p password --rpc-endpoint=127.0.0.1:8091 -d 2>cli-debug.log 1>cli-error.log```

Detach the screen with `Ctrl + a` and then `Ctrl + x` and you now have a `cli_wallet` daemon running.

There are at least 2 ways you can run the STEEM Autovote Bot.

* Use `screen` and navigate to the appropriate directory, and then run this process in the screened shell with `python autovote-bot.py autovote.yaml`
* Use an upstart service



Running as an Upstart Service
===================

It is highly desirable to run the STEEM Autovote Bot as an upstart service so that on reboot and termination, a respawn of the process will occur.

Save the following script in `/etc/init/steem-autovote-bot.conf` (editted for your own system)

```
# steem-autovote-bot service - steem-autovote-bot service for user

description "STEEM Autovote bot"
author "Ima User <user@example.com>"

# Stanzas
#
# Stanzas control when and how a process is started and stopped
# See a list of stanzas here: //upstart.ubuntu.com/wiki/Stanzas

# When to start the service
start on runlevel [2345]

# When to stop the service
stop on runlevel [016]

# Automatically restart process if crashed
respawn

# Essentially lets upstart know the process will detach itself to the background
# This option does not seem to be of great importance, so it does not need to be set.
# expect fork

# Specify working directory
chdir /home/user/path/to/steem-autovote

# Specify the process/command to start, e.g.
exec /usr/bin/python autovote-bot.py autovote.yaml 2>autovote-debug.log 1>autovote-error.log
```

Upcoming Features
==================

* Upvote with weights
* Downvote with weights
* Random Interval (not just from 0 to random_wait)
* Tracking of when (auto)votes occurred and adjusting times to vote to maximize voting power for both immediate votes and queued votes

Acknowledgments
===================

I have heavily modified the STEEM witness [steemed's](https://steemit.com/witness-category/@steemed/steemed-witness-thread) source code for creating a [STEEM Price Feed](https://github.com/steemed/steem-price-feed/).