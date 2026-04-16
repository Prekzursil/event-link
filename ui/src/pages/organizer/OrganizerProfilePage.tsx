import { LoadingPage } from '@/components/ui/loading';
import { OrganizerProfileContent } from './organizer-profile/OrganizerProfileContent';
import { useOrganizerProfileController } from './organizer-profile/useOrganizerProfileController';

/**
 * Test helper: organizer profile page.
 */
export function OrganizerProfilePage() {
  const controller = useOrganizerProfileController();

  if (controller.isLoading) {
    return <LoadingPage message={controller.t.organizerProfile.loading} />;
  }

  return <OrganizerProfileContent controller={controller} />;
}

export default OrganizerProfilePage;
