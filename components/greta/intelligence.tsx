'use client';
import { useState, useEffect, useRef } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  ArrowUpRight,
  Search,
  Plus,
  Download,
  Upload,
  FileText,
  FolderClosed,
  Sparkles,
  Globe2,
  Check,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  ExternalLink,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Row,
  Workspace,
  api,
  Picker,
  Status,
  ErrorBox,
  Empty,
  FilterInput,
  money,
  dateLabel,
  exportCSV,
  download,
} from './shared';

export function Repository({
  data,
  refresh,
  onAsk,
  initialQuery = '',
}: {
  data: Workspace;
  refresh: () => Promise<void>;
  onAsk: (q: string) => void;
  initialQuery?: string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [category, setCategory] = useState('');
  const [mode, setMode] = useState('keyword');
  const [year, setYear] = useState('');
  const [format, setFormat] = useState('');
  const [results, setResults] = useState<Row[]>(data.documents);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState<Row | null>(null);
  const [jobs, setJobs] = useState<Row[]>([]);
  const uploadRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setResults(
      initialQuery
        ? data.documents.filter((d) =>
            d.name.toLowerCase().includes(initialQuery.toLowerCase()),
          )
        : data.documents,
    );
  }, [data.documents, initialQuery]);
  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError('');
    try {
      setResults(
        await api('/repository/search', {
          query,
          category,
          mode,
          year,
          format,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    setBusy(true);
    setError('');
    const body = new FormData();
    body.set('file', file);
    body.set('category_id', category);
    try {
      await api('/repository/upload', body);
      setJobs(await api('/repository/jobs'));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  }
  useEffect(() => {
    if (!jobs.some((j) => ['PENDING', 'PROCESSING'].includes(j.status))) return;
    const id = setInterval(
      () =>
        api('/repository/jobs')
          .then(async (next) => {
            setJobs(next);
            if (
              !next.some((j: Row) =>
                ['PENDING', 'PROCESSING'].includes(j.status),
              )
            )
              await refresh();
          })
          .catch((e) => setError(e.message)),
      2500,
    );
    return () => clearInterval(id);
  }, [jobs]);
  async function openDoc(id: string) {
    try {
      setDoc(await api('/repository/documents/' + id));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="repository-intro">
        <div>
          <BookOpen size={27} />
          <h2>Your institutional knowledge, in one place.</h2>
          <p>
            Find prior RFIs, supplier responses, and analyst reports with
            traceable sources.
          </p>
        </div>
        {data.user.permissions.includes('repository:write') && (
          <Button
            className="primary-button"
            disabled={busy}
            onClick={() => uploadRef.current?.click()}
          >
            <Upload size={16} />
            Upload document
          </Button>
        )}
        <input
          hidden
          ref={uploadRef}
          type="file"
          accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.html"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />
      </div>
      <form className="repository-search" onSubmit={search}>
        <FilterInput
          value={query}
          onChange={setQuery}
          placeholder="Search knowledge, materials, RFIs, or suppliers…"
        />
        <Picker
          value={mode}
          onChange={setMode}
          options={[
            { value: 'keyword', label: 'Keyword search' },
            { value: 'semantic', label: 'Semantic search' },
            { value: 'hybrid', label: 'Hybrid search' },
          ]}
        />
        <Button className="primary-button" disabled={busy} type="submit">
          <Search size={16} />
          {busy ? 'Searching…' : 'Search'}
        </Button>
      </form>
      <div className="toolbar filters">
        <Picker
          value={category}
          onChange={setCategory}
          options={[
            { value: '', label: 'All categories' },
            ...data.categories.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />
        <Picker
          value={format}
          onChange={setFormat}
          options={[
            { value: '', label: 'All formats' },
            'PDF',
            'DOCX',
            'XLSX',
            'PPTX',
            'TXT',
            'CSV',
            'HTML',
          ]}
        />
        <Picker
          value={year}
          onChange={setYear}
          options={[
            { value: '', label: 'All years' },
            '2026',
            '2025',
            '2024',
            '2023',
          ]}
        />
        <span>{results.length} documents</span>
      </div>
      <ErrorBox error={error} />
      {jobs.slice(0, 3).map((j) => (
        <div className="job-notice" key={j.id}>
          <FileText size={15} />
          <span>{j.name || 'Directory scan'}</span>
          <Status>{j.status}</Status>
          {j.errors?.length > 0 && (
            <span>{j.errors.length} file(s) require review</span>
          )}
        </div>
      ))}
      <div className="document-grid">
        {results.map((d) => (
          <article className="document-card" key={d.id}>
            <div className="document-top">
              <span className={'file-icon ' + (d.format || '').toLowerCase()}>
                <FileText size={23} />
                <small>{d.format}</small>
              </span>
              <Status>{d.status}</Status>
              {d.score !== undefined && d.score !== null && (
                <span className="match-label">{d.score}% relevance</span>
              )}
            </div>
            <button className="document-title" onClick={() => openDoc(d.id)}>
              {d.name}
            </button>
            <p>
              {d.snippet ||
                d.text?.slice(0, 155) ||
                'Document queued for extraction.'}
            </p>
            <div className="document-tags">
              <span>
                {data.categories.find((c) => c.id === d.category_id)?.name ||
                  'Unclassified'}
              </span>
              <span>{d.year}</span>
              <span>v{d.version}</span>
            </div>
            <div className="document-bottom">
              <small>
                {d.is_demo ? 'Sample source' : d.classification || 'INTERNAL'}
              </small>
              <button onClick={() => openDoc(d.id)}>
                Open source
                <ArrowRight size={14} />
              </button>
            </div>
          </article>
        ))}
      </div>
      {!results.length && (
        <Empty
          title="No matching documents"
          text="Adjust your search or upload a document to grow the repository."
        />
      )}
      <Dialog
        open={!!doc}
        onOpenChange={(v) => {
          if (!v) setDoc(null);
        }}
      >
        <DialogContent className="large-dialog">
          <DialogTitle>{doc?.name}</DialogTitle>
          <DialogDescription>
            Source document · {doc?.source} · Indexed{' '}
            {dateLabel(doc?.indexed_at)}
          </DialogDescription>
          <div className="source-content">
            {doc?.text || 'Text extraction is not available for this document.'}
          </div>
          <div className="dialog-actions">
            <span>
              {doc?.is_demo
                ? 'Illustrative source content'
                : doc?.classification}{' '}
              · Version {doc?.version}
            </span>
            <div className="inline-fields">
              <Button
                variant="outline"
                onClick={() => {
                  onAsk('Summarize ' + doc?.name);
                  setDoc(null);
                }}
              >
                <Sparkles size={16} />
                Ask Intelligence
              </Button>
              <a
                className="button-link"
                href={'/api/v1/repository/documents/' + doc?.id + '/download'}
              >
                <Download size={16} />
                {doc?.has_file ? 'Download original' : 'Download excerpt'}
              </a>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AskIntelligence({
  data,
  initialQuery,
  onCreate,
  onRefresh,
}: {
  data: Workspace;
  initialQuery: string;
  onCreate: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState('sources');
  const [category, setCategory] = useState('');
  const [messages, setMessages] = useState<Row[]>([]);
  const [conversation, setConversation] = useState<string | undefined>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Record<string, boolean>>({});
  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 3) return;
    setBusy(true);
    setError('');
    try {
      const r = await api('/ai/chat', {
        message: query,
        category,
        mode,
        conversation_id: conversation,
      });
      setMessages([...messages, r]);
      setConversation(r.conversation_id);
      setQuery('');
      await onRefresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="research-layout">
      <aside className="research-history">
        <Button
          variant="outline"
          onClick={() => {
            setMessages([]);
            setConversation(undefined);
            setQuery('');
          }}
        >
          <Plus size={16} />
          New research
        </Button>
        <div className="nav-label">YOUR CONVERSATIONS</div>
        {data.conversations.map((c) => (
          <button
            key={c.id}
            className={conversation === c.id ? 'active' : ''}
            onClick={() => {
              setConversation(c.id);
              setMessages(c.messages);
            }}
          >
            <BookOpen size={15} />
            <span>{c.title}</span>
          </button>
        ))}
        {!data.conversations.length && (
          <p className="section-note">Your saved research will appear here.</p>
        )}
      </aside>
      <section className="research-main">
        <div className="research-top">
          <span>
            <Sparkles size={18} />
            Ask Intelligence
          </span>
          <Picker
            value={category}
            onChange={setCategory}
            options={[
              { value: '', label: 'All categories' },
              ...data.categories.map((c) => ({ value: c.id, label: c.name })),
            ]}
          />
        </div>
        <div className="messages">
          {!messages.length && (
            <div className="research-welcome">
              <span className="large-ai-icon">
                <Sparkles size={31} />
              </span>
              <h2>What would you like to understand?</h2>
              <p>Start with a question. Build your decision on evidence.</p>
              <div className="research-prompts">
                {[
                  'What do we know about gas compressor lead times?',
                  'Compare historical OCTG price indications',
                  'Find previous gas engine maintenance RFIs',
                  'Summarize supplier capabilities for rotating equipment',
                ].map((q) => (
                  <button onClick={() => setQuery(q)} key={q}>
                    {q}
                    <ArrowUpRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <article className="conversation-message" key={m.id}>
              <div className="question-bubble">{m.question}</div>
              <div className="answer-header">
                <Sparkles size={18} />
                <strong>Greta Intelligence</strong>
                <Status>
                  {m.mode === 'ai' ? 'AI assessment' : 'Source retrieval'}
                </Status>
              </div>
              <div className="answer-text">{m.answer}</div>
              {m.citations?.length > 0 && (
                <div className="citations">
                  <h3>Supporting evidence · {m.citations.length} sources</h3>
                  {m.citations.map((c: Row, i: number) => (
                    <details key={c.id}>
                      <summary>
                        <span>{i + 1}</span>
                        <FileText size={16} />
                        {c.name}
                        <small>p. {c.page}</small>
                      </summary>
                      <blockquote>{c.excerpt}</blockquote>
                      <p>
                        Source ID: {c.id} · Indexed {dateLabel(c.indexed_at)}
                        {c.is_demo ? ' · Sample data' : ''}
                      </p>
                      <a
                        href={
                          '/api/v1/repository/documents/' + c.id + '/download'
                        }
                      >
                        Download source excerpt
                      </a>
                    </details>
                  ))}
                </div>
              )}
              <div className="answer-actions">
                <span>
                  {feedback[m.id] !== undefined
                    ? 'Feedback saved'
                    : 'Was this useful?'}
                </span>
                {[true, false].map((v) => (
                  <button
                    aria-label={v ? 'Useful' : 'Not useful'}
                    disabled={feedback[m.id] !== undefined}
                    key={String(v)}
                    onClick={async () => {
                      try {
                        await api('/ai/messages/' + m.id + '/feedback', {
                          useful: v,
                        });
                        setFeedback({ ...feedback, [m.id]: v });
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    {v ? <ThumbsUp size={15} /> : <ThumbsDown size={15} />}
                  </button>
                ))}
                <button
                  onClick={() =>
                    download(
                      'greta-research.md',
                      '# ' +
                        m.question +
                        '\n\n' +
                        m.answer +
                        '\n\n' +
                        m.citations
                          .map((c: Row) => '## ' + c.name + '\n' + c.excerpt)
                          .join('\n\n'),
                    )
                  }
                >
                  <Download size={15} />
                  Export
                </button>
                {data.user.permissions.includes('rfi:create') && (
                  <button onClick={onCreate}>
                    <Plus size={15} />
                    Create RFI
                  </button>
                )}
              </div>
            </article>
          ))}
          {busy && (
            <div className="info-note">
              <Sparkles size={17} />
              Retrieving authorized evidence…
            </div>
          )}
        </div>
        <ErrorBox error={error} />
        <form className="research-composer" onSubmit={send}>
          <Textarea
            aria-label="Research question"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about a category, supplier, or sourcing requirement…"
            rows={3}
            required
            minLength={3}
          />
          <div>
            <Picker
              value={mode}
              onChange={setMode}
              options={[
                { value: 'sources', label: 'Find sources' },
                { value: 'ai', label: 'Azure AI analysis' },
              ]}
            />
            <span>Answers should be reviewed before procurement action.</span>
            <Button className="primary-button" type="submit" disabled={busy}>
              <ArrowRight size={17} />
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function Suppliers({
  data,
  refresh,
}: {
  data: Workspace;
  refresh: () => Promise<void>;
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [selected, setSelected] = useState<Row | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<Row>({
    name: '',
    country: 'Indonesia',
    category_id: data.categories[0]?.id || '',
    type: 'Manufacturer',
    email: '',
  });
  const [error, setError] = useState('');
  const suppliers = data.suppliers.filter(
    (s) =>
      (s.name + ' ' + s.country).toLowerCase().includes(query.toLowerCase()) &&
      (!category || s.category_id === category),
  );
  return (
    <>
      <div className="toolbar">
        <FilterInput
          value={query}
          onChange={setQuery}
          placeholder="Find a supplier…"
        />
        <Picker
          value={category}
          onChange={setCategory}
          options={[
            { value: '', label: 'All categories' },
            ...data.categories.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />
        {data.user.permissions.includes('supplier:write') && (
          <Button className="primary-button" onClick={() => setCreating(true)}>
            <Plus size={16} />
            Add supplier
          </Button>
        )}
      </div>
      <div className="supplier-grid">
        {suppliers.map((s) => (
          <button
            className="supplier-card"
            key={s.id}
            onClick={() => setSelected(s)}
          >
            <div className="supplier-card-top">
              <span className="supplier-logo">
                {s.name.slice(0, 2).toUpperCase()}
              </span>
              <ArrowUpRight size={17} />
            </div>
            <h3>{s.name}</h3>
            <p>
              <Globe2 size={13} />
              {s.country} · {s.type}
            </p>
            <div className="document-tags">
              <span>
                {data.categories.find((c) => c.id === s.category_id)?.name}
              </span>
              <span>{s.landscape}</span>
            </div>
            <div className="supplier-metrics">
              <div>
                <strong>
                  {s.response_rate === undefined ? '—' : s.response_rate + '%'}
                </strong>
                <span>Response rate</span>
              </div>
              <div>
                <strong>{s.lead_time ? s.lead_time + ' wks' : '—'}</strong>
                <span>Lead time</span>
              </div>
              <div>
                <strong>{s.participations ?? '—'}</strong>
                <span>Prior RFIs</span>
              </div>
            </div>
          </button>
        ))}
      </div>
      {!suppliers.length && <Empty title="No suppliers found" />}
      <Dialog
        open={!!selected}
        onOpenChange={(v) => {
          if (!v) setSelected(null);
        }}
      >
        <DialogContent className="large-dialog">
          <DialogTitle>{selected?.name}</DialogTitle>
          <DialogDescription>
            {selected?.country} · {selected?.type} · {selected?.landscape}
          </DialogDescription>
          <div className="detail-body">
            <h3>Capabilities & certifications</h3>
            <div className="document-tags">
              {selected?.certifications?.map((x: string) => (
                <span key={x}>
                  <Check size={13} />
                  {x}
                </span>
              ))}
            </div>
            {selected?.portal_profile && (
              <div className="ai3-card">
                <h3>Supplier-reported company profile</h3>
                <p className="section-note">
                  Updated {selected.portal_profile.updated_at?.slice(0, 10)} by{' '}
                  {selected.portal_profile.updated_by}
                </p>
                <p className="body-copy">
                  {selected.portal_profile.capabilities}
                </p>
                <p className="body-copy">
                  {selected.portal_profile.certifications}
                </p>
                <p className="section-note">
                  {selected.portal_profile.contact_name} ·{' '}
                  {selected.portal_profile.phone} ·{' '}
                  {selected.portal_profile.website}
                </p>
              </div>
            )}
            <h3>Historical interaction</h3>
            <div className="info-grid">
              <div>
                <strong>
                  {selected?.delivery === undefined
                    ? '—'
                    : selected.delivery + '%'}
                </strong>
                <span>On-time delivery</span>
              </div>
              <div>
                <strong>{selected?.lead_time || '—'}</strong>
                <span>Lead time in weeks</span>
              </div>
              <div>
                <strong>{selected?.price ? money(selected.price) : '—'}</strong>
                <span>Price indication</span>
              </div>
            </div>
            {data.rfis
              .filter((r) => r.supplier_ids.includes(selected?.id))
              .map((r) => (
                <div className="supplier-line" key={r.id}>
                  <FileText size={18} />
                  <div>
                    <strong>{r.title}</strong>
                    <small>{r.number}</small>
                  </div>
                  <Status>{r.status}</Status>
                </div>
              ))}
            <div className="info-note">
              {selected?.is_demo
                ? 'Illustrative supplier profile. Performance values are sample data.'
                : 'Supplier details entered by your organization.'}
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="large-dialog">
          <DialogTitle>Add supplier</DialogTitle>
          <DialogDescription>
            Add a potential supplier to your organization’s supplier directory.
          </DialogDescription>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError('');
              try {
                await api('/suppliers', form);
                await refresh();
                setCreating(false);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <div className="form-grid">
              {['name', 'country', 'email'].map((k) => (
                <label key={k}>
                  {k[0].toUpperCase() + k.slice(1)}
                  <Input
                    required={k !== 'email'}
                    type={k === 'email' ? 'email' : 'text'}
                    value={form[k]}
                    onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  />
                </label>
              ))}
              <label>
                Category
                <Picker
                  value={form.category_id}
                  onChange={(v) => setForm({ ...form, category_id: v })}
                  options={data.categories.map((c) => ({
                    value: c.id,
                    label: c.name,
                  }))}
                />
              </label>
              <label>
                Supplier type
                <Picker
                  value={form.type}
                  onChange={(v) => setForm({ ...form, type: v })}
                  options={['Manufacturer', 'Distributor', 'Service provider']}
                />
              </label>
            </div>
            <ErrorBox error={error} />
            <div className="dialog-actions">
              <Button className="primary-button" type="submit">
                Save supplier
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
function PriceChart({
  series,
  labels,
}: {
  series: number[];
  labels: string[];
}) {
  const min = Math.min(...series) * 0.97,
    max = Math.max(...series) * 1.02;
  const point = (v: number, i: number) =>
    `${50 + i * (650 / Math.max(1, series.length - 1))},${200 - ((v - min) / (max - min || 1)) * 160}`;
  return (
    <svg
      className="price-chart"
      viewBox="0 0 750 260"
      role="img"
      aria-label={'Price trend: ' + series.join(', ')}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i}>
          <line
            x1="50"
            y1={40 + i * 40}
            x2="710"
            y2={40 + i * 40}
            stroke="#e8ede8"
            strokeDasharray="4 5"
          />
          <text x="3" y={44 + i * 40} fontSize="12" fill="#929c92">
            {Math.round(max - ((max - min) * i) / 4).toLocaleString()}
          </text>
        </g>
      ))}
      <polyline
        points={series.map(point).join(' ')}
        fill="none"
        stroke="#527e58"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {series.map((v, i) => (
        <g key={i}>
          <circle
            cx={point(v, i).split(',')[0]}
            cy={point(v, i).split(',')[1]}
            r="5"
            fill="white"
            stroke="#527e58"
            strokeWidth="2"
          >
            <title>
              {labels[i]}: {v}
            </title>
          </circle>
          <text
            x={50 + i * (650 / Math.max(1, series.length - 1))}
            y="235"
            fontSize="12"
            fill="#929c92"
            textAnchor="middle"
          >
            {labels[i]?.slice(5, 7)
              ? [
                  'Jan',
                  'Feb',
                  'Mar',
                  'Apr',
                  'May',
                  'Jun',
                  'Jul',
                  'Aug',
                  'Sep',
                  'Oct',
                  'Nov',
                  'Dec',
                ][Number(labels[i].slice(5, 7)) - 1]
              : labels[i]}
          </text>
        </g>
      ))}
    </svg>
  );
}
export function Market({
  data,
  onRFI,
  onAsk,
  refresh,
}: {
  data: Workspace;
  onRFI: (id: string) => void;
  onAsk: (q: string) => void;
  refresh: () => Promise<void>;
}) {
  const [category, setCategory] = useState('');
  const [price, setPrice] = useState(data.prices[0]?.id || '');
  const [eventOpen, setEventOpen] = useState(false);
  const [error, setError] = useState('');
  const [event, setEvent] = useState<Row>({
    title: '',
    description: '',
    category_id: data.categories[0]?.id || '',
    date: new Date().toISOString().slice(0, 10),
    impact: 'Medium',
    source: '',
  });
  const c = data.categories.find((c) => c.id === category);
  const p = data.prices.find((p) => p.id === price) || data.prices[0];
  return (
    <>
      {c ? (
        <>
          <button className="back-link" onClick={() => setCategory('')}>
            <ArrowLeft size={16} />
            All categories
          </button>
          <div className="category-heading">
            <div>
              <span className="eyebrow">
                {c.group} / {c.subcategory}
              </span>
              <h2>{c.name}</h2>
              <p>{c.commodity}</p>
            </div>
            <Button
              className="primary-button"
              onClick={() => onAsk('Give me a market overview for ' + c.name)}
            >
              <Sparkles size={16} />
              Research category
            </Button>
          </div>
          <div className="module-stats">
            <div>
              <span>Historical spend</span>
              <strong>{c.spend ? '$' + c.spend + 'M' : '—'}</strong>
            </div>
            <div>
              <span>Lead time</span>
              <strong>
                {c.lead_time || '—'} <small>weeks</small>
              </strong>
            </div>
            <div>
              <span>Suppliers</span>
              <strong>
                {data.suppliers.filter((s) => s.category_id === c.id).length}
              </strong>
            </div>
            <div>
              <span>Historical RFIs</span>
              <strong>
                {data.rfis.filter((r) => r.category_id === c.id).length}
              </strong>
            </div>
          </div>
          <section className="panel detail-body">
            <h3>Related RFIs</h3>
            {data.rfis
              .filter((r) => r.category_id === c.id)
              .map((r) => (
                <button
                  className="supplier-line full-width"
                  key={r.id}
                  onClick={() => onRFI(r.id)}
                >
                  <FileText size={18} />
                  <div>
                    <strong>{r.title}</strong>
                    <small>{r.number}</small>
                  </div>
                  <Status>{r.status}</Status>
                  <ArrowRight size={15} />
                </button>
              ))}
          </section>
        </>
      ) : (
        <>
          <div className="section-heading">
            <h2>Category intelligence</h2>
            <span>{data.categories.length} monitored categories</span>
          </div>
          <div className="category-grid">
            {data.categories.map((c) => (
              <button
                className="category-card"
                onClick={() => setCategory(c.id)}
                key={c.id}
              >
                <div>
                  <span className="category-symbol">
                    <FolderClosed size={20} />
                  </span>
                  <ArrowUpRight size={16} />
                </div>
                <small>{c.group}</small>
                <h3>{c.name}</h3>
                <p>
                  {c.subcategory} → {c.commodity}
                </p>
                <footer>
                  <span>
                    {
                      data.suppliers.filter((s) => s.category_id === c.id)
                        .length
                    }{' '}
                    suppliers
                  </span>
                  <span>
                    {data.rfis.filter((r) => r.category_id === c.id).length}{' '}
                    RFIs
                  </span>
                </footer>
              </button>
            ))}
          </div>
        </>
      )}
      {p && (
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <h2>Price intelligence</h2>
              <p>
                {p.source} · {p.unit} · {p.region}
              </p>
            </div>
            <Picker
              value={p.id}
              onChange={setPrice}
              options={data.prices.map((p) => ({ value: p.id, label: p.name }))}
            />
          </div>
          <div className="chart-value">
            {p.value.toLocaleString('en-US')}
            <small>{p.unit}</small>
            <Status>
              {p.change > 0 ? '+' : ''}
              {p.change}% MoM
            </Status>
          </div>
          <PriceChart series={p.series} labels={p.dates} />
          <div className="panel-footer">
            <span>
              Source: {p.source} · {dateLabel(p.date)}
            </span>
            <button
              onClick={() =>
                exportCSV(
                  p.name + '.csv',
                  ['Date', 'Value', 'Unit', 'Source'],
                  p.series.map((v: number, i: number) => [
                    p.dates[i],
                    v,
                    p.unit,
                    p.source,
                  ]),
                )
              }
            >
              Export series
              <Download size={14} />
            </button>
          </div>
        </section>
      )}
      <div className="section-heading">
        <h2>Market events</h2>
        {data.user.permissions.includes('market:write') && (
          <Button variant="outline" onClick={() => setEventOpen(true)}>
            <Plus size={16} />
            Add event
          </Button>
        )}
      </div>
      <div className="events-grid">
        {data.events
          .filter((e) => !category || e.category_id === category)
          .map((e) => (
            <article className="panel event-card" key={e.id}>
              <div className="signal-meta">
                <Status>{e.type}</Status>
                <span>{dateLabel(e.date)}</span>
              </div>
              <h3>{e.title}</h3>
              <p>{e.description}</p>
              <div className="event-source">
                <span>Impact: {e.impact}</span>
                <span>Source: {e.source}</span>
              </div>
            </article>
          ))}
      </div>
      <Dialog open={eventOpen} onOpenChange={setEventOpen}>
        <DialogContent className="large-dialog">
          <DialogTitle>Record a market event</DialogTitle>
          <DialogDescription>
            Include the source and your assessment so the event can support
            future research.
          </DialogDescription>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api('/market/events', event);
                await refresh();
                setEventOpen(false);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <div className="form-grid">
              {['title', 'description', 'source', 'date'].map((k) => (
                <label key={k} className={k === 'description' ? 'full' : ''}>
                  {k[0].toUpperCase() + k.slice(1)}
                  <Input
                    required
                    value={event[k]}
                    type={k === 'date' ? 'date' : 'text'}
                    onChange={(e) =>
                      setEvent({ ...event, [k]: e.target.value })
                    }
                  />
                </label>
              ))}
              <label>
                Category
                <Picker
                  value={event.category_id}
                  onChange={(v) => setEvent({ ...event, category_id: v })}
                  options={data.categories.map((c) => ({
                    value: c.id,
                    label: c.name,
                  }))}
                />
              </label>
              <label>
                Impact
                <Picker
                  value={event.impact}
                  onChange={(v) => setEvent({ ...event, impact: v })}
                  options={['Low', 'Medium', 'High']}
                />
              </label>
            </div>
            <ErrorBox error={error} />
            <Button className="primary-button" type="submit">
              Save event
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
export function Analytics({ data }: { data: Workspace }) {
  const invitations = data.rfis.reduce(
    (sum, r) => sum + r.supplier_ids.length,
    0,
  );
  const submitted = data.responses.filter((r) => r.submitted).length;
  const rate = invitations ? (submitted / invitations) * 100 : 0;
  return (
    <>
      <div className="module-stats">
        <div>
          <span>Total RFIs</span>
          <strong>{data.rfis.length}</strong>
        </div>
        <div>
          <span>Response rate</span>
          <strong>{rate.toFixed(1)}%</strong>
        </div>
        <div>
          <span>Participating suppliers</span>
          <strong>
            {new Set(data.responses.map((r) => r.supplier_id)).size}
          </strong>
        </div>
        <div>
          <span>Indexed documents</span>
          <strong>
            {data.documents.filter((d) => d.status === 'Indexed').length}
          </strong>
        </div>
      </div>
      <div className="analytics-grid">
        <section className="panel detail-body">
          <h3>RFI lifecycle distribution</h3>
          <p className="section-note">
            Current status across your authorized RFIs
          </p>
          {[
            'Draft',
            'Internal Review',
            'Approved',
            'Open',
            'Response Received',
            'Closed',
            'Analysis',
            'Completed',
            'Archived',
          ].map((s) => {
            const value = data.rfis.filter((r) => r.status === s).length;
            return (
              <div className="analytics-bar" key={s}>
                <span>{s}</span>
                <div>
                  <i
                    style={{
                      width: `${(value / Math.max(data.rfis.length, 1)) * 100}%`,
                    }}
                  />
                </div>
                <strong>{value}</strong>
              </div>
            );
          })}
        </section>
        <section className="panel detail-body">
          <h3>Knowledge by category</h3>
          <p className="section-note">
            Document coverage for your category research
          </p>
          {data.categories.map((c) => {
            const value = data.documents.filter(
              (d) => d.category_id === c.id,
            ).length;
            return (
              <div className="analytics-bar" key={c.id}>
                <span>{c.name}</span>
                <div>
                  <i
                    style={{
                      width: `${(value / Math.max(data.documents.length, 1)) * 100}%`,
                    }}
                  />
                </div>
                <strong>{value}</strong>
              </div>
            );
          })}
        </section>
      </div>
      <section className="panel module-panel">
        <div className="panel-heading">
          <div>
            <h2>Category performance</h2>
            <p>
              All metrics are calculated from the current workspace records.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() =>
              exportCSV(
                'category-analytics.csv',
                ['Category', 'RFIs', 'Suppliers', 'Documents'],
                data.categories.map((c) => [
                  c.name,
                  data.rfis.filter((r) => r.category_id === c.id).length,
                  data.suppliers.filter((s) => s.category_id === c.id).length,
                  data.documents.filter((d) => d.category_id === c.id).length,
                ]),
              )
            }
          >
            <Download size={16} />
            Export
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              {[
                'CATEGORY',
                'RFIS',
                'SUPPLIERS',
                'DOCUMENTS',
                'HISTORICAL SPEND',
              ].map((h) => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.categories.map((c) => (
              <TableRow key={c.id}>
                <TableCell>{c.name}</TableCell>
                <TableCell>
                  {data.rfis.filter((r) => r.category_id === c.id).length}
                </TableCell>
                <TableCell>
                  {data.suppliers.filter((s) => s.category_id === c.id).length}
                </TableCell>
                <TableCell>
                  {data.documents.filter((d) => d.category_id === c.id).length}
                </TableCell>
                <TableCell>{c.spend ? '$' + c.spend + 'M' : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
      <div className="info-note">
        Response rate = {submitted} submitted responses ÷ {invitations} selected
        supplier participations × 100.{' '}
        {data.demo ? 'Demo spend values are illustrative.' : ''}
      </div>
    </>
  );
}
