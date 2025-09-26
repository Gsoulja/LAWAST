from langgraph.constants import END
from langgraph.graph import StateGraph, START

from src.agentic.models.state import PlanExecute
from src.agentic.nodes.legal_case_element_node import legal_case_element_node
from src.agentic.nodes.plan_node import plan_node
from src.agentic.nodes.replan_node import replan_step


def should_end(state: PlanExecute):
    return END if state.get("response") else "agent"

def build_workflow():
    workflow = StateGraph(PlanExecute)
    workflow.add_node("planner", plan_node)
    workflow.add_node("agent", legal_case_element_node)
    workflow.add_node("replan", replan_step)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "agent")
    workflow.add_edge("agent", "replan")
    workflow.add_conditional_edges(
        "replan",
        should_end,
        ["agent", END]
    )

    return workflow.compile()
