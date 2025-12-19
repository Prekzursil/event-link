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

## State machines

### Registration + confirmation email job

```mermaid
stateDiagram-v2
direction LR

[*] --> NotRegistered

NotRegistered --> Registered : POST /api/events/{event_id}/register
Registered --> Unregistered : DELETE /api/events/{event_id}/register
Unregistered --> Registered : POST /api/events/{event_id}/register

state Registered {
  [*] --> EmailJobQueued : enqueue send_email
  EmailJobQueued --> EmailJobRunning : worker locks job
  EmailJobRunning --> EmailJobSucceeded : SMTP ok / email_disabled
  EmailJobRunning --> EmailJobFailed : transient error
  EmailJobFailed --> EmailJobQueued : retry (attempts < max_attempts)
  EmailJobFailed --> EmailJobDead : attempts >= max_attempts
}
```

### Personalization controls (hidden tags + blocked organizers)

```mermaid
stateDiagram-v2
direction LR

state "Hidden tag (user_id, tag_id)" as HiddenTag {
  [*] --> Visible
  Visible --> Hidden : POST /api/me/personalization/hidden-tags/{tag_id}
  Hidden --> Visible : DELETE /api/me/personalization/hidden-tags/{tag_id}
}

state "Blocked organizer (user_id, organizer_id)" as BlockedOrganizer {
  [*] --> Unblocked
  Unblocked --> Blocked : POST /api/me/personalization/blocked-organizers/{organizer_id}
  Blocked --> Unblocked : DELETE /api/me/personalization/blocked-organizers/{organizer_id}
}
```
