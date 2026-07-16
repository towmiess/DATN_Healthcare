CREATE SCHEMA IF NOT EXISTS "public";

CREATE TYPE "public"."meal_type" AS ENUM ('BREAKFAST', 'LUNCH', 'DINNER', 'SNACK', 'OTHER');
CREATE TYPE "public"."measurement_context" AS ENUM ('FASTING', 'BEFORE_MEAL', 'AFTER_MEAL', 'BEDTIME', 'RANDOM');
CREATE TYPE "public"."notification_type" AS ENUM ('REMINDER', 'TREND_ALERT', 'EMERGENCY_ALERT', 'AI_INSIGHT', 'WEEKLY_REPORT', 'MONTHLY_REPORT', 'SYSTEM');
CREATE TYPE "public"."recommendation_type" AS ENUM ('DIET', 'EXERCISE', 'LIFESTYLE', 'GLUCOSE', 'GENERAL');
CREATE TYPE "public"."reminder_type" AS ENUM ('GLUCOSE_CHECK', 'MEDICATION', 'MEAL', 'EXERCISE', 'WATER', 'SLEEP', 'CUSTOM');
CREATE TYPE "public"."report_period_type" AS ENUM ('WEEKLY', 'MONTHLY');
CREATE TYPE "public"."risk_band" AS ENUM ('SAFE', 'WARNING', 'DANGEROUS');
CREATE TYPE "public"."sender_type" AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');
CREATE TYPE "public"."source_type" AS ENUM ('MANUAL', 'SCAN', 'DEVICE_SYNC');
CREATE TYPE "public"."alert_rule_type" AS ENUM ('GLUCOSE_THRESHOLD', 'GLUCOSE_TREND', 'GI_THRESHOLD', 'EMERGENCY_SYMPTOM', 'ADHERENCE');
CREATE TYPE "public"."threshold_operator" AS ENUM ('GT', 'GTE', 'LT', 'LTE', 'EQ', 'BETWEEN');
CREATE TYPE "public"."export_format" AS ENUM ('PDF', 'CSV', 'XLSX');

CREATE TABLE "public"."activity_factors" (
    "id" bigserial NOT NULL,
    "code" varchar(50) NOT NULL UNIQUE,
    "name" varchar(100) NOT NULL,
    "description" text NOT NULL,
    "factor_value" numeric(4, 3) NOT NULL,
    "display_order" int NOT NULL DEFAULT 0,
    "is_active" boolean NOT NULL DEFAULT true,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."glucose_scan_uploads" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "glucose_measurement_id" bigint UNIQUE,
    "file_url" varchar(500) NOT NULL,
    "ocr_engine" varchar(100),
    "raw_ocr_text" text,
    "confidence_score" numeric(5, 2),
    "scan_status" varchar(50),
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."ai_insights" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "risk_prediction_id" bigint,
    "assessment_id" bigint,
    "insight_type" varchar(100) NOT NULL,
    "explanation" text,
    "recommendation" text,
    "llm_model" varchar(100),
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."meal_glucose_analyses" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "meal_log_id" bigint NOT NULL,
    "pre_meal_glucose_id" bigint,
    "post_meal_glucose_id" bigint,
    "glucose_delta" numeric(8, 2),
    "abnormal_spike" boolean NOT NULL DEFAULT false,
    "conclusion" text,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."chat_sessions" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "session_title" varchar(255),
    "status" varchar(50),
    "started_at" timestamp NOT NULL,
    "ended_at" timestamp,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."health_assessments" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "health_profile_id" bigint,
    "diagnosis_session_id" bigint,
    "assessment_type" varchar(100) NOT NULL,
    "risk_level" varchar(50),
    "health_score" numeric(6, 2),
    "summary" text,
    "findings_json" jsonb,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."reminders" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "reminder_type" reminder_type NOT NULL,
    "title" varchar(255) NOT NULL,
    "reminder_time" time NOT NULL,
    "recurrence_rule" varchar(120),
    "is_active" boolean NOT NULL DEFAULT true,
    "snooze_minutes" int DEFAULT 15,
    "payload" jsonb,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."meal_logs" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "meal_type" meal_type NOT NULL,
    "eaten_at" timestamp NOT NULL,
    "total_calories" numeric(10, 2),
    "total_carbs" numeric(10, 2),
    "total_sugar" numeric(10, 2),
    "avg_gi" numeric(6, 2),
    "gi_alert" boolean NOT NULL DEFAULT false,
    "note" text,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."chat_messages" (
    "id" bigserial NOT NULL,
    "session_id" bigint NOT NULL,
    "user_id" bigint,
    "sender_type" sender_type NOT NULL,
    "content" text NOT NULL,
    "llm_model" varchar(100),
    "flagged_emergency" boolean NOT NULL DEFAULT false,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."roles" (
    "id" bigserial NOT NULL,
    "name" varchar(100) NOT NULL UNIQUE,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."risk_predictions" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "assessment_id" bigint NOT NULL,
    "diagnosis_session_id" bigint,
    "model_name" varchar(100) NOT NULL,
    "prediction_type" varchar(100) NOT NULL,
    "risk_percent" numeric(5, 2) NOT NULL,
    "risk_band" risk_band NOT NULL,
    "high_risk_flag" boolean NOT NULL DEFAULT false,
    "feature_snapshot" jsonb,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."users" (
    "id" BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    "full_name" varchar(255) NOT NULL,
    "email" varchar(255) NOT NULL UNIQUE,
    "phone_number" varchar(30),
    "password" varchar(255) NOT NULL,
    "avatar" varchar(500),
    "status" boolean NOT NULL DEFAULT false,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL
);

CREATE TABLE "public"."meal_log_items" (
    "id" bigserial NOT NULL,
    "meal_log_id" bigint NOT NULL,
    "food_external_id" varchar(120),
    "food_name" varchar(255) NOT NULL,
    "food_source" varchar(100),
    "serving_unit" varchar(50),
    "quantity" numeric(10, 2) NOT NULL,
    "calories" numeric(10, 2),
    "carbs" numeric(10, 2),
    "sugar" numeric(10, 2),
    "protein" numeric(10, 2),
    "fat" numeric(10, 2),
    "gi_index" numeric(6, 2),
    "nutrition_snapshot" jsonb,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."health_goals" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "goal_type" varchar(100) NOT NULL,
    "level" varchar(50),
    "target_value" numeric(10, 2),
    "start_date" date,
    "target_date" date,
    "status" varchar(50),
    "note" text,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."medical_histories" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "diabetes_type" varchar(50),
    "family_history_diabetes" boolean DEFAULT false,
    "hypertension" boolean DEFAULT false,
    "cardiovascular_disease" boolean DEFAULT false,
    "kidney_disease" boolean DEFAULT false,
    "pregnancy_history" boolean DEFAULT false,
    "allergies" text,
    "current_medications" text,
    "past_conditions" text,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."chat_citations" (
    "id" bigserial NOT NULL,
    "message_id" bigint NOT NULL,
    "knowledge_document_id" bigint NOT NULL,
    "cited_chunk" text,
    "relevance_score" numeric(5, 2),
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."community_clusters" (
    "id" bigserial NOT NULL,
    "cluster_name" varchar(150) NOT NULL,
    "age_group" varchar(50),
    "risk_group" varchar(50),
    "description" text,
    "snapshot_date" date NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."journal_analyses" (
    "id" bigserial NOT NULL,
    "journal_entry_id" bigint NOT NULL,
    "analyzed_by_model" varchar(100),
    "extracted_symptoms" jsonb,
    "extracted_trends" jsonb,
    "risk_flag" boolean NOT NULL DEFAULT false,
    "summary" text,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."user_recommendations" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "assessment_id" bigint,
    "risk_prediction_id" bigint,
    "recommendation_type" recommendation_type NOT NULL,
    "food_external_id" varchar(120),
    "food_name" varchar(255),
    "exercise_id" bigint,
    "priority" varchar(30),
    "content" text NOT NULL,
    "valid_from" date,
    "valid_to" date,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."user_roles" (
    "user_id" bigint NOT NULL,
    "role_id" bigint NOT NULL,
    PRIMARY KEY ("user_id", "role_id")
);

CREATE TABLE "public"."notifications" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "reminder_id" bigint,
    "alert_rule_id" bigint,
    "ai_insight_id" bigint,
    "type" notification_type NOT NULL,
    "title" varchar(255) NOT NULL,
    "content" text NOT NULL,
    "is_read" boolean NOT NULL DEFAULT false,
    "delivery_channel" varchar(50),
    "related_entity_type" varchar(100),
    "related_entity_id" bigint,
    "created_at" timestamp NOT NULL,
    "read_at" timestamp,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."food_image_analyses" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "meal_log_id" bigint,
    "image_url" varchar(500) NOT NULL,
    "ai_provider" varchar(100),
    "detected_foods" jsonb,
    "confidence_score" numeric(5, 2),
    "status" varchar(50),
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."periodic_reports" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "period_type" report_period_type NOT NULL,
    "period_start" date NOT NULL,
    "period_end" date NOT NULL,
    "avg_glucose" numeric(8, 2),
    "health_score" numeric(6, 2),
    "bmi" numeric(6, 2),
    "weight_change" numeric(8, 2),
    "achievement_summary" text,
    "issue_summary" text,
    "achievements_json" jsonb,
    "issues_json" jsonb,
    "file_url" varchar(500),
    "generated_by" varchar(100),
    "generated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."report_exports" (
    "id" bigserial NOT NULL,
    "report_id" bigint NOT NULL,
    "user_id" bigint NOT NULL,
    "export_format" export_format NOT NULL,
    "file_url" varchar(500) NOT NULL,
    "exported_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."report_drafts" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "period_type" report_period_type NOT NULL,
    "period_start" date NOT NULL,
    "period_end" date NOT NULL,
    "payload" jsonb NOT NULL DEFAULT '{}'::jsonb,
    "status" varchar(30) NOT NULL DEFAULT 'DRAFT',
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id"),
    UNIQUE ("user_id", "period_type", "period_start", "period_end")
);

CREATE TABLE "public"."diagnosis_sessions" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "session_type" varchar(50) NOT NULL DEFAULT 'DIAGNOSIS',
    "source_type" varchar(50) NOT NULL DEFAULT 'MANUAL',
    "baseline_id" bigint,
    "sample_collected_at" timestamp,
    "status" varchar(30) NOT NULL DEFAULT 'DRAFT',
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."clinical_documents" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "diagnosis_session_id" bigint,
    "document_type" varchar(50) NOT NULL DEFAULT 'LAB_REPORT',
    "original_filename" varchar(255),
    "file_url" varchar(500),
    "mime_type" varchar(100),
    "provider_name" varchar(255),
    "sample_collected_at" timestamp,
    "ocr_engine" varchar(100),
    "raw_ocr_text" text,
    "confidence_score" numeric(5, 2),
    "verification_status" varchar(30) NOT NULL DEFAULT 'REVIEW_REQUIRED',
    "file_sha256" varchar(64),
    "created_at" timestamp NOT NULL,
    "verified_at" timestamp,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."lab_panels" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "clinical_document_id" bigint,
    "diagnosis_session_id" bigint,
    "provider_name" varchar(255),
    "sampled_at" timestamp NOT NULL,
    "reported_at" timestamp,
    "status" varchar(30) NOT NULL DEFAULT 'VERIFIED',
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."lab_results" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "lab_panel_id" bigint NOT NULL,
    "test_code" varchar(80) NOT NULL,
    "test_name" varchar(255) NOT NULL,
    "value" numeric(14, 4) NOT NULL,
    "unit" varchar(50) NOT NULL,
    "canonical_value" numeric(14, 4),
    "canonical_unit" varchar(50),
    "reference_min" numeric(14, 4),
    "reference_max" numeric(14, 4),
    "reference_text" varchar(255),
    "abnormal_flag" varchar(20),
    "source_type" varchar(50) NOT NULL DEFAULT 'HOSPITAL_LAB',
    "confidence_score" numeric(5, 2),
    "is_verified" boolean NOT NULL DEFAULT false,
    "observed_at" timestamp NOT NULL,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."clinical_observations" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "diagnosis_session_id" bigint NOT NULL,
    "clinical_document_id" bigint,
    "observation_code" varchar(80) NOT NULL,
    "observation_name" varchar(255) NOT NULL,
    "value" numeric(14, 4) NOT NULL,
    "unit" varchar(50) NOT NULL,
    "canonical_value" numeric(14, 4),
    "canonical_unit" varchar(50),
    "reference_min" numeric(14, 4),
    "reference_max" numeric(14, 4),
    "reference_text" varchar(255),
    "abnormal_flag" varchar(20),
    "source_type" varchar(50) NOT NULL DEFAULT 'HOSPITAL_RECORD',
    "confidence_score" numeric(5, 2),
    "is_verified" boolean NOT NULL DEFAULT false,
    "observed_at" timestamp NOT NULL,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."clinical_baselines" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "diagnosis_session_id" bigint NOT NULL,
    "label" varchar(255) NOT NULL,
    "effective_at" timestamp NOT NULL,
    "status" varchar(30) NOT NULL DEFAULT 'ACTIVE',
    "supersedes_baseline_id" bigint,
    "created_at" timestamp NOT NULL,
    "archived_at" timestamp,
    PRIMARY KEY ("id"),
    UNIQUE ("diagnosis_session_id")
);

CREATE TABLE "public"."user_cluster_snapshots" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "cluster_id" bigint NOT NULL,
    "percentile_rank" int,
    "community_score" numeric(8, 2),
    "snapshot_date" date NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."journal_entries" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "title" varchar(255),
    "content" text NOT NULL,
    "mood" varchar(50),
    "symptom_tags" jsonb,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."knowledge_documents" (
    "id" bigserial NOT NULL,
    "title" varchar(255) NOT NULL,
    "source_type" varchar(100),
    "source_url" varchar(500),
    "medical_topic" varchar(150),
    "version" varchar(50),
    "is_active" boolean NOT NULL DEFAULT true,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."health_profiles" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL UNIQUE,
    "date_of_birth" date,
    "gender" varchar(20),
    "height_cm" numeric(6, 2),
    "weight_kg" numeric(6, 2),
    "waist_cm" numeric(6, 2),
    "bmi" numeric(6, 2),
    "bmr" numeric(8, 2),
    "tdee" numeric(8, 2),
    "activity_factor_id" bigint,
    "activity_level" varchar(50),
    "smoking_status" varchar(50),
    "alcohol_status" varchar(50),
    "sleep_pattern" varchar(100),
    "medical_notes" text,
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."exercises" (
    "id" bigserial NOT NULL,
    "name" varchar(255) NOT NULL,
    "intensity_level" varchar(50),
    "duration_minutes" int,
    "calories_burn_est" numeric(8, 2),
    "description" text,
    PRIMARY KEY ("id")
);

CREATE TABLE "public"."glucose_measurements" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "meal_log_id" bigint,
    "glucose_value" numeric(8, 2) NOT NULL,
    "unit" varchar(20) NOT NULL DEFAULT 'mg/dL',
    "measurement_context" measurement_context NOT NULL,
    "measured_at" timestamp NOT NULL,
    "source_type" source_type NOT NULL DEFAULT 'MANUAL',
    "note" text,
    "created_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

INSERT INTO "public"."activity_factors"
    ("code", "name", "description", "factor_value", "display_order", "is_active", "created_at", "updated_at")
VALUES
    ('SEDENTARY', 'Ít vận động', 'Người ít hoặc không tham gia hoạt động thể chất.', 1.200, 1, true, now(), now()),
    ('LIGHT', 'Vận động nhẹ', 'Vận động thể chất hoặc tập thể dục 1-3 ngày/tuần.', 1.375, 2, true, now(), now()),
    ('MODERATE', 'Vận động vừa phải', 'Vận động thể chất hoặc tập thể dục 3-5 ngày/tuần.', 1.550, 3, true, now(), now()),
    ('ACTIVE', 'Vận động nhiều', 'Vận động thể chất hoặc tập thể dục 6-7 ngày/tuần.', 1.725, 4, true, now(), now()),
    ('VERY_ACTIVE', 'Vận động rất nhiều', 'Vận động hơn 90 phút mỗi ngày hoặc làm công việc nặng.', 1.900, 5, true, now(), now());

-- Indexes
CREATE INDEX "idx_glucose_measurements_user_measured_at" ON "public"."glucose_measurements" ("user_id", "measured_at");
CREATE INDEX "idx_glucose_measurements_meal_log_id" ON "public"."glucose_measurements" ("meal_log_id");
CREATE INDEX "idx_meal_logs_user_eaten_at" ON "public"."meal_logs" ("user_id", "eaten_at");
CREATE INDEX "idx_notifications_user_is_read" ON "public"."notifications" ("user_id", "is_read");
CREATE INDEX "idx_notifications_user_created_at" ON "public"."notifications" ("user_id", "created_at");
CREATE INDEX "idx_periodic_reports_user_period" ON "public"."periodic_reports" ("user_id", "period_type", "period_start", "period_end");
CREATE INDEX "idx_report_drafts_user_period" ON "public"."report_drafts" ("user_id", "period_type", "period_start", "period_end");
CREATE INDEX "idx_diagnosis_sessions_user_created_at" ON "public"."diagnosis_sessions" ("user_id", "created_at");
CREATE INDEX "idx_clinical_documents_user_created_at" ON "public"."clinical_documents" ("user_id", "created_at");
CREATE INDEX "idx_lab_panels_user_sampled_at" ON "public"."lab_panels" ("user_id", "sampled_at");
CREATE INDEX "idx_lab_results_user_test_observed" ON "public"."lab_results" ("user_id", "test_code", "observed_at");
CREATE INDEX "idx_clinical_observations_user_code_observed" ON "public"."clinical_observations" ("user_id", "observation_code", "observed_at");
CREATE INDEX "idx_clinical_baselines_user_effective" ON "public"."clinical_baselines" ("user_id", "effective_at");
CREATE UNIQUE INDEX "uq_clinical_baselines_active_user" ON "public"."clinical_baselines" ("user_id") WHERE "status" = 'ACTIVE';
CREATE INDEX "idx_user_cluster_snapshots_user_snapshot" ON "public"."user_cluster_snapshots" ("user_id", "snapshot_date");
CREATE INDEX "idx_user_cluster_snapshots_cluster_snapshot" ON "public"."user_cluster_snapshots" ("cluster_id", "snapshot_date");
CREATE INDEX "idx_chat_messages_session_created_at" ON "public"."chat_messages" ("session_id", "created_at");
CREATE INDEX "idx_health_assessments_diagnosis_session_id" ON "public"."health_assessments" ("diagnosis_session_id");
CREATE INDEX "idx_risk_predictions_diagnosis_session_id" ON "public"."risk_predictions" ("diagnosis_session_id");

-- Check constraints
ALTER TABLE "public"."user_recommendations" ADD CONSTRAINT "chk_user_recommendations_valid_period" CHECK ("valid_from" IS NULL OR "valid_to" IS NULL OR "valid_from" < "valid_to");

-- Foreign key constraints
-- Schema: public
ALTER TABLE "public"."ai_insights" ADD CONSTRAINT "fk_ai_insights_assessment_id_health_assessments_id" FOREIGN KEY("assessment_id") REFERENCES "public"."health_assessments"("id");
ALTER TABLE "public"."ai_insights" ADD CONSTRAINT "fk_ai_insights_risk_prediction_id_risk_predictions_id" FOREIGN KEY("risk_prediction_id") REFERENCES "public"."risk_predictions"("id");
ALTER TABLE "public"."ai_insights" ADD CONSTRAINT "fk_ai_insights_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."chat_citations" ADD CONSTRAINT "fk_chat_citations_knowledge_document_id_knowledge_documents_" FOREIGN KEY("knowledge_document_id") REFERENCES "public"."knowledge_documents"("id");
ALTER TABLE "public"."chat_citations" ADD CONSTRAINT "fk_chat_citations_message_id_chat_messages_id" FOREIGN KEY("message_id") REFERENCES "public"."chat_messages"("id");
ALTER TABLE "public"."chat_messages" ADD CONSTRAINT "fk_chat_messages_session_id_chat_sessions_id" FOREIGN KEY("session_id") REFERENCES "public"."chat_sessions"("id");
ALTER TABLE "public"."chat_messages" ADD CONSTRAINT "fk_chat_messages_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."chat_sessions" ADD CONSTRAINT "fk_chat_sessions_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."food_image_analyses" ADD CONSTRAINT "fk_food_image_analyses_meal_log_id_meal_logs_id" FOREIGN KEY("meal_log_id") REFERENCES "public"."meal_logs"("id");
ALTER TABLE "public"."food_image_analyses" ADD CONSTRAINT "fk_food_image_analyses_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."glucose_measurements" ADD CONSTRAINT "fk_glucose_measurements_meal_log_id_meal_logs_id" FOREIGN KEY("meal_log_id") REFERENCES "public"."meal_logs"("id");
ALTER TABLE "public"."glucose_measurements" ADD CONSTRAINT "fk_glucose_measurements_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."glucose_scan_uploads" ADD CONSTRAINT "fk_glucose_scan_uploads_glucose_measurement_id_glucose_measu" FOREIGN KEY("glucose_measurement_id") REFERENCES "public"."glucose_measurements"("id");
ALTER TABLE "public"."glucose_scan_uploads" ADD CONSTRAINT "fk_glucose_scan_uploads_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."health_assessments" ADD CONSTRAINT "fk_health_assessments_health_profile_id_health_profiles_id" FOREIGN KEY("health_profile_id") REFERENCES "public"."health_profiles"("id");
ALTER TABLE "public"."health_assessments" ADD CONSTRAINT "fk_health_assessments_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."health_goals" ADD CONSTRAINT "fk_health_goals_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."health_profiles" ADD CONSTRAINT "fk_health_profiles_activity_factor_id_activity_factors_id" FOREIGN KEY("activity_factor_id") REFERENCES "public"."activity_factors"("id");
ALTER TABLE "public"."health_profiles" ADD CONSTRAINT "fk_health_profiles_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."journal_analyses" ADD CONSTRAINT "fk_journal_analyses_journal_entry_id_journal_entries_id" FOREIGN KEY("journal_entry_id") REFERENCES "public"."journal_entries"("id");
ALTER TABLE "public"."journal_entries" ADD CONSTRAINT "fk_journal_entries_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."meal_glucose_analyses" ADD CONSTRAINT "fk_meal_glucose_analyses_meal_log_id_meal_logs_id" FOREIGN KEY("meal_log_id") REFERENCES "public"."meal_logs"("id");
ALTER TABLE "public"."meal_glucose_analyses" ADD CONSTRAINT "fk_meal_glucose_analyses_post_meal_glucose_id_glucose_measur" FOREIGN KEY("post_meal_glucose_id") REFERENCES "public"."glucose_measurements"("id");
ALTER TABLE "public"."meal_glucose_analyses" ADD CONSTRAINT "fk_meal_glucose_analyses_pre_meal_glucose_id_glucose_measure" FOREIGN KEY("pre_meal_glucose_id") REFERENCES "public"."glucose_measurements"("id");
ALTER TABLE "public"."meal_glucose_analyses" ADD CONSTRAINT "fk_meal_glucose_analyses_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."meal_log_items" ADD CONSTRAINT "fk_meal_log_items_meal_log_id_meal_logs_id" FOREIGN KEY("meal_log_id") REFERENCES "public"."meal_logs"("id");
ALTER TABLE "public"."meal_logs" ADD CONSTRAINT "fk_meal_logs_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."medical_histories" ADD CONSTRAINT "fk_medical_histories_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."notifications" ADD CONSTRAINT "fk_notifications_reminder_id_reminders_id" FOREIGN KEY("reminder_id") REFERENCES "public"."reminders"("id");
ALTER TABLE "public"."notifications" ADD CONSTRAINT "fk_notifications_ai_insight_id_ai_insights_id" FOREIGN KEY("ai_insight_id") REFERENCES "public"."ai_insights"("id");
ALTER TABLE "public"."notifications" ADD CONSTRAINT "fk_notifications_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."periodic_reports" ADD CONSTRAINT "fk_periodic_reports_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."report_exports" ADD CONSTRAINT "fk_report_exports_report_id_periodic_reports_id" FOREIGN KEY("report_id") REFERENCES "public"."periodic_reports"("id");
ALTER TABLE "public"."report_exports" ADD CONSTRAINT "fk_report_exports_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."report_drafts" ADD CONSTRAINT "fk_report_drafts_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."diagnosis_sessions" ADD CONSTRAINT "fk_diagnosis_sessions_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."clinical_documents" ADD CONSTRAINT "fk_clinical_documents_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."clinical_documents" ADD CONSTRAINT "fk_clinical_documents_diagnosis_session_id" FOREIGN KEY("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions"("id");
ALTER TABLE "public"."lab_panels" ADD CONSTRAINT "fk_lab_panels_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."lab_panels" ADD CONSTRAINT "fk_lab_panels_clinical_document_id" FOREIGN KEY("clinical_document_id") REFERENCES "public"."clinical_documents"("id");
ALTER TABLE "public"."lab_panels" ADD CONSTRAINT "fk_lab_panels_diagnosis_session_id" FOREIGN KEY("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions"("id");
ALTER TABLE "public"."lab_results" ADD CONSTRAINT "fk_lab_results_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."lab_results" ADD CONSTRAINT "fk_lab_results_lab_panel_id" FOREIGN KEY("lab_panel_id") REFERENCES "public"."lab_panels"("id");
ALTER TABLE "public"."clinical_observations" ADD CONSTRAINT "fk_clinical_observations_user_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."clinical_observations" ADD CONSTRAINT "fk_clinical_observations_diagnosis_session_id" FOREIGN KEY("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions"("id");
ALTER TABLE "public"."clinical_observations" ADD CONSTRAINT "fk_clinical_observations_clinical_document_id" FOREIGN KEY("clinical_document_id") REFERENCES "public"."clinical_documents"("id");
ALTER TABLE "public"."clinical_baselines" ADD CONSTRAINT "fk_clinical_baselines_user_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."clinical_baselines" ADD CONSTRAINT "fk_clinical_baselines_diagnosis_session_id" FOREIGN KEY("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions"("id");
ALTER TABLE "public"."clinical_baselines" ADD CONSTRAINT "fk_clinical_baselines_supersedes_id" FOREIGN KEY("supersedes_baseline_id") REFERENCES "public"."clinical_baselines"("id");
ALTER TABLE "public"."diagnosis_sessions" ADD CONSTRAINT "fk_diagnosis_sessions_baseline_id" FOREIGN KEY("baseline_id") REFERENCES "public"."clinical_baselines"("id");
ALTER TABLE "public"."reminders" ADD CONSTRAINT "fk_reminders_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."risk_predictions" ADD CONSTRAINT "fk_risk_predictions_assessment_id_health_assessments_id" FOREIGN KEY("assessment_id") REFERENCES "public"."health_assessments"("id");
ALTER TABLE "public"."risk_predictions" ADD CONSTRAINT "fk_risk_predictions_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."user_cluster_snapshots" ADD CONSTRAINT "fk_user_cluster_snapshots_cluster_id_community_clusters_id" FOREIGN KEY("cluster_id") REFERENCES "public"."community_clusters"("id");
ALTER TABLE "public"."user_cluster_snapshots" ADD CONSTRAINT "fk_user_cluster_snapshots_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."user_recommendations" ADD CONSTRAINT "fk_user_recommendations_assessment_id_health_assessments_id" FOREIGN KEY("assessment_id") REFERENCES "public"."health_assessments"("id");
ALTER TABLE "public"."user_recommendations" ADD CONSTRAINT "fk_user_recommendations_exercise_id_exercises_id" FOREIGN KEY("exercise_id") REFERENCES "public"."exercises"("id");
ALTER TABLE "public"."user_recommendations" ADD CONSTRAINT "fk_user_recommendations_risk_prediction_id_risk_predictions_" FOREIGN KEY("risk_prediction_id") REFERENCES "public"."risk_predictions"("id");
ALTER TABLE "public"."user_recommendations" ADD CONSTRAINT "fk_user_recommendations_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");
ALTER TABLE "public"."user_roles" ADD CONSTRAINT "fk_user_roles_role_id_roles_id" FOREIGN KEY("role_id") REFERENCES "public"."roles"("id");
ALTER TABLE "public"."user_roles" ADD CONSTRAINT "fk_user_roles_user_id_users_id" FOREIGN KEY("user_id") REFERENCES "public"."users"("id");

-- Descriptions for db tools and generated documentation
COMMENT ON TABLE "public"."users" IS 'Tài khoản người dùng, admin và các vai trò mở rộng trong hệ thống.';
COMMENT ON COLUMN "public"."users"."id" IS 'Khóa chính người dùng.';
COMMENT ON COLUMN "public"."users"."full_name" IS 'Họ tên hiển thị.';
COMMENT ON COLUMN "public"."users"."email" IS 'Email đăng nhập, nhận OTP và thông báo.';
COMMENT ON COLUMN "public"."users"."phone_number" IS 'Số điện thoại liên hệ.';
COMMENT ON COLUMN "public"."users"."password" IS 'Mật khẩu đã băm theo form hiện tại của bảng users.';
COMMENT ON COLUMN "public"."users"."avatar" IS 'URL ảnh đại diện.';
COMMENT ON COLUMN "public"."users"."status" IS 'Trạng thái kích hoạt tài khoản: false/0 là chưa kích hoạt hoặc không hoạt động, true/1 là hoạt động.';
COMMENT ON COLUMN "public"."users"."created_at" IS 'Thời điểm tạo.';
COMMENT ON COLUMN "public"."users"."updated_at" IS 'Thời điểm cập nhật.';

COMMENT ON TABLE "public"."roles" IS 'Danh mục vai trò như USER, ADMIN, DOCTOR.';
COMMENT ON COLUMN "public"."roles"."id" IS 'Khóa chính vai trò.';
COMMENT ON COLUMN "public"."roles"."name" IS 'Tên vai trò duy nhất.';
COMMENT ON TABLE "public"."user_roles" IS 'Bảng trung gian nhiều-nhiều giữa người dùng và vai trò.';
COMMENT ON COLUMN "public"."user_roles"."user_id" IS 'Người dùng được gán vai trò.';
COMMENT ON COLUMN "public"."user_roles"."role_id" IS 'Vai trò được gán.';

COMMENT ON TABLE "public"."activity_factors" IS 'Danh mục hệ số hoạt động AF dùng trong công thức TDEE = BMR x AF.';
COMMENT ON COLUMN "public"."activity_factors"."id" IS 'Khóa chính hệ số hoạt động.';
COMMENT ON COLUMN "public"."activity_factors"."code" IS 'Mã mức vận động.';
COMMENT ON COLUMN "public"."activity_factors"."name" IS 'Tên mức vận động.';
COMMENT ON COLUMN "public"."activity_factors"."description" IS 'Mô tả mức vận động để người dùng chọn.';
COMMENT ON COLUMN "public"."activity_factors"."factor_value" IS 'Giá trị AF: 1.2, 1.375, 1.55, 1.725 hoặc 1.9.';
COMMENT ON COLUMN "public"."activity_factors"."display_order" IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN "public"."activity_factors"."is_active" IS 'Cờ còn sử dụng.';
COMMENT ON COLUMN "public"."activity_factors"."created_at" IS 'Thời điểm tạo.';
COMMENT ON COLUMN "public"."activity_factors"."updated_at" IS 'Thời điểm cập nhật.';

COMMENT ON TABLE "public"."health_profiles" IS 'Hồ sơ sức khỏe cá nhân phục vụ tính BMI, BMR, TDEE và AI feature engineering.';
COMMENT ON COLUMN "public"."health_profiles"."id" IS 'Khóa chính hồ sơ sức khỏe.';
COMMENT ON COLUMN "public"."health_profiles"."user_id" IS 'Người dùng sở hữu hồ sơ, quan hệ 1-1.';
COMMENT ON COLUMN "public"."health_profiles"."date_of_birth" IS 'Ngày sinh để tính tuổi.';
COMMENT ON COLUMN "public"."health_profiles"."gender" IS 'Giới tính phục vụ tính toán.';
COMMENT ON COLUMN "public"."health_profiles"."height_cm" IS 'Chiều cao theo cm.';
COMMENT ON COLUMN "public"."health_profiles"."weight_kg" IS 'Cân nặng theo kg.';
COMMENT ON COLUMN "public"."health_profiles"."waist_cm" IS 'Vòng eo theo cm.';
COMMENT ON COLUMN "public"."health_profiles"."bmi" IS 'Chỉ số khối cơ thể.';
COMMENT ON COLUMN "public"."health_profiles"."bmr" IS 'Năng lượng chuyển hóa cơ bản.';
COMMENT ON COLUMN "public"."health_profiles"."tdee" IS 'Tổng năng lượng tiêu hao hằng ngày, tính bằng BMR x AF.';
COMMENT ON COLUMN "public"."health_profiles"."activity_factor_id" IS 'Mức hệ số hoạt động tham chiếu activity_factors.';
COMMENT ON COLUMN "public"."health_profiles"."activity_level" IS 'Nhãn mức vận động để hiển thị hoặc tương thích dữ liệu cũ.';
COMMENT ON COLUMN "public"."health_profiles"."smoking_status" IS 'Tình trạng hút thuốc.';
COMMENT ON COLUMN "public"."health_profiles"."alcohol_status" IS 'Tình trạng dùng rượu bia.';
COMMENT ON COLUMN "public"."health_profiles"."sleep_pattern" IS 'Thói quen hoặc chất lượng giấc ngủ.';
COMMENT ON COLUMN "public"."health_profiles"."medical_notes" IS 'Ghi chú y tế bổ sung.';
COMMENT ON COLUMN "public"."health_profiles"."created_at" IS 'Thời điểm tạo.';
COMMENT ON COLUMN "public"."health_profiles"."updated_at" IS 'Thời điểm cập nhật.';

COMMENT ON TABLE "public"."medical_histories" IS 'Tiền sử bệnh và yếu tố nguy cơ của người dùng.';
COMMENT ON TABLE "public"."health_goals" IS 'Mục tiêu sức khỏe cá nhân.';
COMMENT ON TABLE "public"."glucose_measurements" IS 'Bảng core lưu chỉ số đường huyết theo thời gian.';
COMMENT ON TABLE "public"."glucose_scan_uploads" IS 'OPTIONAL MODULE: upload ảnh để OCR đường huyết; hệ thống vẫn hoạt động nếu không dùng bảng này.';
COMMENT ON TABLE "public"."health_assessments" IS 'Kết quả đánh giá sức khỏe tổng hợp.';
COMMENT ON COLUMN "public"."health_assessments"."diagnosis_session_id" IS 'Phiên/chụp dữ liệu chẩn đoán gốc dùng để tạo đánh giá này.';
COMMENT ON TABLE "public"."risk_predictions" IS 'Kết quả dự đoán nguy cơ bằng AI/ML.';
COMMENT ON COLUMN "public"."risk_predictions"."diagnosis_session_id" IS 'Phiên/chụp dữ liệu chẩn đoán gốc dùng để tạo dự đoán này.';
COMMENT ON TABLE "public"."ai_insights" IS 'Giải thích và khuyến nghị do AI sinh.';
COMMENT ON TABLE "public"."meal_logs" IS 'Nhật ký bữa ăn tổng quan.';
COMMENT ON TABLE "public"."meal_log_items" IS 'Chi tiết món ăn trong bữa; món lấy từ Food API và lưu snapshot, không FK tới bảng foods.';
COMMENT ON TABLE "public"."food_image_analyses" IS 'Kết quả AI nhận diện món ăn từ ảnh.';
COMMENT ON TABLE "public"."meal_glucose_analyses" IS 'Phân tích tương quan bữa ăn và biến động đường huyết.';
COMMENT ON TABLE "public"."exercises" IS 'Danh mục bài tập dùng cho khuyến nghị.';
COMMENT ON TABLE "public"."user_recommendations" IS 'Khuyến nghị cá nhân hóa; món ăn tham chiếu Food API bằng external id/name.';
COMMENT ON TABLE "public"."reminders" IS 'Lịch nhắc cá nhân.';
COMMENT ON TABLE "public"."notifications" IS 'Trung tâm thông báo.';
COMMENT ON TABLE "public"."periodic_reports" IS 'Báo cáo tuần/tháng.';
COMMENT ON TABLE "public"."report_exports" IS 'Lịch sử xuất báo cáo PDF/CSV/XLSX.';
COMMENT ON TABLE "public"."community_clusters" IS 'Cụm cộng đồng để so sánh người dùng tương đồng.';
COMMENT ON TABLE "public"."user_cluster_snapshots" IS 'Snapshot xếp cụm của người dùng.';
COMMENT ON TABLE "public"."chat_sessions" IS 'Phiên chat với chatbot AI.';
COMMENT ON TABLE "public"."chat_messages" IS 'Tin nhắn trong phiên chat.';
COMMENT ON TABLE "public"."knowledge_documents" IS 'Metadata tài liệu tri thức y khoa cho RAG.';
COMMENT ON TABLE "public"."chat_citations" IS 'Trích dẫn nguồn cho câu trả lời chatbot.';
COMMENT ON TABLE "public"."journal_entries" IS 'Nhật ký tự do của người dùng.';
COMMENT ON TABLE "public"."journal_analyses" IS 'Kết quả AI phân tích nhật ký.';

COMMENT ON COLUMN "public"."meal_log_items"."food_external_id" IS 'ID món ăn từ Food API bên ngoài.';
COMMENT ON COLUMN "public"."meal_log_items"."food_name" IS 'Tên món ăn từ Food API hoặc nhập tay.';
COMMENT ON COLUMN "public"."meal_log_items"."food_source" IS 'Nguồn dữ liệu món ăn.';
COMMENT ON COLUMN "public"."meal_log_items"."serving_unit" IS 'Đơn vị khẩu phần.';
COMMENT ON COLUMN "public"."meal_log_items"."quantity" IS 'Số lượng khẩu phần.';
COMMENT ON COLUMN "public"."meal_log_items"."calories" IS 'Calories snapshot theo số lượng.';
COMMENT ON COLUMN "public"."meal_log_items"."carbs" IS 'Carb snapshot theo số lượng.';
COMMENT ON COLUMN "public"."meal_log_items"."sugar" IS 'Đường snapshot theo số lượng.';
COMMENT ON COLUMN "public"."meal_log_items"."protein" IS 'Protein snapshot theo số lượng.';
COMMENT ON COLUMN "public"."meal_log_items"."fat" IS 'Chất béo snapshot theo số lượng.';
COMMENT ON COLUMN "public"."meal_log_items"."gi_index" IS 'GI snapshot tại thời điểm ghi nhận.';
COMMENT ON COLUMN "public"."meal_log_items"."nutrition_snapshot" IS 'Payload dinh dưỡng gốc từ Food API.';
COMMENT ON COLUMN "public"."user_recommendations"."food_external_id" IS 'ID món ăn từ Food API nếu khuyến nghị món cụ thể.';
COMMENT ON COLUMN "public"."user_recommendations"."food_name" IS 'Tên món ăn khuyến nghị từ Food API.';
COMMENT ON COLUMN "public"."notifications"."alert_rule_id" IS 'Luật cảnh báo sinh thông báo nếu có.';
COMMENT ON COLUMN "public"."notifications"."ai_insight_id" IS 'Insight AI liên quan nếu có.';
COMMENT ON COLUMN "public"."periodic_reports"."achievements_json" IS 'Chi tiết thành tựu dạng JSON text.';
COMMENT ON COLUMN "public"."periodic_reports"."issues_json" IS 'Chi tiết vấn đề dạng JSON text.';
