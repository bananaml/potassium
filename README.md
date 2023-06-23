# Potassium

![Potassium (1)](https://user-images.githubusercontent.com/44653944/222016748-ca2c6905-8fd5-4ee5-a68e-7aed48f23436.png)

[Potassium](https://github.com/bananaml/potassium) is an open source web framework, built to tackle the unique challenges of serving custom models in production.

The goal of this project is to:

- Provide a familiar web framework similar to Flask/FastAPI
- Bake in best practices for handling large, GPU-bound ML models
- Provide a set of primitives common in ML serving, such as:
    - POST request handlers
    - Websocket / streaming connections
    - Async handlers w/ webhooks
- Maintain a standard interface, to allow the code and models to compile to specialized hardware (ideally on [Banana Serverless GPUs](https://banana.dev) 😉)

### Stability Notes:
Potassium uses Semantic Versioning, in that major versions imply breaking changes, and v0 implies instability even between minor/patch versions. Be sure to lock your versions, as we're still in v0!

---

## Quickstart: Serving a Huggingface BERT model

The fastest way to get up and running is to use the [Banana CLI](https://github.com/bananaml/banana-cli), which downloads and runs your first model.

[Here's a demo video](https://www.loom.com/share/86d4e7b0801549b9ab2f7a1acce772aa)


1. Install the CLI with pip
```bash
pip3 install banana-cli
```
This downloads boilerplate for your potassium app, and automatically installs potassium into the venv.

2. Create a new project directory with 
```bash
banana init my-app
cd my-app
```
3. Start the dev server
```bash
. ./venv/bin/activate
python3 app.py
```

4. Call your API (from a separate terminal)
```bash
curl -X POST -H "Content-Type: application/json" -d '{"prompt": "Hello I am a [MASK] model."}' http://localhost:8000/
``` 

---

## Or do it yourself:

1. Install the potassium package

```bash
pip3 install potassium
```

Create a python file called `app.py` containing:

```python
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

# @app.handler is an http post handler running for every call
@app.handler()
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
```

This runs a Huggingface BERT model.

For this example, you'll also need to install transformers and torch.

```
pip3 install transformers torch
```

Start the server with:

```bash
python3 app.py
```

Test the running server with:

```bash
curl -X POST -H "Content-Type: application/json" -d '{"prompt": "Hello I am a [MASK] model."}' http://localhost:8000
```

---

# Documentation

## potassium.Potassium

```python
from potassium import Potassium

app = Potassium("server")
```

This instantiates your HTTP app, similar to popular frameworks like [Flask](https://flask.palletsprojects.com/en/2.2.x/_)

---

## @app.init

```python
@app.init
def init():
    device = 0 if torch.cuda.is_available() else -1
    model = pipeline('fill-mask', model='bert-base-uncased', device=device)

    return {
        "model": model
    }
```

The `@app.init` decorated function runs once on server startup, and is used to load any reuseable, heavy objects such as:

- Your AI model, loaded to GPU
- Tokenizers
- Precalculated embeddings

The return value is a dictionary which saves to the app's `context`, and is used later in the handler functions.

There may only be one `@app.init` function.

---

## @app.handler()

```python
@app.handler("/")
def handler(context: dict, request: Request) -> Response:
    
    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )
```

The `@app.handler` decorated function runs for every http call, and is used to run inference or training workloads against your model(s).

You may configure as many `@app.handler` functions as you'd like, with unique API routes.

The context dict passed in is a mutable reference, so you can modify it in-place to persist objects between warm handlers.

---

## @app.background(path="/background")

```python
@app.background("/background")
def handler(context: dict, request: Request) -> Response:

    prompt = request.json.get("prompt")
    model = context.get("model")
    outputs = model(prompt)

    send_webhook(url="http://localhost:8001", json={"outputs": outputs})

    return
```

The `@app.background()` decorated function runs a nonblocking job in the background, for tasks where results aren't expected to return clientside. It's on you to forward the data to wherever you please. Potassium supplies a `send_webhook()` helper function for POSTing data onward to a url, or you may add your own custom upload/pipeline code.

When invoked, the server immediately returns a `{"success": true}` message.

You may configure as many `@app.background` functions as you'd like, with unique API routes.


The context dict passed in is a mutable reference, so you can modify it in-place to persist objects between warm handlers.

---
## app.serve()

`app.serve` runs the server, and is a blocking operation.


---

# Store
Potassium includes a key-value storage primative, to help users persist data between calls.

Example usage: your own Redis backend (encouraged)
```
from potassium.store import Store, RedisConfig

store = Store(
    backend="redis",
    config = RedisConfig(
        host = "localhost",
        port = 6379
    )
)

# in one handler
store.set("key", "value", ttl=60)

# in another handler
value = store.get("key")
```

Example usage: using local storage 
- Note: not encouraged on Banana serverless or multi-replica environments, as data is stored only on the single replica
```
from potassium.store import Store, RedisConfig

store = Store(
    backend="local"
)

# in one handler
store.set("key", "value", ttl=60)

# in another handler
value = store.get("key")
```

