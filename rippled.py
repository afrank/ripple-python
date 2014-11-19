#!/usr/bin/python

import json
from pprint import pprint
from websocket import create_connection
from enum import Enum

#class Struct:
#	def __init__(self, **entries):
#		self.__dict__.update(entries)

class Rippled:
	def __init__(self,host):
		self.set_proto("ws")
		self.set_host(host)
		self.set_port(51233)
		self.ws = create_connection("%s://%s:%i" % (self.protocol,self.host,self.port))
	def set_proto(self,protocol):
		self.protocol = protocol
	def set_port(self,port):
		self.port = port
	def set_host(self,host):
		self.host = host
	def close(self):
		self.ws.close()
	def get(self,command,params=None):
		#self.ws.send(json.JSONEncoder().encode({"command": command}))
		cmd = {'command': str(command)}
		if params:
			cmd['params'] = params
		self.ws.send(json.dumps(cmd).encode())
		res = self.ws.recv()
		return json.loads(res)['result']

# 
# this extends Rippled, to add some extra parsing 
# to make certain things easier to derive
#
class ServerInfo(Rippled):
	def __init__(self,host):
		Rippled.__init__(self,host)
		self.raw = Rippled.get(self,'server_info')
	def get(self):
		self.build_version = self.get_safe(self.raw,'info.build_version')
		ledgers = self.get_safe(self.raw,'info.complete_ledgers')
		if '-' in ledgers:
			a = ledgers.split('-')
			ledger_min = a[0]
			ledger_max = a[-1]
			if len(a) > 2:
				ledger_gaps = len(a)-2
			else:
				ledger_gaps = 0
		else:
			ledger_min = 0
			ledger_max = 0
			ledger_gaps = 0
		self.ledgers = { 'min':ledger_min, 'max':ledger_max, 'gaps':ledger_gaps }
		self.fetch_pack = self.get_safe(self.raw,'info.fetch_pack')
		self.io_latency_ms = self.get_safe(self.raw,'info.io_latency_ms')
		self.converge_time_s = self.get_safe(self.raw,'info.last_close.converge_time_s')
		self.proposers = self.get_safe(self.raw,'info.last_close.proposers')
		self.age = self.get_safe(self.raw,'info.closed_ledger.age')
		self.peers = self.get_safe(self.raw,'info.peers')
		self.load_factor = self.get_safe(self.raw,'info.load_factor')
		self.validation_quorum = self.get_safe(self.raw,'info.validation_quorum')
		self.jobs_raw = self.get_safe(self.raw,'info.load.job_types')
		self.threads = self.get_safe(self.raw,'info.load.threads')
		server_state_str = self.get_safe(self.raw,'info.server_state')
		self.server_state = ServerState[server_state_str]
		self.validated_age = self.get_safe(self.raw,'info.validated_ledger.age')
		self.base_fee_xrp = self.get_safe(self.raw,'info.validated_ledger.base_fee_xrp')
		self.reserve_base_xrp = self.get_safe(self.raw,'info.validated_ledger.reserve_base_xrp')
		self.reserve_inc_xrp = self.get_safe(self.raw,'info.validated_ledger.reserve_inc_xrp')
		self.validated_seq = self.get_safe(self.raw,'info.validated_ledger.seq')

		jobs = []
		for job in self.jobs_raw:
			j = {}
			t = self.get_safe(job,'job_type')
			if t is not None:
				j = {	'name':t,
					'avg_time':self.get_safe(job,'avg_time'),
					'in_progress':self.get_safe(job,'in_progress'),
					'peak_time':self.get_safe(job,'peak_time'),
					'per_second':self.get_safe(job,'per_second'),
					'waiting':self.get_safe(job,'waiting')
				}
				jobs += [j]
		self.jobs = jobs
		return self
	def get_safe(self,a,chain):
		top = a
		for h in chain.split('.'):
			try:
				if h in top:
					top = top[h]
				else:
					return None
			except:
				return None
		return top

class ServerState(Enum):
	disconnected = 0
	connected = 1
	syncing = 2
	tracking = 3
	full = 4
	proposing = 5
	validating = 6

class ServerType(Enum):
	validator = (1,4,"proposing")
	client_handler = (2,5,"full")
	hub = (3,5,"full")
	def __init__(self,i,proposers_needed,state_needed):
		self.proposers_needed = proposers_needed
		self.state_needed = state_needed
	@classmethod
	def lookup(cls,hostname):
		if "val" in hostname:
			return cls.validator
		if "stch" in hostname:
			return cls.client_handler
		if "hub" in hostname:
			return cls.hub
		return False

