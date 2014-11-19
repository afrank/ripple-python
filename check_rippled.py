#!/usr/bin/python2.7

import json
import time
import socket
import glob
from websocket import create_connection
import rippled
import monitoring2_7

apiKey = "APIKEY"
core_dir = "/data/rippled/var/cores"
SLEEP = 20

hostname = socket.gethostname()
host_type = rippled.ServerType.lookup(hostname)

if not host_type:
	print("Could not determine state from hostname: %s") % hostname
	exit(2)

host_type.proposers_needed -= 1

key = "rippled.%s.%s.status" % (host_type.name,hostname)
#target = "http://flrrb.com:8000/api/alert"

#print "Detected host type as: %s" % host_type.name

d = rippled.ServerInfo('localhost').get()
build_version_1 = d.build_version
ledger_s_1 = d.ledgers['min']
ledger_e_1 = d.ledgers['max']
proposers_1 = d.proposers
server_state_1 = d.server_state.name

time.sleep(SLEEP)

d = rippled.ServerInfo('localhost').get()
build_version_2 = d.build_version
ledger_s_2 = d.ledgers['min']
ledger_e_2 = d.ledgers['max']
proposers_2 = d.proposers
server_state_2 = d.server_state.name

ledger_gaps = d.ledgers['gaps']

core_count = len(glob.glob('%s/core.*' % core_dir))

if server_state_2 != host_type.state_needed:
	msg = "Wrong state for host type: %s (needed %s)" % (server_state_2,host_type.state_needed)
	code = 2
elif ledger_e_2 <= ledger_e_1:
	msg = "Ledger sample 2 not greater than 1: %s %s" % (ledger_e_1,ledger_e_2)
	code = 1
elif proposers_2 < host_type.proposers_needed:
	msg = "Do not have enough proposers: %s (needed %s)" % (proposers_2,host_type.proposers_needed)
	code = 1
else:
	ledger_rate = float(int(ledger_e_2)-int(ledger_e_1))*60/10
	msg = "Version: %s Ledgers: %s (%s/min) Proposers: %s Gaps: %i Coredumps: %i State: %s" % (build_version_2,ledger_e_2,ledger_rate,proposers_2,ledger_gaps,core_count,server_state_2)
	code = 0

n = monitoring2_7.Nagios(apiKey)
n.add(key,msg,code)
n.send()

g = monitoring2_7.Graphite()
g.set_prefix("rippled.%s.server_info" % g.get('hostname'))
g.add("ledgers_min",d.ledgers['min'])
g.add("ledgers_max",d.ledgers['max'])
g.add("fetch_pack",d.fetch_pack)
g.add("io_latency_ms",d.io_latency_ms)
g.add("last_close.converge_time_s",d.converge_time_s)
g.add("last_close.proposers",d.proposers)
g.add("peers",d.peers)
g.add("validation_quorum",d.validation_quorum)
g.add("load.threads",d.threads)
g.add("server_state",d.server_state.value)
g.add("state.%s" % server_state_2, 1)
g.add("age",d.age)
g.add("validated_age",d.validated_age)
g.add("load_factor",d.load_factor)
g.add("reserve_base_xrp",d.reserve_base_xrp)
g.add("reserve_inc_xrp",d.reserve_inc_xrp)
g.add("validated_seq",d.validated_seq)
g.add("base_fee_xrp",format(d.base_fee_xrp,'f'))

for job in d.jobs:
        job_name = job['name']
        g.add("jobs.%s.avg_time" % job_name, job['avg_time'])
        g.add("jobs.%s.in_progress" % job_name, job['in_progress'])
        g.add("jobs.%s.peak_time" % job_name, job['peak_time'])
        g.add("jobs.%s.per_second" % job_name, job['per_second'])
        g.add("jobs.%s.waiting" % job_name, job['waiting'])

g.set_prefix("rippled.%s" % g.get('hostname'))
g.add("coredumps.count",core_count)

# fee-related stuff
if host_type.name == 'validator':
	f = rippled.Rippled('localhost').get('min_cluster_fee')
	g.set_prefix("rippled.%s.fee" % g.get('hostname'))
	g.add('cost_of_ref_txn',f['cost_of_ref_txn'])
	g.add('load_base',f['load_base'])
	g.add('effective_min_fee',f['effective_min_fee'])
	g.add('min_load_value',f['min_load_value'])

g.set_prefix("rippled.%s" % g.get('hostname'))
g.add("check_rippled.status_code",code)

# nodestore activity
getCounts = rippled.Rippled('localhost').get('get_counts', ({'min_count': 0}) )
g.set_prefix('rippled.%s.get_counts' % g.get('hostname'))
if 'node_reads_hit' in getCounts:
	g.add('node_reads_hit', getCounts['node_reads_hit'])
if 'node_reads_total' in getCounts:
	g.add('node_reads_total', getCounts['node_reads_total'])
if 'node_writes' in getCounts:
	g.add('node_writes', getCounts['node_writes'])

g.send('0.0.0.0')

print(msg)
exit(code)
