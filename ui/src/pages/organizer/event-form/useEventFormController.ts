import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { EventSuggestResponse } from '@/types';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import {
  EMPTY_EVENT_FORM_STATE,
  applySuggestionToFormData,
  buildEventPayload,
  buildSuggestionPayload,
  errorDetail,
  eventToFormState,
  getSubmitLabel,
  type EventFormState,
  validateEventForm,
} from './shared';

export function useEventFormController() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { language, t } = useI18n();
  const isEditing = Boolean(id);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState<EventSuggestResponse | null>(null);
  const [tagInput, setTagInput] = useState('');
  const [formData, setFormData] = useState<EventFormState>(EMPTY_EVENT_FORM_STATE);

  const loadEvent = useCallback(async (eventId: number) => {
    setIsLoading(true);
    try {
      const event = await eventService.getEvent(eventId);
      setFormData(eventToFormState(event));
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
  }, [navigate, t, toast]);

  useEffect(() => {
    if (isEditing && id) {
      void loadEvent(Number.parseInt(id, 10));
    }
  }, [id, isEditing, loadEvent]);

  const updateField = useCallback(<K extends keyof EventFormState>(field: K, value: EventFormState[K]) => {
    setFormData((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSuggest = useCallback(async () => {
    setIsSuggesting(true);
    try {
      const response = await eventService.suggestEvent(buildSuggestionPayload(formData));
      setSuggestion(response);
      toast({
        title: t.eventForm.suggestedTitle,
        description: t.eventForm.suggestedDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventForm.suggestErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsSuggesting(false);
    }
  }, [formData, t, toast]);

  const applySuggestion = useCallback(() => {
    if (!suggestion) {
      return;
    }
    setFormData((current) => applySuggestionToFormData(current, suggestion));
    toast({
      title: t.eventForm.suggestionAppliedTitle,
      description: t.eventForm.suggestionAppliedDescription,
    });
  }, [suggestion, t, toast]);

  const handleSubmit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();

    const validationError = validateEventForm(formData, t);
    if (validationError) {
      toast({
        title: t.common.error,
        description: validationError,
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      const payload = buildEventPayload(formData);
      if (isEditing && id) {
        await eventService.updateEvent(Number.parseInt(id, 10), payload);
        toast({
          title: t.common.success,
          description: t.eventForm.updatedDescription,
        });
        navigate('/organizer');
        return;
      }

      const newEvent = await eventService.createEvent(payload);
      toast({
        title: t.common.success,
        description: t.eventForm.createdDescription,
      });
      navigate(`/events/${newEvent.id}`);
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventForm.genericError),
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  }, [formData, id, isEditing, navigate, t, toast]);

  const addTag = useCallback(() => {
    const tag = tagInput.trim();
    if (tag && !formData.tags.includes(tag)) {
      setFormData((current) => ({ ...current, tags: [...current.tags, tag] }));
    }
    setTagInput('');
  }, [formData.tags, tagInput]);

  const removeTag = useCallback((tagToRemove: string) => {
    setFormData((current) => ({
      ...current,
      tags: current.tags.filter((tag) => tag !== tagToRemove),
    }));
  }, []);

  const submitLabel = useMemo(
    () => getSubmitLabel(isSaving, isEditing, t),
    [isEditing, isSaving, t],
  );

  return {
    addTag,
    applySuggestion,
    formData,
    handleSubmit,
    handleSuggest,
    id,
    isEditing,
    isLoading,
    isSaving,
    isSuggesting,
    language,
    navigate,
    removeTag,
    setTagInput,
    submitLabel,
    suggestion,
    t,
    tagInput,
    updateField,
  };
}

export type EventFormController = ReturnType<typeof useEventFormController>;
