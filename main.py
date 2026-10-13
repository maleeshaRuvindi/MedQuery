from fastapi import FastAPI
from pydantic import BaseModel
from agent.db_query_agent import run_medquery

app = FastAPI()

class UserQuery(BaseModel):
    question:str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/chat")
async def run_agent(question:str):
    return await run_medquery(question)
