import requests
from flask import Flask, request, make_response, abort
from werkzeug.serving import make_server
from threading import Thread, Lock
import functools
from queue import Queue, Full
import traceback

class Endpoint():
    def __init__(self, type, func, gpu):
        self.type = type
        self.func = func
        self.gpu = gpu

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
        self._lock = Lock()
        self.event_chan = Queue(maxsize=1)

    # init runs once on server start
    def init(self, func): 
        def wrapper():
            self.context = func()
        self.init_func=wrapper
        return wrapper
    
    # handler is a blocking http POST handler
    def handler(self, route: str = "/", gpu: bool = True):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                if gpu:
                    return func(self.context, request)
                return func(None, request)
            self.endpoints[route] = Endpoint(type="handler", func=wrapper, gpu=gpu)
            return wrapper
        return actual_decorator
    
    # background is a non-blocking http POST handler
    def background(self, route: str = "/", gpu: bool = True):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                if gpu:
                    return func(self.context, request)
                return func(None, request)
            self.endpoints[route] = Endpoint(type="background", func=wrapper, gpu=gpu)
            return wrapper
        return actual_decorator
    
    # _handle_generic takes in a request and the endpoint it was routed to and handles it as expected by that endpoint
    def _handle_generic(self, route, endpoint, flask_request):
        if endpoint.type == "handler":
            req = Request(
                json = flask_request.get_json()
            )

            # run in gpu lock by default
            if endpoint.gpu:
            
                # gpu rejects if lock already in use
                if self.is_working():
                    res = make_response()
                    res.status_code = 423
                    res.headers['X-Endpoint-Type'] = endpoint.type
                    return res
                    
                with self._lock:
                    try:
                        response = endpoint.func(req).json
                    except:
                        tb_str = traceback.format_exc()
                        response = tb_str
                        failed = True
                try:
                    self.event_chan.put(item = True, block=False)
                except Full:
                    pass

            else:
                try:
                    response = endpoint.func(req).json
                except:
                    tb_str = traceback.format_exc()
                    response = tb_str
                    failed = True

            res = make_response(response)
            res.headers['X-Endpoint-Type'] = endpoint.type
            if failed:
                res.status_code = 500
            return res
        
        if endpoint.type == "background":
            req = Request(
                json = flask_request.get_json()
            )

            if endpoint.gpu:
                
                # gpu rejects if lock already in use
                if self.is_working():
                    res = make_response()
                    res.status_code = 423
                    res.headers['X-Endpoint-Type'] = endpoint.type
                    return res
            
            # run as threaded task
            def task(endpoint, lock, req):
                if endpoint.gpu:
                    with lock:
                        try:
                            endpoint.func(req)
                        except Exception as e:
                            # do any cleanup before re-raising user error
                            try:
                                self.event_chan.put(item = True, block=False)
                            except Full:
                                pass
                            raise e
                    
                else:
                    try:
                        endpoint.func(req)
                    except Exception as e:
                        # do any cleanup before re-raising user error
                        # in this case, there is no cleanup
                        raise e
                
            thread = Thread(target=task, args=(endpoint, self._lock, req))
            thread.start()

            # send task start success message
            res = make_response({'started': True})            
            res.headers['X-Endpoint-Type'] = endpoint.type
            return res
    
    def read_event_chan(self) -> bool:
        return self.event_chan.get()
        
    def is_working(self):
        return self._lock.locked()
    
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
            return self._handle_generic(route, endpoint, request)
        
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
