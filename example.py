from potassium import Potassium, Request, Response
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
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    time.sleep(5)
    print("done")

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )

@app.async_handler("/async-with-webhook", result_webhook="http://localhost:8001")
def handler(context: dict, request: Request) -> Response:
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    time.sleep(5)
    print("done")

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )

# # app.async_handler immediately returns success on the trigger call, and runs the handler as a background process.
# # Any response returned fires as a webhook to the optional result_webhook
# @app.async_handler(path="/path/to/async", result_webhook = "https://some_backend/")
# def async_handler(context: dict, request: Request) -> Response:
#     prompt = request.json.get("prompt")
#     model = context.get("model")

#     outputs = model(prompt)

#     return Response(
#         body = {"outputs": outputs}, 
#         status=200
#     )

# # app.websocket runs a streaming connection
# @app.websocket(path="/ws")
# def websocket(context: dict, request: Request) -> None:
#     model = context.get("model")
    
#     ws = request.ws
#     while True:
#         prompt = ws.recv()
#         outputs = model(prompt)
#         ws.send(outputs)

#         exit_condition = True
#         if exit_condition:
#             return None

if __name__ == "__main__":
    app.serve()