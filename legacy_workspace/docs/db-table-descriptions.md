# Mô tả các bảng trong `RawDB/db.sql`

Tài liệu này mô tả mục đích của từng bảng và vai trò chính của các trường trong schema PostgreSQL, được cập nhật theo `docs/healthcare-system.dbml`.

Ghi chú chung:
- `id`: khóa chính định danh duy nhất cho bản ghi.
- Các trường `_id`: khóa ngoại hoặc mã tham chiếu đến thực thể liên quan.
- Các trường thời gian như `created_at`, `updated_at`, `measured_at`, `generated_at`, `started_at`, `ended_at`, `read_at`, `exported_at`: dùng để truy vết lịch sử, thống kê, đồng bộ và báo cáo.
- Các trường `jsonb`: lưu snapshot hoặc payload linh hoạt để audit, phân tích và mở rộng nghiệp vụ.
- Các enum như `meal_type`, `measurement_context`, `risk_band`, `notification_type`, `sender_type`... giúp giới hạn giá trị hợp lệ và giữ dữ liệu nhất quán.

## 1. `users`
**Mục đích:** Lưu tài khoản người dùng, admin và các vai trò mở rộng trong hệ thống.

**Các trường chính:**
- `full_name`, `email`, `phone_number`: thông tin định danh và liên hệ.
- `password`: mật khẩu đã băm theo form hiện tại của bảng `users`.
- `avatar`: URL ảnh đại diện.
- `status`: trạng thái kích hoạt tài khoản, `false` là chưa kích hoạt hoặc không hoạt động, `true` là hoạt động.
- `created_at`, `updated_at`: thời điểm tạo và cập nhật tài khoản.

## 2. `roles`
**Mục đích:** Danh mục vai trò như `USER`, `ADMIN`, `DOCTOR`.

**Các trường chính:**
- `name`: tên vai trò, duy nhất trong hệ thống.

## 3. `user_roles`
**Mục đích:** Bảng trung gian nhiều-nhiều giữa `users` và `roles`.

**Các trường chính:**
- `user_id`: người dùng được gán vai trò.
- `role_id`: vai trò được gán cho người dùng.

## 4. `activity_factors`
**Mục đích:** Danh mục hệ số hoạt động AF để tính TDEE theo công thức `TDEE = BMR x AF`.

**Các trường chính:**
- `code`: mã mức vận động như `SEDENTARY`, `LIGHT`, `MODERATE`, `ACTIVE`, `VERY_ACTIVE`.
- `name`, `description`: tên và mô tả mức vận động để người dùng chọn đúng.
- `factor_value`: hệ số AF.
- `display_order`, `is_active`: thứ tự hiển thị và trạng thái còn sử dụng.

## 5. `health_profiles`
**Mục đích:** Hồ sơ sức khỏe cá nhân, nền tảng cho BMI, BMR, TDEE, dashboard và AI feature engineering.

**Các trường chính:**
- `user_id`: người dùng sở hữu hồ sơ, quan hệ 1-1.
- `date_of_birth`, `gender`: dữ liệu nhân khẩu học phục vụ tính toán.
- `height_cm`, `weight_kg`, `waist_cm`, `bmi`: chỉ số cơ thể.
- `bmr`, `tdee`, `activity_factor_id`, `activity_level`: dữ liệu chuyển hóa và mức vận động.
- `smoking_status`, `alcohol_status`, `sleep_pattern`, `medical_notes`: yếu tố lối sống và ghi chú y tế.

## 6. `medical_histories`
**Mục đích:** Lưu tiền sử bệnh và yếu tố nguy cơ để phục vụ đánh giá, dự đoán và cá nhân hóa khuyến nghị.

**Các trường chính:**
- `user_id`: người dùng sở hữu tiền sử bệnh.
- `diabetes_type`: loại tiểu đường nếu đã xác định.
- `family_history_diabetes`, `hypertension`, `cardiovascular_disease`, `kidney_disease`, `pregnancy_history`: các yếu tố nguy cơ dạng boolean.
- `allergies`, `current_medications`, `past_conditions`: thông tin bệnh sử, dị ứng và thuốc.

## 7. `health_goals`
**Mục đích:** Lưu mục tiêu sức khỏe cá nhân để hệ thống theo dõi và đề xuất kế hoạch. Đây là module tùy chọn theo DBML.

**Các trường chính:**
- `user_id`: người đặt mục tiêu.
- `goal_type`, `level`, `target_value`: loại mục tiêu, mức độ và giá trị cần đạt.
- `start_date`, `target_date`, `status`, `note`: thời gian, trạng thái và ghi chú mục tiêu.

## 8. `glucose_measurements`
**Mục đích:** Bảng core time-series lưu các lần đo đường huyết cho dashboard, cảnh báo xu hướng và AI dự đoán.

**Các trường chính:**
- `user_id`: người dùng sở hữu chỉ số.
- `meal_log_id`: bữa ăn liên quan nếu đo trước hoặc sau ăn.
- `glucose_value`, `unit`: giá trị và đơn vị đo, mặc định `mg/dL`.
- `measurement_context`: bối cảnh đo như đói, trước ăn, sau ăn, trước ngủ, ngẫu nhiên.
- `measured_at`, `source_type`, `note`: thời điểm đo, nguồn dữ liệu và ghi chú.

## 9. `glucose_scan_uploads`
**Mục đích:** Lưu ảnh upload để OCR chỉ số đường huyết. Hệ thống vẫn hoạt động nếu không dùng module này.

**Các trường chính:**
- `user_id`: người upload ảnh.
- `glucose_measurement_id`: bản ghi đường huyết được tạo sau OCR, có thể null.
- `file_url`, `ocr_engine`, `raw_ocr_text`, `confidence_score`, `scan_status`: thông tin xử lý OCR.

## 10. `health_assessments`
**Mục đích:** Lưu kết quả phân tích sức khỏe dùng cho dashboard, dự đoán nguy cơ và khuyến nghị.

**Các trường chính:**
- `user_id`: người dùng được đánh giá.
- `health_profile_id`: hồ sơ sức khỏe làm đầu vào.
- `assessment_type`, `risk_level`, `health_score`: loại đánh giá, mức nguy cơ và điểm sức khỏe.
- `summary`, `findings_json`: tóm tắt và chi tiết phát hiện dạng JSON.

## 11. `risk_predictions`
**Mục đích:** Lưu kết quả dự đoán nguy cơ bằng AI/ML.

**Các trường chính:**
- `user_id`, `assessment_id`: người dùng và đánh giá sức khỏe làm cơ sở dự đoán.
- `model_name`, `prediction_type`: model và loại dự đoán.
- `risk_percent`, `risk_band`, `high_risk_flag`: mức nguy cơ và cờ cảnh báo.
- `feature_snapshot`: snapshot feature đầu vào tại thời điểm dự đoán.

## 12. `ai_insights`
**Mục đích:** Lưu giải thích và lời khuyên do AI sinh từ đánh giá hoặc dự đoán.

**Các trường chính:**
- `user_id`: người nhận insight.
- `risk_prediction_id`, `assessment_id`: kết quả AI hoặc đánh giá liên quan.
- `insight_type`, `explanation`, `recommendation`, `llm_model`: loại insight, nội dung giải thích, khuyến nghị và model sinh nội dung.

## 13. `meal_logs`
**Mục đích:** Nhật ký bữa ăn tổng quan; món ăn được lấy từ Food API và lưu snapshot ở `meal_log_items`.

**Các trường chính:**
- `user_id`: người dùng ghi nhận bữa ăn.
- `meal_type`, `eaten_at`: loại bữa ăn và thời điểm ăn.
- `total_calories`, `total_carbs`, `total_sugar`, `avg_gi`, `gi_alert`: tổng hợp dinh dưỡng và cảnh báo GI.
- `note`: ghi chú bữa ăn.

## 14. `meal_log_items`
**Mục đích:** Chi tiết món ăn trong bữa. Bảng này không FK tới bảng `foods`; dữ liệu món ăn được lấy từ Food API hoặc nhập tay rồi lưu snapshot.

**Các trường chính:**
- `meal_log_id`: bữa ăn cha.
- `food_external_id`, `food_name`, `food_source`: định danh và nguồn món ăn bên ngoài.
- `serving_unit`, `quantity`: đơn vị và số lượng khẩu phần.
- `calories`, `carbs`, `sugar`, `protein`, `fat`, `gi_index`: snapshot dinh dưỡng theo lượng ăn thực tế.
- `nutrition_snapshot`: payload dinh dưỡng gốc để audit hoặc tính lại.

## 15. `food_image_analyses`
**Mục đích:** Lưu kết quả AI nhận diện món ăn từ ảnh, có thể dùng để gọi Food API lấy dinh dưỡng. Đây là module backup theo DBML.

**Các trường chính:**
- `user_id`, `meal_log_id`: người upload và bữa ăn được gắn kết quả nếu có.
- `image_url`, `ai_provider`, `detected_foods`, `confidence_score`, `status`: thông tin ảnh và kết quả nhận diện.

## 16. `meal_glucose_analyses`
**Mục đích:** Phân tích mối liên hệ giữa bữa ăn và biến động đường huyết.

**Các trường chính:**
- `user_id`, `meal_log_id`: người dùng và bữa ăn được phân tích.
- `pre_meal_glucose_id`, `post_meal_glucose_id`: chỉ số trước và sau ăn.
- `glucose_delta`, `abnormal_spike`, `conclusion`: chênh lệch, cờ tăng bất thường và kết luận.

## 17. `exercises`
**Mục đích:** Danh mục bài tập dùng cho khuyến nghị vận động. Đây là module tùy chọn theo DBML.

**Các trường chính:**
- `name`, `intensity_level`: tên và cường độ bài tập.
- `duration_minutes`, `calories_burn_est`, `description`: thời lượng gợi ý, calo ước tính và mô tả.

## 18. `user_recommendations`
**Mục đích:** Lưu khuyến nghị cá nhân hóa; món ăn tham chiếu Food API thay vì bảng `foods`.

**Các trường chính:**
- `user_id`: người nhận khuyến nghị.
- `assessment_id`, `risk_prediction_id`: đánh giá hoặc dự đoán liên quan.
- `recommendation_type`: loại khuyến nghị như dinh dưỡng, vận động, lối sống, glucose.
- `food_external_id`, `food_name`: món ăn khuyến nghị từ Food API nếu có.
- `exercise_id`, `priority`, `content`: bài tập, mức ưu tiên và nội dung khuyến nghị.
- `valid_from`, `valid_to`: thời hạn hiệu lực; SQL có check `valid_from < valid_to` khi cả hai không null.

## 19. `reminders`
**Mục đích:** Lịch nhắc cá nhân cho đo đường huyết, uống thuốc, bữa ăn, vận động, uống nước, ngủ hoặc nhắc tùy chỉnh.

**Các trường chính:**
- `user_id`: người dùng sở hữu lịch nhắc.
- `reminder_type`, `title`, `reminder_time`: loại, tiêu đề và giờ nhắc.
- `recurrence_rule`, `is_active`, `snooze_minutes`, `payload`: cấu hình lặp, trạng thái, hoãn nhắc và dữ liệu mở rộng.

## 20. `notifications`
**Mục đích:** Trung tâm thông báo lưu nhắc nhở, cảnh báo, insight, báo cáo và thông báo hệ thống.

**Các trường chính:**
- `user_id`: người nhận thông báo.
- `reminder_id`, `alert_rule_id`, `ai_insight_id`: nguồn sinh thông báo nếu có. Theo DBML hiện tại `alert_rule_id` là mã tham chiếu, chưa có bảng `alert_rules`.
- `type`, `title`, `content`: loại, tiêu đề và nội dung thông báo.
- `is_read`, `delivery_channel`, `related_entity_type`, `related_entity_id`, `read_at`: trạng thái đọc, kênh gửi và thực thể liên quan.

## 21. `periodic_reports`
**Mục đích:** Báo cáo tuần/tháng gồm tổng quan sức khỏe, xu hướng glucose, so sánh kỳ trước và vấn đề cần cải thiện.

**Các trường chính:**
- `user_id`: người dùng sở hữu báo cáo.
- `period_type`, `period_start`, `period_end`: loại kỳ báo cáo và phạm vi thời gian.
- `avg_glucose`, `health_score`, `bmi`, `weight_change`: chỉ số tổng hợp.
- `achievement_summary`, `issue_summary`, `achievements_json`, `issues_json`: tóm tắt và chi tiết báo cáo.
- `file_url`, `generated_by`, `generated_at`: file mặc định, nguồn sinh và thời điểm sinh báo cáo.

## 22. `report_exports`
**Mục đích:** Lưu lịch sử xuất báo cáo để chia sẻ hoặc tải về.

**Các trường chính:**
- `report_id`, `user_id`: báo cáo được export và người yêu cầu hoặc sở hữu file.
- `export_format`: định dạng `PDF`, `CSV`, `XLSX`.
- `file_url`, `exported_at`: file đã export và thời điểm export.

## 23. `community_clusters`
**Mục đích:** Cụm cộng đồng dùng để so sánh người dùng với nhóm tương đồng.

**Các trường chính:**
- `cluster_name`: tên cụm.
- `age_group`, `risk_group`: nhóm tuổi và nhóm nguy cơ đại diện.
- `description`, `snapshot_date`: mô tả cụm và ngày chụp dữ liệu phân cụm.

## 24. `user_cluster_snapshots`
**Mục đích:** Lưu kết quả xếp cụm theo từng thời điểm cho mỗi người dùng.

**Các trường chính:**
- `user_id`, `cluster_id`: người dùng và cụm tương ứng.
- `percentile_rank`, `community_score`: thứ hạng phân vị và điểm so sánh cộng đồng.
- `snapshot_date`: ngày ghi nhận snapshot.

## 25. `chat_sessions`
**Mục đích:** Phiên hội thoại chatbot về tiểu đường, dinh dưỡng, biến chứng và FAQ.

**Các trường chính:**
- `user_id`: người mở phiên chat.
- `session_title`, `status`: tiêu đề gợi nhớ và trạng thái phiên.
- `started_at`, `ended_at`: thời điểm bắt đầu và kết thúc.

## 26. `chat_messages`
**Mục đích:** Tin nhắn trong phiên chat, bao gồm user, assistant và system.

**Các trường chính:**
- `session_id`: phiên chat chứa tin nhắn.
- `user_id`: người dùng liên quan, có thể null với assistant/system.
- `sender_type`, `content`, `llm_model`: loại người gửi, nội dung và model AI nếu có.
- `flagged_emergency`: cờ phát hiện nội dung khẩn cấp.

## 27. `knowledge_documents`
**Mục đích:** Metadata nguồn tri thức y khoa cho chatbot RAG.

**Các trường chính:**
- `title`, `source_type`, `source_url`: tiêu đề, loại nguồn và URL gốc.
- `medical_topic`, `version`, `is_active`: chủ đề y khoa, phiên bản và trạng thái dùng cho RAG.

## 28. `chat_citations`
**Mục đích:** Trích dẫn nguồn cho câu trả lời chatbot để tăng khả năng kiểm chứng.

**Các trường chính:**
- `message_id`: tin nhắn assistant chứa trích dẫn.
- `knowledge_document_id`: tài liệu nguồn được trích.
- `cited_chunk`, `relevance_score`: đoạn tri thức được dùng và điểm liên quan.

## 29. `journal_entries`
**Mục đích:** Nhật ký tự do về triệu chứng, cảm xúc, cơ thể và sự kiện sức khỏe.

**Các trường chính:**
- `user_id`: người viết nhật ký.
- `title`, `content`, `mood`: tiêu đề, nội dung và tâm trạng.
- `symptom_tags`: nhãn triệu chứng dạng JSON.

## 30. `journal_analyses`
**Mục đích:** Kết quả LLM phân tích nhật ký không cấu trúc.

**Các trường chính:**
- `journal_entry_id`: nhật ký được phân tích.
- `analyzed_by_model`: model AI dùng để phân tích.
- `extracted_symptoms`, `extracted_trends`: triệu chứng và xu hướng trích xuất.
- `risk_flag`, `summary`: cờ nguy cơ và tóm tắt phân tích.

## Mối liên kết nghiệp vụ chính
- `users` là bảng gốc, liên kết đến hồ sơ sức khỏe, tiền sử bệnh, mục tiêu, đường huyết, bữa ăn, thông báo, báo cáo, chat, nhật ký.
- `health_profiles`, `activity_factors`, `medical_histories` là cụm dữ liệu nền cho đánh giá sức khỏe và AI feature engineering.
- `health_assessments`, `risk_predictions`, `ai_insights`, `user_recommendations` là cụm đánh giá, dự đoán, giải thích và khuyến nghị.
- `meal_logs`, `meal_log_items`, `food_image_analyses`, `meal_glucose_analyses` là cụm dinh dưỡng và tương quan đường huyết; dữ liệu món ăn lấy từ Food API/snapshot, không dùng bảng `foods` nội bộ.
- `reminders`, `notifications`, `periodic_reports`, `report_exports` là cụm nhắc nhở, thông báo và báo cáo.
- `chat_sessions`, `chat_messages`, `knowledge_documents`, `chat_citations` là cụm chatbot RAG.
- `community_clusters`, `user_cluster_snapshots` là cụm so sánh cộng đồng.

## Nhận xét nhanh về schema
- Schema đã bao phủ các module chính của hệ thống giám sát và phòng ngừa tiểu đường.
- Các trường snapshot dạng `jsonb` đã phù hợp với PostgreSQL để lưu payload linh hoạt và truy vấn sâu khi cần.
- DBML hiện vẫn khai báo enum `alert_rule_type` và `threshold_operator`, nhưng chưa có bảng `alert_rules`; vì vậy `notifications.alert_rule_id` hiện là mã tham chiếu chưa có FK.
