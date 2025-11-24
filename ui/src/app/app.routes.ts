import { Routes } from '@angular/router';
import { EventListComponent } from './components/event-list.component';
import { LoginComponent } from './components/login.component';
import { RegisterComponent } from './components/register.component';
import { EventDetailComponent } from './components/event-detail.component';
import { EventFormComponent } from './components/event-form.component';
import { MyEventsComponent } from './components/my-events.component';
import { OrganizerEventsComponent } from './components/organizer-events.component';
import { ParticipantsComponent } from './components/participants.component';

export const routes: Routes = [
  { path: '', component: EventListComponent },
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'events/:id', component: EventDetailComponent },
  { path: 'create', component: EventFormComponent },
  { path: 'edit/:id', component: EventFormComponent },
  { path: 'my-events', component: MyEventsComponent },
  { path: 'organizer/events', component: OrganizerEventsComponent },
  { path: 'events/:id/participants', component: ParticipantsComponent },
];
