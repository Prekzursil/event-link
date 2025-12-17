import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SearchX, ArrowLeft } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <Card className="mx-auto max-w-md">
        <CardContent className="pt-6 text-center">
          <SearchX className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="mb-2 text-xl font-semibold">Pagina nu a fost găsită</h1>
          <p className="mb-6 text-muted-foreground">
            Link-ul accesat nu există sau a fost mutat.
          </p>
          <Button asChild>
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Înapoi la evenimente
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default NotFoundPage;
