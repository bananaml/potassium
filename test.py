import requests
import json

url = "http://localhost:8000"

res = requests.post(url + "/", json={"prompt": "this is a cluster-[MASK]!"})
print(res.json())

res = requests.post(url + "/bg", json={"prompt": "this is a cluster-[MASK]!"})
print(res.json())