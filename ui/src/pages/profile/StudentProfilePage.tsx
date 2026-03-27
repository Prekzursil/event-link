import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type {
  LanguagePreference,
  NotificationPreferences,
  PersonalizationSettings,
  StudyLevel,
  Tag,
  StudentProfile,
  ThemePreference,
  UniversityCatalogItem,
} from '@/types';
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
import { Download, Trash2, User, Tag as TagIcon, Save, Sparkles, GraduationCap, EyeOff, UserX, Mail } from 'lucide-react';
import authService from '@/services/auth.service';

const MAX_YEARS_BY_LEVEL: Record<StudyLevel, number> = {
  bachelor: 4,
  master: 2,
  phd: 4,
  medicine: 6,
};

type TagOptionCardProps = Readonly<{
  tag: Tag;
  isSelected: boolean;
  onToggle: (tagId: number) => void;
}>;

type ProfileTexts = ReturnType<typeof useI18n>['t'];

function TagOptionCard({ tag, isSelected, onToggle }: TagOptionCardProps) {
  return (
    <label
      htmlFor={`tag-${tag.id}`}
      className={`flex w-full items-center space-x-3 rounded-lg border p-3 text-left transition-colors ${
        isSelected ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
      }`}
    >
      <Checkbox
        id={`tag-${tag.id}`}
        checked={isSelected}
        onClick={(e) => {
          e.stopPropagation();
          onToggle(tag.id);
        }}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(tag.id);
          }
        }}
      />
      <Label htmlFor={`tag-${tag.id}`} className="cursor-pointer flex-1 text-sm">
        {tag.name}
      </Label>
    </label>
  );
}

type AcademicProfileCardProps = Readonly<{
  city: string;
  university: string;
  faculty: string;
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  cityOptions: string[];
  universityCatalog: UniversityCatalogItem[];
  facultyOptions: string[];
  selectedUniversity: UniversityCatalogItem | null;
  studyYearOptions: number[];
  t: ProfileTexts;
  onCityChange: (value: string) => void;
  onUniversityChange: (value: string) => void;
  onFacultyChange: (value: string) => void;
  onStudyLevelChange: (value: string) => void;
  onStudyYearChange: (value: string) => void;
}>;

function AcademicProfileCard({
  city,
  university,
  faculty,
  studyLevel,
  studyYear,
  cityOptions,
  universityCatalog,
  facultyOptions,
  selectedUniversity,
  studyYearOptions,
  t,
  onCityChange,
  onUniversityChange,
  onFacultyChange,
  onStudyLevelChange,
  onStudyYearChange,
}: AcademicProfileCardProps) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GraduationCap className="h-5 w-5" />
          {t.profile.academicTitle}
        </CardTitle>
        <CardDescription>{t.profile.academicDescription}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="city">{t.profile.cityLabel}</Label>
            <Input
              id="city"
              value={city}
              onChange={(event) => onCityChange(event.target.value)}
              placeholder={t.profile.cityPlaceholder}
              list="city-options"
            />
            {cityOptions.length > 0 && (
              <datalist id="city-options">
                {cityOptions.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="university">{t.profile.universityLabel}</Label>
            <Input
              id="university"
              value={university}
              onChange={(event) => onUniversityChange(event.target.value)}
              placeholder={t.profile.universityPlaceholder}
              list="university-options"
            />
            {universityCatalog.length > 0 && (
              <datalist id="university-options">
                {universityCatalog.map((item) => (
                  <option key={item.name} value={item.name} />
                ))}
              </datalist>
            )}
            {universityCatalog.length === 0 && (
              <p className="text-xs text-muted-foreground">{t.profile.universityFallbackNote}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="faculty">{t.profile.facultyLabel}</Label>
            <Input
              id="faculty"
              value={faculty}
              onChange={(event) => onFacultyChange(event.target.value)}
              placeholder={
                facultyOptions.length > 0
                  ? t.profile.facultyPlaceholderWithOptions
                  : t.profile.facultyPlaceholderNoOptions
              }
              list={facultyOptions.length > 0 ? 'faculty-options' : undefined}
            />
            {facultyOptions.length > 0 && (
              <datalist id="faculty-options">
                {facultyOptions.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            )}
            {selectedUniversity && facultyOptions.length === 0 && (
              <p className="text-xs text-muted-foreground">{t.profile.facultyFallbackNote}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>{t.profile.studyLevelLabel}</Label>
            <Select value={studyLevel} onValueChange={onStudyLevelChange}>
              <SelectTrigger className="max-w-xs" data-testid="study-level-trigger">
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
              onValueChange={onStudyYearChange}
              disabled={!studyLevel}
            >
              <SelectTrigger className="max-w-xs" data-testid="study-year-trigger">
                <SelectValue
                  placeholder={studyLevel ? t.profile.studyYearPlaceholder : t.profile.studyYearSelectLevelFirst}
                />
              </SelectTrigger>
              <SelectContent>
                {studyYearOptions.map((year) => (
                  <SelectItem key={year} value={String(year)}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

type AppearanceCardProps = Readonly<{
  themePreference: ThemePreference;
  languagePreference: LanguagePreference;
  isSavingTheme: boolean;
  isSavingLanguage: boolean;
  t: ProfileTexts;
  onThemeChange: (preference: ThemePreference) => void;
  onLanguageChange: (preference: LanguagePreference) => void;
}>;

function AppearanceCard({
  themePreference,
  languagePreference,
  isSavingTheme,
  isSavingLanguage,
  t,
  onThemeChange,
  onLanguageChange,
}: AppearanceCardProps) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" />
          {t.profile.preferencesTitle}
        </CardTitle>
        <CardDescription>{t.profile.preferencesDescription}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>{t.theme.label}</Label>
          <Select
            value={themePreference}
            onValueChange={(value) => onThemeChange(value as ThemePreference)}
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
            onValueChange={(value) => onLanguageChange(value as LanguagePreference)}
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
  );
}

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

function PersonalizationSection({
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
            <Sparkles className="h-5 w-5" />
            {t.personalization.profileTitle}
          </CardTitle>
          <CardDescription>{t.personalization.profileDescription}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
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
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium">{t.notifications.weeklyDigestLabel}</div>
              <div className="text-xs text-muted-foreground">{t.notifications.weeklyDigestDescription}</div>
            </div>
            <Checkbox
              checked={Boolean(notificationPrefs?.email_digest_enabled)}
              disabled={isSavingNotifications || !notificationPrefs}
              onCheckedChange={
                notificationPrefs
                  ? (checked) => onNotificationPreferenceChange({ email_digest_enabled: Boolean(checked) })
                  : undefined
              }
            />
          </div>

          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium">{t.notifications.fillingFastLabel}</div>
              <div className="text-xs text-muted-foreground">{t.notifications.fillingFastDescription}</div>
            </div>
            <Checkbox
              checked={Boolean(notificationPrefs?.email_filling_fast_enabled)}
              disabled={isSavingNotifications || !notificationPrefs}
              onCheckedChange={
                notificationPrefs
                  ? (checked) => onNotificationPreferenceChange({ email_filling_fast_enabled: Boolean(checked) })
                  : undefined
              }
            />
          </div>

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

type InterestTagsCardProps = Readonly<{
  allTags: Tag[];
  musicTags: Tag[];
  otherTags: Tag[];
  selectedTagIds: number[];
  t: ProfileTexts;
  onToggleTag: (tagId: number) => void;
}>;

function InterestTagsCard({
  allTags,
  musicTags,
  otherTags,
  selectedTagIds,
  t,
  onToggleTag,
}: InterestTagsCardProps) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          {t.profile.interestsTitle}
        </CardTitle>
        <CardDescription>{t.profile.interestsDescription}</CardDescription>
      </CardHeader>
      <CardContent>
        {allTags.length === 0 ? (
          <p className="py-4 text-center text-muted-foreground">{t.profile.noTags}</p>
        ) : (
          <div className="space-y-6">
            {musicTags.length > 0 && (
              <div className="space-y-3">
                <div className="text-sm font-medium">{t.profile.musicSection}</div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {musicTags.map((tag) => (
                    <TagOptionCard
                      key={tag.id}
                      tag={tag}
                      isSelected={selectedTagIds.includes(tag.id)}
                      onToggle={onToggleTag}
                    />
                  ))}
                </div>
              </div>
            )}
            {otherTags.length > 0 && (
              <div className="space-y-3">
                <div className="text-sm font-medium">{t.profile.otherInterestsSection}</div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {otherTags.map((tag) => (
                    <TagOptionCard
                      key={tag.id}
                      tag={tag}
                      isSelected={selectedTagIds.includes(tag.id)}
                      onToggle={onToggleTag}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {selectedTagIds.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <p className="mb-2 text-sm text-muted-foreground">
              {t.profile.selectedInterests} ({selectedTagIds.length}):
            </p>
            <div className="flex flex-wrap gap-2">
              {allTags
                .filter((tag) => selectedTagIds.includes(tag.id))
                .map((tag) => (
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
  );
}

type ProfileActionsProps = Readonly<{
  isExporting: boolean;
  isSaving: boolean;
  t: ProfileTexts;
  onExport: () => void;
  onSave: () => void;
}>;

function ProfileActions({ isExporting, isSaving, t, onExport, onSave }: ProfileActionsProps) {
  return (
    <div className="flex flex-wrap justify-end gap-3">
      <Button onClick={onExport} disabled={isExporting} variant="outline" size="lg">
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
      <Button onClick={onSave} disabled={isSaving} size="lg">
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
  );
}

type PrivacyCardProps = Readonly<{
  t: ProfileTexts;
  onOpenDeleteDialog: () => void;
}>;

function PrivacyCard({ t, onOpenDeleteDialog }: PrivacyCardProps) {
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

export function StudentProfilePage() {
  const { toast } = useToast();
  const { user, logout, refreshUser } = useAuth();
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, setPreference: setLanguagePreference, language, t } = useI18n();
  const navigate = useNavigate();
  const isStudent = user?.role === 'student';
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
  const [personalization, setPersonalization] = useState<PersonalizationSettings | null>(null);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPreferences | null>(null);
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

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
  const hiddenTags = personalization?.hidden_tags ?? [];
  const blockedOrganizers = personalization?.blocked_organizers ?? [];

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
      setFullName(profileData.full_name ?? '');
      setCity(profileData.city ?? '');
      setUniversity(profileData.university ?? '');
      setFaculty(profileData.faculty ?? '');
      setStudyLevel(profileData.study_level ?? '');
      setStudyYear(profileData.study_year ?? undefined);
      setSelectedTagIds(profileData.interest_tags.map(t => t.id));
      setAllTags(tagsData);

      if (isStudent) {
        const [personalizationData, notificationData] = await Promise.all([
          eventService.getPersonalizationSettings().catch(() => ({ hidden_tags: [], blocked_organizers: [] })),
          eventService.getNotificationPreferences().catch(() => ({
            email_digest_enabled: false,
            email_filling_fast_enabled: false,
          })),
        ]);
        setPersonalization(personalizationData);
        setNotificationPrefs(notificationData);
      } else {
        setPersonalization(null);
        setNotificationPrefs(null);
      }

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
  }, [isStudent, t, toast]);

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

  const handleUniversityChange = (nextUniversity: string) => {
    const normalized = nextUniversity.trim().toLowerCase();
    const match = universityCatalog.find((item) => item.name.toLowerCase() === normalized);
    setUniversity(nextUniversity);
    if (nextUniversity !== university) {
      setFaculty('');
    }
    const matchedCity = typeof match?.city === 'string' && match.city.trim() ? match.city : '';
    if (matchedCity) {
      setCity((previousCity) => (previousCity.trim() ? previousCity : matchedCity));
    }
  };

  const handleStudyLevelChange = (value: string) => {
    const next = value as StudyLevel;
    setStudyLevel(next);
    const max = MAX_YEARS_BY_LEVEL[next];
    if (typeof studyYear === 'number' && (studyYear < 1 || studyYear > max)) {
      setStudyYear(undefined);
    }
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
      setFullName(updatedProfile.full_name ?? '');
      setCity(updatedProfile.city ?? '');
      setUniversity(updatedProfile.university ?? '');
      setFaculty(updatedProfile.faculty ?? '');
      setStudyLevel(updatedProfile.study_level ?? '');
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

  const handleNotificationPreferenceChange = async (
    patch: Partial<NotificationPreferences>,
  ) => {
    const previous = notificationPrefs!;
    const next = { ...previous, ...patch };
    setNotificationPrefs(next);
    setIsSavingNotifications(true);
    try {
      const saved = await eventService.updateNotificationPreferences(patch);
      setNotificationPrefs(saved);
      toast({
        title: t.notifications.savedTitle,
        description: t.notifications.savedDescription,
      });
    } catch {
      setNotificationPrefs(previous);
      toast({
        title: t.common.error,
        description: t.notifications.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingNotifications(false);
    }
  };

  const handleUnhideTag = async (tagId: number) => {
    const currentPersonalization = personalization!;
    try {
      await eventService.unhideTag(tagId);
      setPersonalization({
        ...currentPersonalization,
        hidden_tags: currentPersonalization.hidden_tags.filter((tag) => tag.id !== tagId),
      });
      toast({
        title: t.personalization.tagUnhiddenTitle,
        description: t.personalization.tagUnhiddenDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.tagUnhiddenErrorFallback,
        variant: 'destructive',
      });
    }
  };

  const handleUnblockOrganizer = async (organizerId: number) => {
    const currentPersonalization = personalization!;
    try {
      await eventService.unblockOrganizer(organizerId);
      setPersonalization({
        ...currentPersonalization,
        blocked_organizers: currentPersonalization.blocked_organizers.filter((org) => org.id !== organizerId),
      });
      toast({
        title: t.personalization.organizerUnblockedTitle,
        description: t.personalization.organizerUnblockedDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.organizerUnblockedErrorFallback,
        variant: 'destructive',
      });
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const blob = await eventService.exportMyData();
      const url = globalThis.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const date = new Date().toISOString().slice(0, 10);
      a.download = `eventlink-export-${date}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      globalThis.URL.revokeObjectURL(url);
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

  const closeDeleteDialog = () => {
    setDeleteDialogOpen(false);
  };

  useEffect(() => {
    if (!deleteDialogOpen) {
      setDeletePassword('');
    }
  }, [deleteDialogOpen]);

  const handleDeleteAccount = async () => {
    const password = deletePassword.trim();
    if (!password) {
      toast({
        title: t.profile.deleteAccessCodeMissingTitle,
        description: t.profile.deleteAccessCodeMissingDescription,
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
      closeDeleteDialog();
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

      <AcademicProfileCard
        city={city}
        university={university}
        faculty={faculty}
        studyLevel={studyLevel}
        studyYear={studyYear}
        cityOptions={cityOptions}
        universityCatalog={universityCatalog}
        facultyOptions={facultyOptions}
        selectedUniversity={selectedUniversity}
        studyYearOptions={studyYearOptions}
        t={t}
        onCityChange={setCity}
        onUniversityChange={handleUniversityChange}
        onFacultyChange={setFaculty}
        onStudyLevelChange={handleStudyLevelChange}
        onStudyYearChange={(value) => setStudyYear(Number.parseInt(value, 10))}
      />

      <AppearanceCard
        themePreference={themePreference}
        languagePreference={languagePreference}
        isSavingTheme={isSavingTheme}
        isSavingLanguage={isSavingLanguage}
        t={t}
        onThemeChange={handleThemeChange}
        onLanguageChange={handleLanguageChange}
      />

      {isStudent && (
        <PersonalizationSection
          hiddenTags={hiddenTags}
          blockedOrganizers={blockedOrganizers}
          notificationPrefs={notificationPrefs}
          isSavingNotifications={isSavingNotifications}
          t={t}
          onUnhideTag={handleUnhideTag}
          onUnblockOrganizer={handleUnblockOrganizer}
          onNotificationPreferenceChange={handleNotificationPreferenceChange}
        />
      )}

      <InterestTagsCard
        allTags={allTags}
        musicTags={musicTags}
        otherTags={otherTags}
        selectedTagIds={selectedTagIds}
        t={t}
        onToggleTag={handleTagToggle}
      />

      <ProfileActions
        isExporting={isExporting}
        isSaving={isSaving}
        t={t}
        onExport={handleExport}
        onSave={handleSave}
      />

      <PrivacyCard
        t={t}
        onOpenDeleteDialog={() => setDeleteDialogOpen(true)}
      />

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.profile.deleteDialogTitle}</DialogTitle>
            <DialogDescription>
              {t.profile.deleteDialogDescription}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="deletePassword">{t.profile.deleteAccessCodeLabel}</Label>
            <Input
              id="deletePassword"
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder={t.profile.deleteAccessCodePlaceholder}
              disabled={isDeleting}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeDeleteDialog}
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
