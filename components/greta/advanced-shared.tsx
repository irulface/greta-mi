'use client';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Row, Picker } from './shared';
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="ai3-field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function Options({
  rows,
  value,
  onChange,
  placeholder = 'Select…',
}: {
  rows: Row[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <Picker
      value={value}
      onChange={onChange}
      options={[
        { value: '', label: placeholder },
        ...rows.map((r) => ({
          value: r.id,
          label: r.name || r.title || r.email || r.id,
        })),
      ]}
    />
  );
}
export function JsonDownload({ value, name }: { value: Row; name: string }) {
  return (
    <Button
      variant="outline"
      onClick={() => {
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(value, null, 2)], {
            type: 'application/json',
          }),
        );
        const a = document.createElement('a');
        a.href = url;
        a.download = name + '.json';
        a.click();
        URL.revokeObjectURL(url);
      }}
    >
      <Download size={16} />
      Export snapshot
    </Button>
  );
}
