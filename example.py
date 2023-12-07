import time
from potassium import Potassium, Request, Response
from transformers import pipeline
import torch
import os

app = Potassium("my_app")


@app.init
def init():
    device = 0 if torch.cuda.is_available() else -1
    model = pipeline('fill-mask', model='bert-base-uncased', device=device)

    context = {
        "model": model,
        "hello": "world"
    }

    return context

@app.handler(route = "/")
def handler(context: dict, request: Request) -> Response:
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    return Response(
        json={"outputs": outputs},
        status=200
    )

@app.handler("/stream")
def stream(context: dict, request: Request):
    def stream():
        for i in range(100):
            yield f"{i}\n"
            time.sleep(1)


    return Response(
        body=stream(),
        status=200,
        headers={"Content-Type": "text/plain"}
    )


if __name__ == "__main__":
    app.serve()
