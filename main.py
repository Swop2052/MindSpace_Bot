<<<<<<< Updated upstream
from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)
=======
"""
Main chatbot application with conversation memory and multi-language support.
"""

import sys
from typing import Dict, Optional

# Ensure standard streams use UTF-8 encoding to prevent UnicodeEncodeErrors on some consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


from langchain_core.messages import SystemMessage, HumanMessage
>>>>>>> Stashed changes

from prompts import SYSTEM_PROMPT
from llm import llm
from safety import analyze_safety_risk
from safe_response import generate_safe_response


<<<<<<< Updated upstream
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
=======
class MindSpaceChatbot:
    """
    Main chatbot class with integrated conversation memory and safety features.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """Initialize the chatbot with a session ID."""
        self.session_id = session_id
        self.memory = get_memory(self.session_id)
        
        # Track conversation stats dynamically in memory
        self.stats = self.memory.stats
        
        # Check if user name already exists
        if self.memory.get_user_name():
            self.stats["name_learned"] = True
    
    def get_response(self, user_message: str) -> str:
        """
        Generate a response based on user input.
        Handles safety checks, language detection, and conversation memory.
        """
        # Validate input
        if not user_message or not user_message.strip():
            return "I'm here to listen. What's on your mind?"
        
        user_message = user_message.strip()
        
        # Step 0: Detect user's language
        user_language = detect_language(user_message)
        self._track_language(user_language)
        
        # Step 0.5: Extract and store user name if mentioned
        extracted_name = extract_name(user_message)
        if extracted_name and not self.memory.get_user_name():
            self.memory.set_user_name(extracted_name)
            self.stats["name_learned"] = True
        
        # Step 1: Translate to English for processing
        user_message_english = translate_to_english(user_message, user_language)
        
        # Step 2: Check for offensive content FIRST
        if is_offensive_content(user_message_english):
            self.stats["offensive_content_blocks"] += 1
            self.memory._save_memory()  # Save updated stats
            response_en = get_offensive_response(user_language)
            # Don't store offensive content in memory
            return translate_from_english(response_en, user_language)
        
        # Step 3: Analyze safety risk
        risk_level, is_self_harm, is_mh = analyze_safety_risk(user_message_english)
        
        # Step 4: Strict harmful/crisis detection - escalate immediately
        if is_crisis_query(user_message_english) or risk_level == "HIGH":
            self.stats["crisis_escalations"] += 1
            self.memory.add_crisis_flag(user_message, "HIGH")
            response_en = generate_crisis_escalation(user_message_english)
            self.memory.add_message("user", user_message)
            self.memory.add_message("assistant", response_en)
            return translate_from_english(response_en, user_language)
        
        # Step 5: Refuse prompt injection attempts
        if is_prompt_injection(user_message_english):
            response_en = get_prompt_injection_reply(user_message_english)
            self.memory.add_message("user", user_message)
            self.memory.add_message("assistant", response_en)
            return translate_from_english(response_en, user_language)
        
        # Step 6: Handle sensitive personal information
        if has_sensitive_personal_info(user_message_english):
            response_en = get_sensitive_info_redirect(user_message_english)
            self.memory.add_message("user", user_message)
            self.memory.add_message("assistant", response_en)
            return translate_from_english(response_en, user_language)
        
        # Step 7: Check if query is within domain
        has_history = len(self.memory.messages) > 0
        word_count = len(user_message_english.split())
        is_short_followup = has_history and word_count <= 3
        
        if is_short_followup:
            # Check if it's completely off-topic technical question
            from domain_guardrail import is_off_topic
            if is_off_topic(user_message_english):
                self.stats["off_topic_redirects"] += 1
                response_en = get_off_topic_reply(user_message_english, user_language)
                self.memory.add_message("user", user_message)
                self.memory.add_message("assistant", response_en)
                return translate_from_english(response_en, user_language)
            # Otherwise let it through to LLM
            pass
        elif not is_domain_query(user_message_english):
            self.stats["off_topic_redirects"] += 1
            response_en = get_off_topic_reply(user_message_english, user_language)
            self.memory.add_message("user", user_message)
            self.memory.add_message("assistant", response_en)
            return translate_from_english(response_en, user_language)
        
        # Step 8: Get complete conversation context
        context = self.memory.get_context_for_llm(max_messages=15)
        user_name = self.memory.get_user_name()
        
        # Step 9: Generate response via LLM
        response_en = self._generate_llm_response(
            user_message_english,
            context,
            user_language,
            user_name,
            is_short_followup
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream

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
=======
    """Main chat loop."""
   
    print("🌟 Hello 🤗")
    
    
    chatbot = MindSpaceChatbot()
    
    if chatbot.memory.get_user_name():
        print(f"\n👋 Welcome back, {chatbot.memory.get_user_name()}!")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                print("Bot: I'm listening. Take your time.")
                continue
            
            if user_input.lower() == "exit":
                name = chatbot.memory.get_user_name()
                if name:
                    print(f"\nBot: Take care, {name}! ❤️")
                else:
                    print("\nBot: Take care of yourself! ❤️")
                print("Bot: Remember, you can always reach out for support at:")
                print("📱 Mobile/Helpline: 8448440632")
                print("🌐 Website: https://manodarpan.education.gov.in/")
                break
            
            if user_input.lower() == "clear":
                chatbot.clear_memory()
                print("Bot: Conversation memory cleared. I'm ready to listen.")
                continue
            
            if user_input.lower() == "reset":
                chatbot.reset_all()
                print("Bot: Everything reset. I'm ready to start fresh.")
                continue
            
            if user_input.lower() == "stats":
                stats = chatbot.get_stats()
                print(f"Bot: 📊 Session Stats")
                print(f"  - User: {stats.get('user_name') or 'Not shared yet'}")
                print(f"  - Total messages: {stats['total_messages']}")
                print(f"  - History length: {stats['history_length']}")
                print(f"  - Crisis escalations: {stats['crisis_escalations']}")
                print(f"  - Off-topic redirects: {stats['off_topic_redirects']}")
                print(f"  - Offensive content blocks: {stats.get('offensive_content_blocks', 0)}")
                print(f"  - Languages detected: {', '.join(stats['languages_detected'])}")
                continue
            
            response = chatbot.get_response(user_input)
            print(f"\nBot: {response}")
            
        except KeyboardInterrupt:
            print("\n\nBot: Goodbye! Take care of yourself! ❤️")
>>>>>>> Stashed changes
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