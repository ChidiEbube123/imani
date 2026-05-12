from django.db import models
from projects.models import Project, ProjectMilestone
from monitoring.models import ProjectCompletionSnapshot


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('released', 'Released'),
        ('failed', 'Failed'),
        ('disputed', 'Disputed'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='payments')
    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.SET_NULL, null=True, blank=True)
    snapshot = models.ForeignKey(ProjectCompletionSnapshot, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    completion_at_trigger = models.FloatField()   # % completion when payment was triggered
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    blockchain_tx_hash = models.CharField(max_length=256, blank=True)  # ledger record
    reference = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payments'
    )

    def __str__(self):
        return f"Payment ₦{self.amount:,.2f} → {self.project.title} [{self.status}]"


class PaymentAuditLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=100)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.payment.reference} — {self.action}"
