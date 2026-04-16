import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';

/**
 * Test helper: event detail skeleton.
 */
export function EventDetailSkeleton() {
  return (
    <div className="container mx-auto px-4 py-8">
      <Skeleton className="mb-6 h-10 w-24" />

      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Skeleton className="mb-6 aspect-video w-full rounded-xl" />

          <div className="mb-6 space-y-2">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-10 w-3/4" />
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <Skeleton className="h-[88px] rounded-lg" />
            <Skeleton className="h-[88px] rounded-lg" />
            <Skeleton className="h-[88px] rounded-lg" />
            <Skeleton className="h-[88px] rounded-lg" />
          </div>

          <Separator className="my-6" />

          <div className="space-y-3">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>

        <div className="space-y-6">
          <Skeleton className="h-[320px] w-full rounded-xl" />
          <Skeleton className="h-[56px] w-full rounded-xl" />
          <Skeleton className="h-[120px] w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
