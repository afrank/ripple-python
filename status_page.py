#!/usr/bin/python

# this script functions on the components API

import urllib
import urllib2
import json
from pprint import pprint
from enum import Enum
import re

class StatusPage:
	def __init__(self):
		self.apiKey = "XXXXXX"
		self.c_id = "XXXXXX"
		self.url_base = "https://api.statuspage.io/v1/pages/%s" % self.c_id
		self.c_url = "%s/components.json" % self.url_base
		self.headers = { 'Authorization' : 'OAuth %s' % self.apiKey }
	def list(self,match=None):
		req = urllib2.Request(self.c_url,None,self.headers)
		res = urllib2.urlopen(req)
		ret = []
		for d in json.loads(res.read()):
			if match is None or re.match(match,d['name']) is not None:
				ret += [(d['id'],Status.lookup(d['status']),d['name'])]
		return ret
	def match(self,components,pattern):
		out = []
		for c in components:
			res = re.match(pattern,c[2])
			if res is not None:
				out += [c]
		return out
	def set(self,t,e):
		# this method takes two arguments: 
		# a tuple containing the page_id, name and current status of the component, 
		# and the enum object of the requested status
		url = "%s/components/%s.json" % (self.url_base,t[0])
		print url
		v = { 'component[status]' : e.name }
		data = urllib.urlencode(v)
		req = urllib2.Request(url,data,self.headers)
		req.get_method = lambda: 'PATCH'
		res = urllib2.urlopen(req)
		return res.read()

class Status(Enum):
	operational = 0
	degraded_performance = 1
	partial_outage = 2
	major_outage = 3
	@classmethod
	def lookup(cls,status):
		return cls[status]

s = StatusPage()
component = s.list('Wiki')[0]
pprint(json.loads(s.set(component,Status.operational))

