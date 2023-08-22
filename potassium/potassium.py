from flask import Flask, request, make_response, abort
from werkzeug.serving import make_server
from threading import Thread, Lock
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
        self._sequence_number = 0
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
            self._sequence_number += 1
        except:
            res = make_response()
            res.status_code = 423
            res.headers['X-Endpoint-Type'] = endpoint.type
            return res

        res = None

        if endpoint.type == "handler":
            req = Request(
                json=flask_request.get_json()
            )

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
            self._gpu_lock.release()
        elif endpoint.type == "background":
            req = Request(
                json=flask_request.get_json()
            )

            # run as threaded task
            def task(endpoint, lock, req):
                try:
                    endpoint.func(req)
                except Exception as e:
                    # do any cleanup before re-raising user error
                    raise e
                finally:
                    # release lock
                    lock.release()

            thread = Thread(target=task, args=(endpoint, self._gpu_lock, req))
            thread.start()

            # send task start success message
            res = make_response({'started': True})
            res.headers['X-Endpoint-Type'] = endpoint.type
        else:
            raise InvalidEndpointTypeException()

        return res

    # TODO - cover depends on this being called so it should not be private
    def _read_event_chan(self) -> bool:
        # wait until the lock is released to return
        self._gpu_lock.acquire()
        self._gpu_lock.release()

        return True

    # TODO - cover should be updated to point to this method instead of _read_event_chan
    # when we are happy that enough users have migrated to latest potassium
    def block_until_gpu_lock_released(self):
        return self._read_event_chan()

    def _create_flask_app(self):
        flask_app = Flask(__name__)

        # ingest into single endpoint and spread out to multiple downstream funcs
        @flask_app.route('/', defaults={'path': ''}, methods=["POST"])
        @flask_app.route('/<path:path>', methods=["POST"])
        def handle(path):
            route = "/" + path
            if route not in self._endpoints:
                abort(404)

            endpoint = self._endpoints[route]
            return self._handle_generic(endpoint, request)

        @flask_app.route('/__status__', methods=["GET"])
        def status():
            res = make_response({
                "gpu_available": not self._gpu_lock.locked(),
                "sequence_number": self._sequence_number
            })

            res.status_code = 200
            res.headers['X-Endpoint-Type'] = "status"
            res
            return res

        return flask_app

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        self._init_func()
        server = make_server(host, port, self._flask_app)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))
        server.serve_forever()
