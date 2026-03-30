# Docker Guide

## 1. Mục tiêu

Repo này đã được bổ sung đầy đủ file Docker để chạy các stack bằng Docker Compose:

- Frontend Vite/React
- API Gateway
- Users Service
- Discovery Server (Eureka)
- PostgreSQL
- Redis

## 2. Các file chính

- `docker-compose.yml`: điều phối toàn bộ service
- `docker/postgres/init/01-init-users-db.sql`: tạo schema cơ bản cho `users-service`
- `Backend/*/Dockerfile`: build từng service Spring Boot
- `Frontend/healtcare/Dockerfile`: build frontend và serve bằng Nginx
- `Frontend/healtcare/nginx.conf`: cấu hình SPA fallback cho React Router
- `.env.example`: mẫu biến môi trường để tùy chỉnh port, DB, JWT, mail

## 3. Chạy local bằng Docker

Nếu cần OTP qua email, hãy khai báo thêm `MAIL_USERNAME` và `MAIL_PASSWORD`.
Docker Compose cũng có thể lấy biến môi trường đã tồn tại trong máy.
Tất cả lệnh bên dưới được chạy trong thư mục gốc của project:

```powershell
cd d:\Intellij\DoanTN_Healtcare
```

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Nếu không muốn tạo `.env`, bạn vẫn có thể chạy trực tiếp vì `docker-compose.yml` đã có giá trị mặc định:

```powershell
docker compose up --build -d
```

## 4. Địa chỉ truy cập mặc định

- Frontend: `http://localhost:5173`
- API Gateway: `http://localhost:8080`
- Users Service: `http://localhost:8081`
- Discovery Server: `http://localhost:8761`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## 5. Lưu ý quan trọng

- Frontend build với `VITE_API_URL`, mặc định là `http://localhost:8080/api`.
- `users-service` đang để `hibernate.ddl-auto: none`, vì vậy Compose đã được thêm script SQL khởi tạo schema tối thiểu.
- Script SQL hiện tạo bảng `roles`, `users`, `users_roles` và speed 2 role `ADMIN`, `USER`.
- Nếu sau bày repo có thêm entity mới, hãy cập nhật file `docker/postgres/init/01-init-users-db.sql` hoặc chuyển sang Flyway/Liquibase.
- Nếu bạn đổi secret JWT hoặc `GATEWAY_INTERNAL_SECRET`, hãy đổi đồng bộ trong `.env`.
- Nếu bạn sửa script trong `docker/postgres/init`, hay chạy `docker compose down -v` để tạo lại volume và nạp lại schema từ đầu.

## 6. Lệnh hữu ích

Xem log:

```powershell
docker compose logs -f
```

Dừng stack:

```powershell
docker compose down
```

Xóa cả volume DB/Redis để khởi tạo lại từ đầu:

```powershell
docker compose down -v
```

Xem trạng thái container:

```powershell
docker compose ps
```

Xem cấu hình Docker Compose sau khi đã resolve biến môi trường:

```powershell
docker compose config
```

## 7. Chạy lại theo từng trường hợp

Khởi động lại toàn bộ project sau khi sửa nhiều phần:

```powershell
docker compose up --build -d
```

### Sửa frontend

Khi sửa code trong `Frontend/healtcare/src`:

```powershell
docker compose up --build -d --force-recreate frontend
```

Xem log frontend:

```powershell
docker compose logs -f frontend
```

Lưu ý:
- Nếu sửa `Frontend/healtcare/.env` hoặc đổi `VITE_API_URL`, cần build lại `frontend`.

### Sửa users-service

Khi sửa code trong `Backend/users-service`:

```powershell
docker compose up --build -d --force-recreate users-service
```

Xem log users-service:

```powershell
docker compose logs -f users-service
```

### Sửa api-gateway

Khi sửa code trong `Backend/api-gateway`:

```powershell
docker compose up --build -d --force-recreate api-gateway
```

Xem log api-gateway:

```powershell
docker compose logs -f api-gateway
```

### Sửa discovery-server

Khi sửa code trong `Backend/discovery-server`:

```powershell
docker compose up --build -d --force-recreate discovery-server
```

Xem log discovery-server:

```powershell
docker compose logs -f discovery-server
```

### Sửa nhiều service cùng lúc

Ví dụ sửa cả `users-service` và `api-gateway`:

```powershell
docker compose up --build -d --force-recreate users-service api-gateway
```

Ví dụ sửa cả `frontend` và `api-gateway`:

```powershell
docker compose up --build -d --force-recreate frontend api-gateway
```

### Sửa biến môi trường

Nếu sửa file `.env` ở root:
- Backend service cần `force-recreate` để nhận biến mới.
- Frontend cần `--build` nếu biến đó ảnh hưởng đến `VITE_API_URL`.

Chạy lại tất cả service đang dùng biến môi trường:

```powershell
docker compose up -d --build --force-recreate
```

### Sửa database

Nếu sửa file seed/schema trong `docker/postgres/init/01-init-users-db.sql`:

```powershell
docker compose down -v
docker compose up --build -d
```

Luu y:
- `down -v` sẽ xóa volume PostgreSQL và Redis.
- Script trong `docker/postgres/init` chỉ được chạy khi volume database được tạo mới.
- Nếu không muốn xóa dữ liệu, bạn cần chạy SQL thủ công vào database hiện tại thay vì `down -v`.

Nếu chỉ sửa code backend có liên quan DB nhưng không sửa schema/init script:

```powershell
docker compose up --build -d --force-recreate users-service
```
