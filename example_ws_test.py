import requests
import json
import asyncio
from websockets.sync.client import connect

url = "http://localhost:8000"


def hello():

    prompt = "hello world! this is what programmers"
    tokens = 100
    inputs = {"prompt": prompt, "tokens": tokens}
    
    with connect("ws://localhost:8000/ws") as websocket:
        # send payload
        websocket.send(json.dumps(inputs))
        res = prompt
        try:
            while True:
                res += websocket.recv()
                print()
                print(res)
        except:
            pass
            
hello()