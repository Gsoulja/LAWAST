from langchain_core.prompts import ChatPromptTemplate

REPLANNER_PROMPT = ChatPromptTemplate.from_template(
    """For the given objective, update the plan based on past progress.

Objective:
{input}

Original plan:
{plan}

Completed steps:
{past_steps}

Update your plan accordingly. 
- If no more steps are needed, respond with a final answer. 
- Otherwise, return only the remaining necessary steps."""
)
