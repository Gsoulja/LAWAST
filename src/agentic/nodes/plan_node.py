from langchain_huggingface import HuggingFaceEndpoint
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from src.agentic.models.state import PlanExecute
from src.agentic.prompts.planner_prompt import PLANNER_PROMPT


class Plan(BaseModel):
    steps: list[str] = Field(description="Steps to follow in sorted order")

def plan_node(state: PlanExecute):
    api_key = ""
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-4-maverick:free",
        api_key=api_key,
        temperature=0
    )
    # llm = HuggingFaceEndpoint(
    #     repo_id="swiss-ai/Apertus-8B-Instruct-2509",
    #     huggingfacehub_api_token="",
    #     provider="auto",  # set your provider here hf.co/settings/inference-providers
    # )
    planner = PLANNER_PROMPT | llm.with_structured_output(Plan)
    result = planner.invoke({"messages": [("user", state["input"])]})
    return {"plan": result.steps}
