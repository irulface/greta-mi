'use client';
import { useCallback, useEffect, useState } from 'react';
import {
  Plus,
  Download,
  RefreshCw,
  Bell,
  BookOpen,
  CalendarClock,
  FileText,
  Sparkles,
  Save,
  Globe2,
  ArrowRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
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
  api,
  Row,
  Workspace,
  Picker,
  Status,
  ErrorBox,
  Empty,
  dateLabel,
} from './shared';

const landscapeLabels = [
  'Leader',
  'Challenger',
  'Specialist',
  'Emerging Supplier',
  'New Entrant',
  'Local Supplier',
  'Global Supplier',
];
const today = () => new Date().toISOString().slice(0, 10);
const number = (value: unknown, suffix = '') =>
  typeof value === 'number'
    ? value.toLocaleString('en-GB', { maximumFractionDigits: 2 }) + suffix
    : '—';
const categoryOptions = (data: Workspace) =>
  data.categories.map((c) => ({ value: c.id, label: c.name }));
const modeOptions = [
  { value: 'evidence', label: 'Evidence digest' },
  { value: 'ai', label: 'Azure AI analysis' },
];

function TrendChart({ series }: { series: Row[] }) {
  const dates = [
    ...new Set(
      series.flatMap((s) => (s.observations || []).map((p: Row) => p.date)),
    ),
  ].sort() as string[];
  const plotted = dates.map((date) =>
    Object.fromEntries([
      ['date', date],
      ...series.map((s) => [
        s.id,
        s.observations.find((p: Row) => p.date === date)?.value,
      ]),
    ]),
  );
  if (!dates.length)
    return (
      <Empty
        title="No observations yet"
        text="Add observations, import a file, or synchronize a market source."
      />
    );
  return (
    <div
      className="mi-chart"
      role="img"
      aria-label={'Price history for ' + series.map((s) => s.name).join(', ')}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={plotted}
          margin={{ top: 12, right: 20, left: 18, bottom: 12 }}
        >
          <CartesianGrid strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="date" minTickGap={40} tick={{ fontSize: 12 }} />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => number(v)}
            width={75}
          />
          <Tooltip formatter={(v) => number(Number(v))} />
          <Legend />
          {series.map((s, i) => (
            <Line
              key={s.id}
              type="linear"
              dataKey={s.id}
              name={s.geography ? s.name + ' · ' + s.geography : s.name}
              stroke={['#357460', '#3469a1', '#b77632', '#93609a'][i % 4]}
              strokeWidth={2.5}
              dot={dates.length < 30}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Metrics({
  values,
}: {
  values: { label: string; value: string | number }[];
}) {
  return (
    <div className="mi-metrics">
      {values.map((metric) => (
        <div key={metric.label}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
        </div>
      ))}
    </div>
  );
}

function PinnedCharts({ references }: { references: Row[] }) {
  const ids = references
    .filter((ref) => ref.kind === 'price')
    .slice(0, 3)
    .map((ref) => ref.id)
    .join(',');
  const [charts, setCharts] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setCharts([]);
    setError('');
    if (ids)
      Promise.all(ids.split(',').map((id) => api(`/market/series/${id}`)))
        .then((rows) => {
          if (active) setCharts(rows);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [ids]);
  return (
    <>
      <ErrorBox error={error} />
      {charts.map((chart) => (
        <section key={chart.id}>
          <h4>
            {chart.name} · {chart.currency} / {chart.unit}
          </h4>
          <TrendChart series={[chart]} />
        </section>
      ))}
    </>
  );
}

function Report({ report }: { report: Row }) {
  return (
    <div className="mi-report">
      <div className="toolbar">
        <h3>{report.title}</h3>
        <Status>
          {report.mode === 'ai'
            ? 'AI assessment · Review required'
            : 'Evidence digest'}
        </Status>
      </div>
      {report.is_demo && (
        <div className="info-note">
          This report includes illustrative sources.
        </div>
      )}
      {report.findings && (
        <>
          <p className="section-note">{report.outlier_method}</p>
          <Table>
            <TableHeader>
              <TableRow>
                {[
                  'QUESTION',
                  'MIN / MEDIAN / MAX',
                  'MISSING',
                  'REVIEW FLAGS',
                ].map((label) => (
                  <TableHead key={label}>{label}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.findings.map((finding: Row) => (
                <TableRow key={finding.question_id}>
                  <TableCell>{finding.question}</TableCell>
                  <TableCell>
                    {[finding.min, finding.median, finding.max]
                      .map((n) => number(n))
                      .join(' / ')}
                  </TableCell>
                  <TableCell>{finding.missing_response_ids.length}</TableCell>
                  <TableCell>{finding.outlier_response_ids.length}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
      {report.sections.map((section: Row) => (
        <section key={section.title}>
          <h4>
            {section.title}{' '}
            {section.missing_data && <Status>Missing evidence</Status>}
          </h4>
          <p className="answer-text">{section.text}</p>
          <div className="mi-source-links">
            {section.citation_ids.map((id: string) => (
              <a key={id} href={'#citation-' + report.id + '-' + id}>
                {report.citations.find((citation: Row) => citation.id === id)
                  ?.name || id}
              </a>
            ))}
          </div>
        </section>
      ))}
      <h4>Source register</h4>
      {report.citations.map((citation: Row) => (
        <details
          className="mi-citation"
          id={'citation-' + report.id + '-' + citation.id}
          key={citation.id}
        >
          <summary>
            {citation.name} · {dateLabel(citation.as_of)}{' '}
            {citation.is_demo ? '· Sample' : ''}
          </summary>
          <pre>
            {typeof citation.snapshot === 'string'
              ? citation.snapshot
              : JSON.stringify(citation.snapshot, null, 2)}
          </pre>
        </details>
      ))}
      {!!report.tool_errors?.length && (
        <div className="info-note">
          Some enterprise sources were unavailable:{' '}
          {report.tool_errors.map((e: Row) => e.tool).join(', ')}.
        </div>
      )}
    </div>
  );
}

export function AdvancedRFIAnalysis({ id }: { id: string }) {
  const [reports, setReports] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    setSelected(null);
    api(`/market/rfis/${id}/analyses`)
      .then(setReports)
      .catch((e) => setError(e.message));
  }, [id]);
  async function run(mode: string) {
    setBusy(true);
    setError('');
    try {
      const report = await api(`/market/rfis/${id}/analysis`, { mode });
      setSelected(report);
      setReports(await api(`/market/rfis/${id}/analyses`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="detail-body">
      <h3>Advanced supplier analysis</h3>
      <p className="section-note">
        Compare final responses, numerical deviations, supplier profiles, market
        sources and authorized enterprise evidence.
      </p>
      <div className="inline-fields">
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => run('evidence')}
        >
          <FileText size={16} /> Analyze evidence
        </Button>
        <Button
          className="primary-button"
          disabled={busy}
          onClick={() => run('ai')}
        >
          <Sparkles size={16} /> Analyze with Azure AI
        </Button>
      </div>
      <ErrorBox error={error} />
      {!!reports.length && (
        <Picker
          value={selected?.id || ''}
          label="Saved analysis"
          options={[
            { value: '', label: 'Choose a saved analysis' },
            ...reports.map((r) => ({
              value: r.id,
              label: dateLabel(r.generated_at) + ' · ' + r.mode,
            })),
          ]}
          onChange={(value) =>
            setSelected(reports.find((r) => r.id === value) || null)
          }
        />
      )}
      {selected && <Report report={selected} />}
    </div>
  );
}

export function MarketIntelligence({
  data,
  refresh,
  onRFI,
  onAsk,
  initialTab = 'overview',
}: {
  data: Workspace;
  refresh: () => Promise<void>;
  onRFI: (id: string) => void;
  onAsk: (query: string) => void;
  initialTab?: string;
}) {
  const [tab, setTab] = useState(initialTab);
  const [category, setCategory] = useState('');
  const [includeDemo, setIncludeDemo] = useState(false);
  const [store, setStore] = useState<Row>({
    series: [],
    events: [],
    workspaces: [],
    views: [],
    briefs: [],
    rules: [],
    alerts: [],
    providers: [],
    schedules: [],
  });
  const [dashboard, setDashboard] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState('');
  const [form, setForm] = useState<Row>({});
  const [seriesId, setSeriesId] = useState('');
  const [detail, setDetail] = useState<Row | null>(null);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Row | null>(null);
  const [references, setReferences] = useState<Row[]>([]);
  const [users, setUsers] = useState<Row[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Row | null>(null);
  const [viewResults, setViewResults] = useState<Row | null>(null);
  const [report, setReport] = useState<Row | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const canWrite = data.user.permissions.includes('market:write');
  const canResearch = ['Buyer', 'Market Intelligence Analyst'].includes(
    data.user.role,
  );
  const isAdmin = data.user.role === 'Admin';
  const suffix = `?category=${encodeURIComponent(category)}&include_demo=${includeDemo}`;
  const load = useCallback(async () => {
    try {
      const names = [
        'series',
        'events',
        'workspaces',
        'views',
        'briefs',
        'rules',
        'alerts',
        'providers',
        'schedules',
      ];
      const results = await Promise.all(
        names.map((name) =>
          api(
            '/market/' +
              name +
              (['series', 'events'].includes(name) ? suffix : ''),
          ),
        ),
      );
      setStore(Object.fromEntries(names.map((name, i) => [name, results[i]])));
      setDashboard(await api('/market/dashboard' + suffix));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [suffix, data.user.id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (canResearch)
      api('/market/shareable-users')
        .then(setUsers)
        .catch((e) => setError(e.message));
  }, [canResearch, data.user.id]);
  useEffect(() => {
    if (!seriesId) {
      setDetail(null);
      return;
    }
    let active = true;
    api(
      `/market/series/${seriesId}?${new URLSearchParams({ ...(start ? { start } : {}), ...(end ? { end } : {}) })}`,
    )
      .then((row) => {
        if (active) setDetail(row);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [seriesId, start, end, store.series]);
  useEffect(() => {
    if (!['alerts', 'sources', 'briefs'].includes(tab)) return;
    const timer = setInterval(() => void load(), 15000);
    return () => clearInterval(timer);
  }, [tab, load]);
  async function action(path: string, body: unknown = {}, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api(path, body, method);
      await load();
      await refresh();
      if (result.status === 'Connected')
        setNotice(
          `Connection verified · ${result.observations ?? 0} observations available. No data saved.`,
        );
      else if (typeof result.inserted === 'number')
        setNotice(
          `Saved ${result.inserted} new observations; corrected ${result.updated}; unchanged ${result.unchanged}.`,
        );
      else if (typeof result.created === 'number')
        setNotice(`Evaluation completed · ${result.created} new alerts.`);
      else if (result.status === 'PENDING')
        setNotice('Task queued. The worker will process it shortly.');
      return result;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function open(kind: string, value: Row) {
    setError('');
    setForm(value);
    setModal(kind);
  }
  async function openWorkspace(value?: Row) {
    setBusy(true);
    setError('');
    try {
      const [refs, people] = await Promise.all([
        api('/market/references'),
        api('/market/shareable-users'),
      ]);
      setReferences(refs);
      setUsers(people);
      open(
        'workspace',
        value
          ? { ...value }
          : {
              title: '',
              category_id: category,
              notes: '',
              reference_ids: [],
              shared_with: [],
              version: 1,
            },
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const set = (key: string, value: unknown) =>
    setForm((current) => ({ ...current, [key]: value }));
  const field = (
    key: string,
    label: string,
    type = 'text',
    required = true,
  ) => (
    <label key={key} htmlFor={'market-' + key}>
      {label}
      <Input
        id={'market-' + key}
        type={type}
        step={type === 'number' ? 'any' : undefined}
        required={required}
        value={form[key] ?? ''}
        onChange={(e) => set(key, e.target.value)}
      />
    </label>
  );
  const area = (key: string, label: string, required = false) => (
    <label key={key} className="full" htmlFor={'market-' + key}>
      {label}
      <Textarea
        id={'market-' + key}
        required={required}
        rows={4}
        value={form[key] || ''}
        onChange={(e) => set(key, e.target.value)}
      />
    </label>
  );
  const choice = (
    key: string,
    label: string,
    options: (string | { value: string; label: string })[],
  ) => (
    <label key={key}>
      {label}
      <Picker
        value={form[key] ?? ''}
        label={label}
        onChange={(v) => set(key, v)}
        options={options}
      />
    </label>
  );
  const scopedSuppliers = data.suppliers.filter(
    (s) =>
      (!category || s.category_id === category) && (includeDemo || !s.is_demo),
  );
  const seriesOptions = store.series.map((s: Row) => ({
    value: s.id,
    label: s.name + ' · ' + s.geography,
  }));
  const categoryDefault = category || data.categories[0]?.id || '';
  function openSeries() {
    open('series', {
      name: '',
      commodity: '',
      category_id: categoryDefault,
      geography: 'Indonesia',
      currency: 'USD',
      unit: 'MT',
      metric_type: 'price',
      frequency: 'monthly',
      source: '',
      notes: '',
    });
  }

  return (
    <div className="market-intelligence">
      <div className="toolbar mi-main-toolbar">
        <div>
          <span className="eyebrow">MARKET INTELLIGENCE</span>
          <h2>Market research & monitoring</h2>
        </div>
        <div className="inline-fields">
          <Picker
            value={category}
            onChange={(value) => {
              setCategory(value);
              setSeriesId('');
              setComparison(null);
            }}
            label="Category"
            options={[
              { value: '', label: 'All categories' },
              ...categoryOptions(data),
            ]}
          />
          <Button variant="outline" disabled={busy} onClick={load}>
            <RefreshCw size={16} /> Refresh
          </Button>
        </div>
      </div>
      <div className="toolbar">
        <label className="check-label">
          <Checkbox
            checked={includeDemo}
            onCheckedChange={(value) => setIncludeDemo(!!value)}
          />{' '}
          Include illustrative records
        </label>
        <span className="section-note">
          {data.user.region} · Sources retain their observation dates
        </span>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <div className="success-box" role="status">
          {notice}
        </div>
      )}
      <Tabs value={tab} onValueChange={(value) => setTab(String(value))}>
        <TabsList className="workspace-tabs wide-tabs">
          {[
            ['overview', 'Overview'],
            ['prices', 'Price series'],
            ['events', 'Market events'],
            ['landscape', 'Supplier landscape'],
            ['research', 'Research workspaces'],
            ['briefs', 'Briefs'],
            ['alerts', 'Alerts'],
            ['sources', 'Sources & schedules'],
          ].map(([id, label]) => (
            <TabsTrigger key={id} value={id}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="overview">
          {dashboard && (
            <>
              <Metrics
                values={[
                  { label: 'Observed series', value: dashboard.counts.series },
                  {
                    label: 'Observations',
                    value: dashboard.counts.observations,
                  },
                  { label: 'Market events', value: dashboard.counts.events },
                  { label: 'Open alerts', value: dashboard.counts.open_alerts },
                ]}
              />
              <div className="mi-two-columns">
                <section className="panel detail-body">
                  <h3>Price movements</h3>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SERIES</TableHead>
                        <TableHead>AS OF</TableHead>
                        <TableHead>MoM</TableHead>
                        <TableHead>VOLATILITY</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dashboard.series.map((s: Row) => (
                        <TableRow key={s.id}>
                          <TableCell>
                            <button
                              className="text-link"
                              onClick={() => {
                                setSeriesId(s.id);
                                setTab('prices');
                              }}
                            >
                              {s.name}
                            </button>
                            {s.is_demo && <Status>Sample</Status>}
                          </TableCell>
                          <TableCell>{s.statistics.as_of || '—'}</TableCell>
                          <TableCell>{number(s.statistics.mom, '%')}</TableCell>
                          <TableCell>
                            {number(s.statistics.volatility, '%')}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {!dashboard.series.length && (
                    <Empty
                      title="Start with a market series"
                      text="Create a series and add sourced observations to calculate trends."
                    />
                  )}
                  {canWrite && (
                    <Button variant="outline" onClick={openSeries}>
                      <Plus size={16} /> Create series
                    </Button>
                  )}
                </section>
                <section className="panel detail-body">
                  <h3>Supplier landscape</h3>
                  {dashboard.supplier_landscape.map((group: Row) => (
                    <div className="mi-bar-row" key={group.classification}>
                      <span>{group.classification}</span>
                      <div>
                        <i
                          style={{
                            width: `${dashboard.counts.suppliers ? (group.count / dashboard.counts.suppliers) * 100 : 0}%`,
                          }}
                        />
                      </div>
                      <strong>{group.count}</strong>
                    </div>
                  ))}
                  <p className="section-note">
                    Classifications are recorded by analysts.
                  </p>
                </section>
              </div>
              <section className="panel detail-body">
                <div className="toolbar">
                  <h3>Category evidence</h3>
                  {category && (
                    <Button
                      variant="outline"
                      onClick={() =>
                        onAsk(
                          'Research market conditions for ' +
                            data.categories.find((c) => c.id === category)
                              ?.name,
                        )
                      }
                    >
                      <Sparkles size={16} /> Research category
                    </Button>
                  )}
                </div>
                <Metrics
                  values={[
                    { label: 'Suppliers', value: dashboard.counts.suppliers },
                    { label: 'Historical RFIs', value: dashboard.counts.rfis },
                    { label: 'Documents', value: dashboard.counts.documents },
                  ]}
                />
                <div className="mi-card-grid">
                  {data.rfis
                    .filter(
                      (r) =>
                        (!category || r.category_id === category) &&
                        (includeDemo || !r.is_demo),
                    )
                    .slice(0, 6)
                    .map((r) => (
                      <button
                        className="mi-reference-card"
                        key={r.id}
                        onClick={() => onRFI(r.id)}
                      >
                        <FileText size={18} />
                        <strong>{r.title}</strong>
                        <Status>{r.status}</Status>
                        <ArrowRight size={15} />
                      </button>
                    ))}
                </div>
              </section>
            </>
          )}
        </TabsContent>
        <TabsContent value="prices">
          <section className="panel detail-body">
            <div className="toolbar">
              <Picker
                value={seriesId}
                onChange={(v) => {
                  setSeriesId(v);
                  setComparison(null);
                }}
                label="Price series"
                options={[
                  { value: '', label: 'Select a series' },
                  ...seriesOptions,
                ]}
              />
              {canWrite && (
                <Button className="primary-button" onClick={openSeries}>
                  <Plus size={16} /> Create series
                </Button>
              )}
            </div>
            {detail ? (
              <>
                <div className="toolbar">
                  <div>
                    <h3>
                      {detail.name} {detail.is_demo && <Status>Sample</Status>}
                    </h3>
                    <p className="section-note">
                      {detail.commodity} · {detail.geography} ·{' '}
                      {detail.currency} / {detail.unit} · {detail.frequency}
                    </p>
                    <p className="section-note">Source: {detail.source}</p>
                  </div>
                  <Button
                    variant="outline"
                    render={
                      <a href={`/api/v1/market/series/${detail.id}/export`} />
                    }
                  >
                    <Download size={16} /> Export CSV
                  </Button>
                </div>
                <div className="inline-fields">
                  <label>
                    From
                    <Input
                      aria-label="From observation date"
                      type="date"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    To
                    <Input
                      aria-label="To observation date"
                      type="date"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                </div>
                <Metrics
                  values={[
                    {
                      label:
                        'Latest · ' + (detail.statistics.as_of || 'No date'),
                      value: number(detail.statistics.latest),
                    },
                    { label: 'MoM', value: number(detail.statistics.mom, '%') },
                    { label: 'QoQ', value: number(detail.statistics.qoq, '%') },
                    { label: 'YoY', value: number(detail.statistics.yoy, '%') },
                    {
                      label: 'CAGR',
                      value: number(detail.statistics.cagr, '%'),
                    },
                    {
                      label: '7 observations average',
                      value: number(detail.statistics.ma_7),
                    },
                    {
                      label: '30 observations average',
                      value: number(detail.statistics.ma_30),
                    },
                    {
                      label: 'Return volatility',
                      value: number(detail.statistics.volatility, '%'),
                    },
                    {
                      label: 'High / low',
                      value:
                        number(detail.statistics.high) +
                        ' / ' +
                        number(detail.statistics.low),
                    },
                  ]}
                />
                <TrendChart series={[detail]} />
                <p className="section-note">
                  Period changes use the latest observation against the nearest
                  prior observation at the calendar offset (maximum 40-day gap).
                  A dash means insufficient history. Volatility is the sample
                  standard deviation of consecutive observed returns; it is not
                  annualized.
                </p>
                {canWrite && !detail.is_demo && (
                  <div className="mi-import-bar">
                    <Button
                      variant="outline"
                      onClick={() =>
                        open('observation', {
                          date: today(),
                          value: '',
                          confidence: 1,
                          source: detail.source,
                          notes: '',
                        })
                      }
                    >
                      <Plus size={16} /> Add observation
                    </Button>
                    <label className="check-label">
                      <Checkbox
                        checked={replaceExisting}
                        onCheckedChange={(v) => setReplaceExisting(!!v)}
                      />{' '}
                      Replace existing dates
                    </label>
                    <label className="mi-file-label">
                      Import CSV / XLSX
                      <Input
                        type="file"
                        accept=".csv,.xlsx"
                        disabled={busy}
                        onChange={async (event) => {
                          const file = event.target.files?.[0];
                          if (!file) return;
                          const body = new FormData();
                          body.set('file', file);
                          const result = await action(
                            `/market/series/${detail.id}/import?replace_existing=${replaceExisting}`,
                            body,
                          );
                          if (result)
                            setNotice(
                              `Imported ${result.inserted}; corrected ${result.updated}; unchanged ${result.unchanged}.`,
                            );
                          event.target.value = '';
                        }}
                      />
                    </label>
                    <p className="section-note">
                      Columns: date (YYYY-MM-DD), value, confidence (0–1),
                      source, notes. Maximum 10,000 rows / 5 MB. Numeric Excel
                      values only.
                    </p>
                  </div>
                )}
                <details>
                  <summary>
                    Observation table · {detail.observations.length} rows
                  </summary>
                  <div className="mi-table-scroll">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {[
                            'DATE',
                            'VALUE',
                            'CONFIDENCE',
                            'SOURCE',
                            'NOTES',
                          ].map((h) => (
                            <TableHead key={h}>{h}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.observations.map((p: Row) => (
                          <TableRow key={p.date}>
                            <TableCell>{p.date}</TableCell>
                            <TableCell>{number(p.value)}</TableCell>
                            <TableCell>
                              {number(p.confidence * 100, '%')}
                            </TableCell>
                            <TableCell>{p.source}</TableCell>
                            <TableCell>{p.notes}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </details>
              </>
            ) : (
              <Empty
                title="Select a price or operational series"
                text="Inspect observations, calculations and their sources. Lead time and inventory coverage series can also support alerts."
              />
            )}
          </section>
          <section className="panel detail-body">
            <h3>Regional comparison</h3>
            <p className="section-note">
              Select 2–4 series with matching commodity, currency, unit and
              metric. Values are compared on the latest common observation date.
            </p>
            <div className="mi-check-grid">
              {store.series.map((s: Row) => (
                <label className="check-label" key={s.id}>
                  <Checkbox
                    checked={comparisonIds.includes(s.id)}
                    onCheckedChange={(v) =>
                      setComparisonIds(
                        v
                          ? [...comparisonIds, s.id]
                          : comparisonIds.filter((id) => id !== s.id),
                      )
                    }
                  />
                  {s.name} · {s.geography}
                </label>
              ))}
            </div>
            <Button
              variant="outline"
              disabled={
                busy || comparisonIds.length < 2 || comparisonIds.length > 4
              }
              onClick={async () => {
                setError('');
                try {
                  setComparison(
                    await api(
                      '/market/comparison?ids=' + comparisonIds.join(','),
                    ),
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Compare regions
            </Button>
            {comparison && (
              <>
                <p className="section-note">Common date: {comparison.as_of}</p>
                <TrendChart series={comparison.series} />
                <Metrics
                  values={comparison.gaps.map((gap: Row) => ({
                    label:
                      comparison.series.find((s: Row) => s.id === gap.series_id)
                        .name + ' · vs first series',
                    value: number(gap.vs_first_pct, '%'),
                  }))}
                />
              </>
            )}
          </section>
        </TabsContent>
        <TabsContent value="events">
          <div className="toolbar">
            <h3>Market events</h3>
            {canWrite && (
              <Button
                className="primary-button"
                onClick={() =>
                  open('event', {
                    title: '',
                    category_id: categoryDefault,
                    description: '',
                    date: today(),
                    impact: 'Medium',
                    type: 'Market event',
                    source: '',
                    geography: '',
                    supplier_id: '',
                    expected_impact: '',
                    probability: 0.5,
                    assessment: '',
                  })
                }
              >
                <Plus size={16} /> Record event
              </Button>
            )}
          </div>
          <div className="events-grid">
            {store.events.map((event: Row) => (
              <article className="panel event-card" key={event.id}>
                <div className="signal-meta">
                  <Status>{event.type}</Status>
                  <span>{dateLabel(event.date)}</span>
                  {event.is_demo && <Status>Sample</Status>}
                </div>
                <h3>{event.title}</h3>
                <p>{event.description}</p>
                <p>Expected impact: {event.expected_impact || event.impact}</p>
                <p>
                  Probability: {number((event.probability ?? 0.5) * 100, '%')} ·{' '}
                  {event.geography || 'Geography not recorded'}
                </p>
                {event.assessment && (
                  <p>Analyst assessment: {event.assessment}</p>
                )}
                <p className="section-note">Source: {event.source}</p>
                {canWrite && !event.is_demo && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => open('event', event)}
                  >
                    Edit event
                  </Button>
                )}
              </article>
            ))}
          </div>
          {!store.events.length && (
            <Empty
              title="No sourced market events"
              text="Record changes in supply, logistics, regulations or prices and include your assessment."
            />
          )}
        </TabsContent>
        <TabsContent value="landscape">
          <div className="mi-landscape-grid">
            {landscapeLabels.map((label) => (
              <section className="panel detail-body" key={label}>
                <h3>
                  {label}{' '}
                  <Status>
                    {
                      scopedSuppliers.filter((s) => s.landscape === label)
                        .length
                    }
                  </Status>
                </h3>
                {scopedSuppliers
                  .filter((s) => s.landscape === label)
                  .map((s) => (
                    <div className="mi-supplier-card" key={s.id}>
                      <strong>{s.name}</strong>
                      <p>
                        {s.country} · {s.type}
                      </p>
                      {s.is_demo && <Status>Sample</Status>}
                      {s.landscape_history?.length > 0 && (
                        <p className="section-note">
                          {s.landscape_history.at(-1).rationale}
                        </p>
                      )}
                      {canWrite && !s.is_demo && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            open('landscape', {
                              id: s.id,
                              classification: s.landscape || 'New Entrant',
                              rationale: '',
                              source_ids: [],
                            })
                          }
                        >
                          Review classification
                        </Button>
                      )}
                    </div>
                  ))}
              </section>
            ))}
          </div>
          {scopedSuppliers
            .filter((s) => !landscapeLabels.includes(s.landscape))
            .map((s) => (
              <div className="supplier-line" key={s.id}>
                <strong>{s.name}</strong>
                <Status>Unclassified</Status>
                {canWrite && !s.is_demo && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      open('landscape', {
                        id: s.id,
                        classification: 'New Entrant',
                        rationale: '',
                        source_ids: [],
                      })
                    }
                  >
                    Classify supplier
                  </Button>
                )}
              </div>
            ))}
        </TabsContent>
        {/* Research, briefs, alerts and schedules are rendered below. */}
        <MarketResearchTabs
          {...{
            data,
            store,
            category,
            includeDemo,
            canResearch,
            canWrite,
            isAdmin,
            busy,
            action,
            open,
            openWorkspace,
            setTab,
            setSeriesId,
            onRFI,
            selectedWorkspace,
            setSelectedWorkspace,
            viewResults,
            setViewResults,
            report,
            setReport,
            setError,
          }}
        />
      </Tabs>
      <Dialog
        open={!!modal}
        onOpenChange={(value) => {
          if (!value) setModal('');
        }}
      >
        <DialogContent className="large-dialog">
          <DialogTitle>
            {
              (
                {
                  series: 'Create market series',
                  observation: 'Add observation',
                  event: 'Record market event',
                  landscape: 'Approve supplier classification',
                  workspace: 'Research workspace',
                  view: 'Save intelligence view',
                  brief: 'Generate market brief',
                  rule: 'Create alert rule',
                  provider: 'Configure market API',
                  schedule: 'Schedule market task',
                } as Record<string, string>
              )[modal]
            }
          </DialogTitle>
          <DialogDescription>
            Save sourced information within {data.user.region}. Required fields
            are validated before saving.
          </DialogDescription>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              let result;
              const pick = (keys: string[]) =>
                Object.fromEntries(keys.map((key) => [key, form[key]]));
              if (modal === 'series')
                result = await action('/market/series', form);
              if (modal === 'observation')
                result = await action(
                  `/market/series/${seriesId}/observations`,
                  {
                    observations: [
                      { ...form, confidence: Number(form.confidence) },
                    ],
                    replace_existing: replaceExisting,
                  },
                );
              if (modal === 'event')
                result = await action(
                  '/market/events' + (form.id ? '/' + form.id : ''),
                  {
                    ...pick([
                      'title',
                      'category_id',
                      'description',
                      'date',
                      'impact',
                      'type',
                      'source',
                      'geography',
                      'supplier_id',
                      'expected_impact',
                      'assessment',
                    ]),
                    probability: Number(form.probability),
                  },
                  form.id ? 'PUT' : 'POST',
                );
              if (modal === 'landscape')
                result = await action(
                  `/market/suppliers/${form.id}/landscape`,
                  pick(['classification', 'rationale', 'source_ids']),
                  'PUT',
                );
              if (modal === 'workspace')
                result = await action(
                  '/market/workspaces' + (form.id ? '/' + form.id : ''),
                  pick([
                    'title',
                    'category_id',
                    'notes',
                    'reference_ids',
                    'shared_with',
                    'version',
                  ]),
                  form.id ? 'PUT' : 'POST',
                );
              if (modal === 'view')
                result = await action('/market/views', form);
              if (modal === 'brief')
                result = await action('/market/briefs', form);
              if (modal === 'rule')
                result = await action(
                  '/market/rules' + (form.id ? '/' + form.id : ''),
                  {
                    ...pick([
                      'title',
                      'category_id',
                      'metric',
                      'series_id',
                      'benchmark_id',
                      'period',
                      'severity',
                      'enabled',
                    ]),
                    threshold: Number(form.threshold),
                  },
                  form.id ? 'PUT' : 'POST',
                );
              if (modal === 'provider')
                result = await action(
                  '/market/providers' + (form.id ? '/' + form.id : ''),
                  pick([
                    'name',
                    'provider',
                    'series_id',
                    'benchmark',
                    'endpoint',
                    'api_key',
                    'enabled',
                  ]),
                  form.id ? 'PUT' : 'POST',
                );
              if (modal === 'schedule')
                result = await action('/market/schedules', {
                  ...form,
                  interval_hours: Number(form.interval_hours),
                });
              if (result) {
                setModal('');
                setNotice('Saved successfully.');
                if (modal === 'series') {
                  setSeriesId(result.id);
                  setTab('prices');
                }
                if (modal === 'brief') setReport(result);
                if (modal === 'workspace') setSelectedWorkspace(result);
              }
            }}
          >
            <div className="form-grid">
              {modal === 'series' && (
                <>
                  {field('name', 'Series name')}
                  {choice('category_id', 'Category', categoryOptions(data))}
                  {field('commodity', 'Commodity / material')}
                  {field('geography', 'Geographic market')}
                  {choice('metric_type', 'Metric', [
                    'price',
                    'index',
                    'lead_time',
                    'inventory_coverage',
                  ])}
                  {choice('frequency', 'Frequency', [
                    'daily',
                    'weekly',
                    'monthly',
                    'quarterly',
                    'irregular',
                  ])}
                  {field(
                    'currency',
                    'Currency (prices only)',
                    'text',
                    form.metric_type === 'price',
                  )}
                  {field('unit', 'Unit (MT, BBL, weeks, months…)')}
                  {field('source', 'Source')}
                  {area('notes', 'Analyst notes')}
                </>
              )}
              {modal === 'observation' && (
                <>
                  {field('date', 'Observation date', 'date')}
                  {field('value', 'Value', 'number')}
                  {field('confidence', 'Confidence (0–1)', 'number')}
                  {field('source', 'Source')}
                  {area('notes', 'Notes')}
                </>
              )}
              {modal === 'event' && (
                <>
                  {field('title', 'Title')}
                  {choice('category_id', 'Category', categoryOptions(data))}
                  {field('date', 'Event date', 'date')}
                  {field('type', 'Event type')}
                  {field('geography', 'Geography', 'text', false)}
                  {choice('supplier_id', 'Supplier (optional)', [
                    { value: '', label: 'No specific supplier' },
                    ...data.suppliers.map((s) => ({
                      value: s.id,
                      label: s.name,
                    })),
                  ])}
                  {choice('impact', 'Impact', ['Low', 'Medium', 'High'])}
                  {field('probability', 'Probability (0–1)', 'number')}
                  {field('source', 'Source')}
                  {area('description', 'Description', true)}
                  {area('expected_impact', 'Expected impact')}
                  {area('assessment', 'Analyst assessment')}
                </>
              )}
              {modal === 'landscape' && (
                <>
                  {choice('classification', 'Classification', landscapeLabels)}
                  {area(
                    'rationale',
                    'Analyst rationale (minimum 10 characters)',
                    true,
                  )}
                </>
              )}
              {modal === 'workspace' && (
                <>
                  {field('title', 'Title')}
                  {choice('category_id', 'Category', [
                    { value: '', label: 'Cross-category research' },
                    ...categoryOptions(data),
                  ])}
                  {area('notes', 'Research notes')}
                  <div className="full">
                    <h4>Charts, datasets, searches and evidence</h4>
                    <div className="mi-check-grid mi-selection-list">
                      {references.map((ref) => (
                        <label className="check-label" key={ref.id}>
                          <Checkbox
                            checked={form.reference_ids.includes(ref.id)}
                            onCheckedChange={(v) =>
                              set(
                                'reference_ids',
                                v
                                  ? [...form.reference_ids, ref.id]
                                  : form.reference_ids.filter(
                                      (id: string) => id !== ref.id,
                                    ),
                              )
                            }
                          />
                          {ref.title} <small>{ref.kind}</small>
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="full">
                    <h4>Share read access</h4>
                    <p className="section-note">
                      Recipients see only sources their role and data scope
                      allow. Private conversations remain accessible to their
                      owner.
                    </p>
                    <div className="mi-check-grid">
                      {users.map((person) => (
                        <label className="check-label" key={person.id}>
                          <Checkbox
                            checked={form.shared_with.includes(person.id)}
                            onCheckedChange={(v) =>
                              set(
                                'shared_with',
                                v
                                  ? [...form.shared_with, person.id]
                                  : form.shared_with.filter(
                                      (id: string) => id !== person.id,
                                    ),
                              )
                            }
                          />
                          {person.name} · {person.role}
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {modal === 'view' && (
                <>
                  {field('title', 'View name')}
                  {choice('target', 'Search in', [
                    'price',
                    'event',
                    'supplier',
                    'rfi',
                    'document',
                  ])}
                  {field('query', 'Query', 'text', false)}
                  {choice('category_id', 'Category', [
                    { value: '', label: 'All categories' },
                    ...categoryOptions(data),
                  ])}
                  {field('geography', 'Geography filter', 'text', false)}
                  {choice('supplier_type', 'Supplier type', [
                    '',
                    'Manufacturer',
                    'Distributor',
                    'Service provider',
                  ])}
                  <label className="check-label">
                    <Checkbox
                      checked={form.include_demo}
                      onCheckedChange={(v) => set('include_demo', !!v)}
                    />
                    Include illustrative data
                  </label>
                </>
              )}
              {modal === 'brief' && (
                <>
                  {choice('category_id', 'Category', categoryOptions(data))}
                  {choice('mode', 'Brief method', modeOptions)}
                  <label className="check-label">
                    <Checkbox
                      checked={form.include_demo}
                      onCheckedChange={(v) => set('include_demo', !!v)}
                    />
                    Include illustrative sources
                  </label>
                  <p className="section-note full">
                    Evidence digest uses recorded facts and calculations. Azure
                    AI adds interpretation when your Azure connection is
                    configured. Every brief retains a source register.
                  </p>
                  <div className="full">
                    <h4>Share brief with authorized colleagues</h4>
                    <div className="mi-check-grid">
                      {users.map((person) => (
                        <label className="check-label" key={person.id}>
                          <Checkbox
                            checked={form.shared_with.includes(person.id)}
                            onCheckedChange={(v) =>
                              set(
                                'shared_with',
                                v
                                  ? [...form.shared_with, person.id]
                                  : form.shared_with.filter(
                                      (id: string) => id !== person.id,
                                    ),
                              )
                            }
                          />
                          {person.name} · {person.role}
                        </label>
                      ))}
                    </div>
                    <p className="section-note">
                      Each recipient must have access to every source in the
                      brief.
                    </p>
                  </div>
                </>
              )}
              {modal === 'rule' && (
                <>
                  {field('title', 'Alert title')}
                  {choice('category_id', 'Category', categoryOptions(data))}
                  {choice('metric', 'Trigger', [
                    {
                      value: 'change_pct',
                      label: 'Percentage change above threshold',
                    },
                    { value: 'above', label: 'Value above threshold' },
                    { value: 'below', label: 'Value below threshold' },
                    {
                      value: 'benchmark_gap',
                      label: 'Premium above benchmark',
                    },
                    { value: 'new_document', label: 'New indexed document' },
                    { value: 'market_event', label: 'New market event' },
                  ])}
                  {choice('severity', 'Severity', ['Low', 'Medium', 'High'])}
                  {!['new_document', 'market_event'].includes(form.metric) && (
                    <>
                      {choice('series_id', 'Series', [
                        { value: '', label: 'Choose a real series' },
                        ...seriesOptions,
                      ])}
                      {field('threshold', 'Threshold', 'number')}
                      {form.metric === 'change_pct' &&
                        choice('period', 'Comparison period', [
                          'previous',
                          'mom',
                          'qoq',
                          'yoy',
                        ])}
                      {form.metric === 'benchmark_gap' &&
                        choice('benchmark_id', 'Benchmark series', [
                          { value: '', label: 'Choose compatible benchmark' },
                          ...seriesOptions,
                        ])}
                    </>
                  )}
                  <label className="check-label">
                    <Checkbox
                      checked={form.enabled}
                      onCheckedChange={(v) => set('enabled', !!v)}
                    />
                    Enabled
                  </label>
                </>
              )}
              {modal === 'provider' && (
                <>
                  {field('name', 'Source connection name')}
                  {choice('provider', 'Provider', ['eia', 'json'])}
                  {choice('series_id', 'Target series', [
                    { value: '', label: 'Choose a real series' },
                    ...seriesOptions,
                  ])}
                  {form.provider === 'eia'
                    ? choice('benchmark', 'EIA benchmark', ['brent', 'wti'])
                    : field('endpoint', 'HTTPS JSON endpoint', 'url')}
                  {field(
                    'api_key',
                    form.provider === 'eia'
                      ? 'EIA API key (blank retains saved key or uses DEMO_KEY)'
                      : 'Bearer token (blank retains saved token)',
                    'password',
                    false,
                  )}
                  <label className="check-label">
                    <Checkbox
                      checked={form.enabled}
                      onCheckedChange={(v) => set('enabled', !!v)}
                    />
                    Enabled
                  </label>
                  <p className="section-note full">
                    EIA requires monthly USD / BBL price series. JSON providers
                    return an observations array with date, value, confidence,
                    source and notes. Additional hosts must be enabled in the
                    server configuration.
                  </p>
                </>
              )}
              {modal === 'schedule' && (
                <>
                  {field('title', 'Schedule name')}
                  {choice('task_type', 'Task', [
                    { value: 'brief', label: 'Generate market brief' },
                    ...(canWrite
                      ? [
                          {
                            value: 'provider_sync',
                            label: 'Synchronize market API',
                          },
                        ]
                      : []),
                    { value: 'alerts', label: 'Evaluate alert rules' },
                  ])}
                  {form.task_type === 'brief' && (
                    <>
                      {choice('target_id', 'Category', categoryOptions(data))}
                      {choice('mode', 'Brief method', modeOptions)}
                    </>
                  )}
                  {form.task_type === 'provider_sync' &&
                    choice(
                      'target_id',
                      'API connection',
                      store.providers.map((p: Row) => ({
                        value: p.id,
                        label: p.name,
                      })),
                    )}
                  {field(
                    'interval_hours',
                    'Repeat every (hours, 1–720)',
                    'number',
                  )}
                  <label className="check-label">
                    <Checkbox
                      checked={form.enabled}
                      onCheckedChange={(v) => set('enabled', !!v)}
                    />
                    Enabled
                  </label>
                  <p className="section-note full">
                    Scheduled briefs use real sources. The first run is
                    scheduled after the interval; use Run now to queue an
                    immediate run.
                  </p>
                </>
              )}
            </div>
            <ErrorBox error={error} />
            <div className="dialog-actions">
              <Button
                type="button"
                variant="outline"
                onClick={() => setModal('')}
              >
                Cancel
              </Button>
              <Button className="primary-button" type="submit" disabled={busy}>
                <Save size={16} />
                {busy
                  ? 'Working…'
                  : modal === 'landscape'
                    ? 'Approve classification'
                    : modal === 'brief'
                      ? 'Generate brief'
                      : 'Save'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

type ResearchTabProps = {
  data: Workspace;
  store: Row;
  category: string;
  includeDemo: boolean;
  canResearch: boolean;
  canWrite: boolean;
  isAdmin: boolean;
  busy: boolean;
  action: (
    path: string,
    body?: unknown,
    method?: string,
  ) => Promise<Row | undefined>;
  open: (kind: string, value: Row) => void;
  openWorkspace: (value?: Row) => Promise<void>;
  setTab: (tab: string) => void;
  setSeriesId: (id: string) => void;
  onRFI: (id: string) => void;
  selectedWorkspace: Row | null;
  setSelectedWorkspace: (row: Row | null) => void;
  viewResults: Row | null;
  setViewResults: (row: Row | null) => void;
  report: Row | null;
  setReport: (row: Row | null) => void;
  setError: (error: string) => void;
};

function MarketResearchTabs(props: ResearchTabProps) {
  const [referenceDetail, setReferenceDetail] = useState<Row | null>(null);
  const {
    data,
    store,
    category,
    includeDemo,
    canResearch,
    canWrite,
    isAdmin,
    busy,
    action,
    open,
    openWorkspace,
    setTab,
    setSeriesId,
    onRFI,
    selectedWorkspace,
    setSelectedWorkspace,
    viewResults,
    setViewResults,
    report,
    setReport,
    setError,
  } = props;
  const categoryDefault = category || data.categories[0]?.id || '';
  async function openReference(ref: Row) {
    if (ref.kind === 'price') {
      setSeriesId(ref.id);
      setTab('prices');
    } else if (ref.kind === 'rfi') onRFI(ref.id);
    else if (ref.kind === 'market_brief') {
      setReport(store.briefs.find((r: Row) => r.id === ref.id) || null);
      setTab('briefs');
    } else if (ref.kind === 'saved_view') {
      try {
        setViewResults(await api(`/market/views/${ref.id}/results`));
      } catch (e) {
        setError((e as Error).message);
      }
    } else {
      try {
        setReferenceDetail(await api(`/market/references/${ref.id}`));
      } catch (e) {
        setError((e as Error).message);
      }
    }
  }
  return (
    <>
      <TabsContent value="research">
        <div className="toolbar">
          <h3>Research workspaces</h3>
          {canResearch && (
            <Button
              className="primary-button"
              disabled={busy}
              onClick={() => openWorkspace()}
            >
              <Plus size={16} /> Create workspace
            </Button>
          )}
        </div>
        <div className="mi-card-grid">
          {store.workspaces.map((workspace: Row) => (
            <button
              className="mi-reference-card"
              key={workspace.id}
              onClick={() => setSelectedWorkspace(workspace)}
            >
              <BookOpen size={20} />
              <strong>{workspace.title}</strong>
              <small>
                {workspace.references.length} sources ·{' '}
                {workspace.can_edit ? 'Owned by you' : 'Shared with you'}
              </small>
            </button>
          ))}
        </div>
        {!store.workspaces.length && (
          <Empty
            title="Bring your research together"
            text="Collect charts, saved searches, RFIs, supplier profiles, reports, conversations and notes in one workspace."
          />
        )}
        {selectedWorkspace && (
          <section className="panel detail-body">
            <div className="toolbar">
              <h3>{selectedWorkspace.title}</h3>
              {selectedWorkspace.can_edit && (
                <Button
                  variant="outline"
                  onClick={() => openWorkspace(selectedWorkspace)}
                >
                  Edit workspace
                </Button>
              )}
            </div>
            <p className="answer-text">
              {selectedWorkspace.notes || 'No notes yet.'}
            </p>
            <PinnedCharts references={selectedWorkspace.references} />
            <div className="mi-card-grid">
              {selectedWorkspace.references.map((ref: Row) =>
                ref.kind === 'document' ? (
                  <a
                    className="mi-reference-card"
                    key={ref.id}
                    href={`/api/v1/repository/documents/${ref.id}/download`}
                  >
                    <FileText size={16} />
                    <strong>{ref.title}</strong>
                    <small>Document · Open source</small>
                  </a>
                ) : (
                  <button
                    className="mi-reference-card"
                    key={ref.id}
                    onClick={() => openReference(ref)}
                  >
                    <FileText size={16} />
                    <strong>{ref.title}</strong>
                    <small>
                      {ref.kind}
                      {ref.is_demo ? ' · Sample' : ''}
                    </small>
                  </button>
                ),
              )}
            </div>
            {!!selectedWorkspace.unavailable_count && (
              <p className="section-note">
                {selectedWorkspace.unavailable_count} source(s) are unavailable
                under your current access.
              </p>
            )}
          </section>
        )}
        <section className="panel detail-body">
          <div className="toolbar">
            <h3>Saved intelligence views</h3>
            {canResearch && (
              <Button
                variant="outline"
                onClick={() =>
                  open('view', {
                    title: '',
                    target: 'supplier',
                    query: '',
                    category_id: category,
                    geography: '',
                    supplier_type: '',
                    include_demo: includeDemo,
                  })
                }
              >
                <Save size={16} /> Save a view
              </Button>
            )}
          </div>
          <div className="mi-card-grid">
            {store.views.map((view: Row) => (
              <button
                className="mi-reference-card"
                key={view.id}
                onClick={async () => {
                  try {
                    setViewResults(
                      await api(`/market/views/${view.id}/results`),
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                <strong>{view.title}</strong>
                <small>
                  {view.target} · {view.query || 'All matching records'}
                </small>
              </button>
            ))}
          </div>
          {viewResults && (
            <>
              <h4>
                {viewResults.view.title} · {viewResults.results.length} results
              </h4>
              {viewResults.results.map((ref: Row) => (
                <div className="supplier-line" key={ref.id}>
                  <FileText size={16} />
                  <strong>{ref.title}</strong>
                  <Status>{ref.kind}</Status>
                </div>
              ))}
            </>
          )}
        </section>
      </TabsContent>
      <TabsContent value="briefs">
        <div className="toolbar">
          <h3>Market intelligence briefs</h3>
          {canResearch && (
            <Button
              className="primary-button"
              onClick={() =>
                open('brief', {
                  category_id: categoryDefault,
                  mode: 'evidence',
                  include_demo: includeDemo,
                  shared_with: [],
                })
              }
            >
              <Sparkles size={16} /> Generate brief
            </Button>
          )}
        </div>
        <div className="mi-card-grid">
          {store.briefs
            .filter((r: Row) => !category || r.category_id === category)
            .map((brief: Row) => (
              <button
                className="mi-reference-card"
                key={brief.id}
                onClick={() => setReport(brief)}
              >
                <BookOpen size={20} />
                <strong>{brief.title}</strong>
                <span>
                  {brief.mode === 'ai' ? 'Azure AI' : 'Evidence digest'} ·{' '}
                  {brief.review_status}
                  {brief.is_demo ? ' · Includes sample data' : ''}
                </span>
              </button>
            ))}
        </div>
        {!store.briefs.length && (
          <Empty
            title="No intelligence briefs yet"
            text="Generate a sourced brief now or schedule recurring briefs from Sources & schedules."
          />
        )}
        {report && (
          <section className="panel detail-body">
            <div className="toolbar">
              <Status>{report.review_status}</Status>
              <div className="inline-fields">
                <Button
                  variant="outline"
                  render={
                    <a href={`/api/v1/market/briefs/${report.id}/export`} />
                  }
                >
                  <Download size={16} /> Export Markdown
                </Button>
                {canWrite && report.review_status !== 'REVIEWED' && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={async () => {
                      const result = await action(
                        `/market/briefs/${report.id}/review`,
                        { status: 'REVIEWED' },
                        'PUT',
                      );
                      if (result) setReport(result);
                    }}
                  >
                    Mark reviewed
                  </Button>
                )}
              </div>
            </div>
            <Report report={report} />
          </section>
        )}
      </TabsContent>
      <TabsContent value="alerts">
        <div className="toolbar">
          <h3>Personal market alerts</h3>
          {canResearch && (
            <div className="inline-fields">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => action('/market/rules/evaluate')}
              >
                <RefreshCw size={16} /> Evaluate now
              </Button>
              <Button
                className="primary-button"
                onClick={() =>
                  open('rule', {
                    title: '',
                    category_id: categoryDefault,
                    metric: 'change_pct',
                    series_id: '',
                    benchmark_id: '',
                    threshold: 10,
                    period: 'mom',
                    severity: 'Medium',
                    enabled: true,
                  })
                }
              >
                <Plus size={16} /> Add rule
              </Button>
            </div>
          )}
        </div>
        <p className="section-note">
          Enabled rules are evaluated by the worker every minute. Alerts appear
          here; repeated evaluation does not duplicate the same observation.
          Document/event rules monitor new records created after the rule.
        </p>
        {store.alerts
          .filter((a: Row) => !category || a.category_id === category)
          .map((alert: Row) => (
            <article className="panel detail-body" key={alert.id}>
              <div className="toolbar">
                <h3>
                  <Bell size={18} /> {alert.title}
                </h3>
                <div className="inline-fields">
                  <Status>{alert.severity}</Status>
                  <Status>{alert.status}</Status>
                </div>
              </div>
              <p>{alert.message}</p>
              <p className="section-note">
                Detected {new Date(alert.detected_at).toLocaleString('en-GB')}
              </p>
              <div className="inline-fields">
                {alert.status === 'OPEN' && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() =>
                      action(
                        `/market/alerts/${alert.id}`,
                        { status: 'ACKNOWLEDGED' },
                        'PUT',
                      )
                    }
                  >
                    Acknowledge
                  </Button>
                )}
                {alert.status !== 'RESOLVED' && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() =>
                      action(
                        `/market/alerts/${alert.id}`,
                        { status: 'RESOLVED' },
                        'PUT',
                      )
                    }
                  >
                    Resolve
                  </Button>
                )}
              </div>
            </article>
          ))}
        {!store.alerts.length && (
          <Empty
            title="No alerts triggered"
            text="Create a rule for price changes, quote premiums, lead time, inventory coverage or new sources."
          />
        )}
        <section className="panel detail-body">
          <h3>Your rules</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>RULE</TableHead>
                <TableHead>TRIGGER</TableHead>
                <TableHead>STATUS</TableHead>
                <TableHead>ACTION</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {store.rules.map((rule: Row) => (
                <TableRow key={rule.id}>
                  <TableCell>{rule.title}</TableCell>
                  <TableCell>
                    {rule.metric} · {rule.threshold}
                  </TableCell>
                  <TableCell>{rule.enabled ? 'Enabled' : 'Paused'}</TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => open('rule', rule)}
                    >
                      Edit rule
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      </TabsContent>
      <TabsContent value="sources">
        <div className="toolbar">
          <h3>External market sources</h3>
          {isAdmin && (
            <Button
              className="primary-button"
              onClick={() =>
                open('provider', {
                  name: '',
                  provider: 'eia',
                  series_id: '',
                  benchmark: 'brent',
                  endpoint: '',
                  api_key: '',
                  enabled: true,
                })
              }
            >
              <Plus size={16} /> Add API connection
            </Button>
          )}
        </div>
        {!isAdmin && (
          <p className="section-note">
            API credentials are managed by Admin. Analysts can synchronize
            configured sources and schedule updates.
          </p>
        )}
        {store.providers.map((provider: Row) => (
          <section className="panel detail-body" key={provider.id}>
            <div className="toolbar">
              <h3>
                <Globe2 size={19} /> {provider.name}
              </h3>
              <Status>{provider.enabled ? 'Enabled' : 'Disabled'}</Status>
            </div>
            <p>
              {provider.provider.toUpperCase()} ·{' '}
              {provider.last_sync
                ? 'Last sync ' +
                  new Date(provider.last_sync).toLocaleString('en-GB')
                : 'No sync yet'}
            </p>
            {provider.using_demo_key && (
              <p className="section-note">
                EIA exploration key · Limited request quota. Configure your
                organization’s key before regular scheduled use.
              </p>
            )}
            <div className="inline-fields">
              {canWrite && (
                <Button
                  variant="outline"
                  disabled={busy || !provider.enabled}
                  onClick={() =>
                    action(`/market/providers/${provider.id}/sync`)
                  }
                >
                  <RefreshCw size={16} /> Synchronize now
                </Button>
              )}
              {isAdmin && (
                <>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      action(`/market/providers/${provider.id}/test`)
                    }
                  >
                    Test connection
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      open('provider', { ...provider, api_key: '' })
                    }
                  >
                    Edit configuration
                  </Button>
                </>
              )}
            </div>
          </section>
        ))}
        {!store.providers.length && (
          <Empty
            title="No market API connected"
            text="Create a real target series, then ask Admin to configure EIA or an approved JSON provider."
          />
        )}
        <div className="toolbar">
          <h3>Scheduled intelligence</h3>
          {canResearch && (
            <Button
              variant="outline"
              onClick={() =>
                open('schedule', {
                  title: '',
                  task_type: 'brief',
                  target_id: categoryDefault,
                  interval_hours: 24,
                  mode: 'evidence',
                  enabled: true,
                })
              }
            >
              <CalendarClock size={16} /> Add schedule
            </Button>
          )}
        </div>
        {store.schedules.map((schedule: Row) => (
          <section className="panel detail-body" key={schedule.id}>
            <div className="toolbar">
              <div>
                <h3>{schedule.title}</h3>
                <p className="section-note">
                  {schedule.task_type} · Every {schedule.interval_hours} hours ·
                  Next: {new Date(schedule.next_run).toLocaleString('en-GB')}
                </p>
              </div>
              <div className="inline-fields">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    action(
                      `/market/schedules/${schedule.id}`,
                      { enabled: !schedule.enabled },
                      'PUT',
                    )
                  }
                >
                  {schedule.enabled ? 'Pause' : 'Enable'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() => action(`/market/schedules/${schedule.id}/run`)}
                >
                  Run now
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>RUN</TableHead>
                  <TableHead>STATUS</TableHead>
                  <TableHead>RESULT</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedule.runs.map((run: Row) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      {new Date(run.created_at).toLocaleString('en-GB')}
                    </TableCell>
                    <TableCell>
                      <Status>{run.status}</Status>
                    </TableCell>
                    <TableCell>
                      {run.error ||
                        (run.result_id ? (
                          <button
                            className="text-link"
                            onClick={() => {
                              setReport(
                                store.briefs.find(
                                  (r: Row) => r.id === run.result_id,
                                ) || null,
                              );
                              setTab('briefs');
                            }}
                          >
                            Open brief
                          </button>
                        ) : (
                          '—'
                        ))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        ))}
      </TabsContent>
      <Dialog
        open={!!referenceDetail}
        onOpenChange={(value) => {
          if (!value) setReferenceDetail(null);
        }}
      >
        <DialogContent className="large-dialog">
          <DialogTitle>
            {referenceDetail?.title ||
              referenceDetail?.name ||
              'Research source'}
          </DialogTitle>
          <DialogDescription>
            {referenceDetail?.kind} · Source details within your access scope
          </DialogDescription>
          {referenceDetail && (
            <div className="mi-report">
              {referenceDetail.kind === 'conversation' ? (
                referenceDetail.messages.map((message: Row) => (
                  <section key={message.id}>
                    <h4>{message.question}</h4>
                    <p className="answer-text">{message.answer}</p>
                  </section>
                ))
              ) : referenceDetail.sections ? (
                <Report report={referenceDetail} />
              ) : (
                <dl className="mi-source-details">
                  {Object.entries(referenceDetail)
                    .filter(
                      ([key, value]) =>
                        ![
                          'id',
                          'owner',
                          'kind',
                          'category_id',
                          'supplier_id',
                          'is_demo',
                          'shared_with',
                          'source_ids',
                          'landscape_history',
                        ].includes(key) &&
                        (typeof value === 'string' ||
                          typeof value === 'number'),
                    )
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{key.replaceAll('_', ' ')}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))}
                </dl>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
