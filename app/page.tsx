'use client';
import { useState, useEffect } from 'react';
import {
  Row,
  Workspace,
  api,
  Picker,
  ErrorBox,
  Busy,
  emptyWorkspace,
} from '@/components/greta/shared';
import {
  CreateRFI,
  RFIList,
  RFIDetail,
  SupplierResponse,
} from '@/components/greta/rfi';
import {
  Repository,
  AskIntelligence,
  Suppliers,
  Analytics,
} from '@/components/greta/intelligence';
import { GlobalSearch } from '@/components/greta/global-search';
import { Administration } from '@/components/greta/admin';
import {
  SupplierPortal,
  SupplierPortalAdmin,
} from '@/components/greta/supplier-portal';
import { AdvancedIntelligence } from '@/components/greta/advanced-intelligence';
import { AutonomousIntelligence } from '@/components/greta/autonomous-intelligence';
import { MarketIntelligence } from '@/components/greta/market-intelligence';
import {
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  Search,
  Bell,
  Plus,
  Layers3,
  Sparkles,
  LayoutDashboard,
  ChartNoAxesCombined,
  ClipboardList,
  Building2,
  FolderClosed,
  ChartPie,
  Settings2,
  CircleHelp,
  ChevronsUpDown,
  Clock3,
  Globe2,
  Activity,
} from 'lucide-react';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';

const nav = [
  { id: 'home', name: 'Overview', icon: LayoutDashboard },
  { id: 'ask', name: 'Ask Intelligence', icon: Sparkles },
  { id: 'market', name: 'Market Intelligence', icon: ChartNoAxesCombined },
  { id: 'advanced', name: 'Advanced Intelligence', icon: Activity },
  { id: 'agents', name: 'Autonomous Agent', icon: Globe2 },
  { id: 'rfi', name: 'RFI Workspace', icon: ClipboardList },
  { id: 'suppliers', name: 'Suppliers', icon: Building2 },
  { id: 'repository', name: 'Knowledge Repository', icon: FolderClosed },
  { id: 'analytics', name: 'Analytics', icon: ChartPie },
];
function Badge({ children }: { children: React.ReactNode }) {
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
function Sparkline({
  red = false,
  variant = 0,
  series,
}: {
  red?: boolean;
  variant?: number;
  series?: number[];
}) {
  const lines = [
    '0,32 12,28 25,31 36,20 49,24 62,12 73,19 86,9 100,12 114,2',
    '0,4 12,12 25,9 36,15 49,11 62,25 73,20 86,28 100,25 114,36',
    '0,31 12,29 25,19 36,22 49,12 62,16 73,9 86,12 100,3 114,6',
  ];
  const values = series?.filter(Number.isFinite);
  const actual =
    values && values.length > 1
      ? values
          .map(
            (value, i) =>
              `${(i * 114) / (values.length - 1)},${38 - ((value - Math.min(...values)) / (Math.max(...values) - Math.min(...values) || 1)) * 34}`,
          )
          .join(' ')
      : null;
  if (series && !actual) return null;
  return (
    <svg viewBox="0 0 114 42" className="sparkline" aria-hidden="true">
      <polyline
        points={actual || lines[variant]}
        fill="none"
        stroke={red ? '#c26946' : '#36796b'}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
export default function Home() {
  const [page, setPageState] = useState('home');
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [repoQuery, setRepoQuery] = useState('');
  const [modal, setModal] = useState(false);
  const [data, setData] = useState<Workspace>(emptyWorkspace);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedRFI, setSelectedRFI] = useState<string | null>(null);
  const [editRFI, setEditRFI] = useState<Row | null>(null);
  const [help, setHelp] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [marketAlerts, setMarketAlerts] = useState<Row[]>([]);
  const [agentAlerts, setAgentAlerts] = useState<Row[]>([]);
  const [initialAgent, setInitialAgent] = useState('');
  const [marketInitialTab, setMarketInitialTab] = useState('overview');
  const [login, setLogin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [invitation, setInvitation] = useState('');
  const [portal, setPortal] = useState(false);
  const setPage = (p: string) => {
    setPageState(p);
    setSelectedRFI(null);
    if (typeof window !== 'undefined') history.replaceState(null, '', '#' + p);
  };
  const refresh = async () => {
    setData(await api('/workspace'));
    setMarketAlerts(await api('/market/alerts'));
    setAgentAlerts(await api('/agents/inbox/alerts').catch(() => []));
  };
  useEffect(() => {
    if (new URLSearchParams(location.search).has('portal')) {
      setPortal(true);
      setLoading(false);
      return;
    }
    const inv = new URLSearchParams(location.search).get('invitation');
    if (inv) {
      setInvitation(inv);
      setLoading(false);
      return;
    }
    const hash = location.hash.slice(1);
    if (
      [
        'home',
        'ask',
        'market',
        'advanced',
        'agents',
        'rfi',
        'suppliers',
        'repository',
        'analytics',
        'admin',
      ].includes(hash)
    )
      setPageState(hash);
    void (async () => {
      try {
        const setup = await api('/bootstrap');
        try {
          await api('/auth/me');
        } catch {
          if (setup.demo) await api('/auth/demo', { role: 'Buyer' });
          else {
            setLogin(true);
            return;
          }
        }
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  useEffect(() => {
    if (loading || login || invitation || portal) return;
    const timer = setInterval(
      () =>
        api('/market/alerts')
          .then(async (rows) => {
            setMarketAlerts(rows);
            setAgentAlerts(await api('/agents/inbox/alerts').catch(() => []));
          })
          .catch(() => {}),
      60000,
    );
    return () => clearInterval(timer);
  }, [loading, login, invitation, portal, data.user.id]);
  async function switchRole(role: string) {
    try {
      await api('/auth/demo', { role });
      await refresh();
      setPage(role === 'Admin' ? 'admin' : 'home');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const openRFI = (id: string) => {
    setPage('rfi');
    setSelectedRFI(id);
  };
  const openAsk = (q: string) => {
    setQuery(q);
    setPage('ask');
  };
  const rfis: Row[] = data.rfis
    .filter((r) => !['Completed', 'Archived', 'Cancelled'].includes(r.status))
    .slice(0, 4)
    .map((r) => ({
      ...r,
      id: r.id,
      reference: r.number,
      category: data.categories.find((c) => c.id === r.category_id)?.name,
      response: data.responses.filter((x) => x.rfi_id === r.id && x.submitted)
        .length,
      total: r.supplier_ids.length,
      due: new Date(r.closing_date + 'T12:00:00').toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }),
    }));
  const invitations = data.rfis.reduce((n, r) => n + r.supplier_ids.length, 0);
  const responseRate = invitations
    ? (data.responses.length / invitations) * 100
    : 0;
  if (portal) return <SupplierPortal />;
  if (invitation) return <SupplierResponse token={invitation} />;
  if (login)
    return (
      <main className="login-page">
        <div className="login-brand">
          <Layers3 />
          greta
        </div>
        <h1>Welcome to your intelligence workspace.</h1>
        <p>Sign in with your organization account.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            try {
              await api('/auth/login', { email, password });
              await refresh();
              setLogin(false);
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          <label>
            Email
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <Input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          <ErrorBox error={error} />
          <Button type="submit" className="primary-button">
            Sign in
            <ArrowRight size={16} />
          </Button>
        </form>
      </main>
    );
  return (
    <SidebarProvider
      style={{ '--sidebar-width': '244px' } as React.CSSProperties}
    >
      <Sidebar className="app-sidebar">
        <SidebarHeader className="brand">
          <div className="brand-mark">
            <Layers3 size={23} />
          </div>
          <div>
            greta<span>MARKET INTELLIGENCE</span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <div className="workspace-picker">
            <span className="workspace-icon">G</span>
            <div>
              Procurement workspace<small>Enterprise</small>
            </div>
            <ChevronsUpDown size={14} />
          </div>
          <div className="nav-label">WORKSPACE</div>
          <SidebarMenu className="navigation">
            {nav
              .filter(
                (n) =>
                  (n.id !== 'rfi' ||
                    data.user.permissions.includes('rfi:read')) &&
                  (!['advanced', 'agents'].includes(n.id) ||
                    data.user.permissions.includes('procurement')),
              )
              .map((n) => (
                <SidebarMenuItem key={n.id}>
                  <SidebarMenuButton
                    isActive={page === n.id}
                    onClick={() => setPage(n.id)}
                    className="nav-button"
                  >
                    <n.icon size={18} />
                    <span>{n.name}</span>
                    {n.id === 'rfi' && (
                      <span className="nav-count">{rfis.length}</span>
                    )}
                    {n.id === 'ask' && <span className="ai-dot" />}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
          </SidebarMenu>
          <div className="nav-label second">PINNED WORKSPACE</div>
          <button className="pinned" onClick={() => setPage('market')}>
            <span className="pin-dot" />
            2027 OCTG Market Outlook
            <ArrowUpRight size={14} />
          </button>
        </SidebarContent>
        <SidebarFooter className="sidebar-bottom">
          {data.user.role === 'Admin' && (
            <button onClick={() => setPage('admin')}>
              <Settings2 size={18} />
              Administration
            </button>
          )}
          <button onClick={() => setHelp(true)}>
            <CircleHelp size={18} />
            Help & resources
            <ArrowUpRight size={14} />
          </button>
          <div className="user-row">
            <span className="avatar">AP</span>
            <div>
              {data.user.name}
              <small>
                {data.user.role} · {data.user.region}
              </small>
            </div>
            <ChevronsUpDown size={15} />
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <SidebarTrigger className="mobile-toggle" />
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>
              {nav.find((n) => n.id === page)?.name || 'Administration'}
            </strong>
          </div>
          <div className="top-actions">
            <button
              className="global-search"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={16} />
              Search anything...<kbd>⌘ K</kbd>
            </button>
            {data.demo && (
              <Picker
                value={data.user.role}
                onChange={switchRole}
                options={[
                  'Buyer',
                  'Admin',
                  'Fungsi Pengguna',
                  'Market Intelligence Analyst',
                ]}
                label="Demo role"
              />
            )}
            <span className="divider" />
            <button
              className="notification"
              aria-label="Notifications"
              onClick={() => setNotifications(true)}
            >
              <Bell size={19} />
              <i />
            </button>
            <span className="avatar small">AP</span>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="live-dot" />
                YOUR INTELLIGENCE, CONNECTED
              </div>
              <h1>
                {page === 'home'
                  ? 'A clearer view. A smarter decision.'
                  : nav.find((n) => n.id === page)?.name || 'Administration'}
              </h1>
              <p>
                {page === 'home'
                  ? `Welcome back, ${data.user.name.split(' ')[0]}. Here’s what’s moving your procurement forward.`
                  : {
                      rfi: 'Manage your sourcing conversations, from requirement to insight.',
                      repository:
                        'Connect your research to the knowledge you already have.',
                      agents:
                        'Monitor changes, inspect evidence, and respond to intelligence alerts.',
                      advanced:
                        'Model costs, anticipate market changes, and prepare evidence-based decisions.',
                      market:
                        'Follow the categories, benchmarks, and events that matter.',
                      suppliers:
                        'Discover capabilities and understand your supplier network.',
                      ask: 'Research with authorized evidence and traceable sources.',
                      analytics:
                        'Understand activity and coverage across your workspace.',
                      admin:
                        'Configure the services behind your intelligence workspace.',
                    }[page]}
              </p>
            </div>
            {data.user.permissions.includes('rfi:create') && (
              <Button
                className="primary-button"
                onClick={() => {
                  setEditRFI(null);
                  setModal(true);
                }}
              >
                <Plus size={17} />
                Create RFI
              </Button>
            )}
          </div>
          <ErrorBox error={error} />
          {loading && <Busy />}
          {data.demo && (
            <div className="demo-note">
              <span className="live-dot" />
              Demo workspace
              <span>
                Development environment · Illustrative records are labeled
                individually
              </span>
            </div>
          )}
          {page === 'home' && (
            <>
              <section className="intelligence-banner">
                <div className="banner-heading">
                  <span className="intelligence-icon">
                    <Sparkles size={20} />
                  </span>
                  <div>
                    <h2>Your next decision starts with a good question.</h2>
                    <p>
                      Connect market signals, historical RFIs, and internal
                      procurement knowledge.
                    </p>
                  </div>
                  <span className="evidence-label">
                    <span />
                    Evidence-led intelligence
                  </span>
                </div>
                <form
                  className="ask-input"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setPage('ask');
                  }}
                >
                  <Sparkles size={19} />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ask anything. Try ‘Should we issue a new RFI for gas compressors?’"
                    aria-label="Ask Intelligence"
                  />
                  <button aria-label="Ask question" type="submit">
                    <ArrowRight size={20} />
                  </button>
                </form>
                <div className="suggested-queries">
                  Explore{' '}
                  <button
                    onClick={() => {
                      setQuery('Compare latest prices against historical PO');
                      setPage('ask');
                    }}
                  >
                    Compare historical prices
                    <ArrowUpRight size={12} />
                  </button>
                  <button
                    onClick={() => {
                      setQuery('Find suppliers for gas compressors');
                      setPage('ask');
                    }}
                  >
                    Find potential suppliers
                    <ArrowUpRight size={12} />
                  </button>
                  <button
                    onClick={() => {
                      setQuery('Summarize OCTG supply risks');
                      setPage('ask');
                    }}
                  >
                    Understand supply risks
                    <ArrowUpRight size={12} />
                  </button>
                </div>
              </section>
              <div className="overview-label">
                <h2>Workspace at a glance</h2>
                <span>
                  <Clock3 size={13} />
                  Current workspace records
                </span>
              </div>
              <section className="stats-grid">
                {[
                  {
                    label: 'Active RFIs',
                    value: String(
                      data.rfis.filter(
                        (r) =>
                          !['Completed', 'Archived', 'Cancelled'].includes(
                            r.status,
                          ),
                      ).length,
                    ),
                    sub: 'Draft through analysis',
                    change: 'View RFI workspace',
                    icon: ClipboardList,
                  },
                  {
                    label: 'Supplier response rate',
                    value: responseRate.toFixed(1),
                    unit: '%',
                    sub: 'Across selected supplier participations',
                    change: data.responses.length + ' submitted responses',
                    icon: Building2,
                  },
                  {
                    label: 'Monitored categories',
                    value: String(data.categories.length),
                    sub: 'Your authorized category taxonomy',
                    change: data.events.length + ' market events',
                    icon: ChartPie,
                  },
                  {
                    label: 'Knowledge documents',
                    value: String(data.documents.length),
                    sub: 'Available in your knowledge repository',
                    change:
                      data.documents.filter((d) => d.status === 'Indexed')
                        .length + ' indexed documents',
                    icon: FolderClosed,
                  },
                ].map((s, i) => (
                  <article className="stat-card" key={s.label}>
                    <div className="stat-top">
                      {s.label}
                      <s.icon size={17} />
                    </div>
                    <div className="stat-value">
                      {s.value}
                      <span>{s.unit}</span>
                      <Sparkline variant={i % 2 === 0 ? 0 : 2} />
                    </div>
                    <div className="stat-change">
                      <ArrowUpRight size={13} />
                      {s.change}
                    </div>
                    <p>{s.sub}</p>
                  </article>
                ))}
              </section>
              <div className="main-grid">
                <section className="panel active-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        RFIs that need your attention{' '}
                        <span className="count-pill">{rfis.length}</span>
                      </h2>
                      <p>Keep your sourcing conversations moving.</p>
                    </div>
                    <button
                      className="text-link"
                      onClick={() => setPage('rfi')}
                    >
                      View all RFIs
                      <ArrowRight size={15} />
                    </button>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>RFI / CATEGORY</TableHead>
                        <TableHead>STATUS</TableHead>
                        <TableHead>RESPONSES</TableHead>
                        <TableHead>CLOSING DATE</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rfis.map((r) => (
                        <TableRow
                          key={r.id}
                          className="clickable-row"
                          onClick={() => openRFI(r.id)}
                        >
                          <TableCell>
                            <small className="reference">{r.reference}</small>
                            <strong className="rfi-title">{r.title}</strong>
                            <span className="table-category">{r.category}</span>
                          </TableCell>
                          <TableCell>
                            <Badge>{r.status}</Badge>
                          </TableCell>
                          <TableCell>
                            <div className="response-value">
                              {r.response}
                              <span> / {r.total}</span>
                            </div>
                            <div className="mini-progress">
                              <span
                                style={{
                                  width: `${r.total ? (r.response / r.total) * 100 : 0}%`,
                                }}
                              />
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="due-date">{r.due}</span>
                            {r.due === '12 Sept 2026' && (
                              <small className="closing-soon">
                                Closing in 4 days
                              </small>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <div className="panel-footer">
                    <span>
                      <span className="live-dot" />
                      {rfis.length} active RFIs in your workspace
                    </span>
                    <button onClick={() => setPage('rfi')}>
                      Open RFI workspace
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </section>
                <section className="panel signals-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        <Activity size={17} />
                        Market signals
                      </h2>
                      <p>Changes worth paying attention to.</p>
                    </div>
                    <span className="count-pill">
                      {data.events.length} events
                    </span>
                  </div>
                  {data.events.map((e) => (
                    <div className="signal" key={e.id}>
                      <div className="signal-meta">
                        <span className="signal-type amber">
                          {e.type.toUpperCase()}
                        </span>
                        <span>{e.date}</span>
                      </div>
                      <h3>{e.title}</h3>
                      <p>{e.description}</p>
                      <button onClick={() => setPage('market')}>
                        {
                          data.categories.find((c) => c.id === e.category_id)
                            ?.name
                        }
                        <ArrowUpRight size={13} />
                      </button>
                    </div>
                  ))}
                  <div className="signal">
                    <div className="signal-meta">
                      <span className="signal-type blue">
                        KNOWLEDGE COVERAGE
                      </span>
                      <span>Repository</span>
                    </div>
                    <h3>{data.documents.length} sources ready to explore</h3>
                    <p>
                      Search historical RFIs, supplier responses, and indexed
                      reports.
                    </p>
                    <button onClick={() => setPage('repository')}>
                      Explore your repository
                      <ArrowUpRight size={13} />
                    </button>
                  </div>
                  <button
                    className="signal-footer"
                    onClick={() => setPage('market')}
                  >
                    Explore market intelligence
                    <ArrowRight size={15} />
                  </button>
                </section>
              </div>
              <section className="market-strip">
                <div className="strip-heading">
                  <Globe2 size={19} />
                  <div>
                    <h2>Market pulse</h2>
                    <p>Tracked benchmark indices</p>
                  </div>
                </div>
                {data.prices
                  .map((p) => ({
                    name: p.name,
                    value:
                      typeof p.value === 'number'
                        ? p.value.toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                          })
                        : '—',
                    unit: p.unit?.includes(p.currency)
                      ? p.unit
                      : [p.currency, p.unit].filter(Boolean).join(' / '),
                    series: p.series || [],
                    change:
                      typeof p.change === 'number'
                        ? (p.change > 0 ? '+' : '') + p.change + '%'
                        : 'No period comparison',
                    down: p.change < 0,
                  }))
                  .map((x, i) => (
                    <button
                      className="pulse-item"
                      key={x.name}
                      onClick={() => setPage('market')}
                    >
                      <div>
                        <span>{x.name}</span>
                        <strong>
                          {x.value}
                          <small>{x.unit}</small>
                        </strong>
                      </div>
                      <div className="pulse-right">
                        <Sparkline red={!x.down} series={x.series} />
                        <span className={x.down ? 'green-text' : 'red-text'}>
                          {x.down ? (
                            <ArrowDownRight size={13} />
                          ) : (
                            <ArrowUpRight size={13} />
                          )}{' '}
                          {x.change}
                          <small>MoM</small>
                        </span>
                      </div>
                    </button>
                  ))}
              </section>
              <footer className="page-footer">
                <span>
                  <Layers3 size={14} />
                  GRETA · FROM INFORMATION TO INTELLIGENCE
                </span>
                <span>Data first. Evidence always.</span>
              </footer>
            </>
          )}
          {page === 'rfi' &&
            (selectedRFI ? (
              <RFIDetail
                id={selectedRFI}
                data={data}
                onBack={() => setSelectedRFI(null)}
                onEdit={(r) => {
                  setEditRFI(r);
                  setModal(true);
                }}
                onRefresh={refresh}
                onOpen={openRFI}
              />
            ) : (
              <RFIList
                data={data}
                onOpen={openRFI}
                onCreate={() => setModal(true)}
              />
            ))}
          {page === 'repository' && (
            <Repository
              key={repoQuery}
              data={data}
              refresh={refresh}
              onAsk={openAsk}
              initialQuery={repoQuery}
            />
          )}
          {page === 'ask' && (
            <AskIntelligence
              data={data}
              initialQuery={query}
              onCreate={() => setModal(true)}
              onRefresh={refresh}
            />
          )}
          {page === 'suppliers' && (
            <>
              <Suppliers data={data} refresh={refresh} />
              <SupplierPortalAdmin data={data} />
            </>
          )}
          {page === 'advanced' && <AdvancedIntelligence data={data} />}
          {page === 'market' && (
            <MarketIntelligence
              initialTab={marketInitialTab}
              data={data}
              onRFI={openRFI}
              onAsk={openAsk}
              refresh={refresh}
            />
          )}
          {page === 'agents' && (
            <AutonomousIntelligence
              key={initialAgent}
              data={data}
              initialAgent={initialAgent}
              onNotifications={refresh}
            />
          )}
          {page === 'analytics' && <Analytics data={data} />}
          {page === 'admin' && (
            <Administration
              data={data}
              refresh={refresh}
              onMarket={() => {
                setMarketInitialTab('sources');
                setPage('market');
              }}
            />
          )}
        </main>
      </div>
      <CreateRFI
        data={data}
        open={modal}
        onClose={() => setModal(false)}
        initial={editRFI}
        onSaved={async (r) => {
          await refresh();
          openRFI(r.id);
        }}
      />
      <GlobalSearch
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelect={(r) => {
          if (r.kind === 'rfi') openRFI(r.id);
          else if (r.kind === 'document') {
            setRepoQuery(r.title);
            setPage('repository');
          } else if (r.kind === 'supplier') setPage('suppliers');
          else setPage('market');
        }}
      />
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent className="large-dialog">
          <DialogTitle>Your Greta workspace</DialogTitle>
          <DialogDescription>
            From research to an evidence-led sourcing decision.
          </DialogDescription>
          <div className="help-steps">
            <p>
              <strong>1. Explore intelligence</strong> Search historical
              documents, browse categories, or compare supplier capabilities.
            </p>
            <p>
              <strong>2. Create an RFI</strong> Define the requirement, add
              questions, and select suppliers. Submit for internal review before
              issuing.
            </p>
            <p>
              <strong>3. Collect responses</strong> Generate secure invitation
              links after issue. Responses are locked after submission.
            </p>
            <p>
              <strong>4. Build your knowledge</strong> Compare responses and
              complete the RFI to add its findings to the repository.
            </p>
          </div>
          <div className="info-note">
            {data.demo
              ? 'Demo mode is active. Use the role selector to explore the four internal roles.'
              : 'Access follows your role and assigned region.'}{' '}
            Azure AI and MCP require administrator configuration.
          </div>
          <Button
            variant="outline"
            onClick={async () => {
              await api('/auth/logout', {});
              setHelp(false);
              setLogin(true);
            }}
          >
            Sign out
          </Button>
        </DialogContent>
      </Dialog>
      <Dialog open={notifications} onOpenChange={setNotifications}>
        <DialogContent className="large-dialog">
          <DialogTitle>Workspace updates</DialogTitle>
          <DialogDescription>
            Your market alerts and recent events.
          </DialogDescription>
          {agentAlerts
            .filter((a) => a.status !== 'RESOLVED')
            .map((a) => (
              <button
                className="notification-item"
                key={a.id}
                onClick={() => {
                  setNotifications(false);
                  setInitialAgent(a.agent_id);
                  setPage('agents');
                }}
              >
                <Activity size={18} />
                <div>
                  <strong>{a.title}</strong>
                  <p>{a.message}</p>
                </div>
                <Badge>{a.severity}</Badge>
              </button>
            ))}
          {marketAlerts
            .filter((alert) => alert.status !== 'RESOLVED')
            .map((alert) => (
              <button
                className="notification-item"
                key={alert.id}
                onClick={() => {
                  setNotifications(false);
                  setMarketInitialTab('alerts');
                  setPage('market');
                }}
              >
                <Bell size={18} />
                <div>
                  <strong>{alert.title}</strong>
                  <p>{alert.message}</p>
                </div>
                <Badge>{alert.severity}</Badge>
              </button>
            ))}
          {data.events.map((e) => (
            <button
              className="notification-item"
              key={e.id}
              onClick={() => {
                setNotifications(false);
                setPage('market');
              }}
            >
              <Activity size={18} />
              <div>
                <strong>{e.title}</strong>
                <p>
                  {e.date} · {e.impact} impact
                </p>
              </div>
              <ArrowRight size={16} />
            </button>
          ))}
          {!data.events.length &&
            !marketAlerts.length &&
            !agentAlerts.length && <p>No updates in your workspace.</p>}
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  );
}
