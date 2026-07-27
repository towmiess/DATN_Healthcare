const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  ImageRun, Table, TableRow, TableCell, WidthType, ShadingType, VerticalAlign,
  PageBreak
} = require("docx");

const FONT = "Times New Roman";
const CONTENT_W_IN = 6.3;

function p(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 360 },
    children: [new TextRun({ text, font: FONT, size: 26, bold: opts.bold || false })],
  });
}
function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 240 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 32 })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 180 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 28 })] });
}
function caption(text) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 260 },
    children: [new TextRun({ text, font: FONT, bold: true, italics: true, size: 24 })] });
}
function imageParagraph(path, widthIn, heightIn) {
  const buf = fs.readFileSync(path);
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 },
    children: [new ImageRun({ data: buf, transformation: { width: Math.round(widthIn * 96), height: Math.round(heightIn * 96) }, type: "png" })],
  });
}
function cellText(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, font: FONT, size: 22, bold: opts.bold || false })] });
}
function cellMulti(lines) {
  return lines.map((t, i) => new Paragraph({ spacing: { after: i === lines.length - 1 ? 0 : 80 },
    children: [new TextRun({ text: t, font: FONT, size: 22 })] }));
}
function labelCell(text) {
  return new TableCell({ width: { size: 22, type: WidthType.PERCENTAGE }, shading: { type: ShadingType.CLEAR, fill: "E8EEF9" },
    verticalAlign: VerticalAlign.CENTER, children: [cellText(text, { bold: true })] });
}
function valueCell(content) {
  return new TableCell({ width: { size: 78, type: WidthType.PERCENTAGE }, children: Array.isArray(content) ? content : [cellText(content)] });
}
function ucSpecTable(rows) {
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map(([label, value]) => new TableRow({ children: [labelCell(label), valueCell(value)] })) });
}

const children = [];
children.push(h1("Phân tích Use Case — Nhật ký sức khỏe & AI Insight"));

// ---------- 1. UC diagram ----------
children.push(h2("1. Sơ đồ Use Case — Nhật ký sức khỏe & Báo cáo AI Insight"));
children.push(p("Sơ đồ thể hiện các Use case liên quan đến việc ghi và phân tích nhật ký sức khỏe bằng AI, cũng như xem báo cáo và tạo giải thích AI Insight, với tác nhân là Người dùng."));
children.push(imageParagraph("journal_insight_uc.png", CONTENT_W_IN, CONTENT_W_IN * 1520/2600));
children.push(caption("Hình 1. Sơ đồ Use Case module Nhật ký sức khỏe & AI Insight"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 2. UC specs ----------
children.push(h2("2. Đặc tả kịch bản Use Case"));

children.push(p("Bảng 1. Đặc tả Use Case \u201cGhi nhật ký & phân tích bằng AI\u201d", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-JNL-01"],
  ["Tên Use case", "Ghi nhật ký & phân tích bằng AI"],
  ["Tác nhân", "Người dùng đã đăng nhập"],
  ["Mô tả tóm tắt", "Người dùng viết nhật ký mô tả triệu chứng, cảm giác hoặc sự kiện sức khỏe trong ngày; hệ thống dùng LLM để tự động trích xuất thông tin có cấu trúc và đánh giá mức độ cần lưu ý."],
  ["Điều kiện trước", "Người dùng đã đăng nhập; health-service và rag-service đang hoạt động bình thường."],
  ["Luồng sự kiện chính", cellMulti([
    "1. Người dùng nhập nội dung nhật ký trên giao diện và gửi đi.",
    "2. Frontend gọi API POST /api/journal/analyze/ kèm JWT.",
    "3. Gateway xác thực JWT, ký ngữ cảnh người dùng và chuyển tới health-service.",
    "4. health-service lưu nội dung gốc vào JournalEntry.",
    "5. health-service gửi nội dung nhật ký sang rag-service để phân tích.",
    "6. LLM trích xuất tóm tắt, triệu chứng, mức độ, xu hướng, tần suất, mức cần lưu ý và gợi ý theo dõi.",
    "7. health-service lưu kết quả vào JournalAnalysis.",
    "8. Kết quả được trả về và hiển thị cho người dùng.",
  ])],
  ["Luồng thay thế / ngoại lệ", cellMulti([
    "- 6a. Mức cần lưu ý được đánh giá là cao: health-service tạo event cảnh báo gửi sang notification-service (xem UC-JNL-02).",
    "- 5a. rag-service không phản hồi/lỗi: health-service vẫn lưu JournalEntry, đánh dấu trạng thái phân tích thất bại để xử lý lại sau.",
  ])],
  ["Điều kiện sau", "Nhật ký được lưu trữ; kết quả phân tích AI được lưu vào JournalAnalysis và hiển thị cho người dùng."],
]));

children.push(p("Bảng 2. Đặc tả Use Case \u201cCảnh báo mức cần lưu ý cao\u201d (extend của UC-JNL-01)", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-JNL-02"],
  ["Tên Use case", "Cảnh báo mức cần lưu ý cao"],
  ["Tác nhân", "Người dùng (kích hoạt gián tiếp qua UC-JNL-01)"],
  ["Mô tả tóm tắt", "Khi kết quả phân tích nhật ký cho thấy mức cần lưu ý cao, hệ thống tự động tạo cảnh báo và gửi thông báo/email cho người dùng."],
  ["Điều kiện trước", "UC-JNL-01 đã hoàn tất bước phân tích và trả về mức cần lưu ý cao."],
  ["Luồng sự kiện chính", cellMulti([
    "1. health-service tạo event cảnh báo dựa trên kết quả JournalAnalysis.",
    "2. Event được gửi tới notification-service qua API nội bộ (kèm khóa dịch vụ nội bộ).",
    "3. notification-service ghi nhận event vào inbox_events để chống trùng lặp.",
    "4. notification-service tạo notification trong ứng dụng.",
    "5. notification-service gửi email cảnh báo nếu người dùng bật cấu hình nhận email.",
    "6. Frontend hiển thị thông báo cảnh báo cho người dùng qua kênh realtime (SSE).",
  ])],
  ["Luồng thay thế / ngoại lệ", "- 2a. Gửi event thất bại/timeout: cơ chế retry được áp dụng; inbox_events đảm bảo event không bị xử lý trùng khi gửi lại."],
  ["Điều kiện sau", "Người dùng nhận được cảnh báo kịp thời qua thông báo trong ứng dụng và/hoặc email."],
]));

children.push(p("Bảng 3. Đặc tả Use Case \u201cXem báo cáo & tạo AI Insight\u201d", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-RPT-01"],
  ["Tên Use case", "Xem báo cáo sức khỏe & tạo AI Insight"],
  ["Tác nhân", "Người dùng đã đăng nhập"],
  ["Mô tả tóm tắt", "Người dùng xem dashboard tổng hợp các chỉ số sức khỏe theo tuần/tháng và có thể yêu cầu hệ thống sinh giải thích AI Insight về tình trạng hiện tại, hoặc xuất báo cáo."],
  ["Điều kiện trước", "Người dùng đã đăng nhập và có dữ liệu sức khỏe được ghi nhận trong hệ thống."],
  ["Luồng sự kiện chính", cellMulti([
    "1. Người dùng mở trang báo cáo (/user/reports).",
    "2. Frontend gọi GET /api/reports/dashboard/.",
    "3. health-service tổng hợp HealthProfile, GlucoseMeasurement, RiskPrediction, PeriodicReport và so sánh với kỳ trước.",
    "4. Dashboard được hiển thị cho người dùng.",
    "5. Người dùng bấm \u201cTạo AI Insight\u201d; Frontend gọi POST /api/reports/ai-insights/.",
    "6. health-service tổng hợp ngữ cảnh sức khỏe gần đây và gửi yêu cầu tới mô hình ngôn ngữ lớn để sinh giải thích.",
    "7. Kết quả AI Insight được lưu và hiển thị cho người dùng.",
    "8. Người dùng có thể lưu báo cáo nháp (draft) hoặc export báo cáo dạng PDF/CSV.",
  ])],
  ["Luồng thay thế / ngoại lệ", "- 6a. Không đủ dữ liệu để sinh giải thích có ý nghĩa: hệ thống trả thông báo cần bổ sung thêm dữ liệu sức khỏe."],
  ["Điều kiện sau", "Người dùng xem được dashboard, nhận giải thích AI Insight và/hoặc có file báo cáo được xuất ra."],
]));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 3. Sequence + activity: journal ----------
children.push(h2("3. Sơ đồ tuần tự & hoạt động — Ghi nhật ký & phân tích AI"));
children.push(p("Sơ đồ tuần tự mô tả luồng xử lý khi người dùng ghi nhật ký sức khỏe: health-service lưu nhật ký gốc, chuyển nội dung sang rag-service để LLM trích xuất thông tin có cấu trúc, sau đó lưu kết quả và cảnh báo nếu cần."));
children.push(imageParagraph("seq_journal.png", CONTENT_W_IN, CONTENT_W_IN * 1370/2768));
children.push(caption("Hình 2. Sơ đồ tuần tự luồng ghi nhật ký & phân tích bằng AI"));

const ajW = 3.2, ajH = ajW * 3274/1172;
children.push(p("Sơ đồ hoạt động dưới đây thể hiện logic quyết định khi mức cần lưu ý được đánh giá cao, dẫn tới việc tạo cảnh báo và gửi thông báo/email cho người dùng."));
children.push(imageParagraph("activity_journal.png", ajW, ajH));
children.push(caption("Hình 3. Sơ đồ hoạt động luồng phân tích nhật ký sức khỏe"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 4. Sequence + activity: AI insight ----------
children.push(h2("4. Sơ đồ tuần tự & hoạt động — Báo cáo & AI Insight"));
children.push(p("Sơ đồ tuần tự mô tả luồng xem dashboard báo cáo, tạo AI Insight giải thích tình trạng sức khỏe và (tùy chọn) xuất báo cáo PDF/CSV."));
children.push(imageParagraph("seq_insight.png", CONTENT_W_IN, CONTENT_W_IN * 2080/2768));
children.push(caption("Hình 4. Sơ đồ tuần tự luồng xem báo cáo & tạo AI Insight"));

const aiW = 4.6, aiH = aiW * 2506/1600;
children.push(p("Sơ đồ hoạt động thể hiện các nhánh hành động người dùng có thể chọn sau khi xem dashboard: tạo AI Insight, lưu báo cáo nháp, hoặc xuất báo cáo."));
children.push(imageParagraph("activity_insight.png", aiW, aiH));
children.push(caption("Hình 5. Sơ đồ hoạt động luồng báo cáo & AI Insight"));

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, bottom: 1134, left: 1701, right: 1134 } } },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/home/claude/UseCase_Journal_AIInsight.docx", buf);
  console.log("done");
});
