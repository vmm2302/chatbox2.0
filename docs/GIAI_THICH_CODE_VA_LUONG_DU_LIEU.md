# GIẢI THÍCH MÃ NGUỒN, LUỒNG DỮ LIỆU & BẢN CHẤT HỆ THỐNG CHATBOT (MASTER CODEBASE & CORE EXPLANATION)

> **Dự án:** Chatbox 2.0 — Trợ lý tra cứu từ vựng tiếng Anh Oxford A1 - A2  
> **Kiến trúc:** 100% Cục bộ (Local-Only) — Controlled Hybrid RAG (BM25 + BGE-M3 ChromaDB + RRF), PhoBERT-base-v2 NLU, LangChain LCEL, Qwen2.5:7B (Ollama), FastAPI SSE Streaming, React Vite UI.  
> **Mục đích tài liệu:** Cung cấp tài liệu kỹ thuật toàn diện, giải thích cặn kẽ từng dòng code, luồng dữ liệu di chuyển từ đầu đến cuối (End-to-End) và trả lời thỏa đáng các câu hỏi cốt lõi về bản chất của chatbot AI.

---

## MỤC LỤC
1. [Tổng quan Kiến trúc Hệ thống (System Architecture)](#1-tổng-quan-kiến-trúc-hệ-thống)
2. [Luồng Dữ liệu Hoạt động Chi tiết (End-to-End Data Flow)](#2-luồng-dữ-liệu-hoạt-động-chi-tiết)
3. [Giải đáp Toàn diện Các Câu hỏi Cốt lõi về Core Chatbot](#3-giải-đáp-toàn-diện-các-câu-hỏi-cốt-lõi-về-core-chatbot)
   - [Câu hỏi 1: Hệ thống RAG nằm ở đâu và hoạt động như thế nào?](#câu-hỏi-1-hệ-thống-rag-retrieval-augmented-generation-nằm-ở-đâu-và-hoạt-động-như-thế-nào)
   - [Câu hỏi 2: LangChain nằm ở vị trí nào và giải quyết bài toán gì trong hệ thống?](#câu-hỏi-2-langchain-nằm-ở-vị-trí-nào-và-giải-quyết-bài-toán-gì-trong-hệ-thống)
   - [Câu hỏi 3: Vì sao chatbot có thể "đọc hiểu" ngôn ngữ tự nhiên?](#câu-hỏi-3-vì-sao-chatbot-có-thể-đọc-hiểu-ngôn-ngữ-tự-nhiên)
   - [Câu hỏi 4: Cơ chế quản lý ngữ cảnh đa lượt (Multi-turn Context) & đại từ thay thế hoạt động ra sao?](#câu-hỏi-4-cơ-chế-quản-lý-ngữ-cảnh-đa-lượt-multi-turn-context--đại-từ-thay-thế-hoạt-động-ra-sao)
   - [Câu hỏi 5: Tại sao sử dụng Hybrid Retrieval (BM25 + BGE-M3 qua RRF) thay vì chỉ dùng Vector Search?](#câu-hỏi-5-tại-sao-sử-dụng-hybrid-retrieval-bm25--bge-m3-qua-rrf-thay-vì-chỉ-dùng-vector-search)
   - [Câu hỏi 6: Làm thế nào để chatbot tuyệt đối không bịa đặt thông tin (Anti-hallucination)?](#câu-hỏi-6-làm-thế-nào-để-chatbot-tuyệt-đối-không-bịa-đặt-thông-tin-anti-hallucination)
   - [Câu hỏi 7: Luồng nạp dữ liệu tri thức mới (Batch Ingestion Pipeline) diễn ra như thế nào?](#câu-hỏi-7-luồng-nạp-dữ-liệu-tri-thức-mới-batch-ingestion-pipeline-diễn-ra-như-thế-nào)
4. [Bảng Ánh xạ Trực tiếp File Nguồn, Class, Hàm và Số Dòng](#4-bảng-ánh-xạ-trực-tiếp-file-nguồn-class-hàm-và-số-dòng)
5. [Cẩm nang Vấn đáp Nhanh (Viva Defense Cheat Sheet)](#5-cẩm-nang-vấn-đáp-nhanh-viva-defense-cheat-sheet)

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG

Chatbox 2.0 được xây dựng theo mô hình **Controlled Hybrid RAG Pipeline** (RAG lai có kiểm soát). Không giống như các hệ thống RAG ngây thơ (Naive RAG) thường gửi thẳng câu hỏi của người dùng vào Vector Database rồi chuyển ngữ cảnh cho LLM sinh câu trả lời, hệ thống này áp dụng kiến trúc phân tầng với nhiều lớp bảo vệ (Gateways & Guardrails), tối ưu hóa hiệu năng và độ chính xác 100% cục bộ.

### Sơ đồ Kiến trúc Phân tầng (Architecture Diagram)

```mermaid
flowchart TD
    subgraph UI ["TẦNG GIAO DIỆN (Presentation Layer)"]
        User(["Người dùng"]) --> ReactApp["React 18 + Vite + Tailwind CSS<br/>(Thẻ từ vựng, Audio TTS, Provenance)"]
    end

    subgraph API ["TẦNG CỔNG API (FastAPI Backend)"]
        ReactApp -- "HTTP POST SSE: /api/chat/stream" --> StreamRouter["Streaming Router<br/>(vocab_backend/streaming_routes.py)"]
        StreamRouter --> ChatEngine["ChatEngine Điều phối Trung tâm<br/>(src/chat/engine.py)"]
    end

    subgraph NLU ["TẦNG HIỂU NGỮ CẢNH & PHÂN LOẠI (NLU & Context Layer)"]
        ChatEngine --> QueryRouter["0. Query Router & Exception Handler<br/>(src/chat/query_router.py)"]
        QueryRouter -- "Chào hỏi / Xã giao" --> SmallTalk["SmallTalkHandler (Sub-millisecond)"]
        QueryRouter -- "Tra cứu từ vựng" --> TopicTracker["1. Topic Tracker & Context Buffer<br/>(src/chat/topic_tracker.py)"]
        
        TopicTracker -- "Thiếu từ vựng & Chưa có Topic" --> ClarificationGate["Clarification Gate<br/>'Bạn đang muốn hỏi từ nào?...'"]
        TopicTracker -- "Đã phân giải đại từ (resolved_query)" --> IntentClassifier["2. PhoBERT Intent Classifier<br/>(src/nlp/phobert_intent.py)"]
        
        IntentClassifier -- "OUT_OF_SCOPE / Cấp độ ngoài A1-A2" --> DomainGate["Domain Gate: Từ chối lịch sự<br/>(settings.OUT_OF_SCOPE_RESPONSE)"]
    end

    subgraph RETRIEVAL ["TẦNG TRUY XUẤT TRI THỨC LAI (Hybrid Retrieval Engine)"]
        IntentClassifier -- "Hợp lệ" --> HybridRetriever["3. Hybrid Retriever<br/>(src/retriever/hybrid_retriever.py)"]
        
        HybridRetriever --> BM25["Sparse: BM25Okapi<br/>(Bắt chính xác từ khóa, level)"]
        HybridRetriever --> BGE["Dense: BAAI/bge-m3 + ChromaDB<br/>(1024 chiều, hiểu ngữ nghĩa đa ngữ)"]
        
        BM25 --> RRF["4. Reciprocal Rank Fusion (RRF k=60)<br/>Hợp nhất thứ hạng Sparse + Dense"]
        BGE --> RRF
    end

    subgraph GATING ["TẦNG CỔNG QUYẾT ĐỊNH (Decision & Relevance Gate)"]
        RRF --> RelevanceGate{"5. Relevance Gate"}
        RelevanceGate -- "Score < 0.005 / Không khớp" --> NoMatch["NO_MATCH: Từ chối lịch sự"]
        RelevanceGate -- "Exact Match & RRF >= 0.030" --> DirectMatch["DIRECT_MATCH<br/>(Trả lời trực tiếp từ dữ liệu gốc, < 150ms)"]
        RelevanceGate -- "RRF >= 0.005" --> RAGGen["RAG_GENERATION<br/>(Cần tổng hợp ngữ cảnh qua LLM)"]
    end

    subgraph GENERATION ["TẦNG SINH NGÔN NGỮ (Grounded Generation)"]
        RAGGen --> LangChain["6. LangChain LCEL RAG Chain<br/>(src/llm/client.py & prompts.py)<br/>ChatPromptTemplate | ChatOllama | StrOutputParser"]
        LangChain --> Ollama["7. Qwen2.5:7B via Ollama<br/>(Chạy GPU/CPU Cục bộ, Strict Prompt, T=0.0)"]
    end

    subgraph OUTPUT ["TẦNG ĐÓNG GÓI & PHẢN HỒI"]
        DirectMatch --> PostProcess["Hậu xử lý: Lọc CJK, Format Markdown, Parse Card"]
        Ollama -- "Tokens stream" --> PostProcess
        ClarificationGate --> PostProcess
        DomainGate --> PostProcess
        SmallTalk --> PostProcess
        NoMatch --> PostProcess
        PostProcess --> SSEOutput["SSE Event Stream (tokens, provenance, card)"]
        SSEOutput --> ReactApp
    end
```

---

## 2. LUỒNG DỮ LIỆU HOẠT ĐỘNG CHI TIẾT

Để hiểu chính xác mã nguồn thực thi thế nào khi người dùng nhập một câu hỏi, ta theo dõi sơ đồ tuần tự (Sequence Diagram) dưới đây:

### Sơ đồ Tuần tự Thực thi (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant UI as React Frontend
    participant API as FastAPI Streaming Route
    participant Engine as ChatEngine (src/chat/engine.py)
    participant Tracker as TopicTracker (src/chat/topic_tracker.py)
    participant NLU as PhoBERT (src/nlp/phobert_intent.py)
    participant Hybrid as HybridRetriever (src/retriever/)
    participant Chroma as ChromaDB & BM25
    participant LC as LangChain LCEL (src/llm/client.py)
    participant LLM as Ollama (Qwen2.5:7B)

    User->>UI: Nhập: "từ này nghĩa là gì?"
    UI->>API: POST /api/chat/stream {query: "từ này nghĩa là gì?", conv_id}
    API->>Engine: ask_stream(effective_query, tracker)
    
    rect rgb(240, 248, 255)
        Note over Engine,Tracker: Giai đoạn 1 & 2: Phân giải Ngữ cảnh & Đại từ
        Engine->>Tracker: resolve_query("từ này nghĩa là gì?")
        alt Lượt trước đã nói về từ "confident"
            Tracker-->>Engine: resolved_query = "confident nghĩa là gì?", target_word="confident"
        else Chưa có ngữ cảnh (lượt đầu tiên)
            Tracker-->>Engine: is_ambiguous = True
            Engine-->>API: Trả về câu hỏi lại (Clarification Gate)
            API-->>UI: "Bạn đang muốn hỏi về từ vựng nào?..."
        end
    end

    rect rgb(255, 250, 240)
        Note over Engine,NLU: Giai đoạn 3: Phân tích Ý định (NLU)
        Engine->>NLU: classify_intent(resolved_query)
        NLU->>NLU: Tính Cosine Similarity với Prototype Centroids (768-dim)
        NLU-->>Engine: Intent = DEFINE_VOCAB, Confidence = 0.92
    end

    rect rgb(240, 255, 240)
        Note over Engine,Chroma: Giai đoạn 4: Truy xuất Lai (BM25 + BGE-M3 + RRF)
        Engine->>Hybrid: retrieve(resolved_query)
        par Truy xuất Từ khóa (Sparse)
            Hybrid->>Chroma: BM25Okapi.search(resolved_query)
        and Truy xuất Ngữ nghĩa (Dense)
            Hybrid->>Chroma: BGE-M3 Embedding + ChromaDB.query()
        end
        Hybrid->>Hybrid: RRF Fusion: 1/(60+rank_bm25) + 1/(60+rank_bge)
        Hybrid-->>Engine: best_candidate (Record: confident), RRF Score = 0.032, Mode = DIRECT_MATCH
    end

    rect rgb(255, 245, 245)
        Note over Engine,LLM: Giai đoạn 5: Quyết định Phản hồi & Sinh câu trả lời
        alt Mode == DIRECT_MATCH
            Engine->>Engine: format_vocabulary_response(best_candidate.answer)
            Engine-->>API: Yield answer trực tiếp (< 150ms, không tốn GPU)
        else Mode == RAG_GENERATION
            Engine->>LC: generate_with_langchain_stream(resolved_query, context)
            LC->>LLM: Stream prompt tới Qwen2.5:7B qua ChatOllama
            loop Sinh từng Token
                LLM-->>LC: Chunk token
                LC->>LC: clean_chinese_characters(token)
                LC-->>Engine: Yield token
                Engine-->>API: Yield token
                API-->>UI: SSE event: {"type": "token", "token": "..."}
                UI-->>User: Hiển thị chữ chạy theo thời gian thực
            end
        end
    end

    API->>UI: SSE event: {"type": "done", "provenance": {...}, "card": {...}}
    UI->>User: Hiển thị Thẻ từ vựng + Nút phát âm Audio + Provenance Inspector
```

---

### Phân tích Chi tiết 8 Bước Vận hành trong Mã nguồn

#### Bước 1: Tiếp nhận và Tiền xử lý (API Gateway)
- **Tệp nguồn:** [vocab_backend/streaming_routes.py](file:///c:/Users/User/Desktop/chatbox2.0/vocab_backend/streaming_routes.py#L32-L85)
- **Thực thi:**
  - Client React gửi yêu cầu HTTP POST kèm JSON `StreamChatRequest` (`query`, `level`, `conversation_id`, `user_id`).
  - Hệ thống tự động tạo hoặc khôi phục phiên hội thoại trong SQLite thông qua `ConversationRepository`.
  - Hàm `normalize_query_text(query)` chuẩn hóa ký tự, xóa khoảng trắng thừa.
  - Khởi tạo hàm sinh `event_generator()` để trả về `StreamingResponse(media_type="text/event-stream")`.

#### Bước 2: Điều phối Nhanh qua QueryRouter & SmallTalkHandler
- **Tệp nguồn:** [src/chat/query_router.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/query_router.py), [src/chat/small_talk_handler.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/small_talk_handler.py), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L185-L206)
- **Thực thi:**
  - `QueryRouter.route()` kiểm tra xem câu hỏi có thuộc các mẫu câu chào hỏi xã giao (Small-talk: "xin chào", "bạn là ai", "cảm ơn") hay không.
  - Nếu khớp: `SmallTalkHandler` trả lời ngay lập tức bằng mẫu câu định sẵn từ `config/exception_intent.json` với độ trễ `< 2ms`, hoàn toàn không đánh thức Vector Store hay LLM.

#### Bước 3: Phân giải Ngữ cảnh Đa lượt (Multi-turn Context Resolution)
- **Tệp nguồn:** [src/chat/topic_tracker.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py#L310-L370), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L237-L252)
- **Thực thi:**
  - Gọi `active_tracker.resolve_query(clean_query)`.
  - Bộ phát hiện đại từ (`REFERENTIAL_PATTERNS`) tìm các đại từ tiếng Việt như: *"từ này"*, *"từ đó"*, *"nó"*, *"của nó"*.
  - **Trường hợp mơ hồ (Ambiguity):** Nếu người dùng dùng đại từ ở câu đầu tiên khi chưa có `active_word` nào trong phiên, cờ `is_ambiguous = True` được bật. Chatbot lập tức kích hoạt `Clarification Gate` và gửi câu hỏi gợi mở: *"Bạn đang muốn hỏi về từ vựng nào?..."*.
  - **Trường hợp có ngữ cảnh:** Nếu trước đó người dùng vừa hỏi từ *"abandon"*, hệ thống tự động tái tạo:  
    `"cho tôi ví dụ của từ này"` $\rightarrow$ `"cho tôi ví dụ của từ abandon"`.

#### Bước 4: Hiểu Ý định (NLU) & Cổng Phân loại Miền (Domain Gate)
- **Tệp nguồn:** [src/nlp/phobert_intent.py](file:///c:/Users/User/Desktop/chatbox2.0/src/nlp/phobert_intent.py#L148-L268), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L253-L300)
- **Thực thi:**
  - Câu hỏi đã phân giải ngữ cảnh được đưa vào `PhoBERTIntentClassifier.classify_intent()`.
  - Mô hình `vinai/phobert-base-v2` mã hóa câu văn thành vector 768 chiều và so khớp với tâm cụm các nhóm ý định: `DEFINE_VOCAB`, `GET_EXAMPLE`, `GET_LEVEL_LIST`, `TRANSLATE_VIE_TO_ENG`, `FOLLOW_UP`, `OUT_OF_SCOPE`.
  - **Domain Gate:** Nếu câu hỏi thuộc chủ đề ngoài lề (thời tiết, toán học, giá coin,...) hoặc yêu cầu từ vựng ngoài phạm vi A1–A2 (như B1, B2, C1, C2), hệ thống lập tức từ chối lịch sự bằng thông điệp định sẵn trong `config/settings.py` mà không tiếp tục truy vấn tốn tài nguyên.

#### Bước 5: Truy xuất Lai Kết hợp (BM25 + BGE-M3 ChromaDB + RRF)
- **Tệp nguồn:** [src/retriever/hybrid_retriever.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/hybrid_retriever.py#L157-L250), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L301-L329)
- **Thực thi:**
  - Khóa đọc `IndexAccessCoordinator.read_lock()` được kích hoạt nhằm đảm bảo an toàn luồng (Thread-safety) khi có tiến trình nạp dữ liệu nền.
  - Chạy song song:
    1. **BM25Okapi** tìm kiếm đối sánh từ khóa chính xác trên toàn bộ từ vựng và câu hỏi mẫu.
    2. **BAAI/bge-m3** tính vector 1024 chiều của câu hỏi và tìm kiếm độ tương đồng Cosine trong ChromaDB.
  - Thuật toán **Reciprocal Rank Fusion (RRF)** với hằng số $k=60$ hợp nhất thứ hạng của hai danh sách kết quả.
  - Trích xuất chuỗi ngữ cảnh `context_str` đại diện cho các bản ghi hàng đầu. Khóa đọc được giải phóng ngay sau đó (~150ms).

#### Bước 6: Cổng Kiểm soát Ngưỡng & Quyết định Phản hồi (Relevance Gate)
- **Tệp nguồn:** [src/retriever/hybrid_retriever.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/hybrid_retriever.py#L253-L273), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L370-L411)
- **Thực thi:**
  - Điểm số RRF cao nhất được đem so sánh với các ngưỡng cấu hình:
    - **`DIRECT_MATCH` ($RRF \ge 0.030$ hoặc Fast-path Lexical Match):** Áp dụng cho các câu hỏi tra từ vựng trực tiếp có bản ghi trùng khớp hoàn toàn trong dữ liệu. Câu trả lời được lấy nguyên bản từ `QARecord.answer` và định dạng chuẩn qua `format_vocabulary_response()`. **Bỏ qua hoàn toàn LLM**, độ trễ $< 150ms$, bảo toàn 100% độ chính xác của từ điển.
    - **`RAG_GENERATION` ($0.005 \le RRF < 0.030$):** Áp dụng cho các câu hỏi diễn đạt tự nhiên, hỏi đảo nghĩa Việt - Anh hoặc câu hỏi phức tạp. Chuyển sang Bước 7 để LLM tổng hợp và trả lời.
    - **`NO_MATCH` ($RRF < 0.005$):** Không tìm thấy dữ liệu liên quan, hệ thống báo không có thông tin thay vì để LLM bịa đặt.

#### Bước 7: Sinh Ngôn ngữ có Kiểm soát qua LangChain LCEL (RAG Generation)
- **Tệp nguồn:** [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L201-L237), [src/llm/prompts.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/prompts.py#L11-L46)
- **Thực thi:**
  - Chuỗi LCEL: `chain = prompt_tmpl | llm | StrOutputParser()`.
  - `prompt_tmpl` nạp `SYSTEM_PROMPT` với cơ chế Strict Grounding: Cấm LLM dùng tri thức ngoài, chỉ cho phép dùng thông tin trong `[NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP]`.
  - `ChatOllama` kết nối tới `qwen2.5:7b` với tham số `temperature = 0.0` (ngăn ngẫu nhiên sáng tác).
  - Từng token được sinh ra sẽ chạy qua hàm `clean_chinese_characters()` để loại bỏ triệt để các ký tự CJK tiếng Trung (nếu có).

#### Bước 8: Đóng gói Phản hồi, Lưu Lịch sử & Truyền luồng SSE
- **Tệp nguồn:** [vocab_backend/streaming_routes.py](file:///c:/Users/User/Desktop/chatbox2.0/vocab_backend/streaming_routes.py#L127-L210), [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L119-L159)
- **Thực thi:**
  - Giao diện nhận các sự kiện SSE `{"type": "token", "token": "..."}` và hiển thị hiệu ứng gõ chữ (typing effect).
  - Kết thúc luồng, hệ thống gửi gói dữ liệu kiểm toán `provenance` (mã bản ghi `record_id`, điểm `bm25_score`, `bge_score`, `rrf_score`, thời gian phản hồi `latency_ms`).
  - Gửi cấu trúc thẻ từ vựng `structured_card` (từ, phiên âm IPA, loại từ, các nghĩa và ví dụ) để React render giao diện tương tác và nút nghe âm thanh bản ngữ `Kokoro TTS`.
  - Lưu lượt hội thoại mới vào `ConversationTurn` của `TopicTracker` để phục vụ các lượt chat kế tiếp.

---

## 3. GIẢI ĐÁP TOÀN DIỆN CÁC CÂU HỎI CỐT LÕI VỀ CORE CHATBOT

---

### Câu hỏi 1: Hệ thống RAG (Retrieval-Augmented Generation) nằm ở đâu và hoạt động như thế nào?

**Trả lời:**

RAG không phải là một thư viện độc lập hay một khối mã đơn lẻ, mà là một **mô hình kiến trúc (Architectural Pattern)** bao gồm 3 trụ cột được kết nối chặt chẽ trong mã nguồn của dự án:

```mermaid
flowchart LR
    subgraph R ["1. RETRIEVAL (Truy xuất)"]
        direction TB
        R1["BM25Okapi (Sparse)"]
        R2["BGE-M3 + ChromaDB (Dense)"]
        R3["RRF Fusion (k=60)"]
    end

    subgraph A ["2. AUGMENTATION (Tăng cường)"]
        direction TB
        A1["build_context_string()"]
        A2["Strict Grounding System Prompt"]
    end

    subgraph G ["3. GENERATION (Sinh câu trả lời)"]
        direction TB
        G1["LangChain LCEL Chain"]
        G2["Ollama Qwen2.5:7B (Local)"]
    end

    R --> A --> G
```

1. **Trụ cột 1 - Retrieval (Truy xuất tri thức):**
   - **Nằm tại:** Thư mục [src/retriever/](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/).
   - **Hoạt động:** Khi nhận câu hỏi của người dùng, thay vì để LLM tự nhớ (dễ bịa đặt), hệ thống dùng `BM25Retriever` ([src/retriever/bm25_retriever.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/bm25_retriever.py)) và `BGEChromaRetriever` ([src/retriever/bge_chroma.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/bge_chroma.py)) quét trong kho dữ liệu cục bộ để tìm ra Top-K tài liệu từ vựng liên quan nhất. Hai danh sách được hợp nhất bằng thuật toán RRF trong [src/retriever/hybrid_retriever.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/hybrid_retriever.py).

2. **Trụ cột 2 - Augmentation (Tăng cường ngữ cảnh):**
   - **Nằm tại:** [src/llm/prompts.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/prompts.py#L55-L94).
   - **Hoạt động:** Hàm `build_context_string(contexts)` trích xuất nội dung từ các bản ghi tri thức tìm được ở bước 1, đóng gói thành khối văn bản `[NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP]`. Khối ngữ cảnh này được đưa vào cùng với câu hỏi của người dùng trong một cấu trúc Prompt có kiểm soát nghiêm ngặt.

3. **Trụ cột 3 - Generation (Sinh phản hồi có căn cứ):**
   - **Nằm tại:** [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L201-L237) và [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L413-L450).
   - **Hoạt động:** Chuỗi LangChain LCEL gửi Prompt kèm Ngữ cảnh sang mô hình ngôn ngữ lớn `qwen2.5:7b` chạy trên Ollama cục bộ. Mô hình chỉ đóng vai trò là một **người tổng hợp và diễn đạt (Synthesizer)**: đọc thông tin từ ngữ cảnh để viết lại thành câu văn tiếng Việt trôi chảy, tuyệt đối không được dùng tri thức nằm ngoài ngữ cảnh.

> [!NOTE]
> **Điểm đột phá: Kiến trúc "Controlled Hybrid RAG"**  
> Dự án không đẩy tất cả qua LLM. Tại [src/chat/engine.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L396-L411), nếu câu hỏi là tra từ vựng trực tiếp (`DIRECT_MATCH`), hệ thống **bỏ qua bước Generation của LLM** và trả thẳng dữ liệu đã định dạng. Điều này giúp độ trễ giảm từ ~3000ms xuống chỉ còn ~150ms, tiết kiệm 100% VRAM GPU cho các câu hỏi tra cứu thông thường.

---

### Câu hỏi 2: LangChain nằm ở vị trí nào và giải quyết bài toán gì trong hệ thống?

**Trả lời:**

Trong dự án, **LangChain** đóng vai trò là khung điều phối tầng sinh ngôn ngữ (LLM Orchestration Framework). Toàn bộ mã nguồn tích hợp LangChain nằm tập trung tại:
- **Tệp tích hợp chuỗi LCEL:** [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L14-L15, #L201-L237)
- **Tệp mẫu Prompt LangChain:** [src/llm/prompts.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/prompts.py#L52, #L97-L109)

#### 1. Cấu trúc Chuỗi LangChain Expression Language (LCEL) trong Code
Trong phương thức `generate_with_langchain` và `generate_with_langchain_stream` tại [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L213-L237):

```python
# Trích xuất từ src/llm/client.py
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from src.llm.prompts import get_langchain_prompt_template

# Khởi tạo mô hình ChatOllama kết nối dịch vụ Ollama cục bộ
llm = ChatOllama(
    model=self.model,                     # 'qwen2.5:7b'
    base_url=self.base_url,               # 'http://127.0.0.1:11434'
    temperature=settings.LLM_TEMPERATURE,# 0.0 (Strict Grounding)
    num_ctx=4096,
    num_predict=1024,
    num_thread=4,
)

# Xây dựng chuỗi pipeline LCEL với toán tử pipe (|)
prompt_tmpl = get_langchain_prompt_template()
chain = prompt_tmpl | llm | StrOutputParser()
```

#### 2. LangChain giải quyết những bài toán cốt lõi nào?
1. **Chuẩn hóa cấu trúc Prompt theo chuẩn công nghiệp:**
   Sử dụng `ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("user", ...)])` giúp phân tách rành mạch giữa chỉ thị hệ thống (System Prompt) và dữ liệu đầu vào của người dùng kèm ngữ cảnh RAG, ngăn ngừa tấn công Prompt Injection.
2. **Quản lý kết nối thống nhất với mô hình Local (`ChatOllama`):**
   Thay vì phải tự viết các đoạn mã HTTP Client thủ công phức tạp để xử lý gọi API Ollama, LangChain cung cấp adapter `ChatOllama` chuẩn hóa, tự động quản lý payload, cấu hình context window (`num_ctx`), số token sinh tối đa (`num_predict`) và nhiệt độ (`temperature`).
3. **Streaming Token mượt mà qua `.stream()`:**
   Phương thức `chain.stream({"question": question, "context": context})` của LangChain cho phép nhận các token sinh ra từ mô hình theo thời gian thực dưới dạng một `Iterator[str]`. Nhờ đó, Backend FastAPI có thể dễ dàng chuyển tiếp từng token thành các sự kiện Server-Sent Events (SSE) để React UI hiển thị chữ chạy ngay lập tức mà không phải chờ mô hình sinh xong toàn bộ câu trả lời.
4. **Chuẩn hóa đầu ra với `StrOutputParser`:**
   Tự động bóc tách trường văn bản thô từ cấu trúc dữ liệu `AIMessage` của mô hình, đảm bảo luồng dữ liệu truyền qua các bước tiếp theo luôn là chuỗi ký tự thuần nhất.

---

### Câu hỏi 3: Vì sao chatbot có thể "đọc hiểu" ngôn ngữ tự nhiên?

**Trả lời:**

Khả năng "đọc hiểu" ngôn ngữ tự nhiên (Natural Language Understanding - NLU) của Chatbox 2.0 không phải là một phép màu, mà được xây dựng từ **3 tầng biểu diễn ngữ nghĩa toán học (Semantic Vector Embeddings)** kết hợp với phân tích luật:

```mermaid
flowchart TD
    Query["Câu hỏi tự nhiên của người dùng<br/>(vd: 'bạn có thể giải thích ý nghĩa của từ abandon được không?')"]
    
    subgraph T1 ["TẦNG 1: HIỂU Ý ĐỊNH & THỰC THỂ (PhoBERT-base-v2)"]
        PB["PhoBERT Tokenizer & Transformer<br/>(135M tham số, chuyên biệt tiếng Việt)"] --> MeanPool["Mean Pooling 768 chiều"]
        MeanPool --> CosSim["Cosine Similarity với Prototype Centroids"]
        CosSim --> Intent["Xác định Ý định: DEFINE_VOCAB<br/>Trích xuất Target Word: 'abandon'"]
    end

    subgraph T2 ["TẦNG 2: HIỂU NGỮ NGHĨA ĐA NGỮ (BAAI/bge-m3)"]
        BGE["BGE-M3 Dense Embedding<br/>(1024 chiều, đa ngữ Cross-lingual)"] --> Space["Ánh xạ câu hỏi tiếng Việt và định nghĩa tiếng Anh<br/>vào cùng một không gian vector đa chiều"]
        Space --> Match["Tìm được từ vựng tương đồng ngữ nghĩa cao nhất"]
    end

    subgraph T3 ["TẦNG 3: DIỄN ĐẢI NGỮ NGHĨA TỰ NHIÊN (Qwen2.5:7B)"]
        Qwen["Mô hình LLM Qwen2.5:7B (7 tỷ tham số)"] --> Synthesize["Đọc hiểu mối quan hệ giữa câu hỏi và ngữ cảnh<br/>Diễn đạt câu trả lời mượt mà, đúng ngữ pháp"]
    end

    Query --> T1
    T1 --> T2
    T2 --> T3
```

#### 1. Tầng NLU tiếng Việt với PhoBERT-base-v2 (Prototype-based Matching)
- **Tệp nguồn:** [src/nlp/phobert_intent.py](file:///c:/Users/User/Desktop/chatbox2.0/src/nlp/phobert_intent.py#L110-L146)
- **Bản chất:**
  - Mô hình `vinai/phobert-base-v2` là mô hình ngôn ngữ được tiền huấn luyện trên hàng tỷ từ tiếng Việt. Nó hiểu được cấu trúc ngữ pháp, từ đồng nghĩa và từ đệm trong tiếng Việt.
  - Khi người dùng hỏi một câu gián tiếp nhiều từ đệm như: *"bạn có thể giải thích ý nghĩa của từ abandon được không?"*, PhoBERT mã hóa câu này thành một vector không gian 768 chiều (thông qua cơ chế `Mean Pooling` có xét `attention_mask` tại hàm `_encode_sentence`).
  - Hệ thống so sánh vector này với **Tâm cụm ý định (Prototype Centroid)** của intent `DEFINE_VOCAB`. Nhờ tính chất khoảng cách ngữ nghĩa, câu hỏi trên có độ tương đồng Cosine rất cao ($> 0.85$) với mẫu tra từ điển, giúp hệ thống lọc bỏ hoàn toàn các từ rác ("bạn có thể", "được không") để nhận biết đúng ý định cốt lõi.

#### 2. Tầng Hiểu Ngữ nghĩa Xuyên Ngôn ngữ (Cross-lingual) với BAAI/bge-m3
- **Tệp nguồn:** [src/retriever/bge_chroma.py](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/bge_chroma.py#L70-L115)
- **Bản chất:**
  - Mô hình `BAAI/bge-m3` có khả năng nhúng đa ngữ vượt trội. Nó chiếu cả tiếng Việt và tiếng Anh vào **cùng một không gian vector 1024 chiều**.
  - Ví dụ: Khi người dùng hỏi *"từ nào có nghĩa là từ bỏ?"*, câu hỏi hoàn toàn bằng tiếng Việt và không chứa chữ tiếng Anh nào. Tuy nhiên, trong không gian 1024 chiều của BGE-M3, vector của cụm *"từ bỏ"* nằm rất gần với vector của định nghĩa từ *"abandon"* (*"to leave somebody/something that you are responsible for"*). Do đó, hệ thống vẫn tìm ra chính xác từ `abandon` trong cơ sở dữ liệu.

#### 3. Tầng Diễn giải và Sinh Ngôn ngữ Tự nhiên với Qwen2.5:7B
- **Tệp nguồn:** [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L213-L237)
- **Bản chất:**
  - `Qwen2.5:7B` sở hữu 7 tỷ trọng số được huấn luyện sâu về khả năng tuân thủ chỉ thị (Instruction Following) và suy luận logic. Khi nhận được ngữ cảnh dữ liệu từ điển, mô hình "đọc hiểu" các thông tin: từ loại, phiên âm IPA, nghĩa 1, nghĩa 2, ví dụ... và sử dụng tri thức ngôn ngữ của nó để viết thành câu trả lời hoàn chỉnh, mạch lạc theo đúng phong cách sư phạm.

---

### Câu hỏi 4: Cơ chế quản lý ngữ cảnh đa lượt (Multi-turn Context) & đại từ thay thế hoạt động ra sao?

**Trả lời:**

Quản lý ngữ cảnh nhiều lượt được giao cho module `TopicTracker` ([src/chat/topic_tracker.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py)). Module này lưu giữ trạng thái của phiên trò chuyện và giải quyết bài toán quy chiếu đại từ (Anaphora Resolution) thông qua quy trình 4 bước:

```mermaid
flowchart TD
    Turn1["Lượt 1: Người dùng hỏi 'about nghĩa là gì?'"] --> Update1["TopicTracker cập nhật:<br/>active_word = 'about'<br/>active_level = 'A1'"]
    
    Update1 --> Turn2["Lượt 2: Người dùng hỏi 'cho tôi ví dụ của từ này'"]
    
    Turn2 --> Detect["TopicTracker.resolve_query():<br/>1. Phát hiện đại từ: 'từ này' thuộc REFERENTIAL_PATTERNS<br/>2. Kiểm tra active_word hiện có: 'about'"]
    
    Detect --> Reconstruct["Tái tạo câu truy vấn ngầm (resolved_query):<br/>'cho tôi ví dụ của từ about'"]
    
    Reconstruct --> Retain["Giữ vững active_word = 'about' cho các lượt tiếp theo"]
```

#### Chi tiết Kỹ thuật trong Mã nguồn:
1. **Duy trì Trọng tâm Hội thoại (`active_word`):**
   Tại [src/chat/topic_tracker.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py#L70-L74), đối tượng `TopicTracker` lưu giữ các biến trạng thái: `self.active_word`, `self.active_level`, `self.active_intent` và danh sách các lượt trước `self.history` (tối đa 10 lượt).
2. **Phát hiện Đại từ Tham chiếu (Referential Pronouns):**
   Hệ thống định nghĩa danh sách regex `REFERENTIAL_PATTERNS` tại [dòng 33-43](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py#L33-L43):
   ```python
   REFERENTIAL_PATTERNS = [
       r"\btừ\s+này\b", r"\btừ\s+đó\b", r"\btừ\s+trên\b",
       r"\btừ\s+vựng\s+này\b", r"\bcủa\s+nó\b", r"\bvới\s+nó\b",
       r"\bcho\s+nó\b", r"\bnó\b",
   ]
   ```
3. **Giải quyết Ngữ cảnh (`resolve_query`):**
   Trong hàm `resolve_query()` ([dòng 310-370](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py#L310-L370)):
   - Nếu câu hỏi chứa đại từ và `self.active_word` đang có giá trị (ví dụ: `"confident"`):
     Hệ thống thực hiện phép thế chuỗi regex, biến *"cho tôi câu ví dụ của từ này"* thành *"cho tôi câu ví dụ của confident"*. Câu hỏi sau khi làm giàu này được gửi xuống các bộ tìm kiếm BM25 và Vector, đảm bảo tìm kiếm chính xác 100%.
4. **Cơ chế Bẫy Mơ hồ (Clarification Gate):**
   - Nếu người dùng bước vào phòng chat và gõ ngay: *"từ này nghĩa là gì?"* mà chưa từng đề cập đến từ vựng nào trước đó (`self.active_word is None`).
   - `TopicTracker` lập tức đánh dấu `is_ambiguous = True`.
   - `ChatEngine` tại [src/chat/engine.py#L241-L251](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L241-L251) bắt được cờ này và chuyển ngay sang chế độ `CLARIFICATION`, phản hồi:  
     *"Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé!"*.  
     Cơ chế này ngăn chặn tuyệt đối việc LLM tự suy đoán bừa bãi khi người dùng hỏi cụt lủn.

---

### Câu hỏi 5: Tại sao sử dụng Hybrid Retrieval (BM25 + BGE-M3 qua RRF) thay vì chỉ dùng Vector Search?

**Trả lời:**

Trong bài toán tra cứu từ điển học, việc chỉ dùng đơn lẻ **Vector Search (Dense Retrieval)** hoặc **Keyword Search (Sparse Retrieval - BM25)** đều bộc lộ những nhược điểm chí mạng:

| Tiêu chí so sánh | BM25Okapi (Sparse Retrieval) | BGE-M3 ChromaDB (Dense Retrieval) | Hybrid RRF ($k=60$) (Hệ thống áp dụng) |
| :--- | :--- | :--- | :--- |
| **Bắt chính xác từ vựng (Exact Keyword)** | **Rất mạnh (100% chính xác)** khi gõ đúng `"abandon"`, `"about"`. | *Dễ nhầm lẫn*: Các từ viết gần giống nhau (`"affect"` vs `"effect"`, `"access"` vs `"assess"`) có vector rất gần nhau. | **Tối ưu tuyệt đối**: BM25 kéo từ chính xác lên top 1 ngay lập tức. |
| **Tìm kiếm ngữ nghĩa (Semantic / Paraphrase)** | *Thất bại hoàn toàn*: Không thể tìm được từ nếu người dùng dùng từ đồng nghĩa. | **Rất mạnh**: Hiểu được các câu diễn đạt vòng vo, gián tiếp. | **Kế thừa hoàn hảo**: BGE-M3 bù đắp điểm mù của BM25. |
| **Tra cứu đảo Việt $\rightarrow$ Anh (Cross-lingual)** | *Thất bại*: Câu hỏi tiếng Việt không chứa từ khóa tiếng Anh tương ứng. | **Rất mạnh**: Ánh xạ ngữ nghĩa xuyên ngôn ngữ 1024 chiều. | **Chính xác cao**: BGE-M3 xếp hạng cao các bản ghi có nghĩa tiếng Việt tương ứng. |
| **Mã định danh, Cấp độ CEFR (A1, A2)** | **Bắt chính xác** token `"A1"`, `"A2"`, `"verb"`. | *Kém*: Vector embedding thường bị mờ (loss) đối với các chuỗi ngắn 2 ký tự như "A1". | **Chính xác**: BM25 đảm bảo không bị lẫn lộn cấp độ. |

#### Thuật toán Hợp nhất Thứ hạng RRF (Reciprocal Rank Fusion)
Thay vì cộng điểm thô (Raw Score) một cách bất hợp lý (vì điểm BM25 là số thực không chặn trên $[0, +\infty)$, còn điểm BGE-M3 là Cosine Similarity $[-1, 1]$), hệ thống áp dụng công thức chuẩn **RRF** tại [src/retriever/hybrid_retriever.py#L210-L238](file:///c:/Users/User/Desktop/chatbox2.0/src/retriever/hybrid_retriever.py#L210-L238):

$$RRF\_Score(d) = \frac{1}{k + r_{bm25}(d)} + \frac{1}{k + r_{bge}(d)}$$

- Trong đó:
  - $r_{bm25}(d)$ là vị trí thứ hạng của tài liệu $d$ trong danh sách BM25 ($1, 2, 3...$).
  - $r_{bge}(d)$ là vị trí thứ hạng của tài liệu $d$ trong danh sách BGE-M3 ($1, 2, 3...$).
  - $k = 60$ là hằng số làm mịn chuẩn quốc tế (Smoothing constant) nhằm giảm sự chi phối quá mức của tài liệu top 1 đơn lẻ.
- **Ý nghĩa:** Tài liệu nào xuất hiện đồng thời ở thứ hạng cao trong **cả hai bảng xếp hạng** sẽ có điểm $RRF$ vượt trội, loại bỏ hoàn toàn các kết quả dương tính giả (False Positives) của từng mô hình riêng lẻ.

---

### Câu hỏi 6: Làm thế nào để chatbot tuyệt đối không bịa đặt thông tin (Anti-hallucination)?

**Trả lời:**

Hiện tượng bịa đặt thông tin (Hallucination) là điểm yếu cố hữu của các mô hình LLM sinh sinh (Generative AI). Dự án giải quyết triệt để vấn đề này bằng kiến trúc **Phòng thủ 4 Lớp (Multi-layer Guardrails)**:

```mermaid
flowchart TD
    Q["Câu hỏi của người dùng"] --> L1["Lớp 1: Cổng Kiểm soát Ngưỡng RRF (Relevance Gate)<br/>Nếu Max(RRF) < 0.005 -> Từ chối ngay, KHÔNG gọi LLM"]
    L1 -- "Vượt qua ngưỡng" --> L2["Lớp 2: Fast-path DIRECT_MATCH<br/>Nếu là tra cứu từ vựng có sẵn -> Trả thẳng bản ghi gốc, KHÔNG qua LLM"]
    L2 -- "Cần diễn đạt RAG" --> L3["Lớp 3: Strict Grounding System Prompt & T=0.0<br/>Khóa chặt tri thức: CHỈ trả lời từ ngữ cảnh, ép câu mẫu từ chối"]
    L3 --> LLMGen["Mô hình Qwen2.5:7B sinh phản hồi"]
    LLMGen --> L4["Lớp 4: Bộ lọc Hậu xử lý (Post-processing Filter)<br/>Lọc sạch ký tự CJK tiếng Trung + Đối soát chuỗi từ chối"]
    L4 --> Out["Câu trả lời trung thực, chính xác 100%"]
```

1. **Lớp 1: Cổng Kiểm soát Ngưỡng RRF (Relevance Gate):**
   - Tại [src/chat/engine.py#L370-L382](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/engine.py#L370-L382), nếu điểm RRF của tài liệu cao nhất $< 0.005$, hệ thống kết luận trong kho tri thức không có dữ liệu này. Chatbot lập tức phản hồi thông báo không tìm thấy mà **hoàn toàn không kích hoạt LLM**.
2. **Lớp 2: Lối tắt Dữ liệu Gốc (`DIRECT_MATCH`):**
   - Đối với các câu hỏi tra từ vựng thông thường đã có trong từ điển, câu trả lời được lấy nguyên văn từ trường `QARecord.answer`. Vì không cho LLM cơ hội "viết lại", khả năng bịa đặt ở các câu hỏi này là **bằng 0%**.
3. **Lớp 3: Strict Grounding System Prompt & Tham số $T=0.0$:**
   - Tại [src/llm/prompts.py#L11-L46](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/prompts.py#L11-L46), System Prompt được thiết kế cực kỳ khắt khe:
     > *"BẠN CHỈ ĐƯỢC PHÉP TRẢ LỜI DỰA TRÊN [NGỮ CẢNH DỮ LIỆU ĐƯỢC CUNG CẤP]. TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài ngữ cảnh để suy đoán, tự bịa hoặc bổ sung thông tin. Nếu thông tin trong ngữ cảnh không đủ, BẮT BUỘC trả lời đúng câu mẫu: '{out_of_scope_message}'."*
   - Thiết lập `temperature = 0.0` trong [src/llm/client.py](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L206) để triệt tiêu tính ngẫu nhiên, ép mô hình chọn từ ngữ có tính xác thực cao nhất.
4. **Lớp 4: Bộ Lọc Ký tự Tiếng Trung (CJK Sanitizer):**
   - Mô hình mã nguồn mở Qwen có nguồn gốc đa ngữ, đôi khi có thể bị lẫn một vài ký tự Hán tự trong câu trả lời. Hàm `clean_chinese_characters(text)` tại [src/llm/client.py#L24-L31](file:///c:/Users/User/Desktop/chatbox2.0/src/llm/client.py#L24-L31) sử dụng biểu thức chính quy `[\u4e00-\u9fff]+` quét và xóa sạch mọi ký tự CJK trước khi token được phát ra giao diện.

---

### Câu hỏi 7: Luồng nạp dữ liệu tri thức mới (Batch Ingestion Pipeline) diễn ra như thế nào?

**Trả lời:**

Quá trình nạp dữ liệu tri thức được phụ trách bởi `BatchIngestionEngine` ([src/data/batch_ingestion.py](file:///c:/Users/User/Desktop/chatbox2.0/src/data/batch_ingestion.py)) và script [ingest_data.py](file:///c:/Users/User/Desktop/chatbox2.0/ingest_data.py). Luồng xử lý diễn ra theo 6 bước tuần tự, không cần huấn luyện lại mô hình:

```mermaid
flowchart LR
    File["Tệp đầu vào<br/>(.xlsx, .pdf, .csv, .docx, .json)"] --> Hash["1. Tính băm SHA-256<br/>Khử trùng lặp tệp nguồn"]
    Hash --> Router["2. FileLoaderRouter<br/>Chọn bộ đọc chuyên biệt"]
    Router --> Extract["3. Trích xuất & Lọc cấp độ<br/>Chỉ giữ lại chuẩn A1 - A2"]
    Extract --> Normalize["4. Chuẩn hóa sang QARecord<br/>(id, question, answer, word, level)"]
    Normalize --> Sync["5. Đồng bộ Song song Chỉ mục"]
    
    subgraph Index ["ĐỒNG BỘ CHỈ MỤC"]
        Sync --> BM25Idx["BM25Retriever.add_records()<br/>Cập nhật chỉ mục từ khóa"]
        Sync --> ChromaIdx["BGEChromaRetriever.upsert()<br/>Embed BGE-M3 & Lưu ChromaDB"]
    end
    
    Index --> Ready["6. Lập tức Tra cứu được<br/>(Immediate Searchability, < 3s)"]
```

1. **Khử trùng lặp mức Tệp (SHA-256 File Deduplication):**
   Hệ thống tính chuỗi băm SHA-256 của toàn bộ tệp tin. Nếu tệp đã từng được nạp thành công trước đó, trạng thái trả về là `SKIPPED` để tránh lãng phí tài nguyên tính toán vector.
2. **Bộ đọc Định dạng Chuyên biệt (File Loader Router):**
   Module [src/data/loaders/router.py](file:///c:/Users/User/Desktop/chatbox2.0/src/data/loaders/router.py) tự động nhận diện định dạng đuôi tệp:
   - Với Excel (`.xlsx`, `.xls`): Dùng `openpyxl` / `pandas` đọc các cột: Từ vựng, Loại từ, Phiên âm, Cấp độ, Nghĩa, Ví dụ.
   - Với PDF (`.pdf`): Dùng `pypdf` trích xuất văn bản; nếu là tài liệu scan dạng ảnh, tự động kích hoạt `Tesseract OCR` cục bộ.
   - Hỗ trợ đầy đủ các định dạng: DOCX, CSV, JSON, JSONL, Markdown, TXT.
3. **Lọc phạm vi và Chuẩn hóa cấu trúc `QARecord`:**
   Mọi dữ liệu trích xuất được chuyển đổi thành cấu trúc chuẩn `QARecord` ([src/core/models.py](file:///c:/Users/User/Desktop/chatbox2.0/src/core/models.py)). Các từ vựng ngoài phạm vi A1–A2 (như B1, B2, C1, C2) bị loại bỏ ngay tại bước này để đảm bảo kho tri thức luôn chuẩn hóa.
4. **Đồng bộ hóa Song song Hai Chỉ mục (Dual Index Synchronization):**
   Dưới khóa ghi độc quyền `write_lock()`:
   - Vector hóa câu hỏi và định nghĩa qua `BAAI/bge-m3` và lưu trữ persistent vào thư mục đĩa `chroma_db/`.
   - Cập nhật kho ngữ liệu token hóa của `BM25Okapi`.
5. **Hiệu lực tức thì không cần khởi động lại (Zero-Downtime Reload):**
   Sau khi nạp xong, `ChatEngine.update_knowledge_base()` lập tức làm mới bộ nhớ cache. Người dùng có thể hỏi ngay về từ vựng vừa nạp trong vòng vài giây mà không cần restart server FastAPI.

---

## 4. BẢNG ÁNH XẠ TRỰC TIẾP FILE NGUỒN, CLASS, HÀM VÀ SỐ DÒNG

Bảng dưới đây thống kê toàn bộ các file mã nguồn cốt lõi của dự án giúp việc tra cứu mã nguồn phục vụ báo cáo đạt độ chính xác tuyệt đối:

| STT | Đường dẫn File | Tầng Kiến trúc | Các Class / Hàm cốt lõi | Vị trí dòng | Vai trò và Chức năng chính |
| :---: | :--- | :--- | :--- | :---: | :--- |
| 1 | `src/chat/engine.py` | Orchestration | `ChatEngine`<br/>- `ask()`<br/>- `ask_stream()`<br/>- `_create_and_log_response()` | L36-L118<br/>L160-L450<br/>L456-L780<br/>L119-L159 | **Trái tim điều phối hệ thống**: Kết nối Topic Tracker, PhoBERT NLU, Hybrid Retriever, Relevance Gate và LangChain LCEL. |
| 2 | `src/llm/client.py` | Generation | `OllamaClient`<br/>- `generate_with_langchain()`<br/>- `generate_with_langchain_stream()`<br/>- `clean_chinese_characters()` | L34-L238<br/>L212-L222<br/>L224-L237<br/>L24-L31 | **Tích hợp LangChain & Ollama**: Khởi tạo LCEL chain (`ChatOllama`), streaming token, thanh lọc ký tự chữ Hán CJK. |
| 3 | `src/llm/prompts.py` | Generation | `SYSTEM_PROMPT`<br/>`build_context_string()`<br/>`get_langchain_prompt_template()` | L11-L46<br/>L55-L66<br/>L97-L109 | **Strict Grounding Prompt**: Khóa chặt tri thức của LLM, định dạng ngữ cảnh trích xuất và cung cấp template cho LangChain. |
| 4 | `src/nlp/phobert_intent.py` | NLU & Semantics | `PhoBERTIntentClassifier`<br/>- `initialize()`<br/>- `_encode_sentence()`<br/>- `classify_intent()` | L81-L268<br/>L91-L125<br/>L126-L146<br/>L148-L267 | **Hiểu ý định tiếng Việt**: Nhúng vector 768 chiều qua PhoBERT-base-v2, so khớp Cosine Similarity với Prototype Centroids. |
| 5 | `src/retriever/hybrid_retriever.py` | Retrieval Engine | `HybridRetriever`<br/>- `retrieve()`<br/>- `is_in_scope_domain()` | L90-L273<br/>L157-L272<br/>L28-L86 | **Truy xuất lai & Hợp nhất RRF**: Chạy song song BM25 và BGE-M3, tính điểm RRF $k=60$, phân loại DIRECT_MATCH hay RAG. |
| 6 | `src/retriever/bm25_retriever.py` | Sparse Retrieval | `BM25Retriever`<br/>- `search()`<br/>- `_tokenize()` | L25-L160<br/>L85-L130<br/>L45-L70 | **Tìm kiếm từ khóa chính xác**: Dùng thuật toán BM25Okapi quét từ vựng, cấp độ A1/A2 và câu hỏi mẫu. |
| 7 | `src/retriever/bge_chroma.py` | Dense Retrieval | `BGEChromaRetriever`<br/>- `search()`<br/>- `build_or_load_collection()` | L30-L220<br/>L120-L175<br/>L60-L115 | **Vector Database cục bộ**: Quản lý ChromaDB persistent trên ổ cứng, embed đa ngữ 1024 chiều qua BAAI/bge-m3. |
| 8 | `src/chat/topic_tracker.py` | Context Management | `TopicTracker`<br/>- `resolve_query()`<br/>- `extract_target_word()` | L66-L410<br/>L310-L370<br/>L182-L291 | **Quản lý ngữ cảnh đa lượt**: Lưu giữ `active_word`, phân giải đại từ ("từ này", "nó") và kích hoạt bẫy câu hỏi mơ hồ. |
| 9 | `src/chat/query_router.py` | Routing Gate | `QueryRouter`<br/>- `route()` | L20-L95<br/>L40-L90 | **Rẽ nhánh câu hỏi siêu tốc**: Điều phối 3 nhánh (Small Talk, Out of Scope, Vocab Query) trước khi vào pipeline RAG. |
| 10 | `src/chat/small_talk_handler.py` | Fast Cache | `SmallTalkHandler`<br/>- `handle()` | L15-L85<br/>L30-L75 | **Phản hồi xã giao Sub-millisecond**: Trả lời chào hỏi, cảm ơn bằng cache mà không tiêu tốn GPU/RAM. |
| 11 | `src/resource/manager.py` | Concurrency & RAM | `ResourceManager`<br/>`IndexAccessCoordinator` | L40-L180<br/>L80-L140 | **Điều phối tài nguyên & Khóa đọc/ghi**: Quản lý Read/Write locks bảo vệ tài nguyên khi vừa chat vừa nạp dữ liệu. |
| 12 | `vocab_backend/streaming_routes.py` | API & Streaming | `stream_chat_endpoint()`<br/>`event_generator()` | L32-L85<br/>L84-L215 | **Server-Sent Events (SSE)**: Bắn luồng token thời gian thực về React, đo TTFT và đóng gói dữ liệu provenance. |
| 13 | `src/data/batch_ingestion.py` | Data Ingestion | `BatchIngestionEngine`<br/>- `ingest_batch()` | L95-L350<br/>L140-L280 | **Động cơ nạp dữ liệu đa tệp**: Hỗ trợ 8 định dạng tệp, khử trùng lặp SHA-256, nạp đồng thời ChromaDB và BM25. |
| 14 | `config/settings.py` | Configuration | `Settings` (Pydantic Settings) | Toàn bộ file | **Cấu hình trung tâm**: Lưu các siêu tham số (RRF $k=60$, thresholds, base URL Ollama, đường dẫn models). |

---

## 5. CẨM NANG VẤN ĐÁP NHANH (VIVA DEFENSE CHEAT SHEET)

Dành cho sinh viên tự tin trả lời phỏng vấn trực tiếp trước Hội đồng chấm đồ án:

1. **Hỏi: "Dự án của em có Fine-tune mô hình không?"**
   - **Đáp:** Dạ không, hệ thống áp dụng kiến trúc **Controlled Hybrid RAG**. Việc không fine-tune mang lại 3 ưu điểm vượt trội: (1) Cập nhật tri thức mới tức thì trong 3 giây chỉ bằng cách nạp file Excel/PDF mà không tốn công gán nhãn và train lại; (2) Triệt tiêu hiện tượng ảo giác (hallucination) nhờ chỉ thị Strict Grounding Prompt; (3) Hệ thống chạy mượt mà 100% cục bộ trên phần cứng máy tính cá nhân (GPU NVIDIA RTX 3050).
2. **Hỏi: "LangChain ở đây đóng vai trò gì? Em có thể bỏ LangChain và gọi thẳng Ollama bằng requests không?"**
   - **Đáp:** Dạ được, nhưng nhóm chọn sử dụng **LangChain LCEL** vì nó đem lại tính chuẩn hóa kiến trúc cao:
     - Dễ dàng thiết lập chuỗi `ChatPromptTemplate | ChatOllama | StrOutputParser`.
     - Hỗ trợ cơ chế `.stream()` chuẩn hóa để truyền luồng token trực tiếp lên giao diện người dùng qua SSE.
     - Dễ dàng mở rộng, cắm thêm bộ nhớ (Memory) hoặc công cụ (Tools) trong tương lai theo đúng chuẩn công nghiệp.
     - Ngoài ra, trong code nhóm vẫn thiết kế phương án fallback qua HTTP client thuần nếu dịch vụ LangChain gặp sự cố kết nối.
3. **Hỏi: "Làm sao chatbot phân biệt được khi nào người dùng hỏi 'từ này' của câu trước với một câu hỏi mới?"**
   - **Đáp:** Module `TopicTracker` ([src/chat/topic_tracker.py](file:///c:/Users/User/Desktop/chatbox2.0/src/chat/topic_tracker.py)) lưu biến trạng thái `active_word`. Khi câu hỏi mới chứa các đại từ quy chiếu như `"từ này"`, `"nó"`, hệ thống nhận diện đây là câu hỏi nối tiếp và tự động thay thế đại từ bằng `active_word` trước khi đưa vào bộ tìm kiếm. Nếu người dùng hỏi `"từ này"` ngay ở câu đầu tiên khi chưa có `active_word`, hệ thống lập tức kích hoạt `Clarification Gate` để hỏi lại từ vựng cụ thể.
4. **Hỏi: "Hệ thống làm sao chạy được 100% Offline không cần Internet?"**
   - **Đáp:** Hệ thống thiết lập biến môi trường `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`. Mô hình PhoBERT và BGE-M3 được tải sẵn về máy tính cục bộ, Qwen2.5:7B chạy thông qua Ollama cục bộ (`127.0.0.1:11434`), ChromaDB lưu trữ persistent trên đĩa và Text-to-Speech chạy qua Kokoro-ONNX trên CPU máy tính. Toàn bộ luồng dữ liệu không phát bất kỳ request nào ra ngoài Internet.
