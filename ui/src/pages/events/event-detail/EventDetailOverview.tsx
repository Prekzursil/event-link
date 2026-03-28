import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { EventDetail } from '@/types';
import type { ResolvedLanguage } from '@/lib/language';
import { Calendar, Clock, MapPin, Users } from 'lucide-react';
import { formatDate, formatTime } from '@/lib/utils';
import { getEventCategoryLabel } from '@/lib/eventCategories';
import { EVENT_DETAIL_FALLBACK_COVER_URL, type EventDetailTexts } from './shared';

type Props = Readonly<{
  event: EventDetail;
  isPast: boolean;
  isFull: boolean;
  language: ResolvedLanguage;
  t: EventDetailTexts;
}>;

function EventCover({
  event,
  isPast,
  isFull,
  t,
}: Pick<Props, 'event' | 'isPast' | 'isFull' | 't'>) {
  return (
    <div className="relative mb-6 aspect-video overflow-hidden rounded-xl bg-muted">
      {event.cover_url ? (
        <img
          src={event.cover_url}
          alt={event.title}
          className="h-full w-full object-cover"
          onError={(eventTarget) => {
            (eventTarget.target as HTMLImageElement).src = EVENT_DETAIL_FALLBACK_COVER_URL;
          }}
        />
      ) : (
        <div className="flex h-full items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
          <Calendar className="h-24 w-24 text-primary/40" />
        </div>
      )}

      <div className="absolute left-4 top-4 flex flex-wrap gap-2">
        {event.status === 'draft' && <Badge variant="secondary">{t.eventDetail.draft}</Badge>}
        {isPast && <Badge variant="secondary">{t.eventDetail.ended}</Badge>}
        {isFull && !isPast && <Badge variant="destructive">{t.eventDetail.full}</Badge>}
      </div>
    </div>
  );
}

function EventHeading({ event, language }: Pick<Props, 'event' | 'language'>) {
  return (
    <div className="mb-6">
      {event.category && (
        <Badge variant="outline" className="mb-2">
          {getEventCategoryLabel(event.category, language)}
        </Badge>
      )}
      <h1 className="text-3xl font-bold">{event.title}</h1>
    </div>
  );
}

function EventMetaGrid({ event, language, t }: Pick<Props, 'event' | 'language' | 't'>) {
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2">
      <div className="flex items-center gap-3 rounded-lg border p-4">
        <Calendar className="h-5 w-5 text-primary" />
        <div>
          <p className="text-sm text-muted-foreground">{t.eventDetail.dateLabel}</p>
          <p className="font-medium">{formatDate(event.start_time, language)}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border p-4">
        <Clock className="h-5 w-5 text-primary" />
        <div>
          <p className="text-sm text-muted-foreground">{t.eventDetail.timeLabel}</p>
          <p className="font-medium">
            {formatTime(event.start_time, language)}
            {event.end_time && ` - ${formatTime(event.end_time, language)}`}
          </p>
        </div>
      </div>
      {(event.city || event.location) && (
        <div className="flex items-center gap-3 rounded-lg border p-4">
          <MapPin className="h-5 w-5 text-primary" />
          <div>
            <p className="text-sm text-muted-foreground">{t.eventDetail.locationLabel}</p>
            <p className="font-medium">{[event.city, event.location].filter(Boolean).join(' • ')}</p>
          </div>
        </div>
      )}
      <div className="flex items-center gap-3 rounded-lg border p-4">
        <Users className="h-5 w-5 text-primary" />
        <div>
          <p className="text-sm text-muted-foreground">{t.eventDetail.participantsLabel}</p>
          <p className="font-medium">
            {event.seats_taken}
            {event.max_seats && ` / ${event.max_seats}`} {t.eventDetail.seatsTakenSuffix}
          </p>
        </div>
      </div>
    </div>
  );
}

function EventDescription({ event, t }: Pick<Props, 'event' | 't'>) {
  return (
    <div className="mb-6">
      <h2 className="mb-4 text-xl font-semibold">{t.eventDetail.descriptionTitle}</h2>
      <div className="prose prose-neutral dark:prose-invert max-w-none">
        {event.description ? (
          <p className="whitespace-pre-wrap">{event.description}</p>
        ) : (
          <p className="text-muted-foreground">{t.eventDetail.descriptionEmpty}</p>
        )}
      </div>
    </div>
  );
}

function EventTags({ event, t }: Pick<Props, 'event' | 't'>) {
  if (event.tags.length === 0) {
    return null;
  }

  return (
    <div className="mb-6">
      <h2 className="mb-4 text-xl font-semibold">{t.eventDetail.tagsTitle}</h2>
      <div className="flex flex-wrap gap-2">
        {event.tags.map((tag) => (
          <Badge key={tag.id} variant="secondary">
            {tag.name}
          </Badge>
        ))}
      </div>
    </div>
  );
}

export function EventDetailOverview({ event, isPast, isFull, language, t }: Props) {
  return (
    <div className="lg:col-span-2">
      <EventCover event={event} isPast={isPast} isFull={isFull} t={t} />
      <EventHeading event={event} language={language} />
      <EventMetaGrid event={event} language={language} t={t} />
      <Separator className="my-6" />
      <EventDescription event={event} t={t} />
      <EventTags event={event} t={t} />
    </div>
  );
}
