from langchain_ollama import ChatOllama

def get_llm():
    return ChatOllama(
        model="qwen3:0.6b",
        temperature=0,
        num_predict=256,
        keep_alive="10m",
        client_kwargs={
            "timeout": 180,
        },
    )