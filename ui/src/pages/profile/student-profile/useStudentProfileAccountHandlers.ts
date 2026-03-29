import { useCallback, useState } from 'react';
import type { NavigateFunction } from 'react-router-dom';
import eventService from '@/services/event.service';
import { triggerDataExport, type Logout, type ToastFn, type TranslationStrings } from './studentProfileController.shared';

type AccountHandlerArgs = Readonly<{
  closeDeleteDialog: () => void;
  deletePassword: string;
  logout: Logout;
  navigate: NavigateFunction;
  t: TranslationStrings;
  toast: ToastFn;
}>;

/** Export the current student's retained account data as a downloadable blob. */
async function exportStudentProfileData(t: TranslationStrings, toast: ToastFn) {
  const blob = await eventService.exportMyData();
  triggerDataExport(blob);
  toast({ title: t.profile.exportGeneratedTitle, description: t.profile.exportGeneratedDescription });
}

/** Delete the current account after validating the supplied access code. */
async function deleteStudentProfileAccount({
  closeDeleteDialog,
  deletePassword,
  logout,
  navigate,
  t,
  toast,
}: AccountHandlerArgs) {
  const password = deletePassword.trim();
  if (!password) {
    toast({
      title: t.profile.deleteAccessCodeMissingTitle,
      description: t.profile.deleteAccessCodeMissingDescription,
      variant: 'destructive',
    });
    return;
  }

  await eventService.deleteMyAccount(password);
  toast({ title: t.profile.deletedTitle, description: t.profile.deletedDescription });
  closeDeleteDialog();
  logout();
  navigate('/');
}

/** Build account-management actions for export and permanent account deletion. */
export function useStudentProfileAccountHandlers({
  closeDeleteDialog,
  deletePassword,
  logout,
  navigate,
  t,
  toast,
}: AccountHandlerArgs) {
  const [isDeleting, setDeletingState] = useState(false);
  const [isExporting, setExportingState] = useState(false);

  const handleExport = useCallback(async () => {
    setExportingState(true);
    try {
      await exportStudentProfileData(t, toast);
    } catch (error) {
      console.error('Failed to export data:', error);
      toast({ title: t.profile.exportErrorTitle, description: t.profile.exportErrorDescription, variant: 'destructive' });
    } finally {
      setExportingState(false);
    }
  }, [t, toast]);

  const handleDeleteAccount = useCallback(async () => {
    setDeletingState(true);
    try {
      await deleteStudentProfileAccount({ closeDeleteDialog, deletePassword, logout, navigate, t, toast });
    } catch (error: unknown) {
      console.error('Failed to delete account:', error);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({ title: t.profile.deleteErrorTitle, description: axiosError.response?.data?.detail || t.profile.deleteErrorFallback, variant: 'destructive' });
    } finally {
      setDeletingState(false);
    }
  }, [closeDeleteDialog, deletePassword, logout, navigate, t, toast]);

  return { handleDeleteAccount, handleExport, isDeleting, isExporting };
}
