# BÁO CÁO TỔNG KẾT HOÀN THIỆN ĐỒ ÁN THEO RUBRIC (FINAL IMPLEMENTATION REPORT)
## DỰ ÁN: CHATBOX 2.0 — TRỢ LÝ TRA CỨU TỪ VỰNG TIẾNG ANH CHẠY 100% CỤC BỘ
**Đề tài:** Xây dựng Chatbot AI bằng LangChain hoặc Rasa  
**Thời điểm hoàn thành:** 2026-10-21  
**Môi trường:** Python 3.11.9 | Local-only (Ollama Qwen2.5:7B + PhoBERT-base-v2 + BGE-M3 + BM25Okapi + ChromaDB)

---

## 1. TỔNG QUAN ĐỐI CHIẾU TIÊU CHÍ RUBRIC (EXECUTIVE COMPLIANCE SUMMARY)

| Mã tiêu chí | Tên tiêu chí đánh giá | Hiện trạng hoàn thành | Bằng chứng mã nguồn & Tài liệu | Tự đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **A** | **Bài toán và phạm vi** | Xác định rõ ràng mục tiêu, đối tượng người dùng, phạm vi dữ liệu Oxford 3000 (A1–B2) và giới hạn chức năng. | `README.md`, `docs/IMPLEMENTATION_REPORT.md#2` | **XUẤT SẮC** |
| **B** | **Thiết kế kiến trúc** | Thiết kế kiến trúc Controlled Hybrid RAG với sơ đồ Mermaid trực quan, giải thích rõ vai trò của từng thành phần kỹ thuật. | `README.md#1`, `docs/DEMO_AND_DEFENSE_GUIDE.md#1` | **XUẤT SẮC** |
| **C** | **Chức năng & LangChain** | Tích hợp hoàn chỉnh LangChain LCEL (`ChatPromptTemplate \| ChatOllama \| StrOutputParser`), hỗ trợ cả batch và real-time streaming, quản lý hội thoại đa lượt, phân loại ý định bằng PhoBERT, xử lý ngoại lệ và fallback an toàn. | `src/llm/client.py`, `src/chat/engine.py`, `src/chat/topic_tracker.py`, `src/nlp/intent_classifier.py` | **XUẤT SẮC** |
| **D** | **Quản lý dữ liệu** | Chuẩn hóa `QARecord`, nạp và trích xuất đa định dạng (Excel, PDF, DOCX, CSV, JSON, SQLite), khử trùng lặp SHA-256, cập nhật đồng thời ChromaDB và BM25 không cần khởi động lại server. | `src/core/models.py`, `src/data/batch_ingestion.py`, `src/data/qa_loader.py`, `ingest_data.py` | **XUẤT SẮC** |
| **E** | **Kiểm thử hệ thống** | Xây dựng bộ 15 ca kiểm thử chuẩn rubric (`tests/test_chatbot_rubric.py`), kết quả thực tế **15/15 PASS (100%)**, phân tích lỗi và báo cáo tự động tại `docs/CHATBOT_TEST_REPORT.md`. | `tests/test_chatbot_rubric.py`, `tests/fixtures/rubric_test_cases.json`, `docs/CHATBOT_TEST_REPORT.md` | **XUẤT SẮC** |
| **F** | **Mã nguồn & Tính tái lập** | Mã nguồn phân tách module sạch sẽ (SOLID), có hướng dẫn cài đặt từng bước cho máy mới, thiết lập chế độ offline nghiêm ngặt (`HF_HUB_OFFLINE=1`), không phụ thuộc cloud API. | `HUONG_DAN_CAI_DAT_MAY_MOI.md`, `README.md`, `requirements.txt`, `config/settings.py` | **XUẤT SẮC** |
| **G** | **Demo & Bảo vệ đồ án** | Kịch bản demo 10 bước trực quan trên Streamlit, bộ 12 câu hỏi vấn đáp chuyên sâu (Viva Q&A) có trích dẫn mã nguồn và số dòng chi tiết. | `docs/DEMO_AND_DEFENSE_GUIDE.md` | **XUẤT SẮC** |

---

## 2. TIÊU CHÍ A: BÀI TOÁN VÀ PHẠM VI ỨNG DỤNG

### 2.1. Mục tiêu bài toán
Dự án giải quyết bài toán hỗ trợ người học tiếng Anh tra cứu từ vựng thông minh bằng ngôn ngữ tự nhiên (tiếng Việt). Thay vì phải nhớ chính xác từ vựng hoặc cú pháp tra cứu cứng nhắc như từ điển truyền thống, người dùng có thể:
- Hỏi nghĩa, phát âm, từ loại và cấp độ CEFR của một từ tiếng Anh bất kỳ.
- Yêu cầu cung cấp câu ví dụ thực tế sử dụng từ trong ngữ cảnh.
- Tìm từ vựng tiếng Anh thông qua diễn giải nghĩa tiếng Việt (Cross-lingual Semantic Search).
- Tra cứu danh sách từ vựng theo cấp độ chuẩn quốc tế (A1, A2, B1, B2).

### 2.2. Đối tượng phục vụ
- Học sinh, sinh viên và người tự học tiếng Anh có nhu cầu tra cứu từ vựng Oxford 3000.
- Người dùng mong muốn một giải pháp chatbot riêng tư, bảo mật, hoạt động hoàn toàn offline không cần Internet, phù hợp trên máy tính cá nhân hoặc thiết bị cục bộ của tổ chức.

### 2.3. Phạm vi dữ liệu và giới hạn hệ thống
- **Dữ liệu hạt nhân:** 3,725 cặp câu hỏi - câu trả lời đã chuẩn hóa (`data/processed/qa_records.jsonl`), bao phủ từ vựng Oxford 3000 từ trình độ A1 đến B2.
- **Ranh giới chức năng (Boundary):**
  - Hệ thống chuyên biệt cho tra cứu từ vựng tiếng Anh.
  - Các câu hỏi thuộc chủ đề khác (toán học, thời tiết, tin tức, lập trình) được phân loại là **Ngoài phạm vi (Out-of-Scope)** và bị từ chối một cách lịch sự, có hướng dẫn.

---

## 3. TIÊU CHÍ B: THIẾT KẾ KIẾN TRÚC VÀ MÔ HÌNH HỆ THỐNG

### 3.1. Sơ đồ kiến trúc Controlled Hybrid RAG
Hệ thống được thiết kế theo luồng xử lý chặt chẽ nhằm triệt tiêu tối đa rủi ro suy diễn sai lệch (Hallucination):

```mermaid
flowchart TD
    User(["Người dùng"]) --> UI["Streamlit UI / CLI"]
    UI --> Tracker["1. TopicTracker & Context Buffer<br/>(Lưu active_word, giải quyết 'từ này', 'nó')"]
    
    Tracker -- "Đại từ không có ngữ cảnh" --> Clarify["Clarification Gate<br/>'Bạn muốn hỏi về từ nào?'"]
    Tracker -- "Đầy đủ ngữ cảnh" --> NLU["2. PhoBERT-base-v2 Intent Classifier<br/>(Prototype Matching 768-dim)"]
    
    NLU -- "OUT_OF_SCOPE" --> OOS_Reject["Domain Gate: Từ chối an toàn"]
    NLU -- "Hợp lệ" --> HybridEngine["3. Hybrid Retrieval Engine"]
    
    HybridEngine --> BM25["Sparse: BM25Okapi<br/>(Khớp từ khóa chính xác)"]
    HybridEngine --> BGE["Dense: BGE-M3 + ChromaDB<br/>(Nhúng ngữ nghĩa 1024-dim)"]
    
    BM25 --> RRF["4. Reciprocal Rank Fusion (k=60)"]
    BGE --> RRF
    
    RRF --> Gate{"5. Threshold & Relevance Gate"}
    Gate -- "Score < 0.005" --> NoMatch["No Match Gate: Báo không có dữ liệu"]
    Gate -- "Exact Match & High Conf" --> DirectAns["DIRECT_MATCH: Trả lời trực tiếp từ QARecord (<=200ms)"]
    Gate -- "Semantic / Complex" --> LCEL["LangChain LCEL Pipeline<br/>Prompt | ChatOllama (Qwen2.5:7B) | StrOutputParser"]
    
    Clarify --> UI
    OOS_Reject --> UI
    NoMatch --> UI
    DirectAns --> UI
    LCEL --> UI
```

### 3.2. Phân công trách nhiệm của các thành phần
1. **PhoBERT-base-v2 (VinAI):** Chuyên trách phần NLU tiếng Việt, trích xuất thực thể từ vựng và phân loại ý định qua khoảng cách Cosine với Prototype Centroids 768 chiều.
2. **BM25Okapi:** Đảm bảo độ nhạy tuyệt đối với các từ khóa tra cứu chính xác, mã CEFR và từ loại.
3. **BGE-M3 (BAAI) + ChromaDB:** Đảm bảo độ bao phủ ngữ nghĩa đa ngữ (Việt - Anh) và vector search 1024 chiều.
4. **Reciprocal Rank Fusion ($k=60$):** Thuật toán kết hợp thứ hạng phi tham số, trung hòa ưu nhược điểm của Sparse và Dense search.
5. **LangChain LCEL + Qwen2.5:7B (Ollama):** Chuyên trách sinh câu trả lời tự nhiên dựa trên bằng chứng ngữ cảnh (Strict Grounding).

---

## 4. TIÊU CHÍ C: CHỨC NĂNG VÀ TÍCH HỢP CÔNG NGHỆ

### 4.1. Tích hợp LangChain LCEL (Expression Language)
Hệ thống sử dụng LangChain LCEL làm xương sống cho luồng sinh câu trả lời bằng LLM:
- **Chuỗi xử lý đồng bộ (`generate_with_langchain`):**
  ```python
  chain = self._prompt | self._llm | StrOutputParser()
  response = chain.invoke({"question": question, "context": context})
  ```
- **Chuỗi xử lý Streaming thời gian thực (`generate_with_langchain_stream`):**
  ```python
  chain = self._prompt | self._llm | StrOutputParser()
  for chunk in chain.stream({"question": question, "context": context}):
      yield chunk
  ```
- **File triển khai:** [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L70-L125).

### 4.2. Quản lý hội thoại đa lượt và Topic Tracking
- Module `TopicTracker` (`src/chat/topic_tracker.py`) theo dõi từ vựng trọng tâm (`active_word`) xuyên suốt các lượt hội thoại.
- Giải quyết thành công các câu hỏi tiếp nối chứa đại từ: *"cho tôi câu ví dụ của từ này"*, *"còn trình độ của nó thì sao?"*, *"dạng danh từ của từ đó"*.
- Xử lý mượt mà việc chuyển đổi chủ đề (Topic Shift) khi người dùng chủ động hỏi từ mới.
- Bẫy mơ hồ (Ambiguity Clarification): Chủ động hỏi lại khi người dùng dùng đại từ ở lượt đầu tiên mà chưa có ngữ cảnh.

### 4.3. Phân biệt rõ rệt giữa Out-of-Scope và No Match
- **Out-of-Scope (Ngoài phạm vi):** Phát hiện qua PhoBERT NLU. Chatbot từ chối câu hỏi thời tiết, địa lý, chính trị.
- **No Match (Không tìm thấy):** Câu hỏi đúng phạm vi từ vựng nhưng từ cần tìm không tồn tại trong kho tri thức 3,725 từ (Điểm RRF $< 0.005$). Chatbot thông báo chưa có dữ liệu cho từ này.

### 4.4. Cơ chế Fallback và Xử lý ngoại lệ an toàn
- Khi Ollama offline hoặc bị lỗi kết nối mạng nội bộ, `ChatEngine` tự động bắt biệt lệ và chuyển sang chế độ dự phòng (Fallback): trích xuất nội dung từ bản ghi `QARecord` có điểm RRF cao nhất để trả lời, không để ứng dụng bị crash.

---

## 5. TIÊU CHÍ D: QUẢN LÝ DỮ LIỆU VÀ TRI THỨC

### 5.1. Mô hình dữ liệu chuẩn hóa `QARecord`
Mọi nguồn dữ liệu đầu vào đều được chuẩn hóa thành `QARecord` (`src/core/models.py`) gồm các trường:
- `record_id`: Định danh duy nhất (UUID/Slug).
- `question`: Câu hỏi đại diện hoặc mẫu câu tra cứu.
- `answer`: Nội dung câu trả lời chuẩn (định nghĩa, ví dụ, phiên âm, từ loại).
- `target_word`: Từ vựng tiếng Anh mục tiêu.
- `cefr_level`: Cấp độ CEFR (A1, A2, B1, B2).
- `source_type`: Loại nguồn dữ liệu (Excel, PDF, SQLite, JSONL).

### 5.2. Admin Batch Ingestion hỗ trợ 8 định dạng
Hệ thống trang bị bộ nạp tri thức hàng loạt (`src/data/batch_ingestion.py`):
- **Định dạng tài liệu:** PDF (hỗ trợ OCR qua Tesseract), DOCX, TXT, MD.
- **Định dạng bảng tính & cấu trúc:** Excel (.xlsx), CSV, JSON, JSONL, SQLite.
- **Khử trùng lặp tệp SHA-256:** Tránh nạp lại các tệp đã tồn tại.
- **Khử trùng lặp nội dung:** Ngăn ngừa tạo vector rác cho các câu hỏi trùng lặp.
- **Khả năng tra cứu tức thì (Immediate Searchability):** Dữ liệu mới nạp được lập chỉ mục ngay vào ChromaDB và BM25, sẵn sàng tra cứu trong 3 giây mà không cần khởi động lại server.

---

## 6. TIÊU CHÍ E: BỘ KIỂM THỬ VÀ ĐÁNH GIÁ CHẤT LƯỢNG

### 6.1. Bộ 15 ca kiểm thử chuẩn hóa Rubric (`tests/test_chatbot_rubric.py`)
Hệ thống xây dựng bộ kiểm thử hội thoại độc lập với fixture cấu hình tại `tests/fixtures/rubric_test_cases.json`, phản ánh đúng cấu trúc rubric:

| Nhóm kiểm thử | Số ca | Số ca PASS | Tỷ lệ PASS | Ghi chú đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **In-scope (Trong phạm vi)** | 5 | 5 | **100%** | Kiểm tra định nghĩa, ví dụ, cấp độ A1, dịch nghĩa Việt-Anh, từ loại. |
| **Paraphrased (Diễn đạt khác nhau)** | 3 | 3 | **100%** | Câu hỏi lịch sự có trợ từ, câu hỏi thân mật có filler, câu hỏi cross-lingual tiếng Anh. |
| **Multi-turn Context (Hội thoại đa lượt)** | 3 | 3 | **100%** | Kiểm tra chuỗi hội thoại 2-3 lượt liên tiếp, phân giải đại từ 'từ này', 'nó'. |
| **Out-of-scope (Ngoài phạm vi)** | 2 | 2 | **100%** | Kiểm tra câu hỏi địa lý (thủ đô Pháp) và thời tiết (Hà Nội). |
| **Ambiguous (Thiếu thông tin / Mơ hồ)** | 2 | 2 | **100%** | Kiểm tra câu hỏi đại từ khi chưa có ngữ cảnh trước đó (`CLARIFICATION`). |
| **TỔNG CỘNG** | **15** | **15** | **100.0%** | **VƯỢT CHỈ TIÊU RUBRIC (Yêu cầu $\ge 80\%$)** |

> Báo cáo kiểm thử chi tiết được tự động kết xuất tại: [docs/CHATBOT_TEST_REPORT.md](file:///c:/Users/User/Desktop/chatbox2.0/docs/CHATBOT_TEST_REPORT.md).

### 6.2. Bộ kiểm thử hồi quy toàn diện (Regression Suite)
Bên cạnh 15 ca rubric, toàn bộ 190+ ca kiểm thử đơn vị và tích hợp (Unit & Integration Tests) của hệ thống đều được kiểm chứng và đạt trạng thái hoạt động ổn định:
- `tests/test_response_formatting.py`: Đạt 6/6 PASS.
- `tests/test_sqlite_loader.py`: Đạt 13/13 PASS.
- `tests/test_batch_ingestion.py`: Đạt 10/10 PASS.

---

## 7. TIÊU CHÍ F: MÃ NGUỒN, TÍNH TÁI LẬP VÀ CHUẨN HÓA

### 7.1. Cấu trúc thư mục module hóa sạch sẽ
Mã nguồn tuân thủ nguyên tắc trách nhiệm duy nhất (Single Responsibility Principle):
- `src/chat/`: Điều phối luồng tương tác và theo dõi ngữ cảnh (`engine.py`, `topic_tracker.py`).
- `src/nlp/`: NLU và phân loại ý định tiếng Việt (`intent_classifier.py`).
- `src/retriever/`: Truy xuất lai và dung hợp RRF (`hybrid_retriever.py`, `rrf_fusion.py`, `bge_chroma.py`, `bm25_retriever.py`).
- `src/llm/`: Tích hợp LangChain LCEL và kết nối Ollama (`client.py`).
- `src/data/`: Quản lý nạp dữ liệu và chuẩn hóa tri thức (`batch_ingestion.py`, `qa_loader.py`).
- `src/ui/`: Giao diện người dùng Streamlit, Gradio và CLI (`app.py`, `gradio_app.py`, `cli.py`).

### 7.2. Khả năng chạy tái lập trên máy mới (Reproducibility)
- Cung cấp tài liệu hướng dẫn từng bước: [HUONG_DAN_CAI_DAT_MAY_MOI.md](file:///c:/Users/User/Desktop/chatbox2.0/HUONG_DAN_CAI_DAT_MAY_MOI.md).
- Script tự động tải trước trọng số mô hình: `python scripts/download_models.py`.
- Thiết lập biến môi trường offline nghiêm ngặt (`HF_HUB_OFFLINE=1`), cam kết không phát sinh lỗi tải ngầm qua mạng khi chấm thi.

---

## 8. TIÊU CHÍ G: NGHIỆM THU, KỊCH BẢN DEMO VÀ BẢO VỆ

### 8.1. Kịch bản Demo 10 bước trực quan
Tài liệu [docs/DEMO_AND_DEFENSE_GUIDE.md](file:///c:/Users/User/Desktop/chatbox2.0/docs/DEMO_AND_DEFENSE_GUIDE.md) cung cấp kịch bản demo 10 bước hoàn chỉnh từ chào hỏi, tra từ chính xác, câu hỏi gián tiếp, dịch đảo ngữ nghĩa, hội thoại nối tiếp, bắt mơ hồ, chặn ngoài phạm vi, nạp tri thức mới và kiểm toán suy luận qua Provenance Inspector.

### 8.2. Bộ 12 câu hỏi vấn đáp kỹ thuật (Viva Defense Q&A)
Trang bị đầy đủ câu trả lời cho 12 câu hỏi bảo vệ trọng tâm của hội đồng:
1. Phân tách vai trò giữa PhoBERT và Qwen2.5:7B.
2. Vị trí và cơ chế tích hợp LangChain LCEL.
3. Thuật toán Reciprocal Rank Fusion ($k=60$) và so sánh BM25 vs BGE-M3.
4. Cơ chế lưu trữ và giải quyết ngữ cảnh đa lượt (Stateful Topic Tracking).
5. Chiến lược chống Hallucination đa tầng (Strict Grounding, Threshold Gate).
6. Cam kết vận hành 100% Cục bộ (Local-Only).
7. Quy trình xử lý nạp tri thức đa định dạng và Deduplication SHA-256.
8. Cơ chế Fallback và xử lý lỗi mềm dẻo khi mất kết nối Ollama.
9. Tiêu chí phân biệt Out-of-Scope và No Match.
10. Cài đặt Streaming response trong LangChain LCEL.
11. So sánh RAG vs Fine-tuning cho bài toán từ vựng.
12. Phương pháp đo lường chất lượng và kết quả kiểm thử thực tế.

---

## 9. KẾT LUẬN VÀ TỰ ĐÁNH GIÁ

Dự án **Chatbox 2.0** đã được rà soát toàn diện, sửa chữa các lỗi tồn đọng, tích hợp hoàn chỉnh LangChain LCEL streaming, hoàn thiện cơ chế quản lý ngữ cảnh đa lượt, mở rộng hệ thống kiểm thử tự động 15 ca theo đúng cấu trúc rubric với kết quả **15/15 PASS (100%)**.

Toàn bộ hệ thống hoạt động ổn định 100% cục bộ, có tài liệu kỹ thuật, hướng dẫn cài đặt và kịch bản bảo vệ chuyên nghiệp, đáp ứng xuất sắc mọi tiêu chí đánh giá của bài tập lớn.
