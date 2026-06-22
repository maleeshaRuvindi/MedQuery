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
load_dotenv()
class State(TypedDict):
    messages: Annotated[list,add_messages]
llm = init_chat_model("openai/gpt-oss-120b", model_provider="groq", temperature=0)
DB_PATH = os.path.join("data", "mimic.db")

SYSTEM_PROMPT = SystemMessage(content="""
You are ClinIQ, an expert clinical data analyst with deep knowledge of the MIMIC III database schema.
Your job is to answer natural language questions about patient data by generating and executing accurate SQL queries.

## Workflow — always follow this order:
1. Identify which tables are needed to answer the question
2. Use the get_schema tool with those table names to retrieve column definitions
3. Write a precise SQL SELECT query using only the columns you confirmed exist
4. Use the execute_sql tool with the query
5. Check the result:
   - If row_count is 0, reconsider your query logic and retry with a corrected query
   - If values look clinically unreasonable (e.g. age of 300), revisit your query
   - If SQL error is returned, fix the query using the error message and retry
6. Once you have a valid result, synthesize a clear, concise answer in plain English

## Rules:
- Never guess column names — always use the get_schema tool first
- Only use SELECT queries
- Always interpret results in a clinical context for the user
- If the question cannot be answered from the available tables, say so clearly

## Available tables:
patients, admissions, diagnoses_icd
""")
@tool
def get_schema(table_names: list[str]) -> str:
    """
    Returns column names and types for the requested MIMIC tables.
    Call this before writing any SQL query.
    """
    schema = {
        "patients": [
            ("subject_id", "INTEGER"),
            ("gender", "TEXT"),
            ("anchor_age", "INTEGER"),
            ("anchor_year", "INTEGER"),
            ("anchor_year_group", "TEXT"),
            ("dod", "TEXT"),
        ],
        "admissions": [
            ("hadm_id", "INTEGER"),
            ("subject_id", "INTEGER"),
            ("admittime", "TEXT"),
            ("dischtime", "TEXT"),
            ("deathtime", "TEXT"),
            ("admission_type", "TEXT"),
            ("admit_provider_id", "TEXT"),
            ("admission_location", "TEXT"),
            ("discharge_location", "TEXT"),
            ("insurance", "TEXT"),
            ("language", "TEXT"),
            ("marital_status", "TEXT"),
            ("race", "TEXT"),
            ("edregtime", "TEXT"),
            ("edouttime", "TEXT"),
            ("hospital_expire_flag", "INTEGER")
        ],
        "diagnoses_icd": [
            ("subject_id", "INTEGER"),
            ("hadm_id", "INTEGER"),
            ("icd_code", "TEXT"),
            ("seq_num", "INTEGER"),
            ("icd_version", "INTEGER")
        ],
        # ... etc
    }

    result = []
    for table in table_names:
        if table in schema:
            cols = ", ".join(f"{col} ({dtype})" for col, dtype in schema[table])
            result.append(f"Table `{table}`: {cols}")
        else:
            result.append(f"Table `{table}`: not found")
    
    return "\n".join(result)
def is_safe_query(query: str) -> bool:
    forbidden = ["drop", "delete", "insert", "update", "alter", "truncate"]
    query_lower = query.lower().strip()
    return not any(word in query_lower for word in forbidden)
@tool
def execute_sql(query: str) -> str:
    """
    Execute a read-only SQL query against the MIMIC database.
    Returns columns, row count, and up to 20 rows of results.
    Always call get_schema first to ensure correct column names.
    """
    if not is_safe_query(query):
        return "Error: Only SELECT queries are permitted."
    
    if "limit" not in query.lower():
        query = query.rstrip(";") + " LIMIT 100;"
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return json.dumps({"row_count": 0, "message": "No results returned. The query may be too restrictive or reference wrong values."})
        
        return json.dumps({
            "row_count": len(df),
            "columns": list(df.columns),
            "data": df.head(20).to_dict(orient="records")
        }, indent=2, default=str)
    
    except Exception as e:
        return f"SQL Error: {str(e)}\nCheck column names using get_schema and try again."
    finally:
        conn.close()

tools=[get_schema,execute_sql]
llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
def chatbot(state: State) -> State:
    return {"messages":[llm_with_tools.invoke(state['messages'])]}
builder=StateGraph(State)
builder.add_node("chatbot_node",chatbot)
builder.add_node("tools",ToolNode(tools))
builder.add_edge(START,"chatbot_node")
builder.add_conditional_edges("chatbot_node",tools_condition)
builder.add_edge("tools","chatbot_node")
builder.add_edge("chatbot_node",END)
graph = builder.compile()
# png_data = graph.get_graph().draw_mermaid_png()
# with open("db_query_agent.png", "wb") as f:
#     f.write(png_data)
# print("Saved as db_query_agent.png")
question = "What is the gender distribution of patients?"
response = graph.invoke({
    "messages": [SYSTEM_PROMPT, {"role": "user", "content": question}]
})
for i, msg in enumerate(response['messages']):
    print(f"\n[{i}] {type(msg).__name__}")
    print("  content:", repr(getattr(msg, 'content', None))[:300])
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        print("  tool_calls:", msg.tool_calls)
    if hasattr(msg, 'tool_call_id'):
        print("  tool_call_id:", msg.tool_call_id)
