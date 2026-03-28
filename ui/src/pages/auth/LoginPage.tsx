import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
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
import { useToast } from '@/hooks/use-toast';
import { Calendar, Eye, EyeOff } from 'lucide-react';
import type { AxiosError } from 'axios';
import { useI18n } from '@/contexts/LanguageContext';

interface ApiError {
  detail?: string;
  error?: {
    message?: string;
  };
}

type LoginTexts = ReturnType<typeof useI18n>['t']['auth']['login'];

type LoginAccessCodeFieldProps = Readonly<{
  isLoading: boolean;
  password: string;
  setPassword: (value: string) => void;
  showPassword: boolean;
  texts: LoginTexts;
  toggleShowPassword: () => void;
}>;

type LoginFormCardProps = Readonly<{
  email: string;
  isLoading: boolean;
  onEmailChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  password: string;
  setPassword: (value: string) => void;
  showPassword: boolean;
  texts: LoginTexts;
  toggleShowPassword: () => void;
}>;

/** Extract the most useful message from an API-shaped auth error. */
function describeApiError(error: unknown, fallback: string) {
  const axiosError = error as AxiosError<ApiError>;
  return (
    axiosError.response?.data?.detail ||
    axiosError.response?.data?.error?.message ||
    fallback
  );
}

/** Render the access-code field used on the login screen. */
function LoginAccessCodeField({
  isLoading,
  password,
  setPassword,
  showPassword,
  texts,
  toggleShowPassword,
}: LoginAccessCodeFieldProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label htmlFor="password">{texts.accessCodeLabel}</Label>
        <Link
          to="/forgot-password"
          className="text-sm text-primary hover:underline"
        >
          {texts.forgotAccessCode}
        </Link>
      </div>
      <div className="relative">
        <Input
          id="password"
          type={showPassword ? 'text' : 'password'}
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
          onClick={toggleShowPassword}
        >
          {showPassword ? (
            <EyeOff className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Eye className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </div>
    </div>
  );
}

/** Render the full login card while keeping the page shell shallow. */
function LoginFormCard({
  email,
  isLoading,
  onEmailChange,
  onSubmit,
  password,
  setPassword,
  showPassword,
  texts,
  toggleShowPassword,
}: LoginFormCardProps) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="space-y-1 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Calendar className="h-6 w-6 text-primary" />
        </div>
        <CardTitle className="text-2xl">{texts.title}</CardTitle>
        <CardDescription>{texts.description}</CardDescription>
      </CardHeader>
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
          <LoginAccessCodeField
            isLoading={isLoading}
            password={password}
            setPassword={setPassword}
            showPassword={showPassword}
            texts={texts}
            toggleShowPassword={toggleShowPassword}
          />
        </CardContent>
        <CardFooter className="flex flex-col gap-4">
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                {texts.submitting}
              </>
            ) : (
              texts.submit
            )}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            {texts.noAccount}{' '}
            <Link to="/register" className="text-primary hover:underline">
              {texts.registerLink}
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}

/** Render the login form and handle auth submission side effects. */
export function LoginPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  /** Submit the login credentials and route the user back to the requested page. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await login(email, password);
      toast({
        title: t.auth.login.successTitle,
        description: t.auth.login.successDescription,
        variant: 'success' as const,
      });
      navigate(from, { replace: true });
    } catch (error) {
      toast({
        title: t.auth.login.errorTitle,
        description: describeApiError(error, t.auth.login.errorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
      <LoginFormCard
        email={email}
        isLoading={isLoading}
        onEmailChange={setEmail}
        onSubmit={handleSubmit}
        password={password}
        setPassword={setPassword}
        showPassword={showPassword}
        texts={t.auth.login}
        toggleShowPassword={() => setShowPassword(!showPassword)}
      />
    </div>
  );
}
