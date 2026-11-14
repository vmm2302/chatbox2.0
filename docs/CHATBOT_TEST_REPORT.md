# BÁO CÁO KẾT QUẢ KIỂM THỬ ĐỘNG HỘI THOẠI THEO RUBRIC
## DỰ ÁN: CHATBOX 2.0 — LOCAL VOCABULARY ASSISTANT

> **Ngày thực thi:** 2026-11-14 18:00:46
> **Môi trường thực thi:** Python 3.11.9 | Seed lấy mẫu: `1794654014` | Ollama Online: `True`
> **Quy mô KB thực tế:** `3316` bản ghi (`A1, A2`)
> **Tệp đặc tả mẫu:** `tests/fixtures/rubric_test_cases.json`

---

## 1. TỔNG HỢP KẾT QUẢ ĐÁNH GIÁ THỰC TẾ (EXECUTIVE SUMMARY)

| Chỉ số đánh giá | Giá trị thực tế | Tỷ lệ |
| :--- | :---: | :---: |
| **Tổng số ca kiểm thử đã chạy** | **17** | 100% |
| **Số ca ĐẠT (PASS)** | **17** | **100.0%** |
| **Số ca THẤT BẠI (FAIL)** | **0** | 0.0% |
| **Số ca BỊ CHẶN (BLOCKED - Ollama offline)** | **0** | 0.0% |

### Phân bổ kết quả thực tế theo từng nhóm Rubric:
- **Trong phạm vi (In-scope):** 5/5 PASS (100.0%), 0 FAIL, 0 BLOCKED
- **Diễn đạt khác nhau (Paraphrased):** 3/3 PASS (100.0%), 0 FAIL, 0 BLOCKED
- **Hội thoại nhiều lượt (Multi-turn Context):** 3/3 PASS (100.0%), 0 FAIL, 0 BLOCKED
- **Ngoài phạm vi (Out-of-scope):** 2/2 PASS (100.0%), 0 FAIL, 0 BLOCKED
- **Thiếu thông tin / Mơ hồ (Ambiguous):** 2/2 PASS (100.0%), 0 FAIL, 0 BLOCKED
- **Đánh giá mở rộng ngẫu nhiên (Dynamic Coverage):** 2/2 PASS (100.0%), 0 FAIL, 0 BLOCKED

---

## 2. BẢNG CHI TIẾT KẾT QUẢ TỪNG CA KIỂM THỬ

| Mã ca | Nhóm kiểm thử | Câu hỏi kiểm thử (Dynamic Input) | Chế độ (Mode) | Điểm RRF | Độ trễ | Kết quả | Ghi chú & Bằng chứng thực tế |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **AMB-01** | AMBIGUOUS | `từ này nghĩa là gì?` | `CLARIFICATION` | 0.0000 | 5.2ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **AMB-02** | AMBIGUOUS | `cho tôi câu ví dụ của từ đó` | `CLARIFICATION` | 0.0000 | 156.1ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **CTX-01** | MULTI_TURN | `L1: từ geography nghĩa là gì? -> L2: cho tôi câu ví dụ của từ này` | `RAG_GENERATION` | 0.0328 | 6090.5ms | ✅ **PASS** | Từ **geography**:  **Trình độ:** A1  **Phát âm:** /dʒiˈɑɡrəfi/  ### Danh từ (Noun)  **1. địa lý học; địa lý... |
| **CTX-02** | MULTI_TURN | `L1: community nghĩa là gì? -> L2: còn trình độ của nó thì sao?` | `RAG_GENERATION` | 0.0328 | 4653.8ms | ✅ **PASS** | Từ **community**:  **Trình độ:** A2  **Phát âm:** /k(ə)ˈmjunəri/  ### Danh từ (Noun)  **1. Cộng đồng**   • ... |
| **CTX-03** | MULTI_TURN | `L1: owner nghĩa là gì? -> L2: còn ví dụ? -> L3: thế còn phát âm của từ đó?` | `RAG_GENERATION` | 0.0328 | 1614.8ms | ✅ **PASS** | Từ **owner**:  **Trình độ:** A2  **Phát âm:** /ˈəʊnə(r)/ |
| **DYN-01** | DYNAMIC_EVAL | `final, green, benefit, scientist, nervous, film` | `DYNAMIC` | 0.0000 | 352.1ms | ✅ **PASS** | 6/6 (100%): final:PASS, green:PASS, benefit:PASS, scientist:PASS, nervous:PASS, film:PASS |
| **DYN-02** | DYNAMIC_EVAL | `qxrgxkspb, qxkuqvhgz, qxoqdlfnx` | `NO_MATCH` | 0.0000 | 187.3ms | ✅ **PASS** | Từ chối an toàn 3/3 từ ngoài KB. |
| **OOS-01** | OUT_OF_SCOPE | `Ai là người đầu tiên đặt chân lên mặt trăng?` | `NO_MATCH` | 0.0000 | 257.4ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **OOS-02** | OUT_OF_SCOPE | `Giá tiền Bitcoin hôm nay bao nhiêu?` | `NO_MATCH` | 0.0000 | 79.2ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **PAR-01** | PARAPHRASED | `bạn có thể giải thích ý nghĩa của từ beginning được không?` | `RAG_GENERATION` | 0.0328 | 3164.6ms | ✅ **PASS** | Từ **beginning**:  **Trình độ:** A1  **Phát âm:** /bɪˈɡɪnɪŋ/  ### Danh từ (Noun)  **1. Phần đầu; lúc bắt đầ... |
| **PAR-02** | PARAPHRASED | `nghĩa của từ lawyer là gì vậy chatbot?` | `RAG_GENERATION` | 0.0328 | 2708.2ms | ✅ **PASS** | Từ **lawyer**:  **Trình độ:** A2  **Phát âm:** /ˈlɔːjə(r)/  ### Danh từ (Noun)  **1. Luật sư**   • The lawy... |
| **PAR-03** | PARAPHRASED | `What does temperature mean in Vietnamese?` | `DIRECT_MATCH` | 0.0330 | 33.1ms | ✅ **PASS** | Từ **temperature**:  **Trình độ:** A2  **Phát âm:** /ˈtemprətʃə(r)/  ### Danh từ (Noun)  **1. Nhiệt độ**   ... |
| **VOC-01** | IN_SCOPE | `easy nghĩa là gì?` | `DIRECT_MATCH` | 0.0330 | 53.0ms | ✅ **PASS** | Từ **easy**:  **Trình độ:** A1  **Phát âm:** /ˈizi/  ### Tính từ (Adjective)  **1. dễ dàng**   • The teache... |
| **VOC-02** | IN_SCOPE | `Cho tôi câu ví dụ của từ face này.` | `RAG_GENERATION` | 0.0328 | 2838.7ms | ✅ **PASS** | Từ **face**:  **Trình độ:** A1  **Phát âm:** /feɪs/  ### Danh từ (Noun)  • I cannot look you in the face af... |
| **VOC-03** | IN_SCOPE | `Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A2` | `DIRECT_MATCH` | 0.0000 | 256.0ms | ✅ **PASS** | Danh sách từ vựng tiếng Anh trình độ A2 (hiển thị 15/1535 từ): 1. ability 2. able 3. abroad 4. accept 5. ac... |
| **VOC-04** | IN_SCOPE | `từ nào có nghĩa là nghĩ là?` | `DIRECT_MATCH` | 0.0330 | 30.7ms | ✅ **PASS** | Từ **think**:  **Trình độ:** A1  **Phát âm:** /θɪŋk/  ### Động từ (Verb)  **1. Nghĩ, suy nghĩ, ngẫm nghĩ** ... |
| **VOC-05** | IN_SCOPE | `phát âm và từ loại của từ band là gì?` | `RAG_GENERATION` | 0.0328 | 3877.7ms | ✅ **PASS** | Từ **band**:  **Trình độ:** A1  **Phát âm:** /bænd/  ### Danh từ (Noun)  **1. Ban nhạc, dàn nhạc**   • He p... |

---

## 3. KẾT LUẬN KIỂM ĐỊNH
- Thực thi tự động bằng dữ liệu lấy mẫu động từ `3316` bản ghi trong KB (Seed `1794654014`).
- Kết quả thực tế: **17/17 PASS** (100.0%), **0 FAIL**, **0 BLOCKED**.