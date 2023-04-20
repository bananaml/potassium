import requests
from flask import Flask, request, make_response, abort
from werkzeug.serving import make_server
from threading import Thread
import functools
from termcolor import colored

class Endpoint():
    def __init__(self, type, func):
        self.type = type
        self.func = func

class Request():
    def __init__(self, json:dict, ws = None):
        self.json = json
        self.ws = ws

class Response():
    def __init__(self, status:int, json:dict):
        self.json = json
        self.status = status

class Potassium():
    def __init__(self, name):
        def default_func():
            return
        self.name = name
        self.init_func = default_func
        self.endpoints = {} # dictionary to store unlimited Endpoints, by unique route
        self.context = {}
        self._working = False

    # init runs once on server start
    def init(self, func): 
        def wrapper():
            self.context = func()
        self.init_func=wrapper
        return wrapper
    
    # handler is a blocking http POST handler
    def handler(self, route = "/"):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context, and the request
                return func(self.context, request)
            self.endpoints[route] = Endpoint(type="handler", func=wrapper)
            return wrapper
        return actual_decorator
    
    # background is a non-blocking http POST handler
    def background(self, route: str = "/"):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context, and the request
                self._working = True
                try:
                    res = func(self.context, request)
                    self._working = False
                    return res
                except Exception as e:
                    self._working = False
                    raise e

            self.endpoints[route] = Endpoint(type="background", func=wrapper)
            return wrapper
        return actual_decorator
    
    def _create_flask_app(self):
        flask_app = Flask(__name__)

        # ingest into single endpoint and spread out to multiple downstream funcs
        @flask_app.route('/', defaults={'path': ''}, methods=["POST"])
        @flask_app.route('/<path:path>', methods=["POST"])
        def handle(path):
            route = "/" + path
            if route not in self.endpoints:
                abort(404)

            endpoint = self.endpoints[route]

            if endpoint.type == "handler":
                req = Request(
                    json = request.get_json()
                )
                res = make_response(endpoint.func(req).json)
                res.headers['Endpoint-Type'] = endpoint.type
                return res
            
            if endpoint.type == "background":
                req = Request(
                    json = request.get_json()
                )
                # run as threaded task
                def task(func, req):
                    response = func(req)
                    # we currently do nothing with the response
                thread = Thread(target=task, args=(endpoint.func, req))
                thread.start()

                # send task start success message
                res = make_response({"started": True})
                res.headers['Endpoint-Type'] = endpoint.type
                return res
            
        return flask_app

    # serve runs the http server
    def serve(self, host="0.0.0.0", port = 8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))   
        print(colored("Running init()", 'yellow'))
        self.init_func()
        flask_app = self._create_flask_app()
        server = make_server(host, port, flask_app)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))
        server.serve_forever()