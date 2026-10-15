from fastapi import FastAPI
from pydantic import BaseModel
from agent.db_query_agent import run_medquery
from fastapi import HTTPException
from langgraph.errors import GraphRecursionError
import asyncio
import logging
logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 60
app = FastAPI()

class UserQuery(BaseModel):
    question:str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
async def run_agent(question: str):
    try:
        return await asyncio.wait_for(
            run_medquery(question),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Request timed out")
        raise HTTPException(status_code=504, detail="The request took too long. Please try again.")
    except GraphRecursionError:
        logger.error("Agent hit the recursion limit")
        raise HTTPException(status_code=500, detail="I couldn't complete that query. Please rephrase and try again.")
