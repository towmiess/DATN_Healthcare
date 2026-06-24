# Tài liệu Backend cho Frontend

Tài liệu này tổng hợp những gì frontend cần biết để xây dựng giao diện dựa trên backend hiện có trong workspace và schema thiết kế trong `RawDB/db.sql`.

Mục tiêu của tài liệu:
- Cho frontend biết API nào **đã có thật** trong code backend hiện tại.
- Cho frontend biết những module nào **mới dừng ở mức schema/database design**.
- Đề xuất cấu trúc request/response để frontend có thể dựng màn hình, form, state, bảng dữ liệu và điều hướng.

## 1. Phạm vi hiện tại

### 1.1 Backend đã có thật trong code
Hiện tại trong workspace, backend đã implement rõ các nhóm API sau:
- `Auth`: đăng ký, đăng nhập, đăng xuất, đổi mật khẩu, quên mật khẩu, refresh token.
- `Users`: lấy danh sách người dùng.

Các controller hiện có:
- `Backend/users-service/src/main/java/com/javaweb/users_service/controller/AuthController.java`
- `Backend/users-service/src/main/java/com/javaweb/users_service/controller/UserController.java`

### 1.2 Backend mới ở mức thiết kế schema
Các module sau đã có schema trong `RawDB/db.sql` nhưng **chưa thấy controller/service/repository API tương ứng trong code hiện tại**:
- Hồ sơ sức khỏe
- Tiền sử bệnh
- Mục tiêu sức khỏe
- Đường huyết
- Quét OCR đường huyết
- Đánh giá sức khỏe
- Dự đoán nguy cơ AI
- AI insights
- Dinh dưỡng / bữa ăn
- Phân tích ảnh món ăn
- Gợi ý bài tập / khuyến nghị
- Nhắc nhở / thông báo
- Báo cáo định kỳ
- Phân cụm cộng đồng
- Chatbot / RAG
- Nhật ký người dùng / phân tích nhật ký

Vì vậy frontend nên phân biệt rõ:
- **Contract đã chạy được ngay**
- **Contract đề xuất để xây giao diện và chuẩn bị tích hợp sau**

## 2. Base URL và chuẩn gọi API

### 2.1 Base URL
Frontend hiện tại dùng:
- `VITE_API_URL`
- sau đó tự động nối thêm `/api` nếu chưa có.

Theo file `Frontend/healthcare/src/api/Fetcher.tsx`:
- nếu `VITE_API_URL=http://localhost:8080` thì frontend sẽ gọi `http://localhost:8080/api`
- nếu `VITE_API_URL=http://localhost:8080/api` thì giữ nguyên

### 2.2 Authorization
Frontend tự gắn access token vào header:

```http
Authorization: Bearer <access_token>
```

Khi gặp `401`, frontend sẽ tự gọi:

```http
POST /auth/refresh-token
```

với body:

```json
{
  "refreshToken": "..."
}
```

### 2.3 Chuẩn response hiện tại
Backend hiện trả về wrapper:

```json
{
  "code": "string | optional",
  "message": "string",
  "data": {}
}
```

Frontend nên chuẩn hóa toàn bộ xử lý theo envelope này.

## 3. API đã có thật trong backend

## 3.1 Đăng ký
**Endpoint**

```http
POST /auth/signup
```

**Mục đích**
- Tạo tài khoản mới cho người dùng.

**Request body**

```json
{
  "fullName": "Nguyen Van A",
  "email": "a@gmail.com",
  "phoneNumber": "0901234567",
  "password": "123456",
  "confirmPassword": "123456"
}
```

**Response**

```json
{
  "code": "SUCCESS",
  "message": "User created successfully",
  "data": null
}
```

**Frontend cần**
- Form đăng ký
- Validate bắt buộc tất cả field
- Kiểm tra confirm password trùng password
- Sau đăng ký thành công có thể điều hướng sang trang đăng nhập

## 3.2 Đăng nhập
**Endpoint**

```http
POST /auth/signin
```

**Request body**

```json
{
  "email": "a@gmail.com",
  "password": "123456"
}
```

**Response data**

```json
{
  "accessToken": "jwt-access-token",
  "refreshToken": "jwt-refresh-token"
}
```

**Frontend cần**
- Lưu `accessToken` và `refreshToken`
- Điều hướng theo role hoặc theo màn hình mặc định
- Xử lý lỗi sai email/mật khẩu

## 3.3 Đăng xuất
**Endpoint**

```http
POST /auth/logout
```

**Yêu cầu**
- Cần access token hợp lệ

**Request body**

```json
{
  "refreshToken": "jwt-refresh-token"
}
```

**Frontend cần**
- Gọi API logout khi người dùng bấm đăng xuất
- Xóa token local sau khi thành công
- Nếu logout lỗi 401 vẫn nên xóa local state để đảm bảo người dùng thoát phiên

## 3.4 Đổi mật khẩu
**Endpoint**

```http
POST /auth/change-pass
```

**Yêu cầu**
- Cần access token hợp lệ

**Request body**

```json
{
  "oldPassword": "old-pass",
  "newPassword": "new-pass",
  "newPasswordConfirm": "new-pass"
}
```

**Frontend cần**
- Form yêu cầu nhập mật khẩu cũ
- Kiểm tra xác nhận mật khẩu mới
- Hiển thị lỗi backend nếu sai mật khẩu cũ

## 3.5 Kiểm tra email để quên mật khẩu
**Endpoint**

```http
POST /auth/check-mail
```

**Request body**

```json
{
  "email": "a@gmail.com"
}
```

**Response data**

```json
{
  "userId": 1
}
```

**Ý nghĩa**
- Backend xác minh email tồn tại và gửi OTP.
- Trả về `userId` để frontend dùng ở bước xác thực OTP.

## 3.6 Xác thực OTP
**Endpoint**

```http
POST /auth/check-otp
```

**Request body**

```json
{
  "userId": 1,
  "otp": "123456"
}
```

**Response data**

```json
{
  "token": "reset-token",
  "userId": 1
}
```

**Ý nghĩa**
- Nếu OTP hợp lệ, backend trả token dùng để reset password.

## 3.7 Reset mật khẩu
**Endpoint**

```http
POST /auth/reset-password
```

**Request body**

```json
{
  "token": "reset-token",
  "userId": 1,
  "newPassword": "new-pass"
}
```

**Frontend cần**
- Chỉ cho phép vào màn hình này nếu đã qua bước OTP
- Lưu `token` tạm thời trong state hoặc local storage ngắn hạn

## 3.8 Refresh access token
**Endpoint**

```http
POST /auth/refresh-token
```

**Request body**

```json
{
  "refreshToken": "jwt-refresh-token"
}
```

**Response data**

```json
{
  "accessToken": "new-access-token"
}
```

**Frontend hiện tại**
- Đã có interceptor tự refresh khi gặp `401`
- Không cần màn hình riêng

## 3.9 Danh sách người dùng
**Endpoint**

```http
GET /users
```

**Query params**
- Hiện controller nhận `Map<String, Object> params`, nghĩa là backend mở cho filter động.
- Frontend có thể dự kiến các param như:
  - `page`
  - `limit`
  - `keyword`
  - `status`
  - `role`

**Response data**

Danh sách phần tử kiểu:

```json
[
  {
    "id": 1,
    "fullName": "Nguyen Van A",
    "email": "a@gmail.com",
    "phoneNumber": "0901234567",
    "avatar": "https://...",
    "status": "ACTIVE"
  }
]
```

**Frontend cần**
- Bảng danh sách user
- Ô tìm kiếm
- Filter trạng thái
- Nút xem chi tiết

## 4. Chuẩn dữ liệu frontend nên dùng

## 4.1 User model

```ts
type User = {
  id: number;
  fullName: string;
  email: string;
  phoneNumber?: string;
  avatar?: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED" | "HIGH_RISK";
  deleted?: boolean;
  createdAt?: string;
  updatedAt?: string;
};
```

## 4.2 Base response model

```ts
type BaseResponse<T> = {
  code?: string;
  message: string;
  data: T;
};
```

## 4.3 Phân loại trạng thái dữ liệu
Frontend nên đánh dấu mỗi module theo 1 trong 3 mức:
- `implemented`: backend đã có API thật
- `designed`: đã có schema nhưng chưa có API
- `mocked`: frontend tự mock để làm UI trước

## 5. API đề xuất cho frontend theo schema hiện tại

Phần dưới đây là **đề xuất contract** dựa trên `RawDB/db.sql`. Đây chưa phải API đã có trong code, nhưng rất phù hợp để frontend dựng giao diện trước.

## 5.1 Hồ sơ sức khỏe

### Lấy hồ sơ sức khỏe hiện tại
```http
GET /health-profiles/me
```

**Response data**

```json
{
  "id": 1,
  "userId": 1,
  "dateOfBirth": "2000-01-01",
  "gender": "MALE",
  "heightCm": 170,
  "weightKg": 65,
  "waistCm": 78,
  "bmi": 22.49,
  "bmr": 1500,
  "tdee": 2100,
  "activityLevel": "MODERATE",
  "smokingStatus": "NO",
  "alcoholStatus": "OCCASIONAL",
  "sleepPattern": "7 hours/day",
  "medicalNotes": "..."
}
```

### Tạo hoặc cập nhật hồ sơ sức khỏe
```http
POST /health-profiles
PUT /health-profiles/{id}
```

**Frontend cần**
- Form hồ sơ sức khỏe
- Các field số cần validate min/max
- Có thể tính BMI phía frontend để preview, nhưng lấy kết quả chuẩn từ backend

## 5.2 Tiền sử bệnh

### Lấy tiền sử bệnh
```http
GET /medical-histories/me
```

### Tạo / cập nhật
```http
POST /medical-histories
PUT /medical-histories/{id}
```

**Các field chính**
- `diabetesType`
- `familyHistoryDiabetes`
- `hypertension`
- `cardiovascularDisease`
- `kidneyDisease`
- `pregnancyHistory`
- `allergies`
- `currentMedications`
- `pastConditions`

## 5.3 Mục tiêu sức khỏe

### Danh sách mục tiêu
```http
GET /health-goals
```

### Tạo mục tiêu
```http
POST /health-goals
```

### Cập nhật / xóa
```http
PUT /health-goals/{id}
DELETE /health-goals/{id}
```

**Frontend cần**
- Danh sách mục tiêu
- Form tạo/chỉnh sửa
- Badge trạng thái

## 5.4 Đường huyết

### Danh sách bản ghi đường huyết
```http
GET /glucose-measurements
```

**Query params đề xuất**
- `from`
- `to`
- `context`
- `page`
- `limit`

### Tạo bản ghi
```http
POST /glucose-measurements
```

### Cập nhật bản ghi
```http
PUT /glucose-measurements/{id}
```

### Xóa bản ghi
```http
DELETE /glucose-measurements/{id}
```

### Dashboard đường huyết
```http
GET /glucose-measurements/dashboard
```

**Response data đề xuất**

```json
{
  "todayAverage": 118.5,
  "weekAverage": 124.2,
  "monthAverage": 121.7,
  "latestValue": 135,
  "latestMeasuredAt": "2026-04-26T20:00:00",
  "trend": "UP",
  "alerts": [
    {
      "type": "TREND_ALERT",
      "message": "Đường huyết buổi sáng tăng 3 ngày liên tiếp"
    }
  ],
  "chart": [
    {
      "measuredAt": "2026-04-20T07:00:00",
      "glucoseValue": 120
    }
  ]
}
```

## 5.5 Quét ảnh OCR đường huyết

### Upload ảnh
```http
POST /glucose-scans/upload
```

**Request**
- `multipart/form-data`

**Response data đề xuất**

```json
{
  "scanUploadId": 10,
  "status": "PROCESSING",
  "fileUrl": "https://..."
}
```

### Lấy kết quả OCR
```http
GET /glucose-scans/{id}
```

**Frontend cần**
- Trạng thái upload
- Preview ảnh
- Nút xác nhận dùng dữ liệu OCR hay sửa tay

## 5.6 Đánh giá sức khỏe và dự đoán nguy cơ

### Tạo đánh giá sức khỏe
```http
POST /health-assessments/run
```

### Lấy lịch sử đánh giá
```http
GET /health-assessments
```

### Lấy dự đoán nguy cơ mới nhất
```http
GET /risk-predictions/latest
```

**Response data đề xuất**

```json
{
  "id": 20,
  "modelName": "XGBoost",
  "predictionType": "DIABETES_COMPLICATION",
  "riskPercent": 72.5,
  "riskBand": "DANGEROUS",
  "forecastFrom": "2026-05-01",
  "forecastTo": "2026-11-01",
  "highRiskFlag": true,
  "createdAt": "2026-04-26T20:15:00"
}
```

**Frontend cần**
- Risk card
- Gauge / progress visualization
- Badge màu theo `riskBand`

## 5.7 AI insights và khuyến nghị

### Lấy insight mới nhất
```http
GET /ai-insights/latest
```

### Lấy danh sách khuyến nghị
```http
GET /recommendations
```

**Query params đề xuất**
- `type`
- `priority`
- `activeOnly`

**Response data gợi ý**

```json
[
  {
    "id": 100,
    "recommendationType": "DIET",
    "priority": "HIGH",
    "content": "Giảm cơm trắng vào bữa tối, tăng rau xanh",
    "food": {
      "id": 3,
      "name": "Gạo lứt"
    },
    "validFrom": "2026-04-26",
    "validTo": "2026-05-26"
  }
]
```

## 5.8 Dinh dưỡng và bữa ăn

### Danh sách thực phẩm
```http
GET /foods
```

**Query params đề xuất**
- `keyword`
- `categoryId`
- `isSystemDefined`

### Thêm thực phẩm cá nhân
```http
POST /foods
```

### Danh sách bữa ăn
```http
GET /meal-logs
```

### Tạo bữa ăn
```http
POST /meal-logs
```

**Request data đề xuất**

```json
{
  "mealType": "LUNCH",
  "eatenAt": "2026-04-26T12:30:00",
  "note": "Ăn ở nhà",
  "items": [
    {
      "foodId": 1,
      "quantity": 1.5
    },
    {
      "foodId": 2,
      "quantity": 1
    }
  ]
}
```

### Chi tiết bữa ăn
```http
GET /meal-logs/{id}
```

**Frontend cần**
- Search food
- Chọn món
- Bảng item của bữa ăn
- Tự hiển thị tổng calories, carbs, sugar, avgGi

## 5.9 Phân tích tương quan bữa ăn - đường huyết

### Lấy phân tích cho một bữa ăn
```http
GET /meal-glucose-analyses/{mealLogId}
```

**Response data đề xuất**

```json
{
  "mealLogId": 5,
  "preMealGlucose": 105,
  "postMealGlucose": 165,
  "glucoseDelta": 60,
  "abnormalSpike": true,
  "conclusion": "Bữa ăn này có thể làm tăng đường huyết mạnh do tổng carb cao"
}
```

## 5.10 Nhắc nhở

### Danh sách nhắc nhở
```http
GET /reminders
```

### Tạo nhắc nhở
```http
POST /reminders
```

### Cập nhật nhắc nhở
```http
PUT /reminders/{id}
```

### Bật/tắt nhắc nhở
```http
PATCH /reminders/{id}/status
```

**Frontend cần**
- Form chọn loại nhắc
- Giờ nhắc
- Quy tắc lặp
- Switch bật/tắt

## 5.11 Thông báo

### Danh sách thông báo
```http
GET /notifications
```

**Query params đề xuất**
- `type`
- `isRead`
- `page`
- `limit`

### Đánh dấu đã đọc
```http
PATCH /notifications/{id}/read
```

### Đánh dấu tất cả đã đọc
```http
PATCH /notifications/read-all
```

**Frontend cần**
- Notification center
- Counter unread
- Filter theo loại

## 5.12 Báo cáo định kỳ

### Danh sách báo cáo
```http
GET /reports
```

### Báo cáo gần nhất
```http
GET /reports/latest
```

### Xuất báo cáo
```http
GET /reports/{id}/download
```

**Frontend cần**
- Tab tuần / tháng
- Summary card
- Nút tải file

## 5.13 Cộng đồng

### Lấy snapshot cộng đồng của user
```http
GET /community/me
```

**Response data đề xuất**

```json
{
  "clusterName": "Nhóm kiểm soát khá",
  "ageGroup": "25-34",
  "riskGroup": "WARNING",
  "percentileRank": 80,
  "communityScore": 78.5,
  "snapshotDate": "2026-04-26"
}
```

## 5.14 Chatbot AI / RAG

### Danh sách session
```http
GET /chat/sessions
```

### Tạo session mới
```http
POST /chat/sessions
```

### Lấy messages của session
```http
GET /chat/sessions/{id}/messages
```

### Gửi tin nhắn
```http
POST /chat/sessions/{id}/messages
```

**Request**

```json
{
  "content": "Tôi nên ăn gì khi đường huyết buổi sáng cao?"
}
```

**Response data đề xuất**

```json
{
  "userMessage": {
    "id": 1,
    "senderType": "USER",
    "content": "Tôi nên ăn gì khi đường huyết buổi sáng cao?"
  },
  "assistantMessage": {
    "id": 2,
    "senderType": "ASSISTANT",
    "content": "Bạn nên giảm tinh bột hấp thu nhanh...",
    "llmModel": "gpt-4",
    "flaggedEmergency": false,
    "citations": [
      {
        "documentTitle": "ADA Guideline 2025",
        "sourceUrl": "https://...",
        "relevanceScore": 0.92
      }
    ]
  }
}
```

**Frontend cần**
- Danh sách hội thoại
- Màn chat
- Message bubble theo `senderType`
- Vùng citations
- Cảnh báo nếu `flaggedEmergency = true`

## 5.15 Nhật ký người dùng

### Danh sách nhật ký
```http
GET /journals
```

### Tạo nhật ký
```http
POST /journals
```

### Phân tích nhật ký
```http
POST /journals/{id}/analyze
```

**Frontend cần**
- Editor nhập ghi chú
- Hiển thị AI summary
- Tags triệu chứng

## 6. Mapping backend theo màn hình frontend

## 6.1 Nhóm màn hình đã có trong frontend hiện tại

### Đăng ký
- API: `POST /auth/signup`
- File frontend: `src/pages/auth/SignUp/SignUp.tsx`

### Đăng nhập
- API: `POST /auth/signin`
- File frontend: `src/pages/auth/Login/Login.tsx`

### Kiểm tra email
- API: `POST /auth/check-mail`
- File frontend: `src/pages/auth/CheckEmail/CheckEmail.tsx`

### Xác thực OTP
- API: `POST /auth/check-otp`
- File frontend: `src/pages/auth/VerifyOtp/VerifyOtp.tsx`

### Reset password
- API: `POST /auth/reset-password`
- File frontend: `src/pages/auth/ResetPassword/ResetPassword.tsx`

### Đổi mật khẩu
- API: `POST /auth/change-pass`
- File frontend: `src/pages/auth/ChangePass/ChangePass.tsx`

### Admin user list
- API nên dùng: `GET /users`
- File frontend hiện có: `src/pages/admin/AdminHome.tsx`

## 6.2 Nhóm màn hình nên xây tiếp theo

Ưu tiên hợp lý để làm frontend:
1. Hồ sơ sức khỏe
2. Dashboard đường huyết
3. Nhập đường huyết
4. Danh sách / chi tiết bữa ăn
5. Khuyến nghị AI
6. Thông báo
7. Báo cáo định kỳ
8. Chatbot

Lý do:
- Bám sát schema hiện tại
- Dữ liệu nghiệp vụ rõ
- Dễ mock trước khi backend hoàn thiện

## 7. Khuyến nghị cho đội frontend

## 7.1 Tách service theo module
Nên tạo các service:
- `authService`
- `userService`
- `healthProfileService`
- `glucoseService`
- `mealService`
- `recommendationService`
- `notificationService`
- `reportService`
- `chatService`

## 7.2 Tách type theo domain
Nên tạo:
- `types/auth.ts`
- `types/user.ts`
- `types/health.ts`
- `types/glucose.ts`
- `types/meal.ts`
- `types/chat.ts`

## 7.3 Có mock layer cho module chưa implement
Với các API chưa có thật, frontend nên có:
- mock JSON
- fake service
- hoặc MSW/mock adapter

Để tránh chờ backend xong mới làm UI.

## 7.4 Chuẩn hóa trạng thái lỗi
Frontend nên xử lý thống nhất:
- `400`: lỗi validate form
- `401`: hết phiên / chưa đăng nhập
- `403`: không đủ quyền
- `404`: không tìm thấy dữ liệu
- `500`: lỗi hệ thống

## 8. Kết luận

Trong workspace hiện tại:
- phần **auth** và **user list** là backend đã có thật;
- phần còn lại chủ yếu đang ở mức **thiết kế schema và ERD**;
- frontend hoàn toàn có thể dựng giao diện ngay nếu bám theo contract đề xuất trong tài liệu này.

Nếu cần bước tiếp theo, nên làm một trong hai việc:
1. chốt bộ API contract chính thức giữa frontend và backend;
2. sinh mock data theo từng module để frontend code song song với backend.
