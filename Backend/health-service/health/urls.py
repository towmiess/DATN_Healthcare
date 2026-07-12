from django.urls import path

from .views import (
    DiagnosisPredictView,
    DiagnosisSnapshotView,
    ClinicalBaselineActiveView,
    ClinicalBaselineExtractView,
    ClinicalBaselineListCreateView,
    GoogleVisionOcrView,
    GoogleVisionOcrStatusView,
    HealthCheckView,
    ReportDashboardView,
    ReportDraftView,
    ReportExportView,
)


urlpatterns = [
    path("health", HealthCheckView.as_view(), name="health-check"),
    path("diagnosis/predict/", DiagnosisPredictView.as_view(), name="diagnosis-predict"),
    path("diagnosis/profile/", DiagnosisSnapshotView.as_view(), name="diagnosis-profile"),
    path("reports/dashboard/", ReportDashboardView.as_view(), name="reports-dashboard"),
    path("reports/export/", ReportExportView.as_view(), name="reports-export"),
    path("reports/draft/", ReportDraftView.as_view(), name="reports-draft"),
    path("clinical/baselines/", ClinicalBaselineListCreateView.as_view(), name="clinical-baselines"),
    path("clinical/baselines/active/", ClinicalBaselineActiveView.as_view(), name="clinical-baseline-active"),
    path("clinical/baselines/extract/", ClinicalBaselineExtractView.as_view(), name="clinical-baseline-extract"),
    path("ocr/status/", GoogleVisionOcrStatusView.as_view(), name="ocr-status"),
    path("ocr/google-vision/", GoogleVisionOcrView.as_view(), name="ocr-google-vision"),
]
