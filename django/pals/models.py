from django.db import models


class LiveSyncState(models.Model):
    """The single published/requested state for the live Palworld save."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_fingerprint = models.TextField(blank=True)
    requested = models.BooleanField(default=False)
    refreshing = models.BooleanField(default=False)
    last_refresh_at = models.DateTimeField(null=True, blank=True)
    last_result = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "live sync state"
        verbose_name_plural = "live sync state"
