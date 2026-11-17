from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        SOFT_DELETE = "SOFT_DELETE", "Soft delete"
        EXPORT = "EXPORT", "Export"
        IMPORT = "IMPORT", "Import"
        VIEW_CROSS_CENTRE = "VIEW_CROSS_CENTRE", "Cross-centre view"
        ACCESS_DENIED = "ACCESS_DENIED", "Access denied"
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"
        LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
        DATA_REQUEST = "DATA_REQUEST", "Data subject request"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    centre = models.ForeignKey("centres.Centre", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.timestamp:%d-%m-%Y %H:%M} {self.user} {self.action} {self.object_repr}"
