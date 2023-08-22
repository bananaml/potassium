import queue
import threading
import time
import pytest
import potassium


def test_handler():
    app = potassium.Potassium("my_app")

    @app.init
    def init():
        return {}

    @app.handler()
    def handler(context: dict, request: potassium.Request) -> potassium.Response:
        return potassium.Response(
            json={"hello": "root"},
            status=200
        )

    @app.handler("/some_path")
    def handler2(context: dict, request: potassium.Request) -> potassium.Response:
        return potassium.Response(
            json={"hello": "some_path"},
            status=200
        )

    @app.handler("/some_path/child_path")
    def handler2_id(context: dict, request: potassium.Request) -> potassium.Response:
        return potassium.Response(
            json={"hello": f"some_path/child_path"},
            status=200
        )

    client = app.test_client()

    res = client.post("/", json={})
    assert res.status_code == 200
    assert res.json == {"hello": "root"}

    res = client.post("/some_path", json={})
    assert res.status_code == 200
    assert res.json == {"hello": "some_path"}

    res = client.post("/some_path/child_path", json={})
    assert res.status_code == 200
    assert res.json == {"hello": "some_path/child_path"}

def test_background():
    app = potassium.Potassium("my_app")

    order_of_execution_queue = queue.Queue()
    resolve_background_condition = threading.Condition()

    @app.init
    def init():
        return {}

    @app.background("/background")
    def background(context: dict, request: potassium.Request):
        order_of_execution_queue.put("background_started")
        with resolve_background_condition:
            resolve_background_condition.wait()

    client = app.test_client()

    # send post in separate thread
    res = client.post("/background", json={})
    assert res.status_code == 200

    def wait_for_lock():
        order_of_execution_queue.put("wait_for_lock")
        app.block_until_gpu_lock_released()
        order_of_execution_queue.put("lock_released")

    thread = threading.Thread(target=wait_for_lock)
    thread.start()

    # notify background thread to continue
    order_of_execution_queue.put("notify_background")
    with resolve_background_condition:
        resolve_background_condition.notify()

    thread.join()

    # assert order of execution
    assert order_of_execution_queue.get() == "background_started"
    assert order_of_execution_queue.get() == "wait_for_lock"
    assert order_of_execution_queue.get() == "notify_background"
    assert order_of_execution_queue.get() == "lock_released"

# parameterized test for path collisions
@pytest.mark.parametrize("paths", [
    ("/", "",),
    ("/foo", "foo"),
])
def test_path_collision(paths):
    app = potassium.Potassium("my_app")

    @app.init
    def init():
        return {}

    @app.handler(paths[0])
    def handler(context: dict, request: potassium.Request) -> potassium.Response:
        return potassium.Response(
            json={},
            status=200
        )

    # expect exception
    with pytest.raises(potassium.RouteAlreadyInUseException):
        @app.handler(paths[1])
        def handler2(context: dict, request: potassium.Request) -> potassium.Response:
            return potassium.Response(
                json={},
                status=200
            )

def test_status():
    app = potassium.Potassium("my_app")

    resolve_background_condition = threading.Condition()

    @app.init
    def init():
        return {}

    @app.background("/background")
    def background(context: dict, request: potassium.Request):
        with resolve_background_condition:
            resolve_background_condition.wait()

    client = app.test_client()

    # send get for status
    res = client.get("/__status__", json={})

    assert res.status_code == 200
    assert res.json == {
        "gpu_available": True,
        "sequence_number": 0,
    }

    # send background post in separate thread
    res = client.post("/background", json={})
    assert res.status_code == 200

    # check status
    res = client.get("/__status__", json={})

    assert res.status_code == 200
    assert res.json == {
        "gpu_available": False,
        "sequence_number": 1,
    }

    # notify background thread to continue
    with resolve_background_condition:
        resolve_background_condition.notify()

    # wait for the lock to be released
    app.block_until_gpu_lock_released()

    # check status
    res = client.get("/__status__", json={})

    assert res.status_code == 200
    assert res.json == {
        "gpu_available": True,
        "sequence_number": 1,
    }

