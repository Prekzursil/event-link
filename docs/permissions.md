# Role-based permissions

The platform has three roles: **student**, **organizer**, and **admin**. Requests without a valid JWT receive `401 Unauthorized`. Requests with a JWT for the wrong role receive `403 Forbidden`.

## Matrix

| Action                              | Endpoint(s)                                                                   | Student   | Organizer            | Admin                |
| ----------------------------------- | ----------------------------------------------------------------------------- | --------- | -------------------- | -------------------- |
| Browse events                       | `GET /api/events`, `GET /api/events/{id}`                                     | ✅        | ✅                   | ✅                   |
| Register/unregister                 | `POST/DELETE /api/events/{id}/register`                                       | ✅ (self) | ❌                   | ❌                   |
| Resend registration email           | `POST /api/events/{id}/register/resend`                                       | ✅ (self) | ❌                   | ❌                   |
| Create/edit/delete event            | `POST/PUT/DELETE /api/events`                                                 | ❌        | ✅ (own events only) | ✅ (any event)       |
| Clone event                         | `POST /api/events/{id}/clone`                                                 | ❌        | ✅ (own events only) | ✅ (own events only) |
| View own created events             | `GET /api/organizer/events`                                                   | ❌        | ✅                   | ✅ (own events only) |
| View participants / mark attendance | `GET/PUT /api/organizer/events/{id}/participants`                             | ❌        | ✅ (owner only)      | ✅ (any event)       |
| Admin dashboard                     | `GET /api/admin/stats`, `GET/PATCH /api/admin/users`, `GET /api/admin/events` | ❌        | ❌                   | ✅                   |
| Recommendations                     | `GET /api/recommendations`                                                    | ✅        | ✅                   | ✅                   |
| My events feed                      | `GET /api/me/events`, `GET /api/me/calendar`                                  | ✅        | ❌                   | ❌                   |
| Favorites                           | `GET /api/me/favorites`, `POST/DELETE /api/events/{id}/favorite`              | ✅ (self) | ❌                   | ❌                   |
| Export my data                      | `GET /api/me/export`                                                          | ✅ (self) | ✅ (self)            | ✅ (self)            |
| Delete my account                   | `DELETE /api/me`                                                              | ✅ (self) | ✅ (self)            | ✅ (self)            |
| Health check                        | `GET /api/health`                                                             | ✅        | ✅                   | ✅                   |

Ownership rules apply where noted (organizers can only modify their own events and participants). Tests in `backend/tests/test_permissions.py` assert these behaviors.
