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

/** Render the heading copy and spacing for the student profile page. */
function StudentProfileHeader({
  subtitle,
  title,
}: Readonly<{ subtitle: string; title: string }>) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="text-muted-foreground">{subtitle}</p>
    </div>
  );
}

type StudentBasicInfoCardProps = Readonly<{
  email: string;
  emailLabel: string;
  emailNote: string;
  fullName: string;
  fullNameLabel: string;
  fullNamePlaceholder: string;
  onFullNameChange: (value: string) => void;
  sectionDescription: string;
  sectionTitle: string;
}>;

/** Render the immutable email field and editable full-name field for a profile. */
function StudentBasicInfoCard(props: StudentBasicInfoCardProps) {
  const {
    email,
    emailLabel,
    emailNote,
    fullName,
    fullNameLabel,
    fullNamePlaceholder,
    onFullNameChange,
    sectionDescription,
    sectionTitle,
  } = props;

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" />
          {sectionTitle}
        </CardTitle>
        <CardDescription>{sectionDescription}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">{emailLabel}</Label>
          <Input id="email" value={email} disabled className="bg-muted" />
          <p className="text-xs text-muted-foreground">{emailNote}</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="fullName">{fullNameLabel}</Label>
          <Input
            id="fullName"
            value={fullName}
            onChange={(event) => onFullNameChange(event.target.value)}
            placeholder={fullNamePlaceholder}
          />
        </div>
      </CardContent>
    </Card>
  );
}

/** Render the complete student profile form and personalization sections. */
export function StudentProfilePage() {
  const controller = useStudentProfileController();

  if (controller.isLoading) {
    return <LoadingPage message={controller.t.profile.loading} />;
  }

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <StudentProfileHeader
        subtitle={controller.t.profile.subtitle}
        title={controller.t.profile.title}
      />
      <StudentBasicInfoCard
        email={controller.profile?.email || ''}
        emailLabel={controller.t.profile.emailLabel}
        emailNote={controller.t.profile.emailNote}
        fullName={controller.fullName}
        fullNameLabel={controller.t.profile.fullNameLabel}
        fullNamePlaceholder={controller.t.profile.fullNamePlaceholder}
        onFullNameChange={controller.setFullName}
        sectionDescription={controller.t.profile.basicInfoDescription}
        sectionTitle={controller.t.profile.basicInfoTitle}
      />

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
