"""
NEXUS Forge — Multi-Agent Orchestrator

LangGraph-based state machine for hierarchical agent orchestration.
Includes Executive, Manufacturing, and Finance agents.
"""
from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

# Define the state for our agent graph
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    current_agent: str
    pending_approval: bool
    final_response: str

def mock_llm_response(prompt: str) -> str:
    """Mock LLM logic to determine routing and responses for MVP."""
    prompt_lower = prompt.lower()
    if "production" in prompt_lower or "transformer" in prompt_lower or "supply" in prompt_lower:
        return "ROUTE:Manufacturing"
    elif "revenue" in prompt_lower or "cost" in prompt_lower or "budget" in prompt_lower:
        return "ROUTE:Finance"
    elif "trust" in prompt_lower or "quality" in prompt_lower:
        return "The fabric quality monitor lists cur_sales_logs at 87% trust. Try running a Steward scan to check for anomalies."
    elif "lineage" in prompt_lower or "trace" in prompt_lower:
        return "Checking Context Graph... Entity 'transformer_maintenance' flows through clean zones directly into Uptime and Revenue metrics."
    elif "sales" in prompt_lower or "table" in prompt_lower:
        return "Table 'clean_sales_logs' is stored in MinIO S3 and tracked by Postgres schema registry."
    return "I am the Executive Agent. I can help route your request to Manufacturing or Finance."

def executive_node(state: AgentState):
    """The Executive Agent routes tasks to specialists."""
    last_message = state["messages"][-1].content
    response = mock_llm_response(last_message)
    
    if "ROUTE:Manufacturing" in response:
        return {"current_agent": "Manufacturing", "messages": [AIMessage(content="Delegating to Manufacturing Agent...")]}
    elif "ROUTE:Finance" in response:
        return {"current_agent": "Finance", "messages": [AIMessage(content="Delegating to Finance Agent...")]}
        
    return {"current_agent": "Executive", "final_response": response, "messages": [AIMessage(content=response)]}

def manufacturing_node(state: AgentState):
    """The Manufacturing Specialist Agent."""
    response = "I have analyzed the production impact. I recommend adjusting the transformer maintenance schedule. This requires human approval."
    return {
        "current_agent": "Manufacturing",
        "pending_approval": True,
        "final_response": response,
        "messages": [AIMessage(content=response)]
    }

def finance_node(state: AgentState):
    """The Finance Specialist Agent."""
    response = "I have reviewed the budget implications. Cost increase is within the 5% tolerance. Approval required to lock budget."
    return {
        "current_agent": "Finance",
        "pending_approval": True,
        "final_response": response,
        "messages": [AIMessage(content=response)]
    }

def should_continue(state: AgentState):
    """Routing logic between nodes."""
    if state.get("final_response"):
        return "end"
    if state["current_agent"] == "Manufacturing":
        return "manufacturing"
    if state["current_agent"] == "Finance":
        return "finance"
    return "end"

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("executive", executive_node)
workflow.add_node("manufacturing", manufacturing_node)
workflow.add_node("finance", finance_node)

workflow.set_entry_point("executive")

workflow.add_conditional_edges(
    "executive",
    should_continue,
    {
        "manufacturing": "manufacturing",
        "finance": "finance",
        "end": END
    }
)

workflow.add_edge("manufacturing", END)
workflow.add_edge("finance", END)

app_graph = workflow.compile()

def process_chat(message: str) -> Dict[str, Any]:
    """Entry point for the API to interact with the multi-agent system."""
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "current_agent": "Executive",
        "pending_approval": False,
        "final_response": ""
    }
    
    final_state = app_graph.invoke(initial_state)
    
    return {
        "agent": final_state["current_agent"],
        "response": final_state["final_response"],
        "requires_approval": final_state["pending_approval"]
    }
