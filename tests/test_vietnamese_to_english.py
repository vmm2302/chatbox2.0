"""Unit and Integration tests for Vietnamese -> English word lookup.

Covers:
1. Intent classification for Vietnamese queries and cues.
2. Lexical & BM25 retrieval for Vietnamese definitions.
3. Standalone Vietnamese phrase lookup (e.g. 'gia đình' -> 'family').
4. Translation questions with cues (e.g. 'trường học tiếng Anh là gì?' -> 'school').
5. Out-of-scope non-A1/A2 queries (e.g. 'từ bỏ' -> OUT_OF_SCOPE_RESPONSE).
6. Multi-turn conversation follow-ups after translation.
7. Regression protection for English -> Vietnamese lookups and greetings.
8. API response prefixes and structured metadata.
"""

import sys
import time
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.chat.engine import ChatEngine
from src.chat.topic_tracker import TopicTracker
from src.core.models import QARecord
from src.data.loader import QALoader
from src.nlp.phobert_intent import PhoBERTIntentClassifier
from vocab_backend.dependencies import auth_service
from vocab_backend.vocab_parser import ensure_required_search_prefix, parse_vocabulary_text


class TestVietnameseToEnglishTranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = QALoader()
        cls.records = cls.loader.get_or_create_records()
        cls.engine = ChatEngine(records=cls.records)
        cls.classifier = PhoBERTIntentClassifier()

        from fastapi.testclient import TestClient
        from vocab_backend.api_server import app
        cls.client = TestClient(app)
        uname = f"vie_test_{int(time.time() * 1000)}"
        reg = cls.client.post(
            "/api/auth/register",
            json={
                "username": uname,
                "password": "ViePassword123!",
                "confirm_password": "ViePassword123!",
            },
        )
        cls.test_user_id = reg.json()["user"]["id"]
        login = cls.client.post(
            "/api/auth/login",
            json={"username": uname, "password": "ViePassword123!"},
        )
        cls.auth_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "test_user_id", None):
            auth_service.user_repo.delete_user(cls.test_user_id)

    def test_01_intent_classification(self):
        """Test PhoBERT intent classifier recognizes TRANSLATE_VIE_TO_ENG."""
        queries = [
            ("từ nào có nghĩa là gia đình", "TRANSLATE_VIE_TO_ENG"),
            ("trường học tiếng anh là gì", "TRANSLATE_VIE_TO_ENG"),
            ("dịch từ gia đình sang tiếng anh", "TRANSLATE_VIE_TO_ENG"),
            ("gia đình", "TRANSLATE_VIE_TO_ENG"),
            ("trường học", "TRANSLATE_VIE_TO_ENG"),
        ]
        for query, expected_intent in queries:
            res = self.classifier.classify_intent(query, has_active_topic=False)
            self.assertEqual(
                res.intent,
                expected_intent,
                f"Query '{query}' expected intent '{expected_intent}' but got '{res.intent}'"
            )

    def test_02_standalone_vietnamese_phrase(self):
        """Test standalone Vietnamese phrase maps to correct A1/A2 English word."""
        tracker = TopicTracker(records=self.records)
        resp = self.engine.ask("gia đình", tracker=tracker)
        self.assertIn("family", resp.word.lower())
        self.assertEqual(resp.mode, "DIRECT_MATCH")
        self.assertEqual(resp.intent, "TRANSLATE_VIE_TO_ENG")
        self.assertEqual(tracker.active_word, "family")

    def test_03_translation_cue_question(self):
        """Test question with translation cues maps to English word."""
        tracker = TopicTracker(records=self.records)
        resp = self.engine.ask("trường học tiếng anh là gì?", tracker=tracker)
        self.assertIn("school", resp.word.lower())
        self.assertEqual(resp.mode, "DIRECT_MATCH")
        self.assertEqual(resp.intent, "TRANSLATE_VIE_TO_ENG")
        self.assertEqual(tracker.active_word, "school")

    def test_04_out_of_scope_vietnamese_word(self):
        """Test Vietnamese words outside A1/A2 return out of scope response."""
        tracker = TopicTracker(records=self.records)
        # 'từ bỏ' (abandon) was pruned as B2
        resp = self.engine.ask("từ bỏ", tracker=tracker)
        self.assertEqual(resp.mode, "NO_MATCH")
        self.assertIn(settings.OUT_OF_SCOPE_RESPONSE, resp.answer)
        self.assertIsNone(tracker.active_word)

    def test_05_multi_turn_follow_up(self):
        """Test follow-up question after translation uses translated active_word."""
        tracker = TopicTracker(records=self.records)

        # Turn 1: translate 'gia đình'
        resp1 = self.engine.ask("gia đình", tracker=tracker)
        self.assertEqual(tracker.active_word, "family")

        # Turn 2: follow-up asking for example
        resp2 = self.engine.ask("cho tôi ví dụ của từ này", tracker=tracker)
        self.assertEqual(tracker.active_word, "family")
        self.assertEqual(resp2.intent, "GET_EXAMPLE")
        self.assertIn("family", resp2.answer.lower())

    def test_06_english_lookup_regression(self):
        """Ensure standard English lookup continues working unmodified."""
        tracker = TopicTracker(records=self.records)
        resp = self.engine.ask("amazing nghĩa là gì?", tracker=tracker)
        self.assertEqual(resp.word.lower(), "amazing")
        self.assertNotEqual(resp.mode, "NO_MATCH")
        self.assertEqual(tracker.active_word, "amazing")

    def test_07_prefix_formatting(self):
        """Test ensure_required_search_prefix adapts to TRANSLATE_VIE_TO_ENG."""
        # Standard lookup prefix
        res_eng = ensure_required_search_prefix(
            "**Trình độ:** A1\n### Noun\n**1. meaning**",
            word="family",
            intent="DEFINE_VOCAB",
        )
        self.assertTrue(res_eng.startswith("Từ bạn tìm kiếm: family"))

        # Translation prefix
        res_vie = ensure_required_search_prefix(
            "**Trình độ:** A1\n### Noun\n**1. meaning**",
            word="family",
            intent="TRANSLATE_VIE_TO_ENG",
        )
        self.assertTrue(res_vie.startswith("Từ tiếng Anh phù hợp: family"))

        # Parsing recognizes both
        card_eng = parse_vocabulary_text(res_eng)
        self.assertIsNotNone(card_eng)
        self.assertEqual(card_eng["word"], "family")

        card_vie = parse_vocabulary_text(res_vie)
        self.assertIsNotNone(card_vie)
        self.assertEqual(card_vie["word"], "family")

    def test_08_api_chat_translation_endpoint(self):
        """Test POST /api/chat with Vietnamese query returns TRANSLATE_VIE_TO_ENG and correct prefix."""
        unauth = self.client.post("/api/chat", json={"query": "gia đình"})
        self.assertEqual(unauth.status_code, 401)

        res = self.client.post("/api/chat", headers=self.auth_headers, json={"query": "gia đình"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("word"), "family")
        self.assertTrue(data.get("reply", "").startswith("Từ tiếng Anh phù hợp: family"))
        self.assertEqual(data.get("meta", {}).get("intent"), "TRANSLATE_VIE_TO_ENG")
        self.assertIsNotNone(data.get("structured_card"))
        self.assertEqual(data.get("structured_card", {}).get("word"), "family")

    def test_09_api_chat_stream_vietnamese_and_guest(self):
        """Test POST /api/chat/stream requires token and handles Vietnamese queries & placeholder user_id safely."""
        unauth = self.client.post("/api/chat/stream", json={"query": "gia đình"})
        self.assertEqual(unauth.status_code, 401)

        # 1. Test authenticated user passing legacy default_user placeholder
        res_guest = self.client.post(
            "/api/chat/stream",
            headers=self.auth_headers,
            json={"query": "gia đình", "user_id": "default_user"},
        )
        self.assertEqual(res_guest.status_code, 200)
        self.assertIn("family", res_guest.text)
        self.assertIn("data: [DONE]", res_guest.text)

        # 2. Test authenticated integer user with matching user_id
        res_auth = self.client.post(
            "/api/chat/stream",
            headers=self.auth_headers,
            json={"query": "trường học tiếng anh là gì?", "user_id": self.test_user_id},
        )
        self.assertEqual(res_auth.status_code, 200)
        self.assertIn("school", res_auth.text)
        self.assertIn("data: [DONE]", res_auth.text)

        # 3. Spoofing another user_id must be rejected with 403
        res_spoof = self.client.post(
            "/api/chat/stream",
            headers=self.auth_headers,
            json={"query": "gia đình", "user_id": self.test_user_id + 999},
        )
        self.assertEqual(res_spoof.status_code, 403)

    def test_10_truong_hoc_la_gi_variations(self):
        """Test 'X là gì?' and related phrasing maps to English word if X is in vocabulary."""
        queries = [
            "trường học là gì?",
            "trường học là gì",
            "trường học có nghĩa là gì?",
            "nghĩa của từ trường học là gì?",
        ]
        for q in queries:
            with self.subTest(query=q):
                tracker = TopicTracker(records=self.records)
                resp = self.engine.ask(q, tracker=tracker)
                self.assertEqual(resp.word, "school")
                self.assertEqual(resp.intent, "TRANSLATE_VIE_TO_ENG")
                self.assertEqual(resp.mode, "DIRECT_MATCH")
                self.assertEqual(tracker.active_word, "school")

    def test_11_school_la_gi_english_regression(self):
        """Test English word query 'school là gì?' is still handled as English lookup."""
        from fastapi.testclient import TestClient
        from vocab_backend.api_server import app

        tracker = TopicTracker(records=self.records)
        resp = self.engine.ask("school là gì?", tracker=tracker)
        self.assertEqual(resp.word, "school")
        self.assertEqual(resp.intent, "DEFINE_VOCAB")
        self.assertEqual(resp.mode, "DIRECT_MATCH")
        self.assertEqual(tracker.active_word, "school")

        # Test API response prefix
        res = self.client.post("/api/chat", headers=self.auth_headers, json={"query": "school là gì?"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("word"), "school")
        self.assertTrue(data.get("reply", "").startswith("Từ bạn tìm kiếm: school"))
        self.assertEqual(data.get("meta", {}).get("intent"), "DEFINE_VOCAB")

    def test_12_out_of_scope_vietnamese_concept(self):
        """Test unsupported Vietnamese concepts return out of scope without guessing."""
        unsupported = [
            "thuyết tương đối là gì?",
            "con kỳ lân là gì?",
        ]
        for q in unsupported:
            with self.subTest(query=q):
                tracker = TopicTracker(records=self.records)
                resp = self.engine.ask(q, tracker=tracker)
                self.assertEqual(resp.mode, "NO_MATCH")
                self.assertEqual(resp.intent, "OUT_OF_SCOPE")
                self.assertIn(settings.OUT_OF_SCOPE_RESPONSE, resp.answer)
                self.assertIsNone(tracker.active_word)

    def test_13_api_chat_stream_truong_hoc_la_gi(self):
        """Test POST /api/chat/stream for 'trường học là gì?' streams matching English word and card."""
        res = self.client.post("/api/chat/stream", headers=self.auth_headers, json={"query": "trường học là gì?"})
        self.assertEqual(res.status_code, 200)
        text = res.text
        self.assertIn("Từ tiếng Anh phù hợp: school", text)
        self.assertIn('"word": "school"', text)
        self.assertIn("data: [DONE]", text)

    def test_14_qua_tao_translation(self):
        """Test 'quả táo', 'quả táo là gì?', 'quả táo tiếng anh là gì?' returns 'apple'."""
        queries = ["quả táo", "quả táo là gì?", "quả táo tiếng anh là gì?"]
        for q in queries:
            with self.subTest(query=q):
                tracker = TopicTracker(records=self.records)
                resp = self.engine.ask(q, tracker=tracker)
                self.assertEqual(resp.word, "apple")
                self.assertEqual(resp.intent, "TRANSLATE_VIE_TO_ENG")
                self.assertEqual(resp.mode, "DIRECT_MATCH")
                self.assertEqual(tracker.active_word, "apple")

    def test_15_qua_tao_api_and_card(self):
        """Test POST /api/chat and POST /api/chat/stream returns 'apple' in structured_card."""
        # 1. Test POST /api/chat
        res = self.client.post("/api/chat", headers=self.auth_headers, json={"query": "quả táo"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("word"), "apple")
        self.assertEqual(data.get("structured_card", {}).get("word"), "apple")
        self.assertTrue(data.get("reply", "").startswith("Từ tiếng Anh phù hợp: apple"))

        # 2. Test POST /api/chat/stream
        res_stream = self.client.post("/api/chat/stream", headers=self.auth_headers, json={"query": "quả táo"})
        self.assertEqual(res_stream.status_code, 200)
        text = res_stream.text
        self.assertIn("Từ tiếng Anh phù hợp: apple", text)
        self.assertIn('"word": "apple"', text)
        self.assertIn("data: [DONE]", text)

    def test_16_can_phong_co_nghia_la_gi_variations(self):
        """Test 'căn phòng trong tiếng Anh có nghĩa là gì ?' and variations return 'apartment'."""
        queries = [
            "căn phòng trong tiếng Anh có nghĩa là gì ?",
            "căn phòng trong tiếng Anh nghĩa là gì ?",
            "căn phòng có nghĩa là gì trong tiếng Anh ?",
            "trong tiếng Anh căn phòng có nghĩa là gì ?",
            "từ căn phòng trong tiếng Anh có nghĩa là gì ?",
            "căn phòng tiếng Anh là gì ?",
            "căn phòng",
        ]
        for q in queries:
            with self.subTest(query=q):
                tracker = TopicTracker(records=self.records)
                resp = self.engine.ask(q, tracker=tracker)
                self.assertEqual(resp.word, "apartment")
                self.assertEqual(resp.intent, "TRANSLATE_VIE_TO_ENG")
                self.assertEqual(resp.mode, "DIRECT_MATCH")
                self.assertEqual(tracker.active_word, "apartment")

    def test_17_can_phong_api_and_card(self):
        """Test API endpoints for 'căn phòng trong tiếng Anh có nghĩa là gì ?'."""
        # 1. Test POST /api/chat
        res = self.client.post(
            "/api/chat",
            headers=self.auth_headers,
            json={"query": "căn phòng trong tiếng Anh có nghĩa là gì ?"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("word"), "apartment")
        self.assertEqual(data.get("structured_card", {}).get("word"), "apartment")
        self.assertTrue(data.get("reply", "").startswith("Từ tiếng Anh phù hợp: apartment"))

        # 2. Test POST /api/chat/stream
        res_stream = self.client.post(
            "/api/chat/stream",
            headers=self.auth_headers,
            json={"query": "căn phòng trong tiếng Anh có nghĩa là gì ?"},
        )
        self.assertEqual(res_stream.status_code, 200)
        text = res_stream.text
        self.assertIn("Từ tiếng Anh phù hợp: apartment", text)
        self.assertIn('"word": "apartment"', text)
        self.assertIn("data: [DONE]", text)


if __name__ == "__main__":
    unittest.main()
