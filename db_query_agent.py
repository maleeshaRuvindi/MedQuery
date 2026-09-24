from dotenv import load_dotenv
from langgraph.graph import StateGraph,START,END
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, SystemMessage
from tools import TOOLS
from langgraph.prebuilt import ToolNode,tools_condition
import os
import json
from guardrails import run_input_guards
from guardrails.output_guards import scrub_final_response
from guardrails.exceptions import GuardrailError
import logging
logger = logging.getLogger(__name__)
load_dotenv()
class State(TypedDict):
    messages: Annotated[list,add_messages]
llm = llm = init_chat_model("gpt-5.6-luna", model_provider="openai",reasoning_effort="none")
DB_PATH = os.path.join("data", "mimic_hosp.db")

table_names=['admissions', 'diagnoses_icd', 'drgcodes', 'd_hcpcs', 'd_icd_diagnoses', 'd_icd_procedures', 'd_labitems', 'emar', 'emar_detail', 'hcpcsevents', 'labevents', 'microbiologyevents', 'omr', 'patients', 'pharmacy', 'poe', 'poe_detail', 'prescriptions', 'procedures_icd', 'provider', 'services', 'transfers']

SYSTEM_PROMPT = SystemMessage(content=f"""
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
{json.dumps(table_names)}
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
# question = "What is the gender distribution of patients?"
# response = graph.invoke({
#     "messages": [SYSTEM_PROMPT, {"role": "user", "content": question}]
# })
# for i, msg in enumerate(response['messages']):
#     print(f"\n[{i}] {type(msg).__name__}")
#     print("  content:", repr(getattr(msg, 'content', None))[:300])
#     if hasattr(msg, 'tool_calls') and msg.tool_calls:
#         print("  tool_calls:", msg.tool_calls)
#     if hasattr(msg, 'tool_call_id'):
#         print("  tool_call_id:", msg.tool_call_id)
def run_medquery(user_question: str,config: dict = None) -> str:
    # Layer 1 — input guard
    try:
        run_input_guards(user_question)
    except GuardrailError as e:
        logger.warning(f"Input guardrail triggered — rule: {e.rule}")
        return e.message

    # Run graph
    response = graph.invoke({
        "messages": [SYSTEM_PROMPT, {"role": "user", "content": user_question}]
    },config={"recursion_limit": 15, **(config or {})},)

    final_message = response["messages"][-1]
    final_text = final_message.content if isinstance(final_message, AIMessage) else str(final_message.content)

    safe_response = scrub_final_response(final_text)
    logger.info(f"response: {safe_response}")
    return safe_response