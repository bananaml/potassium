from potassium import Potassium, Request, Response
from transformers import pipeline
import torch

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

# @app.handler is an http post handler running for every call
@app.handler("/")
def handler(context: dict, request: Request) -> Response:
    
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )

if __name__ == "__main__":
    app.serve()
