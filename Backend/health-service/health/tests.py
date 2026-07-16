from django.test import SimpleTestCase

from health.clinical_baseline import extract_clinical_baseline
from health.serializers import ClinicalBaselineSerializer
from health.services import normalize_features


class UnitConversionTests(SimpleTestCase):
    def test_insulin_is_derived_in_both_directions(self):
        from_uu = normalize_features({"insulin_uU_ml": 8.2})
        from_pmol = normalize_features({"insulin_pmol_l": 49.2})

        self.assertEqual(from_uu["insulin_pmol_l"], 49.2)
        self.assertEqual(from_pmol["insulin_uU_ml"], 8.2)

    def test_cholesterol_is_derived_in_both_directions(self):
        from_mg = normalize_features({"total_cholesterol_mg_dl": 190})
        from_mmol = normalize_features({"total_cholesterol_mmol_l": 4.91})

        self.assertEqual(from_mg["total_cholesterol_mmol_l"], 4.91)
        self.assertAlmostEqual(from_mmol["total_cholesterol_mg_dl"], 189.87, places=2)


class ClinicalBaselineSerializerTests(SimpleTestCase):
    def baseline_payload(self, confirmed):
        return {
            "provider_name": "Bệnh viện kiểm thử",
            "sampled_at": "2026-07-11T08:00:00+07:00",
            "confirmed": confirmed,
            "results": [
                {
                    "test_code": "HBA1C",
                    "test_name": "HbA1c",
                    "value": "5.7",
                    "unit": "%",
                }
            ],
        }

    def test_user_confirmation_is_required(self):
        serializer = ClinicalBaselineSerializer(data=self.baseline_payload(False))

        self.assertFalse(serializer.is_valid())
        self.assertIn("confirmed", serializer.errors)

    def test_confirmed_baseline_is_valid(self):
        serializer = ClinicalBaselineSerializer(data=self.baseline_payload(True))

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_observation_only_baseline_is_valid(self):
        payload = {
            "provider_name": "Cơ sở kiểm thử",
            "sampled_at": "2026-07-11T08:00:00+07:00",
            "confirmed": True,
            "observations": [
                {
                    "observation_code": "WEIGHT_KG",
                    "observation_name": "Cân nặng",
                    "value": "70.5",
                    "unit": "kg",
                }
            ],
        }
        serializer = ClinicalBaselineSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)


class ClinicalBaselineExtractionTests(SimpleTestCase):
    def test_extracts_supported_values_from_vietnamese_lab_report(self):
        text = """
        BỆNH VIỆN ĐA KHOA MINH TÂM
        Giới tính: Nữ | Tuổi: 45
        Ngày lấy mẫu: 08/07/2026
        Ngày trả kết quả: 09/07/2026
        Chiều cao 162 cm
        Cân nặng 70.5 kg
        BMI 26.86 kg/m2 18.5-22.9
        Vòng bụng 88 cm <80
        Huyết áp tâm thu 118 mmHg 90-120
        Huyết áp tâm trương
        60-80
        76
        mmHg
        Mạch 72 bpm 60-100
        Glucose máu đói 105 mg/dL 70-99
        HbA1c 5.7 % <5.7
        Cholesterol toàn phần 190 mg/dL <200
        Insulin máu đói 8.2 uU/mL 2.6-24.9
        """

        extracted = extract_clinical_baseline(text)
        observations = {
            item["observation_code"]: item["value"] for item in extracted["observations"]
        }
        results = {item["test_code"]: item["value"] for item in extracted["results"]}

        self.assertEqual(extracted["metadata"]["sex"], 2)
        self.assertEqual(extracted["metadata"]["age_years"], 45)
        self.assertEqual(observations["HEIGHT_CM"], 162)
        self.assertEqual(observations["SYSTOLIC_BP"], 118)
        self.assertEqual(observations["DIASTOLIC_BP"], 76)
        self.assertEqual(results["FASTING_GLUCOSE"], 105)
        self.assertEqual(results["HBA1C"], 5.7)
