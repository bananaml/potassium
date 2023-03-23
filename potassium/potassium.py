import requests
from sanic import Sanic
from sanic import json as sanic_json
from threading import Thread
import functools

def forward_to_webhook(url: str, json_out: dict):
    try:
        res = requests.post(url, json=json_out)
    except Exception as e:
        pass

class Endpoint():
    def __init__(self, type, func, result_webhook = None):
        self.type = type
        self.func = func
        self.result_webhook = result_webhook

class Request():
    def __init__(self, json:dict, ws = None):
        self.json = json
        self.ws = ws

class Response():
    def __init__(self, status:int, json:dict):
        self.json = json
        self.status = status

class Potassium():
    def __init__(self, name, mode = "serve"):
        def default_func():
            return
        self.name = name
        self.mode = mode
        self.init_func = default_func
        self.endpoints = {} # dictionary to store unlimited Endpoints, by unique route
        self.context = {}

    # init runs once on server start
    def init(self, func): 
        def wrapper():
            self.context = func()
        self.init_func=wrapper
        return wrapper
    
    # handler is a blocking http POST handler
    def handler(self, path = "/"):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context, and the request
                return func(self.context, request)
            self.endpoints[path] = Endpoint(type="handler", func=wrapper)
            return wrapper
        return actual_decorator
    
    # async_handler is a non-blocking http POST handler
    def async_handler(self, path: str = "/", result_webhook:str = None):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context, and the request
                return func(self.context, request)
            self.endpoints[path] = Endpoint(type="async_handler", func=wrapper, result_webhook=result_webhook)
            return wrapper
        return actual_decorator
    
    # optional util
    # set_context sets the app's context. This overwrites the prior context dictionary
    def set_context(self, val:dict):
        self.context = val

    # optional util
    # get_context gets the app's context
    def get_context(self):
        return self.context

    # serve runs the http server
    def serve(self):
        print("🍌 Starting Potassium Server")        
        print("🍌 Init...")
        self.init_func()
        print("🍌 Serving... (Yay!)")
        print("\n\n")

        sanic_app = Sanic(self.name)
        # transform our potassium paths into sanic paths
        for path, endpoint in self.endpoints.items():
            
            # handler primative
            if endpoint.type == "handler":
                @sanic_app.post(path)
                def handler_wrapper(req):
                    request = Request(
                        json = req.json
                    )
                    # run the respective potassium endpoint at that path
                    # note: we must use the dynamic sanic req.path from runtime, since the "path" varable from our own .items() for loop overwrites itself as it iterates
                    response = self.endpoints[req.path].func(request)
                    return sanic_json(response.json)
                
            if endpoint.type == "async_handler":
                @sanic_app.post(path)
                def handler_wrapper(req):
                    request = Request(
                        json = req.json
                    )
                    
                    # run as threaded task
                    def task(func, request, webhook):
                        response = func(request)
                        # Post results onward if webhook configured
                        if webhook != None:
                            forward_to_webhook(webhook, response.json)

                    endpoint = self.endpoints[req.path]
                    thread = Thread(target=task, args=(endpoint.func, request, endpoint.result_webhook))
                    thread.start()

                    # send task start success message
                    return sanic_json({"started": True})

        sanic_app.run(motd=False)