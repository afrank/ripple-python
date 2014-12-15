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
        del self._cur_punish[ip]
        self._cur_punish += collections.Counter()
        self._changed = True
    def add_cur_punish(self,ip):
        punish_factor = math.sqrt(self._punish_log[ip])
        if punish_factor < 1:
            punish_factor = 1
        #if ip in self._cur_punish:
        if self._cur_punish[ip] == 0:
            print "calling new punishment for %s" % (ip,)
            self._cur_punish[ip] += (int(time.time()) + int(PUNISHMENT_TIME * punish_factor))
            self._changed = True
        else:
            print "adding to existing punishment for %s" % (ip,)
            self._cur_punish[ip] += int(PUNISHMENT_TIME * punish_factor)
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
            self._punish_log[ip] -= 1
            self._punish_log += collections.Counter()

    def publish(self):
        if self._changed == True:
            #print("publish method has been called, would be punishing ",self._cur_punish.keys())
            print("Writing %s" % BLOCKFILE)
            f = open(BLOCKFILE,'w')
            for p in self._cur_punish.keys():
                f.write("deny %s;\n" % p)
            f.close()
            print("Reloading Nginx")
            subprocess.call(["/usr/sbin/nginx","-s","reload"])
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
        sys.exit(128 + signum)

    signal.signal(signum, signal_shutdown)

def worker():
    global cnt
    global P
    ip_list = []
    _x = []
    for k,v in dict(cnt).iteritems():
        if v > MAX_PER_INTERVAL:
            P.add_pre_punish(k)
            ip_list += [k]
    for k,v in dict(P.pre_punish).iteritems():
        if k not in ip_list:
            P.del_pre_punish(k)
            P.del_punish_log(k)
        if v > MAX_INTERVALS:
            P.add_cur_punish(k)
            P.del_pre_punish(k,True)
    print "Current Punishment at this point: ", dict(P.cur_punish)
    print "Current stamp: ",time.time()
    for addr,end in dict(P.cur_punish).iteritems():
        if end < time.time():
            _x += [addr]
    for x in _x:
        print "removing %s from punishment list" % x
        P.del_cur_punish(x)
    P.publish()
    #punish([x[0] for x in _cur_punish])
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
    global cnt
    R = re.compile(r"""(?P<ip>[^ ]+) "(?P<time_local>[^"]+)" (?P<unix_timestamp>[^ ]+) (?P<status>[^ ]+) (?P<method>[^ ]+) (?P<uri>[^ ]+) (?P<proto>[^ ]+) (?P<bytes_sent>[^ ]+) (?P<request_time>[^ ]+) (?P<upstream_response_time>[^ ]+) "(?P<http_referer>[^"]+)" "(?P<http_user_agent>[^"]+)" "(?P<remote_addr>[^"]+)" "(?P<http_x_real_ip>[^"]+)" "(?P<pipe>[^"]+)"$""")
    while True:
        line = p.stdout.readline()

        if not line and p.poll() is not None:
            break  # Nothing more to read and process exited.

        m = R.match(line)
        if m is not None:
            # Look at 2XX status codes only
            #if int(m.group('status')) >= 200 and int(m.group('status')) < 300:
            # This is completely proprietary, and should be removed
            if '&username=1' not in m.group('uri'):
                ip = m.group('ip')
                cnt[ip] += 1


if __name__ == "__main__":
    cnt = collections.Counter()
    P = Punisher()
    sys.exit(main(sys.argv))

