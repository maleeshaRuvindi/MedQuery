from dotenv import load_dotenv
from langgraph.graph import StateGraph,START,END
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
import sqlite3
import pandas as pd
import json
from langgraph.prebuilt import ToolNode,tools_condition
import os
from tools import TOOLS
load_dotenv()
class State(TypedDict):
    messages: Annotated[list,add_messages]
llm = init_chat_model("openai/gpt-oss-120b", model_provider="groq", temperature=0)
DB_PATH = os.path.join("data", "mimic.db")

SYSTEM_PROMPT = SystemMessage(content="""
You are ClinIQ, an expert clinical data analyst with deep knowledge of the MIMIC-IV database schema.
Your job is to answer natural language questions about patient data by generating and executing accurate SQL queries.
 
## Workflow — always follow this order:
1. Call search_schema with a description of what clinical data you need (e.g. "lab results for kidney function",
   not a guessed table name). This searches across the FULL schema and returns the most relevant tables and,
   for wide event tables, the most relevant columns.
2. Use get_schema with the exact table name(s) returned by search_schema to confirm the precise column
   definitions before writing any SQL. Never guess column names.
3. Write a precise SQL SELECT query using only the columns you confirmed exist.
4. Use the execute_sql tool with the query.
5. Check the result:
   - If row_count is 0, reconsider your query logic and retry with a corrected query
   - If values look clinically unreasonable (e.g. age of 300), revisit your query
   - If SQL error is returned, fix the query using the error message and retry
6. Once you have a valid result, synthesize a clear, concise answer in plain English
 
## Rules:
- NEVER guess table or column names — always use search_schema first, then get_schema to confirm.
- If search_schema doesn't return a confident match (low relevance scores, or nothing relevant),
  say clearly that the question cannot be answered from the available schema instead of guessing.
- Only use SELECT queries.
- For wide tables (chartevents, labevents), search_schema may return specific matched columns
  (e.g. itemid values or column names) — use these to narrow your WHERE clause precisely rather
  than scanning the whole table.
- Always interpret results in a clinical context for the user.
""")


llm_with_tools = llm.bind_tools(TOOLS, tool_choice="auto")
def chatbot(state: State) -> State:
    return {"messages":[llm_with_tools.invoke(state['messages'])]}
builder=StateGraph(State)
builder.add_node("chatbot_node",chatbot)
builder.add_node("tools",ToolNode(TOOLS))
builder.add_edge(START,"chatbot_node")
builder.add_conditional_edges("chatbot_node",tools_condition)
builder.add_edge("tools","chatbot_node")
builder.add_edge("chatbot_node",END)
graph = builder.compile()
# png_data = graph.get_graph().draw_mermaid_png()
# with open("db_query_agent.png", "wb") as f:
#     f.write(png_data)
# print("Saved as db_query_agent.png")
if __name__ == "__main__":
    question = "What is the gender distribution of patients?"
    response = graph.invoke(
        {"messages": [SYSTEM_PROMPT, {"role": "user", "content": question}]},
        config={"recursion_limit": 10},
    )
    for i, msg in enumerate(response["messages"]):
        print(f"\n[{i}] {type(msg).__name__}")
        print("  content:", repr(getattr(msg, "content", None))[:300])
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print("  tool_calls:", msg.tool_calls)
        if hasattr(msg, "tool_call_id"):
            print("  tool_call_id:", msg.tool_call_id)