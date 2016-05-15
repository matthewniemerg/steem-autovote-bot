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
  
#def random_number(myseed):
#  try:
#    random.seed(str(myseed))
#  except NotImplementedError:
#    pass
#  return random.random()

      

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
  def import_key(self, wifkey):
    return self("import_key", [wifkey])
  
  def vote(self, voter, author, permlink, weight, broadcast):
    return self("vote", [voter, author, permlink, weight, broadcast])
  
  def list_accounts(self):
    accounts = self("list_accounts", ["", 1000])
    mykeys = accounts.keys()
    accounts = accounts[mykeys[1]]
#    for i in range(0,len(accounts)):
#      accounts[i] = accounts[i][1:]

    while True:
      newaccounts = self("list_accounts", [accounts[len(accounts) - 1], 1000])      
      mykeys2 = newaccounts.keys()
      newaccounts = newaccounts[mykeys[1]]
#      for i in range(0, len(newaccounts)):
#        newaccounts[i] = newaccounts[i][1:]

      accounts.extend(newaccounts)
      if len(newaccounts) != 1000 :
        break
    return accounts
  def get_account(self, accountname):
    return self("get_account", [accountname])
  
  def search_for_proxy(self, accountname):
    total_records = self("get_account_history", [accountname, -1, 0])
    total_records = total_records["result"][0][0]+1
    # get records in batches of 20
    testval = 1
    print "total_records = "
    print total_records
    
    foundproxy = False
    for i in range(0, total_records):
      element_to_start = total_records - 1 - i
      current_account_history = self("get_account_history", [accountname, element_to_start, 0])["result"]
      print current_account_history
      record_to_search = current_account_history[0]
      if record_to_search[1]["op"][0] == "account_witness_proxy":
        if record_to_search[1]["op"][1]["account"] == accountname:
          if record_to_search[1]["op"][1]["proxy"] == "":
            return accountname
          else:
            return record_to_search[1]["op"][1]["proxy"]

    return accountname
  def info(self):
    return self("info")
  def get_block(self, block_num):
    return self("get_block", [block_num])

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
                if 1-settings["monitor"][monitored_account][b]["frequency"] < random.random():
                  max_wait = settings["monitor"][monitored_account][b]["random_wait"]
                  wait_in_seconds = random.random()*max_wait
                  #vote(string voter, string author, string permlink, int16_t weight, bool broadcast)
                  vote_command = [b, monitored_account, cur_oper[1]["permlink"], 100, True]
                  #print "vote(", b, monitored_account, block_tx_info["permlink"], 100, "False)"
                  if wait_in_seconds != 0:
                    time_to_add = wait_in_seconds+time.time()
                    add_to_queue = [time_to_add, vote_command]
                    voting_queue.insert(bisect.bisect_left(voting_queue, add_to_queue, 0, len(voting_queue)), add_to_queue)
             #       print voting_queue
                  else:
                    print "Autovote occured with ", vote_command
                    wallet.vote(vote_command[0], vote_command[1], vote_command[2], vote_command[3], vote_command[4])
              



#  Update = False
#  if Update:
#    voting_queue.insert(bisect.bisect_left(voting_queue, new_vote, 0, len(voting_queue), new_vote))

  
  return False

def monitor_loop(settings, wallet):
  killer = GracefulKiller()
  debug = settings.get("debug", False)
  # secret setting for devs, disable if you don't want to publish
  is_live = settings.get("is_live", True)
  witness_name = settings['witness_name']
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

#get_block 1372903 -- my comment
#get_block 1372891 -- edit
#get_block 1372815 -- original
# for testing purposes
 # last_block = 1372815
  

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
#    else:
     # print "current_block=", current_block, "last_block=", last_block
    if blocks_processed % 10 == 0:
      print "blocks_processed = ", blocks_processed, "last_block = ", last_block, "blocks_to_go = ", current_block - last_block

    
      
    if len(voting_queue) != 0:
      keeppopping = True
      if current_time < voting_queue[0][0]:
        keeppopping = False
      while keeppopping:
        if current_time > voting_queue[0][0]:
          vote_command = voting_queue.pop(0)
          if len(voting_queue) == 0:
            keeppopping = False
          time_to_vote = vote_command[0]
          print "current_time = ", current_time, "time_to_vote = ", time_to_vote
          #      vote_command = vote_command[1]
          # now go ahead and vote
          print "Voting! vote(", vote_command[1], ")"
          wallet.vote(vote_command[1][0], vote_command[1][1], vote_command[1][2], vote_command[1][3], vote_command[1][4])

    cur_info = wallet.info()
    while (time.time() - loop_time) < (min_pub_intrvl * LOOP_GRANULARITY):
      if killer.kill_now:
        logging.info("Caught kill signal, exiting.")
        break
      time.sleep(SLEEP_GRANULARITY)
    if killer.kill_now:
      break   
#    print "going back to the beginning of the loop"  
#    check_time_msg = "#######  Update Cycle | %s  #######" % time.ctime(loop_time)
#    border = "#" * len(check_time_msg)
#    logging.info(border)
#    logging.info(check_time_msg)
#    logging.info(border)
#    stm_usd_wvp = None
#    do_update = False
#    prev = get_previous_feed(wallet, witness_name)
#    logging.debug("Previous: %s", str(prev))
#    if prev['time'] == None:
#      logging.debug("Time is None, updating.")
#      do_update = True
#    elif prev['time'] <= (loop_time - max_pub_intrvl):
#      base = prev['base']
#      logging.debug("Max time has expired, updating.")
#      do_update = True
#    elif prev['time'] > (loop_time - min_pub_intrvl):
#      logging.debug("Min time has not elapsed, skipping.")
#      do_update = False
#    else:
#      base = prev['base']
#      stm_usd_wvp = get_stm_usd_wvp(market_data, debug)
#      fraction = abs(base - stm_usd_wvp) / base
#      if stm_usd_wvp == 0:
#        do_update = False
#      elif fraction >= min_change:
#        logging.debug("%s >= %s, updating.", (fraction, min_change))
#        do_update = True
#      else:
#        logging.debug("%s < %s, skipping." % (fraction, min_change))
#        do_update = False
#    if do_update:
#      if stm_usd_wvp == None:
#        stm_usd_wvp = get_stm_usd_wvp(market_data, debug)
#      if stm_usd_wvp > 0:
#        base = stm_usd_wvp
#        history = get_price_history(wallet)
#        mean, stdev = mean_stdev(history)
#        p = phi(base, mean, stdev)
#        r = random_number()
#        args = (base, mean, stdev, p, r)
#        logging.info("base: %s | mean: %s | dev: %s | p: %s | rand: %s", args)
#      if r < p:
#        feed_base = "%0.3f SBD" % base
#        feed_quote = "1.000 STEEM"
#        exch_rate = {"base": feed_base, "quote": feed_quote}
#        logging.info(str(("publish_feed", [witness_name, exch_rate, True])))
#        if is_live:
#          wallet("publish_feed", [witness_name, exch_rate, True])
#    else:
#      logging.info("Skipping this cycle (%s).", time.ctime(loop_time))
#      sys.stderr.flush()
#      sys.stdout.flush()
#    while (time.time() - loop_time) < (min_pub_intrvl * LOOP_GRANULARITY):
#      if killer.kill_now:
#        logging.info("Caught kill signal, exiting.")
#        break
#      time.sleep(SLEEP_GRANULARITY)
#    if killer.kill_now:
#      break



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

  wallet.import_key("5K2YqbSomJSMGkyCgnGgXPdrstQwSVxrVzG8aPka4zYxUdL2zbL")
  monitor_loop(settings, wallet)
  
#  myproxydictionary = {}
#  accounts = wallet.list_accounts()
  #accounts = ["complexring", "complexring1", "complexring449", "complexring100", "complexring101", "complexring444"]
#  for a in accounts:

#    cur_account = wallet.get_account(a)["result"]
#    cur_proxy = cur_account["proxy"]
#    if cur_proxy == "":
#      cur_proxy = a
#    vests_string = cur_account["vesting_shares"]
#    vests_string = vests_string[:len(vests_string)-6]
#    decimal_index = vests_string.index('.')
#    vests_string = vests_string[:decimal_index] + vests_string[decimal_index+1:]
#    while decimal_index - 6 < 0:
#      vests_string = "0" + vests_string
#      decimal_index=decimal_index+1
#    vests_string = vests_string[:decimal_index-6] + "." + vests_string[decimal_index-6:]
#    current_account_vest = float(vests_string)

#    if cur_proxy in myproxydictionary:
#      myproxydictionary[cur_proxy][0] = myproxydictionary[cur_proxy][0] + current_account_vest
#      myproxydictionary[cur_proxy][1].append((a, current_account_vest))
#
#    else:
#      myproxydictionary[cur_proxy] = [current_account_vest,[(a, current_account_vest)]]
#  sorted_keys = sorted(myproxydictionary, key=myproxydictionary.__getitem__, reverse=True) 
#  for a in sorted_keys:
#    myproxydictionary[a][1] = list(set(myproxydictionary[a][1]))      
#    myproxydictionary[a][1] = sorted(myproxydictionary[a][1],key=itemgetter(1),reverse=True)
#    if a == "complexring":
#      print len(myproxydictionary[a][1])



#  myfile = open('steem-proxy-richlist.html', 'w')
#  myfile.write('<html><head><title>STEEM Proxy Richlist by complexring</head></title><body>\n')
#  myfile.write('<h2>STEEM Proxy Richlist</h2>\n<h3>Brought to you by <a href="http://www.matthewniemerg.com">Matthew Niemerg</a> aka witness')
#  myfile.write(' <a href="http://www.steemit.com/@complexring">complexring</a></h3>\n<br><br>')
#  myfile.write('<table border=1>\n<tr><td>Rank</td><td>Account</td><td>Proxying For</td><td>Total VOTES (in millions)</td></tr>')
#  
#  cur_index = 1
#  for a in sorted_keys:
#    myfile.write('<tr><td>')
#    myfile.write(str(cur_index))
#    cur_index=cur_index+1
#    myfile.write('</td><td>')
#    myfile.write('<a href="http://www.steemit.com/@')
#    myfile.write(a)
#    myfile.write('">')
#    myfile.write(a)
#    myfile.write('</a>')
#    myfile.write('</td><td>')
#    extraprintouts = 4
#    extra = 0
#    mylength = len(myproxydictionary[a][1])
# #   print 'mylength = ', mylength
#    if mylength > 4:
#      mylength = 4
#      extra = len(myproxydictionary[a][1])-4
#    for b in range(0, mylength):
# #     print b
#      myfile.write('<a href="http://www.steemit.com/@')
#      myfile.write(myproxydictionary[a][1][b][0])
#      myfile.write('">')
#      myfile.write(myproxydictionary[a][1][b][0])
#      myfile.write('</a> (')
#      myfile.write(str(myproxydictionary[a][1][b][1]))
#      myfile.write(')<br>\n')
#    if extra > 0:
#      myfile.write('+')
#      myfile.write(str(extra))
#      myfile.write(' others')
#    myfile.write('</td><td>')  
#    myfile.write(str(myproxydictionary[a][0]))
#    myfile.write('</td></tr>\n')
#  myfile.write('</table>\n\n')
#  myfile.write('<p>Last Update: ')
#  myfile.write(strftime('%Y-%m-%d %H:%M:%S', gmtime()))
#  myfile.write(' +0 GMT\n')
#  myfile.write('</body>\n</html>\n')
#  myfile.close()
  
            #    print myproxydictionary[a]
  #  for a in sorted_keys[0:10]
#    print a


#  print myproxydictionary["acoustickitty"]      
#  print myproxydictionary



   
if __name__ == "__main__":
  main()
    
