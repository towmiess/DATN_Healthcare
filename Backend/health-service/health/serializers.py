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


class ReportExportSerializer(serializers.Serializer):
    report_id = serializers.IntegerField(required=False)
    export_format = serializers.ChoiceField(choices=["PDF", "CSV", "XLSX"], default="PDF")
