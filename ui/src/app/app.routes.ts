import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { EventListComponent } from './event-list/event-list.component';
import { LoginComponent } from './login/login.component';
import { RegisterComponent } from './register/register.component';
import { EventDetailsComponent } from './event-details/event-details.component';
import { EventFormComponent } from './event-form/event-form.component';
import { OrganizerEventsComponent } from './organizer-events/organizer-events.component';
import { ParticipantsComponent } from './participants/participants.component';
import { MyEventsComponent } from './my-events/my-events.component';
import { ForbiddenComponent } from './pages/forbidden/forbidden.component';
import { NotFoundComponent } from './pages/not-found/not-found.component';
import { organizerGuard } from './guards/organizer.guard';
import { OrganizerUpgradeComponent } from './organizer-upgrade/organizer-upgrade.component';
import { publicOnlyGuard } from './guards/public-only.guard';

export const routes: Routes = [
  { path: '', component: EventListComponent },
  { path: 'login', component: LoginComponent, canActivate: [publicOnlyGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [publicOnlyGuard] },
  { path: 'organizer/upgrade', component: OrganizerUpgradeComponent, canActivate: [authGuard] },
  { path: 'events/:id', component: EventDetailsComponent },
  { path: 'events/:id/edit', component: EventFormComponent, canActivate: [organizerGuard] },
  { path: 'create-event', component: EventFormComponent, canActivate: [organizerGuard] },
  { path: 'organizer/events', component: OrganizerEventsComponent, canActivate: [organizerGuard] },
  { path: 'organizer/events/:id/participants', component: ParticipantsComponent, canActivate: [organizerGuard] },
  { path: 'my-events', component: MyEventsComponent, canActivate: [authGuard], data: { role: 'student' } },
  { path: 'forbidden', component: ForbiddenComponent },
  { path: '**', component: NotFoundComponent },
];
