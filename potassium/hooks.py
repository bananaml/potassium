import requests

def send_webhook(url: str, json: dict):
    try:
        requests.post(url, json=json)
    except requests.exceptions.ConnectionError:
        print(f"Webhook to {url} failed with connection error")
