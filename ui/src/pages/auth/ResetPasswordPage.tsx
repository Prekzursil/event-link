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
import { LoadingSpinner } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { Calendar, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import type { AxiosError } from 'axios';
import { useI18n } from '@/contexts/LanguageContext';

interface ApiError {
  detail?: string;
}

export function ResetPasswordPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const passwordRequirements = [
    { label: t.auth.resetPassword.passwordRequirementMin, met: password.length >= 8 },
    { label: t.auth.resetPassword.passwordRequirementLetters, met: /[a-zA-Z]/.test(password) },
    { label: t.auth.resetPassword.passwordRequirementNumbers, met: /\d/.test(password) },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast({
        title: t.auth.resetPassword.passwordMismatchTitle,
        description: t.auth.resetPassword.passwordMismatchDescription,
        variant: 'destructive',
      });
      return;
    }

    if (!passwordRequirements.every((req) => req.met)) {
      toast({
        title: t.auth.resetPassword.passwordInvalidTitle,
        description: t.auth.resetPassword.passwordInvalidDescription,
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      await authService.resetPassword(token, password, confirmPassword);
      toast({
        title: t.auth.resetPassword.successTitle,
        description: t.auth.resetPassword.successDescription,
        variant: 'success' as const,
      });
      navigate('/login');
    } catch (error) {
      const axiosError = error as AxiosError<ApiError>;
      toast({
        title: t.auth.resetPassword.errorTitle,
        description: axiosError.response?.data?.detail || t.auth.resetPassword.errorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl">{t.auth.resetPassword.invalidTitle}</CardTitle>
            <CardDescription>
              {t.auth.resetPassword.invalidDescription}
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button asChild className="w-full">
              <Link to="/forgot-password">{t.auth.resetPassword.requestNewLink}</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Calendar className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">{t.auth.resetPassword.title}</CardTitle>
          <CardDescription>
            {t.auth.resetPassword.description}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">{t.auth.resetPassword.newPasswordLabel}</Label>
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
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <Eye className="h-4 w-4 text-muted-foreground" />
                  )}
                </Button>
              </div>
              <div className="space-y-1 pt-2">
                {passwordRequirements.map((req, index) => (
                  <div
                    key={index}
                    className={`flex items-center gap-2 text-xs ${
                      req.met ? 'text-green-600' : 'text-muted-foreground'
                    }`}
                  >
                    <CheckCircle2
                      className={`h-3 w-3 ${req.met ? 'text-green-600' : 'text-muted-foreground'}`}
                    />
                    {req.label}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">{t.auth.resetPassword.confirmPasswordLabel}</Label>
              <Input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={isLoading}
              />
              {confirmPassword && password !== confirmPassword && (
                <p className="text-xs text-destructive">{t.auth.resetPassword.passwordMismatchInline}</p>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  {t.auth.resetPassword.submitting}
                </>
              ) : (
                t.auth.resetPassword.submit
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
