"""Bộ kiểm thử động theo tiêu chí Rubric bài tập lớn Chatbox 2.0.

Thay vì ghi cứng danh sách từ vựng và kết quả giả lập, bộ kiểm thử này:
1. Lấy mẫu ngẫu nhiên (hoặc theo RUBRIC_TEST_SEED) trực tiếp từ CSDL QARecord thực tế.
2. Trích xuất đáp án đối chiếu (ground-truth: từ vựng, cấp độ, IPA, nghĩa tiếng Việt, câu ví dụ) từ chính bản ghi gốc.
3. Kiểm định cả 5 nhóm Rubric (5 In-scope, 3 Paraphrased, 3 Multi-turn, 2 Out-of-scope, 2 Ambiguous) + đánh giá mở rộng ngẫu nhiên (DYN-01, DYN-02).
4. Phát hiện trung thực trạng thái PASS / FAIL / BLOCKED (không đánh dấu PASS nếu Ollama offline hoặc sai nghĩa) và xuất báo cáo thực tế tới docs/CHATBOT_TEST_REPORT.md.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Khóa chế độ offline
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.chat.engine import CLARIFICATION_MESSAGE, ChatEngine
from src.core.models import ChatResponse, QARecord
from src.data.loader import QALoader

logger = logging.getLogger("tests.test_chatbot_rubric")
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "rubric_test_cases.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "CHATBOT_TEST_REPORT.md"

_POS_PREFIXES = (
    "từ bạn tìm kiếm:", "từ tiếng anh phù hợp:", "trình độ:", "phát âm:",
    "danh từ", "động từ", "tính từ", "trạng từ", "giới từ", "liên từ",
    "thán từ", "mạo từ", "đại từ", "noun", "verb", "adjective", "adverb",
)


def _extract_ground_truth(record: QARecord) -> Dict[str, Any]:
    """Trích xuất ground-truth (IPA, nghĩa tiếng Việt, câu ví dụ) từ bản ghi QARecord thực tế."""
    answer = getattr(record, "answer", "") or ""
    lines = [l.strip() for l in answer.splitlines() if l.strip()]

    ipa = ""
    meanings: List[str] = []
    examples: List[str] = []

    for line in lines:
        low = line.lower()
        if low.startswith("phát âm:"):
            ipa = line.split(":", 1)[1].strip()
            continue
        if line.startswith("•"):
            ex = line.lstrip("• ").strip()
            if ex:
                examples.append(ex)
            continue
        if any(low.startswith(p) for p in _POS_PREFIXES):
            continue
        # Dòng định nghĩa tiếng Việt
        no_parens = re.sub(r"\(.*?\)", "", line)
        for part in re.split(r"[,;/]", no_parens):
            clean_part = re.sub(r"^\d+[\.\)]\s*", "", part).strip("* ").strip().lower()
            if len(clean_part) >= 2 and not clean_part.startswith(("ví dụ", "example")):
                meanings.append(clean_part)

    return {
        "word": (record.word or "").strip().lower(),
        "level": (getattr(record, "level", "") or "A1").strip().upper(),
        "ipa": ipa,
        "meanings": meanings,
        "examples": examples,
    }


def _is_ollama_error_response(answer: str) -> bool:
    """Phát hiện câu trả lời lỗi kết nối Ollama (không được phép tính là PASS)."""
    low = (answer or "").lower()
    return (
        "lỗi kết nối: dịch vụ ollama" in low
        or settings.OLLAMA_OFFLINE_RESPONSE.lower() in low
        or "ollama chưa được khởi động" in low
    )


class TestChatbotRubricSuite(unittest.TestCase):
    """Lớp kiểm thử động các tiêu chí Rubric Chatbox 2.0 dựa trên dữ liệu KB thực tế."""

    @classmethod
    def setUpClass(cls):
        loader = QALoader()
        cls.records = loader.get_or_create_records()
        if not cls.records:
            raise RuntimeError(
                "CSDL rỗng! Hãy nạp dữ liệu từ điển (qa_records.jsonl) trước khi chạy test."
            )

        seed_env = os.getenv("RUBRIC_TEST_SEED")
        cls.seed = int(seed_env) if (seed_env and seed_env.isdigit()) else int(time.time())
        cls.rng = random.Random(cls.seed)

        # Lọc danh sách bản ghi tiếng Anh hợp lệ có đầy đủ nghĩa & ví dụ
        cls.vocab_records: List[QARecord] = []
        for r in cls.records:
            w = (getattr(r, "word", "") or "").strip()
            if not w or w.lower() == "list" or not re.fullmatch(r"[a-zA-Z\-]{2,}", w):
                continue
            gt = _extract_ground_truth(r)
            if gt["meanings"] and gt["examples"]:
                cls.vocab_records.append(r)

        if len(cls.vocab_records) < 8:
            raise RuntimeError("Cần ít nhất 8 bản ghi từ vựng đầy đủ nghĩa & ví dụ để chạy kiểm thử động.")

        # Xây dựng chỉ mục nghĩa tiếng Việt đơn trị (1 nghĩa -> 1 từ tiếng Anh duy nhất)
        vie_to_records: Dict[str, List[QARecord]] = defaultdict(list)
        for r in cls.vocab_records:
            gt = _extract_ground_truth(r)
            for m in gt["meanings"]:
                if 2 <= len(m.split()) <= 4 and re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", m):
                    vie_to_records[m].append(r)

        cls.unique_vie_pairs: List[Tuple[str, QARecord]] = [
            (phrase, recs[0])
            for phrase, recs in vie_to_records.items()
            if len({rec.word.strip().lower() for rec in recs}) == 1
        ]

        cls.available_levels = sorted({
            (getattr(r, "level", "") or "").strip().upper()
            for r in cls.vocab_records
            if getattr(r, "level", None)
        })

        # Chọn tập mẫu ngẫu nhiên không trùng lặp cho các ca kiểm thử
        pool = list(cls.vocab_records)
        cls.rng.shuffle(pool)
        cls.sampled_pool = pool

        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            cls.fixture_data = json.load(f)

        cls.engine = ChatEngine(records=cls.records)
        cls.engine.warm_up()
        cls.ollama_ready = cls.engine.llm_client.is_service_ready()
        cls.test_results: List[Dict[str, Any]] = []

    def setUp(self):
        self.engine.tracker.clear()

    @classmethod
    def tearDownClass(cls):
        cls._export_markdown_report()

    @classmethod
    def _pick_record(cls, index: int, require_ipa: bool = False) -> QARecord:
        if require_ipa:
            ipa_recs = [r for r in cls.sampled_pool if _extract_ground_truth(r)["ipa"]]
            if ipa_recs:
                return ipa_recs[index % len(ipa_recs)]
        return cls.sampled_pool[index % len(cls.sampled_pool)]

    @classmethod
    def _export_markdown_report(cls):
        """Tổng hợp báo cáo Markdown trung thực 100% từ kết quả thực thi thực tế."""
        total = len(cls.test_results)
        passed = sum(1 for r in cls.test_results if r["status"] == "PASS")
        failed = sum(1 for r in cls.test_results if r["status"] == "FAIL")
        blocked = sum(1 for r in cls.test_results if r["status"] == "BLOCKED")
        pass_rate = (passed / total * 100.0) if total > 0 else 0.0

        by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in cls.test_results:
            by_cat[r["category"]].append(r)

        md_lines = [
            "# BÁO CÁO KẾT QUẢ KIỂM THỬ ĐỘNG HỘI THOẠI THEO RUBRIC",
            "## DỰ ÁN: CHATBOX 2.0 — LOCAL VOCABULARY ASSISTANT",
            "",
            f"> **Ngày thực thi:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **Môi trường thực thi:** Python {sys.version.split()[0]} | Seed lấy mẫu: `{cls.seed}` | Ollama Online: `{cls.ollama_ready}`",
            f"> **Quy mô KB thực tế:** `{len(cls.records)}` bản ghi (`{', '.join(cls.available_levels)}`)",
            f"> **Tệp đặc tả mẫu:** `tests/fixtures/rubric_test_cases.json`",
            "",
            "---",
            "",
            "## 1. TỔNG HỢP KẾT QUẢ ĐÁNH GIÁ THỰC TẾ (EXECUTIVE SUMMARY)",
            "",
            "| Chỉ số đánh giá | Giá trị thực tế | Tỷ lệ |",
            "| :--- | :---: | :---: |",
            f"| **Tổng số ca kiểm thử đã chạy** | **{total}** | 100% |",
            f"| **Số ca ĐẠT (PASS)** | **{passed}** | **{pass_rate:.1f}%** |",
            f"| **Số ca THẤT BẠI (FAIL)** | **{failed}** | {(failed / total * 100.0 if total else 0.0):.1f}% |",
            f"| **Số ca BỊ CHẶN (BLOCKED - Ollama offline)** | **{blocked}** | {(blocked / total * 100.0 if total else 0.0):.1f}% |",
            "",
            "### Phân bổ kết quả thực tế theo từng nhóm Rubric:",
        ]

        cat_labels = {
            "IN_SCOPE": "Trong phạm vi (In-scope)",
            "PARAPHRASED": "Diễn đạt khác nhau (Paraphrased)",
            "MULTI_TURN": "Hội thoại nhiều lượt (Multi-turn Context)",
            "OUT_OF_SCOPE": "Ngoài phạm vi (Out-of-scope)",
            "AMBIGUOUS": "Thiếu thông tin / Mơ hồ (Ambiguous)",
            "DYNAMIC_EVAL": "Đánh giá mở rộng ngẫu nhiên (Dynamic Coverage)",
        }
        for cat_key, cat_title in cat_labels.items():
            items = by_cat.get(cat_key, [])
            c_pass = sum(1 for i in items if i["status"] == "PASS")
            c_fail = sum(1 for i in items if i["status"] == "FAIL")
            c_blk = sum(1 for i in items if i["status"] == "BLOCKED")
            c_tot = len(items)
            c_pct = (c_pass / c_tot * 100.0) if c_tot else 0.0
            md_lines.append(
                f"- **{cat_title}:** {c_pass}/{c_tot} PASS ({c_pct:.1f}%), {c_fail} FAIL, {c_blk} BLOCKED"
            )

        md_lines.extend([
            "",
            "---",
            "",
            "## 2. BẢNG CHI TIẾT KẾT QUẢ TỪNG CA KIỂM THỬ",
            "",
            "| Mã ca | Nhóm kiểm thử | Câu hỏi kiểm thử (Dynamic Input) | Chế độ (Mode) | Điểm RRF | Độ trễ | Kết quả | Ghi chú & Bằng chứng thực tế |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
        ])

        for r in cls.test_results:
            if r["status"] == "PASS":
                badge = "✅ **PASS**"
            elif r["status"] == "BLOCKED":
                badge = "⚠️ **BLOCKED**"
            else:
                badge = "❌ **FAIL**"
            note = (r.get("evidence") or "").replace("\n", " ").replace("|", "/")
            if len(note) > 110:
                note = note[:107] + "..."
            inp = (r.get("input") or "").replace("\n", " ").replace("|", "/")
            md_lines.append(
                f"| **{r['id']}** | {r['category']} | `{inp}` | `{r['mode']}` | {r['rrf_score']:.4f} | {r['latency_ms']:.1f}ms | {badge} | {note} |"
            )

        md_lines.extend([
            "",
            "---",
            "",
            "## 3. KẾT LUẬN KIỂM ĐỊNH",
            (
                f"- Thực thi tự động bằng dữ liệu lấy mẫu động từ `{len(cls.records)}` bản ghi trong KB (Seed `{cls.seed}`)."
            ),
            (
                f"- Kết quả thực tế: **{passed}/{total} PASS** ({pass_rate:.1f}%), **{failed} FAIL**, **{blocked} BLOCKED**."
            ),
        ])

        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        logger.info("Đã tạo báo cáo kiểm thử rubric động tại: %s", REPORT_PATH)

    def _evaluate_and_record(
        self,
        *,
        case_id: str,
        category: str,
        name: str,
        user_input: str,
        resp: ChatResponse,
        elapsed_ms: float,
        expected_modes: List[str],
        expected_word: Optional[str] = None,
        expected_any_substrings: Optional[List[str]] = None,
        expected_all_substrings: Optional[List[str]] = None,
        extra_checks: Optional[List[Tuple[bool, str]]] = None,
    ) -> None:
        """Đánh giá trung thực phản hồi thực tế và ghi vào test_results."""
        if _is_ollama_error_response(resp.answer):
            self.test_results.append({
                "id": case_id,
                "category": category,
                "name": name,
                "input": user_input,
                "mode": resp.mode,
                "rrf_score": resp.rrf_score,
                "latency_ms": round(elapsed_ms, 2),
                "status": "BLOCKED",
                "evidence": "Ollama chưa sẵn sàng nên RAG_GENERATION bị chặn (không đánh dấu PASS).",
            })
            self.skipTest(f"[{case_id}] Bị chặn do Ollama đang offline trong môi trường test.")

        failure_reasons: List[str] = []
        ans_lower = (resp.answer or "").lower()

        if resp.mode not in expected_modes:
            failure_reasons.append(f"Kỳ vọng mode {expected_modes}, nhận '{resp.mode}'")

        if expected_word:
            actual_word = (resp.word or "").strip().lower()
            if actual_word and actual_word != expected_word.lower():
                failure_reasons.append(f"Kỳ vọng word='{expected_word}', nhận '{actual_word}'")
            if expected_word.lower() not in ans_lower:
                failure_reasons.append(f"Phản hồi không chứa từ mục tiêu '{expected_word}'")

        if expected_any_substrings:
            if not any(s.lower() in ans_lower for s in expected_any_substrings if s):
                failure_reasons.append(f"Thiếu nội dung đối chiếu ground-truth: {expected_any_substrings[:4]}")

        if expected_all_substrings:
            missing = [s for s in expected_all_substrings if s and s.lower() not in ans_lower]
            if missing:
                failure_reasons.append(f"Thiếu từ khóa bắt buộc: {missing}")

        for ok_cond, err_msg in (extra_checks or []):
            if not ok_cond:
                failure_reasons.append(err_msg)

        status = "PASS" if not failure_reasons else "FAIL"
        evidence = resp.answer[:115] if status == "PASS" else "; ".join(failure_reasons)

        self.test_results.append({
            "id": case_id,
            "category": category,
            "name": name,
            "input": user_input,
            "mode": resp.mode,
            "rrf_score": resp.rrf_score,
            "latency_ms": round(elapsed_ms, 2),
            "status": status,
            "evidence": evidence,
        })

        self.assertFalse(
            failure_reasons,
            f"[{case_id}] Thất bại: {'; '.join(failure_reasons)} | Phản hồi: {resp.answer[:250]}",
        )

    # ==========================================================================
    # NHÓM 1: TRONG PHẠM VI (IN-SCOPE QUERIES — 5 CA ĐỘNG)
    # ==========================================================================

    def test_VOC_01_definition(self):
        """VOC-01: Tra cứu định nghĩa của một từ ngẫu nhiên trong KB."""
        rec = self._pick_record(0)
        gt = _extract_ground_truth(rec)
        query = f"{gt['word']} nghĩa là gì?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="VOC-01",
            category="IN_SCOPE",
            name="Tra cứu định nghĩa động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=gt["meanings"],
        )

    def test_VOC_02_example(self):
        """VOC-02: Tra cứu câu ví dụ của một từ ngẫu nhiên trong KB."""
        rec = self._pick_record(1)
        gt = _extract_ground_truth(rec)
        query = f"Cho tôi câu ví dụ của từ {gt['word']} này."
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="VOC-02",
            category="IN_SCOPE",
            name="Tra cứu câu ví dụ động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=[ex[:25] for ex in gt["examples"]] + [gt["word"]],
        )

    def test_VOC_03_level_list(self):
        """VOC-03: Tra cứu danh sách từ theo một cấp độ CEFR có thực trong KB."""
        chosen_level = self.rng.choice(self.available_levels)
        query = f"Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ {chosen_level}"
        level_words = [
            r.word.strip().lower()
            for r in self.vocab_records
            if (getattr(r, "level", "") or "").strip().upper() == chosen_level
        ]
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="VOC-03",
            category="IN_SCOPE",
            name="Danh sách từ theo cấp độ CEFR động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_all_substrings=[chosen_level],
            expected_any_substrings=level_words[:30],
        )

    def test_VOC_04_vietnamese_to_english(self):
        """VOC-04: Dịch nghĩa tiếng Việt thực tế sang từ tiếng Anh tương ứng."""
        if not self.unique_vie_pairs:
            self.skipTest("Không tìm thấy cặp nghĩa tiếng Việt đơn trị trong KB hiện tại.")
        vie_phrase, target_rec = self.rng.choice(self.unique_vie_pairs)
        target_word = target_rec.word.strip().lower()
        query = f"từ nào có nghĩa là {vie_phrase}?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="VOC-04",
            category="IN_SCOPE",
            name="Dịch Việt -> Anh động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=target_word,
            extra_checks=[(resp.intent == "TRANSLATE_VIE_TO_ENG", f"Kỳ vọng intent TRANSLATE_VIE_TO_ENG, nhận {resp.intent}")],
        )

    def test_VOC_05_pronunciation_part_of_speech(self):
        """VOC-05: Tra cứu phát âm và từ loại của từ ngẫu nhiên trong KB."""
        rec = self._pick_record(2, require_ipa=True)
        gt = _extract_ground_truth(rec)
        query = f"phát âm và từ loại của từ {gt['word']} là gì?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        expected_ipa_or_pos = [gt["ipa"]] if gt["ipa"] else ["danh từ", "động từ", "tính từ", "trạng từ"]
        self._evaluate_and_record(
            case_id="VOC-05",
            category="IN_SCOPE",
            name="Tra cứu phát âm & từ loại động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=expected_ipa_or_pos,
        )

    # ==========================================================================
    # NHÓM 2: DIỄN ĐẠT KHÁC NHAU (PARAPHRASED QUERIES — 3 CA ĐỘNG)
    # ==========================================================================

    def test_PAR_01_polite_request(self):
        """PAR-01: Biến thể lời đề nghị lịch sự trên từ ngẫu nhiên trong KB."""
        rec = self._pick_record(3)
        gt = _extract_ground_truth(rec)
        query = f"bạn có thể giải thích ý nghĩa của từ {gt['word']} được không?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="PAR-01",
            category="PARAPHRASED",
            name="Diễn đạt lịch sự động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=gt["meanings"],
        )

    def test_PAR_02_conversational_filler(self):
        """PAR-02: Biến thể thân mật có từ xưng hô filler trên từ ngẫu nhiên."""
        rec = self._pick_record(4)
        gt = _extract_ground_truth(rec)
        query = f"nghĩa của từ {gt['word']} là gì vậy chatbot?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="PAR-02",
            category="PARAPHRASED",
            name="Diễn đạt thân mật kèm filler động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=gt["meanings"],
        )

    def test_PAR_03_english_cross_lingual(self):
        """PAR-03: Biến thể câu hỏi tiếng Anh (Cross-lingual) trên từ ngẫu nhiên."""
        rec = self._pick_record(5)
        gt = _extract_ground_truth(rec)
        query = f"What does {gt['word']} mean in Vietnamese?"
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="PAR-03",
            category="PARAPHRASED",
            name="Diễn đạt tiếng Anh động",
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=gt["word"],
            expected_any_substrings=gt["meanings"],
        )

    # ==========================================================================
    # NHÓM 3: HỘI THOẠI NHIỀU LƯỢT (MULTI-TURN DIALOG — 3 CA ĐỘNG)
    # ==========================================================================

    def test_CTX_01_multi_turn_referential(self):
        """CTX-01: Hội thoại 2 lượt kế thừa thực thể động qua đại từ 'từ này'."""
        rec = self._pick_record(6)
        gt = _extract_ground_truth(rec)
        w = gt["word"]
        q1 = f"từ {w} nghĩa là gì?"
        q2 = "cho tôi câu ví dụ của từ này"

        self.engine.tracker.clear()
        resp1 = self.engine.ask(q1)
        self.assertIn(resp1.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(self.engine.tracker.active_word, w)

        t0 = time.perf_counter()
        resp2 = self.engine.ask(q2)
        self._evaluate_and_record(
            case_id="CTX-01",
            category="MULTI_TURN",
            name="Kế thừa đại từ 'từ này' động",
            user_input=f"L1: {q1} -> L2: {q2}",
            resp=resp2,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=w,
            extra_checks=[(self.engine.tracker.active_word == w, f"active_word phải là '{w}', nhận '{self.engine.tracker.active_word}'")],
        )

    def test_CTX_02_multi_turn_pronoun_level(self):
        """CTX-02: Hội thoại 2 lượt tham chiếu đại từ 'nó' hỏi đúng cấp độ CEFR của từ."""
        rec = self._pick_record(7)
        gt = _extract_ground_truth(rec)
        w = gt["word"]
        lvl = gt["level"]
        q1 = f"{w} nghĩa là gì?"
        q2 = "còn trình độ của nó thì sao?"

        self.engine.tracker.clear()
        resp1 = self.engine.ask(q1)
        self.assertIn(resp1.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(self.engine.tracker.active_word, w)

        t0 = time.perf_counter()
        resp2 = self.engine.ask(q2)
        self._evaluate_and_record(
            case_id="CTX-02",
            category="MULTI_TURN",
            name="Kế thừa đại từ 'nó' hỏi cấp độ động",
            user_input=f"L1: {q1} -> L2: {q2}",
            resp=resp2,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=w,
            expected_all_substrings=[lvl],
            extra_checks=[(self.engine.tracker.active_word == w, f"active_word phải là '{w}', nhận '{self.engine.tracker.active_word}'")],
        )

    def test_CTX_03_three_turn_continuity(self):
        """CTX-03: Hội thoại liên tiếp 3 lượt duy trì chủ đề trên từ ngẫu nhiên trong KB."""
        rec = self._pick_record(8, require_ipa=True)
        gt = _extract_ground_truth(rec)
        w = gt["word"]
        q1 = f"{w} nghĩa là gì?"
        q2 = "còn ví dụ?"
        q3 = "thế còn phát âm của từ đó?"

        self.engine.tracker.clear()
        resp1 = self.engine.ask(q1)
        self.assertIn(resp1.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(self.engine.tracker.active_word, w)

        resp2 = self.engine.ask(q2)
        if not _is_ollama_error_response(resp2.answer):
            self.assertIn(resp2.mode, ["DIRECT_MATCH", "RAG_GENERATION"])
        self.assertEqual(self.engine.tracker.active_word, w)

        t0 = time.perf_counter()
        resp3 = self.engine.ask(q3)
        self._evaluate_and_record(
            case_id="CTX-03",
            category="MULTI_TURN",
            name="Chuỗi hội thoại 3 lượt động",
            user_input=f"L1: {q1} -> L2: {q2} -> L3: {q3}",
            resp=resp3,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=["DIRECT_MATCH", "RAG_GENERATION"],
            expected_word=w,
            expected_any_substrings=[gt["ipa"]] if gt["ipa"] else None,
            extra_checks=[(self.engine.tracker.active_word == w, f"Mất ngữ cảnh active_word='{w}' ở lượt 3")],
        )

    # ==========================================================================
    # NHÓM 4: NGOÀI PHẠM VI (OUT-OF-SCOPE REJECTION — 2 CA ĐỘNG)
    # ==========================================================================

    def test_OOS_01_general_knowledge(self):
        """OOS-01: Chọn ngẫu nhiên câu hỏi kiến thức ngoài phạm vi từ điển."""
        oos_spec = next(c for c in self.fixture_data["categories"]["OUT_OF_SCOPE"]["cases"] if c["id"] == "OOS-01")
        query = self.rng.choice(oos_spec["candidate_queries"])
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="OOS-01",
            category="OUT_OF_SCOPE",
            name=oos_spec["name"],
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=oos_spec["expected_mode"],
            expected_any_substrings=["ngoài phạm vi"],
        )

    def test_OOS_02_realtime_or_absent_topic(self):
        """OOS-02: Chọn ngẫu nhiên câu hỏi thời sự/thời tiết/tài chính ngoài phạm vi."""
        oos_spec = next(c for c in self.fixture_data["categories"]["OUT_OF_SCOPE"]["cases"] if c["id"] == "OOS-02")
        query = self.rng.choice(oos_spec["candidate_queries"])
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="OOS-02",
            category="OUT_OF_SCOPE",
            name=oos_spec["name"],
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=oos_spec["expected_mode"],
            expected_any_substrings=["ngoài phạm vi"],
        )

    # ==========================================================================
    # NHÓM 5: THIẾU THÔNG TIN / MƠ HỒ (AMBIGUOUS — 2 CA)
    # ==========================================================================

    def test_AMB_01_unanchored_meaning(self):
        """AMB-01: Hỏi nghĩa bằng đại từ 'từ này' khi chưa có ngữ cảnh."""
        amb_spec = next(c for c in self.fixture_data["categories"]["AMBIGUOUS"]["cases"] if c["id"] == "AMB-01")
        query = amb_spec["input"]
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="AMB-01",
            category="AMBIGUOUS",
            name=amb_spec["name"],
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=amb_spec["expected_mode"],
            expected_any_substrings=[CLARIFICATION_MESSAGE],
        )

    def test_AMB_02_unanchored_example(self):
        """AMB-02: Hỏi ví dụ bằng đại từ 'từ đó' khi chưa có ngữ cảnh."""
        amb_spec = next(c for c in self.fixture_data["categories"]["AMBIGUOUS"]["cases"] if c["id"] == "AMB-02")
        query = amb_spec["input"]
        t0 = time.perf_counter()
        resp = self.engine.ask(query)
        self._evaluate_and_record(
            case_id="AMB-02",
            category="AMBIGUOUS",
            name=amb_spec["name"],
            user_input=query,
            resp=resp,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            expected_modes=amb_spec["expected_mode"],
            expected_any_substrings=[CLARIFICATION_MESSAGE],
        )

    # ==========================================================================
    # NHÓM 6: ĐÁNH GIÁ MỞ RỘNG ĐỘNG TRÊN TẬP DỮ LIỆU THỰC TẾ
    # ==========================================================================

    def test_DYN_01_random_sampling_ground_truth_coverage(self):
        """DYN-01: Lấy mẫu ngẫu nhiên nhiều từ thực tế từ KB và đối chiếu nghĩa, cấp độ, IPA gốc."""
        sample_recs = self.rng.sample(self.vocab_records, min(6, len(self.vocab_records)))
        passed_samples = 0
        details = []
        t0 = time.perf_counter()

        for rec in sample_recs:
            gt = _extract_ground_truth(rec)
            w = gt["word"]
            self.engine.tracker.clear()
            resp = self.engine.ask(f"{w} nghĩa là gì?")
            ans_low = (resp.answer or "").lower()

            ok = (
                not _is_ollama_error_response(resp.answer)
                and resp.mode in ("DIRECT_MATCH", "RAG_GENERATION")
                and (not resp.word or resp.word.lower() == w)
                and w in ans_low
                and gt["level"].lower() in ans_low
                and any(m in ans_low for m in gt["meanings"])
            )
            if ok:
                passed_samples += 1
                details.append(f"{w}:PASS")
            else:
                details.append(f"{w}:FAIL({resp.mode})")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        pass_rate = passed_samples / len(sample_recs)
        status = "PASS" if pass_rate >= 0.8 else "FAIL"
        self.test_results.append({
            "id": "DYN-01",
            "category": "DYNAMIC_EVAL",
            "name": "Đối chiếu ground-truth ngẫu nhiên trên KB thực tế",
            "input": ", ".join(_extract_ground_truth(r)["word"] for r in sample_recs),
            "mode": "DYNAMIC",
            "rrf_score": 0.0,
            "latency_ms": round(elapsed_ms, 2),
            "status": status,
            "evidence": f"{passed_samples}/{len(sample_recs)} ({pass_rate * 100:.0f}%): {', '.join(details)}",
        })
        self.assertGreaterEqual(pass_rate, 0.8, f"Độ phủ ground-truth động chưa đạt >=80%: {details}")

    def test_DYN_02_absent_words_must_not_hallucinate(self):
        """DYN-02: Sinh ngẫu nhiên các từ không tồn tại trong KB để kiểm chứng hệ thống từ chối an toàn."""
        known_words = set(self.engine.retriever.english_vocab_words)
        fake_words: List[str] = []
        while len(fake_words) < 3:
            candidate = "qx" + "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=7))
            if candidate not in known_words:
                fake_words.append(candidate)

        passed = 0
        t0 = time.perf_counter()
        for fw in fake_words:
            self.engine.tracker.clear()
            resp = self.engine.ask(f"{fw} nghĩa là gì?")
            if resp.mode == "NO_MATCH" and "ngoài phạm vi" in (resp.answer or "").lower():
                passed += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        ok = passed == len(fake_words)
        self.test_results.append({
            "id": "DYN-02",
            "category": "DYNAMIC_EVAL",
            "name": "Từ chối từ ngoài KB không hallucinate",
            "input": ", ".join(fake_words),
            "mode": "NO_MATCH",
            "rrf_score": 0.0,
            "latency_ms": round(elapsed_ms, 2),
            "status": "PASS" if ok else "FAIL",
            "evidence": f"Từ chối an toàn {passed}/{len(fake_words)} từ ngoài KB.",
        })
        self.assertEqual(passed, len(fake_words), f"Chatbot không từ chối hết từ ngoài KB: {fake_words}")


if __name__ == "__main__":
    unittest.main()
