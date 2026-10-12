"""
Safe response generation for crisis situations.
"""

from llm import llm
from langchain_core.messages import SystemMessage, HumanMessage
from prompts import SYSTEM_PROMPT

# Direct helpline numbers - always show these in crisis
CRISIS_HELPLINE_MESSAGE = """

----------------------------
📞 **IMMEDIATE SUPPORT - त्वरित मदत**
----------------------------
🇮🇳 **National Helpline:** 8448440632
🌐 **Website:** https://manodarpan.education.gov.in/
📧 **Email:** manodarpan-mhrd@gov.in

----------------------------
🇮🇳 **Other Helplines:**
📱 **iCall:** 9152987821 (Mon-Sat 10am-8pm)
📱 **Vandrevala Foundation:** 1860-2662-345 (24/7)
📱 **Jeevan Aastha:** 1800-233-3330
----------------------------

❤️ **You are not alone. Please reach out for help.**
❤️ **तुम्ही एकटे नाही. कृपया मदतीसाठी संपर्क करा.**
"""


def generate_crisis_escalation(user_message: str, language: str = 'en') -> str:
    """
    Generate a calm, supportive response for crisis situations.
    ALWAYS shows helpline numbers directly.
    """
    if language == 'mr':
        lang_instruction = "Respond in Marathi (Devanagari script) in a warm, simple tone."
        fallback_closing = "\n\n❤️ मला तुमची काळजी आहे."
    elif language == 'hi':
        lang_instruction = "Respond in Hindi (Devanagari script) in a warm, simple tone."
        fallback_closing = "\n\n❤️ मुझे आपकी चिंता है।"
    elif language == 'hinglish':
        lang_instruction = "Respond in Romanized Hinglish (Latin characters) using warm, casual language."
        fallback_closing = "\n\n❤️ Main aapki care karta hoon."
    else:
        lang_instruction = "Respond in English."
        fallback_closing = "\n\n❤️ I care about you."

    prompt = f"""
The user has shared something that indicates they may be in crisis or having harmful thoughts.

RESPOND LIKE A CALM, CARING FRIEND:

1. Acknowledge their message seriously - show you understand the weight of what they're sharing
2. Express genuine care and concern for their wellbeing
3. Let them know they are not alone and you are here with them
4. Gently encourage them to reach out to professional support
5. Be calm, grounded, and supportive - not panicked
6. {lang_instruction}

CRITICAL RULES:
- NEVER say "everything will be okay" - it dismisses their pain
- NEVER minimize what they're feeling
- Sound genuine and human, not robotic

User message:
{user_message}
"""

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        
        final_response = response.content.strip()
        
        # Add appropriate warm closing if not already present
        if not final_response.endswith(("❤️","💛", "।")):
            final_response += fallback_closing
        
        # ALWAYS add helpline numbers
        final_response += CRISIS_HELPLINE_MESSAGE
        
        return final_response
        
    except Exception:
        # Localized fallback - always show helpline
        if language == 'mr':
            msg = "मी तुमचं ऐकत आहे. तुम्ही जे सांगत आहात ते गंभीर आहे, आणि तुम्ही व्यक्त झालात याचा मला आनंद आहे.\n\nकृपया लक्षात ठेवा की तुम्ही एकटे नाही. ❤️"
        elif language == 'hi':
            msg = "मैं आपकी बात सुन रहा हूँ। आप जो साझा कर रहे हैं वह गंभीर है, और मुझे खुशी है कि आपने बात की।\n\nकृपया जानिए कि आप अकेले नहीं हैं। ❤️"
        elif language == 'hinglish':
            msg = "Main aapki baat sun raha hoon. Jo aap share kar rahe hain wo serious hai, aur achha laga ki aapne baat share ki.\n\nSach mein aap akele nahi hain. ❤️"
        else:
            msg = "I hear you. What you're sharing is serious, and I'm really glad you reached out.\n\nPlease know that you are not alone. ❤️"
        
        return f"{msg}\n\n{CRISIS_HELPLINE_MESSAGE}"


def get_support_message() -> str:
    """Get the support message with contact details."""
    return CRISIS_HELPLINE_MESSAGE