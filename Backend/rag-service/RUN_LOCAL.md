# Run rag-service locally

## 1. Prepare environment

Use Python 3.11. The Dockerfile also uses Python 3.11.

Do not create the virtual environment with Python 3.14 because some pinned
packages, especially `PyMuPDF==1.24.1`, do not provide a ready Windows wheel
for Python 3.14 and pip will try to build it from source.

Check installed Python versions:

```powershell
py -0p
```

```powershell
cd D:\DATN\BE\HealthCare-BE\Backend\rag-service
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
copy .env.example .env
```

Expected Python version:

```text
Python 3.11.x
```

Open `.env` and set:

```env
GEMINI_API_KEY_1=your_real_key
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=healthcare-local-key
REDIS_URL=redis://localhost:6379/0
GATEWAY_INTERNAL_SECRET=change-me-in-production
RAG_ALLOW_DIRECT_ACCESS=false
```

`GATEWAY_INTERNAL_SECRET` must match api-gateway.

## 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

If OCR/PDF parsing is needed locally, install Tesseract OCR and Poppler on Windows.

## 3. Make sure infrastructure is running

Qdrant:

```text
http://localhost:6333/dashboard
```

Redis:

```powershell
docker exec -it <redis-container-name> redis-cli ping
```

Expected:

```text
PONG
```

## 4. Ingest documents before testing chatbot

```powershell
python scripts\ingest.py
```

The chatbot is ready only when Qdrant has chunks in collection `healthcare_diabetes`.

## 5. Run rag-service

```powershell
uvicorn src.api.server:app --host 127.0.0.1 --port 8000
```

## 6. Test through api-gateway

Run api-gateway on port `8080`, then call:

```text
GET http://localhost:8080/api/rag/health
POST http://localhost:8080/api/rag/chat
POST http://localhost:8080/api/rag/chat/session
```

Direct calls to `http://localhost:8000/...` are blocked when `RAG_ALLOW_DIRECT_ACCESS=false`.
