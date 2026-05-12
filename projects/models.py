from django.db import models
from django.contrib.auth.models import User


class Contractor(models.Model):
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    bank_account = models.CharField(max_length=50)
    registration_number = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company})"


class Project(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
    ]
    PROJECT_TYPES = [
        ('road', 'Road Construction'),
        ('bridge', 'Bridge'),
        ('school', 'School Building'),
        ('hospital', 'Hospital'),
        ('water', 'Water Infrastructure'),
        ('power', 'Power Infrastructure'),
        ('housing', 'Housing'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=300)
    project_type = models.CharField(max_length=50, choices=PROJECT_TYPES)
    description = models.TextField()
    contractor = models.ForeignKey(Contractor, on_delete=models.PROTECT, related_name='projects')
    location_name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    total_budget = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateField()
    expected_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completion_percentage = models.FloatField(default=0.0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    satellite_reference_image = models.ImageField(upload_to='satellite/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def amount_remaining(self):
        return self.total_budget - self.amount_paid

    def __str__(self):
        return self.title


class ProjectMilestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_percentage = models.FloatField()  # e.g. 25% = first milestone
    payment_percentage = models.FloatField()  # % of total budget unlocked at this milestone
    achieved = models.BooleanField(default=False)
    achieved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.project.title} - {self.title}"
