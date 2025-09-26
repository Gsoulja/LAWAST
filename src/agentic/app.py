from src.agentic.workflow.workflow import build_workflow

if __name__ == "__main__":
    app = build_workflow()
    # app.invoke({"input": "Some task"})

    config = {"recursion_limit": 50}
    # inputs = {"input": "what is the hometown of the mens 2024 Australia open winner?"}
    inputs = {"input": "Was ist das ordentliche Rentenalter für Frauen in der AHV?"}
    app.invoke(inputs, config=config)
    # for event in app.astream(inputs, config=config):
    #     for k, v in event.items():
    #         if k != "__end__":
    #             print(v)
