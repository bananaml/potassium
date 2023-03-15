import requests
from sanic import Sanic
from sanic import json as sanic_json
import functools

def forward_to_webhook(url: str, json_out: dict):
    try:
        res = requests.post(url, json=json_out)
        print("Webhook status code:", res.status_code)
    except:
        print("Webhook failed")

class Potassium():
    def __init__(self, name, mode = "serve"):
        def default_func():
            return
        self.name = name
        self.mode = mode
        self.handler_func = None
        self.init_func = default_func
        self.webhook_url = None
        self.to_optimize = []
        self.cache = {}

    # init runs once on server start
    def init(self, func): 
        def wrapper():
            func()
        self.init_func=wrapper
        return wrapper

    # handler runs for every call
    def handler(self, func):
        def wrapper(json_in):
            # send in app's stateful cache
            return func(self.cache, json_in)
        self.handler_func=wrapper
        return wrapper

    # result_webhook forwards a handler's output to a URL
    def result_webhook(self, url):  
        # Wrap underlying function and don't modify behavior
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        
        self.webhook_url = url
        return actual_decorator

    # optional util
    # optimize flags pytorch model objects for builtime optimization
    def optimize(self, model):
        # only run in optimization mode
        if self.mode != "optimize":
            return
        print("Registering model for optimization")
        self.to_optimize_.append(model)
    
    # optional util
    # set_cache sets the global cache. This overwrites the prior cache dictionary
    def set_cache(self, val:dict):
        self.cache = val

    # optional util
    # set_cache sets the global cache. This overwrites the prior cache dictionary
    def get_cache(self):
        return self.cache

    # serve runs the http server
    def serve(self):
        print("🍌 Starting Potassium Server")        
        if self.webhook_url != None:
            print("🍌 Webhook enabled: Handler results will POST to:", self.webhook_url)
        print("🍌 Init...")
        self.init_func()
        print("🍌 Serving... (Yay!)")
        print("\n\n")
        sanic_app = Sanic(self.name)
        @sanic_app.post('/')
        def handler_wrapper(request):
            json_out = self.handler_func(request.json)
            if self.webhook_url != None:
                forward_to_webhook(self.webhook_url, json_out)
            return sanic_json(json_out)

        sanic_app.run()