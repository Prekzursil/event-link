import { Link } from 'react-router-dom';
import type { Event } from '@/types';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar, Clock, MapPin, Users, Heart, Sparkles, Pencil } from 'lucide-react';
import { formatDate, formatTime, cn } from '@/lib/utils';
import { useI18n } from '@/contexts/LanguageContext';
import { getEventCategoryLabel } from '@/lib/eventCategories';

export interface EventCardProps {
  event: Event;
  onFavoriteToggle?: (eventId: number, isFavorite: boolean) => void;
  isFavorite?: boolean;
  showRecommendation?: boolean;
  isPast?: boolean;
  showEditButton?: boolean;
  onEventClick?: (eventId: number) => void;
}

export function EventCard({
  event,
  onFavoriteToggle,
  isFavorite = false,
  showRecommendation = false,
  isPast = false,
  showEditButton = false,
  onEventClick,
}: EventCardProps) {
  const { language, t } = useI18n();
  const availableSeats = event.max_seats ? event.max_seats - event.seats_taken : null;
  const isFull = availableSeats !== null && availableSeats <= 0;

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onFavoriteToggle?.(event.id, !isFavorite);
  };

  return (
    <Card className={cn(
      "group overflow-hidden transition-all hover:shadow-lg",
      isPast && "opacity-75"
    )}>
      <Link to={`/events/${event.id}`} onClick={() => onEventClick?.(event.id)}>
        {/* Cover Image */}
        <div className="relative aspect-video overflow-hidden bg-muted">
          {event.cover_url ? (
            <img
              src={event.cover_url}
              alt={event.title}
              className={cn(
                "h-full w-full object-cover transition-transform group-hover:scale-105",
                isPast && "grayscale-[30%]"
              )}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=600&h=400&fit=crop';
              }}
            />
          ) : (
            <div className="flex h-full items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
              <Calendar className="h-12 w-12 text-primary/40" />
            </div>
          )}

          {/* Status Badges */}
          <div className="absolute left-2 top-2 flex flex-wrap gap-1">
            {isPast && (
              <Badge variant="secondary">{t.eventCard.ended}</Badge>
            )}
            {event.status === 'draft' && (
              <Badge variant="secondary">{t.eventCard.draft}</Badge>
            )}
            {isFull && !isPast && (
              <Badge variant="destructive">{t.eventCard.full}</Badge>
            )}
          </div>

          {/* Favorite Button */}
          {onFavoriteToggle && (
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'absolute right-2 top-2 bg-background/80 backdrop-blur-sm hover:bg-background',
                isFavorite && 'text-red-500'
              )}
              onClick={handleFavoriteClick}
            >
              <Heart className={cn('h-5 w-5', isFavorite && 'fill-current')} />
            </Button>
          )}

          {/* Edit Button */}
          {showEditButton && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 bottom-2 bg-background/80 backdrop-blur-sm hover:bg-background"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                window.location.href = `/organizer/events/${event.id}/edit`;
              }}
            >
              <Pencil className="h-4 w-4" />
            </Button>
          )}
        </div>

        <CardHeader className="pb-2">
          {/* Category */}
          {event.category && (
            <Badge variant="outline" className="w-fit">
              {getEventCategoryLabel(event.category, language)}
            </Badge>
          )}
          <h3 className="line-clamp-2 text-lg font-semibold leading-tight">
            {event.title}
          </h3>
        </CardHeader>

        <CardContent className="space-y-2 pb-2">
          {/* Date & Time */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>{formatDate(event.start_time, language)}</span>
            <Clock className="ml-2 h-4 w-4" />
            <span>{formatTime(event.start_time, language)}</span>
          </div>

          {/* City / Location */}
          {(event.city || event.location) && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4" />
              <span className="line-clamp-1">
                {[event.city, event.location].filter(Boolean).join(' • ')}
              </span>
            </div>
          )}

          {/* Seats */}
          {event.max_seats && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Users className="h-4 w-4" />
              <span>
                {event.seats_taken} / {event.max_seats} {t.eventCard.seatsTakenSuffix}
              </span>
            </div>
          )}

          {/* Recommendation Reason */}
          {showRecommendation && event.recommendation_reason && (
            <div className="flex items-center gap-2 rounded-md bg-primary/10 px-2 py-1 text-xs text-primary">
              <Sparkles className="h-3 w-3" />
              <span>{event.recommendation_reason}</span>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex flex-wrap gap-1 pt-0">
          {/* Tags */}
          {event.tags.slice(0, 3).map((tag) => (
            <Badge key={tag.id} variant="secondary" className="text-xs">
              {tag.name}
            </Badge>
          ))}
          {event.tags.length > 3 && (
            <Badge variant="secondary" className="text-xs">
              +{event.tags.length - 3}
            </Badge>
          )}
        </CardFooter>
      </Link>
    </Card>
  );
}
