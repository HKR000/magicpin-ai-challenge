"""Unit tests for IntentClassifier."""

import unittest
from vera.intent.categories import IntentCategory
from vera.intent.classifier import IntentClassifier
from vera.models.intent import IntentType


class TestIntentClassifier(unittest.TestCase):
    """Comprehensive test suite for multilingual intent classification."""

    def setUp(self):
        self.classifier = IntentClassifier()

    # 1. Acceptance & Commitment
    def test_english_acceptance(self):
        cases = [
            "Ok lets do it. Whats next?",
            "Yes please proceed with the update",
            "Please update my google profile",
            "Send me the abstract",
            "I want to join magicpin",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.COMMITMENT, f"Failed on: {text}")
            self.assertGreaterEqual(res.confidence, 0.90)

    def test_hinglish_acceptance(self):
        cases = [
            "Haan please kar do",
            "Theek hai start karo",
            "Mujhe magicpin judna hai",
            "Haan kardo draft bhej do",
            "Bilkul chalega",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.COMMITMENT, f"Failed on: {text}")
            self.assertGreaterEqual(res.confidence, 0.90)

    def test_hindi_devanagari_acceptance(self):
        cases = [
            "हाँ कृपया कर दीजिए",
            "शुरू करो",
            "हाँ भेज दीजिए",
            "ठीक है",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.COMMITMENT, f"Failed on: {text}")
            self.assertGreaterEqual(res.confidence, 0.90)

    # 2. Short Messages
    def test_short_messages(self):
        affirmatives = ["yes", "yep", "sure", "ok", "done", "haan", "chalega", "हाँ"]
        for text in affirmatives:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.COMMITMENT, f"Failed short affirmative: {text}")

        negatives = ["no", "nope", "nahi", "nahin", "नहीं"]
        for text in negatives:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.HOSTILE_OPT_OUT, f"Failed short negative: {text}")

    # 3. Typographical Errors & Collapsing Repeated Characters
    def test_typographical_errors(self):
        cases = [
            ("yeeessss please", IntentType.COMMITMENT),
            ("ok lets do it", IntentType.COMMITMENT),
            ("stopppp messaging", IntentType.HOSTILE_OPT_OUT),
            ("haaaan kardo", IntentType.COMMITMENT),
            ("noooo thanks", IntentType.HOSTILE_OPT_OUT),
        ]
        for text, expected in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, expected, f"Failed typo test: {text}")

    # 4. Long Messages
    def test_long_messages(self):
        long_accept = (
            "Hi Vera, thank you for checking in on our dental practice listing. "
            "We reviewed the JIDA fluoride trial details and would like to proceed with drafting "
            "the patient education WhatsApp message for our high risk adult patients immediately."
        )
        res = self.classifier.classify(long_accept)
        self.assertEqual(res.intent_type, IntentType.COMMITMENT)

        long_question = (
            "Could you explain in more detail how the Google Business Profile verification "
            "process works and how much time it takes before our updated photos and hours go live?"
        )
        res_q = self.classifier.classify(long_question)
        self.assertEqual(res_q.intent_type, IntentType.INQUIRY)

    # 5. Generic Auto-Replies (WhatsApp Business Canned Greetings)
    def test_generic_auto_replies(self):
        canned = [
            "Thank you for contacting us! Our team will respond shortly.",
            "Aapki jaankari ke liye bahut-bahut shukriya. Main aapki yeh sabhi baatein aur sujhaav hamari team tak pahuncha deti hoon.",
            "Aapki madad ke liye shukriya, lekin main ek automated assistant hoon...",
            "We are currently away from the phone. We will reply as soon as possible.",
            "This is an automated response. Our business hours are 9am to 9pm.",
        ]
        for text in canned:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.AUTO_REPLY, f"Failed auto-reply: {text}")
            self.assertGreaterEqual(res.confidence, 0.95)

    # 6. Hostile & Severe Opt-Out
    def test_hostile_and_opt_out(self):
        cases = [
            "Stop messaging me. This is useless spam.",
            "Unsubscribe immediately",
            "This is fraud and scam. I will report you.",
            "Message mat karo faltu dimag kharab mat karo",
            "मैसेज मत करो यह स्पैम है",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.HOSTILE_OPT_OUT, f"Failed hostile: {text}")

    # 7. Off-Topic Inquiries
    def test_off_topic(self):
        cases = [
            "Can you help me file my GST return?",
            "What is the weather today in Delhi?",
            "Who won yesterday's IPL cricket match?",
            "जीएसटी कैसे फाइल करें",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.OFF_TOPIC, f"Failed off-topic: {text}")

    # 8. Questions & Inquiries
    def test_questions_and_inquiries(self):
        cases = [
            "What would it look like?",
            "How much does this package cost?",
            "Kitna kharcha lagega iska?",
            "Kaise hoga process?",
            "Can you explain the timing?",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.INQUIRY, f"Failed question: {text}")

    # 9. Objections & Friction
    def test_objections(self):
        cases = [
            "This is too expensive for our small clinic",
            "Bahut mehenga hai abhi budget nahi hai",
            "Busy right now, call back later",
            "Abhi time nahi hai baad mein baat karte hain",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(res.intent_type, IntentType.QUALIFICATION, f"Failed objection: {text}")

    # 10. Unknown Remains Unknown (Zero Forcing)
    def test_unknown_remains_unknown(self):
        cases = [
            "",
            "   ",
            "hmmmmmm",
            "1234567890",
            "asdfghjkl qwerty",
            "🤔🤔🤔",
            "xyz random noise blabla",
        ]
        for text in cases:
            res = self.classifier.classify(text)
            self.assertEqual(
                res.intent_type,
                IntentType.UNKNOWN,
                f"Failed to keep unknown for ambiguous text: '{text}' -> got {res.intent_type}",
            )
            self.assertLessEqual(res.confidence, 0.50)


if __name__ == "__main__":
    unittest.main()
