from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Connected to the websocket!")