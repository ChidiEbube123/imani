from django.contrib import admin
from .models import MediaEvidence, AIAnalysisResult, ProjectCompletionSnapshot, SiteCamera

@admin.register(SiteCamera)
class SiteCameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'is_active', 'last_capture']
    list_filter = ['is_active']

@admin.register(MediaEvidence)
class MediaEvidenceAdmin(admin.ModelAdmin):
    list_display = ['project', 'source', 'status', 'uploaded_by', 'uploaded_at', 'is_flagged']
    list_filter = ['source', 'status', 'is_flagged']
    search_fields = ['project__title', 'uploader_name']
    actions = ['mark_verified', 'mark_rejected', 'flag_evidence']

    def mark_verified(self, request, queryset):
        queryset.update(status='verified')
    def mark_rejected(self, request, queryset):
        queryset.update(status='rejected')
    def flag_evidence(self, request, queryset):
        queryset.update(is_flagged=True)

@admin.register(AIAnalysisResult)
class AIAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['evidence', 'completion_score', 'confidence', 'analyzed_at']
    readonly_fields = ['raw_detections', 'detected_elements', 'stage_scores']
