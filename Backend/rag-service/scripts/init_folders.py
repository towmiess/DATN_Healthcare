"""Tạo cấu trúc thư mục data/pdfs/. Chạy 1 lần khi setup."""
from pathlib import Path

FOLDERS = [
    "data/pdfs/general",
    "data/pdfs/diagnosis",
    "data/pdfs/blood_glucose",
    "data/pdfs/medication",
    "data/pdfs/diet",
    "data/pdfs/lifestyle",
    "data/pdfs/emergency",
    "data/pdfs/complication/cardiovascular",
    "data/pdfs/complication/nephropathy",
    "data/pdfs/complication/retinopathy",
    "data/pdfs/complication/neuropathy",
    "data/pdfs/complication/foot_care",
    "data/pdfs/complication/pregnancy",
    "data/raw",
    "logs",
]

for f in FOLDERS:
    p = Path(f)
    p.mkdir(parents=True, exist_ok=True)
    (p / ".gitkeep").touch()
    print(f"  ✅ {f}/")

print("\n✅ Tạo xong cấu trúc thư mục!")
