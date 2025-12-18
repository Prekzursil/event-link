import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Tag, StudentProfile } from '@/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { LoadingPage, LoadingSpinner } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Download, Trash2, User, Tag as TagIcon, Save, Sparkles } from 'lucide-react';
import authService from '@/services/auth.service';
import type { ThemePreference } from '@/types';

export function StudentProfilePage() {
  const { toast } = useToast();
  const { logout, refreshUser } = useAuth();
  const { preference, setPreference } = useTheme();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSavingTheme, setIsSavingTheme] = useState(false);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [profileData, tagsData] = await Promise.all([
        eventService.getStudentProfile(),
        eventService.getAllTags(),
      ]);
      setProfile(profileData);
      setFullName(profileData.full_name || '');
      setSelectedTagIds(profileData.interest_tags.map(t => t.id));
      setAllTags(tagsData);
    } catch (error) {
      console.error('Failed to load profile:', error);
      toast({
        title: 'Eroare',
        description: 'Nu am putut încărca profilul',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTagToggle = (tagId: number) => {
    setSelectedTagIds(prev =>
      prev.includes(tagId)
        ? prev.filter(id => id !== tagId)
        : [...prev, tagId]
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const updatedProfile = await eventService.updateStudentProfile({
        full_name: fullName || undefined,
        interest_tag_ids: selectedTagIds,
      });
      setProfile(updatedProfile);
      toast({
        title: 'Succes',
        description: 'Profilul a fost actualizat',
      });
    } catch (error) {
      console.error('Failed to save profile:', error);
      toast({
        title: 'Eroare',
        description: 'Nu am putut salva profilul',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleThemeChange = async (nextPreference: ThemePreference) => {
    const prev = preference;
    setPreference(nextPreference);
    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
      toast({
        title: 'Tema actualizată',
        description: 'Preferința ta a fost salvată.',
      });
    } catch {
      setPreference(prev);
      toast({
        title: 'Eroare',
        description: 'Nu am putut salva preferința de temă.',
        variant: 'destructive',
      });
    } finally {
      setIsSavingTheme(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const blob = await eventService.exportMyData();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const date = new Date().toISOString().slice(0, 10);
      a.download = `eventlink-export-${date}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast({
        title: 'Export generat',
        description: 'Datele au fost descărcate.',
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      toast({
        title: 'Eroare',
        description: 'Nu am putut genera exportul.',
        variant: 'destructive',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    const password = deletePassword.trim();
    if (!password) {
      toast({
        title: 'Parolă lipsă',
        description: 'Introdu parola pentru a confirma ștergerea contului.',
        variant: 'destructive',
      });
      return;
    }

    setIsDeleting(true);
    try {
      await eventService.deleteMyAccount(password);
      toast({
        title: 'Cont șters',
        description: 'Contul tău a fost șters.',
      });
      setDeleteDialogOpen(false);
      setDeletePassword('');
      logout();
      navigate('/');
    } catch (error: unknown) {
      console.error('Failed to delete account:', error);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Nu am putut șterge contul.',
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return <LoadingPage message="Se încarcă profilul..." />;
  }

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Profilul meu</h1>
        <p className="text-muted-foreground">
          Actualizează-ți informațiile și preferințele
        </p>
      </div>

      {/* Profile Info */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Informații personale
          </CardTitle>
          <CardDescription>
            Datele tale de bază
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={profile?.email || ''}
              disabled
              className="bg-muted"
            />
            <p className="text-xs text-muted-foreground">
              Adresa de email nu poate fi schimbată
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="fullName">Nume complet</Label>
            <Input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Introdu numele tău complet"
            />
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Aspect
          </CardTitle>
          <CardDescription>
            Alege tema aplicației (se salvează în contul tău)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Tema</Label>
            <Select value={preference} onValueChange={(value) => handleThemeChange(value as ThemePreference)}>
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">Sistem</SelectItem>
                <SelectItem value="light">Luminos</SelectItem>
                <SelectItem value="dark">Întunecat</SelectItem>
              </SelectContent>
            </Select>
            {isSavingTheme && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoadingSpinner size="sm" />
                Se salvează...
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Interest Tags */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Interese
          </CardTitle>
          <CardDescription>
            Selectează categoriile de evenimente care te interesează pentru recomandări personalizate
          </CardDescription>
        </CardHeader>
        <CardContent>
          {allTags.length === 0 ? (
            <p className="text-center text-muted-foreground py-4">
              Nu există etichete disponibile momentan
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {allTags.map((tag) => {
                const isSelected = selectedTagIds.includes(tag.id);
                return (
                  <div
                    key={tag.id}
                    className={`flex items-center space-x-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      isSelected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => handleTagToggle(tag.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleTagToggle(tag.id);
                      }
                    }}
                  >
                    <Checkbox
                      id={`tag-${tag.id}`}
                      checked={isSelected}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.stopPropagation()}
                      onCheckedChange={() => handleTagToggle(tag.id)}
                    />
                    <Label
                      htmlFor={`tag-${tag.id}`}
                      className="cursor-pointer flex-1 text-sm"
                    >
                      {tag.name}
                    </Label>
                  </div>
                );
              })}
            </div>
          )}

          {selectedTagIds.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-sm text-muted-foreground mb-2">
                Interese selectate ({selectedTagIds.length}):
              </p>
              <div className="flex flex-wrap gap-2">
                {allTags
                  .filter(tag => selectedTagIds.includes(tag.id))
                  .map(tag => (
                    <Badge key={tag.id} variant="secondary">
                      <TagIcon className="mr-1 h-3 w-3" />
                      {tag.name}
                    </Badge>
                  ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex flex-wrap justify-end gap-3">
        <Button onClick={handleExport} disabled={isExporting} variant="outline" size="lg">
          {isExporting ? (
            <>
              <LoadingSpinner size="sm" className="mr-2" />
              Se generează...
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export date
            </>
          )}
        </Button>
        <Button onClick={handleSave} disabled={isSaving} size="lg">
          {isSaving ? (
            <>
              <LoadingSpinner size="sm" className="mr-2" />
              Se salvează...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Salvează modificările
            </>
          )}
        </Button>
      </div>

      {/* Privacy */}
      <Card className="mt-6 border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Ștergere cont
          </CardTitle>
          <CardDescription>
            Ștergerea contului este permanentă. Evenimentele organizate pot rămâne publice, dar nu vor mai fi asociate cu contul tău.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            onClick={() => setDeleteDialogOpen(true)}
          >
            Șterge contul
          </Button>
        </CardContent>
      </Card>

      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        setDeleteDialogOpen(open);
        if (!open) {
          setDeletePassword('');
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmă ștergerea contului</DialogTitle>
            <DialogDescription>
              Introdu parola pentru a confirma. Această acțiune nu poate fi anulată.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="deletePassword">Parolă</Label>
            <Input
              id="deletePassword"
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder="Parola contului"
              disabled={isDeleting}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Anulează
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAccount}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Se șterge...
                </>
              ) : (
                'Șterge contul'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default StudentProfilePage;
