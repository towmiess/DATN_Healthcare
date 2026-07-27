const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  ImageRun, Table, TableRow, TableCell, WidthType, ShadingType, VerticalAlign,
  BorderStyle, PageBreak
} = require("docx");

const FONT = "Times New Roman";
const CONTENT_W_IN = 6.3;

function p(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 360 },
    children: Array.isArray(text) ? text : [new TextRun({ text, font: FONT, size: 26, bold: opts.bold || false, italics: opts.italics || false })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 240 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 32 })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 180 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 28 })],
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 260 },
    children: [new TextRun({ text, font: FONT, bold: true, italics: true, size: 24 })],
  });
}

function imageParagraph(path, widthIn, heightIn) {
  const buf = fs.readFileSync(path);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 80 },
    children: [
      new ImageRun({
        data: buf,
        transformation: { width: Math.round(widthIn * 96), height: Math.round(heightIn * 96) },
        type: "png",
      }),
    ],
  });
}

function cellText(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
    children: [new TextRun({ text, font: FONT, size: 22, bold: opts.bold || false })],
  });
}

function cellMulti(lines, opts = {}) {
  return lines.map((t, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { after: i === lines.length - 1 ? 0 : 80 },
    children: [new TextRun({ text: t, font: FONT, size: 22 })],
  }));
}

function labelCell(text) {
  return new TableCell({
    width: { size: 22, type: WidthType.PERCENTAGE },
    shading: { type: ShadingType.CLEAR, fill: "E8EEF9" },
    verticalAlign: VerticalAlign.CENTER,
    children: [cellText(text, { bold: true })],
  });
}
function valueCell(content) {
  return new TableCell({
    width: { size: 78, type: WidthType.PERCENTAGE },
    children: Array.isArray(content) ? content : [cellText(content)],
  });
}

function ucSpecTable(rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map(([label, value]) => new TableRow({
      children: [labelCell(label), valueCell(value)],
    })),
  });
}

const children = [];

children.push(h1("Phân tích Use Case — Module Chatbot tư vấn RAG"));

// ---------- 1. Overview UC diagram ----------
children.push(h2("1. Sơ đồ Use Case tổng quát toàn hệ thống"));
children.push(p(
  "Sơ đồ dưới đây thể hiện toàn bộ các chức năng chính của hệ thống HealthCare Diabetes, với hai tác nhân chính là Người dùng (bệnh nhân/người theo dõi sức khỏe) và Quản trị viên (vận hành hệ thống)."
));
children.push(imageParagraph("overview_uc.png", CONTENT_W_IN, CONTENT_W_IN * 2120/3000));
children.push(caption("Hình 1. Sơ đồ Use Case tổng quát hệ thống HealthCare Diabetes"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 2. Kịch bản UC cho RAG chatbot ----------
children.push(h2("2. Đặc tả kịch bản Use Case — Module Chatbot tư vấn (RAG)"));

children.push(p("Bảng 1. Đặc tả Use Case \u201cĐặt câu hỏi tư vấn tiểu đường\u201d", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-RAG-01"],
  ["Tên Use case", "Đặt câu hỏi tư vấn tiểu đường (Trò chuyện với chatbot)"],
  ["Tác nhân", "Người dùng đã đăng nhập"],
  ["Mô tả tóm tắt", "Người dùng đặt câu hỏi liên quan đến tiểu đường (kiến thức bệnh, chế độ ăn, triệu chứng...) và nhận câu trả lời được sinh dựa trên tài liệu y khoa đã lập chỉ mục."],
  ["Điều kiện trước", cellMulti([
    "- Người dùng đã đăng nhập, access token còn hiệu lực.",
    "- RAG Service và Qdrant đang hoạt động bình thường.",
  ])],
  ["Luồng sự kiện chính", cellMulti([
    "1. Người dùng nhập câu hỏi trên giao diện chat và gửi đi.",
    "2. Frontend gọi API /api/rag/chat/session kèm JWT.",
    "3. Gateway xác thực JWT, ký ngữ cảnh người dùng (X-User-Context) và chuyển tiếp request tới RAG Service.",
    "4. RAG Service kiểm tra chữ ký gateway, lấy lịch sử phiên chat từ Redis.",
    "5. Hệ thống truy vấn tri thức người dùng/response rule đã lưu trong Qdrant.",
    "6. QueryRouter phân loại câu hỏi thuộc nhóm cơ bản/tài liệu.",
    "7. Retriever tìm top-k đoạn tài liệu y khoa liên quan trong Qdrant.",
    "8. Prompt builder ghép system prompt, lịch sử hội thoại, tri thức và ngữ cảnh tài liệu.",
    "9. Hệ thống gọi Gemini để sinh câu trả lời.",
    "10. Kết quả được làm sạch định dạng, lưu vào lịch sử phiên và trả về cho người dùng kèm nguồn tham khảo.",
  ])],
  ["Luồng thay thế / ngoại lệ", cellMulti([
    "- 3a. Chữ ký gateway không hợp lệ: RAG Service từ chối request (middleware chặn truy cập trực tiếp).",
    "- 9a. Gemini trả lỗi hoặc vượt giới hạn tần suất: hệ thống luân chuyển key pool hoặc dùng fallback model.",
    "- 10a. Câu trả lời bị cắt/không hợp lệ: hệ thống retry sinh lại câu trả lời.",
  ])],
  ["Điều kiện sau", "Câu trả lời được hiển thị cho người dùng; tin nhắn được lưu vào lịch sử phiên chat trong Redis."],
]));

children.push(p("Bảng 2. Đặc tả Use Case \u201cXử lý câu hỏi khẩn cấp\u201d (extend của UC-RAG-01)", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-RAG-02"],
  ["Tên Use case", "Xử lý câu hỏi khẩn cấp"],
  ["Tác nhân", "Người dùng đã đăng nhập (kích hoạt gián tiếp qua UC-RAG-01)"],
  ["Mô tả tóm tắt", "Khi câu hỏi của người dùng được QueryRouter phân loại là tình huống khẩn cấp (ví dụ nghi ngờ hạ đường huyết), hệ thống trả hướng dẫn xử lý ngay và tự động cảnh báo cho các kênh liên quan."],
  ["Điều kiện trước", "Người dùng đang trong một phiên chat hợp lệ (UC-RAG-01 đã được kích hoạt)."],
  ["Luồng sự kiện chính", cellMulti([
    "1. QueryRouter phát hiện nội dung câu hỏi có dấu hiệu khẩn cấp (ví dụ: run tay, vã mồ hôi lạnh, chóng mặt).",
    "2. Hệ thống trả ngay hướng dẫn xử lý khẩn cấp cho người dùng, ưu tiên tốc độ phản hồi.",
    "3. Hệ thống tạo event RAG_EMERGENCY_ALERT và gửi sang Notification Service.",
    "4. Notification Service tạo thông báo trong ứng dụng và gửi email cảnh báo.",
    "5. Frontend hiển thị thông báo khẩn cấp cho người dùng.",
  ])],
  ["Luồng thay thế / ngoại lệ", "- 3a. Gửi event thất bại: Notification Service xử lý theo cơ chế idempotent inbox khi nhận lại event retry."],
  ["Điều kiện sau", "Người dùng nhận được hướng dẫn xử lý khẩn cấp; một cảnh báo được ghi nhận và gửi qua thông báo/email."],
]));

children.push(p("Bảng 3. Đặc tả Use Case \u201cQuản lý kho tri thức RAG\u201d", { bold: true, center: true }));
children.push(ucSpecTable([
  ["Mã Use case", "UC-RAG-03"],
  ["Tên Use case", "Quản lý kho tri thức RAG"],
  ["Tác nhân", "Quản trị viên tri thức"],
  ["Mô tả tóm tắt", "Quản trị viên thêm mới, cập nhật hoặc xóa tài liệu y khoa nguồn, sau đó lập lại chỉ mục để chatbot có thể truy hồi tri thức mới nhất."],
  ["Điều kiện trước", "Quản trị viên đã đăng nhập với quyền admin và có quyền truy cập trang quản lý tri thức AI."],
  ["Luồng sự kiện chính", cellMulti([
    "1. Quản trị viên truy cập trang /admin/ai-knowledge.",
    "2. Quản trị viên tải lên tài liệu PDF/TXT mới qua API /admin/upload.",
    "3. Hệ thống dùng loader để đọc nội dung tài liệu (kèm OCR fallback nếu cần).",
    "4. Indexer chia tài liệu thành các chunk, sinh embedding và lưu vào Qdrant.",
    "5. Quản trị viên có thể gọi /admin/rebuild-index để lập lại toàn bộ chỉ mục khi cần.",
    "6. Quản trị viên có thể xóa tài liệu không còn phù hợp qua /admin/documents.",
  ])],
  ["Luồng thay thế / ngoại lệ", "- 3a. Tài liệu lỗi định dạng hoặc không đọc được: hệ thống ghi log lỗi và bỏ qua tài liệu đó."],
  ["Điều kiện sau", "Kho tri thức trong Qdrant được cập nhật; các câu trả lời tư vấn tiếp theo sẽ phản ánh tài liệu mới nhất."],
]));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 3. Detailed UC diagram for RAG ----------
children.push(h2("3. Sơ đồ Use Case chi tiết — Module Chatbot tư vấn RAG"));
children.push(p(
  "Sơ đồ dưới đây thể hiện các Use case của module chatbot RAG cùng quan hệ include/extend giữa chúng: Use case chính \u201cTrò chuyện / Đặt câu hỏi tư vấn\u201d bao gồm (include) việc lấy phiên chat từ Redis, và được mở rộng (extend) bởi hai luồng đặc biệt là xử lý câu hỏi khẩn cấp và tra cứu thông tin thuốc."
));
children.push(imageParagraph("rag_uc.png", CONTENT_W_IN, CONTENT_W_IN * 1760/2720));
children.push(caption("Hình 2. Sơ đồ Use Case chi tiết module Chatbot tư vấn RAG"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 4. Sequence diagram ----------
children.push(h2("4. Sơ đồ tuần tự — Luồng xử lý một lượt chat tư vấn RAG"));
children.push(p(
  "Sơ đồ tuần tự mô tả chi tiết luồng xử lý khi người dùng gửi một câu hỏi tới chatbot, từ Frontend qua API Gateway, RAG Service, Redis, Qdrant cho đến khi gọi Gemini sinh câu trả lời và trả kết quả về cho người dùng, bao gồm cả nhánh rẽ khi câu hỏi được phân loại là khẩn cấp."
));
children.push(imageParagraph("seq_rag.png", CONTENT_W_IN, CONTENT_W_IN * 1834/2768));
children.push(caption("Hình 3. Sơ đồ tuần tự luồng chat tư vấn RAG"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- 5. Activity diagram ----------
children.push(h2("5. Sơ đồ hoạt động — Luồng xử lý câu hỏi trong RAG Service"));
children.push(p(
  "Sơ đồ hoạt động thể hiện logic xử lý bên trong RAG Service, bao gồm bước xác thực chữ ký gateway, phân loại câu hỏi qua QueryRouter (khẩn cấp / thông tin thuốc / cơ bản), truy hồi ngữ cảnh, sinh câu trả lời bằng Gemini và cơ chế retry khi câu trả lời không hợp lệ."
));
const actW = 3.6, actH = actW * 4850/1792;
children.push(imageParagraph("activity_rag.png", actW, actH));
children.push(caption("Hình 4. Sơ đồ hoạt động luồng xử lý câu hỏi trong RAG Service"));

const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1418, bottom: 1134, left: 1701, right: 1134 },
        },
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/home/claude/UseCase_RAG_Chatbot.docx", buf);
  console.log("done");
});
