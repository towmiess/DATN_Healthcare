from django.urls import path

from .views import (
    DiagnosisPredictView,
    DiagnosisSnapshotView,
    GoogleVisionOcrView,
    HealthCheckView,
    ReportDashboardView,
    ReportExportView,
)


urlpatterns = [
    path("health", HealthCheckView.as_view(), name="health-check"),
    path("diagnosis/predict/", DiagnosisPredictView.as_view(), name="diagnosis-predict"),
    path("diagnosis/profile/", DiagnosisSnapshotView.as_view(), name="diagnosis-profile"),
    path("reports/dashboard/", ReportDashboardView.as_view(), name="reports-dashboard"),
    path("reports/export/", ReportExportView.as_view(), name="reports-export"),
    path("ocr/google-vision/", GoogleVisionOcrView.as_view(), name="ocr-google-vision"),
]
