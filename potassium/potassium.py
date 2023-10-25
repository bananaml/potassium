import time
from flask import Flask, request, make_response, abort
from werkzeug.serving import make_server
from threading import Thread, Lock, Condition
import functools
import traceback
from termcolor import colored


class Endpoint():
    def __init__(self, type, func):
        self.type = type
        self.func = func


class Request():
    def __init__(self, json: dict):
        self.json = json


class Response():
    def __init__(self, status: int = 200, json: dict = {}):
        self.json = json
        self.status = status


class InvalidEndpointTypeException(Exception):
    def __init__(self):
        super().__init__("Invalid endpoint type. Must be 'handler' or 'background'")


class RouteAlreadyInUseException(Exception):
    def __init__(self):
        super().__init__("Route already in use")


class Potassium():
    "Potassium is a simple, stateful, GPU-enabled, and autoscaleable web framework for deploying machine learning models."

    def __init__(self, name):
        self.name = name

        # default init function, if the user doesn't specify one
        self._init_func = lambda: {}
        # dictionary to store unlimited Endpoints, by unique route
        self._endpoints = {}  
        self._context = {}
        self._gpu_lock = Lock()
        self._background_task_cv = Condition()
        self._sequence_number = 0
        self._sequence_number_lock = Lock()
        self._idle_start_time = 0
        self._last_inference_start_time = None
        self._flask_app = self._create_flask_app()

    #
    def init(self, func):
        """init runs once on server start, and is used to initialize the app's context.
        You can use this to load models onto the GPU, set up connections, etc.
        The context is then passed into all handlers and background tasks.
        Notes:
        - this function must return a dictionary
        - the context is not persisted to disk, and will be reloaded on server restart
        - the context is not shared between multiple replicas of the app
        """

        def wrapper():
            print(colored("Running init()", 'yellow'))
            self._context = func()
            if not isinstance(self._context, dict):
                raise Exception("Potassium init() must return a dictionary")
            
        self._init_func = wrapper
        return wrapper
    
    @staticmethod
    def _standardize_route(route):
        # handle empty or None case
        if len(route) == 0 or route == None:
            route = "/"

        # prepend with "/" if not already, as router expects
        if route[0] != "/":
            route = "/" + route
        
        return route

    # handler is a blocking http POST handler
    def handler(self, route: str = "/"):
        "handler is a blocking http POST handler"

        route = self._standardize_route(route)
        if route in self._endpoints:
            raise RouteAlreadyInUseException()

        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                out = func(self._context, request)

                if type(out) != Response:
                    raise Exception("Potassium Response object not returned")

                # check if out.json is a dict
                if type(out.json) != dict:
                    raise Exception(
                        "Potassium Response object json must be a dict")

                return out

            
            self._endpoints[route] = Endpoint(type="handler", func=wrapper)
            return wrapper
        return actual_decorator

    # background is a non-blocking http POST handler
    def background(self, route: str = "/"):    
        "background is a non-blocking http POST handler"
        route = self._standardize_route(route)
        if route in self._endpoints:
            raise RouteAlreadyInUseException()

        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                return func(self._context, request)
            
            self._endpoints[route] = Endpoint(
                type="background", func=wrapper)
            return wrapper
        return actual_decorator

    def test_client(self):
        "test_client returns a Flask test client for the app"
        return self._flask_app.test_client()

    # _handle_generic takes in a request and the endpoint it was routed to and handles it as expected by that endpoint
    def _handle_generic(self, endpoint, flask_request):
        # potassium rejects if lock already in use
        try:
            self._gpu_lock.acquire(blocking=False)
        except:
            res = make_response()
            res.status_code = 423
            res.headers['X-Endpoint-Type'] = endpoint.type
            return res

        res = None
        self._last_inference_start_time = time.time()

        try:
            req = Request(
                json=flask_request.get_json()
            )
        except:
            res = make_response()
            res.status_code = 400
            res.headers['X-Endpoint-Type'] = endpoint.type
            self._gpu_lock.release()
            return res

        if endpoint.type == "handler":
            try:
                out = endpoint.func(req)
                res = make_response(out.json)
                res.status_code = out.status
                res.headers['X-Endpoint-Type'] = endpoint.type
            except:
                tb_str = traceback.format_exc()
                print(colored(tb_str, "red"))
                res = make_response(tb_str)
                res.status_code = 500
                res.headers['X-Endpoint-Type'] = endpoint.type
            self._idle_start_time = time.time()
            self._last_inference_start_time = None
            self._gpu_lock.release()
        elif endpoint.type == "background":


            # run as threaded task
            def task(endpoint, lock, req):
                try:
                    endpoint.func(req)
                except Exception as e:
                    # do any cleanup before re-raising user error
                    raise e
                finally:
                    with self._background_task_cv:
                        self._background_task_cv.notify_all()

                        self._idle_start_time = time.time()
                        self._last_inference_start_time = None
                        lock.release()

            thread = Thread(target=task, args=(endpoint, self._gpu_lock, req))
            thread.start()

            # send task start success message
            res = make_response({'started': True})
            res.headers['X-Endpoint-Type'] = endpoint.type
        else:
            raise InvalidEndpointTypeException()

        return res

    # WARNING: cover depends on this being called so it should not be changed
    def _read_event_chan(self) -> bool:
        """
        _read_event_chan essentially waits for a background task to finish, 
        and then returns True
        """
        with self._background_task_cv:
            # wait until the background task is done
            self._background_task_cv.wait()
        return True

    def _create_flask_app(self):
        flask_app = Flask(__name__)

        # ingest into single endpoint and spread out to multiple downstream funcs
        @flask_app.route('/', defaults={'path': ''}, methods=["POST"])
        @flask_app.route('/<path:path>', methods=["POST"])
        def handle(path):
            with self._sequence_number_lock:
                self._sequence_number += 1

            route = "/" + path
            if route not in self._endpoints:
                abort(404)

            endpoint = self._endpoints[route]
            return self._handle_generic(endpoint, request)
        
        @flask_app.route('/_k/warmup', methods=["POST"])
        def warm():
            with self._sequence_number_lock:
                self._sequence_number += 1
            res = make_response({
                "warm": True,
            })
            res.status_code = 200
            res.headers['X-Endpoint-Type'] = "warmup"
            return res

        @flask_app.route('/_k/status', methods=["GET"])
        @flask_app.route('/__status__', methods=["GET"])
        def status():
            idle_time = 0
            inference_time = 0
            gpu_available = not self._gpu_lock.locked()

            if self._last_inference_start_time != None:
                inference_time = int((time.time() - self._last_inference_start_time)*1000)

            if gpu_available:
                idle_time = int((time.time() - self._idle_start_time)*1000)

            res = make_response({
                "gpu_available": gpu_available,
                "sequence_number": self._sequence_number,
                "idle_time": idle_time,
                "inference_time": inference_time,
            })

            res.status_code = 200
            res.headers['X-Endpoint-Type'] = "status"
            return res

        return flask_app

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        self._init_func()
        server = make_server(host, port, self._flask_app, threaded=True)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))
        self._idle_start_time = time.time()
        server.serve_forever()
