import fitz
from pathlib import Path

files = list(Path('/app/data/pdfs').rglob('*.pdf'))

# Test tất cả file có liên quan
keywords = ['thai_ky', 'thai', 'pregnancy', 'boyte', 'vinmec']
for f in sorted(files):
    name_lower = f.name.lower()
    if any(k in name_lower for k in keywords):
        doc = fitz.open(str(f))
        text = doc[0].get_text('text')[:300] if len(doc) > 0 else ''
        doc.close()
        status = 'EMPTY' if not text.strip() else 'HAS_TEXT'
        print(f'[{status}] {f.name[:60]}')
        if text.strip():
            print(f'  >>> {repr(text[:150])}')
        print()
