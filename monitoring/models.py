from django.db import models
from django.contrib.auth.models import User
from projects.models import Project


class MediaEvidence(models.Model):
    SOURCE_CHOICES = [
        ('satellite', 'Satellite Image'),
        ('camera_gov', 'Government Camera'),
        ('camera_crowd', 'Crowdsourced Camera'),
        ('drone', 'Drone Footage'),
        ('document', 'Document'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Analysis'),
        ('analyzed', 'Analyzed'),
        ('rejected', 'Rejected'),
        ('verified', 'Verified'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='evidence')
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    image = models.ImageField(upload_to='evidence/%Y/%m/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploader_name = models.CharField(max_length=100, blank=True)  # for crowdsourced
    uploader_phone = models.CharField(max_length=20, blank=True)
    gps_lat = models.FloatField(null=True, blank=True)
    gps_lng = models.FloatField(null=True, blank=True)
    captured_at = models.DateTimeField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.project.title} - {self.source} ({self.captured_at.date()})"


class AIAnalysisResult(models.Model):
    evidence = models.OneToOneField(MediaEvidence, on_delete=models.CASCADE, related_name='analysis')
    raw_detections = models.JSONField(default=list)   # YOLO bounding boxes & labels
    detected_elements = models.JSONField(default=dict) # structured construction elements
    completion_score = models.FloatField()             # 0–100
    confidence = models.FloatField()                   # model confidence 0–1
    stage_scores = models.JSONField(default=dict)      # per-stage breakdown
    analysis_notes = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=50, default='yolov3-construction-mvp')

    def __str__(self):
        return f"Analysis for {self.evidence} — {self.completion_score:.1f}%"


class ProjectCompletionSnapshot(models.Model):
    """Aggregated completion score at a point in time."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='snapshots')
    snapshot_date = models.DateTimeField(auto_now_add=True)
    completion_percentage = models.FloatField()
    evidence_count = models.IntegerField()
    method = models.CharField(max_length=100, default='weighted_average')
    notes = models.TextField(blank=True)
    triggered_payment = models.BooleanField(default=False)

    class Meta:
        ordering = ['-snapshot_date']

    def __str__(self):
        return f"{self.project.title} @ {self.completion_percentage:.1f}% ({self.snapshot_date.date()})"
