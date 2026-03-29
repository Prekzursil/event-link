import type { NotificationPreferences, PersonalizationSettings } from '@/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/ui/loading';
import { EyeOff, Mail, Trash2, UserX } from 'lucide-react';
import type { ProfileTexts } from './shared';

type PersonalizationSectionProps = Readonly<{
  hiddenTags: PersonalizationSettings['hidden_tags'];
  blockedOrganizers: PersonalizationSettings['blocked_organizers'];
  notificationPrefs: NotificationPreferences | null;
  isSavingNotifications: boolean;
  t: ProfileTexts;
  onUnhideTag: (tagId: number) => void;
  onUnblockOrganizer: (organizerId: number) => void;
  onNotificationPreferenceChange: (patch: Partial<NotificationPreferences>) => void;
}>;

/** Render the list of hidden tags that can be restored to the student profile. */
function HiddenTagsPanel({
  hiddenTags,
  t,
  onUnhideTag,
}: Readonly<{
  hiddenTags: PersonalizationSettings['hidden_tags'];
  t: ProfileTexts;
  onUnhideTag: (tagId: number) => void;
}>) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <EyeOff className="h-4 w-4" />
        {t.personalization.hiddenTagsTitle}
      </div>
      {hiddenTags.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t.personalization.hiddenTagsEmpty}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {hiddenTags.map((tag) => (
            <Badge key={tag.id} variant="secondary" className="gap-2">
              {tag.name}
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => onUnhideTag(tag.id)}
                aria-label={t.personalization.unhideTagAriaLabel}
              >
                ✕
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

/** Render the list of blocked organizers that can be unblocked. */
function BlockedOrganizersPanel({
  blockedOrganizers,
  t,
  onUnblockOrganizer,
}: Readonly<{
  blockedOrganizers: PersonalizationSettings['blocked_organizers'];
  t: ProfileTexts;
  onUnblockOrganizer: (organizerId: number) => void;
}>) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <UserX className="h-4 w-4" />
        {t.personalization.blockedOrganizersTitle}
      </div>
      {blockedOrganizers.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t.personalization.blockedOrganizersEmpty}</p>
      ) : (
        <div className="space-y-2">
          {blockedOrganizers.map((organizer) => (
            <div key={organizer.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {organizer.org_name || organizer.full_name || organizer.email}
                </div>
                <div className="truncate text-xs text-muted-foreground">{organizer.email}</div>
              </div>
              <Button variant="outline" size="sm" onClick={() => onUnblockOrganizer(organizer.id)}>
                {t.personalization.unblockOrganizerAction}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Render one notification-preference toggle row. */
function NotificationPreferenceRow({
  checked,
  description,
  disabled,
  label,
  onCheckedChange,
}: Readonly<{
  checked: boolean;
  description: string;
  disabled: boolean;
  label: string;
  onCheckedChange?: (checked: boolean) => void;
}>) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      <Checkbox
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
      />
    </div>
  );
}

/** Render the personalization and notification settings available to students. */
export function PersonalizationSection({
  hiddenTags,
  blockedOrganizers,
  notificationPrefs,
  isSavingNotifications,
  t,
  onUnhideTag,
  onUnblockOrganizer,
  onNotificationPreferenceChange,
}: PersonalizationSectionProps) {
  return (
    <>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <EyeOff className="h-5 w-5" />
            {t.personalization.profileTitle}
          </CardTitle>
          <CardDescription>{t.personalization.profileDescription}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <HiddenTagsPanel hiddenTags={hiddenTags} t={t} onUnhideTag={onUnhideTag} />
          <BlockedOrganizersPanel
            blockedOrganizers={blockedOrganizers}
            t={t}
            onUnblockOrganizer={onUnblockOrganizer}
          />
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            {t.notifications.title}
          </CardTitle>
          <CardDescription>{t.notifications.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <NotificationPreferenceRow
            checked={Boolean(notificationPrefs?.email_digest_enabled)}
            description={t.notifications.weeklyDigestDescription}
            disabled={isSavingNotifications || !notificationPrefs}
            label={t.notifications.weeklyDigestLabel}
            onCheckedChange={
              notificationPrefs
                ? (checked) => onNotificationPreferenceChange({ email_digest_enabled: Boolean(checked) })
                : undefined
            }
          />
          <NotificationPreferenceRow
            checked={Boolean(notificationPrefs?.email_filling_fast_enabled)}
            description={t.notifications.fillingFastDescription}
            disabled={isSavingNotifications || !notificationPrefs}
            label={t.notifications.fillingFastLabel}
            onCheckedChange={
              notificationPrefs
                ? (checked) =>
                    onNotificationPreferenceChange({ email_filling_fast_enabled: Boolean(checked) })
                : undefined
            }
          />

          {isSavingNotifications && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoadingSpinner size="sm" />
              {t.profile.saving}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

type PrivacyCardProps = Readonly<{
  t: ProfileTexts;
  onOpenDeleteDialog: () => void;
}>;

/** Render the destructive privacy card that opens the account-deletion dialog. */
export function PrivacyCard({ t, onOpenDeleteDialog }: PrivacyCardProps) {
  return (
    <Card className="mt-6 border-destructive/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <Trash2 className="h-5 w-5" />
          {t.profile.privacyTitle}
        </CardTitle>
        <CardDescription>{t.profile.privacyDescription}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="destructive" onClick={onOpenDeleteDialog}>
          {t.profile.deleteAccount}
        </Button>
      </CardContent>
    </Card>
  );
}

type DeleteAccountDialogProps = Readonly<{
  open: boolean;
  deletePassword: string;
  isDeleting: boolean;
  t: ProfileTexts;
  onOpenChange: (open: boolean) => void;
  onDeletePasswordChange: (value: string) => void;
  onCancel: () => void;
  onDelete: () => void;
}>;

/** Render the destructive confirmation dialog for permanent account deletion. */
export function DeleteAccountDialog({
  open,
  deletePassword,
  isDeleting,
  t,
  onOpenChange,
  onDeletePasswordChange,
  onCancel,
  onDelete,
}: DeleteAccountDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.profile.deleteDialogTitle}</DialogTitle>
          <DialogDescription>{t.profile.deleteDialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="deletePassword">{t.profile.deleteAccessCodeLabel}</Label>
          <Input
            id="deletePassword"
            type="password"
            value={deletePassword}
            onChange={(e) => onDeletePasswordChange(e.target.value)}
            placeholder={t.profile.deleteAccessCodePlaceholder}
            disabled={isDeleting}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isDeleting}>
            {t.common.cancel}
          </Button>
          <Button variant="destructive" onClick={onDelete} disabled={isDeleting}>
            {isDeleting ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                {t.profile.deleting}
              </>
            ) : (
              t.profile.deleteAccount
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
