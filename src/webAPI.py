from fastapi import FastAPI

app = FastAPI(title="ticup")

@app.post("/chat")
async def chat_endpoint(msg: str):
