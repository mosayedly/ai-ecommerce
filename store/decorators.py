"""Reusable view decorators for the custom admin dashboard."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """Restrict a view to staff users only.

    Anonymous visitors are redirected to the login page; authenticated
    non-staff users receive a 403 (PermissionDenied).
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied("You must be a staff member to access this page.")
        return view_func(request, *args, **kwargs)

    return wrapper
