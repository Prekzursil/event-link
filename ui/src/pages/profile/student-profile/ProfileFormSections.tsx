import type {
  LanguagePreference,
  StudyLevel,
  Tag,
  ThemePreference,
  UniversityCatalogItem,
} from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { LoadingSpinner } from '@/components/ui/loading';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Download, GraduationCap, Save, Sparkles, Tag as TagIcon, User } from 'lucide-react';
import type { ProfileTexts } from './shared';

type TagOptionCardProps = Readonly<{
  tag: Tag;
  isSelected: boolean;
  onToggle: (tagId: number) => void;
}>;

/** Render a single selectable interest tag with keyboard and pointer support. */
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

/** Render one datalist-backed input field for academic profile text values. */
function AcademicTextField({
  datalistId,
  label,
  listValues,
  note,
  onChange,
  placeholder,
  testId,
  value,
}: Readonly<{
  datalistId?: string;
  label: string;
  listValues?: string[];
  note?: string;
  onChange: (value: string) => void;
  placeholder: string;
  testId: string;
  value: string;
}>) {
  return (
    <div className="space-y-2">
      <Label htmlFor={testId}>{label}</Label>
      <Input
        id={testId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        list={datalistId}
      />
      {Boolean(listValues?.length) && (
        <datalist id={datalistId}>
          {listValues?.map((option) => (
            <option key={option} value={option} />
          ))}
        </datalist>
      )}
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

/** Render the academic study-level selector. */
function StudyLevelField({
  studyLevel,
  t,
  onStudyLevelChange,
}: Readonly<{
  studyLevel: StudyLevel | '';
  t: ProfileTexts;
  onStudyLevelChange: (value: string) => void;
}>) {
  return (
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
  );
}

/** Render the academic study-year selector with level-aware placeholder copy. */
function StudyYearField({
  studyLevel,
  studyYear,
  studyYearOptions,
  t,
  onStudyYearChange,
}: Readonly<{
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  studyYearOptions: number[];
  t: ProfileTexts;
  onStudyYearChange: (value: string) => void;
}>) {
  return (
    <div className="space-y-2">
      <Label>{t.profile.studyYearLabel}</Label>
      <Select
        value={typeof studyYear === 'number' ? String(studyYear) : ''}
        onValueChange={onStudyYearChange}
        disabled={!studyLevel}
      >
        <SelectTrigger className="max-w-xs" data-testid="study-year-trigger">
          <SelectValue
            placeholder={
              studyLevel ? t.profile.studyYearPlaceholder : t.profile.studyYearSelectLevelFirst
            }
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
  );
}

/** Render the academic profile card with city, university, faculty, and study data. */
export function AcademicProfileCard({
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
  const facultyPlaceholder =
    facultyOptions.length > 0
      ? t.profile.facultyPlaceholderWithOptions
      : t.profile.facultyPlaceholderNoOptions;
  const facultyNote =
    selectedUniversity && facultyOptions.length === 0 ? t.profile.facultyFallbackNote : undefined;

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
          <AcademicTextField
            datalistId={cityOptions.length > 0 ? 'city-options' : undefined}
            label={t.profile.cityLabel}
            listValues={cityOptions}
            onChange={onCityChange}
            placeholder={t.profile.cityPlaceholder}
            testId="city"
            value={city}
          />
          <AcademicTextField
            datalistId={universityCatalog.length > 0 ? 'university-options' : undefined}
            label={t.profile.universityLabel}
            listValues={universityCatalog.map((item) => item.name)}
            note={universityCatalog.length === 0 ? t.profile.universityFallbackNote : undefined}
            onChange={onUniversityChange}
            placeholder={t.profile.universityPlaceholder}
            testId="university"
            value={university}
          />
          <AcademicTextField
            datalistId={facultyOptions.length > 0 ? 'faculty-options' : undefined}
            label={t.profile.facultyLabel}
            listValues={facultyOptions}
            note={facultyNote}
            onChange={onFacultyChange}
            placeholder={facultyPlaceholder}
            testId="faculty"
            value={faculty}
          />
          <StudyLevelField
            studyLevel={studyLevel}
            t={t}
            onStudyLevelChange={onStudyLevelChange}
          />
          <StudyYearField
            studyLevel={studyLevel}
            studyYear={studyYear}
            studyYearOptions={studyYearOptions}
            t={t}
            onStudyYearChange={onStudyYearChange}
          />
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

/** Render one saving indicator row for appearance preference updates. */
function PreferenceSavingState({
  isSaving,
  label,
}: Readonly<{
  isSaving: boolean;
  label: string;
}>) {
  if (!isSaving) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <LoadingSpinner size="sm" />
      {label}
    </div>
  );
}

/** Render the theme-preference selector and loading state. */
function ThemePreferenceField({
  isSavingTheme,
  themePreference,
  t,
  onThemeChange,
}: Readonly<{
  isSavingTheme: boolean;
  themePreference: ThemePreference;
  t: ProfileTexts;
  onThemeChange: (preference: ThemePreference) => void;
}>) {
  return (
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
      <PreferenceSavingState isSaving={isSavingTheme} label={t.profile.saving} />
    </div>
  );
}

/** Render the language-preference selector and loading state. */
function LanguagePreferenceField({
  isSavingLanguage,
  languagePreference,
  t,
  onLanguageChange,
}: Readonly<{
  isSavingLanguage: boolean;
  languagePreference: LanguagePreference;
  t: ProfileTexts;
  onLanguageChange: (preference: LanguagePreference) => void;
}>) {
  return (
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
      <PreferenceSavingState isSaving={isSavingLanguage} label={t.profile.saving} />
    </div>
  );
}

/** Render the appearance-preferences card for theme and language settings. */
export function AppearanceCard({
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
        <ThemePreferenceField
          isSavingTheme={isSavingTheme}
          themePreference={themePreference}
          t={t}
          onThemeChange={onThemeChange}
        />
        <LanguagePreferenceField
          isSavingLanguage={isSavingLanguage}
          languagePreference={languagePreference}
          t={t}
          onLanguageChange={onLanguageChange}
        />
      </CardContent>
    </Card>
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

/** Render one labeled section of tags inside the interests card. */
function TagGroupSection({
  label,
  selectedTagIds,
  tags,
  onToggleTag,
}: Readonly<{
  label: string;
  selectedTagIds: number[];
  tags: Tag[];
  onToggleTag: (tagId: number) => void;
}>) {
  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">{label}</div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {tags.map((tag) => (
          <TagOptionCard
            key={tag.id}
            tag={tag}
            isSelected={selectedTagIds.includes(tag.id)}
            onToggle={onToggleTag}
          />
        ))}
      </div>
    </div>
  );
}

/** Render the selected-interest badge list shown below the available tags. */
function SelectedInterestBadges({
  allTags,
  selectedTagIds,
  t,
}: Readonly<{
  allTags: Tag[];
  selectedTagIds: number[];
  t: ProfileTexts;
}>) {
  return (
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
  );
}

/** Render the interest-tag selection card for the student profile form. */
export function InterestTagsCard({
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
              <TagGroupSection
                label={t.profile.musicSection}
                selectedTagIds={selectedTagIds}
                tags={musicTags}
                onToggleTag={onToggleTag}
              />
            )}
            {otherTags.length > 0 && (
              <TagGroupSection
                label={t.profile.otherInterestsSection}
                selectedTagIds={selectedTagIds}
                tags={otherTags}
                onToggleTag={onToggleTag}
              />
            )}
          </div>
        )}

        {selectedTagIds.length > 0 && (
          <SelectedInterestBadges allTags={allTags} selectedTagIds={selectedTagIds} t={t} />
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

export function ProfileActions({ isExporting, isSaving, t, onExport, onSave }: ProfileActionsProps) {
  // skipcq: JS-0415 - the action row intentionally keeps all save and export button states in one block.
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
