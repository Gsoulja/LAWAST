from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.agentic.models.state import PlanExecute
from src.agentic.prompts.base_prompt import BASE_SYSTEM_PROMPT
from src.agentic.tools.human_tool import human_tool
from src.agentic.tools.retrieval_tool import retrieval_tool
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace


def legal_case_element_node(state: PlanExecute):
    api_key=""
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
    # llm = ChatHuggingFace(llm=llm)
    agent_executor = create_react_agent(
        llm,
        tools=[human_tool, retrieval_tool],
        prompt=BASE_SYSTEM_PROMPT
    )
    # inputs = {
    #     "messages": [
    #         {"role": "system", "content": "TODO: reserch topic using the tools"},
    #         {"role": "user", "content": topic}
    #     ]
    # }
    # return graph.invoke(inputs)

    plan = state["plan"]
    task = plan[0]
    plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
    task_formatted = f"For the plan:\n{plan_str}\n\nExecute step 1: {task}"
    agent_response = agent_executor.invoke({"messages": [{"role": "user", "content": task_formatted}]})
    return {"past_steps": [(task, agent_response["messages"][-1].content)]}
