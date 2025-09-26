from langchain_core.prompts import ChatPromptTemplate

PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """For the given objective, come up with a simple step by step plan. \
            This plan should involve individual tasks, that if executed correctly will yield the correct answer. \
            The result of the final step should be the final answer. \
            Each step must contain all required information – no skipping steps.""",
        ),
        ("placeholder", "{messages}"),
    ]
)
