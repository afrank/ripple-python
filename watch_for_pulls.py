#!/usr/bin/python2.7

import urllib, urllib2
import json
from pprint import pprint
import re
import os.path

GITHUB_PROJECT = "XXXXXX"
GITHUB_TOKEN = "XXXXXX"
JENKINS_HOST = "XXXXXX"
JENKINS_JOB = "XXXXXX"
JENKINS_TOKEN = "XXXXXX"
HTML_BASE = "/data/html/pulls"
CONTEXT = "continuous-integration/afrank"

url = "https://api.github.com/repos/%s/pulls" % GITHUB_PROJECT

req = urllib2.Request(url,None,{'Authorization':'token %s' % GITHUB_TOKEN})
res = urllib2.urlopen(req)
j = res.read()
js = json.loads(j)
for x in js:
    try:
        m = re.match(r".*/([0-9]+)$",x['_links']['self']['href'])
        build_num = int(m.group(1))
    except:
        build_num = 0
    sha = x['head']['sha']
    status_url = "https://api.github.com/repos/%s/statuses/%s" % (GITHUB_PROJECT,sha)
    status_req = urllib2.Request(status_url,None,{'Authorization':'token %s' % GITHUB_TOKEN})
    status = json.loads(urllib2.urlopen(status_req).read())
    _i = 0
    state = 'not_run'
    updated_at = -1
    for s in status:
        if s['id'] > _i and s['context'] == CONTEXT:
            _i = s['id']
            state = s['state']
            updated_at = s['updated_at']
    if state == "success":
        pass
    elif state == "pending":
        print "Checking up on supposedly-running job for %s" % sha
    elif state == "not_run":
        if os.path.isfile("%s/%s/BUILD" % (HTML_BASE,str(build_num))):
            continue
        print "Kicking off a job for pull %s sha %s" % (build_num,sha)
        args = { 'token':JENKINS_TOKEN,'sha':sha,'pull_num':build_num }
        args = urllib.urlencode(args)
        jurl = "%s/job/%s/buildWithParameters?%s" % (JENKINS_HOST,JENKINS_JOB,args)
        jreq = urllib2.Request(jurl, None, {'Authorization':'token %s' % GITHUB_TOKEN})
        jres = urllib2.urlopen(jreq).read()
    else:
        # some other uncaught state
        pass
