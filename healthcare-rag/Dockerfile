FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pytesseract pdf2image pillow
# Copy file requirements.txt vào container
COPY requirements.txt .

# Cập nhật pip, cài đặt torch bản CPU trước, sau đó mới cài các thư viện còn lại
RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY data/ ./data/

# Tạo thư mục cần thiết
RUN mkdir -p data/pdfs data/raw

EXPOSE 8000

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
