import asyncio
from potassium import Potassium, WebSocket

from transformers import AutoTokenizer, AutoModelForSequenceClassification

app = Potassium("bert_ws_app")

# Load the tokenizer and model in app.init
@app.init
def init():
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    model = AutoModelForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=2)
    return {"tokenizer": tokenizer, "model": model}

# Define the WebSocket handler
@app.websocket_handler("/classify")
async def classify(websocket: WebSocket, context: dict):
    # Receive text inputs from the WebSocket
    async for message in websocket:
        text = message.data
        # Tokenize the input text
        inputs = context["tokenizer"](text, return_tensors="pt")
        # Make a prediction using the pre-trained BERT model
        outputs = context["model"](**inputs)[0]
        _, predicted = torch.max(outputs, 1)
        label = predicted.item()
        # Send the predicted label back through the WebSocket
        await websocket.send(str(label))

if __name__ == "__main__":
    app.serve()
