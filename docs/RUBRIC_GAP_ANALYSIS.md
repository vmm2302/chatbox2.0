# BÁO CÁO RÀ SOÁT VÀ PHÂN TÍCH KHOẢNG CÁCH THEO RUBRIC (RUBRIC GAP ANALYSIS)
## DỰ ÁN: CHATBOX 2.0 — LOCAL ENGLISH VOCABULARY ASSISTANT

> **Môn học:** Xây dựng Chatbot AI bằng LangChain hoặc Rasa  
> **Kiến trúc áp dụng:** Controlled Hybrid RAG Pipeline (100% Cục bộ / Offline-Only)  
> **Ngày rà soát:** 21/10/2026  
> **Người thực hiện:** Senior AI & Software Engineer

---

## 1. TỔNG QUAN TIÊU CHÍ RUBRIC ĐÁNH GIÁ

Rubric đánh giá bài tập lớn yêu cầu sinh viên xây dựng một hệ thống chatbot hoàn chỉnh, chạy được trong thực tế, có kiểm thử chặt chẽ và có đầy đủ tài liệu phục vụ bảo vệ. Các tiêu chí cốt lõi gồm:

| Mã | Tiêu chuẩn đánh giá | Yêu cầu cốt lõi theo Rubric |
|:---:|:---|:---|
| **A** | **Bài toán & Phạm vi** | Định rõ mục tiêu, đối tượng sử dụng, phạm vi nghiệp vụ và các chức năng chính. |
| **B** | **Thiết kế Chatbot** | Sơ đồ kiến trúc chi tiết, luồng hội thoại, giải thích vai trò của từng thành phần kỹ thuật. |
| **C** | **Chức năng Chatbot** | Tích hợp thực tế LangChain, xử lý hội thoại nhiều lượt, cơ chế bắt lỗi và giao diện trực quan. |
| **D** | **Quản lý Dữ liệu** | Nguồn dữ liệu, quy trình nạp đa định dạng, chuẩn hóa `QARecord`, cập nhật KB an toàn. |
| **E** | **Kiểm thử Chatbot** | Tối thiểu 15 ca kiểm thử hội thoại đúng cơ cấu chuẩn (5 In-scope, 3 Paraphrase, 3 Multi-turn, 2 Out-of-scope, 2 Ambiguous). |
| **F** | **Mã nguồn & Báo cáo** | Mã nguồn có cấu trúc module rõ ràng, báo cáo thống nhất, hướng dẫn cài đặt chạy tái lập 100%. |
| **G** | **Demo & Bảo vệ** | Kịch bản demo mạch lạc, hướng dẫn trình bày và bộ câu hỏi vấn đáp (Viva Q&A) tự luyện tập. |

---

## 2. HIỆN TRẠNG ĐƯỢC XÁC MINH TRONG CODEBASE VÀ PHÂN TÍCH KHOẢNG CÁCH

### Tiêu chuẩn A: Bài toán và Phạm vi (Problem & Scope)
- **Hiện trạng trong code:**
  - Chatbox 2.0 được xây dựng để tra cứu từ vựng tiếng Anh (nghĩa, từ loại, phiên âm, ví dụ, danh sách từ theo cấp độ CEFR A1–B2, dịch Việt–Anh).
  - Hoạt động 100% offline, không gọi API đám mây, bảo vệ quyền riêng tư người dùng.
- **File/Module liên quan:** `README.md`, `config/settings.py`, `src/chat/query_router.py`.
- **Thiếu sót:** Chưa có một văn bản riêng biệt tổng kết rõ ranh giới bài toán và đối tượng sử dụng để sinh viên đọc nhanh khi chuẩn bị slide bảo vệ.
- **Mức độ ưu tiên:** **P2**
- **Giải pháp:** Bổ sung phần mô tả bài toán và phạm vi rành mạch trong `docs/RUBRIC_GAP_ANALYSIS.md` và `docs/IMPLEMENTATION_REPORT.md`.

---

### Tiêu chuẩn B: Thiết kế Chatbot (System Architecture & Design)
- **Hiện trạng trong code:**
  - Hệ thống sử dụng quy trình tuần tự chặt chẽ:
    1. `TopicTracker`: Quản lý `active_word`, phân giải đại từ (`"từ này"`, `"nó"`), bắt câu hỏi mơ hồ (`CLARIFICATION`).
    2. `QueryRouter` & `SmallTalkHandler`: Phân luồng 3 nhánh (`SMALL_TALK`, `OUT_OF_SCOPE`, `VOCAB_QUERY`) với thời gian phản hồi sub-millisecond cho câu chào hỏi.
    3. `PhoBERTIntentClassifier`: Biểu diễn vector 768 chiều qua `vinai/phobert-base-v2` và so khớp Cosine Similarity với Prototype Centroids tiếng Việt.
    4. `HybridRetriever`: Kết hợp `BM25Okapi` (từ khóa) và `BGE-M3` (semantic dense 1024 chiều trong ChromaDB).
    5. `Reciprocal Rank Fusion (RRF $k=60$)`: Hợp nhất thứ hạng Sparse + Dense.
    6. `Relevance Gate`: Phân loại `DIRECT_MATCH` (điểm cao -> phản hồi tức thì <2ms) hoặc `RAG_GENERATION` (đưa vào LLM diễn đạt).
    7. `LangChain LCEL` + `Qwen2.5:7B (Ollama)`: Diễn đạt dựa nghiêm ngặt trên context trích xuất, chống hallucination.
- **File/Module liên quan:** `src/chat/engine.py`, `src/chat/query_router.py`, `src/nlp/phobert_intent.py`, `src/retriever/hybrid_retriever.py`, `src/llm/client.py`.
- **Thiếu sót:** Sơ đồ trong `README.md` chưa thể hiện đầy đủ nhánh Query Router và cơ chế đồng bộ tài nguyên IndexAccessCoordinator (Reader-Writer Lock).
- **Mức độ ưu tiên:** **P1**
- **Giải pháp:** Cập nhật sơ đồ kiến trúc Mermaid đầy đủ trong các tài liệu báo cáo và README.

---

### Tiêu chuẩn C: Chức năng Chatbot (Core Functionality & LangChain Integration)
- **Hiện trạng trong code:**
  - Chế độ trả lời đồng bộ `ChatEngine.ask()` đã gọi `OllamaClient.generate_with_langchain(...)` sử dụng LangChain LCEL: `prompt_template | chat_ollama | StrOutputParser()`.
  - Quản lý hội thoại đa lượt duy trì lịch sử `history` và thực thể `active_word` rất tốt.
  - Giao diện Streamlit (`src/ui/app.py`) có tab Tra cứu, tab Quản lý dữ liệu và tab Chẩn đoán hệ thống kèm Provenance Inspector.
- **Thiếu sót:**
  1. *Lỗi assertion trong unit test*: Trong `tests/test_response_formatting.py`, bài test kiểm tra từ `address` assert `**1. Gửi**` nhưng trong dữ liệu Động từ của `address`, "Gửi" là nghĩa số 2 (`**2. Gửi**`).
  2. *Tính nhất quán LangChain LCEL Stream*: Phương thức `ask_stream()` trong `ChatEngine` hiện gọi `stream_chat()` trực tiếp qua HTTP requests mà chưa tận dụng LangChain LCEL `chain.stream(...)`.
- **Mức độ ưu tiên:** **P0**
- **Giải pháp:**
  - Sửa assertion đúng số thứ tự nghĩa của động từ trong `tests/test_response_formatting.py`.
  - Bổ sung hàm `generate_with_langchain_stream()` vào `OllamaClient` và tích hợp vào `ChatEngine.ask_stream()` để đảm bảo LCEL được sử dụng nhất quán cả 2 chế độ.

---

### Tiêu chuẩn D: Quản lý Dữ liệu (Data Ingestion & Knowledge Base Management)
- **Hiện trạng trong code:**
  - Hệ thống nạp hàng loạt (`BatchIngestionManager`) hỗ trợ 8 định dạng: `.pdf`, `.docx`, `.txt`, `.md`, `.xlsx`, `.csv`, `.json`, `.jsonl`.
  - Hỗ trợ cơ sở dữ liệu SQLite đa bảng (`SQLiteLoader`) với schema inspection và mapping cấu hình tự động.
  - Khử trùng lặp 2 tầng: File Hash (SHA-256) và Content Hash.
  - Cơ chế Transaction Staging & Rollback snapshot (`.bak`) bảo vệ dữ liệu khi gặp sự cố ghi đĩa hoặc lỗi vector.
- **Thiếu sót:**
  - Trong `tests/test_sqlite_loader.py` (test 11 rollback), mock `BGEChromaRetriever.upsert_records` qua đường dẫn chuỗi có thể bị bypass do binding namespace khi chạy toàn bộ test suite.
- **Mức độ ưu tiên:** **P0**
- **Giải pháp:** Chuyển sang `patch.object(BGEChromaRetriever, "upsert_records", ...)` để đảm bảo cô lập mock 100% trong mọi điều kiện chạy test.

---

### Tiêu chuẩn E: Kiểm thử Chatbot (Chatbot Rubric Testing Suite)
- **Hiện trạng trong code:**
  - Dự án có 190 tests kỹ thuật (`tests/test_*.py`), bao quát từ nạp file, sqlite, rollback, resource manager đến retriever.
  - Tuy nhiên, **chưa có bộ kiểm thử 15 ca hội thoại độc lập theo đúng quy cách Rubric bài tập lớn**.
- **Thiếu sót:**
  1. Chưa có tệp fixture lưu trữ cấu trúc 15 ca: `tests/fixtures/rubric_test_cases.json`.
  2. Chưa có test runner riêng biệt: `tests/test_chatbot_rubric.py` với mã định danh rõ ràng (`VOC-01..05`, `PAR-01..03`, `CTX-01..03`, `OOS-01..02`, `AMB-01..02`).
  3. Chưa có báo cáo kết quả kiểm thử đánh giá: `docs/CHATBOT_TEST_REPORT.md`.
- **Mức độ ưu tiên:** **P0**
- **Giải pháp:** Xây dựng đầy đủ fixture JSON, runner Python và báo cáo Markdown thu thập từ kết quả chạy thực tế trên máy.

---

### Tiêu chuẩn F: Mã nguồn & Báo cáo (Code Quality & Reporting)
- **Hiện trạng trong code:**
  - Codebase được tổ chức sạch sẽ theo từng package: `core`, `chat`, `data`, `llm`, `nlp`, `resource`, `retriever`, `ui`.
  - Có file hướng dẫn môi trường: `HUONG_DAN_CAI_DAT_MAY_MOI.md` và `README.md`.
- **Thiếu sót:**
  - Chưa có báo cáo tổng kết chi tiết `docs/IMPLEMENTATION_REPORT.md` để giảng viên tra cứu nhanh minh chứng đáp ứng rubric.
- **Mức độ ưu tiên:** **P1**
- **Giải pháp:** Biên soạn `docs/IMPLEMENTATION_REPORT.md` trình bày chi tiết mọi công việc đã thực hiện, bằng chứng mã nguồn, kết quả kiểm thử và hướng dẫn vận hành.

---

### Tiêu chuẩn G: Demo và Bảo vệ (Demo Guide & Defense Q&A)
- **Hiện trạng trong code:**
  - Giao diện Streamlit đã hỗ trợ đầy đủ các tính năng để demo trực quan.
- **Thiếu sót:**
  - Chưa có tài liệu kịch bản demo từng bước (Step-by-step Live Demo Script).
  - Chưa có cẩm nang ôn tập vấn đáp kỹ thuật (Viva Defense Q&A) giải thích sâu vì sao chọn LangChain, vai trò của PhoBERT vs Qwen, công thức RRF, cách xử lý hội thoại nhiều lượt dựa vào code.
- **Mức độ ưu tiên:** **P1**
- **Giải pháp:** Biên soạn tài liệu `docs/DEMO_AND_DEFENSE_GUIDE.md` bám sát 100% mã nguồn thực tế.

---

## 3. PHÂN LOẠI MỨC ĐỘ ƯU TIÊN VÀ LỘ TRÌNH THỰC HIỆN

### Danh mục vấn đề mức P0 (Bắt buộc sửa ngay)
1. **[P0-1]** Sửa lỗi assertion định dạng trong `tests/test_response_formatting.py` (khắc phục 1/2 failure).
2. **[P0-2]** Củng cố mock patch trong `tests/test_sqlite_loader.py` bằng `patch.object` (khắc phục 2/2 failure).
3. **[P0-3]** Bổ sung LangChain LCEL Streaming (`generate_with_langchain_stream`) vào `src/llm/client.py` và `src/chat/engine.py`.
4. **[P0-4]** Xây dựng bộ 15 ca kiểm thử hội thoại chuẩn Rubric (`tests/fixtures/rubric_test_cases.json` & `tests/test_chatbot_rubric.py`).
5. **[P0-5]** Chạy thực tế và tạo báo cáo kiểm thử hội thoại `docs/CHATBOT_TEST_REPORT.md`.

### Danh mục vấn đề mức P1 (Yêu cầu bắt buộc để đạt điểm tối đa)
1. **[P1-1]** Biên soạn cẩm nang Demo và ôn tập vấn đáp `docs/DEMO_AND_DEFENSE_GUIDE.md`.
2. **[P1-2]** Biên soạn báo cáo hoàn thiện triển khai `docs/IMPLEMENTATION_REPORT.md`.
3. **[P1-3]** Cập nhật `README.md` với các hướng dẫn chạy test và sơ đồ kiến trúc hoàn chỉnh.

### Danh mục vấn đề mức P2 (Cải thiện trải nghiệm và tài liệu)
1. **[P2-1]** Kiểm tra dọn dẹp các tệp tạm trong thư mục test và bảo đảm working tree git sạch sẽ.
2. **[P2-2]** Đồng bộ tài liệu cài đặt môi trường `HUONG_DAN_CAI_DAT_MAY_MOI.md`.

---

## 4. KẾ HOẠCH KIỂM CHỨNG SAU KHI SỬA
Sau khi hoàn tất việc chỉnh sửa và bổ sung, hệ thống sẽ được kiểm chứng qua các lệnh:
1. `python -m unittest tests.test_response_formatting` -> Đạt 100% PASS.
2. `python -m unittest tests.test_sqlite_loader` -> Đạt 100% PASS.
3. `python -m unittest tests.test_chatbot_rubric` -> Đạt 15/15 ca PASSED (100%).
4. `python -m unittest discover -s tests -p "test_*.py"` -> Đạt 100% toàn bộ test suite.
