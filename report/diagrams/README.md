# Bộ script vẽ sơ đồ (Use Case / Sequence / Activity) - HealthCare Diabetes

## Yêu cầu môi trường
- Node.js (đã cài package `docx`: `npm install docx`)
- Python 3 (đã cài `cairosvg`: `pip install cairosvg --break-system-packages`)
- Mermaid CLI: `npm install -g @mermaid-js/mermaid-cli`
- Chrome/Chromium để mermaid-cli render (mmdc cần trình duyệt headless).
  Nếu gặp lỗi "Could not find Chrome", cài bằng:
  `npx puppeteer browsers install chrome-headless-shell`
  rồi chạy mmdc với: `-p puppeteer-config.json` (file cấu hình no-sandbox đính kèm).

## Cấu trúc file

### 1. Sơ đồ Use Case (vẽ bằng SVG thủ công qua Python)
- `uc_lib.py`            : thư viện vẽ actor (stick-figure), ellipse use case, boundary, quan hệ include/extend.
- `gen_overview.py`      : sinh `overview_uc.svg` — sơ đồ Use Case tổng quát toàn hệ thống.
- `gen_rag_uc.py`        : sinh `rag_uc.svg` — sơ đồ Use Case chi tiết module Chatbot RAG.
- `gen_journal_uc.py`    : sinh `journal_insight_uc.svg` — sơ đồ Use Case module Nhật ký & AI Insight.

Chạy: `python3 gen_overview.py` rồi convert sang PNG:
```python
import cairosvg
cairosvg.svg2png(url="overview_uc.svg", write_to="overview_uc.png", scale=2)
```

Muốn thêm/sửa use case: chỉnh danh sách `col1/col2/...` (overview) hoặc tọa độ `uc_xxx = (x, y)` (rag_uc, journal_uc) rồi chạy lại.

### 2. Sơ đồ tuần tự (Sequence) - Mermaid
- `seq_rag.mmd`      : luồng chat tư vấn RAG
- `seq_journal.mmd`  : luồng ghi nhật ký & phân tích AI
- `seq_insight.mmd`  : luồng xem báo cáo & tạo AI Insight

### 3. Sơ đồ hoạt động (Activity) - Mermaid flowchart
- `activity_rag.mmd`
- `activity_journal.mmd`
- `activity_insight.mmd`

Render mermaid ra PNG:
```bash
export PUPPETEER_EXECUTABLE_PATH=/path/to/chrome
mmdc -i seq_rag.mmd -o seq_rag.png -w 1400 -b white -s 2 -p puppeteer-config.json
```

### 4. Script build file Word (.docx) — ghép ảnh + bảng đặc tả UC
- `build_uc_doc.js`      -> xuất `UseCase_RAG_Chatbot.docx`
- `build_journal_doc.js` -> xuất `UseCase_Journal_AIInsight.docx`

Chạy: `node build_uc_doc.js`

### 5. Script build Chương 1 & 2 báo cáo (lý do chọn đề tài, cơ sở lý thuyết)
- `build_doc.js` -> xuất `Bao_cao_LyDo_Chuong1_Chuong2.docx`

## Ghi chú
- Font dùng trong SVG/Mermaid: DejaVu Sans (hỗ trợ tiếng Việt có dấu). Nếu môi trường khác không có font này, cần cài `fonts-dejavu` hoặc đổi font trong `uc_lib.py`.
- Muốn vẽ thêm sơ đồ cho module khác (dự đoán nguy cơ, OCR, AI Vision dinh dưỡng...), copy 1 trong các file `gen_*_uc.py` hoặc `.mmd` làm mẫu rồi chỉnh nội dung theo đúng flow nghiệp vụ.
