from sanic import Sanic
from sanic import json as sanic_json

class Potassium():
    def __init__(self, name, mode = "serve"):
        def default_func():
            return
        self.name = name
        self.mode = mode
        self.handler_func = None
        self.init_func = default_func
        self.to_optimize = []
        self.cache = {}

    # init runs once on server start
    def init(self, func): 
        def inner():
            func()
        self.init_func=inner

    # handler runs for every call
    def handler(self, func):
        def inner(json_in):
            # send in app's stateful cache
            return func(self.cache, json_in)
        self.handler_func=inner

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
        print("🍌 Init...")
        self.init_func()
        print("🍌 Serving... (Yay!)\n\n")
        sanic_app = Sanic(self.name)
        
        @sanic_app.post('/')
        def handler_wrapper(request):
            json_out = self.handler_func(request.json)
            return sanic_json(json_out)

        sanic_app.run()