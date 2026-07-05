import os
from typing import Annotated, Sequence, TypedDict, Dict, Any, List
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from sqlalchemy import text
from database import engine

import dotenv
dotenv.load_dotenv()

# --- MCP Tool Definition ---
# In a real MCP setup, this would be communicating via stdio or SSE to a separate server.
# Here, we simulate the MCP server tool wrapper for MySQL.
@tool
def execute_mysql_query(query: str) -> str:
    """Executes a SQL query against the school MySQL database and returns the results.
    The schema includes: 
    - users (id, username, role)
    - students (id, user_id, gpa)
    - teachers (id, user_id, department_id)
    - courses (id, name, credits)
    - classes (id, course_id, teacher_id)
    - enrollments (id, student_id, class_id)
    - attendance (id, student_id, class_id, status, date)
    - assignments, grades, fee_invoices, payments, alerts.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            # Return first 20 rows to avoid context bloat
            rows = result.fetchmany(20)
            columns = result.keys()
            
            output = f"Columns: {', '.join(columns)}\n"
            for row in rows:
                output += str(row) + "\n"
                
            return output if output.strip() else "Query returned 0 rows."
    except Exception as e:
        return f"Error executing query: {str(e)}"

# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    dashboard_state: Dict[str, Any]

# --- Model Setup ---
# Use Gemini Pro, ensuring the API key is set
gemini_model = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro-latest", 
    google_api_key=os.getenv("GEMINI_API_KEY", "DUMMY_KEY_FOR_LOCAL")
)

tools = [execute_mysql_query]
model_with_tools = gemini_model.bind_tools(tools)

# --- Nodes ---
def supervisor_node(state: AgentState):
    """The main orchestrator that decides what to do next."""
    messages = state["messages"]
    
    # System prompt for the orchestrator
    sys_prompt = (
        "You are the School Dashboard AI Orchestrator. "
        "You have access to an MCP tool `execute_mysql_query` to fetch data from the MySQL database. "
        "If the user asks a question, use the tool to query the database, then summarize the answer nicely. "
        "Do NOT perform data modifications (INSERT/UPDATE/DELETE)."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        *[(msg.type, msg.content) for msg in messages if msg.type in ['human', 'ai', 'tool']]
    ])
    
    # If the last message is a human message, we run the model
    # Wait, the prompt template needs careful handling of ToolMessages, so we just pass the raw messages
    # to avoid formatting issues.
    
    full_messages = [sys_prompt] + list(messages)
    # Actually just call model with tools
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}

def tool_node(state: AgentState):
    """Executes the tools chosen by the model."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_responses = []
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "execute_mysql_query":
                result = execute_mysql_query.invoke(tool_call["args"])
                tool_responses.append(
                    ToolMessage(
                        content=str(result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"]
                    )
                )
    return {"messages": tool_responses}

def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"
    return "end"


# --- Build Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    should_continue,
    {
        "continue": "tools",
        "end": END
    }
)
workflow.add_edge("tools", "supervisor")

app = workflow.compile()

def run_agent(user_query: str):
    """Entry point for the FastAPI endpoint."""
    inputs = {"messages": [HumanMessage(content=user_query)]}
    
    # Setup Langfuse Callback if credentials exist (disabled for MVP due to SDK path issues)
    callbacks = []
        
    config = {"callbacks": callbacks} if callbacks else {}
    
    # Run the graph
    result = app.invoke(inputs, config=config)
    
    # Get the last AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content
            
    return "I couldn't process that request."
