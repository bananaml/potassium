import potassium

potassium_test_app = potassium.Potassium("test_app")

@potassium_test_app.init
def init():
    return {}

@potassium_test_app.handler()
def handler(context: dict, request: potassium.Request) -> potassium.Response:
    return potassium.Response(
        json={"hello": "root"},
        status=200
    )

@potassium_test_app.handler("/some_path")
def handler2(context: dict, request: potassium.Request) -> potassium.Response:
    return potassium.Response(
        json={"hello": "some_path"},
        status=200
    )

@potassium_test_app.handler("/some_binary_response")
def handler3(context: dict, request: potassium.Request) -> potassium.Response:
    return potassium.Response(
        body=b"hello",
        status=200,
        headers={"Content-Type": "application/octet-stream"}
    )

@potassium_test_app.handler("/some_path_byte_stream_response")
def handler4(context: dict, request: potassium.Request) -> potassium.Response:
    def stream():
        yield b"hello"
        yield b"world"

    return potassium.Response(
        body=stream(),
        status=200,
        headers={"Content-Type": "application/octet-stream"}
    )

@potassium_test_app.handler("/some_path/child_path")
def handler2_id(context: dict, request: potassium.Request) -> potassium.Response:
    return potassium.Response(
        json={"hello": f"some_path/child_path"},
        status=200
    )

@potassium_test_app.handler("/some_headers_request")
def handler5(context: dict, request: potassium.Request) -> potassium.Response:
    assert request.headers["A"] == "a"
    assert request.headers["B"] == "b"
    assert request.headers["X-Banana-Request-Id"] == request.id
    return potassium.Response(
        headers={"A": "a", "B": "b", "X-Banana-Request-Id": request.id},
        json={"hello": "some_headers_request", "id": request.id},
        status=200
    )

