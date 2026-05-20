"""
================================================================
BƯỚC 2: PDF BUILDER — Chuẩn Hóa Tài Liệu Thành PDF
================================================================

TẠI SAO CẦN BƯỚC NÀY?
  Tài liệu crawl về có định dạng .txt lộn xộn, encoding khác
  nhau, không thống nhất. Bước này:
  1. Đọc tất cả file .txt từ data/raw/
  2. Làm sạch text (bỏ ký tự lạ, chuẩn hóa khoảng trắng)
  3. Xuất ra PDF chuẩn với font Unicode (hỗ trợ tiếng Việt)
  4. Lưu vào data/pdfs/ để bước RAG đọc vào

LUỒNG:
  data/raw/*.txt
      │
      ▼
  Làm sạch & chuẩn hóa text
      │
      ▼
  Tạo PDF (fpdf2, hỗ trợ UTF-8)
      │
      ▼
  data/pdfs/*.pdf

CÁCH CHẠY:
  python src/preprocessor/pdf_builder.py
================================================================
"""

import re
import json
from pathlib import Path
from typing import Optional
from loguru import logger
from tqdm import tqdm
from fpdf import FPDF
from fpdf.enums import XPos, YPos


# ── Thư mục ────────────────────────────────────────────────
RAW_DIR   = Path("data/raw")
PDF_DIR   = Path("data/pdfs")
PROC_DIR  = Path("data/processed")

for d in [PDF_DIR, PROC_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def find_unicode_fonts() -> tuple[Path, Path]:
    """Return regular/bold TTF fonts that can render Vietnamese text."""
    font_pairs = [
        (
            Path("DejaVuSansCondensed.ttf"),
            Path("DejaVuSansCondensed-Bold.ttf"),
        ),
        (
            Path("fonts/DejaVuSansCondensed.ttf"),
            Path("fonts/DejaVuSansCondensed-Bold.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]

    for regular, bold in font_pairs:
        if regular.exists() and bold.exists():
            return regular, bold

    raise FileNotFoundError(
        "No Unicode TTF font found. Install DejaVu Sans or use Windows Arial/Segoe UI fonts."
    )


# ================================================================
# CLASS PDF CÓ HỖ TRỢ TIẾNG VIỆT
# fpdf2 hỗ trợ Unicode natively nếu dùng font DejaVu
# ================================================================
class VietnamesePDF(FPDF):
    """
    PDF class tuỳ chỉnh với header/footer tự động
    và hỗ trợ đầy đủ Unicode (tiếng Việt).
    """

    def __init__(self, title: str = "", category: str = "", source_url: str = ""):
        super().__init__()
        self.doc_title    = title
        self.doc_category = category
        self.source_url   = source_url

        # Thêm font DejaVu hỗ trợ Unicode/tiếng Việt
        # fpdf2 bundle sẵn DejaVu, không cần tải thêm
        regular_font, bold_font = find_unicode_fonts()
        self.add_font("DejaVu", style="", fname=str(regular_font))
        self.add_font("DejaVu", style="B", fname=str(bold_font))

        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        """Header xuất hiện trên mỗi trang."""
        # Logo/badge
        self.set_fill_color(41, 128, 185)   # Màu xanh y tế
        self.rect(0, 0, 210, 12, style="F")

        self.set_font("DejaVu", style="B", size=9)
        self.set_text_color(255, 255, 255)
        self.set_y(2)
        self.cell(0, 8, "Healthcare RAG — Kho Tri Thức Y Khoa Tiểu Đường",
                  align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Category badge
        self.set_y(14)
        self.set_font("DejaVu", style="", size=8)
        self.set_text_color(100, 100, 100)
        category_label = {
            "tieu_duong_type2": "Tiểu Đường Type 2",
            "chi_so_duong_huyet": "Chỉ Số Đường Huyết",
            "che_do_an": "Chế Độ Ăn Kiêng",
            "dieu_tri": "Điều Trị & Thuốc",
            "the_duc_loi_song": "Thể Dục & Lối Sống",
        }.get(self.doc_category, self.doc_category)
        self.cell(0, 6, f"Danh mục: {category_label}",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def footer(self):
        """Footer xuất hiện ở cuối mỗi trang."""
        self.set_y(-15)
        self.set_font("DejaVu", style="", size=7)
        self.set_text_color(150, 150, 150)

        # Nguồn tài liệu (cắt ngắn nếu URL dài)
        url_display = self.source_url[:80] + "..." if len(self.source_url) > 80 else self.source_url
        self.cell(0, 5, f"Nguồn: {url_display}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Số trang
        self.set_y(-10)
        self.cell(0, 5, f"Trang {self.page_no()}", align="C")

    def add_title(self, title: str):
        """Thêm tiêu đề tài liệu."""
        self.set_font("DejaVu", style="B", size=16)
        self.set_text_color(31, 97, 141)   # Xanh đậm
        self.multi_cell(0, 10, title, align="L",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

        # Đường kẻ phân cách
        self.set_draw_color(41, 128, 185)
        self.set_line_width(0.5)
        self.line(self.get_x(), self.get_y(), 200, self.get_y())
        self.ln(6)

    def add_body_text(self, text: str):
        """
        Thêm nội dung chính.
        multi_cell tự động xuống dòng khi text dài.
        """
        self.set_font("DejaVu", style="", size=10)
        self.set_text_color(40, 40, 40)     # Gần đen

        # Chia thành đoạn theo dòng trống
        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Đoạn ngắn (tiêu đề phụ) → in đậm
            if len(para) < 80 and not para.endswith(".") and para.isupper():
                self.set_font("DejaVu", style="B", size=11)
                self.set_text_color(31, 97, 141)
            else:
                self.set_font("DejaVu", style="", size=10)
                self.set_text_color(40, 40, 40)

            self.multi_cell(0, 6, para, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(3)


# ================================================================
# HÀM TIỀN XỬ LÝ TEXT
# ================================================================

def parse_raw_file(filepath: Path) -> dict:
    """
    Đọc file .txt từ crawler và tách metadata khỏi content.

    Format file (do crawler tạo ra):
      ===METADATA===
      { "url": "...", "category": "..." }
      ===CONTENT===
      (nội dung tài liệu)

    Returns:
        dict với keys: metadata, content
    """
    text = filepath.read_text(encoding="utf-8")

    if "===METADATA===" in text and "===CONTENT===" in text:
        parts = text.split("===CONTENT===", 1)
        meta_part = parts[0].replace("===METADATA===", "").strip()
        content   = parts[1].strip()
        try:
            metadata = json.loads(meta_part)
        except json.JSONDecodeError:
            metadata = {"source_name": filepath.stem, "url": "", "category": "unknown"}
    else:
        # File không có metadata → dùng thông tin từ tên file
        metadata = {
            "source_name": filepath.stem,
            "url": "",
            "category": filepath.stem.split("__")[0] if "__" in filepath.stem else "unknown",
        }
        content = text.strip()

    return {"metadata": metadata, "content": content}


def clean_text(text: str) -> str:
    """
    Làm sạch text trước khi đưa vào PDF.

    Các bước:
    1. Xóa ký tự điều khiển (không in được)
    2. Chuẩn hóa khoảng trắng và xuống dòng
    3. Bỏ dòng chỉ có ký tự đặc biệt (|, -, =)
    4. Ghép đoạn ngắn liền nhau
    """
    # Bước 1: Xóa ký tự điều khiển (giữ lại \n và \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Drop emoji/supplementary-plane symbols that common PDF fonts cannot render.
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)

    # Bước 2: Chuẩn hóa nhiều dòng trống → tối đa 2 dòng
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Bước 3: Bỏ dòng chỉ có ký tự phân cách
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Bỏ dòng toàn dấu gạch, dấu bằng, ký tự bảng
        if re.match(r'^[-=|_*•·]{3,}$', stripped):
            continue
        # Bỏ dòng quá ngắn (có thể là artifact của HTML)
        if stripped and len(stripped) < 3:
            continue
        cleaned.append(line.rstrip())

    text = "\n".join(cleaned)

    # Bước 4: Chuẩn hóa khoảng trắng trong dòng
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()


def extract_title_from_content(content: str, fallback: str) -> str:
    """
    Tự động tìm tiêu đề từ nội dung.

    Ưu tiên:
    1. Dòng đầu tiên không rỗng (thường là H1)
    2. Fallback về tên file
    """
    for line in content.splitlines():
        line = line.strip()
        if len(line) > 10:  # Dòng đủ dài để là tiêu đề
            return line[:200]  # Cắt tối đa 200 ký tự
    return fallback


# ================================================================
# CLASS CHÍNH: PDF BUILDER
# ================================================================

class PDFBuilder:
    """
    Chuyển đổi tất cả file .txt trong data/raw/ thành PDF chuẩn.
    """

    def __init__(self):
        self.raw_dir  = RAW_DIR
        self.pdf_dir  = PDF_DIR
        self.proc_dir = PROC_DIR

    def build_one(self, txt_file: Path) -> Optional[Path]:
        """
        Build PDF từ một file .txt.

        Args:
            txt_file: Đường dẫn file .txt đầu vào

        Returns:
            Đường dẫn file PDF đầu ra, hoặc None nếu thất bại
        """
        # Đọc và parse file
        parsed = parse_raw_file(txt_file)
        metadata = parsed["metadata"]
        content  = parsed["content"]

        if not content or len(content) < 100:
            logger.warning(f"  ⚠ Nội dung quá ngắn: {txt_file.name}")
            return None

        # Làm sạch text
        clean_content = clean_text(content)

        # Lưu text đã làm sạch (để debug)
        proc_path = self.proc_dir / txt_file.name
        proc_path.write_text(clean_content, encoding="utf-8")

        # Tìm tiêu đề
        title = extract_title_from_content(
            clean_content,
            fallback=metadata.get("source_name", txt_file.stem)
        )

        # Tạo PDF
        try:
            pdf = VietnamesePDF(
                title=title,
                category=metadata.get("category", "unknown"),
                source_url=metadata.get("url", ""),
            )
            pdf.add_page()
            pdf.add_title(title)
            pdf.add_body_text(clean_content)

            # Lưu PDF
            pdf_name = txt_file.stem + ".pdf"
            pdf_path = self.pdf_dir / pdf_name
            pdf.output(str(pdf_path))

            logger.success(f"  ✅ PDF: {pdf_name} ({len(clean_content):,} ký tự)")
            return pdf_path

        except Exception as e:
            logger.error(f"  ✗ Lỗi tạo PDF {txt_file.name}: {e}")
            return None

    def build_all(self) -> list:
        """Build PDF cho tất cả file trong data/raw/."""
        txt_files = sorted(self.raw_dir.glob("*.txt"))
        # Bỏ qua file metadata tổng hợp
        txt_files = [f for f in txt_files if f.name != "crawl_metadata.json"]

        if not txt_files:
            logger.warning("⚠ Không có file .txt nào trong data/raw/")
            logger.info("   Hãy chạy crawler trước: python src/crawler/medical_crawler.py")
            return []

        logger.info(f"🔨 Đang build PDF cho {len(txt_files)} file...")
        results = []

        for txt_file in tqdm(txt_files, desc="Building PDFs"):
            logger.info(f"\n  📄 {txt_file.name}")
            pdf_path = self.build_one(txt_file)
            results.append({
                "input": str(txt_file),
                "output": str(pdf_path) if pdf_path else None,
                "status": "success" if pdf_path else "failed",
            })

        # Thống kê
        ok  = sum(1 for r in results if r["status"] == "success")
        err = sum(1 for r in results if r["status"] == "failed")
        logger.info(f"\n{'='*50}")
        logger.info(f"📊 KẾT QUẢ BUILD PDF:")
        logger.info(f"   ✅ Thành công: {ok}")
        logger.info(f"   ✗ Thất bại  : {err}")
        logger.info(f"   📁 PDF lưu tại: data/pdfs/")
        logger.info(f"{'='*50}")

        return results

    def build_sample_knowledge(self):
        """
        Tạo tài liệu mẫu nếu chưa crawl được.
        Đảm bảo hệ thống RAG luôn có dữ liệu để chạy demo.
        """
        logger.info("📝 Tạo tài liệu mẫu về tiểu đường...")

        sample_docs = {
            "tieu_duong_type2__overview_sample.txt": {
                "metadata": {
                    "source_name": "overview_sample",
                    "url": "https://example.com/sample",
                    "category": "tieu_duong_type2",
                    "language": "vi",
                    "crawled_at": "2024-01-01T00:00:00",
                    "char_count": 0,
                },
                "content": """Bệnh Tiểu Đường Type 2 - Tổng Quan

Bệnh tiểu đường type 2 (đái tháo đường type 2) là tình trạng cơ thể không sử dụng insulin hiệu quả, dẫn đến lượng đường trong máu cao hơn mức bình thường.

NGUYÊN NHÂN
Tiểu đường type 2 xảy ra khi tế bào của cơ thể kháng insulin (kháng insulin), hoặc tuyến tụy không sản xuất đủ insulin. Insulin là hormone giúp đường (glucose) từ máu đi vào tế bào để cung cấp năng lượng.

YẾU TỐ NGUY CƠ
- Thừa cân, béo phì (đặc biệt mỡ bụng)
- Ít vận động thể lực
- Tiền sử gia đình có người bị tiểu đường
- Tuổi trên 45
- Tiền đái tháo đường (đường huyết cao hơn bình thường nhưng chưa đến mức tiểu đường)
- Huyết áp cao, mỡ máu cao

TRIỆU CHỨNG
- Khát nước nhiều, tiểu nhiều
- Mệt mỏi, thiếu năng lượng
- Nhìn mờ
- Vết thương lâu lành
- Tê bì chân tay
- Nhiễm trùng tái phát (nấm, đường tiết niệu)
Lưu ý: Nhiều người tiểu đường type 2 không có triệu chứng rõ ràng trong giai đoạn đầu.

CHỈ SỐ ĐƯỜNG HUYẾT CHẨN ĐOÁN
- Bình thường khi đói: < 100 mg/dL (5.6 mmol/L)
- Tiền đái tháo đường: 100–125 mg/dL
- Tiểu đường: ≥ 126 mg/dL (đo 2 lần riêng biệt)
- HbA1c (phản ánh đường huyết 3 tháng): ≥ 6.5% là tiểu đường

BIẾN CHỨNG NẾU KHÔNG KIỂM SOÁT
- Tim mạch: nhồi máu cơ tim, đột quỵ
- Thận: suy thận mãn tính
- Mắt: mù lòa do bệnh võng mạc tiểu đường
- Thần kinh: tê liệt, đau thần kinh ngoại biên
- Bàn chân: loét, hoại tử có thể phải cắt cụt

KIỂM SOÁT BỆNH
Tiểu đường type 2 có thể được kiểm soát tốt bằng:
1. Thay đổi lối sống (chế độ ăn + tập thể dục)
2. Thuốc uống (Metformin là lựa chọn đầu tay)
3. Insulin (khi cần thiết)
4. Theo dõi đường huyết định kỳ
""",
            },
            "che_do_an__diet_sample.txt": {
                "metadata": {
                    "source_name": "diet_sample",
                    "url": "https://example.com/diet",
                    "category": "che_do_an",
                    "language": "vi",
                    "crawled_at": "2024-01-01T00:00:00",
                    "char_count": 0,
                },
                "content": """Chế Độ Ăn Cho Người Tiểu Đường Type 2

NGUYÊN TẮC CƠ BẢN
Không có chế độ ăn "một size cho tất cả" với tiểu đường. Mục tiêu chính là kiểm soát lượng carbohydrate (tinh bột, đường) để tránh đường huyết tăng đột ngột sau ăn.

CHỈ SỐ GLYCEMIC INDEX (GI)
GI đo tốc độ thức ăn làm tăng đường huyết:
- GI thấp (< 55): tốt cho người tiểu đường
- GI trung bình (55–70): ăn vừa phải
- GI cao (> 70): hạn chế tối đa

THỰC PHẨM NÊN ĂN
Rau xanh không tinh bột: rau muống, cải xanh, bông cải, dưa leo, cà chua
Protein nạc: ức gà, cá (đặc biệt cá béo như cá hồi, cá thu), đậu hũ, trứng
Ngũ cốc nguyên hạt: gạo lứt, yến mạch, bánh mì nguyên cám
Chất béo lành mạnh: dầu ô liu, bơ (avocado), hạt óc chó, hạnh nhân
Trái cây GI thấp: táo, lê, cam, bưởi, dâu tây

THỰC PHẨM CẦN HẠN CHẾ
Cơm trắng, bánh mì trắng, bún, phở, mì (GI cao)
Đồ ngọt: bánh kẹo, nước ngọt, chè, kem
Thức ăn chiên xào nhiều dầu mỡ
Thịt mỡ, thịt chế biến sẵn (xúc xích, thịt nguội)
Rượu bia: làm hạ đường huyết đột ngột, nguy hiểm

VÍ DỤ MỘT NGÀY ĂN LÀNH MẠNH
Bữa sáng: Cháo yến mạch + 1 quả trứng luộc + rau xanh
Bữa trưa: Cơm gạo lứt (1/2 chén nhỏ) + cá kho + canh rau
Bữa tối: Bún (nhỏ) hoặc khoai lang + thịt gà + rau xào
Bữa phụ: Một nắm hạt (hạnh nhân, óc chó) hoặc 1 quả táo

VỀ PHỞ VÀ BÚN
Phở và bún có GI cao (60–70), làm đường huyết tăng nhanh. Nếu ăn:
- Chọn phần nhỏ (nửa tô bình thường)
- Tăng rau giá, rau thơm
- Giảm nước dùng (nhiều muối và đường)
- Ăn protein (thịt, trứng) trước để làm chậm hấp thu đường
- Đo đường huyết sau ăn 1-2 giờ để xem phản ứng cơ thể

PHÂN CHIA BỮA ĂN
Nên ăn 3 bữa chính + 1-2 bữa phụ nhỏ.
Không bỏ bữa: dễ gây hạ đường huyết (nếu đang dùng thuốc).
Ăn đúng giờ giúp ổn định đường huyết.
""",
            },
            "chi_so_duong_huyet__monitoring_sample.txt": {
                "metadata": {
                    "source_name": "monitoring_sample",
                    "url": "https://example.com/monitoring",
                    "category": "chi_so_duong_huyet",
                    "language": "vi",
                    "crawled_at": "2024-01-01T00:00:00",
                    "char_count": 0,
                },
                "content": """Theo Dõi Đường Huyết - Hướng Dẫn Chi Tiết

TẠI SAO CẦN THEO DÕI ĐƯỜNG HUYẾT?
Đường huyết thay đổi liên tục theo bữa ăn, hoạt động thể lực và stress. Theo dõi giúp bạn hiểu cơ thể phản ứng như thế nào và điều chỉnh kịp thời.

CHỈ SỐ MỤC TIÊU (theo ADA 2024)
Đường huyết lúc đói (trước ăn sáng): 80–130 mg/dL
Đường huyết sau ăn 2 giờ: < 180 mg/dL
HbA1c (3 tháng): < 7% (tốt nhất < 6.5% nếu không bị hạ đường huyết)

KHI NÀO ĐO ĐƯỜNG HUYẾT?
Trước bữa ăn (đặc biệt bữa sáng): phản ánh đường huyết nền
Sau bữa ăn 1-2 giờ: xem thức ăn ảnh hưởng thế nào
Trước khi tập thể dục và sau khi tập
Khi cảm thấy chóng mặt, vã mồ hôi (nghi hạ đường huyết)
Trước khi đi ngủ (nếu đang dùng insulin)

HẠ ĐƯỜNG HUYẾT (Hypoglycemia)
Đường huyết < 70 mg/dL là hạ đường huyết - CẦN XỬ TRÍ NGAY.
Triệu chứng: run tay, vã mồ hôi, tim đập nhanh, chóng mặt, đói cồn cào, mờ mắt.

XỬ TRÍ HẠ ĐƯỜNG HUYẾT: Quy tắc 15-15
Uống ngay 15g đường: 3-4 viên kẹo glucose, hoặc 150ml nước cam, hoặc 1 thìa canh đường hoà nước.
Chờ 15 phút, đo lại.
Nếu vẫn < 70 mg/dL: lặp lại.
Sau khi đường huyết ổn: ăn nhẹ (bánh mì, chuối) để duy trì.

TĂNG ĐƯỜNG HUYẾT (Hyperglycemia)
Đường huyết > 250 mg/dL: liên hệ bác sĩ.
Đường huyết > 300 mg/dL: nguy hiểm, cần cấp cứu.
Triệu chứng: khát nước nhiều, tiểu nhiều, mệt mỏi, đau bụng.

GHI NHẬT KÝ ĐƯỜNG HUYẾT
Ghi lại: ngày giờ, chỉ số, bữa ăn đã ăn, hoạt động, cảm giác.
Chia sẻ với bác sĩ mỗi lần tái khám để điều chỉnh thuốc.

XÉT NGHIỆM HbA1c
Đo trung bình đường huyết 2-3 tháng qua.
Làm 3-6 tháng/lần tại cơ sở y tế.
Mục tiêu < 7%: giảm nguy cơ biến chứng lên đến 37%.
""",
            },
            "dieu_tri__treatment_sample.txt": {
                "metadata": {
                    "source_name": "treatment_sample",
                    "url": "https://example.com/treatment",
                    "category": "dieu_tri",
                    "language": "vi",
                    "crawled_at": "2024-01-01T00:00:00",
                    "char_count": 0,
                },
                "content": """Điều Trị Tiểu Đường Type 2

NGUYÊN TẮC ĐIỀU TRỊ
Điều trị tiểu đường type 2 là quá trình lâu dài, kết hợp thay đổi lối sống và thuốc. Mục tiêu: kiểm soát đường huyết, ngăn biến chứng, duy trì chất lượng sống.

THUỐC UỐNG PHỔ BIẾN

Metformin (Glucophage):
- Thuốc đầu tay cho hầu hết bệnh nhân tiểu đường type 2
- Giảm sản xuất glucose từ gan, tăng nhạy cảm insulin
- Uống sau ăn để giảm tác dụng phụ (buồn nôn, tiêu chảy)
- Giá rẻ, an toàn, không gây hạ đường huyết khi dùng một mình
- Chống chỉ định: suy thận nặng (GFR < 30)

Nhóm SGLT-2 (Empagliflozin, Dapagliflozin):
- Thải đường qua nước tiểu
- Bảo vệ tim và thận (lợi ích ngoài đường huyết)
- Có thể gây nhiễm trùng đường tiết niệu

Nhóm GLP-1 (Semaglutide - Ozempic):
- Kích thích tiết insulin, ức chế glucagon
- Giảm cân tốt (phụ lợi ích lớn)
- Dạng tiêm tuần 1 lần hoặc uống ngày 1 lần

Sulfonylurea (Glibenclamide, Glimepiride):
- Kích thích tuyến tụy tiết insulin
- Rẻ, hiệu quả nhưng có thể gây hạ đường huyết
- Tăng cân nhẹ

INSULIN
Khi nào cần insulin?
- HbA1c > 10% và đường huyết rất cao
- Thuốc uống tối đa nhưng không kiểm soát được
- Suy thận, suy gan (không dùng được nhiều thuốc uống)
- Mang thai bị tiểu đường

Các loại insulin:
- Insulin nền (Glargine, Detemir): tiêm 1 lần/ngày, kiểm soát đường huyết đói
- Insulin bữa ăn (Regular, Aspart): tiêm trước ăn, kiểm soát đường huyết sau ăn
- Insulin trộn sẵn: tiện lợi, tiêm 2 lần/ngày

LƯU Ý QUAN TRỌNG
KHÔNG tự ý ngừng thuốc dù cảm thấy khoẻ - tiểu đường type 2 là bệnh mãn tính.
KHÔNG tự tăng/giảm liều thuốc mà không hỏi bác sĩ.
Báo ngay cho bác sĩ nếu: hạ đường huyết thường xuyên, đường huyết quá cao, tác dụng phụ lạ.

TÁI KHÁM ĐỊNH KỲ
3 tháng/lần: đường huyết, HbA1c, huyết áp, cân nặng
6 tháng/lần: mỡ máu, chức năng thận (creatinine, GFR)
12 tháng/lần: khám mắt, khám bàn chân
""",
            },
            "the_duc_loi_song__exercise_sample.txt": {
                "metadata": {
                    "source_name": "exercise_sample",
                    "url": "https://example.com/exercise",
                    "category": "the_duc_loi_song",
                    "language": "vi",
                    "crawled_at": "2024-01-01T00:00:00",
                    "char_count": 0,
                },
                "content": """Tập Thể Dục Cho Người Tiểu Đường Type 2

LỢI ÍCH CỦA VẬN ĐỘNG
Tập thể dục là "thuốc" hiệu quả nhất cho tiểu đường type 2:
- Hạ đường huyết ngay lập tức và duy trì 24-48 giờ sau tập
- Tăng nhạy cảm insulin (cơ thể dùng insulin hiệu quả hơn)
- Giảm cân, giảm mỡ bụng
- Cải thiện sức khoẻ tim mạch
- Giảm stress, cải thiện giấc ngủ

MỤC TIÊU VẬN ĐỘNG (ADA khuyến nghị)
Tối thiểu 150 phút/tuần hoạt động aerobic cường độ vừa
Không ngồi liên tục quá 30 phút (đứng dậy, đi lại nhẹ)
Kết hợp tập sức mạnh 2-3 lần/tuần

CÁC BÀI TẬP PHÙ HỢP
Đi bộ nhanh: dễ nhất, an toàn nhất, 30 phút/ngày
Bơi lội: tốt cho người đau khớp, đường huyết cao
Đạp xe: tốt cho tim mạch và khớp gối
Yoga/Thái cực quyền: giảm stress, tăng linh hoạt
Tập gym nhẹ: tăng cơ, tăng trao đổi chất

TRƯỚC KHI TẬP
Đo đường huyết:
- < 100 mg/dL: ăn nhẹ 15-20g carb trước khi tập
- 100–250 mg/dL: an toàn để tập bình thường
- > 250 mg/dL: hoãn tập, kiểm tra ketone, uống nước
Mang theo kẹo/đường phòng hạ đường huyết khi tập.

TRONG VÀ SAU KHI TẬP
Uống nước đầy đủ (mất nước làm đường huyết tăng).
Nếu cảm thấy run, chóng mặt: ngừng tập, đo đường huyết.
Đo đường huyết sau tập để xem phản ứng cơ thể.

LƯU Ý ĐẶC BIỆT
Người đang tiêm insulin hoặc dùng Sulfonylurea: nguy cơ hạ đường huyết cao hơn khi tập.
Nếu có biến chứng bàn chân: chọn giày phù hợp, kiểm tra chân sau tập.
Nếu có bệnh tim: hỏi bác sĩ trước khi tập cường độ cao.

XÂY DỰNG THÓI QUEN
Bắt đầu từ 10 phút/ngày rồi tăng dần.
Tập vào giờ cố định trong ngày.
Tìm bạn tập để duy trì động lực.
Ghi lại buổi tập và đường huyết tương ứng.
""",
            },
        }

        created = 0
        for filename, data in sample_docs.items():
            filepath = self.raw_dir / filename
            if not filepath.exists():
                meta = data["metadata"]
                meta["char_count"] = len(data["content"])
                content_block = (
                    "===METADATA===\n"
                    + json.dumps(meta, ensure_ascii=False, indent=2)
                    + "\n===CONTENT===\n"
                    + data["content"]
                )
                filepath.write_text(content_block, encoding="utf-8")
                created += 1
                logger.info(f"  ✅ Tạo mẫu: {filename}")

        logger.success(f"✅ Tạo xong {created} tài liệu mẫu")


# ── CHẠY TRỰC TIẾP ──────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("📄 PDF BUILDER — Chuẩn Hóa Tài Liệu Y Khoa")
    logger.info("=" * 60)

    builder = PDFBuilder()

    # Tạo tài liệu mẫu nếu chưa có gì
    txt_files = list(RAW_DIR.glob("*.txt"))
    real_files = [f for f in txt_files if f.name != "crawl_metadata.json"]

    if not real_files:
        logger.info("\n📝 Chưa có tài liệu nào — tạo dữ liệu mẫu để demo...")
        builder.build_sample_knowledge()

    # Build PDF
    results = builder.build_all()
    ok = sum(1 for r in results if r["status"] == "success")

    if ok > 0:
        logger.success(f"\n✅ Tạo xong {ok} file PDF tại data/pdfs/")
        logger.info("▶  Bước tiếp theo: python src/rag/indexer.py")
