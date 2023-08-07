from fastapi import FastAPI, WebSocket, Request as FastAPIRequest, HTTPException
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from uvicorn import run as uvicorn_run
from threading import Thread, Lock
import functools
from queue import Queue, Full
import traceback
from termcolor import colored
import asyncio
import time


class Endpoint:
    def __init__(self, type, func):
        self.type = type
        self.func = func


class Request:
    def __init__(self, json: dict = {}, ws: WebSocket = None):
        self.json = json
        self.ws = ws


class Response:
    def __init__(self, status: int = 200, json: dict = {}):
        self.json = json
        self.status = status


class Potassium:
    "Potassium is a simple, stateful, GPU-enabled, and autoscaleable web framework for deploying machine learning models."

    def __init__(self, name):
        self.name = name

        # default init function, if the user doesn't specify one
        def empty_init():
            return {}

        # semi-private vars, not intended for users to modify
        self._init_func = empty_init
        self._endpoints = {}  # dictionary to store unlimited Endpoints, by unique route
        self._context = {}
        self._lock = Lock()
        self._event_chan = Queue(maxsize=1)

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

        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                out = func(self._context, request)

                if type(out) != Response:
                    raise Exception("Potassium Response object not returned")

                # check if out.json is a dict
                if type(out.json) != dict:
                    raise Exception("Potassium Response object json must be a dict")

                return out

            nonlocal route # we need to modify the route variable in the outer scope
            route = self._standardize_route(route)
            if route in self._endpoints:
                raise Exception("Route already in use")
            
            self._endpoints[route] = Endpoint(type="handler", func=wrapper)
            return wrapper

        return actual_decorator
    
    # websocket is a blocking http POST handler
    def websocket(self, route: str = "/"):
        "handler is a blocking http POST handler"

        def actual_decorator(func):
            @functools.wraps(func)
            async def wrapper(request):
                # send in app's stateful context if GPU, and the request
                await func(self._context, request)

            nonlocal route # we need to modify the route variable in the outer scope
            route = self._standardize_route(route)
            if route in self._endpoints:
                raise Exception("Route already in use")
            
            self._endpoints[route] = Endpoint(type="websocket", func=wrapper)
            return wrapper

        return actual_decorator

    # background is a non-blocking http POST handler
    def background(self, route: str = "/"):    
        "background is a non-blocking http POST handler"
        def actual_decorator(func):
            @functools.wraps(func)
            def wrapper(request):
                # send in app's stateful context if GPU, and the request
                return func(self._context, request)
            
            nonlocal route # we need to modify the route variable in the outer scope
            route = self._standardize_route(route)
            if route in self._endpoints:
                raise Exception("Route already in use")
            
            self._endpoints[route] = Endpoint(
                type="background", func=wrapper)
            return wrapper

        return actual_decorator

    # _handle_POST takes in a request and the endpoint it was routed to and handles it as expected by that endpoint
    async def _handle_POST(self, endpoint, request):
        # potassium rejects if lock already in use
        if self._is_working():
            res = JSONResponse()
            res.status_code = 423
            res.headers["X-Endpoint-Type"] = endpoint.type
            return res
        
        req_json = await request.json()

        if endpoint.type == "handler":
            req = Request(json=req_json)

            with self._lock:
                try:
                    out = endpoint.func(req)
                    res = JSONResponse(out.json)
                    res.status_code = out.status
                    res.headers["X-Endpoint-Type"] = endpoint.type
                    return res
                except:
                    tb_str = traceback.format_exc()
                    print(colored(tb_str, "red"))
                    res = JSONResponse(tb_str)
                    res.status_code = 500
                    res.headers["X-Endpoint-Type"] = endpoint.type
                    return res

        if endpoint.type == "background":
            req = Request(json=req_json)

            # run as threaded task
            def task(endpoint, lock, req):
                with lock:
                    try:
                        endpoint.func(req)
                    except Exception as e:
                        # do any cleanup before re-raising user error
                        self._write_event_chan(True)
                        raise e
                self._write_event_chan(True)

            thread = Thread(target=task, args=(endpoint, self._lock, req))
            thread.start()

            # send task start success message
            res = JSONResponse({"started": True})
            res.headers["X-Endpoint-Type"] = endpoint.type
            return res
        
    # _handle_websocket takes in a request and the endpoint it was routed to and handles it as expected by that endpoint
    async def _handle_websocket(self, endpoint, websocket: WebSocket):
        # potassium rejects if lock already in use
        if self._is_working():
            res = JSONResponse()
            res.status_code = 423
            res.headers["X-Endpoint-Type"] = endpoint.type
            return res
        
        with self._lock:
            try:
                await websocket.accept()
                req = Request(ws=websocket)
                await endpoint.func(req)
                await websocket.close()
            except:
                await websocket.close()
                tb_str = traceback.format_exc()
                print(colored(tb_str, "red"))
        

    def _write_event_chan(self, item):
        try:
            self._event_chan.put(item, block=False)
        except Full:
            pass

    def _read_event_chan(self) -> bool:
        return self._event_chan.get()

    def _is_working(self):
        return self._lock.locked()

    def _create_fastapi_app(self):
        fastapi_app = FastAPI()
        fastapi_app.router.route_class = APIRoute

        async def handle(request: FastAPIRequest, path: str = ""):
            route = "/" + path
            if route not in self._endpoints:
                raise HTTPException(status_code=404)
            endpoint = self._endpoints[route]
            return await self._handle_POST(endpoint, request)
        
        # add a single catchall route
        fastapi_app.add_api_route("/{path:path}", handle, methods=["POST"])

        async def handle_websocket(websocket: WebSocket):
            path = websocket.path_params["path"]
            route = "/" + path
            if route not in self._endpoints:
                raise HTTPException(status_code=404)
            endpoint = self._endpoints[route]
            return await self._handle_websocket(endpoint, websocket)
        
        fastapi_app.add_websocket_route("/{path:path}", handle_websocket)

        return fastapi_app

    # serve runs the http server
    def serve(self, host="0.0.0.0", port=8000):
        print(colored("------\nStarting Potassium Server 🍌", 'yellow'))
        self._init_func()
        app = self._create_fastapi_app()
        print(colored(f"Serving at http://{host}:{port}\n------", "green"))
        uvicorn_run(app, host=host, port=port)
       