# BÁO CÁO KẾT QUẢ KIỂM THỬ ĐỘNG HỘI THOẠI THEO RUBRIC
## DỰ ÁN: CHATBOX 2.0 — LOCAL VOCABULARY ASSISTANT

> **Ngày thực thi:** 2026-11-12 19:32:29
> **Môi trường thực thi:** Python 3.11.9 | Seed lấy mẫu: `1794486719` | Ollama Online: `True`
> **Quy mô KB thực tế:** `3301` bản ghi (`A1, A2`)
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
| **AMB-01** | AMBIGUOUS | `từ này nghĩa là gì?` | `CLARIFICATION` | 0.0000 | 0.7ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **AMB-02** | AMBIGUOUS | `cho tôi câu ví dụ của từ đó` | `CLARIFICATION` | 0.0000 | 85.3ms | ✅ **PASS** | Bạn đang muốn hỏi về từ vựng nào? Vui lòng cung cấp từ tiếng Anh cụ thể để tôi hỗ trợ nhé! |
| **CTX-01** | MULTI_TURN | `L1: từ height nghĩa là gì? -> L2: cho tôi câu ví dụ của từ này` | `RAG_GENERATION` | 0.0328 | 2857.9ms | ✅ **PASS** | Từ **height**:  **Trình độ:** A2  **Phát âm:** /haɪt/  ### Danh từ (Noun)  **1. Chiều cao, bề cao; độ cao**... |
| **CTX-02** | MULTI_TURN | `L1: businessman nghĩa là gì? -> L2: còn trình độ của nó thì sao?` | `RAG_GENERATION` | 0.0328 | 2922.8ms | ✅ **PASS** | Từ **businessman**:  **Trình độ:** A2  **Phát âm:** /ˈbɪznəsmæn/  ### Danh từ (Noun)  **1. Nhà kinh doanh, ... |
| **CTX-03** | MULTI_TURN | `L1: usually nghĩa là gì? -> L2: còn ví dụ? -> L3: thế còn phát âm của từ đó?` | `RAG_GENERATION` | 0.0328 | 2684.6ms | ✅ **PASS** | Từ **usually**:  **Trình độ:** A1  **Phát âm:** /ˈjuːʒ(ʊə)li/  ### Trạng từ (Adverb)  **1. thường xuyên; th... |
| **DYN-01** | DYNAMIC_EVAL | `ancient, product, behaviour, eye, advertise, catch` | `DYNAMIC` | 0.0000 | 326.1ms | ✅ **PASS** | 6/6 (100%): ancient:PASS, product:PASS, behaviour:PASS, eye:PASS, advertise:PASS, catch:PASS |
| **DYN-02** | DYNAMIC_EVAL | `qxbwgaeak, qxajsmuhj, qxganrist` | `NO_MATCH` | 0.0000 | 162.3ms | ✅ **PASS** | Từ chối an toàn 3/3 từ ngoài KB. |
| **OOS-01** | OUT_OF_SCOPE | `Thủ đô của nước Pháp là gì?` | `NO_MATCH` | 0.0000 | 55.0ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **OOS-02** | OUT_OF_SCOPE | `Giá tiền Bitcoin hôm nay bao nhiêu?` | `NO_MATCH` | 0.0000 | 172.0ms | ✅ **PASS** | Xin lỗi, câu hỏi này nằm ngoài phạm vi dữ liệu tra cứu từ vựng tiếng Anh mà chatbot hiện đang hỗ trợ. |
| **PAR-01** | PARAPHRASED | `bạn có thể giải thích ý nghĩa của từ might được không?` | `RAG_GENERATION` | 0.0323 | 4634.0ms | ✅ **PASS** | Từ **might**:  **Trình độ:** A2  **Phát âm:** /maɪt/  ### Động từ (Verb)  **1. Quá khứ của may**   • They m... |
| **PAR-02** | PARAPHRASED | `nghĩa của từ climate là gì vậy chatbot?` | `RAG_GENERATION` | 0.0328 | 3829.1ms | ✅ **PASS** | Từ **climate**:  **Trình độ:** A2  **Phát âm:** /ˈklaɪmət/  ### Danh từ (Noun)  **1. Khí hậu, thời tiết**  ... |
| **PAR-03** | PARAPHRASED | `What does clear mean in Vietnamese?` | `DIRECT_MATCH` | 0.0330 | 34.2ms | ✅ **PASS** | Từ **clear**:  **Trình độ:** A2  **Phát âm:** /klɪə(r)/  ### Tính từ (Adjective)  **1. Trong, trong trẻo, t... |
| **VOC-01** | IN_SCOPE | `biology nghĩa là gì?` | `DIRECT_MATCH` | 0.0330 | 47.6ms | ✅ **PASS** | Từ **biology**:  **Trình độ:** A2  **Phát âm:** /baɪˈɒlədʒi/  ### Danh từ (Noun)  **1. Sinh vật học**   • W... |
| **VOC-02** | IN_SCOPE | `Cho tôi câu ví dụ của từ colleague này.` | `RAG_GENERATION` | 0.0328 | 2329.9ms | ✅ **PASS** | Từ **colleague**:  **Trình độ:** A2  **Phát âm:** /ˈkɒliːɡ/  ### Danh từ (Noun)  **1. Bạn đồng nghiệp, bạn ... |
| **VOC-03** | IN_SCOPE | `Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A2` | `DIRECT_MATCH` | 0.0000 | 165.2ms | ✅ **PASS** | Danh sách từ vựng tiếng Anh trình độ A2 (hiển thị 15/1535 từ): 1. ability 2. able 3. abroad 4. accept 5. ac... |
| **VOC-04** | IN_SCOPE | `từ nào có nghĩa là điểm nối?` | `DIRECT_MATCH` | 0.0330 | 30.5ms | ✅ **PASS** | Từ **join**:  **Trình độ:** A1  **Phát âm:** /dʒɔɪn/  ### Động từ (Verb)  **1. Nối lại, chắp, ghép, buộc (c... |
| **VOC-05** | IN_SCOPE | `phát âm và từ loại của từ taxi là gì?` | `RAG_GENERATION` | 0.0328 | 3754.5ms | ✅ **PASS** | Từ **taxi**:  **Trình độ:** A1  **Phát âm:** /ˈtæksi/  ### Danh từ (Noun)  **1. Xe tắc xi**   • I took a ta... |

---

## 3. KẾT LUẬN KIỂM ĐỊNH
- Thực thi tự động bằng dữ liệu lấy mẫu động từ `3301` bản ghi trong KB (Seed `1794486719`).
- Kết quả thực tế: **17/17 PASS** (100.0%), **0 FAIL**, **0 BLOCKED**.