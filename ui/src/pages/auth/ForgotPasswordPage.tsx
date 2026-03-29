import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import authService from '@/services/auth.service';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading';
import { Calendar, ArrowLeft, CheckCircle } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

type ForgotPasswordTexts = ReturnType<typeof useI18n>['t']['auth']['forgotAccessCode'];

/** Center auth-page cards inside the shared route shell. */
function ForgotPasswordPageShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
      {children}
    </div>
  );
}

/** Render the shared card header used on the forgot-password flow. */
function ForgotPasswordCardHeader({
  description,
  icon,
  title,
}: Readonly<{
  description: ReactNode;
  icon: ReactNode;
  title: string;
}>) {
  return (
    <CardHeader className="space-y-1 text-center">
      {icon}
      <CardTitle className="text-2xl">{title}</CardTitle>
      <CardDescription>{description}</CardDescription>
    </CardHeader>
  );
}

/** Render the success-state icon shown after requesting a reset link. */
function ForgotPasswordSuccessIcon() {
  return (
    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
      <CheckCircle className="h-6 w-6 text-green-600" />
    </div>
  );
}

/** Render the default icon shown on the forgot-password request form. */
function ForgotPasswordRequestIcon() {
  return (
    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
      <Calendar className="h-6 w-6 text-primary" />
    </div>
  );
}

/** Render the full-width button that returns users to the login page. */
function ForgotPasswordBackToLoginButton({ label }: Readonly<{ label: string }>) {
  return (
    <Button asChild variant="outline" className="w-full">
      <Link to="/login">
        <ArrowLeft className="mr-2 h-4 w-4" />
        {label}
      </Link>
    </Button>
  );
}

/** Render the inline link back to the login screen from the request form. */
function ForgotPasswordInlineBackLink({ label }: Readonly<{ label: string }>) {
  return (
    <Link
      to="/login"
      className="flex items-center justify-center text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="mr-2 h-4 w-4" />
      {label}
    </Link>
  );
}

/** Render the submit button and its loading state on the request form. */
function ForgotPasswordSubmitButton({
  isLoading,
  submitLabel,
  submittingLabel,
}: Readonly<{
  isLoading: boolean;
  submitLabel: string;
  submittingLabel: string;
}>) {
  return (
    <Button type="submit" className="w-full" disabled={isLoading}>
      {isLoading ? (
        <>
          <LoadingSpinner size="sm" className="mr-2" />
          {submittingLabel}
        </>
      ) : (
        submitLabel
      )}
    </Button>
  );
}

/** Render the success card after a password-reset request is submitted. */
function ForgotPasswordSubmittedCard({
  email,
  texts,
}: Readonly<{
  email: string;
  texts: ForgotPasswordTexts;
}>) {
  return (
    <Card className="w-full max-w-md">
      <ForgotPasswordCardHeader
        icon={<ForgotPasswordSuccessIcon />}
        title={texts.submittedTitle}
        description={(
          <>
            {texts.submittedDescriptionPrefix} <strong>{email}</strong>,{' '}
            {texts.submittedDescriptionSuffix}
          </>
        )}
      />
      <CardFooter className="flex flex-col gap-4">
        <ForgotPasswordBackToLoginButton label={texts.backToLogin} />
      </CardFooter>
    </Card>
  );
}

/** Render the forgot-password request form and its field controls. */
function ForgotPasswordFormCard({
  email,
  isLoading,
  onEmailChange,
  onSubmit,
  texts,
}: Readonly<{
  email: string;
  isLoading: boolean;
  onEmailChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  texts: ForgotPasswordTexts;
}>) {
  return (
    <Card className="w-full max-w-md">
      <ForgotPasswordCardHeader
        icon={<ForgotPasswordRequestIcon />}
        title={texts.title}
        description={texts.description}
      />
      <form onSubmit={onSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">{texts.emailLabel}</Label>
            <Input
              id="email"
              type="email"
              placeholder={texts.emailPlaceholder}
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              required
              disabled={isLoading}
            />
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4">
          <ForgotPasswordSubmitButton
            isLoading={isLoading}
            submitLabel={texts.submit}
            submittingLabel={texts.submitting}
          />
          <ForgotPasswordInlineBackLink label={texts.backToLogin} />
        </CardFooter>
      </form>
    </Card>
  );
}

/** Render the forgot-password request screen and handle its submission flow. */
export function ForgotPasswordPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  /** Submit a reset-link request while keeping the response generic for privacy. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await authService.requestPasswordReset(email);
      setIsSubmitted(true);
    } catch {
      // Still show success to prevent email enumeration
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <ForgotPasswordPageShell>
        <ForgotPasswordSubmittedCard email={email} texts={t.auth.forgotAccessCode} />
      </ForgotPasswordPageShell>
    );
  }

  return (
    <ForgotPasswordPageShell>
      <ForgotPasswordFormCard
        email={email}
        isLoading={isLoading}
        onEmailChange={setEmail}
        onSubmit={handleSubmit}
        texts={t.auth.forgotAccessCode}
      />
    </ForgotPasswordPageShell>
  );
}
