import json, time
from potassium import Potassium, Request, Response
from transformers import pipeline
import torch

app = Potassium("my_app")

@app.init
def init():
    gpt2 = pipeline("text-generation", model="gpt2")
    context = {"gpt2": gpt2, "hello": "world"}

    return context

@app.websocket(route = "/ws")
async def websocket(context: dict, request: Request) -> Response:  
    
    gpt2 = context.get("gpt2")
    
    inputs = await request.ws.receive_json()
    prompt = inputs.get("prompt")
    tokens = inputs.get("tokens")
    
    for i in range(tokens):
        
        out = gpt2(prompt, max_new_tokens=1)
        
        # stream new tokens!
        new_prompt = out[0]["generated_text"]
        diff = new_prompt[len(prompt):]
        await request.ws.send_text(diff)
        
        prompt = new_prompt

if __name__ == "__main__":
    app.serve()