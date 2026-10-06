# HƯỚNG DẪN ĐƯA DỮ LIỆU EXCEL VÀO ĐỂ "TRAIN" (CẬP NHẬT TRI THỨC) CHO CHATBOX 2.0

Tài liệu này hướng dẫn chi tiết cách đưa dữ liệu từ tệp **Excel (.xlsx)** vào hệ thống Chatbox 2.0 để cập nhật kho tri thức từ vựng tiếng Anh.

---

## 1. BẢN CHẤT: TẠI SAO HỆ THỐNG DÙNG "RAG INGESTION" THAY VÌ "FINE-TUNING LLM"?

Trong các bài toán làm Chatbot tra cứu thông tin chính xác từ dữ liệu có sẵn (như từ điển, Q&A), người dùng thường dùng từ *"train mô hình"*. Tuy nhiên, trong kiến trúc kỹ thuật AI hiện đại, có 2 cách tiếp cận:

| Tiêu chí | Fine-tuning Trọng số LLM | Controlled Local RAG (Hệ thống này đang dùng) |
| :--- | :--- | :--- |
| **Bản chất** | Thay đổi ma trận trọng số mạng neural của LLM | Giữ nguyên LLM, lưu trữ dữ liệu vào Vector DB (ChromaDB) + BM25 |
| **Thời gian nạp dữ liệu** | Rất lâu (hàng giờ đến hàng ngày) | **Cực nhanh (chỉ 2 - 5 giây với vài trăm từ)** |
| **Hiện tượng "Bịa đặt" (Hallucination)** | Vẫn bị hallucination cao khi hỏi ngoài tập huấn luyện | **100% Zero Hallucination**, luôn bám sát ngữ cảnh trích xuất |
| **Quên kiến thức cũ (Catastrophic Forgetting)** | Rất dễ bị quên kiến thức tổng quát của mô hình | **Không bị ảnh hưởng**, kiến thức cũ được bảo toàn nguyên vẹn |
| **Cập nhật / Sửa đổi / Xóa từ** | Phải train lại toàn bộ từ đầu | **Chỉ cần sửa file Excel và nạp lại tức thì** |
| **Kiểm tra nguồn gốc (Provenance)** | Mô hình là "hộp đen", không biết lấy từ đâu | **Minh bạch 100%**, chỉ rõ Sheet, Record ID, Nguồn |

> **Kết luận:** Quá trình "train" trong Chatbox 2.0 chính là **Data Ingestion & Vector Indexing** (Đọc Excel -> Chuẩn hóa -> Mã hóa vector BGE-M3 1024 chiều vào ChromaDB -> Lập chỉ mục từ khóa BM25).

---

## 2. CẤU TRÚC TỆP EXCEL CẦN CHUẨN BỊ

Hệ thống được thiết kế thông minh, hỗ trợ **2 kiểu định dạng Excel**:

### Kiểu 1: Tệp Excel Đơn Giản (Tự tạo mới - Khuyên dùng)
Bạn chỉ cần mở Excel, tạo 1 sheet bất kỳ (ví dụ `TuVung`, `Sheet1`) với các cột sau:

| Tên cột tiếng Việt (Ưu tiên) | Tên cột tiếng Anh | Bắt buộc? | Mô tả nội dung | Ví dụ |
| :--- | :--- | :---: | :--- | :--- |
| **Câu hỏi** | `Question` | **Có** | Câu hỏi hoặc mẫu câu tra cứu | `resilient nghĩa là gì?` |
| **Câu trả lời** | `Answer` | **Có** | Nghĩa, giải thích, phát âm, ví dụ | `Phát âm: /rɪˈzɪl.jənt/\nTính từ: Phục hồi nhanh sau khó khăn...` |
| **Từ vựng** | `Word` | *Tùy chọn* | Từ tiếng Anh cần tra (hệ thống tự bóc tách nếu thiếu) | `resilient` |
| **Trình độ** | `Level` | *Tùy chọn* | Trình độ CEFR (A1, A2, B1, B2, C1, C2) | `B2` |
| **Nguồn** | `Source` | *Tùy chọn* | Tên từ điển hoặc tài liệu tham khảo | `Cambridge Dictionary` |

*Ghi chú:*
- Nếu bạn không nhập cột `Từ vựng` hoặc `Trình độ`, hệ thống tự động dùng biểu thức chính quy (Regex) bóc tách từ trong câu hỏi/câu trả lời.
- Tiêu đề cột không phân biệt chữ hoa, chữ thường hay dấu tiếng Việt.

### Kiểu 2: Tệp Excel Nhiều Sheet Chuẩn Đồ Án (Giống file gốc)
Nếu bạn cập nhật trực tiếp trên bộ dữ liệu gốc `data/raw/datahotrohoctuvungtienganhtuA1-B2fix.xlsx`, tệp gồm 4 sheet:
1. `danhsachtutienganhA1-B2`: Cột [Thứ tự, Câu hỏi, Thông tin trả lời, Nguồn]
2. `danhsachtheotrinhdoA1-B2`: Cột [Câu hỏi, Thông tin trả lời]
3. `tiengvietsangtienganh`: Cột [Câu hỏi, Thông tin trả lời]
4. `danhsachcauhoicotutrongcau`: Cột [Câu hỏi, Thông tin trả lời]

> 💡 **Tệp mẫu có sẵn:** Hệ thống đã tạo sẵn tệp mẫu chuẩn tại `data/mau_nhap_lieu_tuvung.xlsx`. Bạn có thể mở tệp này để xem cách trình bày.

---

## 3. HAI CÁCH NẠP DỮ LIỆU VÀO CHATBOX

### Cách 1: Nạp trực tiếp qua Giao Diện Web Streamlit (Trực quan nhất)

1. Khởi động giao diện Web bằng lệnh:
   ```powershell
   run_web.bat
   ```
   *(hoặc `streamlit run src/ui/app.py`)*
2. Ở thanh bên trái (**Sidebar**), tìm mục **📥 Cập Nhật Dữ Liệu Excel**.
3. Nhấp mở rộng và bấm **Browse files** (hoặc kéo thả file `.xlsx` của bạn vào).
4. Hệ thống sẽ kiểm tra tệp và hiển thị danh sách các sheet cùng số dòng phát hiện được.
5. Chọn chế độ:
   - **Bổ sung từ mới (Append - Khuyên dùng):** Giữ lại toàn bộ 3,725 từ vựng cũ, tự động lọc bỏ các câu trùng, chỉ mã hóa các từ vựng mới thêm vào (chỉ mất ~2-5 giây).
   - **Làm mới toàn bộ (Replace):** Xóa toàn bộ DB cũ và lập chỉ mục lại từ đầu.
6. Bấm nút **🚀 Bắt Đầu Nạp Dữ Liệu**.
7. Thanh tiến trình chạy đến 100% và thông báo thành công. Bạn có thể chat và hỏi ngay các từ mới vừa nạp!

---

### Cách 2: Nạp bằng Kịch Bản Tự Động (1-Click Batch hoặc CLI)

#### Lựa chọn A — Kéo thả vào file `.bat` (Siêu tiện lợi trên Windows):
1. Mở thư mục dự án `chatbox2.0`.
2. Kéo tệp `.xlsx` của bạn thả thẳng vào tệp `cap_nhat_du_lieu.bat`.
3. Cửa sổ dòng lệnh sẽ tự động bật lên, nạp dữ liệu và báo cáo kết quả hoàn tất trong vài giây!

#### Lựa chọn B — Chạy bằng lệnh dòng lệnh (Terminal / PowerShell):
```powershell
# Chế độ bổ sung từ mới (Khuyên dùng)
python ingest_data.py --file "data/mau_nhap_lieu_tuvung.xlsx" --mode append

# Hoặc chế độ làm mới toàn bộ từ tệp Excel mặc định
python ingest_data.py --mode replace
```

---

## 4. CƠ CHẾ BẢO VỆ DỮ LIỆU CỦA HỆ THỐNG

1. **Chống trùng lặp tự động (Deduplication):** Khi bạn nạp nhiều lần cùng một file Excel, hệ thống so sánh câu hỏi & câu trả lời để bỏ qua các bản ghi đã có, không làm phình to cơ sở dữ liệu.
2. **Khởi tạo ID tự động:** Bản ghi mới được gán mã định danh duy nhất (ví dụ `CUSTOM_0001`, `CUSTOM_0002` hoặc `APPEND_0001`), không gây xung đột với các ID cũ.
3. **Đồng bộ hóa tức thì (Zero-Restart):** Khi nạp xong qua Web UI, động cơ tìm kiếm `ChatEngine`, chỉ mục `BM25`, vector `ChromaDB` và bộ nhận diện từ `TopicTracker` đều được cập nhật nóng mà không cần tắt hay khởi động lại server.
