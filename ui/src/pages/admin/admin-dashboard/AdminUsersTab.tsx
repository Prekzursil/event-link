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

type Props = {
  controller: AdminDashboardController;
};

export function AdminUsersTab({ controller }: Props) {
  const {
    handleUpdateUser,
    isLoadingUsers,
    language,
    loadUsers,
    roleLabels,
    t,
    totalUserPages,
    users,
    usersActive,
    usersPage,
    usersRole,
    usersSearch,
    usersTotal,
    setUsersActive,
    setUsersRole,
    setUsersSearch,
  } = controller;

  return (
    <div className="mt-6 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t.adminDashboard.users.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.searchLabel}</label>
              <Input
                value={usersSearch}
                onChange={(event) => setUsersSearch(event.target.value)}
                placeholder={t.adminDashboard.users.searchPlaceholder}
              />
            </div>
            <div className="w-full md:w-56">
              <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.roleLabel}</label>
              <Select value={usersRole} onValueChange={(value) => setUsersRole(value as 'all' | UserRole)}>
                <SelectTrigger>
                  <SelectValue placeholder={t.adminDashboard.users.all} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.adminDashboard.users.all}</SelectItem>
                  <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
                  <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
                  <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-full md:w-56">
              <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.statusLabel}</label>
              <Select value={usersActive} onValueChange={(value) => setUsersActive(value as 'all' | 'active' | 'inactive')}>
                <SelectTrigger>
                  <SelectValue placeholder={t.adminDashboard.users.all} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.adminDashboard.users.all}</SelectItem>
                  <SelectItem value="active">{t.adminDashboard.users.statusActive}</SelectItem>
                  <SelectItem value="inactive">{t.adminDashboard.users.statusInactive}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={() => loadUsers(1)} disabled={isLoadingUsers}>
              <RefreshCw className="mr-2 h-4 w-4" />
              {t.adminDashboard.users.apply}
            </Button>
          </div>

          {isLoadingUsers ? (
            <LoadingPage message={t.adminDashboard.users.loading} />
          ) : users.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t.adminDashboard.users.empty}</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.adminDashboard.users.table.email}</TableHead>
                    <TableHead>{t.adminDashboard.users.table.role}</TableHead>
                    <TableHead>{t.adminDashboard.users.table.active}</TableHead>
                    <TableHead>{t.adminDashboard.users.table.created}</TableHead>
                    <TableHead>{t.adminDashboard.users.table.lastSeen}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.users.table.registrations}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.users.table.attendances}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.users.table.events}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="font-medium">{user.email}</div>
                        {user.full_name && <div className="text-xs text-muted-foreground">{user.full_name}</div>}
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
                  ))}
                </TableBody>
              </Table>

              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {t.adminDashboard.pagination.page} {usersPage} / {totalUserPages} • {t.adminDashboard.pagination.total} {usersTotal}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={usersPage <= 1}
                    onClick={() => loadUsers(usersPage - 1)}
                  >
                    {t.adminDashboard.pagination.prev}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={usersPage >= totalUserPages}
                    onClick={() => loadUsers(usersPage + 1)}
                  >
                    {t.adminDashboard.pagination.next}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
