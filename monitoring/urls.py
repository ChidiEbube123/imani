from django.urls import path
from . import views

urlpatterns = [
    path('project/<int:project_id>/evidence/', views.evidence_list, name='evidence_list'),
    path('project/<int:project_id>/upload/', views.upload_evidence, name='upload_evidence'),
    path('api/evidence/<int:evidence_id>/analysis/', views.analysis_api, name='analysis_api'),
    path('api/evidence/<int:evidence_id>/reanalyse/', views.reanalyse, name='reanalyse'),
]
