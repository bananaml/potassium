from potassium import Potassium, Request, Response
from transformers import pipeline
import torch
import time

app = Potassium("my_app")

# @app.init runs at startup, and initializes the app's context
@app.init
def init():
    print("init")
    return {"hello": "world"}

@app.handler()
def handler(context: dict, request: Request) -> Response:
    hello = context.get("hello")
    print("handler")
    return Response(
        json = {"hello": hello}, 
        status=200
    )

# if __name__ == "__main__":
#     app.serve()


# initial app def above

# run init
app.init_func()

# run server def
from sanic import Sanic
from sanic import json as sanic_json
sanic_app = Sanic(app.name)
# transform our potassium paths into sanic paths
for path, endpoint in app.endpoints.items():
    # handler primative
    if endpoint.type == "handler":
        @sanic_app.post(path)
        def handler_wrapper(req):
            request = Request(
                json = req.json
            )
            # run the respective potassium endpoint at that path
            # note: we must use the dynamic sanic req.path from runtime, since the "path" varable from our own .items() for loop overwrites itself as it iterates
            response = app.endpoints[req.path].func(request)
            return sanic_json(response.json)

from threading import Thread

# run as threaded task
def task():
    sanic_app.run(motd=False)
thread = Thread(target=task)
thread.start()