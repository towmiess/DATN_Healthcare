"""
Tạo cấu trúc thư mục data/pdfs/ đầy đủ.
Chạy 1 lần khi setup project mới.
"""
from pathlib import Path

folders = [
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
    "data/raw",
]

for f in folders:
    path = Path(f)
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch()

print("✅ Tạo xong cấu trúc thư mục:")
for f in folders:
    print(f"   {f}/")
