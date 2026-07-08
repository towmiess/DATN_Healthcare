import fitz
from pathlib import Path

files = list(Path('/app/data/pdfs').rglob('*.pdf'))
print(f'Total: {len(files)} PDFs')

for f in files:
    if 'thai_ky' in f.name or 'vinmec' in f.name.lower():
        doc = fitz.open(str(f))
        text = doc[0].get_text('text')[:200]
        doc.close()
        print(f'\n--- {f.name} ---')
        print(repr(text))
        break
