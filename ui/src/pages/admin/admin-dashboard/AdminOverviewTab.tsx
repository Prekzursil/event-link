import { Bell, Mail, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingPage } from '@/components/ui/loading';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { AdminDashboardController } from './useAdminDashboardController';

type Props = {
  controller: AdminDashboardController;
};

function EmptyState({ message }: { message: string }) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

function OverviewTableCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function AdminOverviewTab({ controller }: Props) {
  const {
    handleEnqueueDigest,
    handleEnqueueFillingFast,
    handleEnqueueRetrain,
    isEnqueueingDigest,
    isEnqueueingFillingFast,
    isEnqueueingRetrain,
    isLoadingPersonalizationMetrics,
    personalizationMetrics,
    personalizationRows,
    registrationsByDay,
    stats,
    t,
    topTags,
  } = controller;

  return (
    <div className="mt-6 space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalUsers}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_users ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalEvents}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_events ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalRegistrations}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_registrations ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <OverviewTableCard title={t.adminDashboard.registrationsByDay.title}>
          {registrationsByDay.length === 0 ? (
            <EmptyState message={t.adminDashboard.noData} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.adminDashboard.registrationsByDay.day}</TableHead>
                  <TableHead className="text-right">{t.adminDashboard.registrationsByDay.registrations}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {registrationsByDay.map((row, index) => (
                  <TableRow key={`${row.date}-${index}`}>
                    <TableCell>{row.date}</TableCell>
                    <TableCell className="text-right">{row.registrations}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </OverviewTableCard>

        <OverviewTableCard title={t.adminDashboard.topTags.title}>
          {topTags.length === 0 ? (
            <EmptyState message={t.adminDashboard.noData} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.adminDashboard.topTags.tag}</TableHead>
                  <TableHead className="text-right">{t.adminDashboard.topTags.registrations}</TableHead>
                  <TableHead className="text-right">{t.adminDashboard.topTags.events}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topTags.map((row, index) => (
                  <TableRow key={`${row.name}-${index}`}>
                    <TableCell>{row.name}</TableCell>
                    <TableCell className="text-right">{row.registrations}</TableCell>
                    <TableCell className="text-right">{row.events}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </OverviewTableCard>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>{t.adminDashboard.personalizationMetrics.title}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={handleEnqueueRetrain} disabled={isEnqueueingRetrain}>
              <Sparkles className="mr-2 h-4 w-4" />
              {isEnqueueingRetrain
                ? t.adminDashboard.personalizationMetrics.queueing
                : t.adminDashboard.personalizationMetrics.retrainNow}
            </Button>
            <Button variant="outline" size="sm" onClick={handleEnqueueDigest} disabled={isEnqueueingDigest}>
              <Mail className="mr-2 h-4 w-4" />
              {isEnqueueingDigest ? t.adminDashboard.notifications.queueing : t.adminDashboard.notifications.enqueueDigest}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleEnqueueFillingFast}
              disabled={isEnqueueingFillingFast}
            >
              <Bell className="mr-2 h-4 w-4" />
              {isEnqueueingFillingFast
                ? t.adminDashboard.notifications.queueing
                : t.adminDashboard.notifications.enqueueFillingFast}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingPersonalizationMetrics ? (
            <LoadingPage message={t.adminDashboard.personalizationMetrics.loading} />
          ) : personalizationRows.length === 0 || !personalizationMetrics ? (
            <EmptyState message={t.adminDashboard.noData} />
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.adminDashboard.personalizationMetrics.totals.impressions}
                  </div>
                  <div className="text-lg font-bold">{personalizationMetrics.totals.impressions}</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.adminDashboard.personalizationMetrics.totals.clicks}
                  </div>
                  <div className="text-lg font-bold">{personalizationMetrics.totals.clicks}</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.adminDashboard.personalizationMetrics.totals.registrations}
                  </div>
                  <div className="text-lg font-bold">{personalizationMetrics.totals.registrations}</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.adminDashboard.personalizationMetrics.totals.ctr}
                  </div>
                  <div className="text-lg font-bold">{Math.round(personalizationMetrics.totals.ctr * 100)}%</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.adminDashboard.personalizationMetrics.totals.conversion}
                  </div>
                  <div className="text-lg font-bold">
                    {Math.round(personalizationMetrics.totals.registration_conversion * 100)}%
                  </div>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.adminDashboard.personalizationMetrics.table.day}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.impressions}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.clicks}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.registrations}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.ctr}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.conversion}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {personalizationRows.map((row, index) => (
                    <TableRow key={`${row.date}-${index}`}>
                      <TableCell>{row.date}</TableCell>
                      <TableCell className="text-right">{row.impressions}</TableCell>
                      <TableCell className="text-right">{row.clicks}</TableCell>
                      <TableCell className="text-right">{row.registrations}</TableCell>
                      <TableCell className="text-right">{Math.round(row.ctr * 100)}%</TableCell>
                      <TableCell className="text-right">{Math.round(row.registration_conversion * 100)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
