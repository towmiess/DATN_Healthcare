lines = open('/app/src/rag/indexer.py').readlines()
print('Line 427:', repr(lines[426]))
# Fix separators line - replace literal newlines with escaped
for i, l in enumerate(lines):
    if 'separators=' in l and i > 415:
        lines[i] = '            separators=["\\n\\n", "\\n", ". ", " ", ""],\n'
        print('Fixed line', i+1)
        break
open('/app/src/rag/indexer.py','w').writelines(lines)
print('Done')
