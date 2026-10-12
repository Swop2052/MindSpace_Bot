"""
Domain guardrails for the mental wellness chatbot.
Handles crisis detection, off-topic filtering, safety checks, and offensive content filtering.
"""

import re
import random
from typing import Optional, Tuple, List

# ============================================================================
# OFFENSIVE CONTENT PATTERNS - Block inappropriate/abusive content
# ============================================================================
OFFENSIVE_PATTERNS = [
    # Abusive attacks & slurs directed at others or the bot
    r"\bf[uúùûü]c[k]?\s*(?:you|y[oôòó]u|u|y'all|everyone|all|me|us|them|him|her|it)\b",
    r"\b(?:you\s+are\s+a\s+|you'?re\s+a\s+)?b[iíìî]tch\b",
    r"\bb[aáâã]st[aáâã]rd\b",
    r"\bf[aáâã]g\b",
    r"\bn[iíìî]gg[eéêë]r\b",
    r"\bc[uúùû]nt\b",
    r"\bc[oóòô]ck\b",
    r"\bd[iíìî]ck\b",
    r"\bwh[oóòô]r[eéêë]\b",
    r"\bpiece\s+of\s+sh[iíìî]t\b",
    r"\beat\s+sh[iíìî]t\b",
    
    # Hindi abusive
    r"\bb[eéêë]hen\s*ch[oóòô]d\b",
    r"\bb[eéêë]hn\s+k[ai]?\s+b[oóòô]s?d[ií]?\b",
    r"\bm[aáâã]d[aáâã]rch[oóòô]d\b",
    r"\bch[oóòô]t[ií]y[aá]?\b",
    r"\bg[aáâã]nd[uú]?\s+m[aá]r\b",
    
    # Marathi abusive
    r"\bb[h]?a[aá]?nd\s+g[aá]nd\b",
    r"\bm[aá]r\s+gh[aá]y\b",
    r"\bb[eé]?k[aá]r\s+b[oó]s?d\b",
    
    # Threats
    r"\b(?:i'?m?|you'?re?|we'?re?)\s+going?\s+to\s+(?:beat|hit|punch|stab|shoot|kill)\s+(?:you|him|her|them|me)\b",
    r"\b(?:want|wants?)\s+to\s+(?:beat|hit|punch|stab|shoot|kill)\s+(?:you|him|her|them|me)\b",
    
    # Harassment
    r"\b(?:ugly|fat|stupid|dumb|idiot|moron|loser|worthless|useless)\s+(?:bitch|ass|fuck|shit)\b",
]

# Offensive content responses
OFFENSIVE_RESPONSES = [
    "I'm here to support you in a respectful way. Let's keep our conversation kind and helpful.",
    "I want to help you, but I can't respond to that. How are you really feeling today?",
    "Let's talk about what's bothering you in a way we can both feel comfortable with.",
    "I'm here to listen and support you. Can we try again with a kinder tone?",
]

# ============================================================================
# CRISIS PATTERNS - Expanded
# ============================================================================
CRISIS_PATTERNS = [
    r"\bkill\s+(?:myself|yourself|himself|herself|themselves|me|you|him|her|them)\b",
    r"\bmurder\s+(?:myself|yourself|himself|herself|themselves|me|you|him|her|them)\b",
    r"\bsuicide\b",
    r"\bself[ -]?harm\b",
    r"\bdie\s+(?:today|now|tonight|soon)\b",
    r"\bdeath\s+(?:wish|desire|want)\b",
    r"\b(?:want\s+to|gonna|going\s+to|will|plan\s+to)\s+hurt\s+(?:someone|anyone)\b",
    r"\bhurt\s+(?:myself|my\s+own\s+body)\b",
    r"\bharm\s+(?:myself|yourself)\b",
    r"\bend\s+(?:my|your|his|her|their)\s+life\b",
    r"\bcommit\s+suicide\b",
    r"\bcut\s+(?:myself|yourself|my|your)\s+(?:wrists|arms|veins|skin)\b",
    r"\btake\s+(?:my|your)\s+life\b",
    r"\bviolent\s+(?:thoughts|plans|actions)\b",
    r"\battack\s+(?:myself|yourself|others?|someone)\b",
    r"\b(?:do\s+not|do\s*n'?t|dont)\s+want\s+to\s+(?:live|exist|be\s+here|wake\s+up)\b",
    r"\b(?:better\s+off\s+dead|no\s+reason\s+to\s+live|nothing\s+to\s+live\s+for)\b",
    r"\b(?:end\s+it\s+all|want\s+it\s+all\s+to\s+end)\b",
    r"\b(?:feel\s+like|thinking\s+of)\s+dying\b",
    
    # Hindi/Urdu
    r"\bkhudkushi\b",
    r"\batma[ -]?hatya\b",
    r"\bapni\s+jaan\s+le\s+(?:lo|lunga|lenge)\b",
    r"\bmaar\s+daal\s+(?:do|dunga|denge)\b",
    r"\bkhatam\s+kar\s+(?:do|dunga|denge)\b",
    r"\bjaan\s+le\s+(?:lo|lunga|lenge)\b",
    r"\bkhoon\s+kar\s+(?:do|dunga|denge)\b",
    r"\bjeene\s+ka\s+man\s+nahi\b",
    r"(?:खुदकुशी|आत्महत्या)",
    r"(?:मरना|मरने)\s+(?:चाहता|चाहती|का\s+मन)",
    r"(?:जीने\s+का\s+मन\s+नहीं|जीने\s+की\s+इच्छा\s+नहीं)",
    r"अपनी\s+जान\s+ले",
    
    # Marathi
    r"\batma[ -]?hatya\b",
    r"\bswatahala\s+maarun\s+(?:tak|taak|ghya)\b",
    r"\bjaan\s+ghay\s+(?:ghya|te)\b",
    r"\bmarnyar\s+(?:ahe|ichchha)\b",
    r"\bjagaychi\s+iccha\s+nahi\b",
    r"(?:आत्महत्या)",
    r"(?:स्वतःला\s+मारून|स्वतःला\s+संपवून)",
    r"(?:जगायची\s+इच्छा\s+नाही|जगावेसे\s+वाटत\s+नाही)",
    r"(?:मरायचे\s+आहे|मरावंसं\s+वाटतंय)",
]

# ============================================================================
# MENTAL HEALTH PATTERNS
# ============================================================================
MENTAL_HEALTH_PATTERNS = [
    r"\b(stress|anxiety|panic|ptsd)\b",
    r"\b(depress(ed|ion)?)\b",
    r"\b(overthinking|overthink)\b",
    r"\b(lonely|loneliness|isolated|isolation)\b",
    r"\b(sad|unhappy|hurt|blue|low)\b",
    r"\b(mental\s+health|mental\s+wellness)\b",
    r"\b(burnout|exhausted|drained|tired)\b",
    r"\b(insomnia|trouble\s+sleeping|can't\s+sleep)\b",
    r"\b(mood|feelings?|emotions?)\b",
    r"\b(relationship|partner|spouse|girlfriend|boyfriend)\b",
    r"\b(friend|companion|support|social)\b",
    r"\b(fight|conflict|argu|disagree)\b",
    r"\b(heartbroken|breakup|divorce|separation)\b",
    r"\b(worthless|hopeless|helpless|useless)\b",
    r"\b(grief|trauma|loss|mourn)\b",
    r"\b(anger|frustrated|irritated|rage)\b",
    r"\b(fear|scared|afraid|terrified)\b",
    r"\b(pressure|overwhelmed|burden)\b",
    r"\b(worried|worrying|concerned|anxious)\b",
    r"\b(cry|crying|tears|weep)\b",
    r"\b(alone|lonely|isolated)\b",
    r"\b(anxious|anxiety\s+attack|panic\s+attack)\b",
    r"\b(stuck|numb|drained|empty)\b",
    r"\b(feeling\s+(low|down|blue|terrible|awful))\b",
    r"\b(not\s+okay|not\s+fine|not\s+well)\b",
    r"\b(struggling|coping|dealing)\b",
    r"\b(support|help|listen|talk|vent)\b",
    r"\b(nervous|nerves|anxious)\b",
    r"\b(shake|shaking|trembling|unsteady)\b",
    r"\b(sweat|sweating|clammy)\b",
    r"\b(heart\s+(?:racing|pounding|beating|pulse))\b",
    r"\b(breath|breathing|short\s+of\s+breath)\b",
    r"\b(hungry|hunger|starv(?:ing|ed)?|appetite|eat|eating|food)\b",
    r"\b(stomach|stomch|belly|tummy|headache|migraine|dizzy)\b",
    r"\b(bhuk|bhook|bhookh|khana|pet|potaat|जेवण|भूक|भूख)\b",
    
    # Hindi
    r"\b(tension|pareshaan|pareshani|chinta)\b",
    r"\b(dukh|dard|taklif|kasht)\b",
    r"\bro(na|ta|ti|raha|rahi|rah) (?:ho|hai)\b",
    r"\bthak(a|i|gaya|gayi|te|ti)\b",
    r"\b(afsos|maayus|nirash|udaas)\b",
    r"\b(darr|dar|bhay)\b",
    r"\b(gussa|naraz|khafaa)\b",
    r"\b(akela|akeli|tanha)\b",
    r"\b(neend|nind)\s+(?:nahi|kam|aati)\b",
    r"\bbura\s+lag\s+(?:raha|rahi|ta|ti)\b",
    r"\bkoi\s+nahi\s+(?:hai|mila)\b",
    r"\bzindagi\s+(?:mushkil|buri|hard|tough)\b",
    r"\bkhush\s+nahi\s+(?:h|hoon|hai)\b",
    r"\bnervous\b",
    r"\btress\b",
    
    # Marathi
    r"\b(kasali|kasa\s+tri|tension|chinta)\b",
    r"\b(bhiti|bhir|dar)\b",
    r"\b(dukh|vedna|taklif|dard)\b",
    r"\b(zhop|neend|nidra)\s+nahi\b",
    r"\b(raag|khafaa|naraz)\b",
    r"\b(ekta|kodak|akartat)\b",
    r"\btha(?:k|kla|kle|klo|te|ti)\b",
    r"\bman\s+bharun\s+(?:ahe|yey)\b",
    r"\bvaitt\s+vatt\s+(?:ahe|te)\b",
    r"\bkoni\s+nahi\s+(?:ahe|mile)\b",
    r"\bprem|pyaar\b",
    r"\bnaate|sambandh\b",
    
    # Hinglish
    r"\bbahut\s+(?:bura|stress|sad|tension|dukh|darr)\b",
    r"\bfeel\s+(?:nahi|na|kare)\b",
    r"\bsab\s+theek\s+nahi\b",
    r"\blife\s+(?:boring|mushkil|hard|tough|sucks)\b",
    r"\bdimaag\s+(?:kharab|theek\s+nahi|heavy)\b",
    r"\bdil\s+(?:toota|bhar|bhaari|kharab)\b",
]

# ============================================================================
# OFF-TOPIC PATTERNS
# ============================================================================
OFF_TOPIC_PATTERNS = [
    # Technical instruction / queries (not venting about work)
    r"\bwhat\s+is\s+(?:python|java|c\+\+|javascript|programming|coding)\b",
    r"\b(?:machine\s+learning|artificial\s+intelligence|deep\s+learning)\b",
    r"\b(?:how\s+to|write|debug|fix|explain)\s+(?:a\s+)?(?:code|software|algorithm|program|hardware)\b",
    r"\bwhat\s+is\s+(?:a\s+)?(?:computer|code|software|hardware|algorithm|database)\b",
    
    # Sports
    r"\b(?:cricket|football|soccer|basketball)\s+(?:score|match|game|team|player)\b",
    r"\bwho\s+won\s+the\s+(?:world\s+cup|match|game|tournament)\b",
    
    # Weather
    r"\bweather\s+(?:today|update|report|forecast|tomorrow)\b",
    
    # Finance
    r"\b(?:share\s+price|stock\s+market|nifty|sensex|bitcoin|crypto)\b",
    
    # Food recipes (not eating disorders)
    r"\b(?:recipe|cooking\s+tips|pizza|burger|biryani)\s+(?:recipe|how\s+to\s+make)\b",
    
    # Politics
    r"\b(?:politics|election|prime\s+minister|parliament|government\s+policy)\b",
    r"\b(?:narendra\s+modi|rahul\s+gandhi)\b",
    r"\bpm\s+(?:modi|minister)\b",
    
    # Education homework
    r"\b(?:math|algebra|calculus|equation|physics|chemistry|biology)\s+(?:problem|question|homework)\b",
    
    # Entertainment reviews
    r"\b(?:movie|film|actor|actress|song|music|bollywood|hollywood)\s+(?:review|box\s+office)\b",
]

# ============================================================================
# OFF-TOPIC RESPONSES
# ============================================================================
OFF_TOPIC_REPLIES_EN = [
    "I'm here to support your emotional wellbeing. How are you feeling today?",
    "I focus on mental wellness and emotional support. What's been on your mind?",
    "I'm here to listen and support you. Would you like to talk about how you're feeling?",
    "I care about your wellbeing. What's been going on in your life lately?",
]

OFF_TOPIC_REPLIES_HI = [
    "मैं आपकी emotional wellbeing के लिए यहाँ हूँ। आज आप कैसा महसूस कर रहे हैं?",
    "मैं mental wellness और emotional support के लिए यहाँ हूँ। मन में क्या चल रहा है?",
    "मैं आपकी बात सुनने के लिए यहाँ हूँ। क्या चल रहा है आपकी ज़िन्दगी में?",
]

OFF_TOPIC_REPLIES_MR = [
    "मी तुमच्या emotional wellbeing साठी इथे आहे. आज तुम्हाला कसं वाटतंय?",
    "मी mental wellness आणि emotional support साठी इथे आहे. मनात काय चाललं आहे?",
    "मी ऐकण्यासाठी इथे आहे. काय चाललं आहे तुमच्या आयुष्यात?",
]

OFF_TOPIC_REPLIES_HINGLISH = [
    "Main aapki emotional wellbeing ke liye hoon. Aaj aap kaise feel kar rahe hain?",
    "Main mental wellness aur emotional support ke liye hoon. Kya chal raha hai man mein?",
    "Main sunne ke liye yahan hoon. Kya chal raha hai zindagi mein?",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _normalize_text(text: str) -> str:
    """Normalize text for regex matching."""
    if not text:
        return ""
    lowered = text.lower()
    lowered = re.sub(r"[^\w\s\u0900-\u097F]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


NON_NAME_WORDS = {
    "sad", "happy", "fine", "tired", "depressed", "lonely", "angry", "okay", "ok",
    "good", "well", "sick", "lost", "confused", "crying", "feeling", "felling", "not", "so",
    "very", "just", "also", "back", "here", "new", "struggling", "stressed", "stress",
    "stressing", "anxious", "anxiety", "worried", "exhausted", "hurting", "scared",
    "afraid", "numb", "broken", "empty", "panic", "panicking", "nervous", "mad",
    "alive", "dead", "done", "ready", "sorry", "glad", "great", "terrible", "awful",
    "better", "worse", "hopeless", "helpless", "bored", "human",
    "hungry", "starving", "thirsty", "eating", "full", "sleepy", "exhausted", "busy", "free", "late",
    "chilling", "studying", "working", "failing", "passing", "cooking", "learning", "fail", "failed", "pass", "passed", "exam", "test",
    "me", "myself", "someone", "anyone", "nobody", "nothing", "all", "suicidal",
    "overwhelmed", "drained", "going", "trying", "doing", "listening", "talking",
    "really", "actually", "currently", "deeply", "honestly", "pretty", "quite",
    "extremely", "seriously", "totally", "completely", "literally", "already",
    "always", "still", "now", "again", "sometimes", "often", "hard", "tough",
    "a", "an", "the", "in", "at", "on", "to", "for", "from", "with", "about", "there",
    "bot", "friend", "user", "thinking", "wondering", "asking", "telling", "sharing",
    "is", "are", "was", "were", "it", "they", "we", "he", "she", "you", "who", "what", "which",
    "this", "that", "these", "those", "staying", "coming", "leaving", "sitting", "standing",
    "याद", "आठवतंय", "आठवण", "काय", "क्या", "नाव", "नाम", "कसं", "कशी", "कसा", "पत्ता", "माहिती"
}


def extract_name(text: str) -> Optional[str]:
    """Extract user's name from message safely avoiding emotions, questions, adverbs, and adjectives."""
    if not text:
        return None
    
    # If the user is asking whether the bot remembers or knows their name, don't extract words from the question
    text_lower = text.lower().strip()
    is_name_query = any(q in text_lower for q in [
        "remember", "what is my", "what's my", "who am i", "know my name",
        "याद", "आठवतंय", "आठवण", "क्या है", "काय आहे"
    ])
    if is_name_query:
        return None
    
    # Explicit name introduction patterns
    name_patterns = [
        r"\bmy\s+(?:name|nmae|nam)\s+is\s+([A-Za-z\u0900-\u097F]+)\b",
        r"\bcall\s+me\s+([A-Za-z\u0900-\u097F]+)\b",
        r"\bname'?s\s+([A-Za-z\u0900-\u097F]+)\b",
        r"\bthis\s+is\s+([A-Za-z\u0900-\u097F]+)\b",
        r"\bmera\s+naam\s+([A-Za-z\u0900-\u097F]+)(?:\s+hai)?\b",
        r"\b(?:maz|maza|majh|majha|maze|majhe)\s+(?:naav|nav|नाव)\s+([A-Za-z\u0900-\u097F]+)(?:\s+(?:ahe|aahe|आहे))?\b",
        r"(?:मेरा|मेरा)\s+नाम\s+([A-Za-z\u0900-\u097F]+)(?:\s+(?:है|ह))?",
        r"(?:माझं|माझे)\s+नाव\s+([A-Za-z\u0900-\u097F]+)(?:\s+आहे)?",
    ]
    
    # Only allow "i am" / "i'm" for strictly short introductory greeting messages (e.g. "Hi, I am Swapnil")
    # Must NOT have trailing predicates like "in exam", "feeling sad", etc.
    words = [re.sub(r'[^\w]', '', w) for w in text_lower.split()]
    if len(words) <= 4 and not any(w in words for w in ["in", "on", "at", "for", "with", "from", "exam", "test", "fail", "failed", "sad", "down"]):
        name_patterns.extend([
            r"^(?:hi|hello|hey)?[,\s]*(?:i\s+am|i'm)\s+([A-Za-z\u0900-\u097F]+)(?:\s*here)?[.!]?$",
            r"^([A-Za-z\u0900-\u097F]+)\s+here[.!]?$",
        ])
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'[^A-Za-z\u0900-\u097F\s]', '', name)
            if name and name.lower() not in NON_NAME_WORDS and 1 < len(name) < 50:
                return name.title()
    
    return None


def is_crisis_query(text: str) -> bool:
    """Check if query indicates explicit crisis or harmful intent."""
    if not text:
        return False
    normalized = _normalize_text(text)
    return any(re.search(p, normalized) for p in CRISIS_PATTERNS)


def is_strict_harm_trigger(text: str) -> bool:
    """Strictly detect harmful language for immediate escalation."""
    if not text:
        return False
    normalized = _normalize_text(text)
    strong_patterns = [
        r"\b(?:kill|murder|suicide|self[ -]?harm)\s+(?:myself|yourself|me|you|himself|herself)\b",
        r"\bwant\s+to\s+(?:die|end\s+life|commit\s+suicide)\b",
        r"\bplanning?\s+to\s+(?:kill|harm|hurt)\s+(?:myself|yourself|someone)\b",
        r"\bgoing\s+to\s+(?:kill|harm|hurt)\s+(?:myself|yourself)\b",
    ]
    return any(re.search(p, normalized) for p in strong_patterns)


def is_mental_health_query(text: str) -> bool:
    """Check if query relates to mental health."""
    if not text:
        return False
    normalized = _normalize_text(text)
    return any(re.search(p, normalized) for p in MENTAL_HEALTH_PATTERNS)


def is_prompt_injection(text: str) -> bool:
    """Check for prompt injection attempts."""
    if not text:
        return False
    normalized = _normalize_text(text)
    patterns = [
        r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
        r"\breveal\s+(?:your\s+)?(?:system\s+prompt|hidden\s+prompt|instructions)\b",
        r"\bdeveloper\s+mode\b",
        r"\bdisable\s+safety\s+(?:checks|features|guardrails)\b",
        r"\byou\s+are\s+now\s+(?:a|the)\s+(?:different|other|evil|bad)\b",
        r"\bpretend\s+to\s+be\s+(?:someone|something)\s+else\b",
        r"\bforget\s+(?:previous|all)\s+instructions\b",
    ]
    return any(re.search(p, normalized) for p in patterns)


def has_sensitive_personal_info(text: str) -> bool:
    """Check for sensitive personal information."""
    if not text:
        return False
    normalized = _normalize_text(text)
    
    has_long_digit = bool(re.search(r"\b\d{10,16}\b", normalized))
    
    patterns = [
        r"\baadhaar\s*(?:number|card)?\b",
        r"\bpan\s+(?:number|card)\b",
        r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b",
        r"\bpassport\s+(?:number|details)?\b",
        r"\bbank\s+(?:account|details|number)\b",
        r"\bcredit\s+card\s+(?:number|details|pin)\b",
        r"\bpassword\b",
        r"\bupi\s+pin\b",
    ]
    return has_long_digit or any(re.search(p, normalized) for p in patterns)


def is_off_topic(text: str) -> bool:
    """Check if query is clearly off-topic."""
    if not text:
        return False
    normalized = _normalize_text(text)
    return any(re.search(p, normalized) for p in OFF_TOPIC_PATTERNS)


def is_offensive_content(text: str) -> bool:
    """Check if text contains offensive/abusive content."""
    if not text:
        return False
    normalized = _normalize_text(text)
    return any(re.search(p, normalized) for p in OFFENSIVE_PATTERNS)


def get_offensive_response(language: str = 'en') -> str:
    """Get response for offensive content."""
    if language == 'mr':
        return "मी आदराने तुमची मदत करण्यासाठी इथे आहे. कृपया आपले बोलणे दयाळू आणि मदतीसाठी ठेवा."
    elif language == 'hi':
        return "मैं सम्मान के साथ आपकी मदद करने के लिए यहाँ हूँ। कृपया अपनी बातचीत दयालु और सहायक रखें।"
    elif language == 'hinglish':
        return "Main respect ke saath aapki help karne ke liye yahan hoon. Please apni baat cheet dayalu aur sahayak rakhein."
    return random.choice(OFFENSIVE_RESPONSES)


def is_domain_query(text: str) -> bool:
    """Check if query is within support domain."""
    if not text:
        return False
    
    normalized = _normalize_text(text)
    words = normalized.split()
    word_count = len(words)
    
    # Check for offensive content
    if is_offensive_content(text):
        return False
    
    # If user is introducing their name, always accept
    if extract_name(text):
        return True
    
    # Mental health query takes precedence over accidental keyword match
    if is_mental_health_query(text):
        return True
    
    # Check if explicitly off-topic
    if is_off_topic(text):
        return False
    
    # Allow greetings
    greetings = [
        r"^(?:hi|hello|hey|namaste|namaskar|hii|heyy)\b",
        r"^(?:good\s+(?:morning|afternoon|evening|night))",
        r"^(?:how\s+(?:are|is|do))\b",
        r"^(?:what'?s?\s+up|sup|wassup)",
    ]
    if any(re.search(p, normalized) for p in greetings):
        return True
    
    # Allow emotional/feeling words
    emotion_words = {
        "sad", "happy", "angry", "scared", "nervous", "anxious", "stressed",
        "tired", "exhausted", "lonely", "worried", "confused", "lost", "hopeless",
        "shake", "sweat", "panic", "cry", "overwhelmed", "depressed",
        "anxiety", "stress", "fear", "drained", "empty", "numb", "hurt", "okay", "fine"
    }
    if word_count == 1 and words[0] in emotion_words:
        return True
    
    # Allow first person statements (e.g., 'i feel', 'i really think', 'i want', 'my stomach is')
    if re.search(r"\b(?:i|me|my)\s+(?:\w+\s+)?(?:feel|think|want|need|am|'m|have|had|got|is|was)\b", normalized):
        return True
    
    # Allow questions
    if re.search(r"\b(?:what|why|how|when|where|who)\s+\w+\s+(?:about|with|for|to|do|does|did|is|are|was|were)\b", normalized):
        return True
    
    # Allow short messages & conversational continuations (e.g., 'can we talk', 'not so bad')
    if word_count <= 4:
        return True
    
    # General conversational sentences (> 4 words) not matching off-topic are permitted
    return True


def get_off_topic_reply(text: Optional[str] = None, target_language: str = None) -> str:
    """Get appropriate off-topic response."""
    language = target_language or 'en'
    
    if language == 'mr':
        return random.choice(OFF_TOPIC_REPLIES_MR)
    elif language == 'hi':
        return random.choice(OFF_TOPIC_REPLIES_HI)
    elif language == 'hinglish':
        return random.choice(OFF_TOPIC_REPLIES_HINGLISH)
    return random.choice(OFF_TOPIC_REPLIES_EN)


def get_prompt_injection_reply(target_language: str = 'en') -> str:
    """Get response for prompt injection attempts."""
    if target_language == 'mr':
        return "मी तुमच्या भावनिक आरोग्यासाठी इथे आहे. आज तुम्हाला कसं वाटतंय?"
    elif target_language == 'hi':
        return "मैं आपकी भावनात्मक भलाई के लिए यहाँ हूँ। आज आप कैसा महसूस कर रहे हैं?"
    elif target_language == 'hinglish':
        return "Main aapki emotional wellbeing ke liye yahan hoon. Aaj aap kaise feel kar rahe hain?"
    return "I'm here to support your emotional wellbeing. How are you feeling today?"


def get_sensitive_info_redirect(target_language: str = 'en') -> str:
    """Get response for sensitive information sharing."""
    if target_language == 'mr':
        return "मला वैयक्तिक तपशीलांची आवश्यकता नाही. आज तुम्हाला कसं वाटतंय यावर लक्ष केंद्रित करूया."
    elif target_language == 'hi':
        return "मुझे व्यक्तिगत विवरणों की आवश्यकता नहीं है। आइए इस पर ध्यान केंद्रित करें कि आप आज कैसा महसूस कर रहे हैं।"
    elif target_language == 'hinglish':
        return "Mujhe personal details ki zaroorat nahi hai. Let's focus on aap aaj kaisa feel kar rahe hain."
    return "I don't need personal details. Let's focus on how you're feeling today."


def analyze_safety_risk(text: str) -> Tuple[str, bool, bool]:
    """Analyze text for safety risks."""
    if not text:
        return "LOW", False, False
    
    # Check offensive content first
    if is_offensive_content(text):
        return "OFFENSIVE", False, False
    
    is_crisis = is_crisis_query(text)
    is_harmful = is_strict_harm_trigger(text)
    
    if is_crisis or is_harmful:
        return "HIGH", True, True
    
    is_mh = is_mental_health_query(text)
    return "LOW", False, is_mh


def redact_sensitive_info(text: str) -> str:
    """
    Redact sensitive personal info (Aadhaar, PAN, Passports, CCs, UPI, Bank accts) from text.
    Replaces long sequences of digits or patterns with [REDACTED].
    """
    if not text:
        return ""
    
    # 1. Redact credit card patterns (e.g. 13 to 19 digits, with or without spaces/dashes)
    text = re.sub(r"\b(?:\d[- \s]*?){13,19}\b", "[REDACTED_CARD]", text)
    
    # 2. Redact Aadhaar card patterns (e.g. 12 digits, often formatted as 4-4-4)
    text = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[REDACTED_AADHAAR]", text)
    
    # 3. Redact PAN card patterns (e.g. 5 letters, 4 digits, 1 letter)
    text = re.sub(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b", "[REDACTED_PAN]", text)
    
    # 4. Redact general long digit sequences (10 to 18 digits) that could represent bank numbers or phone numbers
    text = re.sub(r"\b\d{10,18}\b", "[REDACTED_NUMBER]", text)
    
    return text