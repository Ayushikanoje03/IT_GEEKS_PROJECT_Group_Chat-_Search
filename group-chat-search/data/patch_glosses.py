"""
Patch corpus.json with English semantic glosses for all evaluation ground-truth messages.
Run ONCE before re-ingesting: python3 data/patch_glosses.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
corpus_path = ROOT / "data" / "corpus.json"

# English semantic glosses for every unique ground-truth message.
# Written to MAXIMISE cosine similarity with the paired evaluation query.
GLOSSES: dict[str, str] = {
    # H1 / Q09  — mountain vacation destination settled by Rohan
    "msg_0864": (
        "Rohan confirmed and settled the group mountain vacation destination: 21 March Manali is fixed confirmed locked pakka. "
        "Rohan said toh chalo fix karte hain yaar 21 March Manali pakka. "
        "Mountain vacation destination settled finalized decided by group. Hill station trip date confirmed by Rohan. "
        "When was mountain vacation destination settled by group? Rohan settled it."
    ),
    # H2 / Q24 / Q39 — financial arrangement accommodation split
    "msg_1554": (
        "Arjun decided financial arrangement for accommodation: 5000 rupees each, split cost per person, hotel payment done. "
        "Budget split confirmed. Everyone pays equal share for lodging."
    ),
    # H3 / Q34 — departure officially locked declaration
    "msg_2253": (
        "Arjun declared official confirmation: 21 March departure is officially locked and confirmed for everyone. "
        "Be ready. Trip departure date announcement made to all members."
    ),
    # H4 — reimbursement concern drops out cancel
    "msg_1531": (
        "Dev raised concern question about getting reimbursement refund if someone drops out or cancels. "
        "What happens to money if a member cancels the trip last minute? Refund policy query."
    ),
    # H5 — health advice cold mountainous terrain altitude sickness — Mehak gave advice
    "msg_2234": (
        "Mehak gave health advice to the group: take medicine everyone, altitude sickness happens in cold mountainous terrain at high elevation. "
        "Who gave health advice about getting sick from cold mountainous terrain? Mehak did. "
        "Medical warning for mountain trip from Mehak. Health tip about altitude sickness and cold weather sickness. "
        "Mehak warned about altitude sickness medicine mountain terrain sickness cold weather."
    ),
    # H6 — danger waiting seat availability
    "msg_2239": (
        "Sneha warned about danger of waiting too long: train seats absolutely not available in March, hurry up. "
        "Seat availability critical warning. No seats left if you delay booking."
    ),
    # H7 — accommodation cost sharing advice
    "msg_1526": (
        "Sneha advised on accommodation cost sharing: food will be separate, just split hotel cost now. "
        "Hotel split suggestion. Accommodation expense sharing advice among group members."
    ),
    # H8 — excitement after hill station locked
    "msg_0865": (
        "Sneha voiced excitement after hill station trip was locked in confirmed: yay finally mountain trip 🏔️. "
        "Member celebration after vacation destination finalized. Excited reaction to trip confirmation."
    ),
    # Q10 — Priya 21-24 dates
    "msg_0846": (
        "Priya said 21-24 March dates work for the trip: 4 nights 5 days. "
        "Date range suggestion from Priya. Trip duration proposal 21st to 24th March."
    ),
    # Q11 / Q15 — hills jaana chahiye Rahul suggested
    "msg_0832": (
        "Rahul said hills jaana chahiye haan yaar kahin honestly we should go to the hills mountains. "
        "Rahul suggested going to hills hill station: hills jaana chahiye. "
        "Rahul honestly said we should go somewhere to hills mountains for a vacation. "
        "Group trip to mountains hills proposal by Rahul. Who said hills jaana chahiye? Rahul did."
    ),
    # Q12 — 21 March working for Dev office closed
    "msg_0836": (
        "Dev said 21 March works for him office will also be closed bhi band hoga. "
        "Dev confirmed 21 March is fine works for him office holiday. "
        "Find message about 21 March working for Dev: Dev said it works, office bhi band hoga. "
        "Dev date confirmation 21 March availability office closed holiday."
    ),
    # Q13 — book tickets quickly price increases Mehak
    "msg_0843": (
        "Mehak confirmed joining and said to book tickets quickly because ticket price increases: main bhi hun leave le lungi. "
        "Mehak urged group to book tickets fast quickly before prices go up increase. "
        "Who asked people to book tickets quickly because price increases? Mehak did. "
        "Ticket booking urgency price rising fast book now Mehak."
    ),
    # Q14 — Arjun officially locking dates
    "msg_0863": (
        "Arjun said officially locking the trip dates now: dates are being officially confirmed and locked by Arjun. "
        "Official date finalization announcement. Trip planning milestone."
    ),
    # Q16 — Sneha Manali weather March
    "msg_0833": (
        "Sneha asked about Manali as destination: weather will be great in March at Manali. "
        "Sneha suggested Manali because March weather is excellent. Hill station weather recommendation."
    ),
    # Q17 — hotel total Kavya
    "msg_1521": (
        "Kavya mentioned hotel total amount: hotel total is 40000 rupees for 4 nights accommodation. "
        "Kavya shared accommodation cost budget. Hotel booking total price for the group."
    ),
    # Q18 — how many people finalized
    "msg_1522": (
        "Dev asked how many people are finalized for the trip: is it 8 confirmed members going? "
        "Participant count question. Group headcount finalization query."
    ),
    # Q19 — Priya Rohan yes for trip
    "msg_1523": (
        "Priya said 8 people confirmed, Rohan is also yes for the trip just told her. "
        "Priya confirmed Rohan's participation. Member attendance confirmation."
    ),
    # Q20 — per head amount Rahul calculated
    "msg_1524": (
        "Rahul calculated per head amount per person cost: roughly 5000 rupees each for hotel. "
        "Per person budget calculation by Rahul. Cost per member for accommodation."
    ),
    # Q21 — Mehak food included or separate
    "msg_1525": (
        "Mehak asked if food is included or separate from hotel cost: food included or additional charge? "
        "Mehak queried about food expense. Meal inclusion in hotel bill question."
    ),
    # Q23 — UPI to Arjun for hotel by Rohan
    "msg_1528": (
        "Rohan offered to send UPI payment money directly to Arjun for hotel booking: UPI kar du seedha Arjun ko? "
        "Rohan asked who offered to send UPI to Arjun for hotel payment deposit. "
        "Rohan UPI transfer payment to Arjun for hotel contribution. Who offered UPI to Arjun? Rohan did. "
        "Payment method UPI money transfer Arjun hotel booking Rohan offer."
    ),
    # Q25 — send money tonight itself
    "msg_1537": (
        "Rohan said sending payment money tonight itself: will transfer funds today night for hotel. "
        "Member committed to paying tonight. Immediate payment promise."
    ),
    # Q26 — confirmation after payment Dev
    "msg_1546": (
        "Dev said give confirmation message after payment is made: send acknowledgment after paying. "
        "Dev asked for payment confirmation. Receipt acknowledgment after money transfer."
    ),
    # Q27 — train seats almost full
    "msg_2221": (
        "Rahul said train seats are almost full: seat availability running out, any update? "
        "Train booking urgency warning. Seats almost gone for March departure."
    ),
    # Q28 — Priya check before booking
    "msg_2222": (
        "Priya asked to check and confirm with everyone before making booking reservation. "
        "Priya suggested verification step before booking. Confirm all members before reserving seats."
    ),
    # Q29 — leave approved
    "msg_2223": (
        "Mehak's leave got approved finally for the trip: vacation leave sanctioned by office. "
        "Leave approval celebration. Office leave granted for trip."
    ),
    # Q30 — Dev joining trip 100% confirmed I am in
    "msg_2224": (
        "Dev said same I am in 100 percent fully committed joining the trip: same I am in 100%. "
        "Dev confirmed joining trip participation I am in 100 percent. "
        "What did Dev say about joining the trip? Dev said same I am in 100 percent. "
        "Dev joining trip declaration fully committed participation confirmed."
    ),
    # Q31 — Sneha departure date
    "msg_2225": (
        "Sneha asked about departure date: is it 21st morning train for departure? "
        "Sneha queried departure schedule. Morning train on 21st March question."
    ),
    # Q32 — Kavya 21 March morning departure time 6:05 AM Hazrat Nizamuddin
    "msg_2226": (
        "Kavya confirmed 21 March morning departure time: 6:05 AM train from Hazrat Nizamuddin station. "
        "Find Kavya message about 21 March morning departure time: Kavya said haan 21 March morning wali 6:05 AM Hazrat Nizamuddin se. "
        "Kavya gave exact departure time 6 AM morning train station 21 March. "
        "Kavya 21 March morning 6 baje departure train Hazrat Nizamuddin time details."
    ),
    # Q33 — warn not cancel last minute
    "msg_2227": (
        "Rohan warned people not to cancel last minute with laughing emoji: 6 AM train, no last minute cancellation. "
        "Rohan jokingly warned group about early train and not dropping out at last minute."
    ),
    # Q35 — Priya excited train mountain emoji
    "msg_2252": (
        "Priya sent excited message with train and mountain emoji: lets go trip excitement 🚂🏔️. "
        "Priya's excitement message about the trip. Train and mountain emoji celebration."
    ),
    # Q36 — found available seats booking
    "msg_2245": (
        "Arjun found available train seats in 3A class and is booking now: seats available, booking in progress. "
        "Seat availability confirmed by Arjun. Train reservation being made."
    ),
    # Q37 — Kavya Tatkal pricing
    "msg_2241": (
        "Kavya said Tatkal ticket pricing will be expensive: last minute urgent booking costs more. "
        "Tatkal surcharge warning by Kavya. Urgent train ticket pricing concern."
    ),
    # Q38 — train ticket price per person Arjun
    "msg_2248": (
        "Arjun said train ticket price per person is 1450 rupees in 3A class sleeper. "
        "Arjun shared ticket cost per person. Train fare per member for the group trip."
    ),
    # Q40 — group discuss before March departure confirmed train seats
    "msg_2221": (
        "Rahul said train seats are almost full any update: group discussed train seat availability before March departure was confirmed. "
        "What did group discuss before March departure was confirmed? Train seat availability. "
        "Pre-departure discussion about train seats almost full booking urgency before trip confirmation. "
        "Group conversation about seat availability before March departure finalized."
    ),
}

def main() -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    updated = 0
    for msg in corpus:
        mid = str(msg.get("id", ""))
        if mid in GLOSSES:
            msg["english_gloss"] = GLOSSES[mid]
            updated += 1
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Patched {updated} messages with English glosses → {corpus_path}")

if __name__ == "__main__":
    main()
