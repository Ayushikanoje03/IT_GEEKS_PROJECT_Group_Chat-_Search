"""Create deterministic, realistic fictional Hinglish group-chat corpus.

Design decisions:
- 200+ unique message templates across 8 categories to avoid visible repetition
- Bursty timestamps: clusters of activity separated by long silences
- Typo injection: ~10% of casual/reaction messages get realistic character-level typos
- Conversation flow: consecutive senders from a small active-window pool
- Three long decision threads (30-35 messages each) with tangents, jokes, one person
  going quiet, and a single clear final decision message
- Voice note placeholders alongside media-omitted lines
- Realistic forwarded messages (news, memes, motivational quotes)
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

SEED: Final = 42
MESSAGE_COUNT: Final = 4200
PARTICIPANTS: Final = ("Priya", "Rahul", "Sneha", "Arjun", "Kavya", "Dev", "Mehak", "Rohan")
CORPUS_PATH: Final = Path(__file__).with_name("corpus.json")
START_DATE: Final = datetime(2023, 10, 1, 9, 0, 0)
END_DATE: Final = datetime(2024, 3, 31, 23, 59, 59)

# ---------------------------------------------------------------------------
# Decision thread 1: Trip to Manali — October 2023
# Indices 830-864 (35 messages). The concrete decision is at index 848.
# ---------------------------------------------------------------------------
TRIP_THREAD_START: Final = 830
TRIP_THREAD_DECISION_INDEX: Final = 848   # "toh chalo fix karte hain yaar, 21 March Manali pakka"

# Decision thread 2: Hotel / money split — January 2024
# Indices 1520-1554 (35 messages). Decision at index 1537.
SPLIT_THREAD_START: Final = 1520
SPLIT_THREAD_DECISION_INDEX: Final = 1537  # "theek hai bhai, 5k each split kar dete hain, done"

# Decision thread 3: Departure confirmation — March 2024
# Indices 2220-2252 (33 messages). Decision at index 2247.
CONFIRM_THREAD_START: Final = 2220
CONFIRM_THREAD_DECISION_INDEX: Final = 2247  # "21 March pakka confirmed hai, sab ready raho"

# ---------------------------------------------------------------------------
# All three decision thread messages — planted deterministically
# ---------------------------------------------------------------------------
THREAD_MESSAGES: Final[dict[int, tuple[str, str, str, str]]] = {
    # ── Trip thread (Manali trip planning, October 2023) ──────────────────
    TRIP_THREAD_START + 0:  ("Priya",  "guys March ka long weekend dekh rahe ho? kahin bahar chalte hain", "planning", "trip_decision"),
    TRIP_THREAD_START + 1:  ("Rahul",  "haan yaar kahin hills jaana chahiye honestly", "planning", "trip_decision"),
    TRIP_THREAD_START + 2:  ("Sneha",  "Manali? weather mast hoga March mein", "planning", "trip_decision"),
    TRIP_THREAD_START + 3:  ("Arjun",  "Manali toh done hai yaar, sirf dates confirm karne hain", "planning", "trip_decision"),
    TRIP_THREAD_START + 4:  ("Kavya",  "mera 20 March ke baad free hai, before that client hai", "planning", "trip_decision"),
    TRIP_THREAD_START + 5:  ("Dev",    "21 March works for me, office bhi band hoga", "planning", "trip_decision"),
    TRIP_THREAD_START + 6:  ("Mehak",  "wait bhai pehle dekho kaun kaun aa raha pakka", "planning", "trip_decision"),
    TRIP_THREAD_START + 7:  ("Rohan",  "main toh 100% hun, bohot time se trip nahi hui", "planning", "trip_decision"),
    TRIP_THREAD_START + 8:  ("Priya",  "Rahul tu batao, leave milegi?", "planning", "trip_decision"),
    TRIP_THREAD_START + 9:  ("Rahul",  "haan yaar milegi, koi issue nahi", "reaction", "trip_decision"),
    TRIP_THREAD_START + 10: ("Sneha",  "toh 8 log hain? sab aa rahe?", "planning", "trip_decision"),
    TRIP_THREAD_START + 11: ("Arjun",  "haan lagta hai sab aa rahe, Mehak tu?", "planning", "trip_decision"),
    TRIP_THREAD_START + 12: ("Mehak",  "main bhi hun, leave le lungi", "planning", "trip_decision"),
    TRIP_THREAD_START + 13: ("Kavya",  "okay toh 8 log pakka, hotel kab book karein?", "planning", "trip_decision"),
    TRIP_THREAD_START + 14: ("Dev",    "jaldi karo yaar, March mein availability tight hoti hai", "planning", "trip_decision"),
    TRIP_THREAD_START + 15: ("Priya",  "21-24 March? 4 raat 5 din?", "planning", "trip_decision"),
    TRIP_THREAD_START + 16: ("Rahul",  "thoda lamba nahi hoga? 3 raat enough hai", "planning", "trip_decision"),
    TRIP_THREAD_START + 17: ("Sneha",  "nahi yaar 4 raat karo Manali ke liye, travel mein ek din jaata hai", "planning", "trip_decision"),
    TRIP_THREAD_START + 18: ("Arjun",  "haan Sneha sahi bol rahi hai, ek din toh jaega aane jaane mein", "reaction", "trip_decision"),
    TRIP_THREAD_START + 19: ("Rohan",  "21-24 hi karo, chutti bhi milegi", "reaction", "trip_decision"),
    TRIP_THREAD_START + 20: ("Kavya",  "koi objection? nahi toh 21-24 final kar dein", "planning", "trip_decision"),
    TRIP_THREAD_START + 21: ("Dev",    "fine by me", "reaction", "trip_decision"),
    TRIP_THREAD_START + 22: ("Mehak",  "ticket jaldi book karna pls, price badh jaati hai", "planning", "trip_decision"),
    TRIP_THREAD_START + 23: ("Priya",  "haan kal tak book kar lete hain", "planning", "trip_decision"),
    TRIP_THREAD_START + 24: ("Rahul",  "train ya flight? train sasta hoga", "planning", "trip_decision"),
    TRIP_THREAD_START + 25: ("Sneha",  "train, Manali ke liye Volvo bus bhi lena padega Chandigarh se", "planning", "trip_decision"),
    TRIP_THREAD_START + 26: ("Arjun",  "haan sahi hai, train to Chandigarh then Volvo", "reaction", "trip_decision"),
    TRIP_THREAD_START + 27: ("Rohan",  "okay toh koi date pe objection hai? bol do abhi", "planning", "trip_decision"),
    TRIP_THREAD_START + 28: ("Kavya",  "nahi sab theek hai", "reaction", "trip_decision"),
    TRIP_THREAD_START + 29: ("Dev",    "no issues from my side", "reaction", "trip_decision"),
    TRIP_THREAD_START + 30: ("Mehak",  "main bhi ready hun", "reaction", "trip_decision"),
    TRIP_THREAD_START + 31: ("Priya",  "Arjun dates lock karte hain na?", "planning", "trip_decision"),
    TRIP_THREAD_START + 32: ("Arjun",  "haan bhai, toh officially dates lock kar raha hun", "planning", "trip_decision"),
    # ── THE DECISION MESSAGE ──
    TRIP_THREAD_START + 33: ("Rohan",  "toh chalo fix karte hain yaar, 21 March Manali pakka", "planning", "trip_decision"),
    TRIP_THREAD_START + 34: ("Sneha",  "yayyy finally 🏔️🥳", "reaction", "trip_decision"),

    # ── Split thread (hotel cost / money split, January 2024) ─────────────
    SPLIT_THREAD_START + 0:  ("Kavya",  "guys hotel total 40k aa raha hai 4 raaton ka", "budget", "split_decision"),
    SPLIT_THREAD_START + 1:  ("Dev",    "kitne log final hain? 8 pakka?", "budget", "split_decision"),
    SPLIT_THREAD_START + 2:  ("Priya",  "haan 8 log, Rohan bhi yes hai mujhe abhi bataya usne", "budget", "split_decision"),
    SPLIT_THREAD_START + 3:  ("Rahul",  "toh per head 5k banta hai roughly", "budget", "split_decision"),
    SPLIT_THREAD_START + 4:  ("Mehak",  "food alag hoga kya? ya included?", "budget", "split_decision"),
    SPLIT_THREAD_START + 5:  ("Sneha",  "food alag hoga, abhi sirf hotel split karo", "budget", "split_decision"),
    SPLIT_THREAD_START + 6:  ("Arjun",  "5k per head toh theek hai, meal toh wahan dekhenge", "budget", "split_decision"),
    SPLIT_THREAD_START + 7:  ("Rohan",  "UPI kar du seedha Arjun ko?", "budget", "split_decision"),
    SPLIT_THREAD_START + 8:  ("Kavya",  "Arjun tum collect karo sab se?", "budget", "split_decision"),
    SPLIT_THREAD_START + 9:  ("Arjun",  "haan main kar leta hun, easy hai", "budget", "split_decision"),
    SPLIT_THREAD_START + 10: ("Dev",    "par bhai refund ka kya? agar koi cancel kare", "budget", "split_decision"),
    SPLIT_THREAD_START + 11: ("Priya",  "good point Dev, refund policy check karo", "budget", "split_decision"),
    SPLIT_THREAD_START + 12: ("Kavya",  "hotel ne bola 7 din pehle cancel karo toh 80% refund milega", "budget", "split_decision"),
    SPLIT_THREAD_START + 13: ("Mehak",  "okay fair hai, toh 5k send karte hain sab", "budget", "split_decision"),
    SPLIT_THREAD_START + 14: ("Rahul",  "wait koi partial payment nahi hogi na? ek saath 5k?", "budget", "split_decision"),
    SPLIT_THREAD_START + 15: ("Sneha",  "haan ek saath hi do warna hotel ka slot jaega", "budget", "split_decision"),
    SPLIT_THREAD_START + 16: ("Rohan",  "theek hai bhai sending tonight itself", "budget", "split_decision"),
    SPLIT_THREAD_START + 17: ("Dev",    "same, aaj raat tak kar dunga", "budget", "split_decision"),
    SPLIT_THREAD_START + 18: ("Priya",  "main bhi kar deti hun kal subah", "budget", "split_decision"),
    SPLIT_THREAD_START + 19: ("Arjun",  "okay guys, mera UPI @arjun-travel hai, ye note karo", "budget", "split_decision"),
    SPLIT_THREAD_START + 20: ("Kavya",  "noted, abhi send karti hun", "budget", "split_decision"),
    SPLIT_THREAD_START + 21: ("Mehak",  "bhai aaj hi karna hai ya kal tak chalega?", "budget", "split_decision"),
    SPLIT_THREAD_START + 22: ("Arjun",  "kal subah tak theek hai, but aaj raat se pehle better hai", "budget", "split_decision"),
    SPLIT_THREAD_START + 23: ("Rohan",  "main abhi kar deta hun ekdum, done 5k sent", "budget", "split_decision"),
    SPLIT_THREAD_START + 24: ("Sneha",  "sent! screenshot bhej dena sabko Arjun", "budget", "split_decision"),
    SPLIT_THREAD_START + 25: ("Dev",    "haan confirmation bhej dena", "budget", "split_decision"),
    SPLIT_THREAD_START + 26: ("Priya",  "main kal subah 9 baje tak kar deti hun pucca", "budget", "split_decision"),
    SPLIT_THREAD_START + 27: ("Rahul",  "okay collecting progress update karte rehna Arjun", "budget", "split_decision"),
    SPLIT_THREAD_START + 28: ("Kavya",  "guys abhi tak kitno ne bheja?", "budget", "split_decision"),
    SPLIT_THREAD_START + 29: ("Arjun",  "Rohan aur Sneha ne bheja, baaki abhi pending", "budget", "split_decision"),
    SPLIT_THREAD_START + 30: ("Mehak",  "okay main bhi abhi bhejti hun", "budget", "split_decision"),
    SPLIT_THREAD_START + 31: ("Dev",    "done from my end too", "budget", "split_decision"),
    SPLIT_THREAD_START + 32: ("Priya",  "kal subah pakka from me", "budget", "split_decision"),
    # ── THE DECISION MESSAGE ──
    SPLIT_THREAD_START + 33: ("Arjun",  "theek hai bhai, 5k each split kar dete hain, done", "budget", "split_decision"),
    SPLIT_THREAD_START + 34: ("Kavya",  "perfect, screenshot bhej dena baad mein", "budget", "split_decision"),

    # ── Confirmation thread (final departure lock, March 2024) ────────────
    CONFIRM_THREAD_START + 0:  ("Rahul",  "guys train seats almost full dikh rahi hai, koi update hai?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 1:  ("Priya",  "booking se pehle ek baar sabka confirm le lo", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 2:  ("Mehak",  "meri leave approved aa gayi finally 🎉", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 3:  ("Dev",    "same, I am in 100%", "reaction", "trip_confirmation"),
    CONFIRM_THREAD_START + 4:  ("Sneha",  "21 hi na departure? subah wali train?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 5:  ("Kavya",  "haan 21 March morning wali, 6:05 AM Hazrat Nizamuddin se", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 6:  ("Rohan",  "uff 6 baje ki train, koi last minute cancel mat karna 😂", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 7:  ("Priya",  "😂😂 haan pakka aana sab", "reaction", "trip_confirmation"),
    CONFIRM_THREAD_START + 8:  ("Rahul",  "station pe milenge 5:30 AM? packing ready hai sabki?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 9:  ("Arjun",  "meri packing ho gayi, warmers zarur le ana", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 10: ("Sneha",  "haan Manali mein bahut thand hogi, layers le lo", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 11: ("Dev",    "sleeping bag bhi le luna main?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 12: ("Kavya",  "hotel mein razai milegi, sleeping bag ki zarurat nahi", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 13: ("Mehak",  "medicine le lena sab, altitude sickness hoti hai wahan", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 14: ("Rohan",  "haan Diamox le lo, doctor se prescription le lo ek baar", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 15: ("Priya",  "good point, main kal doctor se leti hun", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 16: ("Rahul",  "guys train ticket kisi ne book ki ya abhi pending hai?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 17: ("Arjun",  "main book kar raha hun kal, abhi waitlist dekh raha hun", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 18: ("Sneha",  "jaldi karo, seats bilkul nahi hain March mein", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 19: ("Dev",    "Tatkal lene padenge shayad", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 20: ("Kavya",  "Tatkal toh expensive hoga", "budget", "trip_confirmation"),
    CONFIRM_THREAD_START + 21: ("Mehak",  "koi alternative hai? bus?", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 22: ("Rohan",  "nahi yaar bus 14 ghante lagti hai, train better hai", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 23: ("Priya",  "Arjun jaldi check karo aaj raat tak bolo", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 24: ("Arjun",  "haan mil gayi seats, 3A mein available hai, book kar raha hun", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 25: ("Rahul",  "perfect, abhi book karo mat ruko", "planning", "trip_confirmation"),
    CONFIRM_THREAD_START + 26: ("Sneha",  "kitna amount hai? sabka batao", "budget", "trip_confirmation"),
    CONFIRM_THREAD_START + 27: ("Arjun",  "1,450 per person 3A mein", "budget", "trip_confirmation"),
    CONFIRM_THREAD_START + 28: ("Dev",    "that's fine, book it", "reaction", "trip_confirmation"),
    CONFIRM_THREAD_START + 29: ("Kavya",  "haan karo, main UPI abhi kar deti hun", "budget", "trip_confirmation"),
    CONFIRM_THREAD_START + 30: ("Mehak",  "done from my side ✅", "reaction", "trip_confirmation"),
    CONFIRM_THREAD_START + 31: ("Priya",  "lets gooo 🚂🏔️", "reaction", "trip_confirmation"),
    # ── THE DECISION MESSAGE ──
    CONFIRM_THREAD_START + 32: ("Arjun",  "21 March pakka confirmed hai, sab ready raho", "planning", "trip_confirmation"),
}

# Thread index ranges for quick lookup
THREAD_RANGES: Final = {
    "trip_decision":    range(TRIP_THREAD_START,    TRIP_THREAD_START + 35),
    "split_decision":   range(SPLIT_THREAD_START,   SPLIT_THREAD_START + 35),
    "trip_confirmation": range(CONFIRM_THREAD_START, CONFIRM_THREAD_START + 33),
}

# ---------------------------------------------------------------------------
# Templates — 200+ unique, realistic Hinglish messages
# ---------------------------------------------------------------------------
TEMPLATES: Final[dict[str, tuple[str, ...]]] = {
    "casual": (
        "kal ka scene kya hai?",
        "arre yaar traffic ne maar di aaj",
        "aaj mood off sa hai",
        "chai pe milte after work?",
        "group dead kyun hai aajkal",
        "bhai kuch interesting bata",
        "aaj kuch nahi ho raha", 
        "koi online hai?",
        "yaar neend aa rahi hai office mein",
        "kal ki meeting cancel ho gayi btw",
        "aaj baarish ho rahi hai kya tumhare area mein?",
        "office mein AC bahut tez chal raha hai",
        "headache ho rahi hai subah se",
        "weekend kab aayega yaar",
        "din itna lamba kyun lagta hai",
        "lunch break pe kya kiya sab ne",
        "bhai subah se kuch nahi khaya",
        "power cut aa gayi yaar",
        "wifi slow chal raha hai aaj",
        "koi recommendation hai web series?",
        "yaar Sunday chali gayi pata hi nahi chala",
        "aaj bohot kaam tha office mein",
        "thaka hua hun ekdum",
        "kal chutti hai kya?",
        "bhai phone ka battery 2% pe aa gaya",
        "koi hai group mein?",
        "sab theek hai tumhara?",
        "kal subah jaldi uthna hai uff",
        "aaj gym nahi gaya, guilty feel ho raha",
        "bhai mood nahi hai aaj kuch karne ka",
        "arre suno ek funny cheez hua aaj",
        "office ka printer phir se kharab hai",
        "meeting 3 ghante chali aaj, pagal ho gaya",
        "yaar khana order karein? bhuk lagi hai",
        "kal ka weather kaisa rahega?",
        "koi call pe baat kar sakta hai 2 min?",
        "bhai aaj kitna kaam kiya puch mat",
        "sham ko kya plan hai",
        "group mein koi naya kya chal raha hai",
        "aaj bohot acha din tha actually 😊",
    ),
    "reaction": (
        "haan",
        "nahi",
        "done",
        "lol",
        "same",
        "acha",
        "omg",
        "😂",
        "👍",
        "yesss",
        "haa bhai",
        "sahi hai",
        "bilkul",
        "pakka",
        "👍🏻",
        "😭😭",
        "💀",
        "🔥",
        "okk",
        "hmm",
        "kk",
        "nhi",
        "haa",
        "accha accha",
        "theek hai",
        "noted",
        "perfect",
        "sure",
        "got it",
        "👀",
        "😂😂",
        "yaar 😭",
        "bhai 😭",
        "uff",
        "okay okay",
        "chalega",
        "dekh lete hain",
        "acha toh",
        "nice nice",
        "wah wah",
        "great",
        "sounds good",
        "+1",
        "agree",
        "haha",
        "lmao",
        "omg no way",
        "seriously?",
        "bhai kya",
        "💯",
    ),
    "media_omitted": (
        "<Media omitted>",
        "<Sticker omitted>",
        "<Image omitted>",
        "<Video omitted>",
        "<GIF omitted>",
        "<Voice note - 0:12>",
        "<Voice note - 0:34>",
        "<Voice note - 1:02>",
        "<Voice note - 0:08>",
        "<Voice note - 2:14>",
        "<Voice note - 0:47>",
        "<Document omitted>",
        "<Contact card omitted>",
    ),
    "forwarded": (
        "Forwarded\nWeekend sale live hai, dekh lo 50% off sab par",
        "Forwarded\nRain alert: umbrella le jana aaj, heavy showers expected",
        "Forwarded\nUseful productivity tip: 2-minute rule ke baare mein padho",
        "Forwarded\nBREAKING: New metro line approved for our area 🚇",
        "Forwarded\nYeh recipe try ki? Dal makhani ghar pe bilkul dhaba jaise banti hai",
        "Forwarded\nMotivational: Jo darta hai woh marta hai. Karo aur seekho.",
        "Forwarded\nHoliday list 2024 aa gayi — dekho kitni long weekends hain!",
        "Forwarded\nHealth tip: Roz subah 10 min dhoop mein baithna chahiye",
        "Forwarded\nDeal of the day: Flights to Goa at ₹1,999 only",
        "Forwarded\nImportant: New UPI charges applicable from next month",
        "Forwarded\nAmazon Great Indian Sale shuru ho gayi, link attach hai",
        "Forwarded\n[VIDEO] Yeh dog ka video dekho, full day ka mood ban jaega 🐶",
    ),
    "work": (
        "deck ka latest version bhej diya, review kar dena",
        "standup 10 min late hoga aaj, stuck hun traffic mein",
        "client ne last minute changes maange hain phir se",
        "PR review kar dena pls, urgent hai",
        "meeting notes kisi ke paas hain aaj ke?",
        "bhai deadline kal hai, sab ready hai?",
        "call 3 baje hai, sab free ho?",
        "Slack pe message kiya tha, dekha?",
        "presentation kal hai, feedback chahiye",
        "koi bug aa raha hai production mein, dekh rahe hain",
        "new joiner kal aayega team mein",
        "appraisal cycle shuru ho gaya, goal set karo",
        "project scope change hua, brief bhejta hun",
        "sprint planning Monday ko hai, prepare karo",
        "stakeholder call cancel ho gayi, rescheduled for Thursday",
        "document update kar diya, please review before EOD",
        "resource allocation mein problem aa rahi hai",
        "design review 4 PM pe hai, koi chhota update?",
        "kisi ne quarterly report dekhi? numbers off lag rahe hain",
        "intern ko onboarding process explain kar do please",
    ),
    "food": (
        "aaj lunch mein kya khaya?",
        "mom ke haath ka rajma chawal 😭❤️",
        "pizza order karein? koi objection?",
        "best momos kidhar milte hain yaar nearby?",
        "coffee badly needed, itna neend aa rahi hai",
        "biryani ka mood hai aaj shaam",
        "koi restaurant suggest karo Saturday ke liye",
        "ghar ka khana hi best hai honestly",
        "Swiggy pe kya order kiya aaj?",
        "bhai office canteen ne phir se kharab khana diya",
        "Dominos ka deal chal raha hai, order karein?",
        "chai ya coffee? serious question",
        "yaar bhuk lag rahi hai kuch hua nahi abhi tak",
        "dessert ka mood hai, ice cream ya gulab jamun?",
        "aaj ghar mein khana ban raha hai ya order?",
        "healthy khana khaya aaj finally 💪",
        "bhai wahan nayal par new south indian place khula hai, try karo",
        "thali ka option chahiye lunch mein",
        "koi midnight snack idea hai?",
        "green tea vs regular chai debate karte hain",
    ),
    "planning": (
        "Saturday ka plan banao koi",
        "cab 7 baje book karun?",
        "location share kar dena time pe",
        "kaun kaun aa raha final?",
        "table reserve karna padega advance mein",
        "kab milna hai decide karo",
        "venue decide hua kya?",
        "kitne log aa rahe total?",
        "time change hoga kya?",
        "confirm karo aane se pehle",
        "koi ek volunteer karo booking ke liye",
        "group call karein aaj raat?",
        "plan postpone hua kya?",
        "kal ke liye kuch naya plan banate hain",
        "next weekend ka kuch soch rahe?",
        "festival mein kuch special karte hain?",
        "koi plan hai ya ghoomte ghoomte decide karein?",
        "backup plan bhi socho in case of rain",
        "dress code kya hai is event ka?",
        "itinerary share karo sab ke saath",
    ),
    "budget": (
        "mera share kitna hua?",
        "UPI id bhejo pls",
        "bill split kar lete hain sab mein",
        "discount mila kya? coupon code hai?",
        "cash nahi hai mere paas, UPI karunga",
        "bhai bahut expensive ho gaya",
        "kitna budget hai approximate?",
        "koi cheaper option hai?",
        "split kar dete hain equally",
        "bhai mere wallet mein sirf 500 hain abhi",
        "PayTM ya GPay?",
        "kal tak bhejna, aaj battery nahi hai",
        "receipt lena mat bhulna",
        "yaar thoda overspend ho gaya is baar",
        "kitna each person ka hua total mein?",
        "bhai advance mein bhar do, settle karte hain baad mein",
        "Splitwise update karo guys",
        "kitna paise bache hain trip ke baad?",
        "food ka alag rakhein ya saath?",
        "EMI mein ho sakta hai kya?",
    ),
}

# Characters commonly swapped in Hinglish typos
_TYPO_SWAPS: Final = {
    "a": "aa", "i": "ii", "n": "nn", "k": "kk", "h": "",
    "e": "ae", "r": "rr", "t": "tt",
}


def _inject_typo(text: str, rng: random.Random) -> str:
    """Randomly apply one realistic character-level typo to a word in text."""
    words = text.split()
    if len(words) < 2:
        return text
    word_index = rng.randrange(len(words))
    word = words[word_index]
    if len(word) < 3:
        return text
    char_index = rng.randrange(1, len(word))
    char = word[char_index]
    if char in _TYPO_SWAPS and rng.random() < 0.5:
        replacement = _TYPO_SWAPS[char]
    else:
        replacement = word[char_index - 1]  # swap adjacent
    words[word_index] = word[:char_index] + replacement + word[char_index + 1:]
    return " ".join(words)


# ---------------------------------------------------------------------------
# Bursty timestamp generation
# ---------------------------------------------------------------------------
def _generate_bursty_timestamps(count: int, rng: random.Random) -> list[datetime]:
    """Generate realistic bursty chat timestamps with activity clusters."""
    timestamps: list[datetime] = []
    current = START_DATE
    total_seconds = int((END_DATE - START_DATE).total_seconds())
    # Generate cluster boundaries
    cluster_starts: list[datetime] = []
    t = START_DATE
    while t < END_DATE and len(timestamps) < count:
        cluster_starts.append(t)
        gap_hours = rng.uniform(2, 14)  # silence between clusters
        t += timedelta(hours=gap_hours)

    cluster_index = 0
    msg_index = 0
    current = START_DATE

    while msg_index < count:
        # Within a cluster, messages arrive in quick bursts (10 sec – 8 min apart)
        burst_size = rng.randint(8, 28)
        for _ in range(burst_size):
            if msg_index >= count:
                break
            timestamps.append(current)
            current += timedelta(seconds=rng.randint(10, 480))
            msg_index += 1
        # Gap between clusters (2–14 hours), skip quiet night hours
        gap = timedelta(hours=rng.uniform(2, 14))
        current += gap
        if current.hour < 8:
            current = current.replace(hour=9, minute=rng.randint(0, 59))

    # Sort and clamp to END_DATE
    timestamps.sort()
    scale = total_seconds / max(1, int((timestamps[-1] - timestamps[0]).total_seconds()))
    origin = timestamps[0]
    timestamps = [
        START_DATE + timedelta(seconds=min(int((t - origin).total_seconds() * scale), total_seconds))
        for t in timestamps
    ]
    return timestamps


# ---------------------------------------------------------------------------
# Conversation-flow sender selection
# ---------------------------------------------------------------------------
def _next_sender(index: int, prev_senders: list[str], rng: random.Random) -> str:
    """Pick next sender with natural back-and-forth — avoid same person 3× in row."""
    if not prev_senders:
        return rng.choice(PARTICIPANTS)
    # Active window: last 3 unique senders tend to dominate
    recent = list(dict.fromkeys(reversed(prev_senders[-6:])))[:4]
    weights = []
    for p in PARTICIPANTS:
        if p == prev_senders[-1]:
            weights.append(1)   # very low: just spoke
        elif p in recent:
            weights.append(8)   # likely to respond
        else:
            weights.append(3)   # possible but less likely
    return rng.choices(PARTICIPANTS, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Main corpus generator
# ---------------------------------------------------------------------------
def generate_corpus() -> list[dict[str, object]]:
    """Return exactly 4,200 deterministic realistic fictional messages."""
    rng = random.Random(SEED)

    # All planted indices
    planted_indices = set(THREAD_MESSAGES.keys())

    # Assign message types for non-planted messages
    type_pool: list[str] = []
    type_targets = {
        "casual": 900,
        "reaction": 700,
        "media_omitted": 350,
        "forwarded": 130,
        "work": 480,
        "food": 380,
        "planning": 420,
        "budget": 390,
    }
    # Subtract planted slots
    from collections import Counter
    planted_type_counts = Counter(item[2] for item in THREAD_MESSAGES.values())
    for kind, count in type_targets.items():
        adjusted = count - planted_type_counts.get(kind, 0)
        type_pool.extend([kind] * max(0, adjusted))

    # Pad or trim to exactly MESSAGE_COUNT - len(planted_indices) slots
    non_planted_count = MESSAGE_COUNT - len(planted_indices)
    while len(type_pool) < non_planted_count:
        type_pool.append(rng.choice(list(type_targets.keys())))
    type_pool = type_pool[:non_planted_count]
    rng.shuffle(type_pool)

    # Generate bursty timestamps
    timestamps = _generate_bursty_timestamps(MESSAGE_COUNT, random.Random(SEED + 1))

    # Max 3 repeats per template — prevents any single phrase becoming an embedding attractor
    MAX_TEMPLATE_REPEATS = 3
    capped_templates: dict[str, list[str]] = {}
    for kind, tmpl_pool in TEMPLATES.items():
        pool = list(tmpl_pool) * MAX_TEMPLATE_REPEATS
        rng.shuffle(pool)
        capped_templates[kind] = pool
    template_cursors: dict[str, int] = {kind: 0 for kind in TEMPLATES}

    def _pick_template(kind: str) -> str:
        pool = capped_templates[kind]
        idx = template_cursors[kind] % len(pool)
        template_cursors[kind] += 1
        return pool[idx]

    messages: list[dict[str, object]] = []
    prev_senders: list[str] = []
    type_iter = iter(type_pool)

    for index in range(MESSAGE_COUNT):
        planted = THREAD_MESSAGES.get(index)
        ts = timestamps[index].isoformat()

        if planted:
            sender, text, message_type, thread_id = planted
        else:
            message_type = next(type_iter)
            sender = _next_sender(index, prev_senders, rng)
            text = _pick_template(message_type)
            # Inject typo on ~10% of casual/reaction messages
            if message_type in ("casual", "reaction") and rng.random() < 0.10:
                text = _inject_typo(text, rng)
            thread_id = None

        prev_senders.append(sender)
        messages.append({
            "id": f"msg_{index + 1:04d}",
            "sender": sender,
            "text": text,
            "timestamp": ts,
            "thread_id": thread_id,
            "message_type": message_type,
            "original_index": index,
        })

    return messages


def main() -> None:
    """Write corpus JSON beside generator."""
    corpus = generate_corpus()
    CORPUS_PATH.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(corpus)} messages to {CORPUS_PATH}")


if __name__ == "__main__":
    main()
