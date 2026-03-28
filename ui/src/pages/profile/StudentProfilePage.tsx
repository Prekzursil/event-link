import { User } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingPage } from '@/components/ui/loading';
import {
  AcademicProfileCard,
  AppearanceCard,
  InterestTagsCard,
  ProfileActions,
} from './student-profile/ProfileFormSections';
import {
  DeleteAccountDialog,
  PersonalizationSection,
  PrivacyCard,
} from './student-profile/ProfileMetaSections';
import { useStudentProfileController } from './student-profile/useStudentProfileController';

export function StudentProfilePage() {
  const controller = useStudentProfileController();

  if (controller.isLoading) {
    return <LoadingPage message={controller.t.profile.loading} />;
  }

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">{controller.t.profile.title}</h1>
        <p className="text-muted-foreground">{controller.t.profile.subtitle}</p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            {controller.t.profile.basicInfoTitle}
          </CardTitle>
          <CardDescription>{controller.t.profile.basicInfoDescription}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">{controller.t.profile.emailLabel}</Label>
            <Input id="email" value={controller.profile?.email || ''} disabled className="bg-muted" />
            <p className="text-xs text-muted-foreground">{controller.t.profile.emailNote}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="fullName">{controller.t.profile.fullNameLabel}</Label>
            <Input
              id="fullName"
              value={controller.fullName}
              onChange={(event) => controller.setFullName(event.target.value)}
              placeholder={controller.t.profile.fullNamePlaceholder}
            />
          </div>
        </CardContent>
      </Card>

      <AcademicProfileCard
        city={controller.city}
        university={controller.university}
        faculty={controller.faculty}
        studyLevel={controller.studyLevel}
        studyYear={controller.studyYear}
        cityOptions={controller.cityOptions}
        universityCatalog={controller.universityCatalog}
        facultyOptions={controller.facultyOptions}
        selectedUniversity={controller.selectedUniversity}
        studyYearOptions={controller.studyYearOptions}
        t={controller.t}
        onCityChange={controller.setCity}
        onUniversityChange={controller.handleUniversityChange}
        onFacultyChange={controller.setFaculty}
        onStudyLevelChange={controller.handleStudyLevelChange}
        onStudyYearChange={(value) => controller.setStudyYear(Number.parseInt(value, 10))}
      />

      <AppearanceCard
        themePreference={controller.themePreference}
        languagePreference={controller.languagePreference}
        isSavingTheme={controller.isSavingTheme}
        isSavingLanguage={controller.isSavingLanguage}
        t={controller.t}
        onThemeChange={controller.handleThemeChange}
        onLanguageChange={controller.handleLanguageChange}
      />

      {controller.isStudent && (
        <PersonalizationSection
          hiddenTags={controller.hiddenTags}
          blockedOrganizers={controller.blockedOrganizers}
          notificationPrefs={controller.notificationPrefs}
          isSavingNotifications={controller.isSavingNotifications}
          t={controller.t}
          onUnhideTag={controller.handleUnhideTag}
          onUnblockOrganizer={controller.handleUnblockOrganizer}
          onNotificationPreferenceChange={controller.handleNotificationPreferenceChange}
        />
      )}

      <InterestTagsCard
        allTags={controller.allTags}
        musicTags={controller.musicTags}
        otherTags={controller.otherTags}
        selectedTagIds={controller.selectedTagIds}
        t={controller.t}
        onToggleTag={controller.handleTagToggle}
      />

      <ProfileActions
        isExporting={controller.isExporting}
        isSaving={controller.isSaving}
        t={controller.t}
        onExport={controller.handleExport}
        onSave={controller.handleSave}
      />

      <PrivacyCard t={controller.t} onOpenDeleteDialog={() => controller.setDeleteDialogOpen(true)} />

      <DeleteAccountDialog
        open={controller.deleteDialogOpen}
        deletePassword={controller.deletePassword}
        isDeleting={controller.isDeleting}
        t={controller.t}
        onOpenChange={controller.setDeleteDialogOpen}
        onDeletePasswordChange={controller.setDeletePassword}
        onCancel={controller.closeDeleteDialog}
        onDelete={controller.handleDeleteAccount}
      />
    </div>
  );
}

export default StudentProfilePage;
