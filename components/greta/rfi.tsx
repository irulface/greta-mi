'use client';
import { useState, useEffect } from 'react';
import { AdvancedRFIAnalysis } from './market-intelligence';
import {
  Plus,
  ArrowLeft,
  ArrowRight,
  Copy,
  Download,
  Trash2,
  Sparkles,
  Check,
  Send,
  Link2,
  FileText,
  Building2,
  ClipboardList,
  LockKeyhole,
  Mail,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
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
  dateLabel,
  exportCSV,
} from './shared';
const QUESTION_TYPES = [
  'short text',
  'long text',
  'integer',
  'decimal',
  'currency',
  'percentage',
  'date',
  'yes/no',
  'single choice',
  'multiple choice',
  'table',
  'file attachment',
];
const templateQuestions = () => [
  {
    id: crypto.randomUUID(),
    section: 'Supplier information',
    text: 'Describe your company, relevant certifications, and manufacturing capabilities.',
    type: 'long text',
    required: true,
  },
  {
    id: crypto.randomUUID(),
    section: 'Technical specification',
    text: 'Describe your technical solution and compliance with the requirement.',
    type: 'long text',
    required: true,
  },
  {
    id: crypto.randomUUID(),
    section: 'Delivery',
    text: 'Manufacturing lead time (weeks)',
    type: 'integer',
    required: true,
  },
  {
    id: crypto.randomUUID(),
    section: 'Commercial information',
    text: 'Indicative price (USD)',
    type: 'currency',
    required: true,
  },
  {
    id: crypto.randomUUID(),
    section: 'After-sales support',
    text: 'Describe warranty coverage, spare parts, and local service support.',
    type: 'long text',
    required: true,
  },
];
export function CreateRFI({
  data,
  open,
  onClose,
  onSaved,
  initial,
}: {
  data: Workspace;
  open: boolean;
  onClose: () => void;
  onSaved: (r: Row) => void;
  initial?: Row | null;
}) {
  const [form, setForm] = useState<Row>({
    title: '',
    category_id: 'rotating',
    closing_date: '',
    requirement: '',
    classification: 'INTERNAL',
    supplier_ids: [],
    questions: [],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('requirement');
  const [templates, setTemplates] = useState<Row[]>([]);
  useEffect(() => {
    if (open) {
      api('/rfi/templates')
        .then(setTemplates)
        .catch(() => {});
      setForm(
        initial
          ? { ...initial, questions: [...initial.questions] }
          : {
              title: '',
              category_id: data.categories[0]?.id || '',
              closing_date: '',
              requirement: '',
              classification: 'INTERNAL',
              supplier_ids: [],
              questions: [],
            },
      );
      setError('');
      setTab('requirement');
    }
  }, [open, initial]);
  const set = (key: string, value: any) => setForm({ ...form, [key]: value });
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const r = await api(
        initial ? '/rfis/' + initial.id : '/rfis',
        form,
        initial ? 'PUT' : 'POST',
      );
      onSaved(r);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    setBusy(true);
    setError('');
    try {
      set(
        'questions',
        await api('/ai/rfi/generate', { requirement: form.requirement }),
      );
      setTab('questions');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent className="large-dialog">
        <DialogTitle>
          {initial ? 'Edit RFI draft' : 'Start a new RFI'}
        </DialogTitle>
        <DialogDescription>
          Build the information you need for your next sourcing decision.
        </DialogDescription>
        <form onSubmit={save}>
          <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
            <TabsList className="workspace-tabs">
              <TabsTrigger value="requirement">1. Requirement</TabsTrigger>
              <TabsTrigger value="questions">
                2. Questions · {form.questions.length}
              </TabsTrigger>
              <TabsTrigger value="suppliers">
                3. Suppliers · {form.supplier_ids.length}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="requirement">
              <div className="form-grid">
                <label className="full">
                  RFI title
                  <Input
                    required
                    minLength={5}
                    value={form.title}
                    onChange={(e) => set('title', e.target.value)}
                    placeholder="e.g. Offshore Gas Compressor Package"
                  />
                </label>
                <label>
                  Category
                  <Picker
                    value={form.category_id}
                    onChange={(v) => set('category_id', v)}
                    options={data.categories.map((c) => ({
                      value: c.id,
                      label: c.name,
                    }))}
                  />
                </label>
                <label>
                  Closing date
                  <Input
                    required
                    type="date"
                    min={new Date().toISOString().slice(0, 10)}
                    value={form.closing_date}
                    onChange={(e) => set('closing_date', e.target.value)}
                  />
                </label>
                <label className="full">
                  Business requirement
                  <Textarea
                    rows={5}
                    required
                    minLength={10}
                    value={form.requirement}
                    onChange={(e) => set('requirement', e.target.value)}
                    placeholder="Describe the equipment, required capacity, operating environment, quantity, and sourcing objective."
                  />
                </label>
                <label>
                  Confidentiality
                  <Picker
                    value={form.classification}
                    onChange={(v) => set('classification', v)}
                    options={[
                      'INTERNAL',
                      'CONFIDENTIAL',
                      'RESTRICTED',
                      'PUBLIC INTERNAL',
                    ]}
                  />
                </label>
              </div>
            </TabsContent>
            <TabsContent value="questions">
              <div className="toolbar">
                {templates.length > 0 && (
                  <Picker
                    value=""
                    label="Saved template"
                    onChange={(v) => {
                      const t = templates.find((t) => t.id === v);
                      if (t) set('questions', t.questions);
                    }}
                    options={[
                      { value: '', label: 'Choose saved template' },
                      ...templates
                        .filter((t) => t.category_id === form.category_id)
                        .map((t) => ({
                          value: t.id,
                          label: t.name + ' · v' + t.version,
                        })),
                    ]}
                  />
                )}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => set('questions', templateQuestions())}
                >
                  <FileText size={16} />
                  Use category template
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={generate}
                  disabled={busy || form.requirement.length < 10}
                >
                  <Sparkles size={16} />
                  Generate with AI
                </Button>
              </div>
              <div className="question-editor">
                {form.questions.map((q: Row, i: number) => (
                  <div className="question-card" key={q.id}>
                    <div className="question-number">
                      {String(i + 1).padStart(2, '0')}
                    </div>
                    <div className="question-fields">
                      <Input
                        aria-label={'Question ' + (i + 1)}
                        value={q.text}
                        onChange={(e) =>
                          set(
                            'questions',
                            form.questions.map((x: Row) =>
                              x.id === q.id
                                ? { ...x, text: e.target.value }
                                : x,
                            ),
                          )
                        }
                      />
                      <div className="inline-fields">
                        <Picker
                          value={q.type}
                          onChange={(type) =>
                            set(
                              'questions',
                              form.questions.map((x: Row) =>
                                x.id === q.id ? { ...x, type } : x,
                              ),
                            )
                          }
                          options={QUESTION_TYPES}
                        />
                        <label className="check-label">
                          <Checkbox
                            checked={q.required}
                            onCheckedChange={(v) =>
                              set(
                                'questions',
                                form.questions.map((x: Row) =>
                                  x.id === q.id ? { ...x, required: v } : x,
                                ),
                              )
                            }
                          />
                          Required
                        </label>
                        <Button
                          type="button"
                          variant="ghost"
                          aria-label="Delete question"
                          onClick={() =>
                            set(
                              'questions',
                              form.questions.filter((x: Row) => x.id !== q.id),
                            )
                          }
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                      {['single choice', 'multiple choice'].includes(
                        q.type,
                      ) && (
                        <Input
                          aria-label="Choice options"
                          placeholder="Options, separated by commas"
                          value={(q.options || []).join(',')}
                          onChange={(e) =>
                            set(
                              'questions',
                              form.questions.map((x: Row) =>
                                x.id === q.id
                                  ? {
                                      ...x,
                                      options: e.target.value
                                        .split(',')
                                        .map((v) => v.trim()),
                                    }
                                  : x,
                              ),
                            )
                          }
                        />
                      )}
                      {i > 0 && (
                        <div className="condition-editor">
                          <Picker
                            value={q.condition?.question_id || ''}
                            onChange={(v) =>
                              set(
                                'questions',
                                form.questions.map((x: Row) =>
                                  x.id === q.id
                                    ? {
                                        ...x,
                                        condition: v
                                          ? { question_id: v, equals: '' }
                                          : null,
                                      }
                                    : x,
                                ),
                              )
                            }
                            options={[
                              { value: '', label: 'Always show question' },
                              ...form.questions.slice(0, i).map((p: Row) => ({
                                value: p.id,
                                label: 'Show if: ' + p.text.slice(0, 45),
                              })),
                            ]}
                          />
                          {q.condition && (
                            <Input
                              aria-label="Condition equals"
                              placeholder="Answer equals…"
                              value={q.condition.equals}
                              onChange={(e) =>
                                set(
                                  'questions',
                                  form.questions.map((x: Row) =>
                                    x.id === q.id
                                      ? {
                                          ...x,
                                          condition: {
                                            ...x.condition,
                                            equals: e.target.value,
                                          },
                                        }
                                      : x,
                                  ),
                                )
                              }
                            />
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  set('questions', [
                    ...form.questions,
                    {
                      id: crypto.randomUUID(),
                      section: 'General',
                      text: '',
                      type: 'long text',
                      required: false,
                    },
                  ])
                }
              >
                <Plus size={16} />
                Add question
              </Button>
            </TabsContent>
            <TabsContent value="suppliers">
              <p className="section-note">
                Select the suppliers you want to invite after internal approval.
              </p>
              <div className="supplier-options">
                {data.suppliers.map((s) => (
                  <label key={s.id}>
                    <Checkbox
                      checked={form.supplier_ids.includes(s.id)}
                      onCheckedChange={(v) =>
                        set(
                          'supplier_ids',
                          v
                            ? [...form.supplier_ids, s.id]
                            : form.supplier_ids.filter(
                                (id: string) => id !== s.id,
                              ),
                        )
                      }
                    />
                    <span className="supplier-logo">
                      {s.name.slice(0, 2).toUpperCase()}
                    </span>
                    <div>
                      <strong>{s.name}</strong>
                      <small>
                        {s.country} · {s.type}
                      </small>
                    </div>
                  </label>
                ))}
              </div>
            </TabsContent>
          </Tabs>
          <ErrorBox error={error} />
          <div className="dialog-actions">
            {data.user.permissions.includes('rfi:manage') &&
              form.questions.length > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={busy || form.title.length < 3}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api('/rfi/templates', {
                        name: form.title,
                        category_id: form.category_id,
                        questions: form.questions,
                      });
                      setTemplates(await api('/rfi/templates'));
                      setError('');
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Save as template
                </Button>
              )}
            <span>
              <LockKeyhole size={14} />
              Saved as a draft. Review before issue.
            </span>
            <Button type="submit" className="primary-button" disabled={busy}>
              {busy ? 'Saving…' : 'Save draft'}
              <ArrowRight size={15} />
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
export function RFIList({
  data,
  onOpen,
  onCreate,
}: {
  data: Workspace;
  onOpen: (id: string) => void;
  onCreate: () => void;
}) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [category, setCategory] = useState('');
  const filtered = data.rfis.filter(
    (r) =>
      (status === 'All statuses' || r.status === status) &&
      (!category || r.category_id === category) &&
      (r.title + ' ' + r.number).toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="module-stats">
        {['Draft', 'Internal Review', 'Open', 'Completed'].map((s) => (
          <div key={s}>
            <span>{s}</span>
            <strong>{data.rfis.filter((r) => r.status === s).length}</strong>
          </div>
        ))}
      </div>
      <section className="panel module-panel">
        <div className="toolbar">
          <FilterInput
            value={query}
            onChange={setQuery}
            placeholder="Search RFIs by title or reference…"
          />
          <Picker
            value={status}
            onChange={setStatus}
            options={[
              'All statuses',
              'Draft',
              'Internal Review',
              'Approved',
              'Issued',
              'Open',
              'Response Received',
              'Closed',
              'Analysis',
              'Completed',
              'Archived',
              'Cancelled',
            ]}
          />
          <Picker
            value={category}
            onChange={setCategory}
            options={[
              { value: '', label: 'All categories' },
              ...data.categories.map((c) => ({ value: c.id, label: c.name })),
            ]}
          />
          <Button
            variant="outline"
            onClick={() =>
              exportCSV(
                'greta-rfis.csv',
                ['Reference', 'Title', 'Status', 'Closing date'],
                filtered.map((r) => [
                  r.number,
                  r.title,
                  r.status,
                  r.closing_date,
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
                'RFI / CATEGORY',
                'STATUS',
                'SUPPLIERS',
                'RESPONSES',
                'CLOSING DATE',
                '',
              ].map((h) => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((r) => (
              <TableRow
                key={r.id}
                className="clickable-row"
                onClick={() => onOpen(r.id)}
              >
                <TableCell>
                  <small className="reference">{r.number}</small>
                  <strong className="rfi-title">{r.title}</strong>
                  <span className="table-category">
                    {data.categories.find((c) => c.id === r.category_id)?.name}
                  </span>
                </TableCell>
                <TableCell>
                  <Status>{r.status}</Status>
                </TableCell>
                <TableCell>{r.supplier_ids.length}</TableCell>
                <TableCell>
                  {
                    data.responses.filter(
                      (x) => x.rfi_id === r.id && x.submitted,
                    ).length
                  }{' '}
                  / {r.supplier_ids.length}
                </TableCell>
                <TableCell>{dateLabel(r.closing_date)}</TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={'Open ' + r.title}
                  >
                    <ArrowRight size={16} />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {!filtered.length && (
          <Empty
            title="No RFIs found"
            text="Create a draft or adjust the filters to get started."
          />
        )}
        <div className="panel-footer">
          <span>
            {filtered.length} RFIs · {data.user.region}
          </span>
          <span>Access is scoped to your workspace</span>
        </div>
      </section>
    </>
  );
}
export function RFIDetail({
  id,
  data,
  onBack,
  onEdit,
  onRefresh,
  onOpen,
}: {
  id: string;
  data: Workspace;
  onBack: () => void;
  onEdit: (r: Row) => void;
  onRefresh: () => Promise<void>;
  onOpen: (id: string) => void;
}) {
  const [rfi, setRfi] = useState<Row | null>(null);
  const [tab, setTab] = useState('overview');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [links, setLinks] = useState<Row[]>([]);
  const [emails, setEmails] = useState<Row[]>([]);
  const [emailOpen, setEmailOpen] = useState(false);
  const canManage = data.user.permissions.includes('rfi:manage');
  const emailPending = emails.some((row) =>
    ['PENDING', 'SENDING'].includes(row.status),
  );
  const [clarification, setClarification] = useState('');
  const load = () =>
    api('/rfis/' + id)
      .then(setRfi)
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
    setLinks([]);
    setEmails([]);
    setEmailOpen(false);
  }, [id]);
  const loadEmails = () =>
    api('/rfis/' + id + '/emails')
      .then(setEmails)
      .catch((e) => setError(e.message));
  useEffect(() => {
    if (!canManage || tab !== 'suppliers') return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result: Row[] = await api('/rfis/' + id + '/emails');
        if (!active) return;
        setEmails(result);
        if (result.some((row) => ['PENDING', 'SENDING'].includes(row.status))) {
          timer = setTimeout(poll, 3000);
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, tab, canManage, emailPending]);
  async function action(path: string, body?: any) {
    setBusy(true);
    setError('');
    try {
      const v = await api(
        path,
        body || {},
        path.startsWith('/clarifications/') ? 'PUT' : 'POST',
      );
      await load();
      await onRefresh();
      return v;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!rfi) return <ErrorBox error={error} />;
  const suppliers = data.suppliers.filter((s) =>
    rfi.supplier_ids.includes(s.id),
  );
  const next: Record<string, string> = {
    Draft: 'Internal Review',
    'Internal Review': 'Approved',
    Approved: 'Issued',
    Issued: 'Open',
    Open: 'Closed',
    'Response Received': 'Closed',
    Closed: 'Analysis',
    Analysis: 'Completed',
    Completed: 'Archived',
  };
  function exportReport() {
    exportCSV(
      rfi!.number + '-comparison.csv',
      ['Supplier', ...rfi!.questions.map((q: Row) => q.text)],
      suppliers.map((s) => [
        s.name,
        ...rfi!.questions.map(
          (q: Row) =>
            rfi!.responses.find((r: Row) => r.supplier_id === s.id)?.answers[
              q.id
            ] ?? 'No response',
        ),
      ]),
    );
  }
  return (
    <>
      <button className="back-link" onClick={onBack}>
        <ArrowLeft size={15} />
        All RFIs
      </button>
      <div className="detail-heading">
        <div>
          <span className="reference">
            {rfi.number} · VERSION {rfi.version}
          </span>
          <h2>{rfi.title}</h2>
          <div className="detail-meta">
            <Status>{rfi.status}</Status>
            <span>Closes {dateLabel(rfi.closing_date)}</span>
            <span>{data.user.region}</span>
            <span>{rfi.classification}</span>
          </div>
        </div>
        <div className="inline-fields">
          {data.user.permissions.includes('rfi:create') && (
            <Button
              variant="outline"
              onClick={async () => {
                const r = await action('/rfis/' + id + '/clone');
                if (r) onOpen(r.id);
              }}
            >
              <Copy size={15} />
              Clone
            </Button>
          )}
          {canManage &&
            ['Approved', 'Issued', 'Open', 'Response Received'].includes(
              rfi.status,
            ) && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => action('/rfis/' + id + '/amend')}
              >
                Open amendment
              </Button>
            )}
          {rfi.status === 'Draft' && (
            <Button variant="outline" onClick={() => onEdit(rfi)}>
              Edit draft
            </Button>
          )}
          {next[rfi.status] && (canManage || rfi.status === 'Draft') && (
            <Button
              className="primary-button"
              disabled={busy}
              onClick={() =>
                action('/rfis/' + id + '/status', { status: next[rfi.status] })
              }
            >
              {next[rfi.status] === 'Issued'
                ? 'Issue approved RFI'
                : next[rfi.status] === 'Internal Review'
                  ? 'Submit for review'
                  : 'Move to ' + next[rfi.status]}
              <ArrowRight size={15} />
            </Button>
          )}
        </div>
      </div>
      <ErrorBox error={error} />
      <section className="panel module-panel">
        <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
          <TabsList className="workspace-tabs wide-tabs">
            {[
              'overview',
              'questions',
              'suppliers',
              'responses',
              'comparison',
              'clarification',
              'ai-analysis',
              'documents',
              'activity',
            ].map((t) => (
              <TabsTrigger key={t} value={t}>
                {t[0].toUpperCase() + t.slice(1)}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="overview">
            <div className="detail-body">
              <h3>Business requirement</h3>
              <p className="body-copy">{rfi.requirement}</p>
              <div className="info-grid">
                <div>
                  <ClipboardList />
                  <strong>{rfi.questions.length}</strong>
                  <span>Questions</span>
                </div>
                <div>
                  <Building2 />
                  <strong>{suppliers.length}</strong>
                  <span>Selected suppliers</span>
                </div>
                <div>
                  <FileText />
                  <strong>{rfi.responses.length}</strong>
                  <span>Responses received</span>
                </div>
              </div>
              <h3>RFI lifecycle</h3>
              <div className="lifecycle">
                {[
                  'Draft',
                  'Internal Review',
                  'Approved',
                  'Issued',
                  'Open',
                  'Closed',
                  'Analysis',
                  'Completed',
                  'Archived',
                ].map((s) => (
                  <span className={rfi.status === s ? 'current' : ''} key={s}>
                    {s}
                  </span>
                ))}
              </div>
              <div className="info-note">
                Supplier recommendations and procurement decisions remain
                subject to human review.
              </div>
            </div>
          </TabsContent>
          <TabsContent value="questions">
            <div className="detail-body">
              {rfi.questions.map((q: Row, i: number) => (
                <div className="read-question" key={q.id}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  <div>
                    <small>{q.section}</small>
                    <h3>{q.text}</h3>
                    <p>
                      {q.type} · {q.required ? 'Required' : 'Optional'}
                    </p>
                    {q.options?.length > 0 && <p>{q.options.join(' · ')}</p>}
                  </div>
                </div>
              ))}
              {!rfi.questions.length && (
                <Empty
                  title="No questions yet"
                  text="Edit the draft to add questions or use a category template."
                />
              )}
            </div>
          </TabsContent>
          <TabsContent value="suppliers">
            <div className="detail-body">
              <div className="toolbar">
                <h3>Selected suppliers</h3>
                {canManage &&
                  ['Issued', 'Open', 'Response Received'].includes(
                    rfi.status,
                  ) && (
                    <div className="inline-fields">
                      <Button
                        className="primary-button"
                        disabled={busy}
                        onClick={() => {
                          setError('');
                          setEmailOpen(true);
                        }}
                      >
                        <Mail size={16} />
                        Send email invitations
                      </Button>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={async () => {
                          const result = await action(
                            '/rfis/' + id + '/invitations',
                          );
                          if (result) setLinks(result);
                        }}
                      >
                        <Link2 size={16} />
                        Generate invitation links
                      </Button>
                    </div>
                  )}
              </div>
              {suppliers.map((s) => (
                <div className="supplier-line" key={s.id}>
                  <span className="supplier-logo">
                    {s.name.slice(0, 2).toUpperCase()}
                  </span>
                  <div>
                    <strong>{s.name}</strong>
                    <small>
                      {s.country} · {s.type}
                    </small>
                    <small>{s.email || 'Email not provided'}</small>
                  </div>
                  <Status>
                    {rfi.responses.some((r: Row) => r.supplier_id === s.id)
                      ? 'Response Received'
                      : 'Selected'}
                  </Status>
                </div>
              ))}
              {links.length > 0 && (
                <div className="info-note">
                  <p>
                    Secure links are ready to share. No email has been sent. New
                    links replace previous invitations.
                  </p>
                  {links.map((l) => (
                    <div className="invitation-row" key={l.supplier_id}>
                      <span>
                        {
                          data.suppliers.find((s) => s.id === l.supplier_id)
                            ?.name
                        }
                      </span>
                      <a href={l.path} target="_blank" rel="noreferrer">
                        Open response form
                        <ArrowRight size={14} />
                      </a>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          navigator.clipboard.writeText(
                            location.origin + l.path,
                          )
                        }
                      >
                        Copy link
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              {canManage && emails.length > 0 && (
                <section aria-label="Invitation email status">
                  <div className="toolbar">
                    <h3>Email status</h3>
                    <Button variant="outline" size="sm" onClick={loadEmails}>
                      <RefreshCw size={15} /> Refresh
                    </Button>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>RECIPIENT</TableHead>
                        <TableHead>STATUS</TableHead>
                        <TableHead>ATTEMPTS</TableHead>
                        <TableHead>ACTION</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {emails.map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>{row.recipient}</TableCell>
                          <TableCell>
                            <Status>
                              {row.status === 'SENT'
                                ? 'Accepted by SMTP'
                                : row.status}
                            </Status>
                            {row.error_code && (
                              <small className="table-category">
                                {row.error_code}
                              </small>
                            )}
                          </TableCell>
                          <TableCell>{row.attempts}</TableCell>
                          <TableCell>
                            {row.status === 'FAILED' && (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={busy}
                                onClick={async () => {
                                  const result = await action(
                                    `/rfis/${id}/emails/${row.id}/retry`,
                                  );
                                  if (result) await loadEmails();
                                }}
                              >
                                Retry email
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <p className="section-note">
                    SMTP acceptance does not confirm inbox delivery. UNKNOWN
                    means the server response was interrupted; check the sender
                    mailbox before creating another invitation.
                  </p>
                </section>
              )}
            </div>
          </TabsContent>
          <TabsContent value="responses">
            <div className="detail-body">
              {rfi.responses.map((r: Row) => (
                <article className="response-card" key={r.id}>
                  <div className="toolbar">
                    <h3>
                      {data.suppliers.find((s) => s.id === r.supplier_id)?.name}
                    </h3>
                    <Status>Submitted</Status>
                  </div>
                  <p className="section-note">
                    {dateLabel(r.submitted_at)} · Response locked
                  </p>
                  {rfi.questions.map((q: Row) => (
                    <div className="answer-row" key={q.id}>
                      <label>{q.text}</label>
                      <p>
                        {q.type === 'file attachment' && r.answers[q.id]?.id ? (
                          <a
                            href={'/api/v1/attachments/' + r.answers[q.id].id}
                            className="text-link"
                          >
                            {r.answers[q.id].name}
                            <Download size={14} />
                          </a>
                        ) : (
                          String(r.answers[q.id] ?? 'Not provided')
                        )}
                      </p>
                    </div>
                  ))}
                </article>
              ))}
              {!rfi.responses.length && (
                <Empty
                  title="Waiting for responses"
                  text="Supplier submissions will appear here."
                />
              )}
            </div>
          </TabsContent>
          <TabsContent value="comparison">
            <div className="detail-body">
              <div className="toolbar">
                <h3>Supplier comparison matrix</h3>
                <Button variant="outline" onClick={exportReport}>
                  <Download size={16} />
                  Export comparison
                </Button>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ATTRIBUTE</TableHead>
                    {suppliers.map((s) => (
                      <TableHead key={s.id}>{s.name}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rfi.questions.map((q: Row) => (
                    <TableRow key={q.id}>
                      <TableCell>{q.text}</TableCell>
                      {suppliers.map((s) => (
                        <TableCell key={s.id}>
                          {String(
                            rfi.responses.find(
                              (r: Row) => r.supplier_id === s.id,
                            )?.answers[q.id] ?? 'No response',
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="info-note">
                Evidence: supplier-submitted responses for {rfi.number}. Missing
                answers are shown explicitly. No supplier ranking or award is
                assigned.
              </div>
            </div>
          </TabsContent>
          <TabsContent value="clarification">
            <div className="detail-body">
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  const result = await action(
                    '/rfis/' + id + '/clarifications',
                    { text: clarification },
                  );
                  if (result) setClarification('');
                }}
              >
                <label className="field-label">
                  Add clarification
                  <Textarea
                    required
                    minLength={3}
                    value={clarification}
                    onChange={(e) => setClarification(e.target.value)}
                    placeholder="Ask a technical or commercial clarification…"
                  />
                </label>
                <Button
                  className="primary-button"
                  disabled={busy}
                  type="submit"
                >
                  Save clarification
                </Button>
              </form>
              {rfi.clarifications.map((c: Row) => (
                <div className="clarification-card" key={c.id}>
                  <div>
                    <Status>{c.status}</Status>
                    <small>{c.author}</small>
                  </div>
                  <p>{c.text}</p>
                  {canManage && c.status !== 'CLOSED' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        action('/clarifications/' + c.id, { status: 'CLOSED' })
                      }
                    >
                      Close clarification
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </TabsContent>
          <TabsContent value="ai-analysis">
            {['Buyer', 'Market Intelligence Analyst'].includes(
              data.user.role,
            ) && <AdvancedRFIAnalysis id={id} />}
          </TabsContent>
          <TabsContent value="documents">
            <div className="detail-body">
              {data.documents
                .filter((d) => d.rfi_id === id || d.rfi_number === rfi.number)
                .map((d) => (
                  <a
                    className="document-link"
                    key={d.id}
                    href={'/api/v1/repository/documents/' + d.id + '/download'}
                  >
                    <FileText size={20} />
                    {d.name}
                    <Download size={15} />
                  </a>
                ))}
              {!data.documents.some(
                (d) => d.rfi_id === id || d.rfi_number === rfi.number,
              ) && (
                <Empty
                  title="No linked documents"
                  text="The completed RFI will automatically become a repository knowledge source."
                />
              )}
            </div>
          </TabsContent>
          <TabsContent value="activity">
            <div className="detail-body">
              {rfi.history.map((h: Row, i: number) => (
                <div className="activity-row" key={i}>
                  <span className="live-dot" />
                  <div>
                    <strong>Moved to {h.status}</strong>
                    <p>
                      {h.actor} · {dateLabel(h.at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </section>
      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent>
          <DialogTitle>Send RFI invitations</DialogTitle>
          <DialogDescription>
            Each supplier below will receive an email with a secure response
            link for {rfi.number}: {rfi.title}. Responses close on{' '}
            {dateLabel(rfi.closing_date)}.
          </DialogDescription>
          <div>
            {suppliers.map((supplier) => (
              <p key={supplier.id}>
                <strong>{supplier.name}</strong>
                <br />
                {supplier.email || 'Email missing'}
              </p>
            ))}
          </div>
          <p className="section-note">
            Existing email invitations are kept. Suppliers without an email
            invitation receive a new link that replaces their previous manual
            link.
          </p>
          <ErrorBox error={error} />
          <div className="dialog-actions">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setEmailOpen(false)}
            >
              Cancel
            </Button>
            <Button
              className="primary-button"
              disabled={busy || !suppliers.length}
              onClick={async () => {
                const result = await action('/rfis/' + id + '/emails');
                if (result) {
                  setEmails(result);
                  setLinks([]);
                  setEmailOpen(false);
                  await loadEmails();
                }
              }}
            >
              <Send size={16} /> Confirm and send
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
export function SupplierResponse({
  token = '',
  endpoint,
}: {
  token?: string;
  endpoint?: string;
}) {
  const base = endpoint || '/respond/' + token;
  const [info, setInfo] = useState<Row | null>(null);
  const [answers, setAnswers] = useState<Row>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api(base)
      .then((r) => {
        setInfo(r);
        setAnswers(r.draft || {});
      })
      .catch((e) => setError(e.message));
  }, [base]);
  async function save(submit: boolean) {
    setBusy(true);
    setError('');
    try {
      await api(base, { answers, submit });
      setNotice(
        submit
          ? 'Your response was submitted successfully.'
          : 'Draft saved. You can return using this invitation link.',
      );
      if (submit) setInfo({ ...info, submitted: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="supplier-response">
      <div className="response-brand">
        greta<span>SUPPLIER RESPONSE</span>
      </div>
      <ErrorBox error={error} />
      {info && (
        <section className="panel">
          <div className="detail-body">
            <span className="reference">{info.number}</span>
            <h1>{info.title}</h1>
            <p className="section-note">
              Invitation for {info.supplier} · Closing{' '}
              {dateLabel(info.closing_date)}
            </p>
            <p className="body-copy">{info.requirement}</p>
            {info.submitted ? (
              <div className="success-box">
                <Check size={20} />
                Response submitted. Contact the buyer if a revision is needed.
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void save(true);
                }}
              >
                {info.questions
                  .filter(
                    (q: Row) =>
                      !q.condition ||
                      answers[q.condition.question_id] === q.condition.equals,
                  )
                  .map((q: Row) => (
                    <label className="response-field" key={q.id}>
                      {q.text}
                      {q.required && <span> *</span>}
                      {['yes/no', 'single choice'].includes(q.type) ? (
                        <Picker
                          value={answers[q.id] || ''}
                          onChange={(v) =>
                            setAnswers({ ...answers, [q.id]: v })
                          }
                          options={[
                            { value: '', label: 'Select an answer' },
                            ...(q.type === 'yes/no'
                              ? ['Yes', 'No']
                              : q.options || []),
                          ]}
                        />
                      ) : q.type === 'multiple choice' ? (
                        <div className="inline-fields">
                          {q.options.map((o: string) => (
                            <label className="check-label" key={o}>
                              <Checkbox
                                checked={(answers[q.id] || []).includes(o)}
                                onCheckedChange={(v) =>
                                  setAnswers({
                                    ...answers,
                                    [q.id]: v
                                      ? [...(answers[q.id] || []), o]
                                      : (answers[q.id] || []).filter(
                                          (x: string) => x !== o,
                                        ),
                                  })
                                }
                              />
                              {o}
                            </label>
                          ))}
                        </div>
                      ) : q.type === 'file attachment' ? (
                        <div>
                          <Input
                            type="file"
                            aria-label={q.text}
                            accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.html"
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              const body = new FormData();
                              body.set('file', file);
                              setBusy(true);
                              try {
                                const result = await api(
                                  base + '/attachments',
                                  body,
                                );
                                setAnswers({ ...answers, [q.id]: result });
                                setError('');
                              } catch (e) {
                                setError((e as Error).message);
                              } finally {
                                setBusy(false);
                              }
                            }}
                          />
                          {answers[q.id]?.name && (
                            <p className="section-note">
                              Uploaded: {answers[q.id].name}
                            </p>
                          )}
                        </div>
                      ) : ['long text', 'table'].includes(q.type) ? (
                        <Textarea
                          required={q.required}
                          rows={4}
                          value={answers[q.id] || ''}
                          onChange={(e) =>
                            setAnswers({ ...answers, [q.id]: e.target.value })
                          }
                          placeholder={
                            q.type === 'table'
                              ? 'Enter one row per line, columns separated by commas'
                              : ''
                          }
                        />
                      ) : (
                        <Input
                          required={q.required}
                          type={
                            [
                              'integer',
                              'decimal',
                              'currency',
                              'percentage',
                            ].includes(q.type)
                              ? 'number'
                              : q.type === 'date'
                                ? 'date'
                                : 'text'
                          }
                          step={q.type === 'integer' ? '1' : 'any'}
                          value={answers[q.id] ?? ''}
                          onChange={(e) =>
                            setAnswers({ ...answers, [q.id]: e.target.value })
                          }
                        />
                      )}
                    </label>
                  ))}
                <div className="dialog-actions">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => save(false)}
                  >
                    Save draft
                  </Button>
                  <Button
                    type="submit"
                    className="primary-button"
                    disabled={busy}
                  >
                    Submit final response
                    <Send size={16} />
                  </Button>
                </div>
              </form>
            )}
            {notice && <div className="success-box">{notice}</div>}
          </div>
        </section>
      )}
    </main>
  );
}
