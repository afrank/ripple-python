#!/usr/bin/python

import websocket
import thread
import time
import json
import sys

if len(sys.argv) > 1:
    host = sys.argv[1]
else:
    host = 'wss://s1.ripple.com:443/'

def on_message(ws, message):
    print message

def on_error(ws, error):
    print error

def on_close(ws):
    print "### closed ###"

def on_open(ws):
    def run(*args):
        for i in range(3):
            time.sleep(1)
            request = json.JSONEncoder().encode({"command": "server_info"})
            ws.send(request)
        time.sleep(1)
        ws.close()
        print "thread terminating..."
    thread.start_new_thread(run, ())


if __name__ == "__main__":
    while(1):
       websocket.enableTrace(True)
       ws = websocket.WebSocketApp(host,
                                   on_message = on_message,
                                   on_error = on_error,
                                   on_close = on_close)
       ws.on_open = on_open

       ws.run_forever()
       time.sleep(10)
