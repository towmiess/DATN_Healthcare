const IMPORTANT_PREFIXES = [
  "lưu ý:",
  "lưu ý quan trọng:",
  "quan trọng:",
  "cảnh báo:",
  "khuyến nghị:",
  "chống chỉ định:",
  "thận trọng:",
];

const HEADING_PREFIXES = [
  "định nghĩa",
  "công dụng",
  "liều dùng",
  "tác dụng phụ",
  "lưu ý",
  "khuyến nghị",
  "cảnh báo",
  "chống chỉ định",
  "tương tác",
  "chỉ định",
  "cơ chế hoạt động",
  "lời khuyên",
  "điều quan trọng",
  "thành phần",
  "dinh dưỡng",
  "tác dụng",
];

// \b của JS chỉ coi [A-Za-z0-9_] là "ký tự từ", nên với chữ có dấu tiếng Việt
// (vd: "giúp") nó tạo ranh giới từ ngay giữa "gi" và "úp" -> match nhầm.
// Dùng lookaround theo \p{L}\p{N} (Unicode-aware) để tránh lỗi này.
const WORD_BOUNDARY_START = "(?<![\\p{L}\\p{N}_])";
const WORD_BOUNDARY_END = "(?![\\p{L}\\p{N}_])";

// ── Markdown emphasis / inline syntax ──
// Thứ tự xử lý RẤT quan trọng: link -> code -> strikethrough -> bold+italic
// (***) -> bold (**) -> italic (*) -> dọn dấu "*" lẻ còn sót. Nếu đảo thứ tự,
// các cặp lồng nhau (vd "***text***") sẽ bị regex "**" nuốt sai lệch.
const MARKDOWN_LINK_RE = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
const INLINE_CODE_RE = /`([^`]+)`/g;
const STRIKETHROUGH_RE = /~~(.+?)~~/g;
const MARKDOWN_BOLD_ITALIC_RE = /\*\*\*(.+?)\*\*\*/g;
const MARKDOWN_BOLD_RE = /\*\*(.+?)\*\*/g;
const MARKDOWN_ITALIC_RE = /\*(.+?)\*/g;

// Markdown heading "#", "##", "###"... -> tiêu đề in đậm.
const MARKDOWN_HEADING_RE = /^(#{1,6})\s+(.+)$/;

// Đường kẻ ngang markdown đứng riêng 1 dòng: "---", "***", "___" (>=3 ký tự
// cùng loại, không xen ký tự khác).
const HR_RE = /^(-{3,}|\*{3,}|_{3,})$/;

// Blockquote markdown: dòng bắt đầu bằng ">" (có hoặc không có khoảng trắng
// theo sau).
const BLOCKQUOTE_LINE_RE = /^>\s?/;

const INLINE_WARNING_RE = new RegExp(
  WORD_BOUNDARY_START +
    "(không nên|không được|tránh(?:\\s+dùng|\\s+ăn)?|nguy hiểm|nguy cơ cao|chống chỉ định|thận trọng|cảnh báo|khẩn cấp|cần đi khám ngay|gọi (?:cấp cứu|115) ngay|tuyệt đối không|quá liều|tác dụng phụ nghiêm trọng|phải tham khảo bác sĩ|hãy tham khảo bác sĩ)" +
    WORD_BOUNDARY_END,
  "giu"
);

const HIGHLIGHT_RE = new RegExp(
  WORD_BOUNDARY_START +
    "(HbA1c|Metformin|Insulin|Aspirin|Glucophage|Mixtard|Atoris|tiểu đường|đái tháo đường|hạ đường huyết|tăng đường huyết|đường huyết|tim mạch|thận|võng mạc|mắt|bàn chân|thần kinh ngoại biên|chỉ số đường huyết|calo|protein|đạm|chất béo|carbohydrate|carb|chất xơ|đường|natri|kali|canxi|sắt|vitamin\\s*[A-Za-z0-9]*|omega-3|cholesterol|huyết áp|kháng insulin|type\\s*1|type\\s*2|thai kỳ)" +
    WORD_BOUNDARY_END,
  "giu"
);

// "GI"/"GL" (viết tắt Glycemic Index/Load) chỉ tô đậm khi viết HOA nguyên vẹn,
// tránh khớp nhầm vào các âm tiết "gi"/"gl" rất phổ biến trong tiếng Việt.
const HIGHLIGHT_ABBR_RE = new RegExp(
  WORD_BOUNDARY_START + "(GI|GL)" + WORD_BOUNDARY_END,
  "gu"
);

// Dòng bullet CÓ marker rõ ràng, vd "  - Bullet 1", "    • Bullet cấp 2",
// "1. Section". Nhóm bắt: [1] = khoảng trắng thụt lề, [2] = marker, [3] = nội dung.
const BULLET_RE = /^([ \t\u200b\ufeff]*)([*•+-]|(?:\d+[.)]))\s+(.+)$/;

// Dòng CHỈ có marker số đứng riêng, không có nội dung theo sau, vd "1." đứng
// một mình trên cả dòng -> mục cấp cha của danh sách thứ tự.
const BULLET_ONLY_MARKER_RE = /^([ \t\u200b\ufeff]*)(\d+[.)])[ \t]*$/;

// Dòng dạng "**1. Nội dung**" hoặc "**- Nội dung**" / "**• Nội dung**" — cả
// marker LẪN nội dung đều bị LLM bọc chung trong một cặp "**" (thay vì chỉ bọc
// riêng nội dung). Nếu không xử lý riêng, marker sẽ không đứng ngay sau khoảng
// trắng đầu dòng (mà đứng sau "**"), khiến BULLET_RE/BULLET_ONLY_MARKER_RE
// không nhận diện được, dòng bị rơi xuống nhánh mặc định và hiện dạng đoạn in
// đậm phẳng thay vì mục danh sách thật sự.
const BOLD_WRAPPED_BULLET_RE = /^([ \t\u200b\ufeff]*)\*\*\s*(\d+[.)]|[•+-])\s+(.+?)\s*\*\*\s*$/;

// Dòng KHÔNG có marker "-"/"•"/số nào cả, nhưng có dạng "Nhãn: nội dung mô tả"
// trên cùng MỘT dòng (vd "Rau xanh đậm: Rau bina, cải xoăn..."). Rất phổ biến
// khi LLM liệt kê ý mà quên chèn dấu gạch đầu dòng. Coi mỗi dòng như vậy là
// một bullet phẳng (không dùng dấu ":" để suy luận CẤP LỒNG NHAU — cấp lồng
// vẫn chỉ do độ thụt lề đầu dòng quyết định, giống các bullet có marker).
const LABEL_LINE_RE = /^([ \t\u200b\ufeff]*)([^\s:：.][^:：\n]{0,58}?)[:：]\s+(\S.*)$/;

// Dấu "*" đơn còn sót lại ngay đầu phần nội dung sau nhãn (vd LLM viết
// "Nhãn: * nội dung" khi định làm marker con nhưng bị parser nuốt luôn vào
// nội dung do đã match LABEL_LINE_RE) -> dọn bỏ để không hiện dấu "*" thừa.
const STRAY_LEADING_STAR_RE = /^\*\s+/;

// Dòng KHÔNG có marker, kết thúc bằng ":" và KHÔNG có nội dung nào khác sau đó
// (vd "Ví dụ:", "Dưới đây là bảng so sánh chi tiết để bạn dễ hình dung:") ->
// tiêu đề dẫn dắt, in đậm, không phải bullet.
const isColonOnlyHeading = (strippedLine: string): boolean =>
  /[:：]$/.test(strippedLine) && strippedLine.length > 1 && strippedLine.length <= 140;

/**
 * Loại trừ các trường hợp LABEL_LINE_RE khớp NHẦM (không phải ý định liệt kê
 * "Nhãn: nội dung" của người viết), gồm:
 * - Giờ giấc dạng "7:30", "10:00 sáng..." -> label toàn số, rest bắt đầu bằng số.
 * - URL "https://...", "ftp://..." -> rest bắt đầu bằng "//".
 * - Tỷ lệ/phân số dạng số:số (vd "3: 1") -> cả label lẫn ký tự đầu rest đều là số.
 */
const isLikelyFalseLabelMatch = (label: string, rest: string): boolean => {
  const isNumericLabel = /^\d{1,4}$/.test(label);
  const restStartsWithDigit = /^\d/.test(rest);
  if (isNumericLabel && restStartsWithDigit) return true; // giờ giấc / tỷ lệ
  if (rest.startsWith("//")) return true; // URL dạng "https: //..." sau khi trim
  if (/^(https?|ftp)$/i.test(label)) return true; // URL dạng "https: //..."
  return false;
};

const escapeHtml = (raw: string): string =>
  raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

/**
 * Áp toàn bộ cú pháp inline markdown lên một chuỗi ĐÃ escape: link, code,
 * gạch ngang, đậm+nghiêng, đậm, nghiêng — theo đúng thứ tự để tránh các cặp
 * lồng nhau bị nhận nhầm. Bước cuối dọn sạch mọi dấu "*" còn sót lại không ghép
 * được thành cặp hợp lệ (LLM gõ thiếu dấu đóng), để không bao giờ lộ "*" thô
 * ra giao diện.
 *
 * Đánh đổi đã biết: nếu văn bản gốc dùng "*" với nghĩa khác (vd phép nhân
 * "2 * 3"), dấu "*" đó cũng sẽ bị dọn theo. Trường hợp này gần như không xảy
 * ra trong nội dung tư vấn y tế/dinh dưỡng tiếng Việt nên chấp nhận đánh đổi
 * để đổi lấy việc không bao giờ lộ markdown thô.
 */
const renderMarkdownEmphasis = (escaped: string): string => {
  let out = escaped.replace(
    MARKDOWN_LINK_RE,
    (_m, text: string, url: string) =>
      `<a href="${url}" target="_blank" rel="noreferrer" style="color:#2563eb;text-decoration:underline;">${text}</a>`
  );
  out = out.replace(
    INLINE_CODE_RE,
    (_m, code: string) =>
      `<code style="background:#eef1f5;padding:1px 5px;border-radius:4px;font-size:0.85em;">${code}</code>`
  );
  out = out.replace(STRIKETHROUGH_RE, (_m, inner: string) => `<s>${inner}</s>`);
  out = out.replace(MARKDOWN_BOLD_ITALIC_RE, (_m, inner: string) => `<b><i>${inner}</i></b>`);
  out = out.replace(MARKDOWN_BOLD_RE, (_m, inner: string) => `<b>${inner}</b>`);
  out = out.replace(MARKDOWN_ITALIC_RE, (_m, inner: string) => `<i>${inner}</i>`);
  out = out.replace(/\*+/g, "");
  return out;
};

const inlineFormat = (escaped: string): string => {
  let out = renderMarkdownEmphasis(escaped);
  out = out.replace(
    INLINE_WARNING_RE,
    (m) => `<span style="color:#dc2626;font-weight:700;">${m}</span>`
  );
  out = out.replace(HIGHLIGHT_RE, "<b>$1</b>");
  out = out.replace(HIGHLIGHT_ABBR_RE, "<b>$1</b>");
  return out;
};

// ── Table parsing (đã nới lỏng nhưng có kiểm tra hợp lệ) ──
// Chấp nhận bảng markdown dùng "|" và cả bảng do LLM/backend trả về bằng tab.
// Để tránh dựng "bảng ma" từ một câu văn tình cờ có dấu phân cách, MỘT bảng chỉ
// thực sự được dựng khi số cột của header và hàng dữ liệu đầu tiên gần khớp nhau
// (chênh lệch tối đa 1 cột) và có tối thiểu 2 cột.
const isTableRow = (line: string): boolean => {
  const s = line.trim();
  return s.includes("|") && splitTableCells(s).length >= 2;
};

const isTableSeparator = (line: string): boolean => {
  const s = line.trim().replace(/^\||\|$/g, "");
  const cells = s.split("|").map((c) => c.trim());
  return cells.length >= 2 && cells.every((c) => /^:?-{2,}:?$/.test(c));
};

const splitPipeTableCells = (line: string): string[] =>
  line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

const splitTableCells = (line: string): string[] =>
  line.includes("|") ? splitPipeTableCells(line) : [];

const isValidTableShape = (headerCells: string[], bodyRows: string[][]): boolean => {
  if (headerCells.length < 2 || bodyRows.length === 0) return false;
  const validRows = bodyRows.filter((row) => row.length >= 2);
  if (validRows.length === 0) return false;
  const matchingRows = validRows.filter((row) => Math.abs(headerCells.length - row.length) <= 1);
  return matchingRows.length / validRows.length >= 0.75;
};

const normalizeTableRow = (row: string[], targetLength: number): string[] => {
  if (row.length === targetLength) return row;
  if (row.length > targetLength) {
    return [...row.slice(0, targetLength - 1), row.slice(targetLength - 1).join(" ")];
  }
  return [...row, ...Array.from({ length: targetLength - row.length }, () => "")];
};

const renderHtmlTable = (headerCells: string[], bodyRows: string[][]): string => {
  const normalizedBodyRows = bodyRows.map((row) => normalizeTableRow(row, headerCells.length));
  const ths = headerCells
    .map(
      (c) =>
        `<th style="padding:8px 10px;border:1px solid #dbe4ff;background:#eef4ff;text-align:left;font-size:13px;">${inlineFormat(
          escapeHtml(c)
        )}</th>`
    )
    .join("");
  const trs = normalizedBodyRows
    .map((row) => {
      const tds = row
        .map(
          (c) =>
            `<td style="padding:8px 10px;border:1px solid #e2e8f0;font-size:13px;">${inlineFormat(
              escapeHtml(c)
            )}</td>`
        )
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  return `<div class="chat-answer-table-wrap"><table style="border-collapse:collapse;width:100%;min-width:520px;margin:10px 0;"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div>`;
};

// Symbol xoay vòng cho danh sách không thứ tự theo độ sâu: cấp 1 = chấm tròn đặc
// (disc), cấp 2 = vòng tròn rỗng (circle), cấp 3 = ô vuông (square). Từ cấp 4 trở
// đi lặp lại chu kỳ này.
const UNORDERED_BULLET_STYLES = ["disc", "circle", "square"];

const measureIndent = (whitespace: string): number => whitespace.replace(/\t/g, "    ").length;

const leadingWhitespaceOf = (rawLine: string): string => rawLine.match(/^[ \t\u200b\ufeff]*/)?.[0] ?? "";

/**
 * Chuyển văn bản trả lời thô của chatbot thành HTML. Các trường hợp được xử lý:
 * - Heading markdown "#".."######", đường kẻ ngang "---"/"***"/"___", blockquote "> ".
 * - Nhấn mạnh inline: link [chữ](url), code `...`, gạch ngang ~~...~~,
 *   đậm+nghiêng ***...***, đậm **...**, nghiêng *...*; dọn sạch mọi dấu "*" lẻ
 *   không ghép được cặp thay vì hiện thô ra UI.
 * - Cảnh báo (đỏ đậm) và từ khóa y khoa (đậm).
 * - Danh sách lồng cấp nhiều tầng dựa theo ĐỘ THỤT LỀ thực tế (disc/circle/square
 *   xoay vòng theo độ sâu); áp dụng cho cả bullet có marker "-•*số" lẫn dòng
 *   "Nhãn: nội dung" không marker (có loại trừ giờ giấc/URL/tỷ lệ để tránh
 *   nhận nhầm) và dòng in đậm bọc luôn cả marker ("**1. ...**", "**- ...**").
 * - Danh sách số ở CẤP GỐC được đánh số LIÊN TỤC xuyên suốt cả câu trả lời dù
 *   bị ngắt quãng bởi đoạn văn/bullet khác ở giữa.
 * - Dòng tiếp nối (LLM xuống dòng giữa chừng một bullet dài, có thụt lề nhưng
 *   không lặp lại marker) được nối vào đúng mục bullet đang mở thay vì tách
 *   thành đoạn văn rời rạc.
 * - Bảng markdown: chịu được thiếu dấu "|" ở đầu/cuối hàng và thiếu dòng phân
 *   cách "---", nhưng có kiểm tra số cột hợp lý để không dựng "bảng ma" từ một
 *   câu văn tình cờ có dấu "|"; nếu header không có hàng dữ liệu nào theo sau
 *   (phản hồi bị cắt cụt), không dựng bảng rỗng mà để hiển thị như văn bản
 *   thường.
 *
 * An toàn XSS: mọi nội dung gốc đều được escape trước khi chèn thẻ định dạng;
 * link chỉ chấp nhận scheme http/https.
 *
 * Giới hạn đã biết (không thể tự khắc phục ở tầng hiển thị): nếu backend trả
 * bảng dùng ký tự tab thay vì dấu "|" để phân cách cột, hoặc cắt cụt dữ liệu
 * giữa chừng do vượt giới hạn token, phần dữ liệu bị thiếu sẽ không tự phục
 * hồi được — cần kiểm tra ở phía backend/RAG service.
 */
export const formatChatAnswer = (text: string): string => {
  if (!text) return "";

  interface ListNode {
    ordered: boolean;
    html: string;
    children: ListNode[];
  }

  interface StackFrame {
    indent: number;
    children: ListNode[];
  }

  const rawLines = text.split(/\r?\n/);
  const formattedLines: string[] = [];

  let listRoot: ListNode[] = [];
  let listStack: StackFrame[] = [{ indent: -1, children: listRoot }];
  let listActive = false;
  // Node bullet gần nhất vừa được tạo, dùng để nối các dòng tiếp nối (wrap)
  // của cùng một bullet dài vào đúng chỗ thay vì tách thành đoạn văn rời rạc.
  const listState: { lastNode: ListNode | null } = { lastNode: null };

  // Bộ đếm cho danh sách số Ở CẤP GỐC, sống suốt cả hàm formatChatAnswer (không
  // reset theo từng lần flushList). Danh sách số lồng bên trong một bullet khác
  // (không phải cấp gốc) vẫn tự restart về 1 như hành vi <ol> chuẩn.
  let rootOrderedCounter = 0;

  const pushListNode = (indent: number, ordered: boolean, html: string): ListNode => {
    while (listStack.length > 1 && listStack[listStack.length - 1].indent >= indent) {
      listStack.pop();
    }
    const node: ListNode = { ordered, html, children: [] };
    listStack[listStack.length - 1].children.push(node);
    listStack.push({ indent, children: node.children });
    listActive = true;
    listState.lastNode = node;
    return node;
  };

  const renderListNodes = (nodes: ListNode[], unorderedDepth: number, isRoot: boolean): string => {
    let html = "";
    let idx = 0;
    while (idx < nodes.length) {
      const ordered = nodes[idx].ordered;
      const group: ListNode[] = [];
      while (idx < nodes.length && nodes[idx].ordered === ordered) {
        group.push(nodes[idx]);
        idx += 1;
      }

      if (ordered) {
        const items = group
          .map((node) => {
            const childHtml = node.children.length
              ? renderListNodes(node.children, unorderedDepth, false)
              : "";
            return `<li style="margin:0.2rem 0;">${node.html}${childHtml}</li>`;
          })
          .join("");
        // Chỉ danh sách số ở CẤP GỐC mới dùng start= để nối số liên tục xuyên
        // suốt các lần flush khác nhau; danh sách số lồng trong bullet khác thì
        // để trình duyệt tự đánh số lại từ 1 như bình thường.
        const startAttr = isRoot ? ` start="${rootOrderedCounter + 1}"` : "";
        if (isRoot) rootOrderedCounter += group.length;
        html += `<ol style="margin:0.35rem 0 0.6rem 1.25rem;padding-left:1.1rem;"${startAttr}>${items}</ol>`;
      } else {
        const styleType = UNORDERED_BULLET_STYLES[unorderedDepth % UNORDERED_BULLET_STYLES.length];
        const items = group
          .map((node) => {
            const childHtml = node.children.length
              ? renderListNodes(node.children, unorderedDepth + 1, false)
              : "";
            return `<li style="margin:0.2rem 0;">${node.html}${childHtml}</li>`;
          })
          .join("");
        html += `<ul style="list-style-type:${styleType};margin:0.3rem 0 0.5rem 1.25rem;padding-left:1.1rem;">${items}</ul>`;
      }
    }
    return html;
  };

  const flushList = () => {
    if (!listActive) return;
    formattedLines.push(renderListNodes(listRoot, 0, true));
    listRoot = [];
    listStack = [{ indent: -1, children: listRoot }];
    listActive = false;
    listState.lastNode = null;
  };

  let i = 0;
  const n = rawLines.length;
  while (i < n) {
    const rawLine = rawLines[i];
    const line = rawLine.trim();

    // ── Bảng ──
    // Chỉ dựng bảng markdown khi có dòng phân cách chuẩn "|---|---|".
    // Trước đây parser cho phép thiếu separator nên dễ nhận nhầm văn bản thường
    // có dấu "|" thành bảng, làm UI bị vỡ.
    if (isTableRow(line)) {
      const hasSeparator = i + 1 < n && isTableSeparator(rawLines[i + 1]);
      const bodyStart = i + 2;
      if (hasSeparator && bodyStart < n && isTableRow(rawLines[bodyStart])) {
        const headerCells = splitTableCells(line);
        let j = bodyStart;
        const bodyRows: string[][] = [];
        while (j < n && isTableRow(rawLines[j])) {
          bodyRows.push(splitTableCells(rawLines[j]));
          j += 1;
        }
        if (isValidTableShape(headerCells, bodyRows)) {
          flushList();
          formattedLines.push(renderHtmlTable(headerCells, bodyRows));
          i = j;
          continue;
        }
        // Không có hàng dữ liệu hợp lệ theo sau (bảng bị cắt cụt, hoặc số cột
        // không khớp -> nhiều khả năng không phải bảng thật) -> không dựng
        // bảng, để dòng này rơi xuống xử lý như văn bản thường bên dưới.
      }
    }

    if (!line) {
      if (!listActive) {
        formattedLines.push("");
      }
      i += 1;
      continue;
    }

    // ── Blockquote: gộp các dòng "> " liên tiếp thành 1 khối ──
    if (BLOCKQUOTE_LINE_RE.test(line)) {
      flushList();
      const quoteLines: string[] = [];
      let j = i;
      while (j < n && BLOCKQUOTE_LINE_RE.test(rawLines[j].trim())) {
        quoteLines.push(rawLines[j].trim().replace(BLOCKQUOTE_LINE_RE, ""));
        j += 1;
      }
      const inner = quoteLines.map((q) => inlineFormat(escapeHtml(q))).join("<br>");
      formattedLines.push(
        `<blockquote style="margin:8px 0;padding:8px 12px;border-left:3px solid #94a3b8;background:#f8fafc;color:#475569;">${inner}</blockquote>`
      );
      i = j;
      continue;
    }

    // ── Đường kẻ ngang "---" / "***" / "___" đứng riêng 1 dòng ──
    if (HR_RE.test(line)) {
      flushList();
      formattedLines.push('<hr style="border:none;border-top:1px solid #e2e8f0;margin:10px 0;" />');
      i += 1;
      continue;
    }

    const strippedForMatch = line.replace(/\*/g, "").trim();
    const lower = strippedForMatch.toLowerCase();

    if (IMPORTANT_PREFIXES.some((prefix) => lower.startsWith(prefix))) {
      flushList();
      formattedLines.push(
        `<span style="color:#dc2626;font-weight:700;">${renderMarkdownEmphasis(escapeHtml(line))}</span>`
      );
      i += 1;
      continue;
    }

    if (lower.startsWith("luôn tham khảo ý kiến bác sĩ")) {
      flushList();
      formattedLines.push(`<b>${renderMarkdownEmphasis(escapeHtml(line))}</b>`);
      i += 1;
      continue;
    }

    if (HEADING_PREFIXES.some((prefix) => lower === prefix || lower.startsWith(`${prefix} `))) {
      flushList();
      formattedLines.push(`<b>${renderMarkdownEmphasis(escapeHtml(line))}</b>`);
      i += 1;
      continue;
    }

    const mdHeadingMatch = MARKDOWN_HEADING_RE.exec(line);
    if (mdHeadingMatch) {
      flushList();
      const content = renderMarkdownEmphasis(escapeHtml(mdHeadingMatch[2].trim()));
      formattedLines.push(
        `<div style="font-weight:700;font-size:0.95rem;margin:10px 0 4px;color:#0f172a;">${content}</div>`
      );
      i += 1;
      continue;
    }

    const boldBulletMatch = BOLD_WRAPPED_BULLET_RE.exec(rawLine);
    if (boldBulletMatch) {
      const indent = measureIndent(boldBulletMatch[1]);
      const marker = boldBulletMatch[2];
      const ordered = /^\d+[.)]$/.test(marker);
      const html = `<b>${inlineFormat(escapeHtml(boldBulletMatch[3].trim()))}</b>`;
      pushListNode(indent, ordered, html);
      i += 1;
      continue;
    }

    const bulletOnlyMatch = BULLET_ONLY_MARKER_RE.exec(rawLine);
    if (bulletOnlyMatch) {
      const indent = measureIndent(bulletOnlyMatch[1]);
      pushListNode(indent, true, "");
      i += 1;
      continue;
    }

    const bulletMatch = BULLET_RE.exec(rawLine);
    if (bulletMatch) {
      const indent = measureIndent(bulletMatch[1]);
      const marker = bulletMatch[2];
      const bulletText = bulletMatch[3].trim();
      const ordered = /^\d+[.)]$/.test(marker);
      const html = inlineFormat(escapeHtml(bulletText));
      pushListNode(indent, ordered, html);
      i += 1;
      continue;
    }

    // Không có marker nào cả, nhưng kết thúc bằng ":" và không có nội dung gì
    // khác -> tiêu đề dẫn dắt (không phải bullet).
    if (isColonOnlyHeading(strippedForMatch)) {
      flushList();
      formattedLines.push(`<b>${renderMarkdownEmphasis(escapeHtml(line))}</b>`);
      i += 1;
      continue;
    }

    // Không có marker, nhưng có dạng "Nhãn: nội dung" trên cùng một dòng ->
    // vẫn bullet hoá (phẳng, không dùng dấu ":" để suy đoán cấp lồng — cấp lồng
    // ở đây do độ thụt lề của chính dòng này quyết định). Có loại trừ các
    // trường hợp khớp nhầm (giờ giấc, URL, tỷ lệ số:số).
    const labelMatch = LABEL_LINE_RE.exec(rawLine);
    if (labelMatch) {
      const label = labelMatch[2].trim();
      const restRaw = labelMatch[3].trim();
      if (!isLikelyFalseLabelMatch(label, restRaw)) {
        const indent = measureIndent(labelMatch[1]);
        const rest = restRaw.replace(STRAY_LEADING_STAR_RE, "");
        const html = `<b>${renderMarkdownEmphasis(escapeHtml(label))}:</b> ${inlineFormat(escapeHtml(rest))}`;
        pushListNode(indent, false, html);
        i += 1;
        continue;
      }
      // Khớp nhầm (giờ giấc/URL/tỷ lệ) -> để rơi xuống các nhánh bên dưới.
    }

    // Dòng tiếp nối (wrap) của một bullet dài: không khớp bất kỳ marker/label
    // nào ở trên, nhưng đang có danh sách mở dở và dòng này có thụt lề (>0) ->
    // nối vào đúng mục bullet gần nhất thay vì tách thành đoạn văn rời rạc.
    const continuationNode = listState.lastNode;
    if (listActive && continuationNode && measureIndent(leadingWhitespaceOf(rawLine)) > 0) {
      continuationNode.html += " " + inlineFormat(escapeHtml(line));
      i += 1;
      continue;
    }

    flushList();
    formattedLines.push(inlineFormat(escapeHtml(line)));
    i += 1;
  }

  flushList();
  return formattedLines.join("<br>");
};
