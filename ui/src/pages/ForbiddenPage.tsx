import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export function ForbiddenPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <Card className="mx-auto max-w-md">
        <CardContent className="pt-6 text-center">
          <ShieldAlert className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="mb-2 text-xl font-semibold">Acces interzis</h1>
          <p className="mb-6 text-muted-foreground">
            Nu ai permisiunea necesară pentru a accesa această pagină.
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

export default ForbiddenPage;
