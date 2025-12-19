# Mermaid UML diagrams

This document contains high-level Mermaid UML diagrams for EventLink (backend domain + core flows).

## Backend domain (SQLAlchemy models)

```mermaid
classDiagram
direction LR

class UserRole {
  <<enumeration>>
  student
  organizator
  admin
}

class User {
  +int id
  +string email
  +UserRole role
  +bool is_active
  +datetime created_at
  +datetime last_seen_at
  +string theme_preference
  +string language_preference
  +string city
  +string university
  +string faculty
  +string study_level
  +int study_year
  +bool email_digest_enabled
  +bool email_filling_fast_enabled
}

class Event {
  +int id
  +string title
  +string category
  +datetime start_time
  +datetime end_time
  +string location
  +string city
  +int max_seats
  +string status
  +datetime publish_at
  +float moderation_score
  +string moderation_status
  +datetime deleted_at
}

class Tag {
  +int id
  +string name
}

class Registration {
  +int id
  +int user_id
  +int event_id
  +datetime registration_time
  +bool attended
  +datetime deleted_at
}

class FavoriteEvent {
  +int id
  +int user_id
  +int event_id
  +datetime created_at
}

class PasswordResetToken {
  +int id
  +int user_id
  +string token
  +datetime expires_at
  +bool used
}

class BackgroundJob {
  +int id
  +string job_type
  +string dedupe_key
  +json payload
  +string status
  +int attempts
  +datetime run_at
  +datetime locked_at
  +string locked_by
}

class NotificationDelivery {
  +int id
  +string notification_type
  +int user_id
  +int event_id
  +datetime sent_at
  +json meta
}

class AuditLog {
  +int id
  +string entity_type
  +int entity_id
  +string action
  +int actor_user_id
  +datetime created_at
  +json meta
}

class UserRecommendation {
  +int id
  +int user_id
  +int event_id
  +float score
  +int rank
  +string model_version
  +datetime generated_at
  +string reason
}

class RecommenderModel {
  +int id
  +string model_version
  +json feature_names
  +json weights
  +bool is_active
  +datetime created_at
}

class EventInteraction {
  +int id
  +int user_id
  +int event_id
  +string interaction_type
  +datetime occurred_at
  +json meta
}

class UserImplicitInterestTag {
  +int id
  +int user_id
  +int tag_id
  +float score
  +datetime last_seen_at
}

class UserImplicitInterestCategory {
  +int id
  +int user_id
  +string category
  +float score
  +datetime last_seen_at
}

class UserImplicitInterestCity {
  +int id
  +int user_id
  +string city
  +float score
  +datetime last_seen_at
}

User --> UserRole : role

User "1" --> "0..*" Event : owns
User "1" --> "0..*" Registration : registrations
Event "1" --> "0..*" Registration : registrations

User "1" --> "0..*" FavoriteEvent : favorites
Event "1" --> "0..*" FavoriteEvent : favorited_by

User "1" --> "0..*" PasswordResetToken : password_resets

Event "0..*" -- "0..*" Tag : tags
User "0..*" -- "0..*" Tag : interest_tags
User "0..*" -- "0..*" Tag : hidden_tags
User "0..*" -- "0..*" User : blocks_organizers

User "1" --> "0..*" NotificationDelivery : notifications
Event "0..1" --> "0..*" NotificationDelivery : notifications

User "0..1" --> "0..*" AuditLog : actor

User "1" --> "0..*" UserRecommendation : recommendations
Event "1" --> "0..*" UserRecommendation : recommended_event
RecommenderModel "1" <-- "0..*" UserRecommendation : model_version

User "0..1" --> "0..*" EventInteraction : interactions
Event "0..1" --> "0..*" EventInteraction : interactions

User "1" --> "0..*" UserImplicitInterestTag : implicit_tag
Tag "1" --> "0..*" UserImplicitInterestTag : tag
User "1" --> "0..*" UserImplicitInterestCategory : implicit_category
User "1" --> "0..*" UserImplicitInterestCity : implicit_city

Event "0..1" --> User : deleted_by
Registration "0..1" --> User : deleted_by
Event "0..1" --> User : moderation_reviewed_by
```

## Communication diagram (core components + key messages)

```mermaid
flowchart LR
  Student([Student])
  Organizer([Organizer])
  Admin([Admin])

  UI[UI (React/Vite)]
  API[Backend API (FastAPI)]
  DB[(Postgres)]
  Worker[Worker (task queue)]
  SMTP[(SMTP provider)]

  Student -->|1. Browse / register / personalize| UI
  Organizer -->|2. Create events / manage participants| UI
  Admin -->|3. Moderate + manage users| UI

  UI -->|4. REST calls (JWT)| API
  API -->|5. Query / write| DB
  API -->|6. Enqueue BackgroundJob (send_email, digests, alerts)| DB

  Worker -->|7. Poll + lock queued jobs| DB
  Worker -->|8. Deliver outbound email| SMTP
  Worker -->|9. Persist delivery result| DB
```

## Interaction overview diagram (student discovery + registration + personalization)

```mermaid
flowchart TB
  Start([Start]) --> Browse[Browse events list]
  Browse --> Open[Open event details]

  Open --> Decide{Choose action}

  Decide -->|Hide tag| HideTag[POST /api/me/personalization/hidden-tags/{tag_id}]
  Decide -->|Block organizer| BlockOrg[POST /api/me/personalization/blocked-organizers/{organizer_id}]
  HideTag --> Refresh[Reload events list (filters applied)]
  BlockOrg --> Refresh

  Decide -->|Register| Register[POST /api/events/{event_id}/register]
  Register --> Enqueue[Enqueue send_email BackgroundJob]
  Enqueue --> Async[Worker delivers email (async)]

  Refresh --> Done([Done])
  Async --> Done
```

## Timing diagram (registration + background email confirmation)

```mermaid
gantt
title Registration + email confirmation (relative timing)
dateFormat  YYYY-MM-DD
axisFormat  %Y-%m-%d

section Student
Click "Register"                   :a1, 2025-01-01, 1d

section UI
POST /api/events/{id}/register      :a2, after a1, 1d
Render success + button state       :a3, after a2, 1d

section API
Validate + seat availability        :a4, after a2, 1d
Insert registration                 :a5, after a4, 1d
Insert background_jobs(send_email)  :a6, after a5, 1d

section Worker
Poll background_jobs queue          :a7, after a6, 1d
Send confirmation email             :a8, after a7, 1d
Mark job succeeded/failed           :a9, after a8, 1d
```
