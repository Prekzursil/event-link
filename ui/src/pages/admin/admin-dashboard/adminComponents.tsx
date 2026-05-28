import { Button } from '@/components/ui/button';
import { SelectItem } from '@/components/ui/select';
import type { useI18n } from '@/contexts/LanguageContext';

type Translations = ReturnType<typeof useI18n>['t'];
type PaginationCopy = Translations['adminDashboard']['pagination'];

/** Render the three role-selection options shared by the admin role controls. */
export function RoleSelectItems({ t }: Readonly<{ t: Translations }>) {
  return (
    <>
      <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
      <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
      <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
    </>
  );
}

export type AdminPaginationProps = Readonly<{
  copy: PaginationCopy;
  currentPage: number;
  onNext: () => void;
  onPrevious: () => void;
  totalItems: number;
  totalPages: number;
}>;

/** Render the shared pagination footer below an admin dashboard table. */
export function AdminPagination({
  copy,
  currentPage,
  onNext,
  onPrevious,
  totalItems,
  totalPages,
}: AdminPaginationProps) {
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
