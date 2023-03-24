import requests

def send_webhook(url: str, json: dict):
    try:
        res = requests.post(url, json=json)
    except requests.exceptions.ConnectionError:
        print(f"Webhook to {url} failed with connection error")