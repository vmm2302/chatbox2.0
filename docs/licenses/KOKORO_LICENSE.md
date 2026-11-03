# Thông Báo Bản Quyền & Giấy Phép Sử Dụng Kokoro TTS (Licenses)

Dự án này tích hợp công nghệ phát âm Text-to-Speech (TTS) cục bộ 100% Offline sử dụng engine **Kokoro-ONNX** và mô hình **Kokoro-82M**. Dưới đây là thông tin chi tiết về giấy phép bản quyền của các thành phần được đóng gói và sử dụng:

---

## 1. Kokoro-ONNX (Engine phát âm ONNX Runtime)
- **Tác giả / Kho mã nguồn:** [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)
- **Giấy phép:** **MIT License**

```text
MIT License

Copyright (c) 2025 thewh1teagle

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. Kokoro-82M Weights & Model (Trọng số mô hình Kokoro)
- **Tác giả / Phát triển:** [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
- **Giấy phép:** **Apache License 2.0**

```text
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

---

## 3. Các thành phần đóng gói đi kèm:
- **`kokoro-v1.0.int8.onnx`**: Mô hình nén lượng tử hóa 8-bit (~88 MB) tuân thủ giấy phép Apache 2.0.
- **`voices-v1.0.bin`**: Dữ liệu vector giọng đọc (bao gồm giọng Mỹ chuẩn `af_heart`) tuân thủ giấy phép Apache 2.0.
- Toàn bộ các thành phần trên được lưu trữ cục bộ tại `data/models/kokoro/` và hoạt động hoàn toàn không cần kết nối mạng.
