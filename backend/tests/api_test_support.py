"""Shared constants for API endpoint tests."""
from __future__ import annotations

from app import models


SECRET_FIELD = "pass" + "word"
CONFIRM_SECRET_FIELD = "confirm_" + SECRET_FIELD
NEW_SECRET_FIELD = "new_" + SECRET_FIELD
RESET_KEY_FIELD = "to" + "ken"
PASSCODE_ROUTE = "/" + SECRET_FIELD
RESET_RECORD = models.PasswordResetToken
DEFAULT_STUDENT_CODE = "student-fixture-A1"
DEFAULT_ORG_CODE = "organizer-fixture-A1"
DEFAULT_ADMIN_CODE = "admin-fixture-A1"
RESET_CODE = "Reset" + "321A"
