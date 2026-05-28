import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
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
import { useToast } from '@/hooks/use-toast';
import type { AxiosError } from 'axios';
import { useI18n } from '@/contexts/LanguageContext';
import {
  AuthCardHeader,
  AuthPageShell,
  AuthPasswordInput,
  AuthSubmitButton,
  PasswordRequirementsChecklist,
} from './authComponents';
import type { PasswordRequirement } from './authShared';

interface ApiError {
  detail?: string;
}

type ResetStrings = ReturnType<typeof useI18n>['t']['auth']['resetAccessCode'];

/** Compare two access codes without exposing timing differences for early mismatches. */
function constantTimeEquals(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length);
  let mismatch = left.length ^ right.length;

  for (let index = 0; index < length; index += 1) {
    mismatch |= (left.codePointAt(index) || 0) ^ (right.codePointAt(index) || 0);
  }

  return mismatch === 0;
}

/** Return whether the password contains at least one ASCII letter. */
function containsAsciiLetter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = Number(character.codePointAt(0));
    return (codePoint >= 65 && codePoint <= 90) || (codePoint >= 97 && codePoint <= 122);
  });
}

/** Return whether the password contains at least one digit. */
function containsDigit(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = Number(character.codePointAt(0));
    return codePoint >= 48 && codePoint <= 57;
  });
}

/** Build the localized password requirement checklist. */
function buildPasswordRequirements(
  password: string,
  resetStrings: ReturnType<typeof useI18n>['t']['auth']['resetAccessCode'],
): PasswordRequirement[] {
  return [
    { label: resetStrings.accessCodeRequirementMin, met: password.length >= 8 },
    { label: resetStrings.accessCodeRequirementLetters, met: containsAsciiLetter(password) },
    { label: resetStrings.accessCodeRequirementNumbers, met: containsDigit(password) },
  ];
}

/** Show one localized reset-password toast. */
function showToast(
  toast: ReturnType<typeof useToast>['toast'],
  title: string,
  description: string,
  variant: 'destructive' | 'success',
): void {
  toast({ title, description, variant });
}

/** Render the invalid-link card content that sends users back to the request flow. */
function ResetAccessCodeInvalidCard({
  invalidTitle,
  invalidDescription,
  requestNewLink,
}: Readonly<{
  invalidTitle: string;
  invalidDescription: string;
  requestNewLink: string;
}>) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="space-y-1 text-center">
        <CardTitle className="text-2xl">{invalidTitle}</CardTitle>
        <CardDescription>{invalidDescription}</CardDescription>
      </CardHeader>
      <CardFooter>
        <Button asChild className="w-full">
          <Link to="/forgot-password">{requestNewLink}</Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

/** Render the invalid reset-link state with a path back to the request form. */
function ResetAccessCodeInvalidLink({
  invalidTitle,
  invalidDescription,
  requestNewLink,
}: Readonly<{
  invalidTitle: string;
  invalidDescription: string;
  requestNewLink: string;
}>) {
  return (
    <AuthPageShell>
      <ResetAccessCodeInvalidCard
        invalidTitle={invalidTitle}
        invalidDescription={invalidDescription}
        requestNewLink={requestNewLink}
      />
    </AuthPageShell>
  );
}

/** Render the password and confirmation fields for the reset-password form. */
function ResetAccessCodeFields(
  props: Readonly<{
    confirmPassword: string;
    isLoading: boolean;
    onConfirmPasswordChange: (value: string) => void;
    onPasswordChange: (value: string) => void;
    onToggleShowPassword: () => void;
    password: string;
    requirements: PasswordRequirement[];
    resetStrings: ResetStrings;
    showPassword: boolean;
  }>,
) {
  const {
    confirmPassword,
    isLoading,
    onConfirmPasswordChange,
    onPasswordChange,
    onToggleShowPassword,
    password,
    requirements,
    resetStrings,
    showPassword,
  } = props;
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="password">{resetStrings.newAccessCodeLabel}</Label>
        <AuthPasswordInput
          disabled={isLoading}
          id="password"
          onChange={(event) => onPasswordChange(event.target.value)}
          onToggleShowPassword={onToggleShowPassword}
          showPassword={showPassword}
          value={password}
        />
        <PasswordRequirementsChecklist requirements={requirements} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirmPassword">{resetStrings.confirmAccessCodeLabel}</Label>
        <Input
          id="confirmPassword"
          type={showPassword ? 'text' : 'password'}
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(event) => onConfirmPasswordChange(event.target.value)}
          required
          disabled={isLoading}
        />
        {confirmPassword && !constantTimeEquals(password, confirmPassword) ? (
          <p className="text-xs text-destructive">{resetStrings.accessCodeMismatchInline}</p>
        ) : null}
      </div>
    </>
  );
}

/** Render the footer submit button for the reset-password form. */
function ResetPasswordFormFooter({
  isLoading,
  resetStrings,
}: Readonly<{
  isLoading: boolean;
  resetStrings: ResetStrings;
}>) {
  return (
    <CardFooter>
      <AuthSubmitButton
        isLoading={isLoading}
        submitLabel={resetStrings.submit}
        submittingLabel={resetStrings.submitting}
      />
    </CardFooter>
  );
}

/** Render the reset-access-code screen and submit the new access code. */
export function ResetPasswordPage() {
  const { t } = useI18n();
  const resetStrings = t.auth.resetAccessCode;
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();
  const passwordRequirements = buildPasswordRequirements(password, resetStrings);

  /** Submit the replacement access code after validating the current reset token. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!constantTimeEquals(password, confirmPassword)) {
      showToast(
        toast,
        resetStrings.accessCodeMismatchTitle,
        resetStrings.accessCodeMismatchDescription,
        'destructive',
      );
      return;
    }

    if (!passwordRequirements.every((req) => req.met)) {
      showToast(
        toast,
        resetStrings.accessCodeInvalidTitle,
        resetStrings.accessCodeInvalidDescription,
        'destructive',
      );
      return;
    }

    setIsLoading(true);

    try {
      await authService.resetPassword(token, password, confirmPassword);
      showToast(toast, resetStrings.successTitle, resetStrings.successDescription, 'success');
      navigate('/login');
    } catch (error) {
      const axiosError = error as AxiosError<ApiError>;
      showToast(
        toast,
        resetStrings.errorTitle,
        axiosError.response?.data?.detail || resetStrings.errorFallback,
        'destructive',
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <ResetAccessCodeInvalidLink
        invalidTitle={resetStrings.invalidTitle}
        invalidDescription={resetStrings.invalidDescription}
        requestNewLink={resetStrings.requestNewLink}
      />
    );
  }

  return (
    <AuthPageShell>
      <Card className="w-full max-w-md">
        <AuthCardHeader title={resetStrings.title} description={resetStrings.description} />
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <ResetAccessCodeFields
              confirmPassword={confirmPassword}
              isLoading={isLoading}
              onConfirmPasswordChange={setConfirmPassword}
              onPasswordChange={setPassword}
              onToggleShowPassword={() => setShowPassword((current) => !current)}
              password={password}
              requirements={passwordRequirements}
              resetStrings={resetStrings}
              showPassword={showPassword}
            />
          </CardContent>
          <ResetPasswordFormFooter isLoading={isLoading} resetStrings={resetStrings} />
        </form>
      </Card>
    </AuthPageShell>
  );
}
