"""
lambda_handler.py

Entry point AWS Lambda invokes. Wraps the existing db_query_agent.py graph

API Gateway (HTTP API, Lambda proxy integration) invokes this with an `event`
dict containing the HTTP request; we extract the question, run the graph, and
return a properly-shaped HTTP response.

DB_PATH note: tools.py currently does:
    DB_PATH = os.path.join("data", "mimic.db")
This is a RELATIVE path. Lambda's container working directory is /var/task
(where your deployment image's WORKDIR lands), so as long as the Dockerfile
COPYs data/mimic.db to /var/task/data/mimic.db, this relative path resolves
correctly with ZERO code change in tools.py. 
"""

import json
import logging

from db_query_agent import graph, SYSTEM_PROMPT

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Expects a JSON body like: {"question": "What is the gender distribution of patients?"}
    Returns a JSON body like: {"answer": "...", "question": "..."}
    """
    try:
        body = json.loads(event.get("body") or "{}")
        question = body.get("question")

        if not question:
            return _response(400, {"error": "Missing 'question' in request body."})

        logger.info(f"Processing question: {question}")

        result = graph.invoke(
            {"messages": [SYSTEM_PROMPT, {"role": "user", "content": question}]},
            config={"recursion_limit": 15},
        )

        final_message = result["messages"][-1]
        answer = final_message.content if hasattr(final_message, "content") else str(final_message)

        return _response(200, {"question": question, "answer": answer})

    except Exception as e:
        logger.exception("Error processing request")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
    """Shapes a response for API Gateway's Lambda proxy integration."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
