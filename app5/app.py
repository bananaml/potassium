from potassium import Potassium, Request, Response
import json
import numpy as np

app = Potassium("my_app")

@app.handler("/")
def handler(context: dict, request: Request) -> Response:
    large_array = np.zeros(50_000_000)  # Create a large array of zeros
    response_data = {"large_array": list(large_array)}  # Convert to a list to create a JSON-serializable response
    response_json = json.dumps(response_data)  # Convert the data to a JSON string
    return Response(
        json=response_json,
        status=200
    )

if __name__ == "__main__":
    app.serve()
