#!/usr/bin/python

import os
import re
import signal
import subprocess
import sys
import time
import math
import threading
import collections
from monitoring2_7 import Graphite

INTERVAL = 30
MAX_PER_INTERVAL = 20
MAX_INTERVALS = 1
PUNISHMENT_TIME = INTERVAL * (MAX_INTERVALS + 1)
BLOCKFILE = "/etc/nginx/block.conf"
LOGFILE = "/var/log/nginx/access.log"

"""
        log_format main '$remote_addr "$time_local" $msec $status '
          '$request $body_bytes_sent $request_time $upstream_response_time "$http_referer" '
          '"$http_user_agent" "$http_x_forwarded_for" "$http_x_real_ip" "$pipe"';
"""

class Punisher:
    def __init__(self):
        self._pre_punish = collections.Counter()
        self._cur_punish = collections.Counter()
        self._punish_log = collections.Counter()
        print "Setting changed = True (__init__)"
        self._changed = True
    
    @property
    def pre_punish(self):
        return self._pre_punish
    def del_pre_punish(self,ip,full_delete=False):
        if full_delete == True:
            del self._pre_punish[ip]
        else:
            self._pre_punish[ip] -= 1
        self._pre_punish += collections.Counter()
    def add_pre_punish(self,ip):
        self._pre_punish[ip] += 1
    
    @property
    def cur_punish(self):
        return self._cur_punish
    def del_cur_punish(self,ip):
        #del self._cur_punish[ip]
        self._cur_punish[ip] -= 1
        self._cur_punish += collections.Counter()
        if self._cur_punish[ip] == 0:
            print "Setting changed = True (del_cur_punish)"
            self._changed = True
    def add_cur_punish(self,ip):
        punish_factor = math.sqrt(self._punish_log[ip])
        if punish_factor < 1:
            punish_factor = 1
        if self._cur_punish[ip] == 0:
            print "Setting changed = True (add_cur_punish)"
            self._changed = True
        self._cur_punish[ip] += int(round(punish_factor))
        #if self._cur_punish[ip] == 0:
        #    print "calling new punishment for %s" % (ip,)
        #    self._cur_punish[ip] += (int(time.time()) + int(PUNISHMENT_TIME * punish_factor))
        #    self._cur_punish[ip] += (int(time.time()) + int(PUNISHMENT_TIME * punish_factor))
        #    self._changed = True
        #else:
        #    print "adding to existing punishment for %s" % (ip,)
        #    self._cur_punish[ip] += int(PUNISHMENT_TIME * punish_factor)
        self.add_punish_log(ip)

    @property
    def punish_log(self):
        return self._punish_log
    def add_punish_log(self,ip):
        self._punish_log[ip] += 1
    def del_punish_log(self,ip,full_delete=False):
        if full_delete == True:
            del self._punish_log[ip]
        else:
            print "Decrementing %s by 1" % (ip,)
            self._punish_log[ip] -= 1
            self._punish_log += collections.Counter()

    def publish(self):
        if self._changed == True:
            print("Writing %s" % BLOCKFILE)	
            f = open(BLOCKFILE,'w')
            for p in self._cur_punish.keys():
                f.write("deny %s;\n" % p)
            f.close()
            print("Reloading Nginx")
            subprocess.call(["/usr/sbin/nginx","-s","reload"])
            print "Setting changed = False (publish)"
            self._changed = False
        else:
            print "No changes to publish."
    
def kill(proc):
    """Kills the subprocess given in argument."""
    # Clean up after ourselves.
    proc.stdout.close()
    rv = proc.poll()
    if rv is None:
        os.kill(proc.pid, 15)
        rv = proc.poll()
        if rv is None:
            os.kill(proc.pid, 9)  # Bang bang!
            rv = proc.wait()  # This shouldn't block too long.
    print >> sys.stderr, "warning: proc exited %d" % rv
    return rv

def do_on_signal(signum, func, *args, **kwargs):
    """Calls func(*args, **kwargs) before exiting when receiving signum."""

    def signal_shutdown(signum, frame):
        print >> sys.stderr, "got signal %d, exiting" % signum
        func(*args, **kwargs)
        print "...And we're back!"
        sys.exit(128 + signum)

    signal.signal(signum, signal_shutdown)

def worker():
    ip_list = []
    decremented = []
    _x = []
    for k,v in dict(cnt).iteritems():
        if v > MAX_PER_INTERVAL:
            P.add_pre_punish(k)
            ip_list += [k]
    for k in list(P.cur_punish):
        P.del_cur_punish(k)
    for k,v in dict(P.pre_punish).iteritems():
        if k not in ip_list:
            print "%s was in pre-punishment, but not in the current iteration, so decrementing pre-punishment" % (k,)
            P.del_pre_punish(k)
            #P.del_punish_log(k)
        if v > MAX_INTERVALS:
            print "%s triggered add_cur_punish because %i was greater than %i" % (k,v,MAX_INTERVALS)
            P.add_cur_punish(k)
            P.del_pre_punish(k,True)
    for a in list(P.punish_log):
        #print "Debug LOOP: ",a
        if a not in ip_list and a not in decremented:
            print "%s is in post-punishment but not in this iteration, so decrementing post-punishment" % (a,)
            print "Current Decrement Log: ", decremented
            P.del_punish_log(a)
            decremented += [a]
    P.publish()
    if len(P.cur_punish) > 0:
        G.add("blocked_count",len(P.cur_punish))
        G.add("total_blocked_iterations", sum(P.cur_punish.values()))
        G.add("avg_blocked_iterations", sum(P.cur_punish.values())/len(P.cur_punish) )
        G.send("54.91.39.21")
    print "Current: ",ip_list
    print "Pre-Punishment: ",P.pre_punish
    print "Currently Punished: ",P.cur_punish
    print "Punishment Log: ",P.punish_log
    print ""
    cnt.clear()
    threading.Timer(INTERVAL, worker).start()

def main(argv):
    p = subprocess.Popen(["/usr/bin/tail","-qF",LOGFILE], stdout=subprocess.PIPE, bufsize=1)
    do_on_signal(signal.SIGINT, kill, p)
    do_on_signal(signal.SIGPIPE, kill, p)
    do_on_signal(signal.SIGTERM, kill, p)
    worker()
    R = re.compile(r"""(?P<ip>[^ ]+) "(?P<time_local>[^"]+)" (?P<unix_timestamp>[^ ]+) (?P<status>[^ ]+) (?P<method>[^ ]+) (?P<uri>[^ ]+) (?P<proto>[^ ]+) (?P<bytes_sent>[^ ]+) (?P<request_time>[^ ]+) (?P<upstream_response_time>[^ ]+) "(?P<http_referer>[^"]+)" "(?P<http_user_agent>[^"]+)" "(?P<remote_addr>[^"]+)" "(?P<http_x_real_ip>[^"]+)" "(?P<pipe>[^"]+)"$""")
    while True:
        line = p.stdout.readline()

        if not line and p.poll() is not None:
            break  # Nothing more to read and process exited.

        m = R.match(line)
        if m is not None:
            # This is completely proprietary, and should be removed
            if '&username=1' not in m.group('uri') and '/v1/authinfo' in m.group('uri') and m.group('method') == 'GET':
                ip = m.group('ip')
                cnt[ip] += 1


if __name__ == "__main__":
    cnt = collections.Counter()
    P = Punisher()
    G = Graphite()
    G.set_prefix("punisher.%s" % G.get("hostname"))
    sys.exit(main(sys.argv))

