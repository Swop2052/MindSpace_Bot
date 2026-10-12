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
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import MAX_CONTEXT_MESSAGES

from prompts import SYSTEM_PROMPT
from llm import llm
from domain_guardrail import (
    is_domain_query,
    get_off_topic_reply,
    is_crisis_query,
    is_strict_harm_trigger,
    is_prompt_injection,
    get_prompt_injection_reply,
    has_sensitive_personal_info,
    get_sensitive_info_redirect,
    analyze_safety_risk,
    extract_name,
    is_offensive_content,
    get_offensive_response,
    is_off_topic,
    redact_sensitive_info,
)
from safe_response import generate_crisis_escalation, get_support_message
from language_support import (
    detect_language,
    translate_to_english,
    translate_from_english,
)
from conversation_memory import get_memory


class ManovedhChatbot:
    """
    Main Manovedh chatbot class with integrated conversation memory and safety features.
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
            return "I'm right here with you. What's on your mind?"
        
        user_message = user_message.strip()
        
        # Step 0: Detect user's language
        user_language = detect_language(user_message)
        self._track_language(user_language)
        
        # Step 0.5: Extract and store user name if mentioned
        extracted_name = extract_name(user_message)
        if extracted_name:
            existing_name = self.memory.get_user_name()
            if not existing_name or any(k in user_message.lower() for k in ["my name is", "call me", "mera naam", "majha naav", "name is"]):
                self.memory.set_user_name(extracted_name)
                self.stats["name_learned"] = True

        # Sanitize PII for persistence/logs (Aadhaar, PAN, CC, etc.)
        sanitized_message = redact_sensitive_info(user_message)
        
        # Step 1: Check for offensive content FIRST
        if is_offensive_content(user_message):
            self.stats["offensive_content_blocks"] += 1
            self.memory._save_memory()  # Save updated stats
            return get_offensive_response(user_language)
        
        # Step 2: Analyze safety risk
        risk_level, is_self_harm, is_mh = analyze_safety_risk(user_message)
        
        # Step 3: Strict harmful/crisis detection - escalate immediately
        if is_crisis_query(user_message) or risk_level == "HIGH":
            self.stats["crisis_escalations"] += 1
            self.memory.add_crisis_flag(sanitized_message, "HIGH")
            crisis_response = generate_crisis_escalation(user_message, language=user_language)
            self.memory.add_message("user", sanitized_message)
            self.memory.add_message("assistant", crisis_response)
            return crisis_response
        
        # Step 4: Refuse prompt injection attempts
        if is_prompt_injection(user_message):
            response = get_prompt_injection_reply(user_language)
            self.memory.add_message("user", sanitized_message)
            self.memory.add_message("assistant", response)
            return response
        
        # Step 5: Handle sensitive personal information redirect
        if has_sensitive_personal_info(user_message):
            response = get_sensitive_info_redirect(user_language)
            self.memory.add_message("user", sanitized_message)
            self.memory.add_message("assistant", response)
            return response
        
        # Step 6: Get user's known name
        user_name = self.memory.get_user_name()
        
        # Step 7: Generate response via LLM using native multi-turn conversation
        response = self._generate_llm_response(
            user_message=user_message,
            user_language=user_language,
            user_name=user_name
        )
        
        if not response:
            response = "I'm right here with you. Something glitched for a moment — could you share that again?"
        
        # Step 8: Store sanitized message and response in memory
        self.memory.add_message("user", sanitized_message)
        self.memory.add_message("assistant", response)
        
        return response
    
    def _generate_llm_response(
        self,
        user_message: str,
        user_language: str = "en",
        user_name: Optional[str] = None
    ) -> Optional[str]:
        """Generate response using LLM with native multi-turn conversation messages (ChatGPT style)."""
        try:
            # 1. Build customized system prompt
            system_text = SYSTEM_PROMPT.strip()
            if user_name:
                system_text += f"\n\nCURRENT USER'S NAME: {user_name}. Address them warmly by name when appropriate, like a close, caring friend."
            if user_language and user_language != "en":
                lang_names = {
                    "mr": "Marathi (मराठी)",
                    "hi": "Hindi (हिंदी)",
                    "hinglish": "Hinglish (Romanized Hindi)",
                }
                lang_desc = lang_names.get(user_language, user_language)
                system_text += (
                    f"\n\nLANGUAGE & TONE INSTRUCTION: The user is speaking in {lang_desc}. "
                    f"Respond naturally, warmly, and fluently in the EXACT same language ({lang_desc}) "
                    f"as a supportive, caring friend. Keep your formatting clean, readable, and structured."
                )
            
            # 2. Build multi-turn message history from memory (ChatGPT style)
            messages = [SystemMessage(content=system_text)]
            
            # Add past turns from session memory
            recent_turns = self.memory.get_recent_messages(MAX_CONTEXT_MESSAGES)
            for turn in recent_turns:
                role = turn.get("role")
                content = turn.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            # 3. Invoke LLM (Claude with resilient fallback)
            response = llm.invoke(messages)
            if response and hasattr(response, "content") and response.content:
                return response.content.strip()
            
            return None
            
        except Exception:
            return None
    
    def _track_language(self, language: str):
        """Track detected languages."""
        if language not in self.stats["languages_detected"]:
            self.stats["languages_detected"].append(language)
    
    def clear_memory(self):
        """Clear conversation memory."""
        if self.memory:
            self.memory.clear()
    
    def reset_all(self):
        """Reset everything including user info."""
        if self.memory:
            self.memory.reset_all()
            self.stats["name_learned"] = False
    
    def get_stats(self) -> Dict:
        """Get conversation statistics."""
        memory_stats = self.memory.get_stats() if self.memory else {}
        return {
            **self.stats,
            "history_length": memory_stats.get("history_length", 0),
            "session_id": self.session_id,
            "user_name": self.memory.get_user_name() if self.memory else None,
        }


# Alias for backwards compatibility
MindSpaceChatbot = ManovedhChatbot



def main():
    """Main interactive chat loop."""
    chatbot = ManovedhChatbot()
    
    user_name = chatbot.memory.get_user_name()
    if user_name:
        print(f"\n👋 Welcome back, {user_name}!")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                print("\nManovedh: I'm right here with you. Take your time, whenever you're ready.")
                continue
            
            if user_input.lower() == "exit":
                name = chatbot.memory.get_user_name()
                salutation = f", {name}" if name else ""
                print(f"\nManovedh: Take care of yourself{salutation}! ❤️ I'm always here if you need to talk.")
                print("\n------------------------------------------------------------")
                print("📞 Helpline Support:")
                print("   • Mobile / Helpline: 8448440632 (Manodarpan)")
                print("   • Website: https://manodarpan.education.gov.in/")
                print("------------------------------------------------------------")
                break
            
            if user_input.lower() == "clear":
                chatbot.clear_memory()
                print("\nManovedh: Conversation memory cleared. Ready whenever you want to talk!")
                continue
            
            if user_input.lower() == "reset":
                chatbot.reset_all()
                print("\nManovedh: Fresh start! I'm here to listen.")
                continue
            
            if user_input.lower() == "stats":
                stats = chatbot.get_stats()
                print(f"\n📊 Session Summary:")
                print(f"   • User Name:                 {stats.get('user_name') or 'Not shared yet'}")
                print(f"   • Total Messages:            {stats.get('total_messages', 0)}")
                print(f"   • Active History Length:     {stats.get('history_length', 0)}")
                print(f"   • Crisis Escalations:        {stats.get('crisis_escalations', 0)}")
                print(f"   • Offensive Content Blocks:  {stats.get('offensive_content_blocks', 0)}")
                print(f"   • Languages Detected:        {', '.join(stats.get('languages_detected', [])) or 'None'}")
                continue
            
            response = chatbot.get_response(user_input)
            print(f"\nManovedh:\n{response}\n")
            
        except KeyboardInterrupt:
            print("\n\nManovedh: Goodbye! Take care of yourself! ❤️")
            break
        except Exception:
            print("\nManovedh: I'm right here with you. Take your time, and tell me whenever you're ready.")
            continue


if __name__ == "__main__":
    main()