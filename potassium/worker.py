from multiprocessing import Queue
import os
import threading
from typing import Dict, Any, Generator
from dataclasses import dataclass
from flask import make_response, Response as FlaskResponse
from termcolor import colored
import traceback
import inspect

from .status import StatusEvent
from .types import Response

worker = None

class FDRedirect():
    def __init__(self, fd: int):
        self._fd = fd
        self._fd_copy = os.dup(fd)
        self._redirect_w = None

    def _run_redirect_loop(self, redirect_r, prefix):
        redirect_r = os.fdopen(redirect_r, "r")

        for line in redirect_r:
            os.write(self._fd_copy, (prefix + line).encode("utf-8"))
        redirect_r.close()

    def set_prefix(self, prefix):
        if self._redirect_w is not None:
            os.dup2(self._fd_copy, self._fd)
            os.close(self._redirect_w)

        fd = self._fd
        redirect_r, redirect_w = os.pipe()

        self._fd_copy = os.dup(fd)
        os.dup2(redirect_w, fd)
        self._redirect_w = redirect_w

        t = threading.Thread(target=self._run_redirect_loop, args=(redirect_r, prefix))
        t.daemon = True
        t.start()


@dataclass
class Worker():
    worker_num: int
    total_workers: int
    context: Dict[Any, Any]
    event_queue: Queue
    response_queue: Queue
    stderr_redirect: FDRedirect
    stdout_redirect: FDRedirect

def init_worker(index_queue, event_queue, response_queue, init_func, total_workers):
    global worker
    worker_num = index_queue.get()

    stdout_redirect = FDRedirect(1)
    stderr_redirect = FDRedirect(2)

    if total_workers > 1:
        stderr_redirect.set_prefix(f"[worker {worker_num}] ")
        stdout_redirect.set_prefix(f"[worker {worker_num}] ")

    # check if the init function takes in a worker number
    print(colored("Running init()", 'yellow'))
    try:
        if len(inspect.signature(init_func).parameters) == 0:
            context = init_func()
        else:
            context = init_func(worker_num)
    except Exception as e:
        tb_str = traceback.format_exc()
        print(colored(tb_str, "red"))
        raise e

    if not isinstance(context, dict):
        raise Exception("Potassium init() must return a dictionary")

    event_queue.put((StatusEvent.WORKER_STARTED,))

    worker = Worker(
        worker_num,
        total_workers,
        context,
        event_queue,
        response_queue,
        stdout_redirect,
        stderr_redirect
    )

def run_worker(func, request, internal_id, use_response=False):
    assert worker is not None, "worker is not initialized"
    
    if worker.total_workers > 1:
        prefix = f"[worker {worker.worker_num}, requestID {request.id}] "
    else:
        prefix = f"[requestID {request.id}] "


    worker.stderr_redirect.set_prefix(prefix)
    worker.stdout_redirect.set_prefix(prefix)

    resp = None
    worker.event_queue.put((StatusEvent.INFERENCE_START, internal_id))

    try:
        resp = func(worker.context, request)
    except:
        tb_str = traceback.format_exc()
        print(colored(tb_str, "red"))
        resp = Response(
            status=500,
            body=tb_str.encode("utf-8"),
            headers={
                "Content-Type": "text/plain"
            }
        )

    if use_response:
        generator = None
        stream_id = None
        if inspect.isgenerator(resp.body):
            stream_id = 'stream-' + internal_id
            generator = resp.body
            resp.body = None
        worker.response_queue.put((internal_id, (resp, stream_id)))

        # if the response is a generator, we need to iterate through it
        if stream_id:
            assert generator is not None
            for chunk in generator:
                worker.response_queue.put((stream_id, chunk))
            worker.response_queue.put((stream_id, None))


    if worker.total_workers == 1:
        worker.stderr_redirect.set_prefix("")
        worker.stdout_redirect.set_prefix("")

    worker.event_queue.put((StatusEvent.INFERENCE_END, internal_id))

