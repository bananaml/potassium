from enum import Enum
import time
import os
from types import GeneratorType
from typing import Callable
from dataclasses import dataclass
from flask import Flask, request, make_response, abort, Response as FlaskResponse
import uuid
from werkzeug.serving import make_server
from threading import Thread, Lock
from queue import Queue as ThreadQueue
import functools
from termcolor import colored
from multiprocessing import Pool as ProcessPool, Queue as ProcessQueue
from multiprocessing.pool import ThreadPool
from .status import PotassiumStatus, StatusEvent
from .worker import run_worker, init_worker
from .exceptions import RouteAlreadyInUseException, InvalidEndpointTypeException
from .types import Request, RequestHeaders, Response
import logging

class HandlerType(Enum):
    HANDLER = "HANDLER"
    BACKGROUND = "BACKGROUND"

@dataclass
class Endpoint():
    type: HandlerType
    func: Callable

class ResponseMailbox():
    def __init__(self, response_queue):
        self._response_queue = response_queue
        self._mailbox = {}
        self._lock = Lock()

        t = Thread(target=self._response_handler, daemon=True)
        t.start()

    def _response_handler(self):
        try:
            while True:
                request_id, payload = self._response_queue.get()
                with self._lock:
                    if request_id not in self._mailbox:
                        self._mailbox[request_id] = ThreadQueue()
                    self._mailbox[request_id].put(payload)
        except EOFError:
            # queue closed, this happens when the server is shutting down
            pass

    def get_response(self, request_id):
        with self._lock:
            if request_id not in self._mailbox:
                self._mailbox[request_id] = ThreadQueue()
        result, stream_id = self._mailbox[request_id].get()

        if stream_id is not None:
            result.body = self._stream_body(stream_id)

        with self._lock:
            del self._mailbox[request_id]

        return result

    def _stream_body(self, stream_id):
        with self._lock:
            if stream_id not in self._mailbox:
                self._mailbox[stream_id] = ThreadQueue()
        queue = self._mailbox[stream_id]

        try:
            while True:
                result = queue.get()
                if isinstance(result, Exception):
                    with self._lock:
                        del self._mailbox[stream_id]
                    raise result
                elif result == None:
                    break
                else:
                    yield result
        except GeneratorExit:
            while True:
                # flush the queue
                result = queue.get()
                if result == None:
                    break
                elif isinstance(result, Exception):
                    with self._lock:
                        del self._mailbox[stream_id]
                    raise result
        with self._lock:
            del self._mailbox[stream_id]


class Potassium():
    "Potassium is a simple, stateful, GPU-enabled, and autoscaleable web framework for deploying machine learning models."

    def __init__(self, name, experimental_num_workers=1):
        self.name = name

        # default init function, if the user doesn't specify one
        self._init_func = lambda _: {}
        # dictionary to store unlimited Endpoints, by unique route
        self._endpoints = {}  
        self._context = {}
        self._flask_app = self._create_flask_app()
        self._event_queue = ProcessQueue()
        self._response_queue = ProcessQueue()
        self._response_mailbox = ResponseMailbox(self._response_queue)

        self._num_workers = experimental_num_workers

        self._worker_pool = None

        self.event_handler_thread = Thread(target=self._event_handler, daemon=True)
        self.event_handler_thread.start()

        self._status = PotassiumStatus.initial(self._num_workers)

    def _event_handler(self):
        try:
            while True:
                event = self._event_queue.get()
                self._status = self._status.update(event)
        except EOFError:
            # this happens when the process is shutting down
            pass


    def init(self, func):
        """init runs once on server start, and is used to initialize the app's context.
        You can use this to load models onto the GPU, set up connections, etc.
        The context is then passed into all handlers and background tasks.
        Notes:
        - this function must return a dictionary
        - the context is not persisted to disk, and will be reloaded on server restart
        - the context is not shared between multiple replicas of the app
        """

        self._init_func = func
        return func
    
    @staticmethod
    def _standardize_route(route):
        # handle empty or None case
        if len(route) == 0 or route == None:
            route = "/"

        # prepend with "/" if not already, as router expects
        if route[0] != "/":
            route = "/" + route
        
        return route

    def _base_decorator(self, route: str, handler_type: HandlerType):
        route = self._standardize_route(route)
        if route in self._endpoints:
            raise RouteAlreadyInUseException()

        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(context, request):
                # send in app's stateful context if GPU, and the request
                out = func(context, request)

                if handler_type == HandlerType.HANDLER:
                    if type(out) != Response:
                        raise Exception("Potassium Response object not returned")
                    if type(out.body) != bytes and type(out.body) != GeneratorType:
                        raise Exception(
                            "Potassium Response object body must be bytes", type(out.body))

                return out

            
            self._endpoints[route] = Endpoint(type=handler_type, func=wrapper)
            return wrapper
        return actual_decorator

    # handler is a blocking http POST handler
    def handler(self, route: str = "/"):
        "handler is a blocking http POST handler"
        return self._base_decorator(route, HandlerType.HANDLER)

    # background is a non-blocking http POST handler
    def background(self, route: str = "/"):    
        "background is a non-blocking http POST handler"
        return self._base_decorator(route, HandlerType.BACKGROUND)

    def test_client(self):
        "test_client returns a Flask test client for the app"
        self._init_server()
        return self._flask_app.test_client()

    def _create_flask_app(self):
        flask_app = Flask(__name__)

        # ingest into single endpoint and spread out to multiple downstream funcs
        @flask_app.route('/', defaults={'path': ''}, methods=["POST"])
        @flask_app.route('/<path:path>', methods=["POST"])
        def handle(path):
            route = "/" + path
            if route not in self._endpoints:
                self._event_queue.put((StatusEvent.BAD_REQUEST_RECEIVED,))
                abort(404)

            endpoint = self._endpoints[route]
            request_id = request.headers.get("X-Banana-Request-Id", None)
            if request_id is None:
                request_id = str(uuid.uuid4())
            try:
                req = Request(
                    headers=RequestHeaders(dict(request.headers.items())),
                    json=request.get_json(),
                    id=request_id
                )
            except:
                res = make_response()
                res.status_code = 400
                self._event_queue.put((StatusEvent.BAD_REQUEST_RECEIVED,))
                return res

            self._event_queue.put((StatusEvent.INFERENCE_REQUEST_RECEIVED,))

            assert self._worker_pool is not None, "Worker pool not initialized"
            # use an internal id for critical path to prevent user from accidentally
            # breaking things by sending multiple requests with the same id
            internal_id = str(uuid.uuid4())
            if endpoint.type == HandlerType.HANDLER:
                self._worker_pool.apply_async(run_worker, args=(endpoint.func, req, internal_id, True))
                resp = self._response_mailbox.get_response(internal_id)

                flask_response = FlaskResponse(
                    resp.body,
                    status=resp.status,
                    headers=resp.headers
                )
            elif endpoint.type == HandlerType.BACKGROUND:
                self._worker_pool.apply_async(run_worker, args=(endpoint.func, req, internal_id))

                flask_response = make_response({'started': True})
            else:
                raise InvalidEndpointTypeException()

            return flask_response

        @flask_app.route('/_k/warmup', methods=["POST"])
        def warm():
            request_id = str(uuid.uuid4())

            # a bit of a hack but we need to send a start and end event to the event queue
            # in order to update the status the way the load balancer expects
            self._event_queue.put((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
            self._event_queue.put((StatusEvent.INFERENCE_END, request_id))
            res = make_response({
                "warm": True,
            })
            res.status_code = 200
            return res

        @flask_app.route('/_k/status', methods=["GET"])
        @flask_app.route('/__status__', methods=["GET"])
        def status():
            cur_status = self._status

            res = make_response({
                "gpu_available": cur_status.gpu_available,
                "sequence_number": cur_status.sequence_number,
                "idle_time": int(cur_status.idle_time*1000),
                "inference_time": int(cur_status.longest_inference_time*1000),
            })

            res.status_code = 200
            return res

        return flask_app
    
    def _init_server(self):
        # unless the user has already set up logging, set up logging to stdout using
        # a separate fd so that we don't get in the way of request logs
        log = logging.getLogger('werkzeug')
        if len(log.handlers) == 0:
            # duplicate stdout
            stdout_copy = os.dup(1)
            # redirect flask logs to stdout_copy
            log.addHandler(logging.StreamHandler(os.fdopen(stdout_copy, 'w')))

        self._idle_start_time = time.time()
        index_queue = ProcessQueue()
        for i in range(self._num_workers):
            index_queue.put(i)
        if self._num_workers == 1:
            Pool = ThreadPool
        else:
            Pool = ProcessPool
        self._worker_pool = Pool(
            self._num_workers,
            init_worker, 
            (
                index_queue,
                self._event_queue,
                self._response_queue, 
                self._init_func,
                self._num_workers
            )
        )

        while True:
            if self._status.num_workers_started == self._num_workers:
                break
        print(colored(f"Started {self._num_workers} workers", 'green'))

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        self._init_server()
        server = make_server(host, port, self._flask_app, threaded=True)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))

        server.serve_forever()

