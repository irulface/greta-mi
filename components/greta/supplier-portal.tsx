'use client';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, Row, Workspace, Status, ErrorBox, Empty } from './shared';
import { Field, Options } from './advanced-shared';
import { SupplierResponse } from './rfi';

export function SupplierPortal() {
  const [account, setAccount] = useState<Row | null>(null);
  const [activation, setActivation] = useState(() =>
    typeof window === 'undefined'
      ? ''
      : new URLSearchParams(window.location.search).get('activation') || '',
  );
  const [loading, setLoading] = useState(!activation);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [tab, setTab] = useState('rfis');
  const [rfis, setRFIs] = useState<Row[]>([]);
  const [history, setHistory] = useState<Row[]>([]);
  const [profile, setProfile] = useState<Row>({});
  const [form, setForm] = useState<Row>({
    contact_name: '',
    website: '',
    phone: '',
    capabilities: '',
    certifications: '',
  });
  const [selected, setSelected] = useState<Row | null>(null);
  const [threads, setThreads] = useState<Row[]>([]);
  const [question, setQuestion] = useState('');
  async function refresh() {
    const [r, h, p] = await Promise.all([
      api('/portal/rfis'),
      api('/portal/history'),
      api('/portal/profile'),
    ]);
    setRFIs(r);
    setHistory(h);
    setProfile(p);
    setForm({
      contact_name: '',
      website: '',
      phone: '',
      capabilities: '',
      certifications: '',
      ...p.profile,
    });
  }
  useEffect(() => {
    if (activation) {
      window.history.replaceState(null, '', '/?portal=1');
      return;
    }
    api('/portal/me')
      .then(async (a) => {
        setAccount(a);
        await refresh();
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [activation]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function open(r: Row) {
    setSelected(r);
    setQuestion('');
    setThreads(await api('/portal/rfis/' + r.id + '/clarifications'));
  }
  if (loading)
    return (
      <main className="supplier-response">
        <p>Loading supplier portal…</p>
      </main>
    );
  if (!account)
    return (
      <main className="supplier-response ai3">
        <div className="response-brand">
          greta<span>SUPPLIER PORTAL</span>
        </div>
        <form
          className="panel detail-body"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              if (activation) {
                const result = await api('/portal/activate', {
                  token: activation,
                  password,
                });
                setEmail(result.email);
                setActivation('');
                setPassword('');
                setNotice('Account activated. Sign in with your new password.');
              } else {
                setAccount(await api('/portal/login', { email, password }));
                setPassword('');
                await refresh();
              }
            });
          }}
        >
          <h1>
            {activation ? 'Activate your supplier account' : 'Supplier sign in'}
          </h1>
          <p className="section-note">
            Access your company profile, invitations, and submission history.
          </p>
          <ErrorBox error={error} />
          {notice && <div className="success-box">{notice}</div>}
          {!activation && (
            <Field label="Email">
              <Input
                required
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
          )}
          <Field
            label={
              activation
                ? 'Choose password (minimum 12 characters)'
                : 'Password'
            }
          >
            <Input
              required
              type="password"
              minLength={activation ? 12 : 1}
              maxLength={200}
              autoComplete={activation ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button className="primary-button" disabled={busy}>
            {activation ? 'Activate account' : 'Sign in'}
          </Button>
          <p className="section-note">
            Contact your buyer for account access or a password reset.
          </p>
          <Button
            type="button"
            variant="link"
            onClick={() => window.location.assign('/')}
          >
            Internal workspace
          </Button>
        </form>
      </main>
    );
  return (
    <main className="supplier-response ai3 portal-shell">
      <div className="response-brand">
        greta<span>SUPPLIER PORTAL</span>
      </div>
      <section className="panel detail-body">
        <div className="mi-intro">
          <div>
            <h1>{profile.company_name}</h1>
            <p className="section-note">
              {account.name} · {account.email}
            </p>
          </div>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api('/portal/logout', {});
                setAccount(null);
                setSelected(null);
                setHistory([]);
              })
            }
          >
            Sign out
          </Button>
        </div>
        <div className="inline-fields">
          {[
            ['rfis', 'Invited RFIs'],
            ['profile', 'Company profile'],
            ['history', 'Submission history'],
          ].map(([id, label]) => (
            <Button
              key={id}
              variant={tab === id ? 'default' : 'outline'}
              onClick={() => {
                setTab(id);
                setSelected(null);
              }}
            >
              {label}
            </Button>
          ))}
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => act(refresh)}
          >
            Refresh
          </Button>
        </div>
        <ErrorBox error={error} />
        {notice && <div className="success-box">{notice}</div>}
      </section>
      {tab === 'profile' && (
        <form
          className="panel detail-body"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              const payload = Object.fromEntries(
                [
                  'contact_name',
                  'website',
                  'phone',
                  'capabilities',
                  'certifications',
                ].map((k) => [k, form[k] || '']),
              );
              setProfile(await api('/portal/profile', payload, 'PUT'));
              setNotice(
                'Company profile saved. These details are marked as supplier-reported.',
              );
            });
          }}
        >
          <h2>Company profile</h2>
          <p className="section-note">
            Company name and country are maintained by your buyer. Capabilities
            and certifications below are supplier-reported.
          </p>
          {[
            ['contact_name', 'Contact name'],
            ['website', 'Website'],
            ['phone', 'Phone'],
          ].map(([key, label]) => (
            <Field key={key} label={label}>
              <Input
                required={key === 'contact_name'}
                minLength={key === 'contact_name' ? 2 : undefined}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </Field>
          ))}
          {[
            ['capabilities', 'Capabilities and capacity'],
            ['certifications', 'Certifications and validity dates'],
          ].map(([key, label]) => (
            <Field key={key} label={label}>
              <Textarea
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </Field>
          ))}
          <Button disabled={busy} className="primary-button">
            Save company profile
          </Button>
        </form>
      )}
      {tab === 'rfis' && !selected && (
        <section className="panel detail-body">
          <h2>Your invitations</h2>
          {rfis.map((r) => (
            <div className="ai3-card" key={r.id}>
              <p className="reference">
                {r.number} · revision {r.version}
              </p>
              <h3>{r.title}</h3>
              <p className="section-note">Closing {r.closing_date}</p>
              <div className="inline-fields">
                <Status>{r.status}</Status>
                <Button variant="outline" onClick={() => act(() => open(r))}>
                  Open questionnaire & clarification
                </Button>
              </div>
            </div>
          ))}
          {!rfis.length && (
            <Empty
              title="No RFI invitations yet"
              text="Your buyer must issue an invitation to your company before the questionnaire appears here."
            />
          )}
        </section>
      )}
      {tab === 'rfis' && selected && (
        <>
          <Button
            variant="outline"
            onClick={() => {
              setSelected(null);
              void act(refresh);
            }}
          >
            Back to invitations
          </Button>
          <SupplierResponse
            key={selected.id}
            endpoint={'/portal/rfis/' + selected.id}
          />
          <section className="panel detail-body">
            <h2>Private clarification with your buyer</h2>
            {threads.map((t) => (
              <div className="ai3-card" key={t.id}>
                <p className="body-copy">{t.text}</p>
                <p className="section-note">
                  {t.author} · {t.created_at.slice(0, 10)} · {t.status}
                </p>
                {t.reply && (
                  <>
                    <h3>Buyer response</h3>
                    <p className="body-copy">{t.reply}</p>
                  </>
                )}
              </div>
            ))}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void act(async () => {
                  await api('/portal/rfis/' + selected.id + '/clarifications', {
                    text: question,
                  });
                  setQuestion('');
                  setThreads(
                    await api(
                      '/portal/rfis/' + selected.id + '/clarifications',
                    ),
                  );
                });
              }}
            >
              <Field label="Ask for clarification">
                <Textarea
                  required
                  minLength={3}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                />
              </Field>
              <Button disabled={busy} className="primary-button">
                Send clarification to buyer
              </Button>
            </form>
          </section>
        </>
      )}
      {tab === 'history' && (
        <section className="panel detail-body">
          <h2>Submission history</h2>
          {!history.length && (
            <Empty
              title="No submissions yet"
              text="Final responses and earlier amendment cycles will be retained here."
            />
          )}
          {history.map((r) => (
            <details className="ai3-card" key={r.id}>
              <summary>
                {r.number} · {r.title} · revision {r.version}{' '}
                {r.historical ? '(historical)' : ''}
              </summary>
              <p className="section-note">Submitted {r.submitted_at}</p>
              {Object.entries(r.answers).map(([key, value]) => (
                <div className="ai3-card" key={key}>
                  <h3>
                    {r.questions?.find((q: Row) => q.id === key)?.text || key}
                  </h3>
                  {value && typeof value === 'object' && 'id' in value ? (
                    <a
                      className="text-link"
                      href={'/api/v1/portal/attachments/' + (value as Row).id}
                    >
                      {(value as Row).name || 'Download attachment'}
                    </a>
                  ) : (
                    <p className="body-copy">
                      {Array.isArray(value)
                        ? value.join(', ')
                        : typeof value === 'string'
                          ? value
                          : JSON.stringify(value ?? '')}
                    </p>
                  )}
                </div>
              ))}
            </details>
          ))}
        </section>
      )}
    </main>
  );
}

export function SupplierPortalAdmin({ data }: { data: Workspace }) {
  const [accounts, setAccounts] = useState<Row[]>([]);
  const [threads, setThreads] = useState<Row[]>([]);
  const [supplier, setSupplier] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [link, setLink] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [replies, setReplies] = useState<Row>({});
  async function refresh() {
    const [a, t] = await Promise.all([
      api('/portal/accounts'),
      api('/portal/clarifications'),
    ]);
    setAccounts(a);
    setThreads(t);
  }
  const canManage = data.user.permissions.includes('rfi:manage');
  useEffect(() => {
    if (!canManage) return;
    let cancelled = false;
    Promise.all([api('/portal/accounts'), api('/portal/clarifications')])
      .then(([a, t]) => {
        if (!cancelled) {
          setAccounts(a);
          setThreads(t);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [canManage, data.user.id]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!data.user.permissions.includes('rfi:manage')) return null;
  return (
    <section className="panel detail-body ai3">
      <h2>Supplier portal access</h2>
      <p className="section-note">
        Create an account for a supplier contact. Activation links expire in 48
        hours and are displayed once. Share the link through your approved
        channel.
      </p>
      <a
        className="text-link"
        href="/?portal=1"
        target="_blank"
        rel="noreferrer"
      >
        Open supplier portal
      </a>
      <ErrorBox error={error} />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            const r = await api('/portal/accounts', {
              supplier_id: supplier,
              email,
              name,
            });
            setLink(location.origin + r.activation_path);
            setEmail('');
            setName('');
          });
        }}
      >
        <div className="ai3-grid">
          <Field label="Company">
            <Options
              rows={data.suppliers}
              value={supplier}
              onChange={(v) => {
                setSupplier(v);
                setEmail(data.suppliers.find((s) => s.id === v)?.email || '');
              }}
            />
          </Field>
          <Field label="Contact name">
            <Input
              required
              minLength={2}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Contact email">
            <Input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
        </div>
        <Button disabled={busy || !supplier} className="primary-button">
          Create activation link
        </Button>
      </form>
      {link && (
        <div className="ai3-card">
          <Field label="One-time activation link">
            <Input readOnly value={link} onFocus={(e) => e.target.select()} />
          </Field>
          <p className="section-note">
            This localhost link is accessible on this computer. Use the public
            application address when deployed.
          </p>
          <Button variant="outline" onClick={() => setLink('')}>
            Dismiss link
          </Button>
        </div>
      )}
      {accounts.map((a) => (
        <div className="ai3-card" key={a.id}>
          <h3>
            {a.name} ·{' '}
            {data.suppliers.find((s) => s.id === a.supplier_id)?.name}
          </h3>
          <p className="section-note">
            {a.email} ·{' '}
            {a.active
              ? a.activated
                ? 'Active'
                : 'Awaiting activation'
              : 'Deactivated'}
          </p>
          <div className="inline-fields">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await api('/portal/accounts/' + a.id, {
                    action: 'reset',
                  });
                  setLink(location.origin + r.activation_path);
                })
              }
            >
              Reset password / renew activation
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api('/portal/accounts/' + a.id, {
                    action: a.active ? 'deactivate' : 'reactivate',
                  });
                })
              }
            >
              {a.active ? 'Deactivate access' : 'Reactivate access'}
            </Button>
          </div>
        </div>
      ))}
      <h2>Supplier clarifications</h2>
      {threads.map((t) => (
        <form
          className="ai3-card"
          key={t.id}
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await api('/portal/clarifications/' + t.id + '/reply', {
                text: replies[t.id] || '',
              });
            });
          }}
        >
          <h3>
            {data.suppliers.find((s) => s.id === t.supplier_id)?.name} ·{' '}
            {data.rfis.find((r) => r.id === t.rfi_id)?.number}
          </h3>
          <p className="body-copy">{t.text}</p>
          <Status>{t.status}</Status>
          {t.reply && <p className="body-copy">Current reply: {t.reply}</p>}
          <Field label="Reply visible to this supplier">
            <Textarea
              required
              minLength={3}
              value={replies[t.id] || ''}
              onChange={(e) =>
                setReplies({ ...replies, [t.id]: e.target.value })
              }
            />
          </Field>
          <Button disabled={busy} variant="outline">
            Publish reply to supplier portal
          </Button>
        </form>
      ))}
      {!threads.length && (
        <p className="section-note">No supplier questions yet.</p>
      )}
    </section>
  );
}
