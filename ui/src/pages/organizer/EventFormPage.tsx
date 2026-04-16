import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingPage } from '@/components/ui/loading';
import { EventFormEditor } from './event-form/EventFormEditor';
import { EventSuggestionPanel } from './event-form/EventSuggestionPanel';
import { useEventFormController } from './event-form/useEventFormController';

/**
 * Test helper: event form page.
 */
export function EventFormPage() {
  const controller = useEventFormController();

  if (controller.isLoading) {
    return <LoadingPage message={controller.t.eventForm.loading} />;
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <Button variant="ghost" className="mb-6" onClick={() => controller.navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {controller.t.eventForm.back}
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>{controller.isEditing ? controller.t.eventForm.editTitle : controller.t.eventForm.createTitle}</CardTitle>
          <Button
            type="button"
            variant="outline"
            onClick={controller.handleSuggest}
            disabled={controller.isSuggesting || !controller.formData.title.trim()}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {controller.isSuggesting ? controller.t.eventForm.suggesting : controller.t.eventForm.suggestButton}
          </Button>
        </CardHeader>
        <CardContent>
          <EventSuggestionPanel controller={controller} />
          <EventFormEditor controller={controller} />
        </CardContent>
      </Card>
    </div>
  );
}
