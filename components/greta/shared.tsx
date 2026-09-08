'use client';
import { Search, LoaderCircle, FileSearch, AlertCircle } from 'lucide-react';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
export type Row = Record<string, any>;
export type Workspace = {
  user: Row;
  rfis: Row[];
  suppliers: Row[];
  categories: Row[];
  prices: Row[];
  events: Row[];
  documents: Row[];
  responses: Row[];
  conversations: Row[];
  demo: boolean;
};
export const emptyWorkspace: Workspace = {
  user: {
    name: 'Aditya Pratama',
    role: 'Buyer',
    region: 'Region 1',
    permissions: [],
  },
  rfis: [],
  suppliers: [],
  categories: [],
  prices: [],
  events: [],
  documents: [],
  responses: [],
  conversations: [],
  demo: true,
};
export async function api(path: string, body?: any, method?: string) {
  const response = await fetch('/api/v1' + path, {
    credentials: 'same-origin',
    method: method || (body ? 'POST' : 'GET'),
    headers:
      body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    body: body
      ? body instanceof FormData
        ? body
        : JSON.stringify(body)
      : undefined,
  });
  const text = await response.text();
  let result: any;
  try {
    result = JSON.parse(text);
  } catch {
    throw new Error(
      'Layanan aplikasi belum terhubung. Jalankan backend Greta dan coba lagi.',
    );
  }
  if (!response.ok)
    throw new Error(
      typeof result.detail === 'string'
        ? result.detail
        : response.status === 422
          ? 'Periksa kolom wajib dan format data.'
          : 'Permintaan gagal (' + response.status + ').',
    );
  return result;
}
export function Picker({
  value,
  onChange,
  options,
  label = 'Filter',
}: {
  value: string;
  onChange: (s: string) => void;
  options: (string | { value: string; label: string })[];
  label?: string;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(String(v ?? ''))}>
      <SelectTrigger className="picker" aria-label={label}>
        <SelectValue>
          {options
            .map((x) => (typeof x === 'string' ? { value: x, label: x } : x))
            .find((x) => x.value === value)?.label || label}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options
          .map((x) => (typeof x === 'string' ? { value: x, label: x } : x))
          .map((x) => (
            <SelectItem value={x.value} key={x.value}>
              {x.label}
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  );
}
export function Status({ children }: { children: React.ReactNode }) {
  return (
    <span
      className={
        'status s-' + String(children).toLowerCase().replaceAll(' ', '-')
      }
    >
      {children}
    </span>
  );
}
export function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className="error-box" role="alert">
      <AlertCircle size={17} />
      {error}
    </div>
  ) : null;
}
export function Empty({
  title = 'Belum ada data',
  text = 'Data yang sesuai akan tampil di sini.',
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="empty-state">
      <FileSearch size={31} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function Busy() {
  return (
    <div className="busy" role="status">
      <LoaderCircle size={20} className="animate-spin" />
      Memuat workspace…
    </div>
  );
}
export function FilterInput({
  value,
  onChange,
  placeholder = 'Search…',
}: {
  value: string;
  onChange: (s: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="filter-input">
      <Search size={17} />
      <Input
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
export function money(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}
export function dateLabel(value: string) {
  if (!value) return '—';
  return new Date(
    value.length === 10 ? value + 'T12:00:00' : value,
  ).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}
export function download(name: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportCSV(name: string, headers: string[], rows: any[][]) {
  const escape = (v: any) =>
    '"' +
    String(v ?? '')
      .replace(/^[=+@-]/, "'")
      .replaceAll('"', '""') +
    '"';
  download(
    name,
    [headers, ...rows].map((r) => r.map(escape).join(',')).join('\n'),
    'text/csv;charset=utf-8',
  );
}
