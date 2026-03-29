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

type InterestTagsCardProps = Readonly<{
  allTags: Tag[];
  musicTags: Tag[];
  otherTags: Tag[];
  selectedTagIds: number[];
  t: ProfileTexts;
  onToggleTag: (tagId: number) => void;
}>;

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
