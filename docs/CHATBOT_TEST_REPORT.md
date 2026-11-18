# BÁO CÁO KẾT QUẢ KIỂM THỬ ĐỘNG HỘI THOẠI THEO RUBRIC
## DỰ ÁN: CHATBOX 2.0 — LOCAL VOCABULARY ASSISTANT

> **Ngày thực thi:** 2026-11-18 09:50:22
> **Môi trường thực thi:** Python 3.13.15 | Seed lấy mẫu: `1794970200` | Ollama Online: `False`
> **Quy mô KB thực tế:** `5879` bản ghi (`A1, A2, B1, B2`)
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
| **AMB-01** | AMBIGUOUS | `từ này nghĩa là gì?` | `CLARIFICATION` | 0.0000 | 14.0ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **AMB-02** | AMBIGUOUS | `cho tôi câu ví dụ của từ đó` | `CLARIFICATION` | 0.0000 | 245.2ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **CTX-01** | MULTI_TURN | `L1: từ junior nghĩa là gì? -> L2: cho tôi câu ví dụ của từ này` | `RAG_GENERATION` | 0.0328 | 5033.2ms | ✅ **PASS** | Từ **junior**:  **Trình độ:** B2  **Phát âm:** /ˈdʒuːniə(r)/  ### Tính từ (Adjective)  **1. Trẻ tuổi hơn; e... |
| **CTX-02** | MULTI_TURN | `L1: hair nghĩa là gì? -> L2: còn trình độ của nó thì sao?` | `RAG_GENERATION` | 0.0328 | 1514.5ms | ✅ **PASS** | Từ **hair**:  **Trình độ:** A1  **Phát âm:** /heə(r)/  ### Danh từ (Noun)  **1. Tóc, lông (người, thú, cây....) |
| **CTX-03** | MULTI_TURN | `L1: receipt nghĩa là gì? -> L2: còn ví dụ? -> L3: thế còn phát âm của từ đó?` | `RAG_GENERATION` | 0.0328 | 1525.4ms | ✅ **PASS** | Từ **receipt**:  **Trình độ:** B1  **Phát âm:** /rɪˈsiːt/  ### Danh từ (Noun)  **1. Công thức (làm bánh, nấ...) |
| **DYN-01** | DYNAMIC_EVAL | `expedition, proof, slip, judgement, early, wedding` | `DYNAMIC` | 0.0000 | 723.5ms | ✅ **PASS** | 6/6 (100%): expedition:PASS, proof:PASS, slip:PASS, judgement:PASS, early:PASS, wedding:PASS |
| **DYN-02** | DYNAMIC_EVAL | `qxvevctsj, qxwtzrpzg, qxbqasuow` | `NO_MATCH` | 0.0000 | 387.8ms | ✅ **PASS** | Từ chối an toàn 3/3 từ ngoài KB. |
| **OOS-01** | OUT_OF_SCOPE | `Thủ đô của nước Pháp là gì?` | `NO_MATCH` | 0.0000 | 0.1ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **OOS-02** | OUT_OF_SCOPE | `Thời tiết tại Hà Nội hôm nay thế nào?` | `NO_MATCH` | 0.0000 | 0.1ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **PAR-01** | PARAPHRASED | `bạn có thể giải thích ý nghĩa của từ agenda được không?` | `RAG_GENERATION` | 0.0328 | 1375.8ms | ✅ **PASS** | Từ **agenda**:  **Trình độ:** B2  **Phát âm:** /əˈdʒendə/  ### Danh từ (Noun)  **1. Những việc phải làm**  ... |
| **PAR-02** | PARAPHRASED | `nghĩa của từ historic là gì vậy chatbot?` | `RAG_GENERATION` | 0.0328 | 1214.7ms | ✅ **PASS** | Từ **historic**:  **Trình độ:** B1  **Phát âm:** /hɪˈstɒrɪk/  ### Tính từ (Adjective)  **1. Có tính chất lị... |
| **PAR-03** | PARAPHRASED | `What does mood mean in Vietnamese?` | `DIRECT_MATCH` | 0.0330 | 76.3ms | ✅ **PASS** | Từ **mood**:  **Trình độ:** B1  **Phát âm:** /muːd/  ### Danh từ (Noun)  **1. Lối, cách, thức**   • The ver... |
| **VOC-01** | IN_SCOPE | `examination nghĩa là gì?` | `DIRECT_MATCH` | 0.0330 | 120.6ms | ✅ **PASS** | Từ **examination**:  **Trình độ:** B2  **Phát âm:** /ɪɡˌzæmɪˈneɪʃn/  ### Danh từ (Noun)  **1. Sự khám xét k... |
| **VOC-02** | IN_SCOPE | `Cho tôi câu ví dụ của từ temperature này.` | `RAG_GENERATION` | 0.0328 | 1027.5ms | ✅ **PASS** | Từ **temperature**:  **Trình độ:** A2  **Phát âm:** /ˈtemprətʃə(r)/  ### Danh từ (Noun)  **1. Nhiệt độ**   ... |
| **VOC-03** | IN_SCOPE | `Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A1` | `DIRECT_MATCH` | 0.0000 | 570.1ms | ✅ **PASS** | Danh sách từ vựng tiếng Anh trình độ A1 (hiển thị 15/1775 từ): 1. a, an 2. about 3. above 4. across 5. acti... |
| **VOC-04** | IN_SCOPE | `từ nào có nghĩa là dễ nhận thấy?` | `DIRECT_MATCH` | 0.0330 | 67.6ms | ✅ **PASS** | Từ **sensible**:  **Trình độ:** B1  **Phát âm:** /ˈsensəbl/  ### Tính từ (Adjective)  **1. Có thể cảm giác ... |
| **VOC-05** | IN_SCOPE | `phát âm và từ loại của từ skill là gì?` | `RAG_GENERATION` | 0.0328 | 1475.2ms | ✅ **PASS** | Từ **skill**:  **Trình độ:** A1  **Phát âm:** /skɪl/  ### Danh từ (Noun)  **1. Sự khéo léo, sự khéo tay, sự... |

---

## 3. KẾT LUẬN KIỂM ĐỊNH
- Thực thi tự động bằng dữ liệu lấy mẫu động từ `5879` bản ghi trong KB (Seed `1794970200`).
- Kết quả thực tế: **17/17 PASS** (100.0%), **0 FAIL**, **0 BLOCKED**.