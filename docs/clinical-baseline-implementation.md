# Chức năng hồ sơ xét nghiệm và chỉ số gốc

## 1. Mục tiêu

Chức năng này cho phép người dùng tải ảnh phiếu kết quả xét nghiệm từ bệnh viện, kiểm tra lại dữ liệu OCR và xác nhận hồ sơ đó làm mốc lâm sàng. Các lần chẩn đoán tiếp theo được liên kết với mốc đang hoạt động để dashboard hiển thị chênh lệch và biến thiên theo thời gian.

Baseline không tự động tạo một lần đo mới và không ghi đè dữ liệu người dùng đã nhập. Dữ liệu OCR chỉ được lưu chính thức sau khi người dùng xác nhận.

## 2. Các chỉ số được hỗ trợ

### Nhân trắc và dấu hiệu sinh tồn

- Chiều cao (`HEIGHT_CM`)
- Cân nặng (`WEIGHT_KG`)
- BMI (`BMI`)
- Vòng eo hoặc vòng bụng (`WAIST_CM`)
- Huyết áp tâm thu (`SYSTOLIC_BP`)
- Huyết áp tâm trương (`DIASTOLIC_BP`)
- Mạch (`PULSE`)

### Kết quả xét nghiệm

- Glucose máu đói (`FASTING_GLUCOSE`)
- HbA1c (`HBA1C`)
- Cholesterol toàn phần (`TOTAL_CHOLESTEROL`)
- Insulin máu đói (`FASTING_INSULIN`)

Giới tính và tuổi trên phiếu chỉ được trích xuất để hỗ trợ đối chiếu. Hệ thống không tự động thay đổi thông tin tài khoản từ nội dung OCR.

## 3. Luồng sử dụng

1. Người dùng đăng nhập và mở trang báo cáo/dashboard.
2. Chọn **Thêm hồ sơ**.
3. Tải ảnh JPEG, PNG hoặc WEBP, tối đa 15 MB.
4. Backend gửi ảnh đến Google Vision ở chế độ nhận dạng tài liệu.
5. Parser ánh xạ nội dung OCR thành các chỉ số được hỗ trợ.
6. Giao diện hiển thị cơ sở xét nghiệm, ngày lấy mẫu, ngày trả kết quả và từng chỉ số để người dùng kiểm tra.
7. Người dùng chỉnh lại dữ liệu nếu cần và chọn **Xác nhận và đặt làm mốc**.
8. Backend lưu toàn bộ hồ sơ trong một transaction.
9. Baseline cũ chuyển sang `ARCHIVED`; baseline mới trở thành `ACTIVE`.
10. Trang chẩn đoán hiển thị chỉ số gốc dưới trường tương ứng.
11. Sau mỗi lần dự đoán, hệ thống hiển thị chênh lệch tuyệt đối và phần trăm so với baseline.
12. Dashboard hiển thị đường baseline, các lần đo sau baseline và bảng biến thiên theo từng chỉ số.

## 4. Thay đổi cơ sở dữ liệu

### Bảng `clinical_observations`

Lưu các dữ liệu không phải xét nghiệm máu như chiều cao, cân nặng, BMI, vòng eo, huyết áp và mạch. Mỗi bản ghi có giá trị gốc, giá trị chuẩn hóa, đơn vị, khoảng tham chiếu, nguồn, độ tin cậy OCR và trạng thái xác nhận.

### Bảng `clinical_baselines`

Quản lý mốc đang hoạt động của từng người dùng. Bảng lưu phiên hồ sơ nguồn, nhãn, thời điểm hiệu lực, trạng thái và baseline trước đó. PostgreSQL sử dụng partial unique index để mỗi người dùng chỉ có tối đa một baseline `ACTIVE`.

### Bảng `diagnosis_sessions`

Bổ sung `baseline_id`. Mỗi lần chẩn đoán ghi lại baseline được dùng tại thời điểm đó. Việc thay baseline trong tương lai không làm thay đổi lịch sử đối chiếu cũ.

### Bảng `lab_results`

Bổ sung `canonical_value` và `canonical_unit`. Giá trị và đơn vị trên phiếu vẫn được giữ nguyên, đồng thời hệ thống có giá trị chuẩn hóa để so sánh giữa các phiếu dùng đơn vị khác nhau.

Các thay đổi đều mang tính bổ sung, không xóa bảng hoặc dữ liệu cũ. Lệnh `ensure_health_schema` chạy idempotent khi health-service khởi động để cập nhật Docker volume hiện có.

## 5. Vị trí lưu dữ liệu

- Metadata tài liệu: `clinical_documents`.
- Phiếu xét nghiệm: `lab_panels`.
- Chỉ số xét nghiệm: `lab_results`.
- Nhân trắc và dấu hiệu sinh tồn: `clinical_observations`.
- Mốc đang hoạt động và lịch sử mốc: `clinical_baselines`.
- Liên kết lần chẩn đoán với baseline: `diagnosis_sessions.baseline_id`.
- Ảnh gốc: Docker named volume `clinical_uploads` tại `/app/media`.
- Tất cả bản ghi được phân tách theo `user_id` lấy từ access token/gateway context.

PostgreSQL chỉ lưu đường dẫn, MIME type, SHA-256 và dữ liệu đã trích xuất; binary của ảnh không được lưu trực tiếp trong database.

## 6. API

- `POST /api/clinical/baselines/extract/`: OCR và trả dữ liệu nháp, chưa lưu baseline.
- `POST /api/clinical/baselines/`: xác nhận và lưu baseline mới.
- `GET /api/clinical/baselines/`: lấy lịch sử baseline.
- `GET /api/clinical/baselines/active/`: lấy baseline đang hoạt động.
- `GET /api/diagnosis/profile/`: trả thêm baseline cho giao diện chẩn đoán.
- `GET /api/reports/dashboard/`: trả thêm baseline và chuỗi biến thiên.

Các API yêu cầu xác thực và chỉ truy cập dữ liệu thuộc `user_id` của người dùng hiện tại.

## 7. Công thức đối chiếu

```text
chênh_lệch = giá_trị_hiện_tại - giá_trị_gốc
phần_trăm_thay_đổi = chênh_lệch / giá_trị_gốc × 100
```

Hệ thống chỉ tính khi cùng chỉ số có dữ liệu thật ở cả baseline và lần chẩn đoán. Giá trị mặc định của model không được dùng làm số liệu hiện tại trong biểu đồ đối chiếu.

Dấu tăng hoặc giảm chỉ mô tả hướng biến thiên. Hệ thống không mặc định coi mọi giá trị giảm là tốt hoặc mọi giá trị tăng là xấu.

## 8. Kết quả kiểm thử với `hsba_test.jpeg`

Google Vision và parser đã đọc được:

- Chiều cao: 162 cm
- Cân nặng: 70.5 kg
- BMI: 26.86 kg/m2
- Vòng eo: 88 cm
- Huyết áp: 118/76 mmHg
- Mạch: 72 bpm
- Glucose đói: 105 mg/dL
- HbA1c: 5.7%
- Cholesterol toàn phần: 190 mg/dL
- Insulin đói: 8.2 uU/mL
- Cơ sở: Bệnh viện Đa khoa Minh Tâm
- Ngày lấy mẫu: 08/07/2026
- Ngày trả kết quả: 09/07/2026

Parser có xử lý trường hợp Google Vision trả khoảng tham chiếu trước kết quả ở dòng huyết áp tâm trương, tránh lấy nhầm `60` thay cho `76`.

## 9. Kiểm thử kỹ thuật

- Django system check: đạt.
- Sáu test backend: đạt.
- ESLint frontend: đạt.
- TypeScript và Vite production build: đạt.
- Transaction baseline → chẩn đoán → dashboard: đạt.
- Kiểm thử rollback xác nhận không để lại dữ liệu thử.
- Docker health-service, gateway, frontend, model API và PostgreSQL: hoạt động.

## 10. Lưu ý vận hành

- Không tự động tin hoàn toàn vào OCR; người dùng phải kiểm tra trước khi lưu.
- Hồ sơ đã xác nhận được giữ trong lịch sử, không chỉnh sửa âm thầm.
- Khi triển khai production, nên thay Docker volume bằng object storage riêng và thiết lập chính sách sao lưu, mã hóa, thời hạn lưu và nhật ký truy cập cho dữ liệu y tế nhạy cảm.
- Báo cáo và dự đoán của ứng dụng mang tính hỗ trợ theo dõi, không thay thế kết luận của nhân viên y tế.
