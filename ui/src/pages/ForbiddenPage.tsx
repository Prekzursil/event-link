import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

export function ForbiddenPage() {
  const { t } = useI18n();
  return (
    <div className="container mx-auto px-4 py-16">
      <Card className="mx-auto max-w-md">
        <CardContent className="pt-6 text-center">
          <ShieldAlert className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="mb-2 text-xl font-semibold">{t.pages.forbidden.title}</h1>
          <p className="mb-6 text-muted-foreground">
            {t.pages.forbidden.description}
          </p>
          <Button asChild>
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t.pages.forbidden.backToEvents}
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default ForbiddenPage;
