from django.db import models


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    password = models.CharField(max_length=255)
    avatar = models.CharField(max_length=500, null=True, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "users"


class HealthProfile(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, db_column="user_id")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    waist_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    bmi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    bmr = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tdee = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    activity_factor_id = models.BigIntegerField(null=True, blank=True)
    activity_level = models.CharField(max_length=50, null=True, blank=True)
    smoking_status = models.CharField(max_length=50, null=True, blank=True)
    alcohol_status = models.CharField(max_length=50, null=True, blank=True)
    sleep_pattern = models.CharField(max_length=100, null=True, blank=True)
    medical_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "health_profiles"


class GlucoseMeasurement(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    meal_log_id = models.BigIntegerField(null=True, blank=True)
    glucose_value = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=20, default="mg/dL")
    measurement_context = models.CharField(max_length=50, default="FASTING")
    measured_at = models.DateTimeField()
    source_type = models.CharField(max_length=50, default="MANUAL")
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "glucose_measurements"


class HealthAssessment(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    health_profile = models.ForeignKey(HealthProfile, models.DO_NOTHING, db_column="health_profile_id", null=True, blank=True)
    diagnosis_session_id = models.BigIntegerField(null=True, blank=True)
    assessment_type = models.CharField(max_length=100)
    risk_level = models.CharField(max_length=50, null=True, blank=True)
    health_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    findings_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "health_assessments"


class RiskPrediction(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    assessment = models.ForeignKey(HealthAssessment, models.DO_NOTHING, db_column="assessment_id")
    diagnosis_session_id = models.BigIntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=100)
    prediction_type = models.CharField(max_length=100)
    risk_percent = models.DecimalField(max_digits=5, decimal_places=2)
    risk_band = models.CharField(max_length=50)
    high_risk_flag = models.BooleanField(default=False)
    feature_snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "risk_predictions"


class AiInsight(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    risk_prediction = models.ForeignKey(RiskPrediction, models.DO_NOTHING, db_column="risk_prediction_id", null=True, blank=True)
    assessment = models.ForeignKey(HealthAssessment, models.DO_NOTHING, db_column="assessment_id", null=True, blank=True)
    insight_type = models.CharField(max_length=100)
    explanation = models.TextField(null=True, blank=True)
    recommendation = models.TextField(null=True, blank=True)
    llm_model = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "ai_insights"


class PeriodicReport(models.Model):
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    period_type = models.CharField(max_length=20)
    period_start = models.DateField()
    period_end = models.DateField()
    avg_glucose = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    health_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    bmi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    weight_change = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    achievement_summary = models.TextField(null=True, blank=True)
    issue_summary = models.TextField(null=True, blank=True)
    achievements_json = models.JSONField(null=True, blank=True)
    issues_json = models.JSONField(null=True, blank=True)
    file_url = models.CharField(max_length=500, null=True, blank=True)
    generated_by = models.CharField(max_length=100, null=True, blank=True)
    generated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "periodic_reports"


class ReportExport(models.Model):
    report = models.ForeignKey(PeriodicReport, models.DO_NOTHING, db_column="report_id")
    user = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    export_format = models.CharField(max_length=20)
    file_url = models.CharField(max_length=500)
    exported_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "report_exports"
