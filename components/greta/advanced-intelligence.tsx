'use client';
import { useEffect, useState } from 'react';
import { Plus, ArrowLeft, Save, RefreshCw } from 'lucide-react';
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { api, Row, Workspace, Picker, Status, ErrorBox, Empty } from './shared';
import { Field, Options, JsonDownload } from './advanced-shared';
import { EnterprisePanel } from './enterprise';

const today = () => new Date().toISOString().slice(0, 10);
const n = (v: unknown) =>
  typeof v === 'number'
    ? v.toLocaleString('en-GB', { maximumFractionDigits: 4 })
    : '—';
const buckets = ['raw_material', 'labor', 'energy', 'logistics', 'other'];
const factors = [
  'financial',
  'delivery',
  'quality',
  'geopolitical',
  'concentration',
];
const labels: Row = {
  cost_model: 'Should-cost model',
  scenario: 'Cost scenario',
  forecast: 'Price forecast',
  supplier_risk: 'Supplier risk',
  recommendation: 'Procurement recommendation',
};

export function AdvancedIntelligence({ data }: { data: Workspace }) {
  const [tab, setTab] = useState('library');
  const [items, setItems] = useState<Row[]>([]);
  const [external, setExternal] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState<Row | null>(null);
  const [people, setPeople] = useState<Row[]>([]);
  async function refresh() {
    const [a, e, p] = await Promise.all([
      api('/advanced/analyses'),
      api('/enterprise/evidence'),
      api('/market/shareable-users'),
    ]);
    setItems(a);
    setExternal(e);
    setPeople(
      p.filter((u: Row) =>
        ['Buyer', 'Market Intelligence Analyst'].includes(u.role),
      ),
    );
  }
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api('/advanced/analyses'),
      api('/enterprise/evidence'),
      api('/market/shareable-users'),
    ])
      .then(([a, e, p]) => {
        if (cancelled) return;
        setItems(a);
        setExternal(e);
        setPeople(
          p.filter((u: Row) =>
            ['Buyer', 'Market Intelligence Analyst'].includes(u.role),
          ),
        );
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [data.user.id]);
  async function create(path: string, body: Row) {
    setBusy(true);
    setError('');
    try {
      const row = await api('/advanced/' + path, body);
      await refresh();
      setSelected(row);
      setTab('library');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!data.user.permissions.includes('procurement'))
    return (
      <Empty
        title="Buyer and Analyst workspace"
        text="Advanced decision support is available to procurement roles."
      />
    );
  const sources = [
    ...data.documents,
    ...data.prices,
    ...data.events,
    ...external,
  ];
  return (
    <div className="market-intelligence ai3">
      <ErrorBox error={error} />
      <div className="mi-intro">
        <p className="section-note">
          Turn sourced market evidence into cost models, forecasts and
          reviewable procurement decisions.
        </p>
        <Button
          variant="outline"
          onClick={() => refresh().catch((e) => setError(e.message))}
        >
          <RefreshCw size={15} />
          Refresh
        </Button>
      </div>
      <Tabs
        value={tab}
        onValueChange={(v) => {
          setTab(String(v));
          setSelected(null);
        }}
      >
        <TabsList className="workspace-tabs wide-tabs">
          {[
            ['library', 'Analysis library'],
            ['cost', 'Should-cost'],
            ['scenario', 'Scenarios'],
            ['forecast', 'Forecasting'],
            ['risk', 'Supplier risk'],
            ['recommend', 'Recommendations'],
            ['enterprise', 'External & workflow'],
          ].map(([id, label]) => (
            <TabsTrigger key={id} value={id}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="library">
          {selected ? (
            <AnalysisDetail
              row={selected}
              data={data}
              people={people}
              onChange={async (row) => {
                setSelected(row);
                await refresh();
              }}
              onBack={() => setSelected(null)}
              onRevise={() => {
                setRevision(selected);
                setSelected(null);
                setTab('cost');
              }}
            />
          ) : (
            <section className="panel detail-body">
              <h2>Saved analysis</h2>
              <p className="section-note">
                Each run preserves its inputs, results and sources. Sharing
                gives read access; editing a cost model creates a new revision.
              </p>
              {!items.length ? (
                <Empty
                  title="Start with your evidence"
                  text="Create a cost model or forecast to begin an analysis."
                />
              ) : (
                <div className="ai3-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Analysis</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <button
                              className="text-link"
                              onClick={() => {
                                setBusy(true);
                                api('/advanced/analyses/' + r.id)
                                  .then(setSelected)
                                  .catch((e) => setError(e.message))
                                  .finally(() => setBusy(false));
                              }}
                              disabled={busy}
                            >
                              {r.name}
                            </button>
                          </td>
                          <td>{labels[r.variant]}</td>
                          <td>
                            <Status>{r.status}</Status>
                          </td>
                          <td>{r.created_at?.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </TabsContent>
        <TabsContent value="cost">
          <CostForm
            key={revision?.id || 'new'}
            data={data}
            sources={sources}
            initial={revision}
            busy={busy}
            onSave={(v) => create('cost-models', v)}
            onNew={() => setRevision(null)}
          />
        </TabsContent>
        <TabsContent value="scenario">
          <ScenarioForm
            models={items.filter((r) => r.variant === 'cost_model')}
            busy={busy}
            onSave={(v) => create('scenarios', v)}
          />
        </TabsContent>
        <TabsContent value="forecast">
          <ForecastForm
            data={data}
            busy={busy}
            onSave={(v) => create('forecasts', v)}
          />
        </TabsContent>
        <TabsContent value="risk">
          <RiskForm
            data={data}
            sources={sources}
            busy={busy}
            onSave={(v) => create('supplier-risks', v)}
          />
        </TabsContent>
        <TabsContent value="recommend">
          <RecommendationForm
            data={data}
            items={items}
            busy={busy}
            onSave={(v) => create('recommendations', v)}
          />
        </TabsContent>
        <TabsContent value="enterprise">
          <EnterprisePanel data={data} analyses={items} onEvidence={refresh} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CostForm({
  data,
  sources,
  initial,
  busy,
  onSave,
  onNew,
}: {
  data: Workspace;
  sources: Row[];
  initial: Row | null;
  busy: boolean;
  onSave: (v: Row) => void;
  onNew: () => void;
}) {
  const [form, setForm] = useState<Row>({
    name: initial?.name || '',
    category_id: initial?.category_id || '',
    currency: initial?.currency || 'USD',
    output_unit: initial?.output_unit || '',
    margin_pct: initial?.margin_pct || 0,
    margin_method: initial?.margin_method || 'markup',
    assumptions: initial?.assumptions || '',
    parent_id: initial?.id || '',
  });
  const fresh = () => ({
    name: '',
    bucket: 'raw_material',
    quantity: 1,
    rate: '',
    currency: form.currency,
    fx_rate: 1,
    basis: '',
    as_of: today(),
    source_id: '',
  });
  const [components, setComponents] = useState<Row[]>(
    initial?.components || [fresh()],
  );
  function set(key: string, value: unknown) {
    setForm({ ...form, [key]: value });
  }
  function change(index: number, key: string, value: unknown) {
    setComponents(
      components.map((c, i) => (i === index ? { ...c, [key]: value } : c)),
    );
  }
  return (
    <form
      className="panel detail-body"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ ...form, components });
      }}
    >
      <h2>
        {initial
          ? 'Revise cost model · version ' + (initial.version + 1)
          : 'Build a should-cost model'}
      </h2>
      <p className="section-note">
        Enter the inputs needed for one output unit. FX is target currency per
        one source currency. A source-free input is an assumption, not verified
        evidence.
      </p>
      {initial && (
        <Button type="button" variant="outline" onClick={onNew}>
          Start a separate model
        </Button>
      )}
      <div className="ai3-grid">
        <Field label="Model name">
          <Input
            required
            minLength={3}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field label="Category">
          <Options
            rows={data.categories}
            value={form.category_id}
            onChange={(v) => set('category_id', v)}
          />
        </Field>
        <Field label="Target currency (ISO)">
          <Input
            required
            pattern="[A-Z]{3}"
            value={form.currency}
            onChange={(e) => set('currency', e.target.value.toUpperCase())}
          />
        </Field>
        <Field label="Output unit (e.g. MT, item, service)">
          <Input
            required
            value={form.output_unit}
            onChange={(e) => set('output_unit', e.target.value)}
          />
        </Field>
      </div>
      {components.map((c, i) => (
        <fieldset className="ai3-card" key={i}>
          <legend>Component {i + 1}</legend>
          <div className="ai3-grid">
            <Field label="Component name">
              <Input
                required
                minLength={2}
                value={c.name}
                onChange={(e) => change(i, 'name', e.target.value)}
              />
            </Field>
            <Field label="Cost driver">
              <Picker
                value={c.bucket}
                onChange={(v) => change(i, 'bucket', v)}
                options={buckets.map((b) => ({
                  value: b,
                  label: b.replaceAll('_', ' '),
                }))}
              />
            </Field>
            {['quantity', 'rate', 'fx_rate'].map((k) => (
              <Field
                key={k}
                label={
                  {
                    quantity: 'Input quantity per output unit',
                    rate: 'Price per input unit',
                    fx_rate: 'FX conversion rate',
                  }[k]!
                }
              >
                <Input
                  type="number"
                  step="any"
                  min={k === 'rate' ? 0 : 0.00000001}
                  required
                  value={c[k]}
                  onChange={(e) => change(i, k, e.target.value)}
                />
              </Field>
            ))}
            <Field label="Source currency">
              <Input
                required
                pattern="[A-Z]{3}"
                value={c.currency}
                onChange={(e) =>
                  change(i, 'currency', e.target.value.toUpperCase())
                }
              />
            </Field>
            <Field label="Evidence / assumption date">
              <Input
                required
                type="date"
                max={today()}
                value={c.as_of}
                onChange={(e) => change(i, 'as_of', e.target.value)}
              />
            </Field>
            <Field label="Linked evidence">
              <Options
                rows={sources}
                value={c.source_id}
                onChange={(v) => change(i, 'source_id', v)}
                placeholder="Manual assumption"
              />
            </Field>
          </div>
          <Field label="Basis, units and FX source">
            <Input
              required
              minLength={5}
              value={c.basis}
              onChange={(e) => change(i, 'basis', e.target.value)}
              placeholder="Explain the price, quantity basis and currency conversion."
            />
          </Field>
          {components.length > 1 && (
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setComponents(components.filter((_, j) => j !== i))
              }
            >
              Remove component
            </Button>
          )}
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        disabled={components.length >= 50}
        onClick={() => setComponents([...components, fresh()])}
      >
        <Plus size={16} />
        Add component
      </Button>
      <div className="ai3-grid">
        <Field label="Supplier margin (%)">
          <Input
            type="number"
            min="0"
            max="99.99"
            step="any"
            required
            value={form.margin_pct}
            onChange={(e) => set('margin_pct', e.target.value)}
          />
        </Field>
        <Field label="Margin calculation">
          <Picker
            value={form.margin_method}
            onChange={(v) => set('margin_method', v)}
            options={[
              { value: 'markup', label: 'Markup on cost: cost × (1 + %)' },
              { value: 'gross_margin', label: 'Gross margin: cost ÷ (1 − %)' },
            ]}
          />
        </Field>
      </div>
      <Field label="Scope and assumptions">
        <Textarea
          required
          minLength={10}
          value={form.assumptions}
          onChange={(e) => set('assumptions', e.target.value)}
          placeholder="State product specification, location, exclusions, and how the output unit is defined."
        />
      </Field>
      <Button disabled={busy || !form.category_id} className="primary-button">
        <Save size={16} />
        Calculate and save model
      </Button>
    </form>
  );
}

function ScenarioForm({
  models,
  busy,
  onSave,
}: {
  models: Row[];
  busy: boolean;
  onSave: (v: Row) => void;
}) {
  const [form, setForm] = useState<Row>({
    name: '',
    model_id: '',
    shocks: {},
    fx_change_pct: 0,
    margin_pct: null,
    volume: 1,
    assumptions: '',
  });
  const set = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  return (
    <form
      className="panel detail-body"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(form);
      }}
    >
      <h2>Compare a cost scenario</h2>
      <p className="section-note">
        Shocks apply to cost drivers. FX changes apply only to foreign-currency
        components. The original model stays available as the baseline.
      </p>
      <div className="ai3-grid">
        <Field label="Scenario name">
          <Input
            required
            minLength={3}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field label="Baseline model">
          <Options
            rows={models}
            value={form.model_id}
            onChange={(v) => set('model_id', v)}
          />
        </Field>
        {buckets.map((b) => (
          <Field key={b} label={b.replaceAll('_', ' ') + ' change (%)'}>
            <Input
              type="number"
              step="any"
              min="-100"
              max="1000"
              value={form.shocks[b] ?? 0}
              onChange={(e) =>
                set('shocks', { ...form.shocks, [b]: Number(e.target.value) })
              }
            />
          </Field>
        ))}
        <Field label="FX change (%)">
          <Input
            type="number"
            step="any"
            min="-99"
            max="1000"
            value={form.fx_change_pct}
            onChange={(e) => set('fx_change_pct', Number(e.target.value))}
          />
        </Field>
        <Field label="Scenario margin (%) — blank keeps baseline">
          <Input
            type="number"
            min="0"
            max="99.99"
            step="any"
            value={form.margin_pct ?? ''}
            onChange={(e) =>
              set(
                'margin_pct',
                e.target.value === '' ? null : Number(e.target.value),
              )
            }
          />
        </Field>
        <Field label="Procurement volume in output units">
          <Input
            required
            type="number"
            min="0.000001"
            step="any"
            value={form.volume}
            onChange={(e) => set('volume', Number(e.target.value))}
          />
        </Field>
      </div>
      <Field label="Scenario assumptions">
        <Textarea
          required
          minLength={10}
          value={form.assumptions}
          onChange={(e) => set('assumptions', e.target.value)}
        />
      </Field>
      <Button className="primary-button" disabled={busy || !form.model_id}>
        Run scenario
      </Button>
    </form>
  );
}
function ForecastForm({
  data,
  busy,
  onSave,
}: {
  data: Workspace;
  busy: boolean;
  onSave: (v: Row) => void;
}) {
  const [id, setId] = useState('');
  const [horizon, setHorizon] = useState(6);
  const [asOf, setAsOf] = useState(today());
  const [demo, setDemo] = useState(false);
  return (
    <form
      className="panel detail-body"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ series_id: id, horizon, as_of: asOf });
      }}
    >
      <h2>Forecast a market series</h2>
      <p className="section-note">
        At least 18 consecutive observations. Naïve, drift, and eligible
        seasonal baselines are compared using rolling-origin backtesting. Cutoff
        excludes later observations.
      </p>
      <div className="ai3-grid">
        <Field label="Market series">
          <Options
            rows={data.prices.filter((p) => demo || !p.is_demo)}
            value={id}
            onChange={setId}
          />
        </Field>
        <Field label="Forecast horizon (periods)">
          <Input
            type="number"
            required
            min="1"
            max="24"
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          />
        </Field>
        <Field label="Observation cutoff">
          <Input
            type="date"
            required
            max={today()}
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
          />
        </Field>
      </div>
      <label className="check-label">
        <input
          type="checkbox"
          checked={demo}
          onChange={(e) => setDemo(e.target.checked)}
        />
        Include illustrative series
      </label>
      <Button className="primary-button" disabled={busy || !id}>
        Backtest and forecast
      </Button>
    </form>
  );
}
function RiskForm({
  data,
  sources,
  busy,
  onSave,
}: {
  data: Workspace;
  sources: Row[];
  busy: boolean;
  onSave: (v: Row) => void;
}) {
  const [supplier, setSupplier] = useState('');
  const [valid, setValid] = useState(90);
  const [rows, setRows] = useState<Row[]>(
    factors.map((f) => ({
      factor: f,
      score: null,
      rationale: '',
      source_ids: [],
      as_of: today(),
    })),
  );
  function change(i: number, k: string, v: unknown) {
    setRows(rows.map((r, j) => (i === j ? { ...r, [k]: v } : r)));
  }
  return (
    <form
      className="panel detail-body"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ supplier_id: supplier, valid_days: valid, factors: rows });
      }}
    >
      <h2>Assess supplier risk</h2>
      <p className="section-note">
        Score 0–100, where higher means greater risk. Weights: financial 25%,
        delivery 25%, quality 20%, geopolitical 15%, concentration 15%. Missing
        or stale evidence produces an incomplete assessment.
      </p>
      <div className="ai3-grid">
        <Field label="Supplier">
          <Options
            rows={data.suppliers}
            value={supplier}
            onChange={setSupplier}
          />
        </Field>
        <Field label="Evidence validity (days)">
          <Input
            required
            type="number"
            min="1"
            max="365"
            value={valid}
            onChange={(e) => setValid(Number(e.target.value))}
          />
        </Field>
      </div>
      {rows.map((r, i) => (
        <fieldset className="ai3-card" key={r.factor}>
          <legend>{r.factor}</legend>
          <div className="ai3-grid">
            <Field label="Risk score — leave blank if unknown">
              <Input
                type="number"
                min="0"
                max="100"
                step="any"
                value={r.score ?? ''}
                onChange={(e) =>
                  change(
                    i,
                    'score',
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
              />
            </Field>
            <Field label="Evidence">
              <Options
                rows={sources}
                value={r.source_ids[0] || ''}
                onChange={(v) => change(i, 'source_ids', v ? [v] : [])}
                placeholder="No verified evidence"
              />
            </Field>
            <Field label="Evidence date">
              <Input
                required
                type="date"
                max={today()}
                value={r.as_of}
                onChange={(e) => change(i, 'as_of', e.target.value)}
              />
            </Field>
          </div>
          <Field label="Assessment rationale / missing information">
            <Textarea
              required
              minLength={10}
              value={r.rationale}
              onChange={(e) => change(i, 'rationale', e.target.value)}
            />
          </Field>
        </fieldset>
      ))}
      <Button className="primary-button" disabled={busy || !supplier}>
        Save risk assessment
      </Button>
    </form>
  );
}
function RecommendationForm({
  data,
  items,
  busy,
  onSave,
}: {
  data: Workspace;
  items: Row[];
  busy: boolean;
  onSave: (v: Row) => void;
}) {
  const [form, setForm] = useState<Row>({
    name: '',
    category_id: '',
    forecast_id: '',
    scenario_id: '',
    risk_ids: [],
    context: '',
  });
  const set = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  const eligible = items.filter((r) => r.category_id === form.category_id);
  return (
    <form
      className="panel detail-body"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(form);
      }}
    >
      <h2>Generate an evidence-based recommendation</h2>
      <p className="section-note">
        The rules produce procurement options with citations and gaps. A Buyer
        reviews the result before an enterprise review task can be prepared.
      </p>
      <div className="ai3-grid">
        <Field label="Recommendation title">
          <Input
            required
            minLength={3}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field label="Category">
          <Options
            rows={data.categories}
            value={form.category_id}
            onChange={(v) =>
              setForm({
                ...form,
                category_id: v,
                forecast_id: '',
                scenario_id: '',
                risk_ids: [],
              })
            }
          />
        </Field>
        <Field label="Price forecast (optional)">
          <Options
            rows={eligible.filter((r) => r.variant === 'forecast')}
            value={form.forecast_id}
            onChange={(v) => set('forecast_id', v)}
          />
        </Field>
        <Field label="Cost scenario (optional)">
          <Options
            rows={eligible.filter((r) => r.variant === 'scenario')}
            value={form.scenario_id}
            onChange={(v) => set('scenario_id', v)}
          />
        </Field>
      </div>
      <p className="section-note">Supplier risk assessments</p>
      {eligible
        .filter((r) => r.variant === 'supplier_risk')
        .map((r) => (
          <label className="check-label" key={r.id}>
            <input
              type="checkbox"
              checked={form.risk_ids.includes(r.id)}
              onChange={(e) =>
                set(
                  'risk_ids',
                  e.target.checked
                    ? [...form.risk_ids, r.id]
                    : form.risk_ids.filter((id: string) => id !== r.id),
                )
              }
            />
            {r.name} · {r.status}
          </label>
        ))}
      <Field label="Procurement context and constraints">
        <Textarea
          required
          minLength={10}
          value={form.context}
          onChange={(e) => set('context', e.target.value)}
        />
      </Field>
      <Button className="primary-button" disabled={busy || !form.category_id}>
        Generate recommendation
      </Button>
    </form>
  );
}

function AnalysisDetail({
  row,
  data,
  people,
  onChange,
  onBack,
  onRevise,
}: {
  row: Row;
  data: Workspace;
  people: Row[];
  onChange: (r: Row) => Promise<void>;
  onBack: () => void;
  onRevise: () => void;
}) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [rationale, setRationale] = useState('');
  const [sharing, setSharing] = useState<string[]>(row.shared_with || []);
  const result = row.result;
  async function mutate(path: string, body: Row, method?: string) {
    setBusy(true);
    setError('');
    try {
      await onChange(
        await api('/advanced/analyses/' + row.id + path, body, method),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const reviewable =
    row.variant === 'supplier_risk'
      ? data.user.permissions.includes('market:write')
      : data.user.permissions.includes('rfi:approve');
  return (
    <section className="panel detail-body">
      <Button variant="ghost" onClick={onBack}>
        <ArrowLeft size={16} />
        Analysis library
      </Button>
      <div className="mi-intro">
        <div>
          <p className="reference">
            {labels[row.variant]}{' '}
            {row.version ? '· version ' + row.version : ''}
          </p>
          <h2>{row.name}</h2>
          <Status>{row.status}</Status>
        </div>
        <JsonDownload value={row} name={'greta-' + row.variant} />
      </div>
      <ErrorBox error={error} />
      {row.assumptions && <p className="body-copy">{row.assumptions}</p>}
      {['cost_model', 'scenario'].includes(row.variant) && (
        <>
          <div className="mi-metrics">
            <div>
              <span>Should-cost / {row.output_unit}</span>
              <strong>
                {row.currency} {n(result.total)}
              </strong>
            </div>
            <div>
              <span>Component cost</span>
              <strong>{n(result.subtotal)}</strong>
            </div>
            <div>
              <span>Supplier margin</span>
              <strong>{n(result.supplier_margin)}</strong>
            </div>
            {row.variant === 'scenario' && (
              <div>
                <span>Change from baseline</span>
                <strong>{n(row.delta_pct)}%</strong>
              </div>
            )}
          </div>
          <div className="ai3-table">
            <table>
              <thead>
                <tr>
                  <th>Component</th>
                  <th>Driver</th>
                  <th>Converted cost</th>
                  <th>Input basis</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {result.components.map((c: Row, i: number) => (
                  <tr key={i}>
                    <td>{c.name}</td>
                    <td>{c.bucket.replaceAll('_', ' ')}</td>
                    <td>{n(c.cost)}</td>
                    <td>
                      {c.basis}
                      {!c.source_id ? ' · Assumption' : ''}
                    </td>
                    <td>{c.as_of}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {row.variant === 'scenario' && (
            <>
              <p className="body-copy">
                Budget for {n(row.volume)} {row.output_unit}: {row.currency}{' '}
                {n(row.total_budget)} · Baseline {n(row.baseline_budget)}
              </p>
              <h3>Sensitivity — one driver at a time</h3>
              <div className="ai3-table">
                <table>
                  <thead>
                    <tr>
                      <th>Driver</th>
                      <th>Cost at −10%</th>
                      <th>Cost at +10%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {row.sensitivity.map((s: Row) => (
                      <tr key={s.factor}>
                        <td>{s.factor.replaceAll('_', ' ')}</td>
                        <td>{n(s.minus_10)}</td>
                        <td>{n(s.plus_10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {row.variant === 'cost_model' && row.owner === data.user.id && (
            <Button variant="outline" onClick={onRevise}>
              Create revised model
            </Button>
          )}
        </>
      )}
      {row.variant === 'forecast' && (
        <>
          <p className="body-copy">
            Selected method: <strong>{result.model}</strong> ·{' '}
            {result.observations} observations · {row.currency}/{row.unit} ·{' '}
            {row.frequency}
          </p>
          {result.stale && (
            <ErrorBox error="The source is stale relative to the cutoff. Refresh observations before using this forecast." />
          )}
          {row.is_demo && (
            <ErrorBox error="This forecast uses illustrative data." />
          )}
          <div className="mi-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={[
                  ...result.history
                    .slice(-24)
                    .map((p: Row) => ({
                      date: p.date,
                      actual: p.value,
                      ...(p.date === result.training_end
                        ? { forecast: p.value }
                        : {}),
                    })),
                  ...result.forecast.map((p: Row) => ({
                    ...p,
                    forecast: p.value,
                  })),
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" minTickGap={45} />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Line
                  dataKey="actual"
                  name="Observed"
                  stroke="#286b51"
                  dot={false}
                />
                <Line
                  dataKey="forecast"
                  name="Forecast"
                  stroke="#bc753f"
                  dot={false}
                />
                <Line
                  dataKey="lower_95"
                  name="95% lower"
                  stroke="#acb8ad"
                  strokeDasharray="4 4"
                  dot={false}
                />
                <Line
                  dataKey="upper_95"
                  name="95% upper"
                  stroke="#7c9182"
                  strokeDasharray="4 4"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <h3>Rolling-origin model comparison</h3>
          <div className="ai3-table">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>Origins</th>
                </tr>
              </thead>
              <tbody>
                {result.backtest.map((r: Row) => (
                  <tr key={r.model}>
                    <td>{r.model}</td>
                    <td>{n(r.mae)}</td>
                    <td>{n(r.rmse)}</td>
                    <td>{r.origins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="section-note">{result.methodology}</p>
          <ul className="ai3-notes">
            {result.limitations.map((s: string) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <div className="ai3-table">
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Forecast</th>
                  <th>80% range</th>
                  <th>95% range</th>
                </tr>
              </thead>
              <tbody>
                {result.forecast.map((p: Row) => (
                  <tr key={p.date}>
                    <td>{p.date}</td>
                    <td>{n(p.value)}</td>
                    <td>
                      {n(p.lower_80)} – {n(p.upper_80)}
                    </td>
                    <td>
                      {n(p.lower_95)} – {n(p.upper_95)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {row.variant === 'supplier_risk' && (
        <>
          <div className="mi-metrics">
            <div>
              <span>Risk rating</span>
              <strong>{result.rating}</strong>
            </div>
            <div>
              <span>
                {result.coverage_pct < 100
                  ? 'Provisional score'
                  : 'Weighted score'}
              </span>
              <strong>{n(result.score)}/100</strong>
            </div>
            <div>
              <span>Evidence coverage</span>
              <strong>{result.coverage_pct}%</strong>
            </div>
            <div>
              <span>Evidence expires</span>
              <strong>{result.expires_on}</strong>
            </div>
          </div>
          <p className="section-note">{result.methodology}</p>
          {result.gaps.length > 0 && (
            <p className="body-copy">Evidence gaps: {result.gaps.join(', ')}</p>
          )}
          {row.factors.map((f: Row) => (
            <div className="ai3-card" key={f.factor}>
              <h3>
                {f.factor} · {n(f.score)}/100
              </h3>
              <p className="body-copy">{f.rationale}</p>
              <p className="section-note">
                Source date {f.as_of} · {f.source_ids.length} linked evidence
                item(s)
              </p>
            </div>
          ))}
        </>
      )}
      {row.variant === 'recommendation' && (
        <>
          <p className="body-copy">{row.context}</p>
          <p className="section-note">
            {result.engine} · {result.decision_scope}
          </p>
          {result.actions.map((a: Row, i: number) => (
            <div className="ai3-card" key={i}>
              <h3>{a.action}</h3>
              <p className="body-copy">{a.reason}</p>
              <p className="section-note">
                Evidence:{' '}
                {a.source_ids
                  .map(
                    (id: string) =>
                      row.sources.find((s: Row) => s.id === id)?.title || id,
                  )
                  .join(', ')}
              </p>
            </div>
          ))}
          {!result.actions.length && (
            <Empty
              title="More evidence is needed"
              text="Resolve the gaps below to generate procurement actions."
            />
          )}
          {result.gaps.map((g: string) => (
            <p className="body-copy" key={g}>
              • {g}
            </p>
          ))}
        </>
      )}
      <h3>Sources and traceability</h3>
      {row.sources.length ? (
        row.sources.map((s: Row) => (
          <p className="section-note" key={s.id}>
            {s.title} · {s.kind} · updated {s.updated_at.slice(0, 10)}{' '}
            {s.is_demo ? '· illustrative data' : ''}
          </p>
        ))
      ) : (
        <p className="section-note">
          No linked source. This model is based on user-entered assumptions.
        </p>
      )}
      {reviewable && (
        <form
          className="ai3-card"
          onSubmit={(e) => {
            e.preventDefault();
            void mutate('/review', { decision: 'APPROVED', rationale });
          }}
        >
          <h3>
            {row.variant === 'supplier_risk'
              ? 'Analyst review'
              : 'Buyer review'}
          </h3>
          <Field label="Review rationale">
            <Textarea
              required
              minLength={10}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
            />
          </Field>
          <div className="inline-fields">
            <Button disabled={busy} className="primary-button">
              Approve analysis
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy || rationale.length < 10}
              onClick={() =>
                mutate('/review', { decision: 'REJECTED', rationale })
              }
            >
              Reject analysis
            </Button>
          </div>
        </form>
      )}
      {row.review && (
        <p className="section-note">
          Last review: {row.review.decision} by {row.review.by} ·{' '}
          {row.review.rationale}
        </p>
      )}
      {row.owner === data.user.id && (
        <div className="ai3-card">
          <h3>Share with your team</h3>
          <p className="section-note">
            Recipients must already have access to every source, including
            upstream analyses.
          </p>
          {people
            .filter((p) => p.id !== data.user.id)
            .map((p) => (
              <label className="check-label" key={p.id}>
                <input
                  type="checkbox"
                  checked={sharing.includes(p.id)}
                  onChange={(e) =>
                    setSharing(
                      e.target.checked
                        ? [...sharing, p.id]
                        : sharing.filter((id) => id !== p.id),
                    )
                  }
                />
                {p.name} · {p.role}
              </label>
            ))}
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => mutate('/sharing', { user_ids: sharing }, 'PUT')}
          >
            Save sharing
          </Button>
        </div>
      )}
    </section>
  );
}
