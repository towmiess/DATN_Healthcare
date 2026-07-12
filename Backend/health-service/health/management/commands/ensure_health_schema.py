from django.core.management.base import BaseCommand
from django.db import connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS report_drafts (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    period_type varchar(20) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    UNIQUE (user_id, period_type, period_start, period_end)
);
CREATE TABLE IF NOT EXISTS diagnosis_sessions (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    session_type varchar(50) NOT NULL DEFAULT 'DIAGNOSIS',
    source_type varchar(50) NOT NULL DEFAULT 'MANUAL',
    sample_collected_at timestamp,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
);
CREATE TABLE IF NOT EXISTS clinical_documents (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    diagnosis_session_id bigint REFERENCES diagnosis_sessions(id),
    document_type varchar(50) NOT NULL DEFAULT 'LAB_REPORT',
    original_filename varchar(255),
    file_url varchar(500),
    mime_type varchar(100),
    provider_name varchar(255),
    sample_collected_at timestamp,
    ocr_engine varchar(100),
    raw_ocr_text text,
    confidence_score numeric(5, 2),
    verification_status varchar(30) NOT NULL DEFAULT 'REVIEW_REQUIRED',
    file_sha256 varchar(64),
    created_at timestamp NOT NULL,
    verified_at timestamp
);
CREATE TABLE IF NOT EXISTS lab_panels (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    clinical_document_id bigint REFERENCES clinical_documents(id),
    diagnosis_session_id bigint REFERENCES diagnosis_sessions(id),
    provider_name varchar(255),
    sampled_at timestamp NOT NULL,
    reported_at timestamp,
    status varchar(30) NOT NULL DEFAULT 'VERIFIED',
    created_at timestamp NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_results (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    lab_panel_id bigint NOT NULL REFERENCES lab_panels(id),
    test_code varchar(80) NOT NULL,
    test_name varchar(255) NOT NULL,
    value numeric(14, 4) NOT NULL,
    unit varchar(50) NOT NULL,
    canonical_value numeric(14, 4),
    canonical_unit varchar(50),
    reference_min numeric(14, 4),
    reference_max numeric(14, 4),
    reference_text varchar(255),
    abnormal_flag varchar(20),
    source_type varchar(50) NOT NULL DEFAULT 'HOSPITAL_LAB',
    confidence_score numeric(5, 2),
    is_verified boolean NOT NULL DEFAULT false,
    observed_at timestamp NOT NULL,
    created_at timestamp NOT NULL
);
CREATE TABLE IF NOT EXISTS clinical_observations (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    diagnosis_session_id bigint NOT NULL REFERENCES diagnosis_sessions(id),
    clinical_document_id bigint REFERENCES clinical_documents(id),
    observation_code varchar(80) NOT NULL,
    observation_name varchar(255) NOT NULL,
    value numeric(14, 4) NOT NULL,
    unit varchar(50) NOT NULL,
    canonical_value numeric(14, 4),
    canonical_unit varchar(50),
    reference_min numeric(14, 4),
    reference_max numeric(14, 4),
    reference_text varchar(255),
    abnormal_flag varchar(20),
    source_type varchar(50) NOT NULL DEFAULT 'HOSPITAL_RECORD',
    confidence_score numeric(5, 2),
    is_verified boolean NOT NULL DEFAULT false,
    observed_at timestamp NOT NULL,
    created_at timestamp NOT NULL
);
CREATE TABLE IF NOT EXISTS clinical_baselines (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    diagnosis_session_id bigint NOT NULL UNIQUE REFERENCES diagnosis_sessions(id),
    label varchar(255) NOT NULL,
    effective_at timestamp NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    supersedes_baseline_id bigint REFERENCES clinical_baselines(id),
    created_at timestamp NOT NULL,
    archived_at timestamp
);
ALTER TABLE diagnosis_sessions ADD COLUMN IF NOT EXISTS baseline_id bigint;
ALTER TABLE lab_results ADD COLUMN IF NOT EXISTS canonical_value numeric(14, 4);
ALTER TABLE lab_results ADD COLUMN IF NOT EXISTS canonical_unit varchar(50);
DO $$ BEGIN
    ALTER TABLE diagnosis_sessions
        ADD CONSTRAINT fk_diagnosis_sessions_baseline_id
        FOREIGN KEY (baseline_id) REFERENCES clinical_baselines(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_report_drafts_user_period
    ON report_drafts (user_id, period_type, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_diagnosis_sessions_user_created_at
    ON diagnosis_sessions (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_clinical_documents_user_created_at
    ON clinical_documents (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_lab_panels_user_sampled_at
    ON lab_panels (user_id, sampled_at);
CREATE INDEX IF NOT EXISTS idx_lab_results_user_test_observed
    ON lab_results (user_id, test_code, observed_at);
CREATE INDEX IF NOT EXISTS idx_clinical_observations_user_code_observed
    ON clinical_observations (user_id, observation_code, observed_at);
CREATE INDEX IF NOT EXISTS idx_clinical_baselines_user_effective
    ON clinical_baselines (user_id, effective_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_baselines_active_user
    ON clinical_baselines (user_id) WHERE status = 'ACTIVE';
"""


class Command(BaseCommand):
    help = "Creates additive health-service tables for report drafts and clinical baselines."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)
        self.stdout.write(self.style.SUCCESS("Health-service schema extensions are ready."))
