import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { EventFormData } from '@/types';
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
import { ArrowLeft, Save, X } from 'lucide-react';

const CATEGORIES = [
  'Technical',
  'Cultural',
  'Sports',
  'Academic',
  'Social',
  'Workshop',
  'Conference',
];

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
  const [tagInput, setTagInput] = useState('');
  const { toast } = useToast();

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
          title: 'Eroare',
          description: 'Nu am putut încărca evenimentul',
          variant: 'destructive',
        });
        navigate('/organizer');
      } finally {
        setIsLoading(false);
      }
    },
    [navigate, toast],
  );

  useEffect(() => {
    if (isEditing && id) {
      loadEvent(parseInt(id));
    }
  }, [id, isEditing, loadEvent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.title.trim()) {
      toast({
        title: 'Eroare',
        description: 'Titlul este obligatoriu',
        variant: 'destructive',
      });
      return;
    }

    if (!formData.category) {
      toast({
        title: 'Eroare',
        description: 'Categoria este obligatorie',
        variant: 'destructive',
      });
      return;
    }

    if (!formData.location || formData.location.trim().length < 2) {
      toast({
        title: 'Eroare',
        description: 'Locația este obligatorie (minim 2 caractere)',
        variant: 'destructive',
      });
      return;
    }

    if (!formData.city || formData.city.trim().length < 2) {
      toast({
        title: 'Eroare',
        description: 'Orașul este obligatoriu (minim 2 caractere)',
        variant: 'destructive',
      });
      return;
    }

    if (!formData.start_time) {
      toast({
        title: 'Eroare',
        description: 'Data de început este obligatorie',
        variant: 'destructive',
      });
      return;
    }

    if (!formData.max_seats || formData.max_seats < 1) {
      toast({
        title: 'Eroare',
        description: 'Numărul maxim de locuri este obligatoriu',
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
          title: 'Succes',
          description: 'Evenimentul a fost actualizat',
        });
      } else {
        const newEvent = await eventService.createEvent(dataToSend);
        toast({
          title: 'Succes',
          description: 'Evenimentul a fost creat',
        });
        navigate(`/events/${newEvent.id}`);
        return;
      }

      navigate('/organizer');
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'A apărut o eroare',
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
    return <LoadingPage message="Se încarcă evenimentul..." />;
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <Button variant="ghost" className="mb-6" onClick={() => navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Înapoi
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>
            {isEditing ? 'Editează evenimentul' : 'Creează eveniment nou'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">Titlu *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, title: e.target.value }))
                }
                placeholder="Numele evenimentului"
                required
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">Descriere</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, description: e.target.value }))
                }
                placeholder="Descrierea evenimentului"
                rows={5}
              />
            </div>

            {/* Category & Status */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Categorie *</Label>
                <Select
                  value={formData.category}
                  onValueChange={(value) =>
                    setFormData((prev) => ({ ...prev, category: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selectează categoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {cat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Status</Label>
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
                    <SelectItem value="published">Publicat</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Date & Time */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="start_time">Data și ora începerii *</Label>
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
                <Label htmlFor="end_time">Data și ora terminării</Label>
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
                <Label htmlFor="city">Oraș *</Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, city: e.target.value }))
                  }
                  placeholder="ex: București"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">Locație *</Label>
                <Input
                  id="location"
                  value={formData.location}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, location: e.target.value }))
                  }
                  placeholder="Locația evenimentului"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_seats">Număr maxim de locuri *</Label>
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
                  placeholder="ex: 100"
                  required
                />
              </div>
            </div>

            {/* Cover URL */}
            <div className="space-y-2">
              <Label htmlFor="cover_url">URL imagine de copertă</Label>
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
              <Label>Etichete</Label>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder="Adaugă o etichetă"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={addTag}>
                  Adaugă
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
                Anulează
              </Button>
              <Button type="submit" disabled={isSaving}>
                <Save className="mr-2 h-4 w-4" />
                {isSaving
                  ? 'Se salvează...'
                  : isEditing
                    ? 'Salvează modificările'
                    : 'Creează eveniment'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
