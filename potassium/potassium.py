import requests
from flask import Flask, request, make_response, abort
from werkzeug.serving import make_server
from threading import Thread, Lock
import functools
from queue import Queue, Full
import traceback
from termcolor import colored


class Endpoint():
    def __init__(self, type, func, gpu):
        self.type = type
        self.func = func
        self.gpu = gpu


class Request():
    def __init__(self, json: dict, ws=None):
        self.json = json
        self.ws = ws


class Response():
    def __init__(self, status:int = 200, json: dict = {}):
        self.json = json
        self.status = status


class Potassium():
    def __init__(self, name):
        self.name = name

        def default_func():
            return
        
        # semi-private vars, not intended for users to modify
        self._init_func = default_func
        self._endpoints = {}  # dictionary to store unlimited Endpoints, by unique route
        self._context = {}
        self._lock = Lock()
        self._event_chan = Queue(maxsize=1)

    # init runs once on server start
    def init(self, func):
        def wrapper():
            self._context = func()
        self._init_func = wrapper
        return wrapper

    # handler is a blocking http POST handler
    def handler(self, route: str = "/", gpu: bool = True):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                if gpu:
                    return func(self._context, request)
                return func(None, request)
            self._endpoints[route] = Endpoint(
                type="handler", func=wrapper, gpu=gpu)
            return wrapper
        return actual_decorator

    # background is a non-blocking http POST handler
    def background(self, route: str = "/", gpu: bool = True):
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                if gpu:
                    return func(self._context, request)
                return func(None, request)
            self._endpoints[route] = Endpoint(
                type="background", func=wrapper, gpu=gpu)
            return wrapper
        return actual_decorator

    # _handle_generic takes in a request and the endpoint it was routed to and handles it as expected by that endpoint
    def _handle_generic(self, route, endpoint, flask_request):

        if endpoint.type == "handler":
            req = Request(
                json=flask_request.get_json()
            )

            # run in gpu lock by default
            if endpoint.gpu:
                # gpu rejects if lock already in use
                if self._is_working():
                    res = make_response()
                    res.status_code = 423
                    res.headers['X-Endpoint-Type'] = endpoint.type
                    return res

                with self._lock:
                    try:
                        out = endpoint.func(req)
                        res = make_response(out.json)
                        res.status_code = out.status
                        res.headers['X-Endpoint-Type'] = endpoint.type
                        return res
                    except:
                        error_message = f"Unable to create valid Potassium Response, please ensure your Response objects contain valid json, status code)"
                        res = make_response(error_message)
                        res.status_code = 500
                        res.headers['X-Endpoint-Type'] = endpoint.type
                        return res

            else:
                try:
                    out = endpoint.func(req)
                    res = make_response(out.json)
                    res.status_code = out.status
                    res.headers['X-Endpoint-Type'] = endpoint.type
                    return res
                except:
                    tb_str = traceback.format_exc()
                    res = make_response(tb_str)
                    res.status_code = 500
                    res.headers['X-Endpoint-Type'] = endpoint.type
                    return res

        if endpoint.type == "background":
            req = Request(
                json=flask_request.get_json()
            )

            if endpoint.gpu:
                # gpu rejects if lock already in use
                if self._is_working():
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
                            self._write_event_chan(True)
                            raise e
                    self._write_event_chan(True)
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

    def _write_event_chan(self, item):
        try:
            self._event_chan.put(item, block=False)
        except Full:
            pass

    def _read_event_chan(self) -> bool:
        return self._event_chan.get()

    def _is_working(self):
        return self._lock.locked()

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
            return self._handle_generic(route, endpoint, request)

        return flask_app

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        print(colored("Running init()", 'yellow'))
        self._init_func()
        flask_app = self._create_flask_app()
        server = make_server(host, port, flask_app)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))
        server.serve_forever()
