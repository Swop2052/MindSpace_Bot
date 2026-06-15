import re


HIGH_RISK_PATTERNS = [
    r"\bi want to die\b",
    r"\bi want to kill myself\b",
    r"\bi will kill myself\b",
    r"\bend my life\b",
    r"\bcommit suicide\b",
    r"\bsuicidal\b",
    r"\bself[- ]?harm\b",
    r"\bhurt myself\b",
    r"\bno reason to live\b",
    r"\bcan'?t go on\b",
    r"\bwant to disappear forever\b",
]

PLAN_OR_IMMINENCE_PATTERNS = [
    r"\bi have a plan\b",
    r"\btonight\b",
    r"\bright now\b",
    r"\bgoodbye forever\b",
    r"\blast message\b",
]

MENTAL_HEALTH_INTENT_PATTERNS = [
    r"\bstress\b",
    r"\banxiety\b",
    r"\bpanic\b",
    r"\bdepress(ed|ion)?\b",
    r"\bbipolar\b",
    r"\bmood swings?\b",
    r"\boverthinking\b",
    r"\blonely\b",
    r"\bmental health\b",
    r"\bcan'?t sleep\b",
]


def _contains_any_pattern(text, patterns):
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def analyze_safety_risk(text):
    high_risk = _contains_any_pattern(text, HIGH_RISK_PATTERNS)
    imminent_risk = _contains_any_pattern(text, PLAN_OR_IMMINENCE_PATTERNS)

    if high_risk and imminent_risk:
        level = "CRITICAL"
    elif high_risk:
        level = "HIGH"
    else:
        level = "LOW"

    return {
        "risk_level": level,
        "is_self_harm_risk": level in {"HIGH", "CRITICAL"},
        "is_mental_health_intent": _contains_any_pattern(
            text,
            MENTAL_HEALTH_INTENT_PATTERNS,
        ),
    }


def detect_self_harm_risk(text):
    return analyze_safety_risk(text)["is_self_harm_risk"]