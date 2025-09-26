from typing import List

from langchain_core.tools import tool


class Record:
    fact: str = ""

@tool
def retrieval_tool(question: str) -> List[Record]:
    """retrieve relevant laws and legal cases"""
    #TODO: implement the tool
    return list(Record(fact="No relevant info were found."))