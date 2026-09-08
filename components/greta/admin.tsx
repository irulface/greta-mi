'use client';
import { AgentControls } from './autonomous-intelligence';
import { EnterprisePanel } from './enterprise';
import { useState, useEffect } from 'react';
import {
  Settings2,
  ShieldCheck,
  Check,
  PlugZap,
  ScanLine,
  Plus,
  RefreshCw,
  KeyRound,
  Database,
  Mail,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
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
import { Row, Workspace, api, Picker, Status, ErrorBox, Empty } from './shared';
export function Administration({
  data,
  refresh,
  onMarket,
}: {
  data: Workspace;
  refresh: () => Promise<void>;
  onMarket?: () => void;
}) {
  const [config, setConfig] = useState<Row>({
    azure: { enabled: false },
    mcp: { enabled: false },
    prompts: { system: '', version: 1 },
  });
  const [audit, setAudit] = useState<Row[]>([]);
  const [users, setUsers] = useState<Row[]>([]);
  const [jobs, setJobs] = useState<Row[]>([]);
  const [email, setEmail] = useState<Row>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [newUser, setNewUser] = useState<Row>({
    name: '',
    email: '',
    password: '',
    role: 'Buyer',
    region: 'Region 1',
  });
  const [directory, setDirectory] = useState('');
  const [taxonomy, setTaxonomy] = useState<Row[]>(data.categories);
  const [categoryForm, setCategoryForm] = useState<Row>({
    name: '',
    group: '',
    subcategory: '',
    commodity: '',
  });
  async function load() {
    try {
      const [c, a, u, j, mail] = await Promise.all([
        api('/admin/config'),
        api('/admin/audit'),
        api('/admin/users'),
        api('/repository/jobs'),
        api('/admin/email'),
      ]);
      setConfig(c);
      setAudit(a);
      setUsers(u);
      setJobs(j);
      setEmail(mail);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function action(path: string, body: any = {}, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api(path, body, method);
      setNotice(
        result.latency_ms
          ? 'Connection verified · ' + result.latency_ms + ' ms'
          : 'Changes saved successfully.',
      );
      return result;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function setConfigField(id: string, k: string, v: any) {
    setConfig({ ...config, [id]: { ...config[id], [k]: v } });
  }
  if (data.user.role !== 'Admin')
    return (
      <Empty
        title="Administration is restricted"
        text="Your account needs the Admin role to manage system configuration."
      />
    );
  return (
    <>
      <div className="admin-summary">
        <ShieldCheck size={25} />
        <div>
          <h2>Platform administration</h2>
          <p>
            Manage connections, access, and the health of your knowledge
            repository.
          </p>
        </div>
        <Status>
          {data.demo ? 'Development environment' : 'Production environment'}
        </Status>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <div className="success-box" role="status">
          <Check size={16} />
          {notice}
        </div>
      )}
      <Tabs defaultValue="azure">
        <TabsList className="workspace-tabs wide-tabs">
          <TabsTrigger value="azure">Azure OpenAI</TabsTrigger>
          <TabsTrigger value="mcp">Enterprise MCP</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="market">Market APIs</TabsTrigger>
          <TabsTrigger value="agents">Autonomous control</TabsTrigger>
          <TabsTrigger value="advanced">External & workflows</TabsTrigger>
          <TabsTrigger value="users">Users & access</TabsTrigger>
          <TabsTrigger value="taxonomy">Category taxonomy</TabsTrigger>
          <TabsTrigger value="indexing">Indexing</TabsTrigger>
          <TabsTrigger value="prompts">Prompt registry</TabsTrigger>
          <TabsTrigger value="audit">Audit log</TabsTrigger>
        </TabsList>
        <TabsContent value="agents">
          <AgentControls />
        </TabsContent>
        <TabsContent value="advanced">
          <EnterprisePanel data={data} />
        </TabsContent>
        {['azure', 'mcp'].map((id) => (
          <TabsContent key={id} value={id}>
            <section className="panel detail-body config-panel">
              <div className="panel-heading">
                <div>
                  <h2>
                    {id === 'azure' ? <SparkleIcon /> : <PlugZap size={20} />}{' '}
                    {id === 'azure'
                      ? 'Azure OpenAI connection'
                      : 'Internal MCP gateway'}
                  </h2>
                  <p>
                    {id === 'azure'
                      ? 'Map reasoning and embedding tasks to your Azure deployments.'
                      : 'Read-only access to approved demand, inventory, and procurement tools.'}
                  </p>
                </div>
                <Status>
                  {config[id]?.enabled ? 'Enabled' : 'Not configured'}
                </Status>
              </div>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  const result = await action(
                    '/admin/config/' + id,
                    config[id],
                    'PUT',
                  );
                  if (result) setConfig({ ...config, [id]: result });
                }}
              >
                <div className="form-grid">
                  <label className="full">
                    {id === 'azure' ? 'Azure endpoint' : 'MCP gateway endpoint'}
                    <Input
                      type="url"
                      value={config[id]?.endpoint || ''}
                      onChange={(e) =>
                        setConfigField(id, 'endpoint', e.target.value)
                      }
                      placeholder={
                        id === 'azure'
                          ? 'https://your-resource.openai.azure.com'
                          : 'https://mcp.your-company.com/mcp'
                      }
                    />
                  </label>
                  <label className="full">
                    {id === 'azure' ? 'API key' : 'Gateway access token'}
                    <Input
                      type="password"
                      autoComplete="new-password"
                      value={config[id]?.api_key || ''}
                      placeholder={
                        config[id]?.has_secret
                          ? '•••••••• · Saved securely. Leave empty to retain.'
                          : 'Enter credential'
                      }
                      onChange={(e) =>
                        setConfigField(id, 'api_key', e.target.value)
                      }
                    />
                  </label>
                  {id === 'azure' && (
                    <>
                      <label>
                        Reasoning deployment
                        <Input
                          value={config.azure.model || ''}
                          onChange={(e) =>
                            setConfigField(id, 'model', e.target.value)
                          }
                          placeholder="Your deployment name"
                        />
                      </label>
                      <label>
                        Embedding deployment
                        <Input
                          value={config.azure.embedding || ''}
                          onChange={(e) =>
                            setConfigField(id, 'embedding', e.target.value)
                          }
                          placeholder="Your embedding deployment"
                        />
                      </label>
                      <label>
                        Timeout (seconds)
                        <Input
                          type="number"
                          min={5}
                          max={120}
                          value={config.azure.timeout || 60}
                          onChange={(e) =>
                            setConfigField(
                              id,
                              'timeout',
                              Number(e.target.value),
                            )
                          }
                        />
                      </label>
                      <label>
                        Maximum completion tokens
                        <Input
                          type="number"
                          min={100}
                          max={16000}
                          value={config.azure.token_limit || 2000}
                          onChange={(e) =>
                            setConfigField(
                              id,
                              'token_limit',
                              Number(e.target.value),
                            )
                          }
                        />
                      </label>
                    </>
                  )}
                  <label className="check-label full">
                    <Checkbox
                      checked={!!config[id]?.enabled}
                      onCheckedChange={(v) => setConfigField(id, 'enabled', v)}
                    />
                    Enable this connection
                  </label>
                </div>
                <div className="info-note">
                  <KeyRound size={16} />
                  {id === 'azure'
                    ? 'Credentials are encrypted on the server and never returned to the browser.'
                    : 'The gateway host must be in the server’s MCP_ALLOWED_HOSTS configuration. User identity and region are enforced on every call.'}
                </div>
                <div className="dialog-actions">
                  <span>
                    {id === 'azure'
                      ? 'API key authentication'
                      : 'Read-only · No ERP write-back'}
                  </span>
                  <div className="inline-fields">
                    {id === 'azure' && (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={() => action('/admin/config/azure/test')}
                      >
                        <PlugZap size={16} />
                        Test saved connection
                      </Button>
                    )}
                    <Button
                      className="primary-button"
                      type="submit"
                      disabled={busy}
                    >
                      Save configuration
                    </Button>
                  </div>
                </div>
              </form>
            </section>
            {id === 'mcp' && (
              <section className="panel detail-body">
                <h3>Approved domain tools</h3>
                <div className="tool-grid">
                  {[
                    'get_demand_history',
                    'get_inventory_position',
                    'get_po_history',
                    'get_supplier_spend',
                    'get_lead_time_history',
                    'get_open_purchase_orders',
                  ].map((t) => (
                    <div key={t}>
                      <Database size={16} />
                      <code>{t}</code>
                      <Status>Read only</Status>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </TabsContent>
        ))}
        <TabsContent value="market">
          <section className="panel detail-body">
            <h3>External market data</h3>
            <p className="section-note">
              Configure EIA spot-price feeds or approved JSON providers.
              Credentials are encrypted on the server. Analysts can import
              observations and schedule updates.
            </p>
            {onMarket && (
              <Button variant="outline" onClick={onMarket}>
                <Database size={16} /> Manage market API sources
              </Button>
            )}
          </section>
        </TabsContent>
        <TabsContent value="email">
          <section className="panel detail-body config-panel">
            <div className="panel-heading">
              <div>
                <h2>
                  <Mail size={20} /> RFI invitation email
                </h2>
                <p>
                  Connection settings are managed in the server environment.
                </p>
              </div>
              <Status>
                {email.configured ? 'Configured' : 'Not configured'}
              </Status>
            </div>
            <div className="form-grid">
              <label>
                SMTP host
                <Input readOnly value={email.host || 'Not set'} />
              </label>
              <label>
                Port / encryption
                <Input
                  readOnly
                  value={
                    [email.port, email.transport].filter(Boolean).join(' / ') ||
                    'Not set'
                  }
                />
              </label>
              <label className="full">
                Sender
                <Input readOnly value={email.sender || 'Not set'} />
              </label>
              <label className="full">
                Supplier application URL
                <Input readOnly value={email.public_app_url || 'Not set'} />
              </label>
            </div>
            <div className="info-note">
              {email.invitations_ready
                ? 'Buyers can review recipients and send invitations from the RFI Suppliers tab.'
                : 'To enable invitations, configure SMTP and a public HTTPS application address in PUBLIC_APP_URL on the server.'}
            </div>
            <p className="section-note">
              The connection test checks authentication without sending an
              email. Passwords are never returned to the browser.
            </p>
            <Button
              variant="outline"
              disabled={busy || !email.configured}
              onClick={async () => {
                const result = await action('/admin/email/test');
                if (result)
                  setNotice(
                    `SMTP authentication verified · ${result.transport} · ${result.latency_ms} ms · No email sent.`,
                  );
              }}
            >
              <PlugZap size={16} /> Test SMTP connection
            </Button>
          </section>
        </TabsContent>
        <TabsContent value="users">
          <section className="panel module-panel">
            <div className="panel-heading">
              <div>
                <h2>Users & roles</h2>
                <p>Admin access does not grant procurement approval.</p>
              </div>
              <Button
                className="primary-button"
                onClick={() => setAddOpen(true)}
              >
                <Plus size={16} />
                Add user
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  {['USER', 'ROLE', 'DATA SCOPE', 'STATUS'].map((h) => (
                    <TableHead key={h}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <strong className="rfi-title">{u.name}</strong>
                      <span className="table-category">{u.email}</span>
                    </TableCell>
                    <TableCell>
                      {u.id === data.user.id ? (
                        u.role
                      ) : (
                        <Picker
                          value={u.role}
                          onChange={async (role) => {
                            const result = await action(
                              '/admin/users/' + u.id,
                              { role, region: u.region, active: u.active },
                              'PUT',
                            );
                            if (result) await load();
                          }}
                          options={[
                            'Admin',
                            'Buyer',
                            'Fungsi Pengguna',
                            'Market Intelligence Analyst',
                          ]}
                        />
                      )}
                    </TableCell>
                    <TableCell>{u.region}</TableCell>
                    <TableCell>
                      <label className="check-label">
                        <Checkbox
                          aria-label={'Active user ' + u.name}
                          disabled={u.id === data.user.id}
                          checked={u.active}
                          onCheckedChange={async (active) => {
                            const result = await action(
                              '/admin/users/' + u.id,
                              { role: u.role, region: u.region, active },
                              'PUT',
                            );
                            if (result) await load();
                          }}
                        />
                        {u.active ? 'Active' : 'Inactive'}
                      </label>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        </TabsContent>
        <TabsContent value="taxonomy">
          <section className="panel detail-body">
            <h3>Category taxonomy</h3>
            <p className="section-note">
              Maintain the four-level hierarchy used by RFIs, suppliers, and
              knowledge sources.
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  {['GROUP', 'CATEGORY', 'SUBCATEGORY', 'COMMODITY'].map(
                    (h) => (
                      <TableHead key={h}>{h}</TableHead>
                    ),
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {taxonomy.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>{c.group}</TableCell>
                    <TableCell>{c.name}</TableCell>
                    <TableCell>{c.subcategory}</TableCell>
                    <TableCell>{c.commodity}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const result = await action('/admin/categories', categoryForm);
                if (result) {
                  setTaxonomy([...taxonomy, result]);
                  await refresh();
                  setCategoryForm({
                    name: '',
                    group: '',
                    subcategory: '',
                    commodity: '',
                  });
                }
              }}
            >
              <div className="form-grid">
                {[
                  { key: 'group', label: 'Category group' },
                  { key: 'name', label: 'Category name' },
                  { key: 'subcategory', label: 'Subcategory' },
                  { key: 'commodity', label: 'Commodity / material / service' },
                ].map((f) => (
                  <label key={f.key}>
                    {f.label}
                    <Input
                      required
                      minLength={f.key === 'name' ? 3 : 2}
                      value={categoryForm[f.key]}
                      onChange={(e) =>
                        setCategoryForm({
                          ...categoryForm,
                          [f.key]: e.target.value,
                        })
                      }
                    />
                  </label>
                ))}
              </div>
              <Button type="submit" className="primary-button" disabled={busy}>
                <Plus size={16} />
                Add category
              </Button>
            </form>
          </section>
        </TabsContent>
        <TabsContent value="indexing">
          <section className="panel detail-body">
            <div className="panel-heading">
              <div>
                <h2>
                  <ScanLine size={19} />
                  Directory indexing
                </h2>
                <p>
                  Recursive discovery, checksum validation, text extraction, and
                  embedding.
                </p>
              </div>
              <Button variant="outline" onClick={load}>
                <RefreshCw size={15} />
                Refresh jobs
              </Button>
            </div>
            <form
              className="toolbar"
              onSubmit={async (e) => {
                e.preventDefault();
                const result = await action('/repository/index', {
                  path: directory,
                });
                if (result) {
                  setNotice(
                    'Directory scan queued. The indexing worker will process the files.',
                  );
                  setJobs(await api('/repository/jobs'));
                }
              }}
            >
              <Input
                value={directory}
                onChange={(e) => setDirectory(e.target.value)}
                placeholder="Default repository directory, or a subdirectory"
                aria-label="Repository directory"
              />
              <Button type="submit" className="primary-button" disabled={busy}>
                <ScanLine size={16} />
                Scan directory
              </Button>
            </form>
            <p className="section-note">
              Only directories within the server’s configured repository root
              are accessible. Unchanged files are deduplicated using SHA-256.
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  {['JOB', 'STATUS', 'INDEXED', 'DUPLICATES', 'FAILED'].map(
                    (h) => (
                      <TableHead key={h}>{h}</TableHead>
                    ),
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((j) => (
                  <TableRow key={j.id}>
                    <TableCell>
                      {j.name || 'Directory scan'}
                      <small className="table-category">
                        {j.id.slice(0, 8)}
                      </small>
                    </TableCell>
                    <TableCell>
                      <Status>{j.status}</Status>
                    </TableCell>
                    <TableCell>{j.indexed ?? '—'}</TableCell>
                    <TableCell>{j.duplicate ?? '—'}</TableCell>
                    <TableCell>{j.failed ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!jobs.length && (
              <Empty
                title="No indexing jobs yet"
                text="Upload documents in the repository or start a directory scan."
              />
            )}
          </section>
        </TabsContent>
        <TabsContent value="prompts">
          <section className="panel detail-body">
            <h3>
              Market research system prompt{' '}
              <Status>Version {config.prompts.version}</Status>
            </h3>
            <p className="section-note">
              Every change creates a new prompt version and an audit event.
            </p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const result = await action(
                  '/admin/prompts',
                  { system: config.prompts.system },
                  'PUT',
                );
                if (result) setConfig({ ...config, prompts: result });
              }}
            >
              <Textarea
                aria-label="System prompt"
                value={config.prompts.system}
                rows={12}
                onChange={(e) =>
                  setConfigField('prompts', 'system', e.target.value)
                }
              />
              <div className="dialog-actions">
                <Button
                  className="primary-button"
                  type="submit"
                  disabled={busy}
                >
                  Save new version
                </Button>
              </div>
            </form>
          </section>
        </TabsContent>
        <TabsContent value="audit">
          <section className="panel module-panel">
            <div className="panel-heading">
              <div>
                <h2>Audit trail</h2>
                <p>
                  Latest 200 events · Credentials and invitation tokens are
                  excluded.
                </p>
              </div>
              <Button variant="outline" onClick={load}>
                <RefreshCw size={16} />
                Refresh
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  {['EVENT', 'ACTOR', 'TARGET', 'TIMESTAMP', 'CORRELATION'].map(
                    (h) => (
                      <TableHead key={h}>{h}</TableHead>
                    ),
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>{a.event}</TableCell>
                    <TableCell>{a.actor}</TableCell>
                    <TableCell>{a.target?.slice(0, 18) || '—'}</TableCell>
                    <TableCell>
                      {new Date(a.timestamp).toLocaleString('en-GB')}
                    </TableCell>
                    <TableCell>
                      <code>{a.correlation_id.slice(0, 8)}</code>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        </TabsContent>
      </Tabs>
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="large-dialog">
          <DialogTitle>Add internal user</DialogTitle>
          <DialogDescription>
            Assign a role and data scope. Use a password of at least 14
            characters.
          </DialogDescription>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const result = await action('/admin/users', newUser);
              if (result) {
                setAddOpen(false);
                await load();
              }
            }}
          >
            <div className="form-grid">
              {['name', 'email', 'password', 'region'].map((k) => (
                <label key={k}>
                  {k[0].toUpperCase() + k.slice(1)}
                  <Input
                    required
                    minLength={k === 'password' ? 14 : 2}
                    type={
                      k === 'password'
                        ? 'password'
                        : k === 'email'
                          ? 'email'
                          : 'text'
                    }
                    value={newUser[k]}
                    onChange={(e) =>
                      setNewUser({ ...newUser, [k]: e.target.value })
                    }
                  />
                </label>
              ))}
              <label>
                Role
                <Picker
                  value={newUser.role}
                  onChange={(v) => setNewUser({ ...newUser, role: v })}
                  options={[
                    'Admin',
                    'Buyer',
                    'Fungsi Pengguna',
                    'Market Intelligence Analyst',
                  ]}
                />
              </label>
            </div>
            <ErrorBox error={error} />
            <Button type="submit" className="primary-button" disabled={busy}>
              Create user
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
function SparkleIcon() {
  return <Settings2 size={20} />;
}
