import { useCallback, useState, type SetStateAction } from 'react';

/** Manage delete-account dialog visibility and clear the access code when it closes. */
export function useDeleteDialogState() {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<boolean>(false);
  const [deletePassword, setDeletePassword] = useState('');

  const updateDeleteDialogOpen = useCallback((nextValue: SetStateAction<boolean>) => {
    setDeleteDialogOpen((previous) => {
      const resolvedValue = typeof nextValue === 'function' ? nextValue(previous) : nextValue;
      if (!resolvedValue) {
        setDeletePassword('');
      }
      return resolvedValue;
    });
  }, []);

  const closeDeleteDialog = useCallback(() => {
    updateDeleteDialogOpen(false);
  }, [updateDeleteDialogOpen]);

  return {
    closeDeleteDialog,
    deleteDialogOpen,
    deletePassword,
    setDeleteDialogOpen: updateDeleteDialogOpen,
    setDeletePassword,
  };
}
