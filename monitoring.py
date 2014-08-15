#!/usr/bin/python

import socket
import time
import struct
import pickle
import urllib2
import json

class Graphite:
	def __init__(self):
		self.payload = []
		self.hostname = socket.gethostname()
		# set a couple sane defaults
		self.set_port(2004)
		self.set_prefix(self.hostname)
	def set_port(self,port):
		self.port = port
	def set_prefix(self,prefix):
		self.prefix = prefix
	def add(self,key,val):
		if key is None or val is None:
			return False
		key = "%s.%s" % (self.prefix,key)
		self.payload.append((str(key), (self.now(), int(val))))
	def now(self):
		return int(time.time())
	def get(self,t):
		return getattr(self,t)
	def flush(self):
		self.payload = []
	def send(self,host):
		p = pickle.dumps(self.payload, protocol=2)
		header = struct.pack("!L", len(p))
		msg = header + p
		sock = socket.socket()
		sock.connect((host, self.port))
		sock.sendall(msg)
		sock.close()
		self.flush()

class Nagios:
	def __init__(self,apiKey):
		self.payload = []
		self.apiKey = apiKey
		self.set_proto("http")
		self.set_port("8000")
		self.set_host("TARGETHOST")
		self.set_uri("/api/alert")
	def set_host(self,host):
		self.host = host
	def set_port(self,port):
		self.port = port
	def set_uri(self,uri):
		self.uri = uri
	def set_proto(self,protocol):
		self.protocol = protocol
	def add(self,key,comment,code):
		self.payload.append({ "apiKey":self.apiKey, "status_code":code, "key":key, "comment":comment })
	def flush(self):
		self.payload = []
	def send(self):
		target = "%s://%s:%s%s" % (self.protocol,self.host,self.port,self.uri)
		for d in self.payload:
			urllib2.urlopen(target,json.dumps(d))
		self.flush()
