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

interface ApiError {
  detail?: string;
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const passwordRequirements = [
    { label: 'Cel puțin 8 caractere', met: password.length >= 8 },
    { label: 'Conține litere', met: /[a-zA-Z]/.test(password) },
    { label: 'Conține cifre', met: /\d/.test(password) },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast({
        title: 'Eroare',
        description: 'Parolele nu se potrivesc',
        variant: 'destructive',
      });
      return;
    }

    if (!passwordRequirements.every((req) => req.met)) {
      toast({
        title: 'Eroare',
        description: 'Parola nu îndeplinește cerințele',
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      await authService.resetPassword(token, password, confirmPassword);
      toast({
        title: 'Parolă resetată cu succes!',
        description: 'Te poți autentifica acum cu noua parolă.',
        variant: 'success' as const,
      });
      navigate('/login');
    } catch (error) {
      const axiosError = error as AxiosError<ApiError>;
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Token invalid sau expirat',
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
            <CardTitle className="text-2xl">Link invalid</CardTitle>
            <CardDescription>
              Link-ul de resetare este invalid sau a expirat.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button asChild className="w-full">
              <Link to="/forgot-password">Solicită un link nou</Link>
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
          <CardTitle className="text-2xl">Setează parola nouă</CardTitle>
          <CardDescription>
            Introdu noua parolă pentru contul tău
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">Parolă nouă</Label>
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
              <Label htmlFor="confirmPassword">Confirmă parola</Label>
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
                <p className="text-xs text-destructive">Parolele nu se potrivesc</p>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Se resetează...
                </>
              ) : (
                'Resetează parola'
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
