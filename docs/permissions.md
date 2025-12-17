# Role-based permissions

The platform has two roles: **student** and **organizer**. Requests without a valid JWT receive `401 Unauthorized`. Requests with a JWT for the wrong role receive `403 Forbidden`.

## Matrix
| Action | Endpoint(s) | Student | Organizer |
| --- | --- | --- | --- |
| Browse events | `GET /api/events`, `GET /api/events/{id}` | ✅ | ✅ |
| Register/unregister | `POST/DELETE /api/events/{id}/register` | ✅ (self) | ❌ |
| Resend registration email | `POST /api/events/{id}/register/resend` | ✅ (self) | ❌ |
| Create/edit/delete event | `POST/PUT/DELETE /api/events` | ❌ | ✅ (own events only) |
| Clone event | `POST /api/events/{id}/clone` | ❌ | ✅ (own events only) |
| View own created events | `GET /api/organizer/events` | ❌ | ✅ |
| View participants / mark attendance | `GET/PUT /api/organizer/events/{id}/participants` | ❌ | ✅ (owner only) |
| Recommendations | `GET /api/recommendations` | ✅ | ✅ |
| My events feed | `GET /api/me/events`, `GET /api/me/calendar` | ✅ | ❌ |
| Favorites | `GET /api/me/favorites`, `POST/DELETE /api/events/{id}/favorite` | ✅ (self) | ❌ |
| Export my data | `GET /api/me/export` | ✅ (self) | ✅ (self) |
| Delete my account | `DELETE /api/me` | ✅ (self) | ✅ (self) |
| Upgrade to organizer | `POST /organizer/upgrade` | ✅ | ✅ (no-op) |
| Health check | `GET /api/health` | ✅ | ✅ |

Ownership rules apply where noted (organizers can only modify their own events and participants). Tests in `backend/tests/test_permissions.py` assert these behaviors.
