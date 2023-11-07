import pytest
import potassium

def test_json_response():
    response = potassium.Response(
        status=200,
        json={"key": "value"}
    )

    assert response.status == 200
    assert response.json == {"key": "value"}
    assert response.headers["Content-Type"] == "application/json"

    response.json = {"key": "value2"}
    assert response.json == {"key": "value2"}

def test_body_response():
    response = potassium.Response(
        status=200,
        body=b"Hello, world!"
    )

    assert response.status == 200
    assert response.body == b"Hello, world!"
    assert 'Content-Type' not in response.headers

    response.json = {"key": "value2"}

    assert response.json == {"key": "value2"}
    assert response.headers["Content-Type"] == "application/json"

    


