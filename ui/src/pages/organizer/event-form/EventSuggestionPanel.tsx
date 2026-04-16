import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getEventCategoryLabel } from '@/lib/eventCategories';
import type { EventFormController } from './useEventFormController';

type Props = Readonly<{
  controller: EventFormController;
}>;

/**
 * Test helper: event suggestion panel.
 */
export function EventSuggestionPanel({ controller }: Props) {
  const { language, suggestion, t, applySuggestion } = controller;

  if (!suggestion) {
    return null;
  }

  return (
    <div className="mb-6 space-y-3 rounded-lg border bg-muted/30 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium">{t.eventForm.suggestionsTitle}</div>
        <Button type="button" variant="secondary" size="sm" onClick={applySuggestion}>
          {t.eventForm.applySuggestions}
        </Button>
      </div>

      {(suggestion.moderation_status === 'flagged' || suggestion.moderation_flags.length > 0) && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <div className="mb-1 flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {t.eventForm.moderationWarningTitle}
          </div>
          <div className="text-muted-foreground">{t.eventForm.moderationWarningDescription}</div>
          {suggestion.moderation_flags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {suggestion.moderation_flags.map((flag) => (
                <Badge key={flag} variant="destructive">
                  {flag}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs font-medium text-muted-foreground">{t.eventForm.suggestedCategory}</div>
          <div className="text-sm">
            {suggestion.suggested_category
              ? getEventCategoryLabel(suggestion.suggested_category, language)
              : t.eventForm.suggestionNone}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium text-muted-foreground">{t.eventForm.suggestedCity}</div>
          <div className="text-sm">{suggestion.suggested_city || t.eventForm.suggestionNone}</div>
        </div>
      </div>

      <div>
        <div className="text-xs font-medium text-muted-foreground">{t.eventForm.suggestedTags}</div>
        {suggestion.suggested_tags.length ? (
          <div className="mt-1 flex flex-wrap gap-2">
            {suggestion.suggested_tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        ) : (
          <div className="text-sm">{t.eventForm.suggestionNone}</div>
        )}
      </div>

      {suggestion.duplicates.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground">{t.eventForm.duplicatesTitle}</div>
          <div className="mt-2 space-y-2">
            {suggestion.duplicates.slice(0, 5).map((duplicate) => (
              <div key={duplicate.id} className="flex items-center justify-between gap-3 rounded-md border bg-background p-3">
                <div className="min-w-0">
                  <Link to={`/events/${duplicate.id}`} className="truncate text-sm font-medium hover:underline">
                    {duplicate.title}
                  </Link>
                  <div className="text-xs text-muted-foreground">
                    {duplicate.city || '-'} • {Math.round(duplicate.similarity * 100)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
