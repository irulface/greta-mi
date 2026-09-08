'use client';
import { useEffect, useState } from 'react';
import {
  Bot,
  Play,
  Pause,
  RefreshCw,
  Plus,
  ArrowLeft,
  Square,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { api, Row, Workspace, Picker, Status, ErrorBox, Empty } from './shared';
import { Field, Options, JsonDownload } from './advanced-shared';

const domains = [
  'Demand',
  'Inventory',
  'PO',
  'RFI',
  'Market Data',
  'Supplier Data',
  'Price',
  'Market Events',
];
const metricNames: Row = {
  demand_quantity: 'Projected demand',
  inventory_coverage: 'Inventory coverage',
  po_open_value: 'Open PO value',
  po_overdue_count: 'Overdue PO count',
  supplier_lead_time: 'Supplier lead time',
};
const defaults = {
  demand_change_pct: 15,
  lead_time_change_pct: 20,
  price_change_pct: 10,
  po_change_pct: 15,
  inventory_critical_months: 3,
  inventory_watch_months: 6,
};
const policyLabels: Row = {
  demand_change_pct: 'Demand change (%)',
  lead_time_change_pct: 'Lead time change (%)',
  price_change_pct: 'Price change (%)',
  po_change_pct: 'Open PO value change (%)',
  inventory_critical_months: 'Critical inventory coverage (months)',
  inventory_watch_months: 'Watch inventory coverage (months)',
};
const display = (value: unknown) =>
  typeof value === 'number'
    ? value.toLocaleString('en-GB', { maximumFractionDigits: 3 })
    : typeof value === 'string'
      ? value
      : JSON.stringify(value ?? '—');
const when = (v?: string) => (v ? new Date(v).toLocaleString('en-GB') : '—');
const getWorkspace = () =>
  Promise.all([
    api('/agents'),
    api('/agents/signals'),
    api('/agents/inbox/alerts'),
    api('/market/shareable-users'),
  ]);

export function AutonomousIntelligence({
  data,
  initialAgent = '',
  onNotifications,
}: {
  data: Workspace;
  initialAgent?: string;
  onNotifications: () => Promise<void>;
}) {
  const [agents, setAgents] = useState<Row[]>([]);
  const [signals, setSignals] = useState<Row[]>([]);
  const [alerts, setAlerts] = useState<Row[]>([]);
  const [people, setPeople] = useState<Row[]>([]);
  const [tab, setTab] = useState('agents');
  const [selected, setSelected] = useState(initialAgent);
  const [editing, setEditing] = useState<Row | null>(null);
  const [creating, setCreating] = useState(false);
  const [runs, setRuns] = useState<Row[]>([]);
  const [run, setRun] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const agent = agents.find((a) => a.id === selected);
  async function refresh() {
    const [a, s, i, p] = await getWorkspace();
    setAgents(a);
    setSignals(s);
    setAlerts(i);
    setPeople(
      p.filter((u: Row) =>
        ['Buyer', 'Market Intelligence Analyst'].includes(u.role),
      ),
    );
  }
  useEffect(() => {
    let cancelled = false;
    getWorkspace()
      .then(([a, s, i, p]) => {
        if (cancelled) return;
        setAgents(a);
        setSignals(s);
        setAlerts(i);
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
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    api('/agents/' + selected + '/runs')
      .then((r) => {
        if (!cancelled) setRuns(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);
  useEffect(() => {
    let cancelled = false;
    let loading = false;
    const timer = setInterval(async () => {
      if (cancelled || loading || document.hidden) return;
      loading = true;
      await Promise.all([
        getWorkspace()
          .then(([a, s, i]) => {
            if (cancelled) return;
            setAgents(a);
            setSignals(s);
            setAlerts(i);
          })
          .catch((e) => {
            if (!cancelled) setError(e.message);
          }),
        selected
          ? api('/agents/' + selected + '/runs')
              .then((r) => {
                if (!cancelled) setRuns(r);
              })
              .catch((e) => {
                if (!cancelled) setError(e.message);
              })
          : Promise.resolve(),
      ]);
      loading = false;
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [selected]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      await refresh();
      await onNotifications();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const showRun = (agentId: string, runId: string) =>
    act(async () => {
      setSelected(agentId);
      setTab('agents');
      setRun(await api('/agents/' + agentId + '/runs/' + runId));
    });
  return (
    <div className="ai3 market-intelligence">
      <ErrorBox error={error} />
      {notice && <output className="success-box">{notice}</output>}
      <div className="mi-intro">
        <p className="section-note">
          Watch eight evidence domains, see what changed, and follow each alert
          back to its inputs.
        </p>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => act(async () => {})}
        >
          <RefreshCw size={16} />
          Refresh
        </Button>
      </div>
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList className="workspace-tabs">
          <TabsTrigger value="agents">Agent workspace</TabsTrigger>
          <TabsTrigger value="inbox">
            Intelligence alerts (
            {alerts.filter((a) => a.status === 'OPEN').length})
          </TabsTrigger>
          <TabsTrigger value="signals">Operational evidence</TabsTrigger>
        </TabsList>
        <TabsContent value="agents">
          {creating || editing ? (
            <AgentForm
              key={editing?.id || 'new'}
              data={data}
              signals={signals}
              initial={editing}
              busy={busy}
              onCancel={() => {
                setCreating(false);
                setEditing(null);
              }}
              onSave={(body) =>
                act(async () => {
                  const result = await api(
                    '/agents' + (editing ? '/' + editing.id : ''),
                    body,
                    editing ? 'PUT' : 'POST',
                  );
                  setSelected(result.id);
                  setCreating(false);
                  setEditing(null);
                  setRun(null);
                  setNotice(
                    'Agent configuration saved. A new baseline will be recorded.',
                  );
                })
              }
            />
          ) : (
            <>
              <div className="mi-intro">
                <h2>Your intelligence agents</h2>
                <Button
                  className="primary-button"
                  onClick={() => setCreating(true)}
                >
                  <Plus size={16} />
                  New agent
                </Button>
              </div>
              {!agents.length ? (
                <Empty
                  title="Create your first category monitor"
                  text="Choose a category and any operational evidence. The first run records a baseline; later runs identify changes."
                />
              ) : (
                <div className="mi-card-grid">
                  {agents.map((a) => (
                    <button
                      key={a.id}
                      className={
                        'mi-reference-card agent-card ' +
                        (a.id === selected ? 'selected' : '')
                      }
                      onClick={() => {
                        setSelected(a.id);
                        setRun(null);
                      }}
                    >
                      <Bot size={22} />
                      <strong>{a.name}</strong>
                      <span>
                        {
                          data.categories.find((c) => c.id === a.category_id)
                            ?.name
                        }{' '}
                        ·{' '}
                        {a.enabled
                          ? 'Every ' + a.interval_minutes + ' min'
                          : 'Paused'}
                      </span>
                      <Status>{a.latest_run?.status || 'No runs yet'}</Status>
                      <span>
                        {a.latest_run?.result
                          ? 'Risk ' +
                            a.latest_run.result.risk.level +
                            ' · ' +
                            a.latest_run.result.risk.covered_domains +
                            '/8 domains available'
                          : 'Baseline pending'}
                      </span>
                      {!a.system_enabled && (
                        <span>Region execution stopped by Admin</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {agent && (
                <section className="panel detail-body">
                  <div className="mi-intro">
                    <div>
                      <h2>{agent.name}</h2>
                      <p className="section-note">
                        Next scheduled run:{' '}
                        {agent.enabled ? when(agent.next_run) : 'Paused'} ·
                        Configuration {agent.version}{' '}
                        {agent.include_demo ? '· Illustrative mode' : ''}
                      </p>
                    </div>
                    <Status>{agent.latest_run?.status || 'READY'}</Status>
                  </div>
                  <div className="agent-coverage">
                    {domains.map((d) => {
                      const c = agent.latest_run?.result?.coverage?.[d];
                      return (
                        <div
                          key={d}
                          className={
                            'coverage-' + (c?.state || 'MISSING').toLowerCase()
                          }
                        >
                          <strong>{d}</strong>
                          <span>{c?.state || 'Not evaluated'}</span>
                          <small>
                            {c
                              ? c.fresh + ' / ' + c.count + ' current sources'
                              : '—'}
                          </small>
                        </div>
                      );
                    })}
                  </div>
                  {agent.can_manage && (
                    <div className="inline-fields">
                      <Button
                        className="primary-button"
                        disabled={busy || !agent.system_enabled}
                        onClick={() =>
                          act(async () => {
                            const r = await api(
                              '/agents/' + agent.id + '/run',
                              {},
                            );
                            setNotice(
                              'Run ' +
                                r.status.toLowerCase() +
                                '. Progress appears in the history below.',
                            );
                          })
                        }
                      >
                        <Play size={16} />
                        Run once
                      </Button>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            await api('/agents/' + agent.id + '/toggle', {
                              enabled: !agent.enabled,
                            });
                          })
                        }
                      >
                        {agent.enabled ? (
                          <Pause size={16} />
                        ) : (
                          <Play size={16} />
                        )}{' '}
                        {agent.enabled ? 'Pause schedule' : 'Enable schedule'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setEditing(agent)}
                      >
                        Edit policy & sources
                      </Button>
                    </div>
                  )}
                  <p className="section-note">
                    First runs establish a baseline. PARTIAL means one or more
                    domains are missing or degraded. The agent publishes alerts
                    in this app; procurement actions remain under Buyer control.
                  </p>
                  <h3>Execution history</h3>
                  <div className="ai3-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Started</th>
                          <th>Trigger</th>
                          <th>Status</th>
                          <th>Changes</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs
                          .filter((r) => r.agent_id === selected)
                          .map((r) => (
                            <tr key={r.id}>
                              <td>{when(r.started_at || r.created_at)}</td>
                              <td>{r.trigger}</td>
                              <td>
                                <Status>{r.status}</Status>
                              </td>
                              <td>{r.result?.material_changes ?? '—'}</td>
                              <td>
                                <div className="inline-fields">
                                  <Button
                                    variant="ghost"
                                    onClick={() => showRun(agent.id, r.id)}
                                  >
                                    View evidence
                                  </Button>
                                  {agent.can_manage &&
                                    ['PENDING', 'RUNNING'].includes(
                                      r.status,
                                    ) && (
                                      <Button
                                        variant="outline"
                                        disabled={busy}
                                        onClick={() =>
                                          act(async () => {
                                            await api(
                                              '/agents/' +
                                                agent.id +
                                                '/runs/' +
                                                r.id +
                                                '/cancel',
                                              {},
                                            );
                                          })
                                        }
                                      >
                                        <Square size={14} />
                                        Cancel
                                      </Button>
                                    )}
                                </div>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {agent.can_manage && (
                    <div className="ai3-card">
                      <h3>Alert recipients and read access</h3>
                      <p className="section-note">
                        Your account receives alerts. Selected colleagues can
                        read runs and resolve alerts when they have access to
                        all supporting evidence.
                      </p>
                      {people.map((p) => (
                        <label className="check-label" key={p.id}>
                          <input
                            type="checkbox"
                            disabled={busy}
                            checked={agent.shared_with.includes(p.id)}
                            onChange={(e) =>
                              act(async () => {
                                const ids = e.target.checked
                                  ? [...agent.shared_with, p.id]
                                  : agent.shared_with.filter(
                                      (id: string) => id !== p.id,
                                    );
                                await api(
                                  '/agents/' + agent.id + '/sharing',
                                  { user_ids: ids },
                                  'PUT',
                                );
                              })
                            }
                          />
                          {p.name} · {p.role}
                        </label>
                      ))}
                    </div>
                  )}
                </section>
              )}
              {run && (
                <RunEvidence
                  run={run}
                  onClose={() => setRun(null)}
                  onRefresh={() => showRun(run.agent_id, run.id)}
                />
              )}
            </>
          )}
        </TabsContent>
        <TabsContent value="inbox">
          <AlertInbox
            alerts={alerts}
            busy={busy}
            onRun={showRun}
            onUpdate={(id, body) =>
              act(async () => {
                await api('/agents/inbox/alerts/' + id, body, 'PUT');
              })
            }
          />
        </TabsContent>
        <TabsContent value="signals">
          <OperationalSignals
            data={data}
            signals={signals}
            busy={busy}
            act={act}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AgentForm({
  data,
  signals,
  initial,
  busy,
  onSave,
  onCancel,
}: {
  data: Workspace;
  signals: Row[];
  initial: Row | null;
  busy: boolean;
  onSave: (body: Row) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<Row>({
    name: initial?.name || '',
    category_id: initial?.category_id || '',
    signal_ids: initial?.signal_ids || [],
    interval_minutes: initial?.interval_minutes || 1440,
    max_source_age_days: initial?.max_source_age_days || 90,
    min_confidence: initial?.min_confidence ?? 0.5,
    runtime_seconds: initial?.runtime_seconds || 150,
    use_mcp: initial?.use_mcp || false,
    include_demo: initial?.include_demo || false,
    enabled: initial?.enabled || false,
    policy: initial?.policy || defaults,
    version: initial?.version || 1,
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
      <Button type="button" variant="ghost" onClick={onCancel}>
        <ArrowLeft size={16} />
        Back
      </Button>
      <h2>{initial ? 'Edit category agent' : 'Create a category agent'}</h2>
      <p className="section-note">
        RFI, supplier profiles, market sources, prices and events are read from
        the selected category. Choose operational inputs below for demand,
        inventory, PO and lead time.
      </p>
      <div className="ai3-grid">
        <Field label="Agent name">
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
              setForm({ ...form, category_id: v, signal_ids: [] })
            }
          />
        </Field>
        <Field label="Evaluation interval (minutes)">
          <Input
            required
            type="number"
            min="15"
            max="10080"
            value={form.interval_minutes}
            onChange={(e) => set('interval_minutes', Number(e.target.value))}
          />
        </Field>
        <Field label="Maximum observation age (days)">
          <Input
            required
            type="number"
            min="1"
            max="730"
            value={form.max_source_age_days}
            onChange={(e) => set('max_source_age_days', Number(e.target.value))}
          />
        </Field>
        <Field label="Minimum source confidence (0–1)">
          <Input
            required
            type="number"
            min="0"
            max="1"
            step=".01"
            value={form.min_confidence}
            onChange={(e) => set('min_confidence', Number(e.target.value))}
          />
        </Field>
        <Field label="Maximum runtime per run (seconds)">
          <Input
            required
            type="number"
            min="15"
            max="300"
            value={form.runtime_seconds}
            onChange={(e) => set('runtime_seconds', Number(e.target.value))}
          />
        </Field>
      </div>
      <h3>Operational inputs</h3>
      {signals
        .filter((s) => s.category_id === form.category_id)
        .map((s) => (
          <label className="check-label" key={s.id}>
            <input
              type="checkbox"
              checked={form.signal_ids.includes(s.id)}
              onChange={(e) =>
                set(
                  'signal_ids',
                  e.target.checked
                    ? [...form.signal_ids, s.id]
                    : form.signal_ids.filter((id: string) => id !== s.id),
                )
              }
            />
            {s.name} · {metricNames[s.metric]} · {s.scope}
          </label>
        ))}
      {!signals.some((s) => s.category_id === form.category_id) && (
        <p className="section-note">
          No operational series in this category yet. Add them in Operational
          evidence, or connect internal MCP.
        </p>
      )}
      <label className="check-label">
        <input
          type="checkbox"
          checked={form.use_mcp}
          onChange={(e) => set('use_mcp', e.target.checked)}
        />
        Read demand, inventory, open PO and lead-time evidence from the
        configured internal MCP gateway.
      </label>
      <label className="check-label">
        <input
          type="checkbox"
          checked={form.include_demo}
          onChange={(e) => set('include_demo', e.target.checked)}
        />
        Include illustrative records (alerts will be labeled illustrative).
      </label>
      <h3>Change thresholds and risk policy</h3>
      <div className="ai3-grid">
        {Object.keys(defaults).map((k) => (
          <Field label={policyLabels[k]} key={k}>
            <Input
              required
              type="number"
              min="0.01"
              step="any"
              value={form.policy[k]}
              onChange={(e) =>
                set('policy', { ...form.policy, [k]: Number(e.target.value) })
              }
            />
          </Field>
        ))}
      </div>
      <p className="section-note">
        Critical inventory coverage indicates HIGH observed risk. Three distinct
        elevated indicators also indicate HIGH. Otherwise elevated indicators
        indicate MEDIUM. LOW requires current demand, inventory and lead-time
        evidence. Missing data is never assumed to be low risk.
      </p>
      <label className="check-label">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => set('enabled', e.target.checked)}
        />
        Enable periodic evaluation after saving.
      </label>
      {initial && (
        <p className="section-note">
          Changing this configuration cancels active work and resets the
          comparison baseline. Existing evidence reports stay in history.
        </p>
      )}
      <Button disabled={busy || !form.category_id} className="primary-button">
        Save agent
      </Button>
    </form>
  );
}

function RunEvidence({
  run,
  onClose,
  onRefresh,
}: {
  run: Row;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const result = run.result;
  const snapshot = run.snapshot;
  return (
    <section className="panel detail-body">
      <div className="mi-intro">
        <div>
          <h2>What changed?</h2>
          <p className="section-note">
            {when(run.started_at)} · {run.trigger} · configuration {run.version}
          </p>
        </div>
        <div className="inline-fields">
          <Button variant="outline" onClick={onRefresh}>
            <RefreshCw size={15} />
            Refresh run
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Close report
          </Button>
        </div>
      </div>
      <Status>{run.status}</Status>
      <ErrorBox error={run.error || ''} />
      {result?.risk && (
        <>
          <div className="mi-metrics">
            <div>
              <span>Observed procurement risk</span>
              <strong>
                {result.previous_risk ? result.previous_risk + ' → ' : ''}
                {result.risk.level}
              </strong>
            </div>
            <div>
              <span>Domains available</span>
              <strong>{result.risk.covered_domains} / 8</strong>
            </div>
            <div>
              <span>Material changes</span>
              <strong>{result.material_changes}</strong>
            </div>
            <div>
              <span>Risk evidence</span>
              <strong>
                {result.risk.complete ? 'Core metrics available' : 'Incomplete'}
              </strong>
            </div>
          </div>
          {result.is_demo && (
            <p className="section-note">
              Illustrative mode. Demo evidence is excluded from the live risk
              calculation.
            </p>
          )}
          <p className="body-copy agent-summary">{result.summary}</p>
          <p className="section-note">{result.risk.basis}</p>
          {result.risk.signals.map((s: Row) => (
            <div className="ai3-card" key={s.key}>
              <Status>{s.level}</Status>
              <p className="body-copy">{s.reason}</p>
              <p className="section-note">
                {s.source.name} · observation {s.as_of}
              </p>
            </div>
          ))}
          <h3>Change evidence</h3>
          {result.changes.length ? (
            result.changes.map((c: Row, i: number) => (
              <details key={c.key + ':' + i} className="ai3-card">
                <summary>
                  {c.label} · {c.type.replaceAll('_', ' ')} ·{' '}
                  {c.material ? 'Material' : 'Below threshold'}
                </summary>
                <div className="ai3-grid">
                  <div>
                    <h3>Before</h3>
                    <pre className="ai3-pre">{display(c.before)}</pre>
                    <p className="section-note">{c.before_as_of || ''}</p>
                  </div>
                  <div>
                    <h3>After</h3>
                    <pre className="ai3-pre">{display(c.after)}</pre>
                    <p className="section-note">{c.as_of || ''}</p>
                  </div>
                </div>
                {c.pct !== undefined && (
                  <p className="body-copy">
                    Change:{' '}
                    {c.pct === null
                      ? 'Unavailable (zero baseline)'
                      : display(c.pct) + '%'}{' '}
                    · {c.currency} {c.unit}
                  </p>
                )}
                {c.corrected && (
                  <p className="section-note">
                    This is a correction to the same observation date, not a new
                    reporting period.
                  </p>
                )}
                <p className="section-note">{c.source?.name || c.domain}</p>
              </details>
            ))
          ) : (
            <p className="section-note">
              {result.initial_baseline
                ? 'Baseline captured. Subsequent runs will show changes here.'
                : 'No changed evidence.'}
            </p>
          )}
        </>
      )}
      {snapshot?.coverage && (
        <>
          <h3>Evidence coverage and gaps</h3>
          <div className="agent-coverage">
            {domains.map((d) => (
              <div
                key={d}
                className={
                  'coverage-' + snapshot.coverage[d].state.toLowerCase()
                }
              >
                <strong>{d}</strong>
                <span>{snapshot.coverage[d].state}</span>
                <small>
                  {snapshot.coverage[d].fresh}/{snapshot.coverage[d].count}{' '}
                  current
                </small>
              </div>
            ))}
          </div>
          {snapshot.issues.map((issue: Row, i: number) => (
            <p className="section-note" key={i}>
              {issue.domain}: {issue.message}
            </p>
          ))}
          <h3>Observed metrics</h3>
          <div className="ai3-table">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Scope</th>
                  <th>As of</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.metrics.map((m: Row) => (
                  <tr key={m.key}>
                    <td>{m.label}</td>
                    <td>
                      {display(m.value)} {m.currency} {m.unit}
                    </td>
                    <td>
                      {m.scope}
                      {m.metric === 'demand_quantity'
                        ? ' / ' + m.horizon_days + ' days'
                        : ''}
                    </td>
                    <td>
                      {m.as_of}
                      {m.stale ? ' · stale' : ''}
                      {m.low_confidence ? ' · low confidence' : ''}
                    </td>
                    <td>
                      {m.source.name}
                      <br />
                      {m.publication}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="ai3-card">
            <summary>Tracked records ({snapshot.entities.length})</summary>
            {snapshot.entities.map((r: Row) => (
              <p className="section-note" key={r.key}>
                {r.domain} · {r.label} · {when(r.as_of)}
              </p>
            ))}
          </details>
        </>
      )}
      {run.steps && (
        <>
          <h3>Execution steps</h3>
          <ol className="agent-steps">
            {run.steps.map((step: Row, i: number) => (
              <li key={i}>
                <strong>{step.step.replaceAll('_', ' ')}</strong>
                <span>{step.detail}</span>
                <small>{when(step.at)}</small>
              </li>
            ))}
          </ol>
        </>
      )}
      {run.evidence_available && (
        <JsonDownload value={run} name="greta-agent-evidence" />
      )}
    </section>
  );
}
function AlertInbox({
  alerts,
  busy,
  onRun,
  onUpdate,
}: {
  alerts: Row[];
  busy: boolean;
  onRun: (a: string, r: string) => void;
  onUpdate: (id: string, body: Row) => void;
}) {
  const [filter, setFilter] = useState('OPEN');
  const [notes, setNotes] = useState<Row>({});
  const visible = alerts.filter((a) => filter === 'ALL' || a.status === filter);
  return (
    <section className="panel detail-body">
      <div className="mi-intro">
        <h2>Intelligence alerts</h2>
        <Picker
          value={filter}
          onChange={setFilter}
          options={['OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'ALL']}
        />
      </div>
      {!visible.length && (
        <Empty
          title="No alerts in this view"
          text="Alerts appear after a baseline when source changes pass the configured thresholds or coverage changes."
        />
      )}
      {visible.map((a) => (
        <article key={a.id} className="ai3-card">
          <div className="mi-intro">
            <h3>{a.title}</h3>
            <Status>{a.severity}</Status>
          </div>
          <p className="body-copy agent-summary">{a.message}</p>
          <p className="section-note">
            {when(a.detected_at)} · {a.status}{' '}
            {a.is_demo ? '· Illustrative mode' : ''}
          </p>
          <Button variant="outline" onClick={() => onRun(a.agent_id, a.run_id)}>
            Inspect source evidence
          </Button>
          {a.status !== 'RESOLVED' && (
            <>
              <Field label="Review note">
                <Textarea
                  minLength={3}
                  value={notes[a.id] || ''}
                  onChange={(e) =>
                    setNotes({ ...notes, [a.id]: e.target.value })
                  }
                />
              </Field>
              <div className="inline-fields">
                <Button
                  variant="outline"
                  disabled={busy || (notes[a.id] || '').length < 3}
                  onClick={() =>
                    onUpdate(a.id, {
                      status: 'ACKNOWLEDGED',
                      note: notes[a.id],
                    })
                  }
                >
                  Acknowledge
                </Button>
                <Button
                  className="primary-button"
                  disabled={busy || (notes[a.id] || '').length < 3}
                  onClick={() =>
                    onUpdate(a.id, { status: 'RESOLVED', note: notes[a.id] })
                  }
                >
                  Resolve
                </Button>
              </div>
            </>
          )}
          {a.history.length > 0 && (
            <details>
              <summary>Review history</summary>
              {a.history.map((h: Row, i: number) => (
                <p className="section-note" key={i}>
                  {h.status} · {h.note} · {h.by} · {when(h.at)}
                </p>
              ))}
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
function OperationalSignals({
  data,
  signals,
  busy,
  act,
}: {
  data: Workspace;
  signals: Row[];
  busy: boolean;
  act: (fn: () => Promise<void>) => void;
}) {
  const [form, setForm] = useState<Row>({
    name: '',
    category_id: '',
    metric: 'demand_quantity',
    unit: 'MT',
    currency: '',
    scope: '',
    horizon_days: 30,
    source: '',
    notes: '',
  });
  const [selected, setSelected] = useState('');
  const [creating, setCreating] = useState(false);
  const [observation, setObservation] = useState<Row>({
    date: new Date().toISOString().slice(0, 10),
    value: '',
    confidence: 1,
    source: '',
    notes: '',
  });
  const [replace, setReplace] = useState(false);
  const signal = signals.find((s) => s.id === selected);
  const set = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  return (
    <>
      <section className="panel detail-body">
        <div className="mi-intro">
          <div>
            <h2>Operational evidence</h2>
            <p className="section-note">
              Use sourced observations when an enterprise connection is not
              available. Units, planning horizon and scope stay fixed so runs
              compare like-for-like values.
            </p>
          </div>
          <Button onClick={() => setCreating(!creating)} variant="outline">
            <Plus size={16} />
            {creating ? 'Close form' : 'New signal'}
          </Button>
        </div>
        {creating && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const r = await api('/agents/signals', form);
                setSelected(r.id);
                setCreating(false);
              });
            }}
          >
            <div className="ai3-grid">
              <Field label="Series name">
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
              <Field label="Metric">
                <Picker
                  value={form.metric}
                  onChange={(v) =>
                    setForm({
                      ...form,
                      metric: v,
                      unit:
                        (
                          {
                            inventory_coverage: 'months',
                            po_overdue_count: 'orders',
                            supplier_lead_time: 'weeks',
                            po_open_value: 'currency',
                          } as Row
                        )[v] || 'MT',
                      currency: v === 'po_open_value' ? 'USD' : '',
                    })
                  }
                  options={Object.entries(metricNames).map(
                    ([value, label]) => ({ value, label: String(label) }),
                  )}
                />
              </Field>
              <Field label="Unit">
                <Input
                  required
                  readOnly={form.metric !== 'demand_quantity'}
                  value={form.unit}
                  onChange={(e) => set('unit', e.target.value)}
                />
              </Field>
              {form.metric === 'po_open_value' && (
                <Field label="Currency (ISO)">
                  <Input
                    required
                    pattern="[A-Z]{3}"
                    value={form.currency}
                    onChange={(e) =>
                      set('currency', e.target.value.toUpperCase())
                    }
                  />
                </Field>
              )}
              <Field label="Scope (material, supplier or location)">
                <Input
                  required
                  minLength={2}
                  value={form.scope}
                  onChange={(e) => set('scope', e.target.value)}
                />
              </Field>
              {form.metric === 'demand_quantity' && (
                <Field label="Demand planning horizon (days)">
                  <Input
                    required
                    type="number"
                    min="1"
                    max="730"
                    value={form.horizon_days}
                    onChange={(e) =>
                      set('horizon_days', Number(e.target.value))
                    }
                  />
                </Field>
              )}
              <Field label="Source and accountable owner">
                <Input
                  required
                  minLength={5}
                  value={form.source}
                  onChange={(e) => set('source', e.target.value)}
                />
              </Field>
            </div>
            <Field label="Basis and notes">
              <Textarea
                value={form.notes}
                onChange={(e) => set('notes', e.target.value)}
              />
            </Field>
            <Button
              className="primary-button"
              disabled={busy || !form.category_id}
            >
              Create evidence series
            </Button>
          </form>
        )}
        <Field label="Select operational evidence">
          <Options rows={signals} value={selected} onChange={setSelected} />
        </Field>
        {signal && (
          <>
            <h3>{signal.name}</h3>
            <p className="section-note">
              {metricNames[signal.metric]} · {signal.scope} · {signal.unit}{' '}
              {signal.currency} · Source: {signal.source}
            </p>
            <p className="section-note">{signal.notes}</p>
            {(signal.owner === data.user.id ||
              data.user.role === 'Market Intelligence Analyst') && (
              <>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(async () => {
                      await api(
                        '/agents/signals/' + signal.id + '/observations',
                        {
                          observations: [
                            {
                              ...observation,
                              value: Number(observation.value),
                            },
                          ],
                          replace_existing: replace,
                        },
                      );
                      setObservation({ ...observation, value: '' });
                    });
                  }}
                >
                  <div className="ai3-grid">
                    <Field label="Observation date">
                      <Input
                        required
                        type="date"
                        max={new Date().toISOString().slice(0, 10)}
                        value={observation.date}
                        onChange={(e) =>
                          setObservation({
                            ...observation,
                            date: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label="Value">
                      <Input
                        required
                        type="number"
                        min="0"
                        step={
                          signal.metric === 'po_overdue_count' ? '1' : 'any'
                        }
                        value={observation.value}
                        onChange={(e) =>
                          setObservation({
                            ...observation,
                            value: e.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field label="Source confidence (0–1)">
                      <Input
                        required
                        type="number"
                        min="0"
                        max="1"
                        step=".01"
                        value={observation.confidence}
                        onChange={(e) =>
                          setObservation({
                            ...observation,
                            confidence: Number(e.target.value),
                          })
                        }
                      />
                    </Field>
                    <Field label="Observation source — blank uses series source">
                      <Input
                        value={observation.source}
                        onChange={(e) =>
                          setObservation({
                            ...observation,
                            source: e.target.value,
                          })
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Observation notes">
                    <Input
                      value={observation.notes}
                      onChange={(e) =>
                        setObservation({
                          ...observation,
                          notes: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={replace}
                      onChange={(e) => setReplace(e.target.checked)}
                    />
                    Replace a conflicting value on the same date; the correction
                    will be audited.
                  </label>
                  <Button className="primary-button" disabled={busy}>
                    Save observation
                  </Button>
                </form>
                <Field label="Import CSV/XLSX (date,value,confidence,source,notes)">
                  <Input
                    type="file"
                    accept=".csv,.xlsx"
                    disabled={busy}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const payload = new FormData();
                      payload.set('file', file);
                      act(async () => {
                        await api(
                          '/agents/signals/' + signal.id + '/import',
                          payload,
                        );
                      });
                      e.target.value = '';
                    }}
                  />
                </Field>
                <p className="section-note">
                  Maximum 5 MB / 10,000 rows. Imports reject conflicting values
                  and spreadsheet formulas.
                </p>
              </>
            )}
            <div className="ai3-table">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Value</th>
                    <th>Confidence</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {signal.observations
                    .slice()
                    .reverse()
                    .map((p: Row) => (
                      <tr key={p.date}>
                        <td>{p.date}</td>
                        <td>
                          {display(p.value)} {signal.unit}
                        </td>
                        <td>{p.confidence}</td>
                        <td>{p.source}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <p className="section-note">Showing the latest 100 observations.</p>
          </>
        )}
      </section>
    </>
  );
}
export function AgentControls() {
  const [state, setState] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api('/agents/control/status')
      .then(setState)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <section className="panel detail-body ai3">
      <h2>Autonomous agent controls</h2>
      <ErrorBox error={error} />
      {state && (
        <>
          <p className="body-copy">
            {state.region}: {state.agents} agents · {state.active_runs} active
            runs
          </p>
          <Status>
            {state.enabled ? 'Execution allowed' : 'Execution stopped'}
          </Status>
          <p className="section-note">
            Stopping execution cancels queued and running work in your region.
            Results from cancelled runs cannot publish. In-flight reads may take
            until the next checkpoint to stop.
          </p>
          <Button
            variant={state.enabled ? 'outline' : 'default'}
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                setState(
                  await api(
                    '/agents/control/status',
                    { enabled: !state.enabled },
                    'PUT',
                  ),
                );
                setError('');
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {state.enabled
              ? 'Stop agent execution in this region'
              : 'Allow agent execution'}
          </Button>
          <p className="section-note">
            This control does not grant Admin access to procurement evidence or
            approval actions. Agent owners manage their schedules in Autonomous
            Agent.
          </p>
        </>
      )}
    </section>
  );
}
