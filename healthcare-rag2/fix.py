lines = open('/app/src/rag/indexer.py').readlines()
patch = [
    '    all_chunks = []\n',
    '    indexed_date = datetime.now(timezone.utc).date().isoformat()\n',
    '\n',
    '    for doc in documents:\n',
    '        splitter = RecursiveCharacterTextSplitter(\n',
    "            chunk_size=CHUNK_SIZE if len(doc.get('content','')) < 50000 else min(CHUNK_SIZE * 2, 1800),\n",
    '            chunk_overlap=CHUNK_OVERLAP,\n',
    '            length_function=len,\n',
    "            separators=['\n\n', '\n', '. ', ' ', ''],\n",
    '        )\n',
    "        chunks = splitter.split_text(doc['content'])\n",
]
new = lines[:418] + patch + lines[431:]
open('/app/src/rag/indexer.py','w').writelines(new)
print('Done')
