# BIÊN BẢN KIỂM THỬ VÀ NGHIỆM THU GIAO DIỆN NGƯỜI DÙNG (FRONTEND UAT REPORT)

## DỰ ÁN: CHATBOX 2.0 — TRỢ LÝ TRA CỨU TỪ VỰNG TIẾNG ANH (A1 - A2)

> **Môn học:** Xây dựng Chatbot AI bằng LangChain hoặc Rasa
> **Phân hệ nghiệm thu:** Giao diện Người dùng Web Frontend (Single Page Application)
> **Ngôn ngữ & Công nghệ:** React 19, Vite 8, Tailwind CSS v4, Lucide React, Server-Sent Events (SSE), Web Audio API
> **Tiêu chuẩn nghiệm thu:** User Acceptance Testing (UAT) & Responsive Multi-Device UI Checklist
> **Ngày thực hiện:** Tháng 11 / 2026

---

## 1. MÔI TRƯỜNG VÀ THIẾT BỊ NGHIỆM THU

Biên bản này ghi nhận kết quả kiểm thử thực tế của toàn bộ các màn hình và tính năng giao diện người dùng trên các môi trường sau:

- **Hệ điều hành kiểm thử:** Windows 10/11, macOS, Ubuntu Linux.
- **Trình duyệt kiểm thử:** Google Chrome (v125+), Microsoft Edge (v125+), Mozilla Firefox (v126+).
- **Độ phân giải màn hình kiểm thử:**
  - **Màn hình lớn (Desktop / Laptop Full):** 1920 × 1080 px và 1366 × 768 px.
  - **Màn hình chia đôi (Half Screen Multitasking):** 960 × 1080 px (Kiểm tra chống co cụm / gãy chữ).
  - **Màn hình Tablet:** 768 × 1024 px.
  - **Màn hình Mobile:** 390 × 844 px.

---

## 2. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG MÃ NGUỒN (AUTOMATED BUILD & LINTING VERIFICATION)

Trước khi nghiệm thu trực quan, toàn bộ mã nguồn React được kiểm tra cú pháp và khả năng đóng gói tự động:

```bash
cd vocab_frontend
npm test
```

- **Kết quả biên dịch Vite Bundler:** `✓ built in 600ms - 0 errors`
- **Kết quả phân tích tĩnh Linter (Oxlint):** `0 warnings, 0 errors`
- **Gói đầu ra nghiệm thu:** Thư mục tĩnh `vocab_frontend/dist/` được nạp trực tiếp qua FastAPI Server mà không có bất kỳ lỗi Runtime Console nào.

---

## 3. BẢNG CHI TIẾT NGHIỆM THU CHỨC NĂNG GIAO DIỆN (UAT CHECKLIST)

### 3.1. Phân hệ 1: Xác thực & Quản lý Phiên (Auth & Session Flow)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/AuthPage.jsx`

|       STT       | Kịch bản kiểm thử (Test Scenario)   | Thao tác thực hiện                                                        | Kết quả kỳ vọng                                                                               | Kết quả thực tế               |      Đánh giá      |
| :--------------: | :-------------------------------------- | :--------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------ | :-------------------------------- | :--------------------: |
| **UAT-01** | Đăng nhập tài khoản                | Nhập username/password đúng và bấm "Đăng nhập"                       | Chuyển ngay vào giao diện Chat chính, lưu Session vào localStorage                          | Đúng kỳ vọng, mượt mà      | **ĐẠT (PASS)** |
| **UAT-02** | Đăng ký tài khoản mới             | Nhập tài khoản, mật khẩu, xác nhận mật khẩu và bấm "Đăng ký"   | Tạo tài khoản thành công và hiển thị thông báo chúc mừng                              | Tạo tài khoản chuẩn xác      | **ĐẠT (PASS)** |
| **UAT-03** | Cô lập form Đăng nhập & Đăng ký | Nhập tài khoản ở form Đăng nhập rồi chuyển tab sang form Đăng ký | Dữ liệu giữa 2 form được cô lập hoàn toàn, không bị tự động điền chéo giá trị | Không còn bị điền chéo form | **ĐẠT (PASS)** |
| **UAT-04** | Bắt lỗi đăng nhập sai              | Nhập mật khẩu không đúng                                               | Hiển thị thông báo lỗi màu đỏ rõ ràng, không làm crash trang                          | Bắt lỗi chính xác             | **ĐẠT (PASS)** |

---

### 3.2. Phân hệ 2: Giao diện Hội thoại Chatbot & Truyền luồng SSE

*Tệp nguồn phụ trách:* `ChatView.jsx`, `MessageList.jsx`, `ChatInput.jsx`, `SidebarHistory.jsx`

|       STT       | Kịch bản kiểm thử (Test Scenario)                  | Thao tác thực hiện                                               | Kết quả kỳ vọng                                                                                                               | Kết quả thực tế        |      Đánh giá      |
| :--------------: | :----------------------------------------------------- | :------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------- | :------------------------- | :--------------------: |
| **UAT-05** | Gửi tin nhắn tức thì (Optimistic UI)               | Nhập từ vựng `"happy"` và bấm gửi                           | Tin nhắn người dùng xuất hiện trên màn hình ngay lập tức, ô nhập liệu được xóa trắng sẵn sàng cho câu tiếp | Không độ trễ (0ms)     | **ĐẠT (PASS)** |
| **UAT-06** | Hiệu ứng gõ chữ thời gian thực (SSE Streaming)   | Quan sát bot sinh câu trả lời                                   | Chữ xuất hiện dần dần từng token theo thời gian thực (hiệu ứng typing giống ChatGPT)                                   | Truyền luồng mượt mà  | **ĐẠT (PASS)** |
| **UAT-07** | Hiển thị thẻ từ vựng trực quan (Structured Card) | Tra cứu một từ vựng A1/A2 cụ thể                              | Hiển thị thẻ từ vựng với phiên âm IPA, cấp độ CEFR, các tầng nghĩa và câu ví dụ thực tế                       | Render thẻ chuẩn đẹp   | **ĐẠT (PASS)** |
| **UAT-08** | Lịch sử hội thoại bên thanh Sidebar               | Bấm vào các cuộc trò chuyện cũ hoặc bấm "Đoạn chat mới" | Tải lại chính xác nội dung phiên chat cũ hoặc xóa trắng màn hình tạo phiên mới                                     | Tải lịch sử chuẩn xác | **ĐẠT (PASS)** |

---

### 3.3. Phân hệ 3: Phát âm Chuẩn Bản ngữ (Kokoro TTS Audio Player)

*Tệp nguồn phụ trách:* `VocabularyCard.jsx`, `DiscoveryView.jsx`, `services/tts.js`

|       STT       | Kịch bản kiểm thử (Test Scenario)    | Thao tác thực hiện                                  | Kết quả kỳ vọng                                                                                        | Kết quả thực tế                      |      Đánh giá      |
| :--------------: | :--------------------------------------- | :----------------------------------------------------- | :--------------------------------------------------------------------------------------------------------- | :--------------------------------------- | :--------------------: |
| **UAT-09** | Phát âm từ vựng tại Thẻ Chat       | Nhấp vào biểu tượng loa phát âm cạnh từ vựng | Âm thanh giọng chuẩn Mỹ `af_heart` phát ra rõ ràng, nút loa đổi trạng thái animate sóng âm | Âm thanh phát trong trẻo, không trễ | **ĐẠT (PASS)** |
| **UAT-10** | Bộ nhớ đệm âm thanh (Audio Caching) | Nhấp lại nút loa lần thứ hai cho cùng một từ   | Âm thanh phát lại ngay lập tức (0ms) từ bộ nhớ đệm mà không gọi lại mạng                    | Phản hồi tức thì                     | **ĐẠT (PASS)** |

---

### 3.4. Phân hệ 4: Khám phá Từ vựng & Layout Nút Động

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/DiscoveryView.jsx`

|       STT       | Kịch bản kiểm thử (Test Scenario)              | Thao tác thực hiện                                                       | Kết quả kỳ vọng                                                                                                                                                      | Kết quả thực tế              | Đánh giá            |  |
| :--------------: | :------------------------------------------------- | :-------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------- | :--------------------- | :-: |
| **UAT-11** | Tiêu đề & Mô tả tinh gọn                     | Chuyển sang tab "Khám phá từ vựng"                                     | Tiêu đề hiển thị `"🌟 Khám Phá Từ Vựng"`, mô tả gọn gàng không bị lặp chữ rườm rà                                                                  | Giao diện thanh thoát          | **ĐẠT (PASS)** |  |
| **UAT-12** | Layout 2 nút A1/A2 tỷ lệ 50/50 lấp đầy khung | Quan sát 2 nút cấp độ "🌱 A1 – Khởi đầu" và "📘 A2 – Nền tảng" | 2 nút trải dài lấp đầy 100% chiều rộng khung chứa theo tỷ lệ 50/50, chiều cao thon gọn (`py-2.5 sm:py-3`), chữ bên trái và số lượng từ bên phải | Nút cân đối, rất đẹp mắt | **ĐẠT (PASS)** |  |
| **UAT-13** | Nút "Đổi bộ từ ngẫu nhiên"                  | Bấm nút Refresh ở góc trên bên phải                                  | Danh sách 8 thẻ từ vựng mới được tải về kèm hiệu ứng xoay tròn tải dữ liệu                                                                              | Tải từ mới ngẫu nhiên tốt  | **ĐẠT (PASS)** |  |

---

### 3.5. Phân hệ 5: Bảng Điều Khiển Quản Trị Viên (Admin Portal)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/AdminPanel.jsx`, `App.jsx`

|       STT       | Kịch bản kiểm thử (Test Scenario)              | Thao tác thực hiện                                            | Kết quả kỳ vọng                                                                                                                                      | Kết quả thực tế         |      Đánh giá      |
| :--------------: | :------------------------------------------------- | :--------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------- | :--------------------: |
| **UAT-14** | Thanh 4 Tab con trượt ngang (Sub-tabs)           | Xem thanh chọn Tab chức năng tại trang Admin                 | 4 Tab con nằm trên 1 hàng ngang trượt êm ái, không bị rớt dòng lộn xộn                                                                      | Trượt ngang mượt mà    | **ĐẠT (PASS)** |
| **UAT-15** | Bảng dữ liệu chống gãy chữ khi thu nhỏ      | Thu nhỏ cửa sổ trình duyệt xuống 900px                     | Bảng Người dùng, Bảng Nguồn tài liệu và Nhật ký Audit có thanh cuộn ngang an toàn (`min-w-[850px]`), chữ không bị bóp méo gãy dọc | Không bị gãy chữ        | **ĐẠT (PASS)** |
| **UAT-16** | Nạp nhiều tệp tài liệu (Multi-file Ingestion) | Kéo thả cùng lúc 2 file `.xlsx` / `.csv` vào khung nạp | Hiển thị danh sách tệp chờ nạp, có nút xóa từng tệp và nút nạp tất cả                                                                    | Nạp nhiều tệp hoàn hảo | **ĐẠT (PASS)** |
| **UAT-17** | Xóa nguồn tài liệu an toàn                    | Bấm nút "Xóa" tại bảng Nguồn tài liệu đang hoạt động | Xuất hiện hộp thoại Modal xác nhận nguy hiểm trước khi xóa thật khỏi CSDL                                                                    | Xác nhận xóa an toàn    | **ĐẠT (PASS)** |

---

### 3.6. Phân hệ 6: Trải nghiệm Giao diện Đa nền tảng & Chủ đề (Responsive & Theme)

*Tệp nguồn phụ trách:* `Header.jsx`, `ThemeToggle.jsx`, `index.css`

|       STT       | Kịch bản kiểm thử (Test Scenario)                    | Thao tác thực hiện                              | Kết quả kỳ vọng                                                                                                    | Kết quả thực tế    |      Đánh giá      |
| :--------------: | :------------------------------------------------------- | :------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------- | :--------------------- | :--------------------: |
| **UAT-18** | Chuyển đổi Chủ đề Sáng / Tối (Light & Dark Mode) | Bấm nút chuyển Theme (Mặt trời / Mặt trăng) | Toàn bộ giao diện đổi màu đồng bộ tức thì, không bị chớp nháy màu, thanh cuộn ẩn nút mũi tên xấu | Đổi theme mượt mà | **ĐẠT (PASS)** |

---

## 4. TỔNG KẾT VÀ KẾT LUẬN NGHIỆM THU

- **Tổng số kịch bản kiểm thử thực tế:** **18 / 18 ca ĐẠT (PASS)** — Tỷ lệ đạt: **100%**.
- **Độ ổn định giao diện:** Không phát sinh lỗi JavaScript console, không tràn viền màn hình (overflow horizontal bug), tải trang mượt mà dưới 1 giây.
- **Đánh giá trải nghiệm người dùng (UX/UI):** Giao diện hiện đại, trực quan, hỗ trợ đầy đủ các thao tác tra cứu, học tập, phát âm và quản trị hệ thống.

**KẾT LUẬN:** Phân hệ giao diện Frontend React của dự án **Chatbox 2.0** đáp ứng đầy đủ và vượt mức các tiêu chí nghiệm thu bài tập lớn.
