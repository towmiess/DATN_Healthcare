# Huong Dan CI/CD Bang GitHub Actions Self-Hosted Runner Tren EC2

Tai lieu nay tong hop toan bo quy trinh CI/CD ma project hien tai dang dung, theo huong:

`GitHub Actions -> self-hosted runner tren EC2 -> docker compose up -d --build tren chinh EC2`

Tai lieu nay viet theo dung setup thuc te cua repo nay, khong theo flow ECR cu.

## 1. Muc tieu cua flow hien tai

Flow hien tai duoc thiet ke de:

- Khong dung `ECR`
- Khong can `SSH` tu GitHub-hosted runner vao EC2
- Khong can OIDC role de deploy
- Build image truc tiep tren EC2
- Deploy tu dong moi khi push len `main` 

Noi dung chinh:

1. Ban push code len GitHub
2. GitHub Actions kich hoat workflow
3. Workflow duoc chay tren self-hosted runner da cai tren EC2
4. Runner copy source vao thu muc deploy tren EC2
5. Runner chay `docker compose up -d --build --remove-orphans`
6. Runner doi `api-gateway` khoi dong on dinh va check health

## 2. Cac file lien quan trong repo

Flow hien tai phu thuoc vao cac file sau:

- [`.github/workflows/deploy-prod.yml`](/d:/Intellij/BE-HealthCare/.github/workflows/deploy-prod.yml)
- [`Backend/docker-compose.prod.yml`](/d:/Intellij/BE-HealthCare/Backend/docker-compose.prod.yml)
- [`Backend/.env.prod.example`](/d:/Intellij/BE-HealthCare/Backend/.env.prod.example)
- [`Backend/users-service/src/main/resources/application.yaml`](/d:/Intellij/BE-HealthCare/Backend/users-service/src/main/resources/application.yaml)
- [`Backend/api-gateway/src/main/resources/application.yaml`](/d:/Intellij/BE-HealthCare/Backend/api-gateway/src/main/resources/application.yaml)

## 3. Cach flow hien tai dang hoat dong

### 3.1 Workflow GitHub Actions

Workflow hien tai:

- trigger khi push vao nhanh `main`
- hoac chay bang tay qua `workflow_dispatch`
- chay tren runner co labels:
  - `self-hosted`
  - `linux`
  - `x64`

Bien environment tren GitHub hien tai chi con:

- `EC2_DEPLOY_PATH`

Workflow thuc hien:

1. Checkout source
2. Setup Java 21
3. Kiem tra `EC2_DEPLOY_PATH`
4. Kiem tra file `.env.prod` da co san tren EC2
5. Xoa thu muc `Backend` cu trong thu muc deploy
6. Copy `Backend` moi vao EC2
7. Chay `docker compose up -d --build --remove-orphans`
8. Chay health check `api-gateway`
9. Retry health check toi da 24 lan, moi lan cach 5 giay

### 3.2 Docker Compose production

Compose production hien tai:

- build `discovery-server`, `users-service`, `api-gateway` truc tiep tren EC2
- su dung `postgres:15`
- su dung `redis:7`
- chi expose `api-gateway` ra host qua port `8080`
- `users-service` va `discovery-server` chi nam trong mang Docker noi bo

Do do:

- goi API tu ben ngoai phai di qua `api-gateway`
- tu host EC2, ban goi duoc `http://localhost:8080`
- ban khong goi truc tiep `http://localhost:8081` neu `users-service` khong expose port

### 3.3 Eureka

Project nay dung `discovery-server` lam Eureka.

Thu tu khoi dong hop ly:

1. `discovery-server`
2. `postgres` va `redis`
3. `users-service`
4. `api-gateway`

Sau khi container len, `users-service` va `api-gateway` con can thoi gian dang ky vao Eureka. Thuc te voi project nay, qua trinh nay co the mat tu `1-2 phut`.

Vi vay workflow da duoc chinh:

- khong check health qua som
- retry health check trong khoang `120 giay`

## 4. Nhung gi can lam mot lan duy nhat

## 4.1 Tren EC2

Can mot EC2 Ubuntu da duoc cai:

- Docker
- Docker Compose plugin
- `curl`
- `tar`
- `unzip`

Kiem tra:

```bash
docker --version
docker compose version
curl --version
```

Tao thu muc deploy:

```bash
sudo mkdir -p /opt/healthcare
sudo chown -R ubuntu:ubuntu /opt/healthcare
```

### 4.1.1 Tao file env production

Tao file:

```bash
nano /opt/healthcare/.env.prod
```

Ban co the copy tu [`Backend/.env.prod.example`](/d:/Intellij/BE-HealthCare/Backend/.env.prod.example).

Toi thieu file nay phai co:

```env
POSTGRES_DB=healthcare
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-db-password
SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/healthcare
SPRING_DATASOURCE_USERNAME=postgres
SPRING_DATASOURCE_PASSWORD=your-db-password

SPRING_REDIS_HOST=redis
SPRING_REDIS_PORT=6379
SPRING_REDIS_TIMEOUT=6s

SPRING_MAIL_HOST=smtp.gmail.com
SPRING_MAIL_PORT=587
SPRING_MAIL_DEBUG=false
MAIL_USERNAME=your-mail@example.com
MAIL_PASSWORD=your-app-password

EUREKA_CLIENT_ENABLED=true
EUREKA_CLIENT_SERVICEURL_DEFAULTZONE=http://discovery-server:8761/eureka
EUREKA_INSTANCE_PREFER_IP_ADDRESS=true

CORS_ALLOWED_ORIGINS=https://your-domain.example
GATEWAY_INTERNAL_SECRET=your-long-random-secret

JWT_ACCESS_SECRET=your-base64-access-secret
JWT_ACCESS_EXPIRATION=1800000
JWT_REFRESH_SECRET=your-base64-refresh-secret
JWT_REFRESH_EXPIRATION=1209600000

SPRING_JPA_SHOW_SQL=false
SPRING_JPA_HIBERNATE_DDL_AUTO=none
```

Sau khi tao xong:

```bash
chmod 600 /opt/healthcare/.env.prod
cat /opt/healthcare/.env.prod
```

Luu y:

- `.env.prod` khong duoc commit len GitHub
- moi khi doi secret hay bien moi truong, ban phai sua file nay tren EC2

### 4.1.2 Cai self-hosted runner tren EC2

Tren GitHub:

1. Vao `Repository -> Settings -> Actions -> Runners`
2. Bam `New self-hosted runner`
3. Chon `Linux`
4. Chon `x64`

Tren EC2:

```bash
mkdir -p ~/actions-runner
cd ~/actions-runner
```

Sau do copy cac lenh GitHub hien ra:

1. Lenh download runner
2. Lenh `./config.sh --url ... --token ...`

Khi `config.sh` hoi:

- `runner group`: nhan `Enter`
- `runner name`: nhan `Enter` hoac dat ten nhu `healthcare-ec2`
- `additional labels`: nhan `Enter`
- `work folder`: nhan `Enter`

Sau do cai runner thanh service:

```bash
cd ~/actions-runner
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
sudo ./svc.sh status
```

Cho user `ubuntu` chay duoc Docker:

```bash
sudo usermod -aG docker ubuntu
```

Sau lenh tren:

1. logout khoi EC2
2. SSH lai vao EC2

Kiem tra:

```bash
docker ps
docker compose version
```

Neu runner online, trong GitHub se thay runner o trang `Settings -> Actions -> Runners`.

## 4.2 Tren GitHub

### 4.2.1 Tao environment production

Vao:

`Repository -> Settings -> Environments -> New environment`

Tao environment co ten:

```text
production
```

### 4.2.2 Them environment variable

Trong environment `production`, tao variable:

```text
EC2_DEPLOY_PATH=/opt/healthcare
```

Flow hien tai khong can nua:

- `AWS_REGION`
- `ECR_REGISTRY`
- `AWS_ROLE_TO_ASSUME`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_PRIVATE_KEY`

Neu repo cua ban van con cac bien nay tu flow cu, co the de do hoac xoa di. Workflow hien tai khong doc chung nua.

## 5. Cac buoc setup lan dau tu dau den cuoi

Thu tu khuyen nghi:

1. Sua code trong repo cho phu hop production
2. Tao `docker-compose.prod.yml`
3. Tao `Backend/.env.prod.example`
4. Tao GitHub Actions workflow
5. Tao GitHub environment `production`
6. Cai self-hosted runner tren EC2
7. Tao `/opt/healthcare/.env.prod` tren EC2
8. Tao thu muc `/opt/healthcare`
9. Push code len `main`
10. Theo doi workflow deploy

## 6. Cach deploy hang ngay

Sau khi setup xong, moi lan co code moi ban chi can:

```bash
git add .
git commit -m "your message"
git push origin main
```

Sau khi push len `main`, GitHub Actions se tu dong:

1. Chay workflow
2. Su dung self-hosted runner tren EC2
3. Copy source vao `/opt/healthcare/Backend`
4. Build lai image
5. Restart container can thiet
6. Check health cua gateway

Noi ngan gon:

`push main -> GitHub Actions -> runner tren EC2 -> docker compose build va deploy`

## 7. Cach kiem tra sau deploy

Tren EC2:

```bash
cd /opt/healthcare/Backend
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml ps
curl http://localhost:8080/actuator/health
```

Neu can xem log:

```bash
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml logs --tail 100 api-gateway
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml logs --tail 100 users-service
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml logs --tail 100 discovery-server
```

Neu can xem theo doi truc tiep:

```bash
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml logs -f api-gateway users-service discovery-server
```

## 8. Base URL va cach test API

Hien tai chi `api-gateway` duoc expose ra ngoai, nen API base URL cua ban la:

- `http://<public-ip-ec2>:8080`
- hoac domain da tro vao EC2, vi du `https://your-domain.example`

Vi du:

- `POST /api/auth/signin`
- `POST /api/auth/signup`
- `POST /api/auth/change-pass`
- `GET /api/users`

Neu test tu host EC2:

```bash
curl http://localhost:8080/actuator/health
```

Neu muon goi thang `users-service` trong mang Docker noi bo:

```bash
docker run --rm --network backend_default curlimages/curl:8.7.1 -i http://users-service:8081/actuator/health
```

## 9. Lu y dac biet voi project nay

### 9.1 `users-service` khong tu tao schema

Trong [`Backend/users-service/src/main/resources/application.yaml`](/d:/Intellij/BE-HealthCare/Backend/users-service/src/main/resources/application.yaml), project dang dung:

```text
SPRING_JPA_HIBERNATE_DDL_AUTO=none
```

Dieu nay co nghia la:

- Postgres moi khoi tao se khong co bang
- ung dung khong tu tao schema
- neu deploy len DB trong, ban phai tu tao bang hoac migration

Neu khong co schema, ban co the gap loi khi signup, login, phan quyen, role, hoac truy van du lieu.

### 9.2 `api-gateway` can thoi gian de on dinh

Do co Eureka, gateway khong nen bi check health ngay sau khi container vua start.

Workflow da duoc chinh de:

- retry check health toi da 24 lan
- moi lan cach 5 giay

Tong thoi gian cho la khoang `120 giay`.

### 9.3 Chi `api-gateway` la cong public

Trong production compose:

- `api-gateway` mo port `8080`
- `users-service` va `discovery-server` khong mo port ra host

Vi vay:

- request tu Postman, frontend, browser phai di qua `api-gateway`
- khong goi truc tiep `http://localhost:8081` tu host neu service khong expose

## 10. Huong dan tao schema thu cong neu DB trong

Neu ban deploy lan dau len Postgres rong, co the tao schema thu cong nhu sau.

Dang nhap vao Postgres container:

```bash
docker exec -it postgres psql -U postgres -d healthcare
```

Tao bang:

```sql
CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone_number VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    change_pass_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    avatar VARCHAR(255),
    deleted BOOLEAN,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS users_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_users_roles_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_users_roles_role
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
```

Seed role:

```sql
INSERT INTO roles (name)
SELECT 'ADMIN'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'ADMIN');

INSERT INTO roles (name)
SELECT 'USER'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'USER');
```

Kiem tra:

```sql
SELECT * FROM roles;
```

## 11. Mot so loi thuong gap va cach xu ly

### 11.1 Workflow khong start duoc

Neu GitHub Actions bao:

```text
The job was not started because your account is locked due to a billing issue.
```

Thi day la loi billing cua GitHub, khong phai loi code.

Ban can:

- vao `GitHub Billing`
- cap nhat the/thanh toan
- dam bao account khong con bi lock

Self-hosted runner van can GitHub Actions duoc phep start job.

### 11.2 Health check fail nhung container da len

Neu workflow fail o buoc `curl`, trong khi container van `Up`, thuong la do:

- `api-gateway` chua kip khoi dong xong
- `users-service` va `api-gateway` chua dang ky xong vao Eureka

Kiem tra tay:

```bash
cd /opt/healthcare/Backend
docker compose --env-file /opt/healthcare/.env.prod -f docker-compose.prod.yml ps
curl http://localhost:8080/actuator/health
```

### 11.3 Endpoint public goi duoc, endpoint can token bi 403

Khi gap truong hop nay, can kiem tra:

- token co phai access token khong
- header co dung dang `Authorization: Bearer <token>` khong
- user co role phu hop khong
- DB da co bang `roles`, `users`, `users_roles` chua
- user da duoc gan role chua
- neu vua them role trong DB, can login lai de lay token moi

### 11.4 Goi `localhost:8081` tren host bi loi

Dieu nay co the binh thuong.

Ly do:

- `users-service` khong expose port ra host trong production compose
- chi `api-gateway` expose `8080`

Neu can test thang `users-service`, dung container curl trong Docker network.

## 12. Rollback

Flow hien tai la source-based, khong phai image-tag-based.

De rollback, ban co the:

1. revert commit xau tren `main`
2. hoac checkout commit tot cu va push len `main`
3. workflow se tu build va deploy lai version do

Vi du:

```bash
git revert <bad-commit>
git push origin main
```

## 13. Co the xoa gi tu flow cu

Vi flow moi khong dung ECR nua, sau khi da on dinh ban co the bo:

- ECR repositories cu
- IAM role phuc vu ECR cu
- bien GitHub cu lien quan AWS/ECR/SSH

Tuy nhien nen chi xoa sau khi ban chac chan flow moi da chay on dinh.

## 14. Checklist ngan gon cho lan deploy moi

Moi lan co code moi:

1. Sua code
2. `git add .`
3. `git commit -m "..."`
4. `git push origin main`
5. Vao GitHub Actions xem workflow pass
6. Neu can, vao EC2 check:
   - `docker compose ps`
   - `curl http://localhost:8080/actuator/health`

## 15. Checklist ngan gon cho lan setup moi tren server moi

Neu mai sau doi sang EC2 moi, chi can lam lai:

1. Cai Docker va Docker Compose
2. Tao `/opt/healthcare`
3. Tao `/opt/healthcare/.env.prod`
4. Cai self-hosted runner
5. Tao environment `production` tren GitHub neu chua co
6. Dat `EC2_DEPLOY_PATH=/opt/healthcare`
7. Push code len `main`

## 16. Ket luan

Flow CI/CD hien tai cua project nay la:

`Ban push code -> GitHub Actions start -> self-hosted runner tren EC2 chay workflow -> Docker Compose build va deploy tren chinh EC2`

Day la flow don gian, phu hop voi project hien tai vi:

- chi co 1 server EC2
- khong can ECR
- khong can SSH deploy
- khong can IAM/OIDC de push image
- de van hanh va de debug

Neu sau nay project mo rong them nhieu server hoac can rollback theo image version, ban moi nen can nhac quay lai huong registry nhu ECR.
