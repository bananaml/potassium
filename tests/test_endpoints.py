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

    @app.init
    def init():
        return {}

    @app.background("/background")
    def background(context: dict, request: potassium.Request):
        pass
    client = app.test_client()

    res = client.post("/background", json={})
    assert res.status_code == 200

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

