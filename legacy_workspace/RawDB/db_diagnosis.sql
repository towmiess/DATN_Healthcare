-- Migration add-on for diagnosis snapshot storage.
-- Apply this after RawDB/db.sql because it reuses existing enums and tables.

CREATE TABLE "public"."diagnosis_sessions" (
    "id" bigserial NOT NULL,
    "user_id" bigint NOT NULL,
    "input_source" source_type NOT NULL DEFAULT 'MANUAL',
    "ui_input_count" int NOT NULL DEFAULT 22,
    "filled_input_count" int NOT NULL DEFAULT 0,
    "raw_input_snapshot" jsonb NOT NULL,
    "normalized_feature_snapshot" jsonb,
    "ocr_engine" varchar(100),
    "ocr_raw_text" text,
    "confidence_score" numeric(5, 2),
    "input_schema_version" varchar(50) NOT NULL DEFAULT 'v1',
    "created_at" timestamp NOT NULL,
    "updated_at" timestamp NOT NULL,
    PRIMARY KEY ("id")
);

CREATE INDEX "idx_diagnosis_sessions_user_created_at" ON "public"."diagnosis_sessions" ("user_id", "created_at");
CREATE INDEX "idx_diagnosis_sessions_input_source" ON "public"."diagnosis_sessions" ("input_source");

ALTER TABLE "public"."diagnosis_sessions"
    ADD CONSTRAINT "chk_diagnosis_sessions_ui_input_count"
    CHECK ("ui_input_count" > 0 AND "filled_input_count" >= 0 AND "filled_input_count" <= "ui_input_count");

ALTER TABLE "public"."diagnosis_sessions"
    ADD CONSTRAINT "fk_diagnosis_sessions_user_id_users_id"
    FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id");

ALTER TABLE "public"."health_assessments"
    ADD CONSTRAINT "fk_health_assessments_diagnosis_session_id_diagnosis_sessions_id"
    FOREIGN KEY ("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions" ("id");

ALTER TABLE "public"."risk_predictions"
    ADD CONSTRAINT "fk_risk_predictions_diagnosis_session_id_diagnosis_sessions_id"
    FOREIGN KEY ("diagnosis_session_id") REFERENCES "public"."diagnosis_sessions" ("id");

COMMENT ON TABLE "public"."diagnosis_sessions" IS 'Snapshot of one diagnosis submission, including raw form input and normalized model payload.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."input_source" IS 'Input source: MANUAL, SCAN, or DEVICE_SYNC.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."ui_input_count" IS 'Number of fields exposed in the diagnosis UI.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."filled_input_count" IS 'Number of fields actually filled by the user.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."raw_input_snapshot" IS 'Raw snapshot of the diagnosis form input.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."normalized_feature_snapshot" IS 'Normalized feature payload sent to the model.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."ocr_raw_text" IS 'Raw OCR text if the diagnosis data came from an image.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."confidence_score" IS 'OCR or extraction confidence score, when available.';
COMMENT ON COLUMN "public"."diagnosis_sessions"."input_schema_version" IS 'Version of the diagnosis form schema.';
