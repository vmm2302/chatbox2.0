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

### Bước 2: Cài đặt các thư viện bắt buộc (Dependencies)

> [!WARNING]
> **LƯU Ý QUAN TRỌNG VỀ MÔI TRƯỜNG ẢO VÀ LỆNH NÂNG CẤP PIP TRÊN WINDOWS:**  
> - **Không tạo môi trường ảo `.venv`:** Khuyến nghị cài đặt trực tiếp vào môi trường Python của hệ thống.
> - **Tuyệt đối KHÔNG chạy lệnh `python -m pip install --upgrade pip`:** Trên hệ điều hành Windows, khi pip tự cập nhật (đặc biệt trong môi trường ảo `.venv`), cơ chế khóa tệp (file locking) của Windows sẽ chặn tiến trình ghi đè. Pip tự động đổi tên thư mục chính của nó thành `~ip` để chuẩn bị thay thế nhưng bị ngắt quãng.
> - **Hậu quả:** Thư mục `pip` bị mất (chỉ còn thư mục lỗi `~ip`), khiến tất cả các lệnh `pip` hoặc `python -m pip` sau đó đều lập tức báo lỗi: `No module named pip` và không thể tiếp tục cài đặt bất kỳ thư viện nào.
> - Cài đặt trực tiếp không qua `.venv` vừa loại bỏ hoàn toàn rủi ro này, vừa giúp bạn không gặp lỗi chính sách chặn script (`ExecutionPolicy`) của Windows PowerShell.

Cài đặt toàn bộ danh sách thư viện từ `requirements.txt`:

```bash
pip install -r requirements.txt
```
*(Hoặc `python -m pip install -r requirements.txt`)*

> [!TIP]
> **Kích hoạt GPU cho BGE-M3 (Khuyên dùng nếu máy có card NVIDIA RTX / GTX):**  
> Mặc định pip cài bản PyTorch CPU. Để tăng tốc độ mã hóa dữ liệu gấp **15 – 20 lần** (từ 240+ từ/giây) và giải phóng 100% CPU/RAM, hãy chạy thêm lệnh:
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cu124
> ```
> Hệ thống sẽ tự động nhận diện và đẩy toàn bộ tác vụ Embedding sang card đồ họa NVIDIA.

Danh sách các thư viện chính bao gồm:
- **Giao diện Web:** `streamlit`, `gradio`
- **Vector & Tìm kiếm:** `chromadb`, `rank-bm25`
- **Mô hình NLP:** `torch`, `transformers`, `sentence-transformers`
- **Khung RAG & LLM:** `langchain-core`, `langchain-ollama`, `pydantic`
- **Xử lý tài liệu:** `pymupdf`, `pypdf`, `openpyxl`

---

### Bước 3: Thiết lập tệp cấu hình biến môi trường (`.env`)

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

### Bước 4: Cài đặt Ollama & Tải mô hình LLM Qwen2.5:7B

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

### Bước 5: Tải trước các mô hình NLP cục bộ (PhoBERT & BGE-M3)

Chạy script tải tự động các trọng số mô hình vào bộ nhớ đệm máy tính (hỗ trợ chạy 100% offline):

```bash
python scripts/download_models.py
```

Script này sẽ tải:
- **vinai/phobert-base-v2**: Nhận diện ý định câu hỏi (Query Understanding & Intent Routing).
- **BAAI/bge-m3**: Trích xuất đặc trưng ngữ nghĩa đa ngữ 1024 chiều cho ChromaDB.

---

### Bước 6: Đồng bộ & Khởi tạo Chỉ mục Kho Tri Thức (ChromaDB & BM25)

Sau khi clone repo mới, cơ sở dữ liệu vector ChromaDB chưa được tạo sẵn để tiết kiệm dung lượng repo.

1. **Khởi tạo cơ sở dữ liệu Vector ChromaDB và BM25 từ tệp Q&A có sẵn:**
   ```bash
   python ingest_data.py --file "data/processed/qa_records.jsonl" --mode replace
   ```

2. **(Tùy chọn) Đồng bộ lại từ tệp Oxford 3000 PDF & Từ điển SQLite:**
   ```bash
   python scripts/sync_oxford_knowledge.py
   ```

3. **(Tùy chọn) Nạp thêm dữ liệu từ vựng mới từ tệp Excel / PDF / Word / CSV:**
   ```bash
   python ingest_data.py --file "data/raw/du_lieu_tu_vung_RAG_chuan_hoa_v3.xlsx" --mode append
   ```

4. **Khởi tạo tài khoản Quản trị viên (Admin) đầu tiên:**
   ```bash
   python scripts/create_admin.py
   ```
   > Script sẽ yêu cầu nhập tên đăng nhập và mật khẩu an toàn qua console (không hiển thị ký tự mật khẩu). Mật khẩu được băm một chiều bằng Bcrypt trước khi ghi vào cơ sở dữ liệu `data/app_data.db`.

> [!TIP]
> **Nhận diện PDF dạng scan (Tùy chọn OCR):**  
> Dự án hỗ trợ trích xuất văn bản từ trang scan qua OCR cục bộ (`pytesseract`). Để sử dụng, hãy cài đặt [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) (hoặc `sudo apt install tesseract-ocr` trên Ubuntu). Nếu chưa cài, hệ thống vẫn xử lý văn bản bình thường và bỏ qua OCR kèm cảnh báo rõ ràng.

---

## 3. KHỞI CHẠY ỨNG DỤNG TỪ TERMINAL (RUN APPLICATION)

Mở Terminal tại thư mục gốc của dự án (`chatbox2.0`) và thực thi các lệnh sau:

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
# 1. Chạy bộ kiểm thử Xác thực, Phân quyền RBAC & Cách ly Dữ liệu (Mới):
python -m unittest tests.test_auth_rbac_isolation

# 2. Chạy toàn bộ các bài kiểm thử tự động:
python -m unittest discover -s tests -p "test_*.py"

# Hoặc chạy kiểm thử các module cốt lõi:
python -m unittest tests.test_safety_gate tests.test_query_router tests.test_small_talk_handler tests.test_exception_handler tests.test_dictionary_db tests.test_oxford_pdf_loader tests.test_upsert_deduplication
```

---

## 5. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### 1. Lỗi `No module named pip` hoặc xuất hiện thư mục lỗi `~ip`
- **Nguyên nhân:** Lỗi kinh điển trên Windows khi chạy lệnh `python -m pip install --upgrade pip` (đặc biệt trong môi trường ảo `.venv`). Cơ chế khóa tệp (file locking) của Windows chặn tiến trình ghi đè tập tin đang chạy, pip tự đổi tên thư mục chính thành `~ip` để chuẩn bị thay thế nhưng bị ngắt quãng giữa chừng, làm mất module `pip`.
- **Cách khắc phục:**
  - **Nếu gặp trong thư mục `.venv`:** Xóa sạch thư mục `.venv` bị lỗi:
    - CMD: `rmdir /s /q .venv`
    - PowerShell: `Remove-Item -Recurse -Force .venv`  
    Sau đó cài đặt trực tiếp vào Python máy: `pip install -r requirements.txt` (không cần và không nên tạo lại `.venv`).
  - **Nếu gặp trên Python hệ thống của máy:** Truy cập thư mục `site-packages` (ví dụ `C:\Python311\Lib\site-packages`), tìm thư mục `~ip` và đổi tên lại thành `pip`, hoặc chạy lệnh khôi phục:
    ```bash
    python -m ensurepip --default-pip
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
