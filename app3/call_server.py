import asyncio
import websockets

async def send_text_inputs():
    async with websockets.connect("ws://localhost:8000/classify") as websocket:
        # Send some text inputs
        await websocket.send("This is a positive message")
        await websocket.send("This is a negative message")
        await websocket.send("Another positive message")

        # Receive the predicted labels
        async for message in websocket:
            print("Received label:", message)

asyncio.run(send_text_inputs())
