import type { UiStrings } from '@/i18n/strings';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

type Props = Readonly<{
  cancelText: string;
  inputValue: string;
  isBusy: boolean;
  onAddTag: () => void;
  onApply: () => void;
  onInputChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  onRemoveTag: (tag: string) => void;
  open: boolean;
  tags: string[];
  texts: UiStrings['organizerDashboard'];
}>;

export function OrganizerBulkTagsDialog({
  cancelText,
  inputValue,
  isBusy,
  onAddTag,
  onApply,
  onInputChange,
  onOpenChange,
  onRemoveTag,
  open,
  tags,
  texts,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{texts.bulk.tagsDialogTitle}</DialogTitle>
          <DialogDescription>{texts.bulk.tagsDialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label>{texts.bulk.tagsLabel}</Label>
          <div className="flex gap-2">
            <Input
              value={inputValue}
              onChange={(event) => onInputChange(event.target.value)}
              placeholder={texts.bulk.tagsPlaceholder}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  onAddTag();
                }
              }}
            />
            <Button type="button" variant="outline" onClick={onAddTag}>
              {texts.bulk.addTag}
            </Button>
          </div>
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {tags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="cursor-pointer"
                  onClick={() => onRemoveTag(tag)}
                  title={texts.bulk.removeTagHint}
                >
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {cancelText}
          </Button>
          <Button onClick={onApply} disabled={isBusy}>
            {texts.bulk.applyTags}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
