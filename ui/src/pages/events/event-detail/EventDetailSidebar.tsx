import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import type { EventDetail } from '@/types';
import {
  CalendarPlus,
  Copy,
  ExternalLink,
  EyeOff,
  Heart,
  Share2,
  SlidersHorizontal,
  User,
  UserX,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EventDetailTexts } from './shared';

type RegistrationActionsProps = Readonly<{
  event: EventDetail;
  isPast: boolean;
  isFull: boolean;
  isRegistering: boolean;
  isResendingEmail: boolean;
  t: EventDetailTexts;
  onRegister: () => void;
  onUnregister: () => void;
  onResendRegistrationEmail: () => void;
}>;

/** Render the registration controls for attendees based on seat and timing state. */
function RegistrationActions(props: RegistrationActionsProps) {
  const {
    event,
    isPast,
    isFull,
    isRegistering,
    isResendingEmail,
    t,
    onRegister,
    onUnregister,
    onResendRegistrationEmail,
  } = props;

  if (event.is_registered) {
    return (
      <>
        <div className="rounded-lg bg-green-50 p-4 text-center dark:bg-green-900/20">
          <p className="font-medium text-green-700 dark:text-green-400">{t.eventDetail.registeredOk}</p>
        </div>
        <Button
          variant="secondary"
          className="w-full"
          onClick={onResendRegistrationEmail}
          disabled={isResendingEmail}
        >
          {isResendingEmail ? t.eventDetail.resendingEmail : t.eventDetail.resendEmail}
        </Button>
        {!isPast && (
          <Button variant="outline" className="w-full" onClick={onUnregister} disabled={isRegistering}>
            {t.eventDetail.unregister}
          </Button>
        )}
      </>
    );
  }

  if (isPast) {
    return <p className="text-center text-muted-foreground">{t.eventDetail.eventEndedText}</p>;
  }

  if (isFull) {
    return <p className="text-center text-destructive">{t.eventDetail.eventFullText}</p>;
  }

  // skipcq: JS-0415 - the registration action group intentionally keeps auth and seat states together.
  return (
    <Button className="w-full" onClick={onRegister} disabled={isRegistering}>
      {isRegistering ? t.eventDetail.registering : t.eventDetail.register}
    </Button>
  );
}

type Props = Readonly<{
  event: EventDetail;
  isPast: boolean;
  isFull: boolean;
  isStudent: boolean;
  hideTagId: string;
  isRegistering: boolean;
  isResendingEmail: boolean;
  isFavoriting: boolean;
  isCloning: boolean;
  isHidingTag: boolean;
  isBlockingOrganizer: boolean;
  t: EventDetailTexts;
  onRegister: () => void;
  onUnregister: () => void;
  onResendRegistrationEmail: () => void;
  onFavorite: () => void;
  onShare: () => void;
  onExportCalendar: () => void;
  onClone: () => void;
  onHideTagIdChange: (value: string) => void;
  onHideTag: () => void;
  onBlockOrganizer: () => void;
}>;

/** Render the owner or attendee registration card at the top of the sidebar. */
function RegistrationPanel({
  event,
  isCloning,
  isFull,
  isPast,
  isRegistering,
  isResendingEmail,
  onClone,
  onRegister,
  onResendRegistrationEmail,
  onUnregister,
  t,
}: Pick<
  Props,
  | 'event'
  | 'isCloning'
  | 'isFull'
  | 'isPast'
  | 'isRegistering'
  | 'isResendingEmail'
  | 'onClone'
  | 'onRegister'
  | 'onResendRegistrationEmail'
  | 'onUnregister'
  | 't'
>) {
  const ownerActions = (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t.eventDetail.ownerNote}</p>
      <Button asChild className="w-full">
        <Link to={`/organizer/events/${event.id}/edit`}>{t.eventDetail.editEvent}</Link>
      </Button>
      <Button asChild variant="outline" className="w-full">
        <Link to={`/organizer/events/${event.id}/participants`}>
          {t.eventDetail.viewParticipants}
        </Link>
      </Button>
      <Button variant="outline" className="w-full" onClick={onClone} disabled={isCloning}>
        <Copy className="mr-2 h-4 w-4" />
        {isCloning ? t.eventDetail.cloning : t.eventDetail.cloneEvent}
      </Button>
    </div>
  );

  const attendeeActions = (
    <div className="space-y-4">
      <RegistrationActions
        event={event}
        isPast={isPast}
        isFull={isFull}
        isRegistering={isRegistering}
        isResendingEmail={isResendingEmail}
        t={t}
        onRegister={onRegister}
        onUnregister={onUnregister}
        onResendRegistrationEmail={onResendRegistrationEmail}
      />
      {typeof event.available_seats === 'number' && !isPast ? (
        <p className="text-center text-sm text-muted-foreground">
          {event.available_seats} {t.eventDetail.seatsAvailableSuffix}
        </p>
      ) : null}
    </div>
  );

  return (
    <div className="rounded-xl border p-6">
      <h3 className="mb-4 text-lg font-semibold">{t.eventDetail.registrationTitle}</h3>
      {event.is_owner ? ownerActions : attendeeActions}
    </div>
  );
}

/** Render the quick-share, favorite, and export controls under the registration card. */
function EventQuickActions({
  event,
  isFavoriting,
  onExportCalendar,
  onFavorite,
  onShare,
  t,
}: Pick<Props, 'event' | 'isFavoriting' | 'onExportCalendar' | 'onFavorite' | 'onShare' | 't'>) {
  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        size="icon"
        onClick={onFavorite}
        disabled={isFavoriting}
        className={cn(event.is_favorite && 'text-red-500')}
      >
        <Heart className={cn('h-4 w-4', event.is_favorite && 'fill-current')} />
      </Button>
      <Button variant="outline" size="icon" onClick={onShare}>
        <Share2 className="h-4 w-4" />
      </Button>
      <Button variant="outline" className="flex-1" onClick={onExportCalendar}>
        <CalendarPlus className="mr-2 h-4 w-4" />
        {t.eventDetail.addToCalendar}
      </Button>
    </div>
  );
}

/** Render the organizer identity card and profile link. */
function OrganizerPanel({ event, t }: Pick<Props, 'event' | 't'>) {
  return (
    <div className="rounded-xl border p-6">
      <h3 className="mb-4 text-lg font-semibold">{t.eventDetail.organizerTitle}</h3>
      <Link to={`/organizers/${event.owner_id}`} className="flex items-center gap-3 hover:underline">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
          <User className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="font-medium">{event.owner_name || t.eventDetail.organizerFallback}</p>
          <p className="text-sm text-muted-foreground">{t.eventDetail.viewProfile}</p>
        </div>
        <ExternalLink className="ml-auto h-4 w-4 text-muted-foreground" />
      </Link>
    </div>
  );
}

/** Render the hide-tag selector used in the personalization card. */
function HideTagControls({
  event,
  hideTagId,
  isHidingTag,
  onHideTag,
  onHideTagIdChange,
  t,
}: Pick<Props, 'event' | 'hideTagId' | 'isHidingTag' | 'onHideTag' | 'onHideTagIdChange' | 't'>) {
  if (event.tags.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <Label>{t.personalization.hideTagLabel}</Label>
      <div className="flex gap-2">
        <Select value={hideTagId} onValueChange={onHideTagIdChange} disabled={isHidingTag}>
          <SelectTrigger className="w-auto flex-1">
            <SelectValue placeholder={t.personalization.hideTagPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {event.tags.map((tag) => (
              <SelectItem key={tag.id} value={String(tag.id)}>
                {tag.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" variant="outline" onClick={onHideTag} disabled={!hideTagId || isHidingTag}>
          <EyeOff className="mr-2 h-4 w-4" />
          {isHidingTag ? t.personalization.hiding : t.personalization.hideTagAction}
        </Button>
      </div>
    </div>
  );
}

/** Render the student personalization card when recommendations or tags are present. */
function PersonalizationPanel({
  event,
  hideTagId,
  isBlockingOrganizer,
  isHidingTag,
  onBlockOrganizer,
  onHideTag,
  onHideTagIdChange,
  t,
}: Pick<
  Props,
  | 'event'
  | 'hideTagId'
  | 'isBlockingOrganizer'
  | 'isHidingTag'
  | 'onBlockOrganizer'
  | 'onHideTag'
  | 'onHideTagIdChange'
  | 't'
>) {
  return (
    <div className="rounded-xl border p-6">
      <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <SlidersHorizontal className="h-5 w-5" />
        {t.personalization.title}
      </h3>

      <p className="text-sm text-muted-foreground">
        {event.recommendation_reason || t.personalization.genericReason}
      </p>

      <Separator className="my-4" />

      <div className="space-y-4">
        <HideTagControls
          event={event}
          hideTagId={hideTagId}
          isHidingTag={isHidingTag}
          onHideTag={onHideTag}
          onHideTagIdChange={onHideTagIdChange}
          t={t}
        />

        <Button
          type="button"
          variant="outline"
          onClick={onBlockOrganizer}
          disabled={isBlockingOrganizer}
          className="w-full justify-start"
        >
          <UserX className="mr-2 h-4 w-4" />
          {isBlockingOrganizer ? t.personalization.blockingOrganizer : t.personalization.blockOrganizerAction}
        </Button>

        <Link to="/profile" className="text-sm text-primary hover:underline">
          {t.personalization.manageLink}
        </Link>
      </div>
    </div>
  );
}

/** Render the event-detail sidebar sections for registration, organizer metadata, and personalization. */
export function EventDetailSidebar({
  event,
  isPast,
  isFull,
  isStudent,
  hideTagId,
  isRegistering,
  isResendingEmail,
  isFavoriting,
  isCloning,
  isHidingTag,
  isBlockingOrganizer,
  t,
  onRegister,
  onUnregister,
  onResendRegistrationEmail,
  onFavorite,
  onShare,
  onExportCalendar,
  onClone,
  onHideTagIdChange,
  onHideTag,
  onBlockOrganizer,
}: Props) {
  return (
    <div className="lg:col-span-1">
      <div className="sticky top-24 space-y-6">
        <RegistrationPanel
          event={event}
          isCloning={isCloning}
          isFull={isFull}
          isPast={isPast}
          isRegistering={isRegistering}
          isResendingEmail={isResendingEmail}
          onClone={onClone}
          onRegister={onRegister}
          onResendRegistrationEmail={onResendRegistrationEmail}
          onUnregister={onUnregister}
          t={t}
        />

        <EventQuickActions
          event={event}
          isFavoriting={isFavoriting}
          onExportCalendar={onExportCalendar}
          onFavorite={onFavorite}
          onShare={onShare}
          t={t}
        />

        <OrganizerPanel event={event} t={t} />

        {isStudent && (event.recommendation_reason || event.tags.length > 0) ? (
          <PersonalizationPanel
            event={event}
            hideTagId={hideTagId}
            isBlockingOrganizer={isBlockingOrganizer}
            isHidingTag={isHidingTag}
            onBlockOrganizer={onBlockOrganizer}
            onHideTag={onHideTag}
            onHideTagIdChange={onHideTagIdChange}
            t={t}
          />
        ) : null}
      </div>
    </div>
  );
}
