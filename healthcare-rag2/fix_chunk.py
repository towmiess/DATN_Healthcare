import re

content = open('/app/src/rag/indexer.py').read()

old = '        chunk_size=CHUNK_SIZE if len(doc.get(\"content\",\"\")) < 50000 else min(CHUNK_SIZE * 2, 1800),'
new = '        chunk_size=CHUNK_SIZE if len(document.get(\"content\",\"\")) < 50000 else min(CHUNK_SIZE * 2, 1800),'

if old in content:
    content = content.replace(old, new, 1)
    open('/app/src/rag/indexer.py', 'w').write(content)
    print('Fixed')
else:
    # Show context around chunk_size line
    for i, line in enumerate(content.split('\n')):
        if 'chunk_size=CHUNK_SIZE' in line:
            print(f'L{i}: {line}')
