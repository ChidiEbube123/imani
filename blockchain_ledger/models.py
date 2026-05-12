from django.db import models


class Block(models.Model):
    index = models.IntegerField(unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()
    previous_hash = models.CharField(max_length=256)
    hash = models.CharField(max_length=256, unique=True)
    nonce = models.IntegerField(default=0)

    class Meta:
        ordering = ['index']

    def __str__(self):
        return f"Block #{self.index} — {self.hash[:16]}..."
