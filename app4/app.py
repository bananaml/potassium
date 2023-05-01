from potassium import Potassium, Request, Response, send_webhook
import time

app = Potassium("my_app")

# This function runs in the background and simply sleeps for 5 seconds before logging a message
@app.background("/background_job", gpu=False)
def background_handler(context: dict, request: Request) -> Response:
    time.sleep(5)
    print("Background job completed")
    send_webhook(url="http://localhost:8000/", json={"outputs": "dis work?"})

@app.handler("/", gpu=False)
def handler(context: dict, request: Request) -> Response:
    outputs = request.json.get("outputs")

    return Response(
        json = {"outputs": outputs}, 
        status=200
    )
if __name__ == "__main__":
    app.serve()
