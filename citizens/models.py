from django.db import models
from django.contrib.auth.models import User


class CitizenProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='citizen_profile')
    phone = models.CharField(max_length=20, blank=True)
    state = models.CharField(max_length=100, blank=True)
    lga = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    total_submissions = models.IntegerField(default=0)
    accepted_submissions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def acceptance_rate(self):
        if self.total_submissions == 0:
            return 0
        return round((self.accepted_submissions / self.total_submissions) * 100, 1)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — Citizen"
