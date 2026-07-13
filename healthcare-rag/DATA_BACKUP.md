# RAG Data Backup And Migration

This project keeps chatbot knowledge outside Git:

- Qdrant stores indexed documents and taught knowledge.
- Redis stores chat sessions, cache, and temporary runtime data.

The current Docker Compose file uses named volumes, so rebuilding images does not delete RAG data. Data is at risk only when volumes are deleted or when the project is moved to another machine without migrating the volumes.

## Do Not Run These Unless You Intend To Delete Data

```powershell
docker compose down -v
docker volume prune
docker system prune --volumes
```

## Backup On The Current Machine

Run from the `healthcare-rag` folder:

```powershell
.\scripts\backup-rag-data.ps1 -StopServices
```

The script writes files into `healthcare-rag\backups`, for example:

```text
backups\qdrant_data_20260713-153000.tar.gz
backups\redis_data_20260713-153000.tar.gz
```

Copy both files to the target machine.

## Restore On The Service-Merge Machine

Put both `.tar.gz` files inside the target machine's `healthcare-rag\backups` folder, then run:

```powershell
.\scripts\restore-rag-data.ps1 `
  -QdrantBackup .\backups\qdrant_data_YYYYMMDD-HHMMSS.tar.gz `
  -RedisBackup .\backups\redis_data_YYYYMMDD-HHMMSS.tar.gz `
  -Force
```

The restore script stops `rag-api`, `qdrant`, and `redis`, replaces the target volume contents, then starts the RAG services again.

## If The Target Machine Already Has Important Data

Backup the target machine first:

```powershell
.\scripts\backup-rag-data.ps1 -BackupDir .\backups-target-before-restore -StopServices
```

Only restore after that backup exists.

## Verify After Restore

```powershell
docker compose up -d qdrant redis rag-api
Invoke-RestMethod -Uri http://localhost:8000/health | ConvertTo-Json -Depth 8
```

Check that `rag_ready` is `true` and `total_chunks` is greater than `0`.

Then ask the chatbot a few questions that were taught before migration.

## Notes For Git

Do not commit backup archives. They can contain private medical knowledge, chat history, and are usually large.
