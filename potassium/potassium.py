import time
import os
from types import GeneratorType
from flask import Flask, request, make_response, abort, Response as FlaskResponse
from huggingface_hub.file_download import uuid
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
from .types import Request, Endpoint, RequestHeaders, Response

class ResponseMailbox():
    def __init__(self, response_queue):
        self._response_queue = response_queue
        self._mailbox = {}
        self._lock = Lock()

        t = Thread(target=self._response_handler, daemon=True)
        t.start()

    def _response_handler(self):
        while True:
            request_id, payload = self._response_queue.get()
            with self._lock:
                if request_id not in self._mailbox:
                    self._mailbox[request_id] = ThreadQueue()
                self._mailbox[request_id].put(payload)

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
                

            print('generator exit')

        with self._lock:
            del self._mailbox[stream_id]


class Potassium():
    "Potassium is a simple, stateful, GPU-enabled, and autoscaleable web framework for deploying machine learning models."

    def __init__(self, name):
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

        self._num_workers = int(os.environ.get("POTASSIUM_NUM_WORKERS", 1))

        self._worker_pool = None

        self.event_handler_thread = Thread(target=self._event_handler, daemon=True)

        self._status = PotassiumStatus(
            num_started_inference_requests=0,
            num_completed_inference_requests=0,
            num_workers=self._num_workers,
            num_workers_started=0,
            idle_start_timestamp=time.time(),
            in_flight_request_start_times=[]
        )

    def _event_handler(self):
        while True:
            event = self._event_queue.get()
            self._status = self._status.update(event)

    def init(self, func):
        """init runs once on server start, and is used to initialize the app's context.
        You can use this to load models onto the GPU, set up connections, etc.
        The context is then passed into all handlers and background tasks.
        Notes:
        - this function must return a dictionary
        - the context is not persisted to disk, and will be reloaded on server restart
        - the context is not shared between multiple replicas of the app
        """

        # def wrapper(worker_num):
        #     print(colored("Running init()", 'yellow'))
        #     self._context = func(worker_num)
        #     if not isinstance(self._context, dict):
        #         raise Exception("Potassium init() must return a dictionary")
            
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

    # handler is a blocking http POST handler
    def handler(self, route: str = "/"):
        "handler is a blocking http POST handler"

        route = self._standardize_route(route)
        if route in self._endpoints:
            raise RouteAlreadyInUseException()

        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(context, request):
                # send in app's stateful context if GPU, and the request
                out = func(context, request)

                if type(out) != Response:
                    raise Exception("Potassium Response object not returned")

                if type(out.body) != bytes and type(out.body) != GeneratorType:
                    raise Exception(
                        "Potassium Response object body must be bytes", type(out.body))

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
                return res

            self._event_queue.put((StatusEvent.INFERENCE_REQUEST_RECEIVED,))

            assert self._worker_pool is not None, "Worker pool not initialized"
            # use an internal id for critical path to prevent user from accidentally
            # breaking things by sending multiple requests with the same id
            internal_id = str(uuid.uuid4())
            if endpoint.type == "handler":
                self._worker_pool.apply_async(run_worker, args=(endpoint.func, req, internal_id, True))
                resp = self._response_mailbox.get_response(internal_id)

                flask_response = FlaskResponse(
                    resp.body,
                    status=resp.status,
                    headers=resp.headers
                )

                def on_close():
                    print("on_close")
                    self._response_mailbox.cleanup(internal_id)
               
                flask_response.call_on_close(on_close)

            elif endpoint.type == "background":
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
            self._event_queue.put((StatusEvent.INFERENCE_START, request_id))
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
                "idle_time": cur_status.idle_time,
                "inference_time": cur_status.longest_inference_time,
            })

            res.status_code = 200
            return res

        return flask_app
    
    def _init_server(self):
        self._idle_start_time = time.time()
        index_queue = ProcessQueue()
        for i in range(self._num_workers):
            index_queue.put(i)
        if self._num_workers == 1:
            Pool = ThreadPool
        else:
            Pool = ProcessPool
        self._worker_pool = Pool(self._num_workers, init_worker, (index_queue, self._event_queue, self._response_queue, self._init_func))

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        server = make_server(host, port, self._flask_app, threaded=True)
        print(colored(f"Serving at http://{host}:{port}\n------", 'green'))
        self._init_server()

        server.serve_forever()

