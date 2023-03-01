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

