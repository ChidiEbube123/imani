from django.contrib import admin
from .models import CitizenProfile

@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'state', 'lga', 'total_submissions', 'accepted_submissions', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'state']
    search_fields = ['user__username', 'user__email', 'state', 'lga']
    actions = ['verify_citizens']

    def verify_citizens(self, request, queryset):
        queryset.update(is_verified=True)
    verify_citizens.short_description = 'Mark selected citizens as verified'
