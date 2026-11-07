from fastapi import FastAPI
from models import Message
from hello_world_utils import hello_world

app = FastAPI(
    title="Bio informatics",
    description="project backend",
    version="0.0.1"
)

@app.get(
    "/",
    response_model=Message,
    summary="Hello World",
    description="Returns a hello world message.",
)
def get_hello_world():
    return hello_world()
