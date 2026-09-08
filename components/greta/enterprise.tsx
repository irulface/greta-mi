'use client';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, Row, Workspace, Picker, Status, ErrorBox, Empty } from './shared';
import { Field, Options, JsonDownload } from './advanced-shared';

export function EnterprisePanel({
  data,
  analyses = [],
  onEvidence,
}: {
  data: Workspace;
  analyses?: Row[];
  onEvidence?: () => Promise<void>;
}) {
  const admin = data.user.role === 'Admin';
  const buyer = data.user.permissions.includes('rfi:approve');
  const [connectors, setConnectors] = useState<Row[]>([]);
  const [packages, setPackages] = useState<Row[]>([]);
  const [evidence, setEvidence] = useState<Row[]>([]);
  const [people, setPeople] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState('');
  const [form, setForm] = useState<Row>({
    name: '',
    kind: 'external_mcp',
    endpoint: '',
    secret: '',
    clear_secret: false,
    enabled: false,
  });
  const [tools, setTools] = useState('[]');
  const [connector, setConnector] = useState('');
  const [tool, setTool] = useState('');
  const [parameters, setParameters] = useState<Row>({});
  const [category, setCategory] = useState('');
  const [purpose, setPurpose] = useState('');
  const [rec, setRec] = useState('');
  const [destination, setDestination] = useState('');
  const [title, setTitle] = useState('');
  const [justification, setJustification] = useState('');
  const [selected, setSelected] = useState<Row | null>(null);
  const [rationale, setRationale] = useState('');
  const [consent, setConsent] = useState(false);
  const [accepted, setAccepted] = useState('yes');
  const [receipt, setReceipt] = useState('');
  async function refresh() {
    setConnectors(await api('/enterprise/connectors'));
    if (!admin) {
      setPackages(await api('/enterprise/packages'));
      setEvidence(await api('/enterprise/evidence'));
      setPeople(
        (await api('/market/shareable-users')).filter((u: Row) =>
          ['Buyer', 'Market Intelligence Analyst'].includes(u.role),
        ),
      );
    }
  }
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api('/enterprise/connectors'),
      ...(admin
        ? []
        : [
            api('/enterprise/packages'),
            api('/enterprise/evidence'),
            api('/market/shareable-users'),
          ]),
    ])
      .then(([c, p, e, u]) => {
        if (cancelled) return;
        setConnectors(c);
        if (!admin) {
          setPackages(p);
          setEvidence(e);
          setPeople(
            u.filter((r: Row) =>
              ['Buyer', 'Market Intelligence Analyst'].includes(r.role),
            ),
          );
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [admin, data.user.id]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const active = connectors.find((c) => c.id === connector);
  const policy = active?.tools.find((t: Row) => t.name === tool);
  return (
    <div className="ai3">
      <ErrorBox error={error} />
      {notice && <output className="success-box">{notice}</output>}
      {admin && (
        <form
          className="panel detail-body"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              const parsed = JSON.parse(tools);
              await api(
                '/enterprise/connectors' + (editing ? '/' + editing : ''),
                { ...form, tools: parsed },
                editing ? 'PUT' : 'POST',
              );
              setNotice('Connector saved.');
              setForm({ ...form, secret: '' });
            });
          }}
        >
          <h2>
            {editing ? 'Edit connector' : 'Configure an external connector'}
          </h2>
          <p className="section-note">
            Endpoints must be approved in ENTERPRISE_ALLOWED_HOSTS on the
            server. Workflow connectors receive procurement review tasks.
            External MCP tools require an explicit read-only allowlist.
          </p>
          <div className="ai3-grid">
            <Field label="Name">
              <Input
                required
                minLength={3}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Integration type">
              <Picker
                value={form.kind}
                onChange={(v) => setForm({ ...form, kind: v })}
                options={[
                  {
                    value: 'external_mcp',
                    label: 'External MCP (read-only evidence)',
                  },
                  {
                    value: 'workflow',
                    label: 'Enterprise workflow (review task)',
                  },
                ]}
              />
            </Field>
            <Field label="HTTPS endpoint">
              <Input
                required
                type="url"
                value={form.endpoint}
                onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
              />
            </Field>
            <Field label="Bearer token — blank keeps saved token">
              <Input
                type="password"
                autoComplete="new-password"
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
              />
            </Field>
          </div>
          <label className="check-label">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enable connector
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={form.clear_secret}
              onChange={(e) =>
                setForm({ ...form, clear_secret: e.target.checked })
              }
            />
            Remove saved token
          </label>
          {form.kind === 'external_mcp' && (
            <Field label="Approved read-only tools (JSON)">
              <Textarea
                rows={8}
                value={tools}
                onChange={(e) => setTools(e.target.value)}
                placeholder={
                  '[{"name":"search_market","description":"Search public market evidence","parameters":{"query":"string"},"required":["query"]}]'
                }
              />
            </Field>
          )}
          <p className="section-note">
            Parameter types: string, number, boolean. Required keys must be
            listed under parameters. Approve tools only after reviewing their
            behavior with the provider.
          </p>
          <div className="inline-fields">
            <Button className="primary-button" disabled={busy}>
              Save connector
            </Button>
            {editing && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditing('');
                  setForm({
                    name: '',
                    kind: 'external_mcp',
                    endpoint: '',
                    secret: '',
                    clear_secret: false,
                    enabled: false,
                  });
                  setTools('[]');
                }}
              >
                Create another
              </Button>
            )}
          </div>
        </form>
      )}
      <section className="panel detail-body">
        <h2>Connections</h2>
        {!connectors.length ? (
          <Empty
            title="No external connections configured"
            text="An Admin can add the MCP endpoint or enterprise review-task receiver when available."
          />
        ) : (
          connectors.map((c) => (
            <div className="ai3-card" key={c.id}>
              <div className="mi-intro">
                <div>
                  <h3>{c.name}</h3>
                  <p className="section-note">
                    {c.kind === 'external_mcp'
                      ? 'External MCP'
                      : 'Enterprise workflow'}{' '}
                    · version {c.version} ·{' '}
                    {c.has_secret ? 'Token saved' : 'No token'}
                  </p>
                </div>
                <Status>{c.enabled ? 'Enabled' : 'Disabled'}</Status>
              </div>
              {admin && (
                <div className="inline-fields">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEditing(c.id);
                      setForm({
                        name: c.name,
                        kind: c.kind,
                        endpoint: c.endpoint,
                        secret: '',
                        clear_secret: false,
                        enabled: c.enabled,
                      });
                      setTools(JSON.stringify(c.tools, null, 2));
                    }}
                  >
                    Edit configuration
                  </Button>
                  {c.kind === 'external_mcp' && (
                    <Button
                      variant="outline"
                      disabled={busy || !c.enabled}
                      onClick={() =>
                        act(async () => {
                          const r = await api(
                            '/enterprise/connectors/' + c.id + '/test',
                            {},
                          );
                          setNotice(
                            'Connected. Approved read-only tools: ' +
                              (r.tools.map((t: Row) => t.name).join(', ') ||
                                'none advertised'),
                          );
                        })
                      }
                    >
                      Test tool discovery
                    </Button>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </section>
      {!admin && (
        <>
          <form
            className="panel detail-body"
            onSubmit={(e) => {
              e.preventDefault();
              void act(async () => {
                const r = await api(
                  '/enterprise/connectors/' + connector + '/query',
                  { tool, parameters, category_id: category, purpose },
                );
                setNotice('External evidence saved: ' + r.name);
                if (onEvidence) await onEvidence();
              });
            }}
          >
            <h2>Retrieve external evidence</h2>
            <p className="section-note">
              Only the purposefully entered tool parameters below are sent.
              Retrieved text is preserved as external evidence and does not
              become an instruction.
            </p>
            <div className="ai3-grid">
              <Field label="MCP connection">
                <Options
                  rows={connectors.filter(
                    (c) => c.kind === 'external_mcp' && c.enabled,
                  )}
                  value={connector}
                  onChange={(v) => {
                    setConnector(v);
                    setTool('');
                    setParameters({});
                  }}
                />
              </Field>
              <Field label="Approved tool">
                <Picker
                  value={tool}
                  onChange={(v) => {
                    setTool(v);
                    setParameters({});
                  }}
                  options={[
                    { value: '', label: 'Select tool' },
                    ...(active?.tools || []).map((t: Row) => ({
                      value: t.name,
                      label: t.name,
                    })),
                  ]}
                />
              </Field>
              <Field label="Evidence category">
                <Options
                  rows={data.categories}
                  value={category}
                  onChange={setCategory}
                />
              </Field>
            </div>
            {policy && (
              <>
                <p className="section-note">{policy.description}</p>
                {Object.entries(policy.parameters).map(([key, typ]) => (
                  <Field
                    key={key}
                    label={
                      key +
                      (policy.required.includes(key) ? ' *' : ' (optional)')
                    }
                  >
                    {typ === 'boolean' ? (
                      <Picker
                        value={
                          parameters[key] === undefined
                            ? ''
                            : String(parameters[key])
                        }
                        onChange={(v) =>
                          setParameters({ ...parameters, [key]: v === 'true' })
                        }
                        options={[
                          { value: '', label: 'Select value' },
                          { value: 'true', label: 'True' },
                          { value: 'false', label: 'False' },
                        ]}
                      />
                    ) : (
                      <Input
                        type={typ === 'number' ? 'number' : 'text'}
                        step="any"
                        required={policy.required.includes(key)}
                        maxLength={1000}
                        value={parameters[key] ?? ''}
                        onChange={(e) => {
                          const next = { ...parameters };
                          if (e.target.value === '') delete next[key];
                          else
                            next[key] =
                              typ === 'number'
                                ? Number(e.target.value)
                                : e.target.value;
                          setParameters(next);
                        }}
                      />
                    )}
                  </Field>
                ))}
              </>
            )}
            <Field label="Research purpose">
              <Input
                required
                minLength={10}
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              />
            </Field>
            <Button
              disabled={busy || !connector || !tool || !category}
              className="primary-button"
            >
              Query and save evidence
            </Button>
          </form>
          <section className="panel detail-body">
            <h2>External evidence archive</h2>
            {evidence.map((r) => (
              <details key={r.id} className="ai3-card">
                <summary>
                  {r.name} · {r.retrieved_at.slice(0, 10)}
                </summary>
                <p className="section-note">{r.purpose}</p>
                <pre className="ai3-pre">
                  {r.content.text ||
                    JSON.stringify(r.content.structured, null, 2)}
                </pre>
                <JsonDownload value={r} name="greta-external-evidence" />
                {r.owner === data.user.id && (
                  <div>
                    <h3>Share evidence with your team</h3>
                    {people.map((p) => (
                      <label className="check-label" key={p.id}>
                        <input
                          type="checkbox"
                          disabled={busy}
                          checked={(r.shared_with || []).includes(p.id)}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...(r.shared_with || []), p.id]
                              : r.shared_with.filter(
                                  (id: string) => id !== p.id,
                                );
                            void act(async () => {
                              await api(
                                '/enterprise/evidence/' + r.id + '/sharing',
                                { user_ids: next },
                                'PUT',
                              );
                              if (onEvidence) await onEvidence();
                            });
                          }}
                        />
                        {p.name} · {p.role}
                      </label>
                    ))}
                  </div>
                )}
              </details>
            ))}
            {!evidence.length && (
              <p className="section-note">
                Saved queries will appear here and in cost-model and risk
                evidence selectors.
              </p>
            )}
          </section>
          <form
            className="panel detail-body"
            onSubmit={(e) => {
              e.preventDefault();
              void act(async () => {
                const r = await api('/enterprise/packages', {
                  recommendation_id: rec,
                  connector_id: destination,
                  title,
                  business_justification: justification,
                });
                setSelected(r);
                setConsent(false);
                setRationale('');
              });
            }}
          >
            <h2>Prepare an enterprise review task</h2>
            <p className="section-note">
              Select a Buyer-approved recommendation, then inspect the exact
              outgoing package before approving delivery.
            </p>
            <div className="ai3-grid">
              <Field label="Approved recommendation">
                <Options
                  rows={analyses.filter(
                    (r) =>
                      r.variant === 'recommendation' && r.status === 'APPROVED',
                  )}
                  value={rec}
                  onChange={setRec}
                />
              </Field>
              <Field label="Destination">
                <Options
                  rows={connectors.filter((c) => c.kind === 'workflow')}
                  value={destination}
                  onChange={setDestination}
                />
              </Field>
              <Field label="Task title">
                <Input
                  required
                  minLength={5}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Business justification">
              <Textarea
                required
                minLength={10}
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
              />
            </Field>
            <Button
              className="primary-button"
              disabled={busy || !rec || !destination}
            >
              Prepare package for review
            </Button>
          </form>
          <section className="panel detail-body">
            <h2>Workflow packages and delivery history</h2>
            {packages.map((p) => (
              <div className="ai3-card" key={p.id}>
                <button
                  className="text-link"
                  onClick={() => {
                    setSelected(p);
                    setConsent(false);
                    setRationale('');
                    setReceipt('');
                  }}
                >
                  {p.title}
                </button>
                <p className="section-note">
                  {p.delivery?.status || p.status} ·{' '}
                  {p.delivery?.receipt || 'No receiver receipt'}
                </p>
              </div>
            ))}
            {selected && (
              <div className="ai3-card">
                <h3>{selected.title}</h3>
                <p className="section-note">
                  Destination:{' '}
                  {connectors.find((c) => c.id === selected.connector_id)?.name}{' '}
                  · connector version {selected.connector_version}
                </p>
                <details open>
                  <summary>Exact outgoing package</summary>
                  <pre className="ai3-pre">
                    {JSON.stringify(selected.payload, null, 2)}
                  </pre>
                </details>
                <JsonDownload
                  value={selected.payload}
                  name="greta-review-task"
                />
                {buyer && selected.status === 'DRAFT' && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act(async () => {
                        setSelected(
                          await api(
                            '/enterprise/packages/' + selected.id + '/approve',
                            { rationale, approve_external_payload: true },
                          ),
                        );
                      });
                    }}
                  >
                    <Field label="Approval rationale">
                      <Textarea
                        required
                        minLength={10}
                        value={rationale}
                        onChange={(e) => setRationale(e.target.value)}
                      />
                    </Field>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        required
                        checked={consent}
                        onChange={(e) => setConsent(e.target.checked)}
                      />
                      I have reviewed this payload and approve sharing it with
                      the selected receiver.
                    </label>
                    <Button
                      disabled={busy || !consent}
                      className="primary-button"
                    >
                      Approve package
                    </Button>
                  </form>
                )}
                {buyer && selected.status === 'APPROVED' && (
                  <Button
                    className="primary-button"
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        const delivery = await api(
                          '/enterprise/packages/' + selected.id + '/deliver',
                          {},
                        );
                        setSelected({
                          ...selected,
                          status: 'QUEUED',
                          delivery,
                        });
                        setNotice(
                          'Delivery queued. Refresh to check the receiver receipt.',
                        );
                      })
                    }
                  >
                    Send approved review task
                  </Button>
                )}
                {selected.delivery && (
                  <>
                    <p className="body-copy">
                      Delivery: {selected.delivery.status} ·{' '}
                      {selected.delivery.receipt}
                    </p>
                    {selected.delivery.error && (
                      <ErrorBox error={selected.delivery.error} />
                    )}
                  </>
                )}
                {buyer && selected.delivery?.status === 'UNKNOWN' && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act(async () => {
                        const delivery = await api(
                          '/enterprise/packages/' + selected.id + '/reconcile',
                          {
                            accepted: accepted === 'yes',
                            receipt_or_evidence: receipt,
                          },
                        );
                        setSelected({ ...selected, delivery });
                      });
                    }}
                  >
                    <h3>Reconcile with the receiving system</h3>
                    <Field label="Verified outcome">
                      <Picker
                        value={accepted}
                        onChange={setAccepted}
                        options={[
                          { value: 'yes', label: 'Receiver accepted the task' },
                          {
                            value: 'no',
                            label: 'Receiver confirms task was not accepted',
                          },
                        ]}
                      />
                    </Field>
                    <Field label="Receipt or verification evidence">
                      <Textarea
                        required
                        minLength={10}
                        value={receipt}
                        onChange={(e) => setReceipt(e.target.value)}
                      />
                    </Field>
                    <Button disabled={busy}>Record verified outcome</Button>
                  </form>
                )}
              </div>
            )}
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  if (selected) {
                    const rows = await api('/enterprise/packages');
                    setSelected(
                      rows.find((p: Row) => p.id === selected.id) || null,
                    );
                  }
                })
              }
            >
              Refresh delivery status
            </Button>
          </section>
        </>
      )}
    </div>
  );
}
