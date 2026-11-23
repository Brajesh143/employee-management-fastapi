from collections.abc import Callable
from typing import Any

import streamlit as st


def render_chatbot(api_request: Callable[..., Any]) -> None:
    st.title("AI Chatbot")
    st.caption(
        "The chat interface is ready. Agent and tool integration will be "
        "added later."
    )

    if "chatbot_messages" not in st.session_state:
        st.session_state.chatbot_messages = []

    if st.button("Clear conversation"):
        st.session_state.chatbot_messages = []
        st.rerun()

    for message in st.session_state.chatbot_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask a question")
    if not prompt or not prompt.strip():
        return

    messages = [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.chatbot_messages[-18:]
    ]
    messages.append({"role": "user", "content": prompt.strip()})
    st.session_state.chatbot_messages.append(
        {"role": "user", "content": prompt.strip()}
    )

    with st.chat_message("user"):
        st.markdown(prompt.strip())

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = api_request(
                "POST",
                "/chatbot/chat",
                json={"messages": messages},
            )
        if result is not None:
            reply = result["reply"]
            st.markdown(reply)
            st.session_state.chatbot_messages.append(
                {"role": "assistant", "content": reply}
            )

