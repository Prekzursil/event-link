import { RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { LoadingPage } from '@/components/ui/loading';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatDateTime } from '@/lib/utils';
import type { UserRole } from '@/types';
import { roleBadgeVariant } from './shared';
import type { AdminDashboardController } from './useAdminDashboardController';

type Props = Readonly<{
  controller: AdminDashboardController;
}>;

type Controller = Props['controller'];
type UserRecord = Controller['users'][number];
type UsersCopy = Controller['t']['adminDashboard']['users'];
type PaginationCopy = Controller['t']['adminDashboard']['pagination'];

type UserRowProps = Readonly<{
  controller: Controller;
  user: UserRecord;
}>;

type UsersTableProps = Readonly<{
  controller: Controller;
  users: UserRecord[];
}>;

type UsersPaginationProps = Readonly<{
  copy: PaginationCopy;
  currentPage: number;
  onNext: () => void;
  onPrevious: () => void;
  totalItems: number;
  totalPages: number;
}>;

type UsersContentProps = Readonly<{
  controller: Controller;
  users: UserRecord[];
}>;

type UsersFiltersProps = Readonly<{
  controller: Controller;
  usersCopy: UsersCopy;
}>;

/** Render the editable role and activity cells for a single admin user row. */
function UserRow({ controller, user }: UserRowProps) {
  const { handleUpdateUser, language, roleLabels, t } = controller;

  return (
    <TableRow key={user.id}>
      <TableCell>
        <div className="font-medium">{user.email}</div>
        {user.full_name ? (
          <div className="text-xs text-muted-foreground">{user.full_name}</div>
        ) : null}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Badge variant={roleBadgeVariant(user.role)}>{roleLabels[user.role]}</Badge>
          <Select
            value={user.role}
            onValueChange={(value) => handleUpdateUser(user.id, { role: value as UserRole })}
          >
            <SelectTrigger className="h-8 w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
              <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
              <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </TableCell>
      <TableCell>
        <Checkbox
          checked={user.is_active}
          onCheckedChange={(checked) => handleUpdateUser(user.id, { is_active: Boolean(checked) })}
        />
      </TableCell>
      <TableCell>{formatDateTime(user.created_at, language)}</TableCell>
      <TableCell>{user.last_seen_at ? formatDateTime(user.last_seen_at, language) : '-'}</TableCell>
      <TableCell className="text-right">{user.registrations_count}</TableCell>
      <TableCell className="text-right">{user.attended_count}</TableCell>
      <TableCell className="text-right">{user.events_created_count}</TableCell>
    </TableRow>
  );
}

/** Render the user results table once the admin query has returned rows. */
function UsersTable({ controller, users }: UsersTableProps) {
  const table = controller.t.adminDashboard.users.table;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{table.email}</TableHead>
          <TableHead>{table.role}</TableHead>
          <TableHead>{table.active}</TableHead>
          <TableHead>{table.created}</TableHead>
          <TableHead>{table.lastSeen}</TableHead>
          <TableHead className="text-right">{table.registrations}</TableHead>
          <TableHead className="text-right">{table.attendances}</TableHead>
          <TableHead className="text-right">{table.events}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => (
          <UserRow key={user.id} controller={controller} user={user} />
        ))}
      </TableBody>
    </Table>
  );
}

/** Render the shared pagination footer below the admin users table. */
function UsersPagination({
  copy,
  currentPage,
  onNext,
  onPrevious,
  totalItems,
  totalPages,
}: UsersPaginationProps) {
  return (
    <div className="mt-4 flex items-center justify-between">
      <p className="text-sm text-muted-foreground">
        {copy.page} {currentPage} / {totalPages} • {copy.total} {totalItems}
      </p>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={currentPage <= 1} onClick={onPrevious}>
          {copy.prev}
        </Button>
        <Button variant="outline" size="sm" disabled={currentPage >= totalPages} onClick={onNext}>
          {copy.next}
        </Button>
      </div>
    </div>
  );
}

/** Render the loading, empty, or populated results state for admin users. */
function UsersContent({ controller, users }: UsersContentProps) {
  const { isLoadingUsers, loadUsers, t, totalUserPages, usersPage, usersTotal } = controller;

  if (isLoadingUsers) {
    return <LoadingPage message={t.adminDashboard.users.loading} />;
  }
  if (users.length === 0) {
    return <p className="text-sm text-muted-foreground">{t.adminDashboard.users.empty}</p>;
  }

  // skipcq: JS-0415 - this content block intentionally keeps empty, table, and pagination states together.
  return (
    <>
      <UsersTable controller={controller} users={users} />
      <UsersPagination
        copy={t.adminDashboard.pagination}
        currentPage={usersPage}
        onNext={() => loadUsers(usersPage + 1)}
        onPrevious={() => loadUsers(usersPage - 1)}
        totalItems={usersTotal}
        totalPages={totalUserPages}
      />
    </>
  );
}

/** Render the filter controls shown above the admin users table. */
function UsersFilters({ controller, usersCopy }: UsersFiltersProps) {
  const {
    isLoadingUsers,
    loadUsers,
    setUsersActive,
    setUsersRole,
    setUsersSearch,
    t,
    usersActive,
    usersRole,
    usersSearch,
  } = controller;

  return (
    <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
      <div className="flex-1">
        <label className="mb-1 block text-sm font-medium">{usersCopy.searchLabel}</label>
        <Input
          value={usersSearch}
          onChange={(event) => setUsersSearch(event.target.value)}
          placeholder={usersCopy.searchPlaceholder}
        />
      </div>
      <div className="w-full md:w-56">
        <label className="mb-1 block text-sm font-medium">{usersCopy.roleLabel}</label>
        <Select value={usersRole} onValueChange={(value) => setUsersRole(value as 'all' | UserRole)}>
          <SelectTrigger>
            <SelectValue placeholder={usersCopy.all} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{usersCopy.all}</SelectItem>
            <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
            <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
            <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="w-full md:w-56">
        <label className="mb-1 block text-sm font-medium">{usersCopy.statusLabel}</label>
        <Select
          value={usersActive}
          onValueChange={(value) => setUsersActive(value as 'all' | 'active' | 'inactive')}
        >
          <SelectTrigger>
            <SelectValue placeholder={usersCopy.all} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{usersCopy.all}</SelectItem>
            <SelectItem value="active">{usersCopy.statusActive}</SelectItem>
            <SelectItem value="inactive">{usersCopy.statusInactive}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Button onClick={() => loadUsers(1)} disabled={isLoadingUsers}>
        <RefreshCw className="mr-2 h-4 w-4" />
        {usersCopy.apply}
      </Button>
    </div>
  );
}

/** Render the admin users tab with filters, table results, and pagination. */
export function AdminUsersTab({ controller }: Props) {
  // skipcq: JS-0415 - the admin users tab intentionally composes filters and content in a single route component.
  return (
    <div className="mt-6 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{controller.t.adminDashboard.users.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <UsersFilters controller={controller} usersCopy={controller.t.adminDashboard.users} />
          <UsersContent controller={controller} users={controller.users} />
        </CardContent>
      </Card>
    </div>
  );
}
