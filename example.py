from potassium import Potassium, Request, Response, send_webhook
from transformers import pipeline
import torch
import time

app = Potassium("my_app")

# @app.init runs at startup, and initializes the app's context
@app.init
def init():
    device = 0 if torch.cuda.is_available() else -1
    model = pipeline('fill-mask', model='bert-base-uncased', device=device)
   
    context = {
        "model": model,
        "hello": "world"
    }

    return context

@app.handler()
def handler(context: dict, request: Request) -> Response:
    
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )

@app.async_handler("/async")
def handler(context: dict, request: Request) -> Response:

    time.sleep(2)

    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    send_webhook(url="http://localhost:8001", json={"outputs": outputs})

    return

if __name__ == "__main__":
    app.serve()