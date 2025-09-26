from langgraph.types import interrupt
from langchain_core.tools import tool

@tool
def human_tool(question: str) -> str:
    """ask human a question"""
    answer = interrupt(question)
    return answer