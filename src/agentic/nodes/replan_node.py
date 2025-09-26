from typing import Union

from langchain_huggingface import HuggingFaceEndpoint
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from src.agentic.models.state import PlanExecute
from src.agentic.prompts.replanner_prompt import REPLANNER_PROMPT


class Plan(BaseModel):
    steps: list[str] = Field(description="Steps to follow in sorted order")

class Response(BaseModel):
    response: str

class Act(BaseModel):
    action: Union[Response, Plan]

def replan_step(state: PlanExecute):
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
    replanner = REPLANNER_PROMPT | llm.with_structured_output(Act)

    output = replanner.invoke(state)
    # output = replanner.invoke({"messages": [{"role": "user", "content": state}]})
    if isinstance(output.action, Response):
        return {"response": output.action.response}
    return {"plan": output.action.steps}
