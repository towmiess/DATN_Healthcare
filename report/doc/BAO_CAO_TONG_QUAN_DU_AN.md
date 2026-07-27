# Bao cao tong quan du an HealthCare Diabetes

## 1. Muc dich tai lieu

Tai lieu nay tong hop cau truc, chuc nang, cong nghe, kien truc va luong hoat dong cua du an HealthCare Diabetes de phuc vu viet bao cao/do an. Noi dung duoc tong hop tu ma nguon trong hai phan chinh:

- `datn_healthcare`: ung dung frontend React.
- `Backend`: he thong backend microservice dang duoc cau hinh chay qua Docker Compose.

Trong thu muc goc con co `HealthCare-BE`, nhin vao cau truc file thi day la ban sao/ban dong bo khac cua backend. Khi viet bao cao nen uu tien mo ta theo `Backend` vi day la thu muc co `docker-compose.prod.yml`, `.env.prod.example` va cac service dang duoc chinh sua truc tiep.

## 2. Tong quan he thong

HealthCare Diabetes la he thong ho tro theo doi va cham soc suc khoe cho nguoi co nguy co hoac dang quan ly benh tieu duong. He thong ket hop cac module truyen thong nhu quan ly tai khoan, ho so suc khoe, dinh duong, nhac nho, thong bao voi cac module AI nhu:

- Du doan nguy co tieu duong, tim mach, dot quy bang mo hinh ML.
- OCR anh may do duong huyet/huyet ap va tai lieu xet nghiem.
- Phan tich nhat ky suc khoe bang LLM.
- Chatbot RAG tu van kien thuc tieu duong dua tren tai lieu y khoa da lap chi muc.
- AI nhan dien/tham chieu dinh duong tu anh bua an bang Gemini Vision.

Kien truc tong the:

```text
Nguoi dung/Admin
      |
      v
Frontend React Vite (datn_healthcare)
      |
      v
API Gateway - Spring Cloud Gateway, port 8080
      |
      +--> users-service          Quan ly tai khoan, auth, OTP, presence
      +--> nutrition-service      Mon an, nguyen lieu, goi y dinh duong, AI vision bua an
      +--> health-service         Ho so suc khoe, du doan, OCR, bao cao, nhat ky, canh bao
      +--> notification-service   Nhac nho, thong bao realtime, email, inbox event
      +--> rag-service            Chatbot RAG, Qdrant, Redis, Gemini, quan ly tri thuc
      |
      +--> discovery-server       Eureka service registry

Ha tang du lieu:
PostgreSQL, Redis, Qdrant, Cloudinary, Google Vision, Gemini API
```

## 3. Cau truc thu muc

### 3.1. Thu muc goc

```text
HeallthCareDiabetes/
├── Backend/                  Backend chinh, gom cac microservice va Docker Compose
├── datn_healthcare/          Frontend React TypeScript
├── HealthCare-BE/            Ban sao/backend dong bo khac
├── backups/                  Backup du lieu RAG/Redis/Qdrant
├── Backend.zip               File nen backend
├── BAN_GIAO_CAP_NHAT_2026-07-21.md
└── Tài liệu/                 Thu muc tai lieu bao cao
```

### 3.2. Backend

```text
Backend/
├── api-gateway/              Cong vao duy nhat cua backend
├── discovery-server/         Eureka server
├── users-service/            Tai khoan, dang nhap, phan quyen, email OTP
├── nutrition-service/        Dinh duong, mon an, nguyen lieu, anh bua an
├── health-service/           Suc khoe, du doan, OCR, bao cao, nhat ky
├── notification-service/     Nhac nho, thong bao, SSE, email
├── rag-service/              Chatbot RAG
├── docker-compose.prod.yml   Cau hinh chay production/local bang Docker
├── .env.prod.example         Mau bien moi truong production
└── DEPLOYMENT.md             Huong dan trien khai
```

### 3.3. Frontend

```text
datn_healthcare/
├── src/
│   ├── api/                  Axios client, base URL, refresh token
│   ├── assets/               Logo, icon, anh giao dien
│   ├── components/           Component dung chung cho admin/user/chat
│   ├── hooks/                Hook nhu presence
│   ├── layouts/              Layout admin, user, dashboard shell
│   ├── pages/                Man hinh chinh
│   ├── routes/               React Router va ProtectedRoute
│   ├── services/             Lop goi API theo nghiep vu
│   ├── types/                TypeScript type
│   └── utils/                Auth, format cau tra loi chat, history
├── package.json
├── vite.config.ts
└── Dockerfile
```

## 4. Cong nghe su dung

| Nhom | Cong nghe |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, Axios, Sass |
| UI/UX | lucide-react, react-icons, sonner, SweetAlert2 |
| Form/validation frontend | react-hook-form, zod |
| Backend Java | Java 21, Spring Boot 3.5.11, Spring Cloud 2025.0.1 |
| Gateway/Service discovery | Spring Cloud Gateway, Netflix Eureka |
| Backend Python | Django 5.1.4, Django REST Framework, FastAPI, Uvicorn/Gunicorn |
| Database | PostgreSQL 15 |
| Cache/session/queue | Redis 7 |
| Vector database | Qdrant v1.9.2 |
| RAG/Embedding | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, Qdrant |
| LLM | Gemini API, key pool, fallback model |
| OCR | Google Vision API, PyMuPDF, OpenCV, Pillow, local seven-segment OCR |
| ML | joblib, numpy, scikit-learn artifact `.pkl` |
| File/image | Cloudinary, media volume |
| Deploy | Dockerfile tung service, docker-compose.prod.yml, Nginx frontend |
| Testing | JUnit/Spring Boot Test, pytest, Django tests |

## 5. Cac service backend

### 5.1. API Gateway

Thu muc: `Backend/api-gateway`

Vai tro:

- La cong API duy nhat cho frontend, mac dinh chay o port `8080`.
- Dinh tuyen request toi cac microservice noi bo.
- Xu ly JWT access token, CORS, rate limit va bao ve route.
- Gan ngu canh nguoi dung da xac thuc vao header noi bo de cac service Python/Java biet `userId`, `roles`.
- Ky header ngu canh bang `GATEWAY_INTERNAL_SECRET` de ngan client goi truc tiep cac service noi bo.

Cac route chinh:

| Prefix | Service dich |
|---|---|
| `/api/users/**`, `/api/auth/**` | users-service |
| `/api/nutrition/**`, `/api/vision/**`, `/api/meal-history` | nutrition-service |
| `/api/health/**`, `/api/diagnosis/**`, `/api/reports/**`, `/api/ocr/**`, `/api/clinical/**`, `/api/alerts/**`, `/api/journal/**` | health-service |
| `/api/reminders/**`, `/api/notifications/**` | notification-service |
| `/api/rag/**` | rag-service, gateway strip prefix `/api/rag` |

### 5.2. Discovery Server

Thu muc: `Backend/discovery-server`

Vai tro:

- Chay Eureka Server.
- Cho phep cac service Java dang ky ten service.
- Gateway co the route theo `lb://users-service`, `lb://nutrition-service`, `lb://notification-service`.

Cong nghe:

- Spring Boot.
- Spring Cloud Netflix Eureka Server.
- Actuator health check.

### 5.3. Users Service

Thu muc: `Backend/users-service`

Vai tro:

- Quan ly tai khoan nguoi dung/admin.
- Dang ky, dang nhap, dang xuat.
- Cap access token va refresh token.
- Doi mat khau, quen mat khau qua email/OTP.
- Quan ly role, trang thai nguoi dung, danh sach nguoi dung cho admin.
- Theo doi presence cua nguoi dung: bat dau phien, heartbeat, roi phien.

API chinh:

| Endpoint | Chuc nang |
|---|---|
| `POST /api/auth/signup` | Dang ky |
| `POST /api/auth/signin` | Dang nhap |
| `POST /api/auth/logout` | Dang xuat |
| `POST /api/auth/change-pass` | Doi mat khau |
| `POST /api/auth/check-mail` | Kiem tra email/tao OTP |
| `POST /api/auth/check-otp` | Xac thuc OTP |
| `POST /api/auth/reset-password` | Dat lai mat khau |
| `POST /api/auth/refresh-token` | Lam moi access token |
| `GET /api/users/page` | Danh sach user phan trang |
| `GET /api/users/summary` | Thong ke user |
| `PUT /api/users/{id}` | Cap nhat user/role/status |
| `DELETE /api/users/{id}` | Xoa mem user |

Du lieu chinh:

- `users`: ho ten, email, so dien thoai, password hash, avatar, status, deleted.
- `roles`: role nhu `USER`, `ADMIN`.
- Quan he user-role de phan quyen.

### 5.4. Nutrition Service

Thu muc: `Backend/nutrition-service`

Vai tro:

- Quan ly nguyen lieu.
- Quan ly mau mon an/dinh duong.
- Goi y mon an theo doi tuong nguoi dung.
- Lap ke hoach bua an hang ngay.
- Luu lich su bua an.
- Xu ly anh bua an bang AI Vision theo co che job bat dong bo.
- Ho tro admin quan ly kho mon an, kho nguyen lieu va job phan tich anh.

API chinh:

| Endpoint | Chuc nang |
|---|---|
| `GET/POST /api/nutrition/ingredients` | Tim kiem/them nguyen lieu |
| `POST /api/nutrition/ingredients/batch` | Them nhieu nguyen lieu |
| `PUT/DELETE /api/nutrition/ingredients/{id}` | Sua/xoa nguyen lieu |
| `GET/POST /api/nutrition/meal-templates` | Tim kiem/them mon an |
| `GET /api/nutrition/meal-templates/recommendations` | Goi y mon an |
| `GET /api/nutrition/meal-templates/categories` | Danh muc mon an |
| `GET /api/nutrition/meal-templates/daily-plan` | Ke hoach bua an ngay |
| `GET /api/meal-history` | Lich su bua an |
| `POST /api/vision/jobs` | Tao job phan tich anh bua an |
| `GET /api/vision/jobs/{jobId}` | Lay trang thai job |
| `GET /api/vision/admin/summary` | Thong ke job AI Vision |
| `GET /api/vision/admin/jobs` | Quan ly danh sach job |
| `POST /api/vision/admin/jobs/{jobId}/retry` | Chay lai job loi |

Du lieu chinh:

- `ingredient`: ten thuc pham, ten chuan hoa, calories, protein, fat, carbs.
- `nutrition_meal_templates`: ten mon, category, cuisine, image, calories, macro/micro nutrient, GI/GL, phu hop type 1/type 2/thai ky/bien chung.
- `meal_history`: bua an cua user, anh, trang thai phan tich, tong calories/protein/fat/carbs.
- `nutrition_user_types`: danh muc kieu nguoi dung/nhom benh phuc vu goi y.

Luong AI Vision bua an:

1. User upload anh mon an tu frontend.
2. Frontend co the upload anh len Cloudinary.
3. Frontend tao job `/api/vision/jobs`.
4. `nutrition-service` luu job voi trang thai `PENDING/PROCESSING/COMPLETED/FAILED`.
5. `nutrition-worker` doc job tu Redis/queue noi bo.
6. Worker goi Gemini Vision de nhan dien mon an va uoc tinh thanh phan.
7. Ket qua duoc luu vao `meal_history`, user/admin co the xem lai.

### 5.5. Health Service

Thu muc: `Backend/health-service`

Vai tro:

- Quan ly ho so suc khoe ca nhan.
- Luu tien su benh, muc tieu suc khoe, chi so duong huyet.
- Xu ly OCR anh may do va tai lieu xet nghiem.
- Du doan nguy co bang model API.
- Luu snapshot chan doan, danh gia suc khoe, risk prediction.
- Tao dashboard bao cao tuan/thang, export PDF/CSV.
- Phan tich nhat ky suc khoe bang RAG service.
- Sinh canh bao suc khoe va day event sang notification-service.

API chinh:

| Endpoint | Chuc nang |
|---|---|
| `GET /api/health` | Health check |
| `GET/PUT/PATCH /api/health/profile/` | Ho so suc khoe ca nhan |
| `GET /api/health/overview/` | Tong quan suc khoe |
| `GET/POST /api/health/glucose/` | Danh sach/them lan do duong huyet |
| `GET/POST /api/health/goals/` | Muc tieu suc khoe |
| `PATCH/DELETE /api/health/goals/{id}/` | Sua/xoa muc tieu |
| `POST /api/diagnosis/predict/` | Du doan nguy co va luu ket qua |
| `GET /api/diagnosis/profile/` | Snapshot chan doan gan nhat |
| `GET /api/reports/dashboard/` | Dashboard bao cao |
| `POST /api/reports/ai-insights/` | AI insight cho bao cao |
| `POST /api/reports/export/` | Xuat bao cao |
| `GET/POST /api/reports/draft/` | Ban nhap bao cao |
| `GET/POST/DELETE /api/clinical/baselines/` | Ho so/xet nghiem nen |
| `GET /api/clinical/baselines/active/` | Baseline dang dung |
| `POST /api/clinical/baselines/extract/` | Trich xuat tu file xet nghiem |
| `GET /api/ocr/status/` | Trang thai OCR |
| `POST /api/ocr/google-vision/` | OCR anh/thiet bi/tai lieu |
| `GET/PATCH /api/alerts/` | Danh sach/danh dau canh bao |
| `POST /api/journal/analyze/` | Phan tich nhat ky |
| `GET /api/journal/history/` | Lich su nhat ky |

Du lieu chinh:

- `HealthProfile`: ngay sinh, gioi tinh, chieu cao, can nang, BMI, BMR, TDEE, muc van dong.
- `MedicalHistory`: loai tieu duong, tang huyet ap, tim mach, dot quy, than, bien chung, di ung, thuoc dang dung.
- `GlucoseMeasurement`: gia tri duong huyet mg/dL va mmol/L, boi canh do, thoi diem do, nguon du lieu.
- `ClinicalDocument`, `LabPanel`, `LabResult`, `ClinicalBaseline`, `ClinicalConclusion`: tai lieu xet nghiem, chi so lab, ket luan lam sang va baseline.
- `HealthAssessment`, `RiskPrediction`, `AiInsight`: ket qua danh gia, du doan va giai thich AI.
- `JournalEntry`, `JournalAnalysis`: nhat ky va ket qua phan tich.
- `PeriodicReport`, `ReportExport`, `ReportDraft`: bao cao suc khoe.
- `HealthAlert`, `HealthOutboxEvent`: canh bao va event can gui sang notification-service.

### 5.6. Health Model API

Thu muc: `Backend/health-service/model_api`

Day la FastAPI rieng chay noi bo de phuc vu `health-service`.

Vai tro:

- Load cac model `.pkl`: `diabetes_model.pkl`, `cardio_model.pkl`, `stroke_model.pkl`.
- Nhan feature dau vao va tra ve du doan cho 3 muc tieu: diabetes, cardiovascular, stroke.
- Kiem tra artifact model, so luong feature va fingerprint SHA-256.
- Cung cap OCR local cho man hinh may do bang logic seven-segment/OpenCV.

Endpoint chinh:

| Endpoint | Chuc nang |
|---|---|
| `GET /health` | Kiem tra model artifacts |
| `POST /predict/all` | Du doan 3 nguy co |
| `POST /ocr/google-vision` | Nhan dien chi so thiet bi tu anh/base64 |

Dac diem model:

- Feature contract gom 34 cot, vi du: sex, age, BMI, glucose, insulin, cholesterol, huyet ap, thai ky.
- Mot so cap don vi duoc dong bo: glucose mg/dL <-> mmol/L, insulin uU/mL <-> pmol/L, cholesterol mg/dL <-> mmol/L.
- Neu thieu truong bat buoc, API tra `INSUFFICIENT_DATA`.
- Ket qua duoc gan nhan la uoc tinh thuc nghiem, khong thay the chan doan y khoa.

### 5.7. Notification Service

Thu muc: `Backend/notification-service`

Vai tro:

- Quan ly lich nhac ca nhan.
- Tao notification trong app.
- Day thong bao realtime qua SSE.
- Gui email cho reminder, health alert, RAG emergency alert, journal analysis.
- Nhan event noi bo tu cac service khac theo co che idempotent inbox.

API public:

| Endpoint | Chuc nang |
|---|---|
| `GET/POST /api/reminders` | Danh sach/them lich nhac |
| `PATCH/DELETE /api/reminders/{id}` | Sua/xoa lich nhac |
| `GET /api/notifications` | Danh sach thong bao |
| `GET /api/notifications/stream` | SSE realtime |
| `GET /api/notifications/summary` | So thong bao chua doc |
| `PATCH/DELETE /api/notifications/{id}` | Doc/xoa thong bao |
| `POST /api/notifications/bulk` | Mark all read/delete all |
| `POST /api/notifications/{id}/action` | Complete/snooze reminder |

API noi bo:

| Endpoint | Chuc nang |
|---|---|
| `POST /api/internal/notifications/events` | Nhan event tu health/rag/service khac |

Du lieu chinh:

- `reminders`: lich nhac, kieu nhac, recurrence, days_of_week, next_run_at.
- `reminder_executions`: moi lan lich nhac duoc chay.
- `notifications`: thong bao trong app, severity, action_url, metadata, read state.
- `inbox_events`: event da nhan de chong trung lap khi retry.

### 5.8. RAG Service

Thu muc: `Backend/rag-service`

Vai tro:

- Chatbot tu van tieu duong dua tren RAG.
- Lap chi muc PDF/TXT vao Qdrant.
- Sinh embedding bang SentenceTransformer multilingual.
- Quan ly lich su chat/session bang Redis.
- Goi Gemini de sinh cau tra loi.
- Dinh tuyen cau hoi: basic, drug, emergency.
- Tra cuu thong tin thuoc qua web/openFDA client neu can.
- Quan ly tri thuc bo sung cua user/admin.
- Phan tich nhat ky suc khoe cho health-service.
- Phat hien cau hoi khan cap va gui event sang notification-service.

Cau truc module:

```text
src/
├── api/server.py              FastAPI endpoints
├── rag/pipeline.py            Orchestrate retrieve -> prompt -> generate
├── rag/indexer.py             Doc PDF, chunk, index Qdrant
├── rag/session.py             Redis session/chat history
├── retrieval/retriever.py     Semantic retrieval, intent, emergency rule
├── retrieval/query_router.py  Phan loai basic/drug/emergency
├── retrieval/openfda_client.py
├── retrieval/web_search_client.py
├── vectordb/vector_store.py   Qdrant operations
├── prompts/templates.py       System prompt va RAG prompt
├── llm/gemini_client.py       Gemini key pool, retry, fallback
├── ingestion/loader.py        Load PDF/TXT/OCR fallback
└── journal_analysis.py        Phan tich nhat ky
```

API chinh:

| Endpoint | Chuc nang |
|---|---|
| `GET /health` | Trang thai RAG |
| `GET /stats` | So chunk/tai lieu trong Qdrant |
| `POST /chat` | Chat mot luot |
| `POST /chat/session` | Chat theo session, co memory |
| `POST /chat/v2` | Hybrid RAG day du |
| `POST /chat/stream` | Streaming SSE |
| `DELETE /chat/session/{session_id}` | Xoa session |
| `GET/PUT /chat/history/{user_key}` | Dong bo lich su chat |
| `POST /journal/analyze` | Phan tich nhat ky |
| `GET /search` | Debug search |
| `GET/POST/DELETE /admin/knowledge` | Quan ly tri thuc |
| `POST /admin/upload` | Upload tai lieu vao RAG |
| `GET/DELETE /admin/documents` | Quan ly tai lieu |
| `POST /admin/rebuild-index` | Lap chi muc lai |
| `DELETE /admin/cache` | Xoa cache LLM |

Luong RAG chatbot:

1. Frontend goi `/api/rag/chat/session`.
2. Gateway xac thuc JWT, ky user context va route sang `rag-service`.
3. RAG middleware chi chap nhan request co chu ky gateway hop le.
4. Service lay lich su session tu Redis.
5. Tim tri thuc user va response rule da luu trong Qdrant.
6. `QueryRouter` phan loai cau hoi:
   - `emergency`: tra huong dan khan cap va gui event thong bao.
   - `drug`: ket hop web/thong tin thuoc + Qdrant.
   - `basic/document`: tim Qdrant noi bo.
7. Retriever tim top-k chunk lien quan trong Qdrant.
8. Prompt builder ghep system prompt, lich su hoi thoai, tri thuc user va context tai lieu.
9. Gemini sinh cau tra loi.
10. Backend lam sach Markdown, kiem tra cau tra loi bi cat, retry neu can.
11. Luu tin nhan vao Redis va tra response + sources ve frontend.

## 6. Frontend

Thu muc: `datn_healthcare`

Vai tro:

- Cung cap giao dien cho nguoi dung va admin.
- Quan ly phien dang nhap, refresh token, chuyen route theo role.
- Hien thi dashboard suc khoe, chan doan, goi y mon an, chat, thong bao.
- Goi API thong qua `src/api/Fetcher.tsx` va cac service theo nghiep vu.

### 6.1. Route frontend

Route public:

| Route | Man hinh |
|---|---|
| `/login` | Dang nhap |
| `/signup` | Dang ky |
| `/check-email` | Kiem tra email quen mat khau |
| `/verify-otp` | Xac thuc OTP |
| `/reset-password` | Dat lai mat khau |

Route admin:

| Route | Man hinh |
|---|---|
| `/admin/operations` | Tong quan van hanh |
| `/admin/vision-jobs` | Quan ly job AI phan tich anh |
| `/admin/ai-knowledge` | Kho tri thuc AI/RAG |
| `/admin/ingredients` | Quan ly nguyen lieu |
| `/admin/meals` | Quan ly mon an |
| `/admin/users` | Quan ly nguoi dung |

Route user:

| Route | Man hinh |
|---|---|
| `/user` | Trang chu user/dashboard |
| `/user/profile` | Ho so suc khoe |
| `/user/recommendations` | Goi y mon an |
| `/user/recommendations/daily` | Ke hoach bua an ngay |
| `/user/history` | Lich su bua an |
| `/user/diagnosis` | Nhap chi so, OCR, du doan |
| `/user/chat` | Chatbot RAG |
| `/user/reports` | Bao cao dinh ky |
| `/user/reminders` | Trung tam nhac nho |
| `/change-password` | Doi mat khau |

### 6.2. Lop goi API

`src/api/Fetcher.tsx` cau hinh Axios:

- `baseURL` lay tu `API_BASE_URL`.
- Tu dong gan `Authorization: Bearer <accessToken>` cho request can auth.
- Neu gap `401`, tu dong goi `/auth/refresh-token`.
- Neu refresh that bai, xoa auth va dieu huong ve login.
- Timeout mac dinh 120 giay, rieng chat co the den 240 giay.

Cac service frontend quan trong:

| File | Vai tro |
|---|---|
| `services/authservices/*` | Dang nhap, dang ky, OTP, reset, logout |
| `services/health.ts` | Ho so suc khoe, overview, glucose, goal |
| `services/prediction.ts` | Du doan, OCR, diagnosis snapshot |
| `services/clinical.ts` | Baseline/xet nghiem |
| `services/reports.ts` | Bao cao va AI insight |
| `services/journal.ts` | Phan tich nhat ky |
| `services/notifications.ts` | Reminder, notification, SSE |
| `services/chatservices/ragChat.ts` | Chatbot RAG, history, sources |
| `services/nutritionservices/*` | Goi y mon, admin meal/ingredient |
| `services/cloudinary/upload.ts` | Upload anh |

## 7. Cac tinh nang chinh

### 7.1. Xac thuc va phan quyen

Chuc nang:

- Dang ky tai khoan.
- Dang nhap bang email/password.
- Access token/refresh token.
- Quen mat khau bang email OTP.
- Doi mat khau.
- Phan quyen `ADMIN` va `USER`.
- Bao ve route frontend bang `ProtectedRoute`.

Luong dang nhap:

```text
User nhap email/password
 -> Frontend POST /api/auth/signin
 -> Gateway route users-service
 -> users-service kiem tra user/password/status
 -> Sinh accessToken + refreshToken
 -> Frontend luu token
 -> Chuyen trang theo role: ADMIN -> /admin, USER -> /user
```

### 7.2. Quan ly ho so suc khoe

Chuc nang:

- Luu thong tin co ban: ngay sinh, gioi tinh, chieu cao, can nang, vong eo, vong hong.
- Tu tinh BMI, BMR, TDEE theo activity factor.
- Luu loi song: hut thuoc, ruou bia, giac ngu.
- Luu tien su benh: tieu duong, tang huyet ap, tim mach, than, bien chung, thai ky.
- Dong bo baseline tu ket qua xet nghiem/chan doan neu co.

Y nghia trong he thong:

- La nguon feature dau vao cho model du doan.
- Ca nhan hoa goi y dinh duong.
- Hien thi overview va tinh do hoan thien ho so.
- Lam ngu canh cho AI insight va bao cao.

### 7.3. Theo doi duong huyet va OCR

Chuc nang:

- Nhap tay chi so duong huyet.
- Chon don vi `mg/dL` hoac `mmol/L`.
- Chon boi canh do: luc doi, truoc bua an, sau bua an, truoc ngu, ngau nhien.
- Upload anh may do de OCR.
- Upload anh/PDF xet nghiem de trich xuat chi so.
- So sanh chi so hien tai voi baseline phu hop.

Luong OCR may do:

```text
Frontend upload anh
 -> health-service nhan image_base64
 -> Goi Google Vision neu da cau hinh
 -> Neu can, goi health-model-api de doc seven-segment/local OCR
 -> Chuan hoa ket qua: glucose/huyet ap/pulse
 -> User review
 -> Luu vao GlucoseMeasurement/DiagnosisSession
```

### 7.4. Du doan nguy co

Chuc nang:

- Du doan nguy co tieu duong.
- Du doan nguy co tim mach.
- Du doan nguy co dot quy.
- Luu assessment, risk prediction, model metadata.
- Hien thi missing fields neu du lieu chua du.
- Ghi ro canh bao: day la uoc tinh ho tro sang loc, khong phai chan doan y khoa.

Luong du doan:

```text
User nhap chi so hoac OCR
 -> Frontend POST /api/diagnosis/predict/
 -> health-service chuan hoa don vi va boi canh
 -> health-service goi health-model-api /predict/all
 -> model_api tra probability cho diabetes/cardio/stroke
 -> health-service luu HealthAssessment + RiskPrediction
 -> Tao monitoring comparison voi baseline neu co
 -> Frontend hien thi ket qua va goi y
```

### 7.5. Dinh duong va goi y mon an

Chuc nang user:

- Xem goi y mon an.
- Xem ke hoach bua an hang ngay.
- Luu/xem lich su bua an.
- Upload anh bua an de AI phan tich.

Chuc nang admin:

- Them/sua/xoa nguyen lieu.
- Them/sua/xoa mon an.
- Quan ly anh mon an.
- Theo doi job AI Vision.

Tieu chi goi y:

- Loai tieu duong hoac bien chung cua user.
- Thong tin phu hop trong `nutrition_meal_templates`: type 1, type 2, thai ky, than kinh, tim mach, dot quy.
- Chi so calories, carb, protein, fat, GI, GL.

### 7.6. Chatbot RAG tu van tieu duong

Chuc nang:

- Chat theo session.
- Hien thi nguon tai lieu tham khao.
- Luu lich su chat theo user.
- Cho phep day tri thuc/luat tra loi bang cu phap ghi nho.
- Admin quan ly kho tri thuc.
- Tra loi bang Markdown, co ho tro bang.
- Phat hien tinh huong khan cap va sinh canh bao.

Diem manh:

- Khong chi goi LLM truc tiep; he thong tim tai lieu noi bo trong Qdrant truoc.
- Co cache cau tra loi de giam do tre.
- Co retry khi Gemini cat cau tra loi hoac cat bang Markdown.
- Co route rieng cho cau hoi ve thuoc.
- Co response rule/user knowledge de ca nhan hoa.

### 7.7. Nhat ky suc khoe va AI analysis

Chuc nang:

- User viet nhat ky ve trieu chung/cam giac/su kien suc khoe.
- health-service gui text sang rag-service `/journal/analyze`.
- RAG/LLM trich xuat:
  - tom tat,
  - trieu chung,
  - muc do,
  - xu huong,
  - tan suat,
  - muc can luu y,
  - goi y theo doi.
- Ket qua luu vao `JournalAnalysis`.
- Neu can luu y, health-service tao event gui sang notification-service.

### 7.8. Bao cao suc khoe va AI Insight

Chuc nang:

- Dashboard bao cao theo tuan/thang.
- Tong hop duong huyet, BMI, can nang, muc tieu, canh bao.
- So sanh voi ky truoc.
- Tao AI Insight giai thich tinh trang.
- Export bao cao PDF/CSV.
- Luu draft bao cao.

Luong bao cao:

```text
Frontend /user/reports
 -> GET /api/reports/dashboard/
 -> health-service tong hop HealthProfile + GlucoseMeasurement + RiskPrediction + PeriodicReport
 -> User co the goi AI Insight
 -> User export PDF/CSV
```

### 7.9. Nhac nho va thong bao realtime

Chuc nang:

- Tao lich nhac do duong huyet, uong thuoc, insulin, bua an, van dong, lich hen.
- Lap lai mot lan/hang ngay/hang tuan.
- Scheduler sinh execution den han.
- Tao notification trong app.
- Gui email neu cau hinh bat.
- Frontend nhan notification realtime qua SSE.
- User co the mark read, delete, complete, snooze.

Luong event thong bao:

```text
Service nguon tao event
 -> POST /api/internal/notifications/events voi X-Internal-Service-Key
 -> notification-service ghi inbox_events de chong trung lap
 -> Tao notifications
 -> Gui email neu can
 -> Day SSE den frontend dang online
```

### 7.10. Canh bao khan cap

Nguon canh bao:

- RAG chatbot phat hien user dang mo ta trieu chung nguy hiem.
- Health alert worker phat hien xu huong/glucose bat thuong.
- Journal analysis phat hien muc can luu y cao.

Vi du RAG emergency:

```text
User: "Toi dang run tay, va mo hoi lanh, chong mat, nghi ha duong huyet"
 -> rag-service QueryRouter nhan dien emergency
 -> Tra huong dan xu ly ngay
 -> Tao event RAG_EMERGENCY_ALERT
 -> notification-service tao notification va email
 -> Frontend hien thong bao
```

## 8. Database va luu tru

### 8.1. PostgreSQL

PostgreSQL la database chinh, duoc chia so huu theo service:

- users-service so huu user/role.
- nutrition-service so huu nguyen lieu, mon an, meal history, vision job.
- health-service so huu ho so suc khoe, chi so, chan doan, bao cao, nhat ky, canh bao.
- notification-service so huu reminders, notifications, inbox events.

Mot so service dung Flyway migration:

- nutrition-service: `V1__meal_history_and_ingredient_indexes.sql`, `V2__alter_meal_template_text_columns.sql`, `V3__async_vision_analysis.sql`, `V4__add_meal_template_images.sql`.
- notification-service: `V1__create_notification_schema.sql`.

### 8.2. Redis

Redis duoc dung cho:

- Session/chat history RAG.
- Cache cau tra loi/du lieu phu tro.
- Rate limit gateway.
- Hang doi/job hoac trang thai worker trong nutrition.
- Presence/OTP/cache trong users-service neu cau hinh.

### 8.3. Qdrant

Qdrant duoc dung trong rag-service:

- Luu vector embedding cua chunk tai lieu y khoa.
- Luu user knowledge va response rule.
- Tim kiem semantic theo cau hoi.
- Collection mac dinh: `healthcare_diabetes`.

### 8.4. File/media

- `Backend/health-service/media` hoac volume `/app/media`: luu file upload/y te.
- `Backend/rag-service/data/pdfs`: tai lieu PDF nguon cho RAG.
- Cloudinary: luu anh bua an/anh giao dien neu frontend upload.
- `backups/rag`: backup Qdrant snapshot, Redis RDB va file RAG.

## 9. Bao mat va kiem soat truy cap

Co che bao mat chinh:

- JWT access token cho request frontend.
- Refresh token de khoi phuc phien.
- ProtectedRoute tren frontend theo role.
- Gateway la cong duy nhat frontend goi vao backend.
- Gateway ky `X-User-Context` bang HMAC de service noi bo tin duoc ngu canh user.
- RAG service co middleware chan request truc tiep neu khong co chu ky gateway.
- Internal service key cho API noi bo notification.
- Rate limit dang nhap va global rate limit tren gateway.
- Khong nen dua gia tri that cua `.env` vao bao cao, vi co JWT secret, Gmail app password, Gemini key, Qdrant key.

## 10. Trien khai

`Backend/docker-compose.prod.yml` gom cac container:

- `postgres`: PostgreSQL 15.
- `redis`: Redis 7.
- `qdrant`: Vector database.
- `discovery-server`: Eureka.
- `users-service`.
- `nutrition-service`.
- `nutrition-worker`.
- `health-model-api`.
- `health-service`.
- `notification-service`.
- `health-alert-worker`.
- `rag-service`.
- `api-gateway`.

Thu tu phu thuoc:

```text
postgres/redis/qdrant
 -> discovery-server
 -> users/nutrition/health/notification/rag
 -> workers
 -> api-gateway
 -> frontend
```

Frontend co:

- `npm run dev`: chay local Vite.
- `npm run build`: build production.
- Dockerfile + nginx config de serve static file.
- `vercel.json` de deploy tren Vercel neu can.

## 11. Kiem thu

Backend Java:

- users-service co test cho role policy va global exception handler.
- notification-service co test cho reminder schedule, notification service, JSON contract.
- Spring Boot test dung JUnit, H2 cho test.

Backend Python:

- health-service co nhieu test ve glucose monitoring, prediction, OCR, baseline, nutrition sync.
- rag-service co test ve chunker, loader, OCR, vector store, intent, prompt hierarchy, learned response format, journal analysis.

Frontend:

- Co ESLint va TypeScript build.
- Chua thay bo test UI rieng trong package hien tai.

Lenh tham khảo:

```bash
# Frontend
npm run build
npm run lint

# Java service
mvn test

# RAG service
python -m pytest tests/ -v
```

## 12. Luong hoat dong tieu bieu

### 12.1. Luong nguoi dung moi

```text
Dang ky -> Dang nhap -> Cap nhat ho so suc khoe
 -> Nhap/OCR chi so duong huyet
 -> Chay du doan nguy co
 -> Xem goi y mon an
 -> Tao nhac nho
 -> Dung chatbot/bao cao theo doi hang ngay
```

### 12.2. Luong admin van hanh

```text
Dang nhap ADMIN
 -> Quan ly users
 -> Quan ly ingredients/meals
 -> Theo doi AI Vision jobs
 -> Cap nhat kho tri thuc RAG
 -> Xem trang thai van hanh
```

### 12.3. Luong chan doan va baseline

```text
User upload xet nghiem/nhap chi so
 -> OCR/trich xuat lab result
 -> User xac nhan ket qua
 -> health-service tao ClinicalBaseline
 -> Dong bo sang PersonalHealthRecord
 -> Dung baseline de so sanh cac lan do sau
```

### 12.4. Luong RAG co tri thuc user

```text
User day bot: "/nho ..."
 -> rag-service phan loai knowledge hay response rule
 -> Luu vao Qdrant
 -> Lan chat sau retriever tim lai tri thuc/rule lien quan
 -> Prompt uu tien rule/knowledge truoc tai lieu chung
 -> Gemini tra loi ca nhan hoa
```

## 13. Diem noi bat cua du an

- Kien truc microservice ro rang, tach frontend, gateway, service nghiep vu va AI service.
- Co ca AI du doan co cau truc va AI ngon ngu tu nhien.
- RAG dung vector database rieng, khong chi goi chatbot tong quat.
- Co co che canh bao khan cap lien thong chatbot/health/journal -> notification -> email/realtime.
- Co OCR cho ca thiet bi do tai nha va tai lieu xet nghiem.
- Co quan ly dinh duong theo ngu canh benh, khong chi la danh sach mon an.
- Co dashboard, bao cao, export va AI insight phuc vu theo doi dai han.
- Co co che gateway signature va internal service key de bao ve service noi bo.

## 14. Goi y bo cuc bao cao

Co the viet bao cao theo bo cuc sau:

1. Gioi thieu de tai va ly do chon de tai.
2. Muc tieu he thong.
3. Pham vi chuc nang.
4. Kien truc tong the.
5. Cong nghe su dung.
6. Phan tich thiet ke he thong:
   - Use case nguoi dung.
   - Use case admin.
   - Kien truc microservice.
   - Co so du lieu.
7. Cac module chinh:
   - Xac thuc/nguoi dung.
   - Ho so suc khoe.
   - Du doan nguy co.
   - OCR.
   - Dinh duong.
   - Chatbot RAG.
   - Nhac nho/thong bao.
   - Bao cao/AI insight.
8. Luong hoat dong nghiep vu.
9. Trien khai va kiem thu.
10. Danh gia, han che va huong phat trien.

## 15. Han che va huong phat trien co the neu trong bao cao

Han che:

- Model ML dang la uoc tinh ho tro sang loc, chua thay the chan doan y khoa.
- Phu thuoc API ngoai nhu Gemini, Google Vision, Cloudinary.
- Neu thieu du lieu ho so/chi so, du doan co the khong kha dung.
- Cac file tai lieu cu co dau hieu loi encoding, nen can chuan hoa tai lieu nguon khi nop bao cao.
- He thong microservice can cau hinh secret va Docker Compose dung moi chay day du.

Huong phat trien:

- Them dashboard bac si/doctor role.
- Them thong bao push mobile.
- Mo rong bo model va danh gia lai tren tap du lieu Viet Nam.
- Them lich su tuong tac voi bac si.
- Cai thien OCR bang model vision chuyen dung.
- Them quan ly consent va audit log y te.
- Chuan hoa schema migration cho tat ca service.

## 16. Bo sung theo ban cap nhat HealthCare-BE ngay 27/07/2026

### 16.1. Pham vi cap nhat

Phan bo sung nay duoc doi chieu voi cac commit moi trong
`HealthCare-BE/Backend`. Cac thay doi la sua logic xu ly va du lieu tra ve,
khong bo sung bang, entity, endpoint hay microservice moi. Vi vay kien truc
tong the, ERD va cac tac nhan Use Case van giu nguyen.

Hai thu muc backend dang ton tai song song:

- `Backend`: ban da duoc dung de lap tai lieu tong quan ban dau.
- `HealthCare-BE/Backend`: ban Git rieng co cac commit sua report,
  notification va health-service moi hon.

Khi trien khai can chon mot thu muc lam nguon chinh. Chay
`docker compose` trong thu muc nao thi cac build context tuong doi se lay ma
nguon trong thu muc do. Sua `HealthCare-BE/Backend` khong tu dong dong bo sang
`Backend`.

### 16.2. Cap nhat luong bao cao va baseline

Ban cap nhat thay doi cach theo doi chi so so voi baseline:

- Duong huyet doi chieu tren giao dien dung khoa
  `fasting_glucose_mmol_l`.
- Cholesterol doi chieu dung khoa `total_cholesterol_mmol_l`.
- Khi tim `BaselineComparison`, backend anh xa hai khoa tren ve ma luu tru cu
  dang `mg_dl`, nham giu tuong thich voi du lieu da co.
- Neu mot ngay co nhieu `HealthAssessment`, bieu do baseline tracking chi giu
  lan do moi nhat trong ngay.

Luong cap nhat:

```text
Health Assessment theo thoi gian
 -> Nhom theo ngay
 -> Chon assessment moi nhat cua tung ngay
 -> Chuan hoa don vi mmol/L
 -> Doi chieu Clinical Baseline
 -> Tim Baseline Comparison da luu
 -> Tinh delta va delta_percent
 -> Tra baseline_tracking cho bao cao
```

Anh huong nghiep vu:

- Bieu do khong bi lap nhieu diem do trong cung mot ngay.
- Gia tri tren bao cao thong nhat voi don vi frontend dang hien thi.
- AI Insight nhan local context on dinh hon vi su dung report dashboard.
- Khong thay doi bang `clinical_baselines` hoac
  `baseline_comparisons`.

### 16.3. Cap nhat ket qua du doan nguy co

Model API bo sung `risk_band` vao tung ket qua du doan:

| Khoang xac suat | Risk band | Y nghia |
|---|---|---|
| Nho hon `0.35` | `SAFE` | Tin hieu nguy co thap |
| Tu `0.35` den duoi `0.65` | `WARNING` | Can tiep tuc theo doi |
| Tu `0.65` tro len | `DANGEROUS` | Tin hieu nguy co cao |

Day la phan loai ho tro hien thi, khong phai chan doan y khoa.

Quy tac uu tien ket qua:

1. Neu ho so benh vien da xac nhan tieu duong, he thong giu nguyen ket luan
   chinh thuc.
2. Ket qua model tieu duong thu nghiem khong duoc dung de phu nhan ket luan
   benh vien.
3. Neu chua co chan doan chinh thuc va model co ket qua hop le, snapshot chan
   doan co the hien thi tin hieu thu nghiem kem `risk_band`.
4. Cac canh bao phai neu ro model chi la uoc tinh, dac biet voi nguoi mang
   thai va nguoi ngoai mien du lieu ma model duoc kiem dinh.

Luong ket qua moi:

```text
Nguoi dung gui chi so
 -> Health Service kiem tra pham vi ap dung
 -> Model API tinh positive_probability
 -> Gan SAFE / WARNING / DANGEROUS
 -> Kiem tra ket luan benh vien
 -> Neu da xac nhan: an tin hieu tieu duong thu nghiem
 -> Neu chua xac nhan: cho phep hien thi uoc tinh
 -> Luu Assessment va Risk Prediction
 -> Tra snapshot chan doan
```

### 16.4. Cap nhat AI Insight

Kien truc AI Insight khong thay doi. Health Service van:

1. Tong hop profile, diagnosis, baseline va report dashboard.
2. Tao local context va cac driver.
3. Dung cache/local rules cho che do nhanh.
4. Goi RAG va Gemini khi `force_refresh=true`.
5. Luu ket qua vao `ai_insights`.

Du lieu dau vao da thay doi nhe:

- Baseline tracking da chuan hoa don vi.
- Moi ngay chi con diem do cuoi cung.
- Ket qua du doan co them muc `risk_band`.
- Uu tien ket luan lam sang chinh thuc truoc tin hieu model.

Noi dung Insight co the khac truoc, nhung Use Case, sequence diagram va
activity diagram van giu nguyen.

### 16.5. Cap nhat bao cao PDF

Trong file PDF, nhan "Moc xet nghiem dang su dung" duoc doi thanh "Ho so benh
an dang su dung". Thay doi nay phan anh dung hon y nghia cua
`ClinicalBaseline`, vi baseline co the duoc tao tu tai lieu, ket qua xet
nghiem va ket luan lam sang da xac minh.

Disclaimer cua theo doi duong huyet duoc rut gon:

```text
Canh bao chi mang tinh nhac nho theo doi, khong phai ket luan y khoa.
```

### 16.6. Cap nhat notification

Khi tao notification tu reminder, backend bo sung
`metadata.reminder_type`.

```json
{
  "reminder_id": 12,
  "execution_id": 35,
  "reminder_type": "MEDICATION"
}
```

Frontend co the dung `reminder_type` de chon icon, dieu huong den chuc nang
lien quan va phan loai thong bao. Thay doi nay khong lam thay doi ERD vi
`notifications.metadata` da la cot JSON.

### 16.7. Cap nhat cau hinh RAG

Trong `HealthCare-BE/Backend/docker-compose.prod.yml`:

- RAG Service khong con khai bao
  `env_file: ./rag-service/.env`.
- Bo sung bien `TAVILY_API_KEY` cho kha nang tim kiem web.

Khi trien khai, cac bien RAG phai duoc cung cap boi file `.env` cua Docker
Compose hoac moi truong he thong. Can kiem tra toi thieu:

- Gemini API key va model.
- Qdrant URL, collection va API key.
- Redis URL/session configuration.
- Gateway internal secret.
- Internal service key cho notification.
- Tavily API key neu bat tim kiem web.

Neu cac bien truoc day chi nam trong `rag-service/.env`, RAG co the khoi dong
that bai sau khi bo `env_file`.

### 16.8. Anh huong den tai lieu va so do

| Tai lieu/so do | Trang thai | Noi dung can bo sung |
|---|---|---|
| Kien truc microservice | Giu nguyen | Khong co service moi |
| Use Case tong quat | Giu nguyen | UC du doan co them phan loai risk band |
| ERD tong quat | Giu nguyen | Khong co bang/cot moi bat buoc |
| Sequence chan doan | Giu luong chinh | Them buoc gan risk band va uu tien chan doan chinh thuc |
| Sequence AI Insight | Giu nguyen | Local context nhan du lieu da chuan hoa |
| Activity bao cao | Giu luong chinh | Them buoc chon lan do cuoi moi ngay |
| Notification | Giu nguyen | Metadata co them reminder type |
| Deployment RAG | Can cap nhat | Bo service env file, them Tavily key |

### 16.9. So do Class va Use Case bo sung

So do Class tong quat va Use Case tong quat theo phong cach UML duoc xuat
trong file:

`Tai lieu/So do/SO_DO_CLASS_VA_UC_TONG_QUAT.drawio`

So do Class chia cac lop theo mien:

- Identity: `User`, `Role`.
- Health: `HealthProfile`, `DiagnosisSession`, `HealthAssessment`,
  `RiskPrediction`, `ClinicalBaseline`, `AiInsight`.
- Nutrition: `Ingredient`, `MealTemplate`, `MealHistory`.
- Notification: `Reminder`, `ReminderExecution`, `Notification`.
- RAG: `RagPipeline`, `ChatSession`, `VectorDocument`.

So do bieu dien ca quan he cau truc trong CSDL va quan he phu thuoc nghiep vu
giua cac service.

### 16.10. Luoc do co so du lieu tong quat

Luoc do CSDL theo phong cach bang du lieu, co khoa, kieu du lieu va quan he
chan chim duoc xuat tai:

`Tai lieu/So do/LUOC_DO_CSDL_TONG_QUAT.drawio`

Luoc do gom 35 bang quan trong cua toan project:

- Tai khoan: `users`, `roles`, `users_roles`.
- Ho so suc khoe: `health_profiles`, `medical_histories`,
  `clinical_contexts`, `health_goals`, `glucose_measurements`.
- Chan doan: `diagnosis_sessions`, `health_assessments`,
  `risk_predictions`.
- Lam sang: `clinical_documents`, `lab_panels`, `lab_results`,
  `clinical_observations`, `clinical_baselines`, `clinical_conclusions`,
  `baseline_comparisons`, `pregnancy_health_records`.
- Dinh duong: `ingredient`, `nutrition_meal_templates`,
  `nutrition_user_types`, `meal_template_user_types`, `meal_history`.
- Bao cao va AI: `periodic_reports`, `report_exports`, `ai_insights`.
- Nhat ky va canh bao: `journal_entries`, `journal_analyses`,
  `health_alerts`, `health_outbox_events`.
- Nhac nho va thong bao: `reminders`, `reminder_executions`,
  `notifications`, `inbox_events`.

Quy uoc:

- `PK`: khoa chinh.
- `FK`: khoa ngoai.
- `UK`: rang buoc duy nhat.
- Net lien: quan he khoa ngoai vat ly trong CSDL.
- Net dut: lien ket logic qua `user_id`, `meal_log_id` hoac event giua cac
  microservice.

Qdrant va Redis khong duoc ep thanh bang quan he trong luoc do nay. Qdrant
luu vector/tai lieu RAG, con Redis luu session, chat history, cache va queue;
hai kho nay da duoc mo ta rieng trong tai lieu phan he Chatbot RAG.
