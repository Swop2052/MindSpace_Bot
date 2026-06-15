from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from prompts import SYSTEM_PROMPT
from llm import llm
from safety import analyze_safety_risk
from safe_response import generate_safe_response


def build_context(history):

    if not history:
        return ""

    formatted = []

    recent = history[-8:]

    for msg in recent:

        if msg["role"] == "user":
            formatted.append(
                f"User: {msg['message']}"
            )

        else:
            formatted.append(
                f"Assistant: {msg['message']}"
            )

    return "\n".join(formatted)


def generate_response(
    user_message,
    history
):
    safety_analysis = analyze_safety_risk(
        user_message
    )

    if safety_analysis[
        "is_self_harm_risk"
    ]:
        return generate_safe_response(
            user_message,
            safety_analysis
        )

    context = build_context(
        history
    )

    if safety_analysis[
        "is_mental_health_intent"
    ]:
        intent_label = "MENTAL_HEALTH_SUPPORT"
    else:
        intent_label = "GENERAL_CHAT"

    prompt = f"""
Previous conversation:

{context}

Current user message:

{user_message}

Detected intent:

{intent_label}

Respond naturally.

IMPORTANT:

- Understand intent first, then answer.
- Continue conversation naturally.
- Match language.
- Keep responses casual.
- Avoid robotic replies.
- Do not hallucinate facts or make up resources.
- If unsure, say so briefly and ask one clarifying question.
"""

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT
        ),
        HumanMessage(
            content=prompt
        )
    ]

    try:
        response = llm.invoke(
            messages
        )

        content = response.content.strip()

        if not content:
            return (
                "I hear you. I want to understand you better. "
                "Can you tell me a little more about what feels hardest right now?"
            )

        return content

    except Exception:
        return (
            "I'm here with you. I had a temporary issue generating a reply, "
            "but I still want to support you. Tell me what you're feeling right now."
        )


def main():

    print("=" * 50)
    print(" Conversational AI Chatbot ")
    print(" Type 'exit' to quit ")
    print("=" * 50)

    conversation_history = []

    while True:

        user_input = input(
            "\nYou: "
        )

        if (
            user_input.lower()
            == "exit"
        ):
            print(
                "\nBot: Goodbye!"
            )
            break

        response = generate_response(
            user_input,
            conversation_history
        )

        print(
            f"\nBot: {response}"
        )

        conversation_history.append(
            {
                "role": "user",
                "message": user_input
            }
        )

        conversation_history.append(
            {
                "role": "assistant",
                "message": response
            }
        )


if __name__ == "__main__":
    main()