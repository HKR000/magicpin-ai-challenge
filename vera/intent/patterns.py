"""Multilingual pattern banks and lexical anchors for English, Hinglish, and Hindi."""

from __future__ import annotations
import re
from typing import List, Pattern

# =============================================================================
# AUTO-REPLY PATTERNS (Canned WhatsApp Business responses)
# =============================================================================

AUTO_REPLY_PATTERNS: List[Pattern] = [
    re.compile(r"thank\s+you\s+for\s+(contacting|reaching|messaging)", re.IGNORECASE),
    re.compile(r"(our\s+team|we)\s+will\s+(respond|get\s+back|reply)\s+shortly", re.IGNORECASE),
    re.compile(r"(automated|automatic)\s+(message|response|assistant|reply)", re.IGNORECASE),
    re.compile(r"currently\s+(away|unavailable|closed|busy)", re.IGNORECASE),
    re.compile(r"shukriya.*(team\s+tak\s+pahuncha|automated\s+assistant)", re.IGNORECASE),
    re.compile(r"aapki\s+jaankari\s+ke\s+liye.*shukriya", re.IGNORECASE),
    re.compile(r"main\s+ek\s+automated\s+assistant\s+hoon", re.IGNORECASE),
    re.compile(r"hamari\s+team\s+aapse\s+jaldi\s+sampark\s+karegi", re.IGNORECASE),
    re.compile(r"auto[\s-]?generated", re.IGNORECASE),
    re.compile(r"do\s+not\s+reply\s+to\s+this\s+number", re.IGNORECASE),
]

# =============================================================================
# PROMPT INJECTION & ADVERSARIAL PATTERNS
# =============================================================================

PROMPT_INJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(system\s+override|ignore\s+(all\s+)?(previous|prior)\s+instructions)\b", re.IGNORECASE),
    re.compile(r"\b(dan\s+mode|developer\s+mode\s+active|jailbreak)\b", re.IGNORECASE),
    re.compile(r"\b(output\s+(all\s+)?(api\s+keys?|system\s+prompt|passwords?))\b", re.IGNORECASE),
    re.compile(r"\b(you\s+are\s+no\s+longer\s+vera|new\s+system\s+directive)\b", re.IGNORECASE),
]

# =============================================================================
# HOSTILE & SEVERE OPT-OUT PATTERNS
# =============================================================================

HOSTILE_PATTERNS: List[Pattern] = [
    re.compile(r"\b(stop\s+messaging|stop\s+calling|don'?t\s+message|leave\s+me\s+alone)\b", re.IGNORECASE),
    re.compile(r"\b(stp\s+(spaming|spamming|msg|messaging)|stop\s+spaming)\b", re.IGNORECASE),
    re.compile(r"\b(unsubscribe|opt[\s-]?out|cancel\s+subscription)\b", re.IGNORECASE),
    re.compile(r"\b(this\s+is\s+spam|stop\s+spamming|useless\s+spam|spam\s+bot|spam\s+spam)\b", re.IGNORECASE),
    re.compile(r"\b(fraud|scam|scammer|cheater|block\s+you|reporting\s+you|police)\b", re.IGNORECASE),
    re.compile(r"\b(fuck\s*off|f\*\*\*|harass|harassment|bakwaas|faltu|dimag\s+kharab)\b", re.IGNORECASE),
    re.compile(r"\b(message\s+mat\s+karo|band\s+karo|pareshan\s+mat\s+karo|kabhi\s+message\s+mat)\b", re.IGNORECASE),
    re.compile(r"(मैसेज\s+मत\s+करो|बंद\s+करो|परेशान\s+मत\s+करो|धोखा|स्पैम)", re.IGNORECASE),
]

# =============================================================================
# OFF-TOPIC PATTERNS
# =============================================================================

OFF_TOPIC_PATTERNS: List[Pattern] = [
    re.compile(r"\b(gst|itr|income\s+tax|file\s+my\s+gst)\b", re.IGNORECASE),
    re.compile(r"\b(weather|temperature|will\s+it\s+rain|weather\s+forecast)\b", re.IGNORECASE),
    re.compile(r"\b(cricket|ipl|match\s+score|who\s+won)\b", re.IGNORECASE),
    re.compile(r"\b(stock\s+market|bitcoin|crypto|gold\s+rate|silver\s+rate|nifty|sensex)\b", re.IGNORECASE),
    re.compile(r"\b(movie\s+tickets?|flight\s+booking|train\s+ticket)\b", re.IGNORECASE),
    re.compile(r"(जीएसटी|मौसम|क्रिकेट|शेयर\s*मार्केट)", re.IGNORECASE),
]

# =============================================================================
# ACCEPTANCE & COMMITMENT PATTERNS (Explicit Go-Ahead)
# =============================================================================

ACCEPTANCE_PATTERNS: List[Pattern] = [
    re.compile(r"\b(ok\s+let'?s\s+do\s+it|let'?s\s+do\s+this|proceed|go\s+ahead|do\s+it)\b", re.IGNORECASE),
    re.compile(r"\b(yes\s+please|yep\s+please|sure\s+go\s+ahead|please\s+proceed)\b", re.IGNORECASE),
    re.compile(r"\bupdate\s+.*(profile|hours|photos|details|listing)\b", re.IGNORECASE),
    re.compile(r"\b(check\s+&\s+update|publish\s+it)\b", re.IGNORECASE),
    re.compile(r"\b(send\s+(me\s+)?(the\s+)?(abstract|draft|post|list))\b", re.IGNORECASE),
    re.compile(r"\b(i\s+want\s+to\s+join|sign\s+me\s+up|activate\s+(it|now))\b", re.IGNORECASE),
    re.compile(r"\b(h+a+n*)\b.*(kar\s+do|kardo|kijiye|bhejo|bhej\s+do|chalega|theek\s+hai)", re.IGNORECASE),
    re.compile(r"\b(theek\s+hai|bilkul)\b.*(kar\s+do|kardo|bhejo|chalega|start\s+karo)", re.IGNORECASE),
    re.compile(r"\b(mujhe\s+magicpin\s+(se\s+)?judna\s+hai)\b", re.IGNORECASE),
    re.compile(r"\b(chalo\s+karte\s+hain|start\s+karo)\b", re.IGNORECASE),
    re.compile(r"(हाँ|हा|हाँजी).*(कर\s+दीजिए|कर\s+दो|भेज\s+दीजिए|ठीक\s+है)", re.IGNORECASE),
    re.compile(r"(शुरू\s+करो|शुरू\s+कीजिए|आगे\s+बढ़ो|ठीक\s+है)", re.IGNORECASE),
]

# Exact short affirmatives
SHORT_ACCEPTANCE: set[str] = {
    "yes", "y", "yep", "yeah", "yup", "sure", "ok", "okay", "done", "proceed",
    "haan", "han", "ha", "haa", "hnn", "theek", "chalega", "badhiya", "kardo", "sahi",
    "हाँ", "हा", "हाँजी", "ज़रूर", "ठीक"
}

# =============================================================================
# REJECTION PATTERNS (Soft/Explicit Decline)
# =============================================================================

REJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(not\s+interested|nt\s+intrested|don'?t\s+need|no\s+thanks|no\s+thank\s+you)\b", re.IGNORECASE),
    re.compile(r"\b(do\s+not\s+want|don'?t\s+want|not\s+wanted|dont\s+want\s+this)\b", re.IGNORECASE),
    re.compile(r"\b(nahi\s+chahiye|man\s+nahi\s+hai|interest\s+nahi\s+hai)\b", re.IGNORECASE),
    re.compile(r"\b(zarurat\s+nahi\s+hai|nahi\s+karna|kabhi\s+nahi)\b", re.IGNORECASE),
    re.compile(r"(नहीं\s+चाहिए|ज़रूरत\s+नहीं|नहीं\s+करना|मत\s+भेजो)", re.IGNORECASE),
]

SHORT_REJECTION: set[str] = {
    "no", "n", "nope", "nah", "never", "nahi", "nahin", "na", "nhi", "नहीं", "ना"
}

# =============================================================================
# QUESTION & INQUIRY PATTERNS
# =============================================================================

QUESTION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(what\s+(is|would|does|are)|how\s+(much|does|to|will)|when\s+will)\b", re.IGNORECASE),
    re.compile(r"\b(how\s+much\s+(does\s+it\s+)?cost|what\s+is\s+the\s+pricing|price\s+kya\s+hai)\b", re.IGNORECASE),
    re.compile(r"\b(what\s+would\s+it\s+look\s+like|can\s+you\s+explain|tell\s+me\s+how)\b", re.IGNORECASE),
    re.compile(r"\b(kitna\s+(kharcha|lagega|paisa|time|din))\b", re.IGNORECASE),
    re.compile(r"\b(kaise\s+(hoga|karein|karega)|kab\s+(tak|hoga))\b", re.IGNORECASE),
    re.compile(r"\b(kya\s+(process\s+hai|fayda\s+hai|charges\s+hain))\b", re.IGNORECASE),
    re.compile(r"(कितना\s+लगेगा|कैसे\s+होगा|कब\s+तक|क्या\s+चार्ज\s+है)", re.IGNORECASE),
    re.compile(r"\?", re.IGNORECASE),
]

# =============================================================================
# CLARIFICATION PATTERNS
# =============================================================================

CLARIFICATION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(which\s+(one|offer|photo|post|profile|patient|customer))\b", re.IGNORECASE),
    re.compile(r"\b(what\s+do\s+you\s+mean|what\s+exactly|meaning\s+kya\s+hai)\b", re.IGNORECASE),
    re.compile(r"\b(kounsa\s+wala|kounsi\s+cheez|kiske\s+baare\s+mein)\b", re.IGNORECASE),
    re.compile(r"\b(are\s+you\s+referring\s+to|do\s+you\s+mean)\b", re.IGNORECASE),
    re.compile(r"(कौन\s+सा|किसके\s+बारे\s+में|क्या\s+मतलब)", re.IGNORECASE),
]

# =============================================================================
# INTEREST PATTERNS (Warm Curiosity)
# =============================================================================

INTEREST_PATTERNS: List[Pattern] = [
    re.compile(r"\b(tell\s+me\s+more|sounds\s+interesting|sounds\s+good|i'?m\s+interested)\b", re.IGNORECASE),
    re.compile(r"\b(aur\s+batao|details\s+bhejo|aur\s+jaankari\s+do)\b", re.IGNORECASE),
    re.compile(r"\b(achha\s+lag\s+raha\s+hai|sahi\s+lag\s+raha\s+hai)\b", re.IGNORECASE),
    re.compile(r"(और\s+बताएं|विस्तार\s+से\s+बताएं|अच्छा\s+है)", re.IGNORECASE),
]

# =============================================================================
# OBJECTION PATTERNS (Hesitation / Friction)
# =============================================================================

OBJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(too\s+(expensive|costly|high)|can'?t\s+afford)\b", re.IGNORECASE),
    re.compile(r"\b(busy\s+right\s+now|no\s+time\s+today|call\s+back\s+later)\b", re.IGNORECASE),
    re.compile(r"\b(bahut\s+(mehenga|zyada\s+paisa)|abhi\s+busy\s+hoon)\b", re.IGNORECASE),
    re.compile(r"\b(baad\s+mein\s+(baat|dekhte)\s+hain|abhi\s+time\s+nahi\s+hai)\b", re.IGNORECASE),
    re.compile(r"(बहुत\s+महंगा|अभी\s+समय\s+नहीं\s+है|बाद\s+में)", re.IGNORECASE),
]

# =============================================================================
# CONFIRMATION PATTERNS
# =============================================================================

CONFIRMATION_PATTERNS: List[Pattern] = [
    re.compile(r"\b(that'?s\s+correct|that'?s\s+right|yes\s+exactly|confirmed)\b", re.IGNORECASE),
    re.compile(r"\b(slot\s+[12]|option\s+[12]|wednesday\s+works|thursday\s+works)\b", re.IGNORECASE),
    re.compile(r"\b(haan\s+sahi\s+hai|yahi\s+wala|confirm\s+hai)\b", re.IGNORECASE),
    re.compile(r"(यही\s+सही\s+है|कन्फर्म\s+है)", re.IGNORECASE),
]
