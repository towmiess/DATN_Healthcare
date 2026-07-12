"""
reset.py — Chạy bên trong Docker container để reset crawler state
Dùng khi không xóa được .crawler_state.json bằng rm (device busy)

Cách dùng:
  docker exec rag-api python scripts/reset.py
  docker exec rag-api python scripts/reset.py --dry-run   # xem trước, không xóa
"""
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

STATE_FILE = ROOT / ".crawler_state.json"
PDF_DIR    = ROOT / "data" / "pdfs"

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="Chỉ xem, không xóa")
args = parser.parse_args()

DRY = args.dry_run
tag = "[DRY RUN] " if DRY else ""

print("=" * 55)
print(f"  {tag}RESET CRAWLER STATE & FILES")
print("=" * 55)

# ── 1. Reset state file (ghi đè bằng {} thay vì xóa) ────────
print(f"\n📄 State file: {STATE_FILE}")
if STATE_FILE.exists():
    # Đọc để xem có bao nhiêu entry
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        print(f"   Có {len(state)} URL đã crawl trong state")
    except Exception:
        state = {}
        print("   State file bị lỗi JSON")

    if not DRY:
        # Ghi đè bằng dict rỗng thay vì rm (tránh 'device busy')
        STATE_FILE.write_text("{}", encoding="utf-8")
        print("   ✅ Đã reset state → {}")
    else:
        print(f"   {tag}Sẽ reset về {{}}")
else:
    print("   ℹ  Không tồn tại — bỏ qua")

# ── 2. Xóa file .txt cũ trong data/pdfs/ ────────────────────
print(f"\n📁 Xóa .txt cũ trong: {PDF_DIR}")
if not PDF_DIR.exists():
    print("   ℹ  Thư mục chưa tồn tại — bỏ qua")
else:
    txt_files = list(PDF_DIR.rglob("*.txt"))
    print(f"   Tìm thấy {len(txt_files)} file .txt")

    deleted = 0
    failed  = 0
    for f in txt_files:
        if DRY:
            print(f"   {tag}Sẽ xóa: {f.relative_to(ROOT)}")
        else:
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                print(f"   ⚠  Không xóa được {f.name}: {e}")
                failed += 1

    if not DRY:
        print(f"   ✅ Đã xóa {deleted} file")
        if failed:
            print(f"   ⚠  Không xóa được {failed} file")

# ── 3. Tóm tắt ───────────────────────────────────────────────
print("\n" + "=" * 55)
if DRY:
    print("  [DRY RUN] Chạy lại không có --dry-run để thực hiện")
else:
    print("  ✅ RESET XONG — Chạy crawler:")
    print("     python scripts/crawler.py --force")
print("=" * 55)
