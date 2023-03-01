# Potassium

![Potassium (1)](https://user-images.githubusercontent.com/44653944/222016748-ca2c6905-8fd5-4ee5-a68e-7aed48f23436.png)

An HTTP server designed for AI, by [Banana](https://banana.dev)

### Quickstart

Install the potassium package

```bash
pip3 install potassium
```

Create a python file called `app.py` with this:

```python
from potassium import Potassium

from transformers import pipeline
import torch

app = Potassium("server")

@app.init
def init():
    device = 0 if torch.cuda.is_available() else -1
    model = pipeline('fill-mask', model='bert-base-uncased', device=device)

    app.optimize(model)

    return app.set_cache({
        "model": model
    })

@app.handler
def handler(cache: dict, json_in: dict) -> dict:
    prompt = json_in.get('prompt', None)
    model = cache.get("model")

    outputs = model(prompt)
    return {"outputs": outputs}

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

# Documentation

### potassium.Potassium

```python
from potassium import Potassium

app = Potassium("server")
```

This instantiates your HTTP app, similar to popular frameworks like [Flask](https://flask.palletsprojects.com/en/2.2.x/_)

This HTTP server is production-ready out of the box.

### @app.init

```python
@app.init
def init():
    device = 0 if torch.cuda.is_available() else -1
    model = pipeline('fill-mask', model='bert-base-uncased', device=device)

    app.optimize(model)

    return app.set_cache({
        "model": model
    })
```

The `@app.init` decorated function runs once on server startup, and is used to load any reuseable, heavy objects such as:

- Your AI model, loaded to GPU
- Tokenizers
- Precalculated embeddings

Once initialized, you must save those variables to the cache with `app.set_cache({})` so they can be referenced later.

There may only be one `@app.init` function.

### @app.handler

```python
@app.handler
def handler(cache: dict, json_in: dict) -> dict:
    prompt = json_in.get('prompt', None)
    model = cache.get("model")

    outputs = model(prompt)
    return {"outputs": outputs}
```

The `@app.handler` decorated function runs for every http call, and is used to run inference or training workloads against your model(s).

| Arg     | Type | Description                                                                                       |
| ------- | ---- | ------------------------------------------------------------------------------------------------- |
| cache   | dict | The app's cache, set with set_cache()                                                             |
| json_in | dict | The json body of the input call. If using the Banana client SDK, this is the same as model_inputs |

| Return Val | Type | Description                                                                                              |
| ---------- | ---- | -------------------------------------------------------------------------------------------------------- |
| json_out   | dict | The json body to return to the client. If using the Banana client SDK, this is the same as model_outputs |

There may only be one `@app.handler` function.

### app.set_cache()

```python
app.set_cache({})
```

`app.set_cache` saves the input dictionary to the app's cache, for reuse in future calls. It may be used in both the `@app.init` and `@app.handler` functions.

`app.set_cache` overwrites any preexisting cache.

### app.get_cache()

```python
cache = app.get_cache()
```

`app.get_cache` fetches the dictionary to the app's cache. This value is automatically provided for you as the `cache` argument in the `@app.handler` function.

### app.optimize(model)

```python
model # some pytorch model
app.optimize(model)
```

`app.optimize` is a feature specific to users hosting on [Banana's serverless GPU infrastructure](https://banana.dev). It is run during buildtime rather than runtime, and is used to locate the model(s) to be targeted for Banana's Fastboot optimization.

Multiple models may be optimized. Only Pytorch models are currently supported.
