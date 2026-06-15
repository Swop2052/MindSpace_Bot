from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from llm import llm

SUPPORT_MESSAGE = """

----------------------------

Helpline: 8448440632

Email:
manodarpan-mhrd@gov.in

Website:
https://manodarpan.education.gov.in/

"""


FALLBACK_SAFE_REPLY = (
    "I'm really glad you shared this. "
    "You matter, and you don't have to handle this alone. "
    "If you might hurt yourself or feel in immediate danger, "
    "please call your local emergency services right now and contact "
    "someone you trust to stay with you. "
    "If you want, we can take one small step together right now: "
    "drink some water, take 10 slow breaths, and tell me where you are."
)


def generate_safe_response(user_message, risk_analysis=None):
    risk_level = "HIGH"

    if risk_analysis:
        risk_level = risk_analysis.get(
            "risk_level",
            "HIGH"
        )

    prompt = f"""
You are responding to a mental-health crisis conversation.

Risk level: {risk_level}

Rules you must follow:
- Be calm, caring, and concise.
- Validate emotion first.
- Do not provide any harmful methods or details.
- Ask one direct safety check question.
- Suggest immediate support from trusted person and local emergency services if danger is immediate.
- Offer one grounding step (for example breathing, water, sitting with someone).
- Keep it human and non-robotic.

User message:
{user_message}
"""

    try:
        response = llm.invoke([
            SystemMessage(
                content="You are a safe mental-health support assistant."
            ),
            HumanMessage(
                content=prompt
            )
        ])

        reply = response.content.strip()

        if not reply:
            reply = FALLBACK_SAFE_REPLY

    except Exception:
        reply = FALLBACK_SAFE_REPLY

    return (
        reply
        + SUPPORT_MESSAGE
    )