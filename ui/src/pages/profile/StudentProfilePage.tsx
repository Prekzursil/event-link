import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { StudyLevel, Tag, StudentProfile, UniversityCatalogItem } from '@/types';
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
import { useI18n } from '@/contexts/LanguageContext';
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
import { Download, Trash2, User, Tag as TagIcon, Save, Sparkles, GraduationCap } from 'lucide-react';
import authService from '@/services/auth.service';
import type { LanguagePreference, ThemePreference } from '@/types';

const MAX_YEARS_BY_LEVEL: Record<StudyLevel, number> = {
  bachelor: 4,
  master: 2,
  phd: 4,
  medicine: 6,
};

export function StudentProfilePage() {
  const { toast } = useToast();
  const { logout, refreshUser } = useAuth();
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, setPreference: setLanguagePreference, language, t } = useI18n();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSavingTheme, setIsSavingTheme] = useState(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState(false);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [universityCatalog, setUniversityCatalog] = useState<UniversityCatalogItem[]>([]);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [city, setCity] = useState('');
  const [university, setUniversity] = useState('');
  const [faculty, setFaculty] = useState('');
  const [studyLevel, setStudyLevel] = useState<StudyLevel | ''>('');
  const [studyYear, setStudyYear] = useState<number | undefined>(undefined);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);

  const musicInterestNames = useMemo(
    () =>
      new Set([
        'Muzică',
        'Rock',
        'Pop',
        'Hip-Hop',
        'EDM',
        'Jazz',
        'Clasică',
        'Folk',
        'Metal',
      ]),
    [],
  );

  const musicTags = useMemo(
    () => allTags.filter((tag) => musicInterestNames.has(tag.name)),
    [allTags, musicInterestNames],
  );

  const otherTags = useMemo(
    () => allTags.filter((tag) => !musicInterestNames.has(tag.name)),
    [allTags, musicInterestNames],
  );

  const renderTagOption = (tag: Tag) => {
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
        <Label htmlFor={`tag-${tag.id}`} className="cursor-pointer flex-1 text-sm">
          {tag.name}
        </Label>
      </div>
    );
  };

  const selectedUniversity = useMemo(() => {
    const normalized = university.trim().toLowerCase();
    if (!normalized) return null;
    return (
      universityCatalog.find((item) => item.name.toLowerCase() === normalized) ??
      null
    );
  }, [university, universityCatalog]);

  const facultyOptions = useMemo(
    () => selectedUniversity?.faculties ?? [],
    [selectedUniversity],
  );

  const cityOptions = useMemo(() => {
    const set = new Set<string>();
    for (const item of universityCatalog) {
      if (item.city) set.add(item.city);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, language));
  }, [language, universityCatalog]);

  const studyYearOptions = useMemo(() => {
    if (!studyLevel) return [];
    const max = MAX_YEARS_BY_LEVEL[studyLevel];
    return Array.from({ length: max }, (_, idx) => idx + 1);
  }, [studyLevel]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [profileData, tagsData] = await Promise.all([
        eventService.getStudentProfile(),
        eventService.getAllTags(),
      ]);
      setProfile(profileData);
      setFullName(profileData.full_name || '');
      setCity(profileData.city || '');
      setUniversity(profileData.university || '');
      setFaculty(profileData.faculty || '');
      setStudyLevel(profileData.study_level || '');
      setStudyYear(profileData.study_year ?? undefined);
      setSelectedTagIds(profileData.interest_tags.map(t => t.id));
      setAllTags(tagsData);

      try {
        const catalog = await eventService.getUniversityCatalog();
        setUniversityCatalog(catalog);
      } catch {
        setUniversityCatalog([]);
      }
    } catch (error) {
      console.error('Failed to load profile:', error);
      toast({
        title: t.profile.loadErrorTitle,
        description: t.profile.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [t, toast]);

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
        full_name: fullName.trim() ? fullName.trim() : undefined,
        city: city.trim(),
        university: university.trim(),
        faculty: faculty.trim(),
        study_level: studyLevel || undefined,
        study_year: typeof studyYear === 'number' ? studyYear : undefined,
        interest_tag_ids: selectedTagIds,
      });
      setProfile(updatedProfile);
      setFullName(updatedProfile.full_name || '');
      setCity(updatedProfile.city || '');
      setUniversity(updatedProfile.university || '');
      setFaculty(updatedProfile.faculty || '');
      setStudyLevel(updatedProfile.study_level || '');
      setStudyYear(updatedProfile.study_year ?? undefined);
      toast({
        title: t.profile.saveSuccessTitle,
        description: t.profile.saveSuccessDescription,
      });
    } catch (error) {
      console.error('Failed to save profile:', error);
      toast({
        title: t.profile.saveErrorTitle,
        description: t.profile.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleThemeChange = async (nextPreference: ThemePreference) => {
    const prev = themePreference;
    setThemePreference(nextPreference);
    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
      toast({
        title: t.theme.savedTitle,
        description: t.theme.savedDescription,
      });
    } catch {
      setThemePreference(prev);
      toast({
        title: t.theme.saveErrorTitle,
        description: t.theme.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingTheme(false);
    }
  };

  const handleLanguageChange = async (nextPreference: LanguagePreference) => {
    const prev = languagePreference;
    setLanguagePreference(nextPreference);
    setIsSavingLanguage(true);
    try {
      await authService.updateLanguagePreference(nextPreference);
      await refreshUser();
      toast({
        title: t.language.savedTitle,
        description: t.language.savedDescription,
      });
    } catch {
      setLanguagePreference(prev);
      toast({
        title: t.language.saveErrorTitle,
        description: t.language.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingLanguage(false);
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
        title: t.profile.exportGeneratedTitle,
        description: t.profile.exportGeneratedDescription,
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      toast({
        title: t.profile.exportErrorTitle,
        description: t.profile.exportErrorDescription,
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
        title: t.profile.deletePasswordMissingTitle,
        description: t.profile.deletePasswordMissingDescription,
        variant: 'destructive',
      });
      return;
    }

    setIsDeleting(true);
    try {
      await eventService.deleteMyAccount(password);
      toast({
        title: t.profile.deletedTitle,
        description: t.profile.deletedDescription,
      });
      setDeleteDialogOpen(false);
      setDeletePassword('');
      logout();
      navigate('/');
    } catch (error: unknown) {
      console.error('Failed to delete account:', error);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.profile.deleteErrorTitle,
        description: axiosError.response?.data?.detail || t.profile.deleteErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return <LoadingPage message={t.profile.loading} />;
  }

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">{t.profile.title}</h1>
        <p className="text-muted-foreground">
          {t.profile.subtitle}
        </p>
      </div>

      {/* Profile Info */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            {t.profile.basicInfoTitle}
          </CardTitle>
          <CardDescription>
            {t.profile.basicInfoDescription}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">{t.profile.emailLabel}</Label>
            <Input
              id="email"
              value={profile?.email || ''}
              disabled
              className="bg-muted"
            />
            <p className="text-xs text-muted-foreground">
              {t.profile.emailNote}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="fullName">{t.profile.fullNameLabel}</Label>
            <Input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t.profile.fullNamePlaceholder}
            />
          </div>
        </CardContent>
      </Card>

      {/* Academic Profile */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GraduationCap className="h-5 w-5" />
            {t.profile.academicTitle}
          </CardTitle>
          <CardDescription>
            {t.profile.academicDescription}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="city">{t.profile.cityLabel}</Label>
              <Input
                id="city"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder={t.profile.cityPlaceholder}
                list="city-options"
              />
              {cityOptions.length > 0 && (
                <datalist id="city-options">
                  {cityOptions.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="university">{t.profile.universityLabel}</Label>
              <Input
                id="university"
                value={university}
                onChange={(e) => {
                  const next = e.target.value;
                  const prev = university;
                  setUniversity(next);
                  if (next !== prev) {
                    setFaculty('');
                  }
                  const match = universityCatalog.find((item) => item.name.toLowerCase() === next.trim().toLowerCase());
                  if (match?.city && !city.trim()) {
                    setCity(match.city);
                  }
                }}
                placeholder={t.profile.universityPlaceholder}
                list="university-options"
              />
              {universityCatalog.length > 0 && (
                <datalist id="university-options">
                  {universityCatalog.map((u) => (
                    <option key={u.name} value={u.name} />
                  ))}
                </datalist>
              )}
              {universityCatalog.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  {t.profile.universityFallbackNote}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="faculty">{t.profile.facultyLabel}</Label>
              <Input
                id="faculty"
                value={faculty}
                onChange={(e) => setFaculty(e.target.value)}
                placeholder={
                  facultyOptions.length > 0 ? t.profile.facultyPlaceholderWithOptions : t.profile.facultyPlaceholderNoOptions
                }
                list={facultyOptions.length > 0 ? 'faculty-options' : undefined}
              />
              {facultyOptions.length > 0 && (
                <datalist id="faculty-options">
                  {facultyOptions.map((f) => (
                    <option key={f} value={f} />
                  ))}
                </datalist>
              )}
              {selectedUniversity && facultyOptions.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  {t.profile.facultyFallbackNote}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>{t.profile.studyLevelLabel}</Label>
              <Select
                value={studyLevel}
                onValueChange={(value) => {
                  const next = value as StudyLevel;
                  setStudyLevel(next);
                  const max = MAX_YEARS_BY_LEVEL[next];
                  if (typeof studyYear === 'number' && (studyYear < 1 || studyYear > max)) {
                    setStudyYear(undefined);
                  }
                }}
              >
                <SelectTrigger className="max-w-xs">
                  <SelectValue placeholder={t.profile.studyLevelPlaceholder} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bachelor">{t.profile.studyLevelBachelor}</SelectItem>
                  <SelectItem value="master">{t.profile.studyLevelMaster}</SelectItem>
                  <SelectItem value="phd">{t.profile.studyLevelPhd}</SelectItem>
                  <SelectItem value="medicine">{t.profile.studyLevelMedicine}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t.profile.studyYearLabel}</Label>
              <Select
                value={typeof studyYear === 'number' ? String(studyYear) : ''}
                onValueChange={(value) => setStudyYear(parseInt(value))}
                disabled={!studyLevel}
              >
                <SelectTrigger className="max-w-xs">
                  <SelectValue
                    placeholder={studyLevel ? t.profile.studyYearPlaceholder : t.profile.studyYearSelectLevelFirst}
                  />
                </SelectTrigger>
                <SelectContent>
                  {studyYearOptions.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            {t.profile.preferencesTitle}
          </CardTitle>
          <CardDescription>
            {t.profile.preferencesDescription}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>{t.theme.label}</Label>
            <Select
              value={themePreference}
              onValueChange={(value) => handleThemeChange(value as ThemePreference)}
              disabled={isSavingTheme}
            >
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">{t.theme.system}</SelectItem>
                <SelectItem value="light">{t.theme.light}</SelectItem>
                <SelectItem value="dark">{t.theme.dark}</SelectItem>
              </SelectContent>
            </Select>
            {isSavingTheme && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoadingSpinner size="sm" />
                {t.profile.saving}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label>{t.language.label}</Label>
            <Select
              value={languagePreference}
              onValueChange={(value) => handleLanguageChange(value as LanguagePreference)}
              disabled={isSavingLanguage}
            >
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">{t.language.system}</SelectItem>
                <SelectItem value="ro">{t.language.ro}</SelectItem>
                <SelectItem value="en">{t.language.en}</SelectItem>
              </SelectContent>
            </Select>
            {isSavingLanguage && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoadingSpinner size="sm" />
                {t.profile.saving}
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
            {t.profile.interestsTitle}
          </CardTitle>
          <CardDescription>
            {t.profile.interestsDescription}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {allTags.length === 0 ? (
            <p className="text-center text-muted-foreground py-4">
              {t.profile.noTags}
            </p>
          ) : (
            <div className="space-y-6">
              {musicTags.length > 0 && (
                <div className="space-y-3">
                  <div className="text-sm font-medium">{t.profile.musicSection}</div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {musicTags.map(renderTagOption)}
                  </div>
                </div>
              )}
              {otherTags.length > 0 && (
                <div className="space-y-3">
                  <div className="text-sm font-medium">{t.profile.otherInterestsSection}</div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {otherTags.map(renderTagOption)}
                  </div>
                </div>
              )}
            </div>
          )}

          {selectedTagIds.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-sm text-muted-foreground mb-2">
                {t.profile.selectedInterests} ({selectedTagIds.length}):
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
              {t.profile.exportGenerating}
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              {t.profile.exportData}
            </>
          )}
        </Button>
        <Button onClick={handleSave} disabled={isSaving} size="lg">
          {isSaving ? (
            <>
              <LoadingSpinner size="sm" className="mr-2" />
              {t.profile.saving}
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              {t.profile.saveChanges}
            </>
          )}
        </Button>
      </div>

      {/* Privacy */}
      <Card className="mt-6 border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            {t.profile.privacyTitle}
          </CardTitle>
          <CardDescription>
            {t.profile.privacyDescription}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            onClick={() => setDeleteDialogOpen(true)}
          >
            {t.profile.deleteAccount}
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
            <DialogTitle>{t.profile.deleteDialogTitle}</DialogTitle>
            <DialogDescription>
              {t.profile.deleteDialogDescription}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="deletePassword">{t.profile.deletePasswordLabel}</Label>
            <Input
              id="deletePassword"
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder={t.profile.deletePasswordPlaceholder}
              disabled={isDeleting}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAccount}
              disabled={isDeleting}
            >
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
    </div>
  );
}

export default StudentProfilePage;
