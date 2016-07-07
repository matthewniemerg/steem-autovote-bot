#! /usr/bin/env python
from time import gmtime, strftime
import os
import sys
import time
import math
import json
import random
import signal
import logging
import datetime
import bisect
import dateutil.parser

import requests
import yaml
from operator import itemgetter, attrgetter, methodcaller

SQRT2 = math.sqrt(2.0)

# no real reason to make any of these configurable
SEC_PER_HR = 3600.0       # 3600 seconds/hr
MAX_HIST = 1000           # 1000 tx
SLEEP_GRANULARITY = 0.25  # 0.25 sec
LOOP_GRANULARITY = 0.25   # 1/4 of the min_publish_interval
  


      

class DebugException(Exception):
  pass

class GracefulKiller:
  # https://stackoverflow.com/a/31464349
  kill_now = False
  def __init__(self):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

  def exit_gracefully(self,signum, frame):
    self.kill_now = True


class WalletRPC(object):
  def __init__(self, ip, port, rpcuser, rpcpassword):
    self.url = "http://%s:%s/rpc" % (ip, port)
    self.rpcuser = rpcuser
    self.rpcpassword = rpcpassword
    self._headers = {'content-type': 'application/json'}
    self._jsonrpc = "1.0"
    self._id = 1
    self._auth = (rpcuser, rpcpassword)
  def __call__(self, method, params=None):
    if params is None:
      params = []
    else:
      params = list(params)
    payload = {
      "method": method,
      "params": params,
      "jsonrpc": self._jsonrpc,
      "id": self._id
    }
    data = json.dumps(payload)
    response = requests.post(self.url, data=data,
                             headers=self._headers, auth=self._auth)
    return response.json()
  def is_locked(self):
    return self("is_locked")
  def unlock(self, password):
    if self.is_locked():
      return self("unlock", [password])
    return True

  
  def vote(self, voter, author, permlink, weight, broadcast):
    return self("vote", [voter, author, permlink, weight, broadcast])
  

  def get_account(self, accountname):
    return self("get_account", [accountname])
  

  def info(self):
    return self("info")
  def get_block(self, block_num):
    return self("get_block", [block_num])

  def get_state(self, state):
    return self("get_state", [state])
  
def timestamp(dt):
  delta = dt - datetime.datetime(1970, 1, 1)
  return delta.total_seconds()



def usage(message=None):
  if message is not None:
    print "##"
    print "## ERROR: %s" % message
    print "##"
    print
  
  print "usage: %s " % os.path.basename(sys.argv[0])
  raise SystemExit





def load_config(config_name):
  with open(config_name) as f:
    s = f.read()
    try:
      config = yaml.safe_load(s)
    except Exception, e:
      usage(str(e))
  return config
    

def access(r, accessor):
  for i in accessor:
    try:
      r = r[i]
    except:
      raise TypeError("Can not access attribute '%s'." % (i,))
  return r

def process_block(wallet,settings, last_block, voting_queue):
  block_tx_info = wallet.get_block(last_block)["result"]["transactions"]
#  print "block_tx_info =", block_tx_info
  for a in block_tx_info:
    if "operations" in a:
      random.seed(str(wallet.get_block(last_block)["result"]["block_id"]))

      for cur_oper in a["operations"]:
        if cur_oper[0] == "comment":
          if cur_oper[1]["author"] in settings["monitor"]:
            if cur_oper[1]["parent_author"] == "": #this means this is an original post and not a comment
              monitored_account = cur_oper[1]["author"]
              # go through all of the controlled accounts to upvote with and determine if and when 
              for b in settings["monitor"][monitored_account]:
                randval = random.random()
                vote_command = [b, monitored_account, cur_oper[1]["permlink"], 100, True]
                if 1-settings["monitor"][monitored_account][b]["frequency"] < randval:
                  min_wait = settings["monitor"][monitored_account][b]["min_random_wait"]
                  max_wait = min_wait
                  if 'max_random_wait' in settings["monitor"][monitored_account][b].keys():
                    max_wait = settings["monitor"][monitored_account][b]["random_wait"]
                  wait_in_seconds = random.random()*(max_wait-min_wait + 1) + min_wait
                  state_to_get = cur_oper[1]["parent_permlink"]+"/@"+cur_oper[1]["author"]+"/"+cur_oper[1]["permlink"]
                  my_state = wallet.get_state(state_to_get)["result"]
                  a_new_key = cur_oper[1]["author"]+"/"+cur_oper[1]["permlink"]                  
                  some_more_info = my_state["content"][a_new_key]

                  if some_more_info["last_update"] == some_more_info["created"]:
                    if wait_in_seconds > 0:
                      time_to_add = wait_in_seconds+time.time()
                      add_to_queue = [time_to_add, vote_command]
                      voting_queue.insert(bisect.bisect_left(voting_queue, add_to_queue, 0, len(voting_queue)), add_to_queue)
                      print "will broadcast vote(", b, monitored_account, cur_oper[1]["permlink"], 100, "True)", "in", wait_in_seconds, "seconds"
                    else:
                      print "Autovote occured with ", vote_command
                      myresponse = wallet.vote(vote_command[0], vote_command[1], vote_command[2], vote_command[3], vote_command[4])
                  #print myresponse
                  else:
                    print "Bot scanned editted post, not upvoting."
                else:
                  print "Probability of voting event occuring failed.  Did not add vote(", vote_command, ")."





  
  return False

def monitor_loop(settings, wallet):
  killer = GracefulKiller()
  debug = settings.get("debug", False)
  # secret setting for devs, disable if you don't want to publish
  is_live = settings.get("is_live", True)

  logfile_name = settings.get("log_file", None)

  if debug:
    log_level = logging.DEBUG
  else:
    log_level = logging.INFO
    
  # secret advanced user setting, see https://docs.python.org/2/howto/logging.html
  log_format = settings.get("log_format", "%(levelname)s: %(message)s")
  if logfile_name is None:
    logging.basicConfig(format=log_format, level=log_level)
  else:
    logging.basicConfig(format=log_format, filename=logfile_name, level=log_level)
  cur_info = wallet.info()
  last_block = cur_info["result"]["last_irreversible_block_num"]

#  last_block = 


  

  voting_queue = []
  process_block(wallet,settings, last_block, voting_queue)


  blocks_processed = 1
  while True:
    if logfile_name is None:
      logfile = sys.stdout
    else:
      logfile = open(logfile_name, "a")
    loop_time = time.time()

    min_pub_intrvl = 10
    do_update = False
    # test if a new block has been found

    current_time = time.time()    
    current_block = cur_info["result"]["last_irreversible_block_num"]

    if current_block > last_block:
      last_block = last_block+1
      blocks_processed = blocks_processed+1
      process_block(wallet,settings,last_block,voting_queue)

    if blocks_processed % 100 == 0:
      print "blocks_processed = ", blocks_processed, "last_block = ", last_block
      if (len(voting_queue)) != 0:
        print "There are", len(voting_queue), "votes in the queue."
        print "Next vote broadcast in", time.time() - voting_queue[0][0], "seconds"
      
    if len(voting_queue) != 0:
      keeppopping = True
      if current_time < voting_queue[0][0]:
        keeppopping = False
      while keeppopping:
        if current_time > voting_queue[0][0]:
          vote_command = voting_queue.pop(0)
          time_to_vote = vote_command[0]
          
          # now go ahead and vote
          wallet.vote(vote_command[1][0], vote_command[1][1], vote_command[1][2], vote_command[1][3], vote_command[1][4])
          print "Voting with vote(", vote_command[1], ")"
          print "length of voting queue =", len(voting_queue)

          if len(voting_queue) == 0:
            keeppopping = False
          else :
            print "next vote broadcast will occur in", time.time() - voting_queue[0][0], "-- negative time indicates continued broadcasting of votes in queue"
        else :
          keeppopping = False
          if len(voting_queue) != 0:
            print "waiting to vote for :", time.time() - voting_queue[0][0], "seconds" 

    cur_info = wallet.info()
    while (time.time() - loop_time) < (min_pub_intrvl * LOOP_GRANULARITY):
      if killer.kill_now:
        logging.info("Caught kill signal, exiting.")
        break
      time.sleep(SLEEP_GRANULARITY)
    if killer.kill_now:
      break   
    cur_info = wallet.info()



def main():
  if len(sys.argv) != 2:
    usage()
  config_name = sys.argv[1]
  if not os.path.exists(config_name):
    usage('Config file "%s" does not exist.' % config_name)
  if not os.path.isfile(config_name):
    usage('"%s" is not a file.' % config_name)
  config = load_config(config_name)

  settings = config['settings']
  wallet = WalletRPC(settings['rpc_ip'], settings['rpc_port'],
                     settings['rpc_user'], settings['rpc_password'])

  if not wallet.unlock(settings['wallet_password']):
    print("Can't unlock wallet with password. Aborting.")
    raise SystemExit

  monitor = settings['monitor']
  
  print monitor
  for a in monitor:
    for b in monitor[a]:
      print b, " is monitoring", a, "with a random wait between 0 and", monitor[a][b]['random_wait'], "seconds with a probability of", monitor[a][b]['frequency']


  monitor_loop(settings, wallet)
  

   
if __name__ == "__main__":
  main()
    
