## Google Vision OCR

### 1. Them API key vao Docker Compose

Tao file `.env` o thu muc goc cua repo va them:

```env
GOOGLE_VISION_API_KEY=your_real_google_vision_api_key
```

Neu ban da co file `.env`, chi can bo sung dong tren.

### 2. Khoi dong lai service can thiet

```powershell
docker compose up --build -d --force-recreate health-service frontend
```

### 3. Luong OCR hien tai

- OCR man hinh may do huyet ap/duong huyet van uu tien bo nhan dien cuc bo.
- Khi `GOOGLE_VISION_API_KEY` da duoc cau hinh, frontend se goi Google Vision cho OCR van ban.
- Neu Google Vision khong trich xuat du chi so, he thong se fallback ve OCR cuc bo.

### 4. Endpoint lien quan

- OCR status: `/api/ocr/status/`
- Google Vision OCR: `/api/ocr/google-vision/`

### 5. Kiem tra nhanh

Sau khi dang nhap, vao trang `diagnosis` va upload anh OCR:

- Neu Google Vision da san sang, frontend se uu tien dung ket qua Vision.
- Neu chua san sang, frontend se quay ve local OCR va hien thong bao phu hop.
