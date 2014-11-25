#!/usr/bin/python3

import sqlite3
import datetime
import math
import time
from monitoring import Graphite
import urllib.request
import json

#thresh = 300 # seconds
now = int(time.time())
max_inserted_ledger = -1
min_txt_acct_record = 10

GRAPHITE_HOST = "0.0.0.0"

def searcht(s,L):
        return [i for i, v in enumerate(L) if v[0] == s]

def latest_ledger():
        try:
                url = "http://%s/render/?target=rippled.testch1.idx&format=json&from=-60minutes" % GRAPHITE_HOST
                res = urllib.request.urlopen(url)
                j = json.loads(res.read().decode('utf-8'))
                datapoints = j[0]['datapoints']
                datapoints1 = []
                for d in datapoints:
                        if d[0] is not None:
                                datapoints1 += [d]
                l = int(datapoints1[-1][0])
                #l = int(j[0]['datapoints'][-1][0])
        except:
                l = -1
        return l

def keep_max_ledger(cur,new):
        if new > cur:
                return new
        else:
                return cur

print("Retrieving Latest Ledger from Graphite...")
max_ledger = latest_ledger()
if max_ledger < 32570:
        print("failed to retrieve max ledger. Dying.")
        exit(1)
print("Done. Max Ledger: %i" % max_ledger)
# create a little wiggle room
max_ledger -= 1000

print("Fetching Ledger Data...")
conn = sqlite3.connect('/var/db/rippled/db/ledger.db')
c = conn.cursor()
q = """select
                L.LedgerSeq,
                AVG(V.SignTime),
                count(1) count
        FROM
                (select LedgerHash,LedgerSeq from Ledgers WHERE LedgerSeq > %i ORDER BY LedgerSeq DESC) L
                JOIN Validations V
                ON (V.LedgerHash=L.LedgerHash)
        GROUP BY L.LedgerHash,L.LedgerSeq
        HAVING count >= 3
        ORDER BY 2 DESC;""" % max_ledger
c.execute(q)
ledgers = c.fetchall()
conn.close()
print("Done. Retrieved %i ledgers" % len(ledgers))

print("Fetching TX Data...")
conn = sqlite3.connect('/var/db/rippled/db/transaction.db')
c = conn.cursor()
q = """select
                LedgerSeq,
                TransType,
                count(1)
       from
                (select
                        LedgerSeq,
                        TransType,
                        Status
                from Transactions WHERE LedgerSeq > %i order by LedgerSeq desc) foo
        group by 1,2 order by 1 desc;""" % max_ledger
c.execute(q)
tx = c.fetchall()
#conn.close()
print("Done. Retrieved %i ledgers with transactions" % len(tx))

print("Fetching Account Data...")
q = """select
                LedgerSeq,
                count(DISTINCT Account) count
        from (select * from AccountTransactions WHERE LedgerSeq > %i order by LedgerSeq desc) foo
        group by 1
        order by 1 desc;""" % max_ledger
c.execute(q)
acct = c.fetchall()
print("Done. Retrieved %i ledgers with user counts" % len(acct))

print("Fetching Top Accounts...")
q = """select
                LedgerSeq,
                FromAcct,
                SUM(case when TransType = 'OfferCancel' then 1 else 0 end) OfferCancel,
                SUM(case when TransType = 'OfferCreate' then 1 else 0 end) OfferCreate,
                SUM(case when TransType = 'Payment' then 1 else 0 end) Payment,
                SUM(case when TransType = 'AccountSet' then 1 else 0 end) AccountSet,
                SUM(case when TransType = 'TrustSet' then 1 else 0 end) TrustSet
        from Transactions
        where ledgerSeq > %i
        GROUP BY 1,2
        HAVING OfferCancel > %i OR OfferCreate > %i OR Payment > %i OR AccountSet > %i OR TrustSet > %i
        ORDER BY 1 DESC;""" % (max_ledger,min_txt_acct_record,min_txt_acct_record,min_txt_acct_record,min_txt_acct_record,min_txt_acct_record)
c.execute(q)
acct_tx = c.fetchall()
print("Done. Retrieved %i records" % len(acct_tx))

conn.close()

g = Graphite()
g.set_prefix("rippled.testch1")

count = 0
for row in tx:
        idx = searcht(row[0],ledgers)
        if type(idx) == list and len(idx) > 0:
                l = ledgers[idx[0]]
                d = (datetime.datetime.fromtimestamp(int(l[1])) + datetime.timedelta(days=math.floor(365.25*30))).strftime('%s')
                s = row[0]
                c = row[2]
                #if int(d) > now - thresh - 60:
                max_inserted_ledger = keep_max_ledger(max_inserted_ledger,row[0])
                g.add("tx_volume.%s" % row[1],c,d)
                print(g.count())
                #count+=1
                a_idx = searcht(row[0],acct)
                if type(a_idx) == list and len(a_idx) > 0:
                        a_count = acct[a_idx[0]][1]
                        if a_count is not None and a_count > 0:
                                g.add("tx_accounts",a_count,d)
                                print(g.count())
                                count+=1
                atx_idx = searcht(row[0],acct_tx)
                if type(atx_idx) == list and len(atx_idx) > 0:
                        for atx in atx_idx:
                                t = acct_tx[atx]
                                t_from = t[1]
                                t_cancel = t[2]
                                t_create = t[3]
                                t_payment = t[4]
                                t_set = t[5]
                                t_trust = t[6]
                                if t_cancel > 0:
                                        g.add("acct_tx.%s.OfferCancel" % t_from,t_cancel,d)
                                if t_create > 0:
                                        g.add("acct_tx.%s.OfferCreate" % t_from,t_create,d)
                                if t_payment > 0:
                                        g.add("acct_tx.%s.Payment" % t_from,t_payment,d)
                                if t_set > 0:
                                        g.add("acct_tx.%s.AccountSet" % t_from,t_set,d)
                                if t_trust > 0:
                                        g.add("acct_tx.%s.TrustSet" % t_from,t_trust,d)
                if g.count() >= 100:
                        print("Sending...")
                        g.send(GRAPHITE_HOST)
                        #count = 0

g.addA("idx",max_inserted_ledger)

if g.count() > 0:
        g.send(GRAPHITE_HOST)
