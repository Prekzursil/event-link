import type { ReactNode } from 'react';
import { Bell, Mail, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingPage } from '@/components/ui/loading';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { AdminDashboardController } from './useAdminDashboardController';

type Props = Readonly<{
  controller: AdminDashboardController;
}>;

type RegistrationsRow = Props['controller']['registrationsByDay'][number];
type TopTagRow = Props['controller']['topTags'][number];
type PersonalizationRow = Props['controller']['personalizationRows'][number];
type PersonalizationTotals = NonNullable<Props['controller']['personalizationMetrics']>['totals'];

type EmptyStateProps = Readonly<{
  message: string;
}>;

type OverviewTableCardProps = Readonly<{
  children: ReactNode;
  title: string;
}>;

type StatCardProps = Readonly<{
  title: string;
  value: number;
}>;

type QueueActionProps = Readonly<{
  disabled: boolean;
  idleLabel: string;
  isPending: boolean;
  onClick: () => void;
  pendingLabel: string;
  title: 'digest' | 'fillingFast' | 'retrain';
}>;

type RegistrationsTableProps = Readonly<{
  dayLabel: string;
  emptyMessage: string;
  registrationsLabel: string;
  rows: RegistrationsRow[];
}>;

type TopTagsTableProps = Readonly<{
  emptyMessage: string;
  eventsLabel: string;
  registrationsLabel: string;
  rows: TopTagRow[];
  tagLabel: string;
}>;

type MetricsSummaryGridProps = Readonly<{
  labels: {
    clicks: string;
    conversion: string;
    ctr: string;
    impressions: string;
    registrations: string;
  };
  totals: PersonalizationTotals;
}>;

type PersonalizationTableProps = Readonly<{
  rows: PersonalizationRow[];
  table: Props['controller']['t']['adminDashboard']['personalizationMetrics']['table'];
}>;

type StatsGridProps = Readonly<{
  labels: Props['controller']['t']['adminDashboard']['stats'];
  stats: Props['controller']['stats'];
}>;

type PersonalizationContentProps = Readonly<{
  controller: Props['controller'];
}>;

type PersonalizationActionsProps = Readonly<{
  controller: Props['controller'];
}>;

/** Render the shared empty state for admin overview cards. */
const EmptyState = ({ message }: EmptyStateProps) => (
  <p className="text-sm text-muted-foreground">{message}</p>
);

/** Wrap overview table content in the dashboard card shell. */
const OverviewTableCard = ({ children, title }: OverviewTableCardProps) => (
  <Card>
    <CardHeader>
      <CardTitle>{title}</CardTitle>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

/** Render a single top-level statistic card. */
const StatCard = ({ title, value }: StatCardProps) => (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
    </CardContent>
  </Card>
);

/** Render a queue action with a consistent icon/button layout. */
const QueueAction = ({
  disabled,
  idleLabel,
  isPending,
  onClick,
  pendingLabel,
  title,
}: QueueActionProps) => {
  const iconByTitle = {
    digest: Mail,
    fillingFast: Bell,
    retrain: Sparkles,
  } as const;
  const Icon = iconByTitle[title];

  return (
    <Button variant="outline" size="sm" onClick={onClick} disabled={disabled}>
      <Icon className="mr-2 h-4 w-4" />
      {isPending ? pendingLabel : idleLabel}
    </Button>
  );
};

/** Render the registrations-by-day table or its empty state. */
const RegistrationsTable = ({
  dayLabel,
  emptyMessage,
  registrationsLabel,
  rows,
}: RegistrationsTableProps) => {
  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{dayLabel}</TableHead>
          <TableHead className="text-right">{registrationsLabel}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.date}>
            <TableCell>{row.date}</TableCell>
            <TableCell className="text-right">{row.registrations}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

/** Render the top-tags table or its empty state. */
const TopTagsTable = ({
  emptyMessage,
  eventsLabel,
  registrationsLabel,
  rows,
  tagLabel,
}: TopTagsTableProps) => {
  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{tagLabel}</TableHead>
          <TableHead className="text-right">{registrationsLabel}</TableHead>
          <TableHead className="text-right">{eventsLabel}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.name}-${row.events}-${row.registrations}`}>
            <TableCell>{row.name}</TableCell>
            <TableCell className="text-right">{row.registrations}</TableCell>
            <TableCell className="text-right">{row.events}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

/** Render the personalization totals summary. */
const MetricsSummaryGrid = ({ labels, totals }: MetricsSummaryGridProps) => {
  const cards = [
    { label: labels.impressions, value: totals.impressions },
    { label: labels.clicks, value: totals.clicks },
    { label: labels.registrations, value: totals.registrations },
    { label: labels.ctr, value: `${Math.round(totals.ctr * 100)}%` },
    {
      label: labels.conversion,
      value: `${Math.round(totals.registration_conversion * 100)}%`,
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border p-3">
          <div className="text-xs font-medium text-muted-foreground">{card.label}</div>
          <div className="text-lg font-bold">{card.value}</div>
        </div>
      ))}
    </div>
  );
};

/** Render the day-level personalization metrics table. */
const PersonalizationTable = ({ rows, table }: PersonalizationTableProps) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>{table.day}</TableHead>
        <TableHead className="text-right">{table.impressions}</TableHead>
        <TableHead className="text-right">{table.clicks}</TableHead>
        <TableHead className="text-right">{table.registrations}</TableHead>
        <TableHead className="text-right">{table.ctr}</TableHead>
        <TableHead className="text-right">{table.conversion}</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {rows.map((row) => (
        <TableRow key={row.date}>
          <TableCell>{row.date}</TableCell>
          <TableCell className="text-right">{row.impressions}</TableCell>
          <TableCell className="text-right">{row.clicks}</TableCell>
          <TableCell className="text-right">{row.registrations}</TableCell>
          <TableCell className="text-right">{Math.round(row.ctr * 100)}%</TableCell>
          <TableCell className="text-right">
            {Math.round(row.registration_conversion * 100)}%
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

/** Render the top-level admin overview statistic cards. */
const StatsGrid = ({ labels, stats }: StatsGridProps) => {
  const statCards = [
    { title: labels.totalUsers, value: stats?.total_users ?? 0 },
    { title: labels.totalEvents, value: stats?.total_events ?? 0 },
    { title: labels.totalRegistrations, value: stats?.total_registrations ?? 0 },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {statCards.map((card) => (
        <StatCard key={card.title} title={card.title} value={card.value} />
      ))}
    </div>
  );
};

/** Render the queue actions shown in the personalization metrics card header. */
const PersonalizationActions = ({ controller }: PersonalizationActionsProps) => (
  <div className="flex flex-wrap gap-2">
    <QueueAction
      disabled={controller.isEnqueueingRetrain}
      idleLabel={controller.t.adminDashboard.personalizationMetrics.retrainNow}
      isPending={controller.isEnqueueingRetrain}
      onClick={controller.handleEnqueueRetrain}
      pendingLabel={controller.t.adminDashboard.personalizationMetrics.queueing}
      title="retrain"
    />
    <QueueAction
      disabled={controller.isEnqueueingDigest}
      idleLabel={controller.t.adminDashboard.notifications.enqueueDigest}
      isPending={controller.isEnqueueingDigest}
      onClick={controller.handleEnqueueDigest}
      pendingLabel={controller.t.adminDashboard.notifications.queueing}
      title="digest"
    />
    <QueueAction
      disabled={controller.isEnqueueingFillingFast}
      idleLabel={controller.t.adminDashboard.notifications.enqueueFillingFast}
      isPending={controller.isEnqueueingFillingFast}
      onClick={controller.handleEnqueueFillingFast}
      pendingLabel={controller.t.adminDashboard.notifications.queueing}
      title="fillingFast"
    />
  </div>
);

/** Render the body of the personalization metrics card. */
const PersonalizationContent = ({ controller }: PersonalizationContentProps) => {
  if (controller.isLoadingPersonalizationMetrics) {
    return <LoadingPage message={controller.t.adminDashboard.personalizationMetrics.loading} />;
  }
  if (controller.personalizationRows.length === 0 || !controller.personalizationMetrics) {
    return <EmptyState message={controller.t.adminDashboard.noData} />;
  }

  return (
    <div className="space-y-4">
      <MetricsSummaryGrid
        labels={controller.t.adminDashboard.personalizationMetrics.totals}
        totals={controller.personalizationMetrics.totals}
      />
      <PersonalizationTable
        rows={controller.personalizationRows}
        table={controller.t.adminDashboard.personalizationMetrics.table}
      />
    </div>
  );
};

/** Render the admin overview tab with stats and personalization controls. */
export function AdminOverviewTab({ controller }: Props) {
  return (
    <div className="mt-6 space-y-6">
      <StatsGrid labels={controller.t.adminDashboard.stats} stats={controller.stats} />

      <div className="grid gap-6 lg:grid-cols-2">
        <OverviewTableCard title={controller.t.adminDashboard.registrationsByDay.title}>
          <RegistrationsTable
            dayLabel={controller.t.adminDashboard.registrationsByDay.day}
            emptyMessage={controller.t.adminDashboard.noData}
            registrationsLabel={controller.t.adminDashboard.registrationsByDay.registrations}
            rows={controller.registrationsByDay}
          />
        </OverviewTableCard>

        <OverviewTableCard title={controller.t.adminDashboard.topTags.title}>
          <TopTagsTable
            emptyMessage={controller.t.adminDashboard.noData}
            eventsLabel={controller.t.adminDashboard.topTags.events}
            registrationsLabel={controller.t.adminDashboard.topTags.registrations}
            rows={controller.topTags}
            tagLabel={controller.t.adminDashboard.topTags.tag}
          />
        </OverviewTableCard>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>{controller.t.adminDashboard.personalizationMetrics.title}</CardTitle>
          <PersonalizationActions controller={controller} />
        </CardHeader>
        <CardContent>
          <PersonalizationContent controller={controller} />
        </CardContent>
      </Card>
    </div>
  );
}
