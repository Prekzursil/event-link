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

/** Render the input row used to add tags inside the bulk-tag dialog. */
function BulkTagsInputRow({
  inputValue,
  onAddTag,
  onInputChange,
  texts,
}: Pick<Props, 'inputValue' | 'onAddTag' | 'onInputChange' | 'texts'>) {
  return (
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
  );
}

/** Render the removable tag badges inside the bulk-tag dialog. */
function BulkTagsBadgeList({
  onRemoveTag,
  tags,
  texts,
}: Pick<Props, 'onRemoveTag' | 'tags' | 'texts'>) {
  if (tags.length === 0) {
    return null;
  }

  return (
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
  );
}

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
  // skipcq: JS-0415 - the bulk-tag dialog intentionally keeps selection, loading, and action states together.
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{texts.bulk.tagsDialogTitle}</DialogTitle>
          <DialogDescription>{texts.bulk.tagsDialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label>{texts.bulk.tagsLabel}</Label>
          <BulkTagsInputRow
            inputValue={inputValue}
            onAddTag={onAddTag}
            onInputChange={onInputChange}
            texts={texts}
          />
          <BulkTagsBadgeList onRemoveTag={onRemoveTag} tags={tags} texts={texts} />
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
