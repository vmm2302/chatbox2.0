# HƯỚNG DẪN CÀI ĐẶT & THIẾT LẬP MÔI TRƯỜNG CHATBOX 2.0 TRÊN MÁY MỚI

Tài liệu này hướng dẫn chi tiết quy trình thiết lập toàn bộ môi trường từ đầu khi chuyển sang máy tính mới (Windows, macOS hoặc Linux) hoàn toàn thông qua **Terminal / Dòng lệnh**, không phụ thuộc vào bất kỳ tệp `.bat` nào.

---

## 1. YÊU CẦU HỆ THỐNG (PREREQUISITES)

| Thành phần | Yêu cầu khuyến nghị | Ghi chú |
| :--- | :--- | :--- |
| **Hệ điều hành** | Windows 10/11, Ubuntu 20.04+, macOS | Tương thích đa nền tảng |
| **Python** | **Python 3.10** hoặc **3.11** (Khuyên dùng 3.11) | Tải từ [python.org](https://www.python.org/downloads/) |
| **Git** | Phiên bản mới nhất | Tải từ [git-scm.com](https://git-scm.com/) |
| **Ollama** | Phiên bản mới nhất | Tải từ [ollama.com](https://ollama.com/) |
| **RAM** | Tối thiểu 8 GB (Khuyên dùng 16 GB) | Đủ để chạy mô hình LLM và Embedding |
| **Dung lượng đĩa** | Tối thiểu 15 GB trống | Lưu trữ các checkpoint mô hình NLP và LLM |

> [!IMPORTANT]
> Khi cài đặt Python trên Windows, hãy nhớ tích chọn **"Add Python to PATH"** để có thể chạy lệnh `python` từ bất kỳ cửa sổ dòng lệnh nào.

---

## 2. QUY TRÌNH THIẾT LẬP TỪNG BƯỚC (STEP-BY-STEP SETUP)

### Bước 1: Tải mã nguồn về máy (Clone Repository)

Mở Terminal (PowerShell / Command Prompt / Bash) và thực thi:

```bash
git clone https://github.com/vmm2302/chatbox2.0.git
cd chatbox2.0
```

---

### Bước 2: Tạo và kích hoạt môi trường ảo Python (`.venv`)

Tạo môi trường ảo độc lập để không ảnh hưởng đến các gói phần mềm hệ thống:

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo:

- **Trên Windows PowerShell:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *(Nếu gặp lỗi `Execution_Policies`, mở PowerShell với quyền Administrator và chạy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

- **Trên Windows Command Prompt (CMD):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

- **Trên macOS / Linux:**
  ```bash
  source .venv/bin/activate
  ```

> Khi kích hoạt thành công, bạn sẽ thấy tiền tố `(.venv)` xuất hiện ở đầu dòng lệnh Terminal.

---

### Bước 3: Cài đặt các thư viện bắt buộc (Dependencies)

Nâng cấp `pip` và cài đặt toàn bộ danh sách thư viện từ `requirements.txt`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Danh sách các thư viện chính bao gồm:
- **Giao diện Web:** `streamlit`, `gradio`
- **Vector & Tìm kiếm:** `chromadb`, `rank-bm25`
- **Mô hình NLP:** `torch`, `transformers`, `sentence-transformers`
- **Khung RAG & LLM:** `langchain-core`, `langchain-ollama`, `pydantic`
- **Xử lý tài liệu:** `pymupdf`, `pypdf`, `openpyxl`

---

### Bước 4: Thiết lập tệp cấu hình biến môi trường (`.env`)

Tạo tệp cấu hình `.env` từ tệp mẫu `.env.example`:

- **Windows PowerShell:**
  ```powershell
  Copy-Item .env.example .env
  ```
- **Windows CMD:**
  ```cmd
  copy .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

---

### Bước 5: Cài đặt Ollama & Tải mô hình LLM Qwen2.5:7B

1. Tải và cài đặt Ollama từ [https://ollama.com](https://ollama.com).
2. Khởi động dịch vụ Ollama trong Terminal (hoặc mở ứng dụng Ollama):
   ```bash
   ollama serve
   ```
3. Mở một cửa sổ Terminal mới và kéo mô hình:
   ```bash
   ollama pull qwen2.5:7b
   ```
   *(Nếu máy tính có cấu hình RAM dưới 8 GB, bạn có thể tải bản nhẹ hơn: `ollama pull qwen2.5:3b` hoặc `ollama pull qwen2.5:1.5b` và đổi tên model trong file `.env`)*

---

### Bước 6: Tải trước các mô hình NLP cục bộ (PhoBERT & BGE-M3)

Chạy script tải tự động các trọng số mô hình vào bộ nhớ đệm máy tính (hỗ trợ chạy 100% offline):

```bash
python scripts/download_models.py
```

Script này sẽ tải:
- **vinai/phobert-base-v2**: Nhận diện ý định câu hỏi (Query Understanding & Intent Routing).
- **BAAI/bge-m3**: Trích xuất đặc trưng ngữ nghĩa đa ngữ 1024 chiều cho ChromaDB.

---

### Bước 7: Đồng bộ & Chuẩn bị Kho Tri Thức (Knowledge Base)

Nếu bạn có tệp từ điển SQLite `dictionary_en_vi.db` và danh mục từ vựng `The_Oxford_3000_by_CEFR_level.pdf` trong thư mục `data/raw/`:

1. **Đồng bộ từ vựng Oxford 3000 & Từ điển SQLite vào JSONL:**
   ```bash
   python scripts/sync_oxford_knowledge.py
   ```

2. **Nạp thêm dữ liệu từ vựng mới từ tệp Excel / PDF / Word / CSV:**
   ```bash
   python ingest_data.py --file "data/raw/du_lieu_tu_vung_RAG_chuan_hoa_v3.xlsx" --mode append
   ```

---

## 3. KHỞI CHẠY ỨNG DỤNG TỪ TERMINAL (RUN APPLICATION)

Đảm bảo môi trường ảo `.venv` đã được kích hoạt trước khi chạy các lệnh sau:

### 1. Giao diện Web Streamlit (Khuyên dùng cho trải nghiệm Chatbox hiện đại)

```bash
streamlit run src/ui/app.py --server.port 8501
```
> Truy cập trình duyệt tại địa chỉ: **`http://localhost:8501`**  
> Giao diện hỗ trợ 4 Tabs: Tra cứu từ vựng, Cài đặt tham số RAG, Provenance Audit Inspector, và Quản trị kho tri thức đa tệp.

### 2. Giao diện Web Gradio (Phong cách Soft Slate chuẩn rag-chatbot-main)

```bash
python src/ui/gradio_app.py
```
> Truy cập trình duyệt tại địa chỉ: **`http://localhost:7860`**

### 3. Giao diện Dòng lệnh (Terminal CLI)

Dành cho kiểm tra nhanh không cần mở trình duyệt web:

```bash
python src/ui/cli.py
```

---

## 4. CHẠY BỘ KIỂM THỬ HỆ THỐNG (TESTING & VERIFICATION)

Để kiểm tra tính toàn vẹn của tất cả các module trên máy tính mới:

```bash
# Chạy toàn bộ các bài kiểm thử tự động
python -m unittest discover -s tests -p "test_*.py"

# Hoặc chạy kiểm thử các module cốt lõi:
python -m unittest tests.test_safety_gate tests.test_query_router tests.test_small_talk_handler tests.test_exception_handler tests.test_dictionary_db tests.test_oxford_pdf_loader tests.test_upsert_deduplication
```

---

## 5. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### 1. Lỗi PowerShell `running scripts is disabled on this system`
- **Nguyên nhân:** Chính sách bảo mật ExecutionPolicy mặc định của Windows PowerShell ngăn chặn script kích hoạt `.ps1`.
- **Cách khắc phục:** Mở PowerShell và chạy lệnh:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### 2. Lỗi `ConnectionRefusedError: [WinError 10061]` khi gọi Ollama
- **Nguyên nhân:** Dịch vụ Ollama chưa được khởi động trên máy tính.
- **Cách khắc phục:** Mở một cửa sổ Terminal và gõ `ollama serve`, hoặc mở ứng dụng Ollama từ Start Menu.

### 3. Lỗi hiển thị tiếng Việt trên Windows CMD
- **Cách khắc phục:** Chuyển mã trang CMD sang UTF-8 trước khi chạy:
  ```cmd
  chcp 65001
  ```

### 4. Lỗi thiếu VRAM / Máy tính không có card đồ họa rời (GPU)
- Hệ thống được cấu hình tự động nhận diện thiết bị (`device='cuda'` nếu có GPU NVIDIA, hoặc tự động fallback về `device='cpu'`).
- Với máy tính chỉ có CPU, mô hình Qwen2.5:7B chạy thông qua RAM hệ thống mượt mà hoặc bạn có thể chuyển sang model `qwen2.5:3b`.
