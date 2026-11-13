# BIÊN BẢN KIỂM THỬ VÀ NGHIỆM THU GIAO DIỆN NGƯỜI DÙNG (FRONTEND UAT REPORT)

## DỰ ÁN: CHATBOX 2.0 — TRỢ LÝ TRA CỨU TỪ VỰNG TIẾNG ANH

> **Môn học:** Xây dựng Chatbot AI bằng LangChain hoặc Rasa
> **Phân hệ nghiệm thu:** Giao diện Người dùng Web Frontend (Single Page Application)
> **Ngôn ngữ & Công nghệ:** React 19, Vite 8, Tailwind CSS v4, Lucide React, Server-Sent Events (SSE), Web Audio API
> **Tiêu chuẩn nghiệm thu:** Automated Build/Lint/Unit Test & Live Browser User Acceptance Testing (UAT)
> **Ngày thực hiện:** 2026-11-12

---

## 1. MÔI TRƯỜNG VÀ THIẾT BỊ NGHIỆM THU

- **Hệ điều hành kiểm thử:** Windows 11 (`Node.js v24.20.0`)
- **Máy chủ phục vụ gói tĩnh nghiệm thu:** FastAPI (`uvicorn vocab_backend.api_server:app`) phục vụ trực tiếp `vocab_frontend/dist/`
- **Độ phân giải màn hình kiểm thử thực tế trên trình duyệt:**
  - **Desktop:** 1280 × 800 px / 1920 × 1080 px
  - **Mobile:** 390 × 844 px (Kiểm tra `document.documentElement.scrollWidth <= window.innerWidth` và bounding box từng phần tử Header)

---

## 2. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG MÃ NGUỒN (AUTOMATED BUILD, LINT & UNIT TESTS)

Toàn bộ mã nguồn React được kiểm tra qua lệnh nghiệm thu tự động:

```bash
cd vocab_frontend
npm test
# Thực thi tuần tự: vite build && oxlint && node --test tests/*.test.mjs
```

- **Kết quả biên dịch Vite Bundler (`vite build`):** `✓ built in 714ms` — **0 errors** (`dist/index.html`, `dist/assets/*.css`, `dist/assets/*.js`)
- **Kết quả phân tích tĩnh Linter (`oxlint` trên 20 tệp):** **`Found 0 warnings and 0 errors`**
- **Kết quả Unit Test dịch vụ Frontend (`node --test tests/*.test.mjs`):** **`6 / 6 tests PASS`** (`API Auth Token & Session Lifecycle`, `CEFR Dynamic Styling & Theme Utils`)

---

## 3. BẢNG CHI TIẾT NGHIỆM THU CHỨC NĂNG GIAO DIỆN TRÊN TRÌNH DUYỆT (LIVE UAT CHECKLIST)

### 3.1. Phân hệ 1: Xác thực & Quản lý Phiên (Auth & Session Flow)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/AuthPage.jsx`, `vocab_frontend/src/services/api.js`, `vocab_frontend/src/App.jsx`

| STT | Kịch bản kiểm thử (Test Scenario) | Thao tác & Quan sát thực tế | Kết quả kỳ vọng | Đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **UAT-01** | Đăng nhập & lưu Access Token an toàn | Đăng nhập đúng tài khoản/mật khẩu | Chuyển vào `ChatView`, giữ Bearer Access Token trong bộ nhớ RAM (`authToken` ở `api.js`), không lưu phiên người dùng vào `localStorage` | **ĐẠT (PASS)** |
| **UAT-02** | Đăng ký tài khoản mới | Đăng ký tài khoản với username, display name, password, confirm password | Tạo tài khoản thành công, hiển thị thông báo chúc mừng và chuyển về tab Đăng nhập | **ĐẠT (PASS)** |
| **UAT-03** | Cô lập form Đăng nhập & Đăng ký | Nhập `draft_user` ở tab Đăng nhập rồi chuyển sang tab Đăng ký | Ô tên đăng nhập ở tab Đăng ký rỗng hoàn toàn (`""`), không bị điền chéo | **ĐẠT (PASS)** |
| **UAT-04** | Bắt lỗi đăng nhập sai | Nhập mật khẩu sai (`WrongPass1!`) | Backend trả `401 Unauthorized`, UI hiển thị thông báo lỗi rõ ràng, không crash | **ĐẠT (PASS)** |

---

### 3.2. Phân hệ 2: Giao diện Hội thoại Chatbot & Truyền luồng SSE

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/ChatView.jsx`, `vocab_frontend/src/components/VocabCard.jsx`, `vocab_frontend/src/components/SidebarHistory.jsx`

| STT | Kịch bản kiểm thử (Test Scenario) | Thao tác & Quan sát thực tế | Kết quả kỳ vọng | Đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **UAT-05** | Gửi câu hỏi & Optimistic UI | Nhấp chip gợi ý `"amazing"` | Tin nhắn người dùng hiển thị tức thì và bắt đầu luồng SSE | **ĐẠT (PASS)** |
| **UAT-06** | Truyền luồng SSE thời gian thực | Quan sát quá trình phản hồi | Hiển thị trạng thái streaming và hoàn tất render thẻ từ vựng không lỗi | **ĐẠT (PASS)** |
| **UAT-07** | Hiển thị thẻ từ vựng (`VocabCard`) | Kiểm tra nội dung thẻ `"amazing"` | Hiển thị đúng tiền tố `🎯 Từ bạn tìm kiếm: amazing`, badge `🌱 A1 · Khởi đầu`, IPA `/əˈmeɪzɪŋ/`, nghĩa tiếng Việt, ví dụ và nguồn tham chiếu | **ĐẠT (PASS)** |
| **UAT-08** | Lịch sử hội thoại & Đăng xuất | Mở sidebar `"Lịch sử chat"`, kiểm tra mục `"Hôm nay"`, bấm `"Đăng xuất"` | Hội thoại vừa tạo xuất hiện trong nhóm `"Hôm nay"`, sau khi đăng xuất quay về `AuthPage` an toàn | **ĐẠT (PASS)** |

---

### 3.3. Phân hệ 3: Phát âm Chuẩn Bản ngữ (Kokoro TTS Audio Player)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/VocabCard.jsx`, `vocab_frontend/src/components/DiscoveryView.jsx`, `vocab_frontend/src/services/tts.js`

| STT | Kịch bản kiểm thử (Test Scenario) | Thao tác & Quan sát thực tế | Kết quả kỳ vọng | Đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **UAT-09** | Phát âm từ vựng qua `/api/tts/synthesize` | Bấm nút `"Phát âm (US)"` trên thẻ từ vựng | Gọi API kèm Bearer token thành công, nút chuyển sang trạng thái `"Dừng phát"`, không phát sinh cảnh báo lỗi TTS | **ĐẠT (PASS)** |

---

### 3.4. Phân hệ 4: Khám phá Từ vựng Động (`DiscoveryView`)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/DiscoveryView.jsx`, `vocab_frontend/src/utils/cefr.js`

| STT | Kịch bản kiểm thử (Test Scenario) | Thao tác & Quan sát thực tế | Kết quả kỳ vọng | Đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **UAT-10** | Tải danh sách cấp độ động | Chuyển sang tab `"Khám phá từ vựng"` | Hiển thị động các cấp độ có trong KB thực tế (`A1: 1,766 từ`, `A2: 1,535 từ`) kèm 8 thẻ từ vựng | **ĐẠT (PASS)** |
| **UAT-11** | Đổi bộ từ ngẫu nhiên | Bấm nút `"Đổi bộ từ ngẫu nhiên"` | Danh sách 8 thẻ từ vựng được làm mới ngẫu nhiên ngay lập tức | **ĐẠT (PASS)** |

---

### 3.5. Phân hệ 5: Chủ đề Sáng/Tối & Responsive Mobile (`390 × 844`)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/Header.jsx`, `vocab_frontend/src/components/ThemeToggle.jsx`, `vocab_frontend/src/utils/theme.js`

| STT | Kịch bản kiểm thử (Test Scenario) | Thao tác & Quan sát thực tế | Kết quả kỳ vọng | Đánh giá |
| :---: | :--- | :--- | :--- | :---: |
| **UAT-12** | Chuyển đổi Chủ đề Sáng / Tối | Bấm nút chuyển Theme trên Desktop & nút chu kỳ Theme trên Mobile | Class `dark` trên thẻ `<html>` cập nhật tức thì giữa chế độ Hệ thống / Sáng / Tối | **ĐẠT (PASS)** |
| **UAT-13** | Responsive Mobile Header (`390 × 844`) | Thu nhỏ viewport về `390 × 844` và đo bounding box Header | `scrollWidth === 390px` (`0px` tràn ngang); thương hiệu `VocabChat` (`x<=128.5px`), nút `Chat` (`x<=220.7px`), nút `Khám phá` (`x<=336.0px`) và nút Theme (`x<=381.0px`) nằm gọn 100% trong khung `390px` | **ĐẠT (PASS)** |

---

### 3.6. Phân hệ 6: Bảng Điều Khiển Quản Trị Viên (`AdminPanel`)

*Tệp nguồn phụ trách:* `vocab_frontend/src/components/AdminPanel.jsx`, `vocab_frontend/src/components/ConfirmModal.jsx`

- Luồng bảo vệ phân quyền: Tài khoản `user` bị chặn truy cập các endpoint `/api/admin/*` với `403 Forbidden`, giao diện `App.jsx` hiển thị màn hình từ chối khi truy cập `?page=admin` với vai trò không phải `admin`.
- Toàn bộ API gọi từ `AdminPanel.jsx` gửi `Authorization: Bearer <token>` qua `authFetch` và tự động đăng xuất khi token bị thu hồi (`401`).

---

## 4. TỔNG KẾT VÀ KẾT LUẬN NGHIỆM THU

- **Kiểm thử tự động Frontend (`npm test`):** `vite build` 0 errors, `oxlint` **0 warnings / 0 errors**, `node --test` **6/6 PASS**.
- **Kiểm thử trực tiếp trên trình duyệt:** Toàn bộ kịch bản người dùng (Auth, SSE Chat, VocabCard, TTS, Discovery, Theme, History/Logout, Mobile 390×844) đều **ĐẠT (PASS)** với **0 lỗi JavaScript console**.

**KẾT LUẬN:** Phân hệ giao diện Frontend React của dự án **Chatbox 2.0** đã được kiểm thử tự động và nghiệm thu trực quan đầy đủ trên trình duyệt, sẵn sàng vận hành ổn định.
