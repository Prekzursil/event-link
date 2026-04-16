import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SearchX, ArrowLeft } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

/** Render the back-to-events call to action for the not-found page. */
/**
 * Test helper: not found back button.
 */
function NotFoundBackButton({ label }: Readonly<{ label: string }>) {
  return (
    <Button asChild>
      <Link to="/">
        <ArrowLeft className="mr-2 h-4 w-4" />
        {label}
      </Link>
    </Button>
  );
}

/** Render the not-found page shown for unmatched routes. */
export function NotFoundPage() {
  const { t } = useI18n();
  const pageAction = <NotFoundBackButton label={t.pages.notFound.backToEvents} />;

  // skipcq: JS-0415 - the page intentionally keeps the icon, copy, and CTA in one compact layout.
  return (
    <div className="container mx-auto px-4 py-16">
      <Card className="mx-auto max-w-md">
        <CardContent className="pt-6 text-center">
          <SearchX className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="mb-2 text-xl font-semibold">{t.pages.notFound.title}</h1>
          <p className="mb-6 text-muted-foreground">
            {t.pages.notFound.description}
          </p>
          {pageAction}
        </CardContent>
      </Card>
    </div>
  );
}

export default NotFoundPage;
