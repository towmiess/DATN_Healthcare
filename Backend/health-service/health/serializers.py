from rest_framework import serializers


class DiagnosisPredictSerializer(serializers.Serializer):
    sex = serializers.IntegerField(required=False)
    age_years = serializers.FloatField(required=False)
    weight_kg = serializers.FloatField(required=False)
    height_cm = serializers.FloatField(required=False)
    bmi = serializers.FloatField(required=False)
    waist_cm = serializers.FloatField(required=False)
    hip_cm = serializers.FloatField(required=False)
    hba1c_percent = serializers.FloatField(required=False)
    fasting_glucose_mg_dl = serializers.FloatField(required=False)
    fasting_glucose_mmol_l = serializers.FloatField(required=False)
    insulin_uU_ml = serializers.FloatField(required=False)
    insulin_pmol_l = serializers.FloatField(required=False)
    fasting_hours = serializers.FloatField(required=False)
    fasting_minutes = serializers.FloatField(required=False)
    total_cholesterol_mg_dl = serializers.FloatField(required=False)
    total_cholesterol_mmol_l = serializers.FloatField(required=False)
    high_blood_pressure_history = serializers.IntegerField(required=False)
    systolic_bp_mean = serializers.FloatField(required=False)
    diastolic_bp_mean = serializers.FloatField(required=False)
    pulse_mean = serializers.FloatField(required=False)


class GoogleVisionOcrSerializer(serializers.Serializer):
    image_base64 = serializers.CharField()
    mime_type = serializers.CharField(required=False, default="image/jpeg")
    mode = serializers.ChoiceField(choices=["text", "document"], required=False, default="document")


class ClinicalBaselineExtractSerializer(GoogleVisionOcrSerializer):
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True)


class ReportExportSerializer(serializers.Serializer):
    report_id = serializers.IntegerField(required=False)
    period_type = serializers.ChoiceField(choices=["WEEKLY", "MONTHLY"], required=False, default="WEEKLY")
    export_format = serializers.ChoiceField(choices=["PDF", "CSV", "XLSX"], default="PDF")


class ReportDraftSerializer(serializers.Serializer):
    period_type = serializers.ChoiceField(choices=["WEEKLY", "MONTHLY"], default="WEEKLY")


class LabResultInputSerializer(serializers.Serializer):
    test_code = serializers.CharField(max_length=80)
    test_name = serializers.CharField(max_length=255)
    value = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit = serializers.CharField(max_length=50)
    canonical_value = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    canonical_unit = serializers.CharField(max_length=50, required=False, allow_blank=True)
    reference_min = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    reference_max = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    reference_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    abnormal_flag = serializers.CharField(max_length=20, required=False, allow_blank=True)
    confidence_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)


class ClinicalObservationInputSerializer(serializers.Serializer):
    observation_code = serializers.CharField(max_length=80)
    observation_name = serializers.CharField(max_length=255)
    value = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit = serializers.CharField(max_length=50)
    canonical_value = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    canonical_unit = serializers.CharField(max_length=50, required=False, allow_blank=True)
    reference_min = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    reference_max = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    reference_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    abnormal_flag = serializers.CharField(max_length=20, required=False, allow_blank=True)
    confidence_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)


class ClinicalBaselineSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    provider_name = serializers.CharField(max_length=255)
    sampled_at = serializers.DateTimeField()
    reported_at = serializers.DateTimeField(required=False, allow_null=True)
    confirmed = serializers.BooleanField()
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True)
    file_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    mime_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ocr_engine = serializers.CharField(max_length=100, required=False, allow_blank=True)
    raw_ocr_text = serializers.CharField(required=False, allow_blank=True)
    confidence_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    file_sha256 = serializers.CharField(max_length=64, required=False, allow_blank=True)
    image_base64 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    results = LabResultInputSerializer(many=True, allow_empty=True, required=False, default=list)
    observations = ClinicalObservationInputSerializer(many=True, allow_empty=True, required=False, default=list)

    def validate_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("Người dùng phải xác nhận kết quả trước khi lưu baseline.")
        return value

    def validate(self, attrs):
        if not attrs.get("results") and not attrs.get("observations"):
            raise serializers.ValidationError("Hồ sơ cần có ít nhất một chỉ số đã xác nhận.")
        return attrs
