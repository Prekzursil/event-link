import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { EventFormData, EventSuggestResponse } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import { ArrowLeft, Save, X, Sparkles, AlertTriangle } from 'lucide-react';
import { EVENT_CATEGORIES, getEventCategoryLabel } from '@/lib/eventCategories';

const formatDateTimeLocal = (dateString: string) => {
  const date = new Date(dateString);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

export function EventFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = !!id;
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState<EventSuggestResponse | null>(null);
  const [tagInput, setTagInput] = useState('');
  const { toast } = useToast();
  const { language, t } = useI18n();

  const [formData, setFormData] = useState<EventFormData>({
    title: '',
    description: '',
    category: '',
    start_time: '',
    end_time: '',
    city: '',
    location: '',
    max_seats: undefined,
    cover_url: '',
    tags: [],
    status: 'published',
  });

  const loadEvent = useCallback(
    async (eventId: number) => {
      setIsLoading(true);
      try {
        const event = await eventService.getEvent(eventId);
        setFormData({
          title: event.title,
          description: event.description || '',
          category: event.category || '',
          start_time: formatDateTimeLocal(event.start_time),
          end_time: event.end_time ? formatDateTimeLocal(event.end_time) : '',
          city: event.city || '',
          location: event.location || '',
          max_seats: event.max_seats || undefined,
          cover_url: event.cover_url || '',
          tags: event.tags.map((t) => t.name),
          status: (event.status as 'draft' | 'published') || 'published',
        });
      } catch {
        toast({
          title: t.common.error,
          description: t.eventForm.loadErrorDescription,
          variant: 'destructive',
        });
        navigate('/organizer');
      } finally {
        setIsLoading(false);
      }
    },
    [navigate, t, toast],
  );

  useEffect(() => {
    if (isEditing && id) {
      loadEvent(parseInt(id));
    }
  }, [id, isEditing, loadEvent]);

  const handleSuggest = async () => {
    if (!formData.title.trim() || isSuggesting) return;
    setIsSuggesting(true);
    try {
        const payload = {
          title: formData.title.trim(),
          description: formData.description?.trim() || undefined,
          category: formData.category || undefined,
          city: formData.city?.trim() || undefined,
          location: formData.location?.trim() || undefined,
          start_time: formData.start_time ? new Date(formData.start_time).toISOString() : undefined,
        };
      const res = await eventService.suggestEvent(payload);
      setSuggestion(res);
      toast({
        title: t.eventForm.suggestedTitle,
        description: t.eventForm.suggestedDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventForm.suggestErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsSuggesting(false);
    }
  };

  const applySuggestion = () => {
    if (!suggestion) return;
    setFormData((prev) => {
      const nextTags = Array.from(
        new Set([...(prev.tags ?? []), ...(suggestion.suggested_tags ?? [])].map((t) => t.trim()).filter(Boolean)),
      );
      return {
        ...prev,
        category: prev.category || suggestion.suggested_category || prev.category,
        city: prev.city || suggestion.suggested_city || prev.city,
        tags: nextTags,
      };
    });
    toast({
      title: t.eventForm.suggestionAppliedTitle,
      description: t.eventForm.suggestionAppliedDescription,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.title.trim()) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.titleRequired,
        variant: 'destructive',
      });
      return;
    }

    if (!formData.category) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.categoryRequired,
        variant: 'destructive',
      });
      return;
    }

    if (!formData.location || formData.location.trim().length < 2) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.locationRequired,
        variant: 'destructive',
      });
      return;
    }

    if (!formData.city || formData.city.trim().length < 2) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.cityRequired,
        variant: 'destructive',
      });
      return;
    }

    if (!formData.start_time) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.startRequired,
        variant: 'destructive',
      });
      return;
    }

    if (!formData.max_seats || formData.max_seats < 1) {
      toast({
        title: t.common.error,
        description: t.eventForm.validation.maxSeatsRequired,
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      // Build data object, excluding empty optional fields
      const dataToSend: EventFormData = {
        title: formData.title.trim(),
        category: formData.category,
        city: formData.city.trim(),
        location: formData.location.trim(),
        start_time: new Date(formData.start_time).toISOString(),
        max_seats: formData.max_seats,
        status: formData.status,
        tags: formData.tags || [],
      };

      // Only add optional fields if they have values
      if (formData.description && formData.description.trim()) {
        dataToSend.description = formData.description.trim();
      }
      if (formData.end_time) {
        dataToSend.end_time = new Date(formData.end_time).toISOString();
      }
      if (formData.cover_url && formData.cover_url.trim()) {
        dataToSend.cover_url = formData.cover_url.trim();
      }

      if (isEditing && id) {
        await eventService.updateEvent(parseInt(id), dataToSend);
        toast({
          title: t.common.success,
          description: t.eventForm.updatedDescription,
        });
      } else {
        const newEvent = await eventService.createEvent(dataToSend);
        toast({
          title: t.common.success,
          description: t.eventForm.createdDescription,
        });
        navigate(`/events/${newEvent.id}`);
        return;
      }

      navigate('/organizer');
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventForm.genericError,
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && formData.tags && !formData.tags.includes(tag)) {
      setFormData((prev) => ({
        ...prev,
        tags: [...(prev.tags || []), tag],
      }));
    }
    setTagInput('');
  };

  const removeTag = (tagToRemove: string) => {
    setFormData((prev) => ({
      ...prev,
      tags: prev.tags?.filter((t) => t !== tagToRemove),
    }));
  };

  if (isLoading) {
    return <LoadingPage message={t.eventForm.loading} />;
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <Button variant="ghost" className="mb-6" onClick={() => navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t.eventForm.back}
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>{isEditing ? t.eventForm.editTitle : t.eventForm.createTitle}</CardTitle>
          <Button
            type="button"
            variant="outline"
            onClick={handleSuggest}
            disabled={isSuggesting || !formData.title.trim()}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {isSuggesting ? t.eventForm.suggesting : t.eventForm.suggestButton}
          </Button>
        </CardHeader>
        <CardContent>
          {suggestion && (
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
                  <div className="text-muted-foreground">
                    {t.eventForm.moderationWarningDescription}
                  </div>
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
                {!suggestion.suggested_tags.length ? (
                  <div className="text-sm">{t.eventForm.suggestionNone}</div>
                ) : (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {suggestion.suggested_tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {suggestion.duplicates.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-muted-foreground">{t.eventForm.duplicatesTitle}</div>
                  <div className="mt-2 space-y-2">
                    {suggestion.duplicates.slice(0, 5).map((dup) => (
                      <div key={dup.id} className="flex items-center justify-between gap-3 rounded-md border bg-background p-3">
                        <div className="min-w-0">
                          <Link to={`/events/${dup.id}`} className="truncate text-sm font-medium hover:underline">
                            {dup.title}
                          </Link>
                          <div className="text-xs text-muted-foreground">
                            {dup.city || '-'} • {Math.round(dup.similarity * 100)}%
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">{t.eventForm.fields.title} *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, title: e.target.value }))
                }
                placeholder={t.eventForm.placeholders.title}
                required
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">{t.eventForm.fields.description}</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, description: e.target.value }))
                }
                placeholder={t.eventForm.placeholders.description}
                rows={5}
              />
            </div>

            {/* Category & Status */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t.eventForm.fields.category} *</Label>
                <Select
                  value={formData.category}
                  onValueChange={(value) =>
                    setFormData((prev) => ({ ...prev, category: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t.eventForm.placeholders.category} />
                  </SelectTrigger>
                  <SelectContent>
                    {EVENT_CATEGORIES.map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {getEventCategoryLabel(cat, language)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t.eventForm.fields.status}</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) =>
                    setFormData((prev) => ({
                      ...prev,
                      status: value as 'draft' | 'published',
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="published">{t.eventForm.status.published}</SelectItem>
                    <SelectItem value="draft">{t.eventForm.status.draft}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Date & Time */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="start_time">{t.eventForm.fields.startTime} *</Label>
                <Input
                  id="start_time"
                  type="datetime-local"
                  value={formData.start_time}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, start_time: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="end_time">{t.eventForm.fields.endTime}</Label>
                <Input
                  id="end_time"
                  type="datetime-local"
                  value={formData.end_time}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, end_time: e.target.value }))
                  }
                />
              </div>
            </div>

            {/* City, Location & Max Seats */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="city">{t.eventForm.fields.city} *</Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, city: e.target.value }))
                  }
                  placeholder={t.eventForm.placeholders.cityExample}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">{t.eventForm.fields.location} *</Label>
                <Input
                  id="location"
                  value={formData.location}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, location: e.target.value }))
                  }
                  placeholder={t.eventForm.placeholders.location}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_seats">{t.eventForm.fields.maxSeats} *</Label>
                <Input
                  id="max_seats"
                  type="number"
                  min="1"
                  value={formData.max_seats || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      max_seats: e.target.value ? parseInt(e.target.value) : undefined,
                    }))
                  }
                  placeholder={t.eventForm.placeholders.maxSeatsExample}
                  required
                />
              </div>
            </div>

            {/* Cover URL */}
            <div className="space-y-2">
              <Label htmlFor="cover_url">{t.eventForm.fields.coverUrl}</Label>
              <Input
                id="cover_url"
                type="url"
                value={formData.cover_url}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, cover_url: e.target.value }))
                }
                placeholder="https://example.com/image.jpg"
              />
              {formData.cover_url && (
                <img
                  src={formData.cover_url}
                  alt="Preview"
                  className="mt-2 h-32 w-auto rounded-lg object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <Label>{t.eventForm.fields.tags}</Label>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder={t.eventForm.placeholders.tag}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={addTag}>
                  {t.eventForm.addTag}
                </Button>
              </div>
              {formData.tags && formData.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {formData.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      {tag}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeTag(tag)}
                      />
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* Submit */}
            <div className="flex justify-end gap-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/organizer')}
              >
                {t.common.cancel}
              </Button>
              <Button type="submit" disabled={isSaving}>
                <Save className="mr-2 h-4 w-4" />
                {isSaving
                  ? t.eventForm.saving
                  : isEditing
                    ? t.eventForm.saveChanges
                    : t.eventForm.createButton}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
