'use client';
import { useEffect, useState } from 'react';
import {
  FileText,
  Building2,
  FolderClosed,
  ArrowRight,
  ClipboardList,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Row, api, FilterInput, ErrorBox, Empty } from './shared';
export function GlobalSearch({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (r: Row) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    let active = true;
    const timer = setTimeout(() => {
      api('/search?q=' + encodeURIComponent(query))
        .then((r) => {
          if (active) {
            setResults(r);
            setError('');
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, open]);
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent className="large-dialog">
        <DialogTitle>Search your intelligence</DialogTitle>
        <DialogDescription>
          RFIs, suppliers, categories, documents, and market data.
        </DialogDescription>
        <FilterInput
          value={query}
          onChange={setQuery}
          placeholder="Search across your authorized workspace…"
        />
        <ErrorBox error={error} />
        <div className="global-results">
          {results.map((r) => {
            const Icon =
              r.kind === 'supplier'
                ? Building2
                : r.kind === 'rfi'
                  ? ClipboardList
                  : r.kind === 'category'
                    ? FolderClosed
                    : FileText;
            return (
              <button
                key={r.kind + r.id}
                onClick={() => {
                  onSelect(r);
                  onClose();
                }}
              >
                <Icon size={20} />
                <div>
                  <small>{r.kind.toUpperCase()}</small>
                  <strong>{r.title}</strong>
                </div>
                <ArrowRight size={16} />
              </button>
            );
          })}
          {!results.length && !error && (
            <Empty
              title="No matching results"
              text="Try a material name, supplier, RFI reference, or category."
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
