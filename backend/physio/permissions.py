"""
Role-based access control for PhysioAI endpoints.

Role hierarchy (most privileged first):
    admin      → full access everywhere
    physio     → full physio read/write; audit logs
    coach      → read risk summaries, overview, injuries (no edit)
    nutritionist → read overview only (no medical detail)
    scout      → no physio access
"""
from rest_framework.permissions import BasePermission


class IsAdminOrPhysio(BasePermission):
    """Full read/write access: admin and physio only."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in ('admin', 'physio') or user.is_superuser


class IsCoachOrAbove(BasePermission):
    """Read-only physio data: admin, physio, coach."""
    ALLOWED = ('admin', 'physio', 'coach')

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in self.ALLOWED or user.is_superuser


class IsPhysioReadOnly(BasePermission):
    """Coach gets GET; physio/admin get full access."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role in ('admin', 'physio') or user.is_superuser:
            return True
        if user.role == 'coach' and request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return False


class IsAdminOnly(BasePermission):
    """Admin only (e.g. CSV import, audit log)."""
    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated and (user.role == 'admin' or user.is_superuser)
