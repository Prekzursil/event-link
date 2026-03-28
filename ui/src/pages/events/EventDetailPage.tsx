import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EventDetailOverview } from './event-detail/EventDetailOverview';
import { EventDetailSidebar } from './event-detail/EventDetailSidebar';
import { EventDetailSkeleton } from './event-detail/EventDetailSkeleton';
import { useEventDetailController } from './event-detail/useEventDetailController';

export function EventDetailPage() {
  const controller = useEventDetailController();

  if (controller.isLoading) {
    return <EventDetailSkeleton />;
  }

  if (!controller.event) {
    return null;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <Button variant="ghost" className="mb-6" onClick={() => controller.navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {controller.t.eventDetail.back}
      </Button>

      <div className="grid gap-8 lg:grid-cols-3">
        <EventDetailOverview
          event={controller.event}
          isPast={controller.isPast}
          isFull={controller.isFull}
          language={controller.language}
          t={controller.t}
        />
        <EventDetailSidebar
          event={controller.event}
          isPast={controller.isPast}
          isFull={controller.isFull}
          isStudent={controller.isStudent}
          hideTagId={controller.hideTagId}
          isRegistering={controller.isRegistering}
          isResendingEmail={controller.isResendingEmail}
          isFavoriting={controller.isFavoriting}
          isCloning={controller.isCloning}
          isHidingTag={controller.isHidingTag}
          isBlockingOrganizer={controller.isBlockingOrganizer}
          t={controller.t}
          onRegister={controller.handleRegister}
          onUnregister={controller.handleUnregister}
          onResendRegistrationEmail={controller.handleResendRegistrationEmail}
          onFavorite={controller.handleFavorite}
          onShare={controller.handleShare}
          onExportCalendar={controller.handleExportCalendar}
          onClone={controller.handleClone}
          onHideTagIdChange={controller.setHideTagId}
          onHideTag={controller.handleHideTag}
          onBlockOrganizer={controller.handleBlockOrganizer}
        />
      </div>
    </div>
  );
}
