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

    @app.handler("/some_binary_response")
    def handler3(context: dict, request: potassium.Request) -> potassium.Response:
        return potassium.Response(
            body=b"hello",
            status=200,
            headers={"Content-Type": "application/octet-stream"}
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

    res = client.post("/some_binary_response", json={})
    assert res.status_code == 200
    assert res.data == b"hello"
    assert res.headers["Content-Type"] == "application/octet-stream"

    res = client.post("/some_path/child_path", json={})
    assert res.status_code == 200
    assert res.json == {"hello": "some_path/child_path"}

    res = client.post("/", data='{"key": unquoted_value}', content_type='application/json')
    assert res.status_code == 400
    # check status
    res = client.get("/__status__")
    assert res.status_code == 200
    assert res.json is not None
    assert res.json["gpu_available"] == True

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
    assert res.json is not None
    assert res.json["gpu_available"] == True
    assert res.json["sequence_number"] == 0
    assert res.json["idle_time"] > 0
    assert res.json["inference_time"] == 0

    # send background post in separate thread
    res = client.post("/background", json={})
    assert res.status_code == 200

    # add a small sleep for inference time to be above 0
    time.sleep(0.1)

    # check status
    res = client.get("/__status__", json={})

    assert res.status_code == 200
    assert res.json is not None
    assert res.json["gpu_available"] == False
    assert res.json["sequence_number"] == 1
    assert res.json["idle_time"] == 0
    assert res.json["inference_time"] > 0

    # notify background thread to continue
    with resolve_background_condition:
        resolve_background_condition.notify()

    # wait for the lock to be released
    time.sleep(0.1)

    # check status
    res = client.get("/__status__", json={})

    assert res.status_code == 200
    assert res.json is not None
    assert res.json["gpu_available"] == True
    assert res.json["sequence_number"] == 1
    assert res.json["idle_time"] > 0
    assert res.json["inference_time"] == 0

    res = client.post("/this_path_does_not_exist", json={})
    assert res.status_code == 404
    res = client.get("/__status__", json={})
    assert res.status_code == 200
    assert res.json is not None
    assert res.json["gpu_available"] == True
    assert res.json["sequence_number"] == 2


def test_wait_for_background_task():
    app = potassium.Potassium("my_app")

    order_of_execution_queue = queue.Queue()
    resolve_background_condition = threading.Condition()

    @app.init
    def init():
        return {}

    @app.background("/background")
    def background(context: dict, request: potassium.Request):
        with resolve_background_condition:
            resolve_background_condition.wait()

    
    def wait_for_background_task():
        app._read_event_chan()
        order_of_execution_queue.put("background_task_completed")

    thread = threading.Thread(target=wait_for_background_task)
    thread.start()

    client = app.test_client()

    # send background post in separate thread
    order_of_execution_queue.put("send_background_task")
    res = client.post("/background", json={})
    assert res.status_code == 200

    # notify background thread to continue
    with resolve_background_condition:
        resolve_background_condition.notify()

    thread.join()

    # assert order of execution
    assert order_of_execution_queue.get() == "send_background_task"
    assert order_of_execution_queue.get() == "background_task_completed"

def test_warmup():
    app = potassium.Potassium("my_app")

    @app.init
    def init():
        return {}

    @app.handler()
    def handler(context: dict, request: potassium.Request) -> potassium.Response:
        raise Exception("should not be called")

    client = app.test_client()

    res = client.post("/_k/warmup", json={})
    assert res.status_code == 200
    assert res.json == {"warm": True}

    res = client.get("/__status__", json={})
    assert res.status_code == 200
    assert res.json is not None
    assert res.json["gpu_available"] == True
    assert res.json["sequence_number"] == 1
