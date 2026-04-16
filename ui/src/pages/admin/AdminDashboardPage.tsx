import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LoadingPage } from '@/components/ui/loading';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdminEventsTab } from './admin-dashboard/AdminEventsTab';
import { AdminOverviewTab } from './admin-dashboard/AdminOverviewTab';
import { type AdminTab } from './admin-dashboard/shared';
import { AdminUsersTab } from './admin-dashboard/AdminUsersTab';
import { useAdminDashboardController } from './admin-dashboard/useAdminDashboardController';

/**
 * Test helper: admin dashboard page.
 */
export function AdminDashboardPage() {
  const controller = useAdminDashboardController();

  if (!controller.stats && controller.isLoadingStats) {
    return <LoadingPage message={controller.t.adminDashboard.loading} />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{controller.t.adminDashboard.title}</h1>
          <p className="mt-2 text-muted-foreground">{controller.t.adminDashboard.subtitle}</p>
        </div>
        <Button variant="outline" onClick={() => controller.loadStats()} disabled={controller.isLoadingStats}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {controller.t.adminDashboard.reload}
        </Button>
      </div>

      <Tabs value={controller.tab} onValueChange={(value) => controller.setTab(value as AdminTab)}>
        <TabsList className="h-auto w-full flex flex-wrap justify-start">
          <TabsTrigger value="overview">{controller.t.adminDashboard.tabs.overview}</TabsTrigger>
          <TabsTrigger value="users">{controller.t.adminDashboard.tabs.users}</TabsTrigger>
          <TabsTrigger value="events">{controller.t.adminDashboard.tabs.events}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <AdminOverviewTab controller={controller} />
        </TabsContent>

        <TabsContent value="users">
          <AdminUsersTab controller={controller} />
        </TabsContent>

        <TabsContent value="events">
          <AdminEventsTab controller={controller} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
