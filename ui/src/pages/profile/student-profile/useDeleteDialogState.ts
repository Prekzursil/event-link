import { useCallback, useState, type SetStateAction } from 'react';

/** Manage delete-account dialog visibility and clear the access code when it closes. */
export function useDeleteDialogState() {
  const [deleteDialogOpen, setDeleteDialogOpenState] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');

  const setDeleteDialogOpen = useCallback((nextValue: SetStateAction<boolean>) => {
    setDeleteDialogOpenState((previous) => {
      const resolvedValue = typeof nextValue === 'function' ? nextValue(previous) : nextValue;
      if (!resolvedValue) {
        setDeletePassword('');
      }
      return resolvedValue;
    });
  }, []);

  const closeDeleteDialog = useCallback(() => {
    setDeleteDialogOpen(false);
  }, [setDeleteDialogOpen]);

  return {
    closeDeleteDialog,
    deleteDialogOpen,
    deletePassword,
    setDeleteDialogOpen,
    setDeletePassword,
  };
}
