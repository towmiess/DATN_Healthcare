# Docker Guide

Repo nay co cau hinh Docker Compose de chay stack gom:

- Frontend Vite/React
- API Gateway
- Users Service
- Discovery Server (Eureka)
- PostgreSQL
- Redis

## Cac file chinh

- `docker-compose.yml`: dieu phoi toan bo service.
- `docker/postgres/init/01-init-users-db.sql`: khoi tao schema/toi thieu data cho `users-service`.
- `Backend/*/Dockerfile`: build cac service Spring Boot bang Maven va Java 21.
- `Frontend/healthcare/Dockerfile`: build frontend va serve bang Nginx.
- `Frontend/healthcare/nginx.conf`: SPA fallback cho React Router.

## Chay bang Docker Compose

Tat ca lenh chay tu thu muc goc project:

```powershell
cd d:\study\DATN_Healthcare
docker compose up --build -d
```

Compose da co gia tri mac dinh cho port, database, Redis va JWT secret. Neu muon tuy chinh, tao file `.env` o thu muc goc project, vi Docker Compose chi tu dong doc `.env` nam cung thu muc voi `docker-compose.yml`.

Vi du `.env`:

```env
POSTGRES_DB=users_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123456
POSTGRES_PORT=5432

REDIS_PORT=6379

DISCOVERY_PORT=8761
USERS_SERVICE_PORT=8081
GATEWAY_PORT=8080
FRONTEND_PORT=5173

CORS_ALLOWED_ORIGINS=http://localhost:5173
VITE_API_URL=http://localhost:8080/api

GATEWAY_INTERNAL_SECRET=change-me
JWT_ACCESS_SECRET=S1TZnHDnQS6ojlPYPI+bjd6CXxYhBP/eYmubZsRSANY=
JWT_REFRESH_SECRET=TaqlmGv1iEDMRiFp/pHuID1+T84IABfuA0xXh4GhiUI=

MAIL_USERNAME=
MAIL_PASSWORD=
```

Neu can OTP qua email, khai bao `MAIL_USERNAME` va `MAIL_PASSWORD` trong file `.env` root.

## Dia chi mac dinh

- Frontend: `http://localhost:5173`
- API Gateway: `http://localhost:8080`
- Users Service: `http://localhost:8081`
- Discovery Server: `http://localhost:8761`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Lenh huu ich

Xem log:

```powershell
docker compose logs -f
```

Dung stack:

```powershell
docker compose down
```

Xoa volume PostgreSQL/Redis va khoi tao lai schema tu dau:

```powershell
docker compose down -v
docker compose up --build -d
```

Xem trang thai container:

```powershell
docker compose ps
```

Kiem tra Compose sau khi resolve bien moi truong:

```powershell
docker compose config
```

## Build lai tung phan

Frontend:

```powershell
docker compose up --build -d --force-recreate frontend
```

Users Service:

```powershell
docker compose up --build -d --force-recreate users-service
```

API Gateway:

```powershell
docker compose up --build -d --force-recreate api-gateway
```

Discovery Server:

```powershell
docker compose up --build -d --force-recreate discovery-server
```

## Luu y

- Frontend Docker build dung `VITE_API_URL`, mac dinh la `http://localhost:8080/api`.
- `users-service` dang de `spring.jpa.hibernate.ddl-auto: none`, nen schema ban dau duoc nap tu `docker/postgres/init/01-init-users-db.sql`.
- Neu sua file trong `docker/postgres/init`, can chay `docker compose down -v` de tao lai volume va nap lai script init.
- File `Frontend/.env` hien khong duoc Docker Compose tu dong doc. Neu can cau hinh cho Docker, dat bien trong `.env` o root project.
