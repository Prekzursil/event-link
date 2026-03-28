import type React from 'react';
import { Save, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { EVENT_CATEGORIES, getEventCategoryLabel } from '@/lib/eventCategories';
import type { EventFormController } from './useEventFormController';

type Props = Readonly<{
  controller: EventFormController;
}>;

function TitleDescriptionFields({ controller }: Props) {
  const { formData, t, updateField } = controller;

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="title">{t.eventForm.fields.title} *</Label>
        <Input
          id="title"
          value={formData.title}
          onChange={(event) => updateField('title', event.target.value)}
          placeholder={t.eventForm.placeholders.title}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t.eventForm.fields.description}</Label>
        <Textarea
          id="description"
          value={formData.description}
          onChange={(event) => updateField('description', event.target.value)}
          placeholder={t.eventForm.placeholders.description}
          rows={5}
        />
      </div>
    </>
  );
}

function CategoryStatusFields({ controller }: Props) {
  const { formData, language, t, updateField } = controller;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <Label>{t.eventForm.fields.category} *</Label>
        <Select value={formData.category} onValueChange={(value) => updateField('category', value)}>
          <SelectTrigger>
            <SelectValue placeholder={t.eventForm.placeholders.category} />
          </SelectTrigger>
          <SelectContent>
            {EVENT_CATEGORIES.map((category) => (
              <SelectItem key={category} value={category}>
                {getEventCategoryLabel(category, language)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>{t.eventForm.fields.status}</Label>
        <Select
          value={formData.status}
          onValueChange={(value) => updateField('status', value as 'draft' | 'published')}
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
  );
}

function ScheduleFields({ controller }: Props) {
  const { formData, t, updateField } = controller;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <Label htmlFor="start_time">{t.eventForm.fields.startTime} *</Label>
        <Input
          id="start_time"
          type="datetime-local"
          value={formData.start_time}
          onChange={(event) => updateField('start_time', event.target.value)}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="end_time">{t.eventForm.fields.endTime}</Label>
        <Input
          id="end_time"
          type="datetime-local"
          value={formData.end_time}
          onChange={(event) => updateField('end_time', event.target.value)}
        />
      </div>
    </div>
  );
}

function VenueFields({ controller }: Props) {
  const { formData, t, updateField } = controller;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div className="space-y-2">
        <Label htmlFor="city">{t.eventForm.fields.city} *</Label>
        <Input
          id="city"
          value={formData.city}
          onChange={(event) => updateField('city', event.target.value)}
          placeholder={t.eventForm.placeholders.cityExample}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="location">{t.eventForm.fields.location} *</Label>
        <Input
          id="location"
          value={formData.location}
          onChange={(event) => updateField('location', event.target.value)}
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
          onChange={(event) => updateField('max_seats', event.target.value ? Number.parseInt(event.target.value, 10) : undefined)}
          placeholder={t.eventForm.placeholders.maxSeatsExample}
          required
        />
      </div>
    </div>
  );
}

function CoverField({ controller }: Props) {
  const { formData, t, updateField } = controller;

  return (
    <div className="space-y-2">
      <Label htmlFor="cover_url">{t.eventForm.fields.coverUrl}</Label>
      <Input
        id="cover_url"
        type="url"
        value={formData.cover_url}
        onChange={(event) => updateField('cover_url', event.target.value)}
        placeholder="https://example.com/image.jpg"
      />
      {formData.cover_url && (
        <img
          src={formData.cover_url}
          alt="Preview"
          className="mt-2 h-32 w-auto rounded-lg object-cover"
          onError={(event) => {
            (event.target as HTMLImageElement).style.display = 'none';
          }}
        />
      )}
    </div>
  );
}

function TagsField({ controller }: Props) {
  const { addTag, formData, removeTag, setTagInput, t, tagInput } = controller;

  return (
    <div className="space-y-2">
      <Label>{t.eventForm.fields.tags}</Label>
      <div className="flex gap-2">
        <Input
          value={tagInput}
          onChange={(event) => setTagInput(event.target.value)}
          placeholder={t.eventForm.placeholders.tag}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addTag();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={addTag}>
          {t.eventForm.addTag}
        </Button>
      </div>
      {formData.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {formData.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              <X className="h-3 w-3 cursor-pointer" onClick={() => removeTag(tag)} />
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function FormActions({ controller }: Props) {
  const { isSaving, navigate, submitLabel, t } = controller;

  return (
    <div className="flex justify-end gap-4">
      <Button type="button" variant="outline" onClick={() => navigate('/organizer')}>
        {t.common.cancel}
      </Button>
      <Button type="submit" disabled={isSaving}>
        <Save className="mr-2 h-4 w-4" />
        {submitLabel}
      </Button>
    </div>
  );
}

export function EventFormEditor({ controller }: Props) {
  return (
    <form onSubmit={controller.handleSubmit as unknown as (event: React.FormEvent<HTMLFormElement>) => void} className="space-y-6">
      <TitleDescriptionFields controller={controller} />
      <CategoryStatusFields controller={controller} />
      <ScheduleFields controller={controller} />
      <VenueFields controller={controller} />
      <CoverField controller={controller} />
      <TagsField controller={controller} />
      <FormActions controller={controller} />
    </form>
  );
}
