#!/usr/bin/python2.7

import json
import time, datetime
import socket
import glob
from websocket import create_connection
import rippled
import monitoring2_7

apiKey = "XXXXXXXXXX"
core_dir = "/data/rippled/cores"
SLEEP = 20

hostname = socket.gethostname()
host_type = rippled.ServerType.lookup(hostname)

if not host_type:
	print("Could not determine state from hostname: %s") % hostname
	exit(2)

host_type.proposers_needed -= 1

key = "rippled.%s.%s.status" % (host_type.name,hostname)

OLD = {}
NEW = {}

while True:
    try:
        d = rippled.ServerInfo('localhost').get()
    except:
        d = None
        NEW['msg'] = "Rippled is not running"
        NEW['code'] = 2

    if d is not None:
        NEW['build_version'] = d.build_version
        NEW['ledger_s'] = d.ledgers['min']
        NEW['ledger_e'] = d.ledgers['max']
        NEW['proposers'] = d.proposers
        NEW['server_state'] = d.server_state.name
        NEW['ledger_gaps'] = d.ledgers['gaps']
        NEW['core_count'] = len(glob.glob('%s/core.*' % core_dir))

        if NEW['server_state'] != host_type.state_needed:
            NEW['msg'] = "Wrong state for host type: %s (needed %s)" % (NEW['server_state'],host_type.state_needed)
            NEW['code'] = 2
        elif 'ledger_e' in OLD and NEW['ledger_e'] <= OLD['ledger_e']:
            NEW['msg'] = "Ledger sample 2 not greater than 1: %s %s" % (OLD['ledger_e'],NEW['ledger_e'])
            NEW['code'] = 1
        elif NEW['proposers'] < host_type.proposers_needed:
            NEW['msg'] = "Do not have enough proposers: %s (needed %s)" % (NEW['proposers'],host_type.proposers_needed)
            NEW['code'] = 1
        elif 'ledger_e' in OLD:
            NEW['ledger_rate'] = float(int(NEW['ledger_e'])-int(OLD['ledger_e']))*60/10
            NEW['msg'] = "Version: %s Ledgers: %s (%s/min) Proposers: %s Gaps: %i Coredumps: %i State: %s" % (NEW['build_version'],NEW['ledger_e'],NEW['ledger_rate'],NEW['proposers'],NEW['ledger_gaps'],NEW['core_count'],NEW['server_state'])
            NEW['code'] = 0
        else:
            # there is no OLD, this is probably the first iteration
            NEW['code'] = -1

    if NEW['code'] >= 0:
        n = monitoring2_7.Nagios(apiKey)
        n.add(key,NEW['msg'],NEW['code'])
        n.send()
    
        if d is not None:
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
            g.add("state.%s" % NEW['server_state'], 1)
            g.add("age",d.age)
            g.add("validated_age",d.validated_age)
            g.add("load_factor",d.load_factor)
            g.add("reserve_base_xrp",d.reserve_base_xrp)
            g.add("reserve_inc_xrp",d.reserve_inc_xrp)
            g.add("validated_seq",d.validated_seq)
            if d.base_fee_xrp is None:
                d.base_fee_xrp = -1
            g.add("base_fee_xrp",format(d.base_fee_xrp,'f'))
    
            for job in d.jobs:
                job_name = job['name']
                g.add("jobs.%s.avg_time" % job_name, job['avg_time'])
                g.add("jobs.%s.in_progress" % job_name, job['in_progress'])
                g.add("jobs.%s.peak_time" % job_name, job['peak_time'])
                g.add("jobs.%s.per_second" % job_name, job['per_second'])
                g.add("jobs.%s.waiting" % job_name, job['waiting'])
    
            g.set_prefix("rippled.%s" % g.get('hostname'))
            g.add("coredumps.count",NEW['core_count'])
    
            # fee-related stuff
            if host_type.name == 'validator':
                f = rippled.Rippled('localhost').get('min_cluster_fee')
                g.set_prefix("rippled.%s.fee" % g.get('hostname'))
                g.add('cost_of_ref_txn',f['cost_of_ref_txn'])
                g.add('load_base',f['load_base'])
                g.add('effective_min_fee',f['effective_min_fee'])
                g.add('min_load_value',f['min_load_value'])
    
            g.set_prefix("rippled.%s" % g.get('hostname'))
            g.add("check_rippled.status_code",NEW['code'])
    
            # nodestore activity
            getCounts = rippled.Rippled('localhost').get('get_counts', ({'min_count': 0}) )
            g.set_prefix('rippled.%s.get_counts' % g.get('hostname'))
            if 'node_reads_hit' in getCounts:
                g.add('node_reads_hit', getCounts['node_reads_hit'])
            if 'node_reads_total' in getCounts:
                g.add('node_reads_total', getCounts['node_reads_total'])
            if 'node_writes' in getCounts:
                g.add('node_writes', getCounts['node_writes'])
    
            g.send('54.91.39.21')

        logstamp = '[' + str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')) + '] '
        print(logstamp+NEW['msg'])
        #exit(code)
    time.sleep(SLEEP)
    OLD = NEW
    NEW = {}
