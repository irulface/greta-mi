# Greta — AI Driven Market Intelligence & RFI Repository

Aplikasi web yang dibangun dari **PRD versi 1.0**, mencakup fondasi MVP (§114) dan implementasi fungsional **Phase 2 — Market Intelligence (§115)**, **Phase 3 — Advanced Intelligence (§116)**, dan **Phase 4 — Autonomous Agent (§117)**. Frontend React + TypeScript, backend FastAPI, PostgreSQL + pgvector, dan SQLite sebagai opsi development tanpa infrastruktur tambahan. Integrasi AI/enterprise live dan acceptance production masih perlu diselesaikan.

## Menjalankan secara lokal

Prasyarat: Node.js ≥22.13 dan Python 3.12 (3.11 didukung).

```bash
./scripts/setup.sh
./scripts/dev.sh
```

Buka **http://127.0.0.1:3000**. Script menjalankan migration, frontend, API, worker indexing/email/market/workflow, serta worker autonomous agent terpisah. API docs: http://127.0.0.1:8000/docs.

Mode development menyiapkan data **contoh**, dan masuk sebagai Buyer. Gunakan pemilih role untuk mencoba Buyer, Admin, Fungsi Pengguna, dan Market Intelligence Analyst. Ini khusus development; endpoint login demo **tidak tersedia** saat `APP_ENV=production`. Tidak ada password demo yang berlaku di production.

Instalasi lokal saat ini memakai PostgreSQL di `localhost:5432`, database **gretamidb**, user **gretami**, dengan pgvector aktif. Konfigurasi ada di `backend/.env` (izin file `0600`, dikecualikan dari Git). Autentikasi PostgreSQL lokal berhasil tanpa password; konfigurasi role/server tidak diubah. File dokumen dan kunci enkripsi tetap berada di `backend/data/`. Refresh browser tidak menghapus data.

Data SQLite sebelumnya sudah dimigrasikan dan diverifikasi per isi baris: 37 record, 4 pengguna, 4 chunks, 4 sesi, 7 audit event, dan 1 konfigurasi. File sumber `backend/data/greta.db` dan snapshot di `backend/data/backups/` dipertahankan. SQLite hanya menjadi fallback untuk instalasi baru yang tidak menetapkan `DATABASE_URL`; aplikasi lokal ini sudah memakai PostgreSQL.

Untuk instalasi baru, salin `backend/.env.example` menjadi `backend/.env`. Jika memindahkan instalasi SQLite lain, hentikan API/worker, aktifkan pgvector pada database target, jalankan `alembic upgrade head` dari `backend/`, kemudian `backend/.venv/bin/python scripts/migrate_sqlite_to_postgres.py` dari root. Script membuat snapshot SQLite dan menolak target yang sudah berisi data; seluruh penyalinan berlangsung dalam satu transaksi dan diverifikasi sebelum commit.

## Alur yang bisa dicoba

1. **RFI Workspace → Create RFI**: isi kebutuhan, pilih kategori, buat pertanyaan manual/template/Azure AI, tentukan supplier, dan simpan draft.
2. **Submit for review → Approved → Issue approved RFI → Open**. Validasi status dan izin dilakukan backend.
3. **Suppliers → Send email invitations**: tinjau penerima lalu konfirmasi. Worker mengirim tautan respons melalui SMTP dan menampilkan statusnya. **Generate invitation links** tetap tersedia untuk berbagi manual. Simpan draft respons, unggah lampiran, lalu submit. Link kedaluwarsa sesuai tanggal penutupan. Link baru mencabut link sebelumnya. Respons final terkunci.
4. **Responses / Comparison**: tinjau respons dan ekspor CSV. **AI analysis** memerlukan Azure yang aktif. **Open amendment** membuat versi baru, mencabut undangan, dan mempertahankan versi respons sebelumnya.
5. **Closed → Analysis → Completed → Archived**: penyelesaian otomatis menambahkan ringkasan RFI sebagai sumber di repositori.
6. **Knowledge Repository**: unggah PDF, DOCX, XLSX, PPTX, TXT, CSV, atau HTML (maks. 25 MB). Worker mengekstrak teks, membuat chunks, memeriksa SHA-256, dan membuat embeddings jika sudah dikonfigurasi. PDF hasil scan tanpa teks berstatus `OCR REQUIRED`.
7. **Ask Intelligence**: mode *Find sources* menampilkan kutipan yang benar-benar ditemukan. Mode *Azure AI analysis* menggunakan model yang dikonfigurasi, sumber terotorisasi, serta domain tools MCP jika tersedia. Hasil disimpan sebagai percakapan, disertai sumber, ekspor, dan feedback.
8. **Administration**: konfigurasi Azure/MCP, status dan tes autentikasi SMTP, versi prompt, pengguna dan role, directory scan, dan audit log. Admin tidak mendapatkan izin procurement approval otomatis.

## Email undangan RFI

SMTP lokal sudah dikonfigurasi ke **asia.emailarray.com:465**, SSL aktif, STARTTLS nonaktif, sender **admin@greta.id**, dan timeout 15 detik. Autentikasi live sudah berhasil; pengujian ini **tidak mengirim email**. Kredensial hanya tersedia di environment server dan tidak dikembalikan ke browser. Periksa melalui **Administration → Email → Test SMTP connection**.

Sebelum mengirim undangan, tetapkan `PUBLIC_APP_URL` pada `backend/.env` ke origin HTTPS aplikasi yang dapat diakses supplier, lalu restart API dan worker. Nilai ini belum diisi karena alamat publik aplikasi belum diberikan. Localhost tidak dapat digunakan untuk tautan undangan email. Untuk Docker, gunakan variabel SMTP dan `PUBLIC_APP_URL` yang sama di `.env` root; Compose meneruskannya ke API dan worker.

Pengiriman hanya dilakukan setelah Buyer memilih **Confirm and send**, untuk RFI yang sudah diterbitkan dan supplier dengan email valid. Data contoh tidak dapat dikirimi email. Isi antrean yang memuat token dienkripsi dan dibersihkan setelah diterima SMTP. Pengulangan klik tidak menduplikasi undangan yang sama. Status **Accepted by SMTP** berarti server menerima pesan, bukan bukti email sudah masuk inbox. Kegagalan terkonfirmasi dapat dicoba kembali secara eksplisit; hasil **UNKNOWN** tidak dicoba ulang otomatis. Undangan yang dicabut atau kedaluwarsa dibatalkan sebelum pengiriman. Jika worker terhenti saat `SENDING`, administrator harus memeriksa log/mailbox sebelum membuat undangan pengganti; pemulihan otomatis belum tersedia.

## Phase 2 — Market Intelligence

Lihat [panduan Phase 2](docs/PHASE-2.md) untuk price series manual/CSV/XLSX/API, tren dan regional comparison, event, supplier landscape, shared research workspace, advanced RFI analysis, alert, sourced brief, dan scheduler. Buka **Market Intelligence**. Seri Brent dari EIA sudah tersedia sebagai sumber nyata; workspace **Energy market watch** memuat chart dan brief yang dibuat worker. Jadwal brief harian disiapkan dalam status paused.

## Phase 3 — Advanced Intelligence

Buka **Advanced Intelligence** sebagai Buyer/Analyst untuk should-cost, skenario, forecast, supplier risk, rekomendasi bersumber, dan enterprise review tasks. Forecast enam periode dari 120 observasi Brent nyata sudah tersedia sebagai draft yang dibagikan ke Analyst. **Suppliers → Supplier portal access** mengelola aktivasi akun; supplier masuk di **http://127.0.0.1:3000/?portal=1**.

**Administration → External & workflows** mengatur external MCP dan tujuan workflow. Adapter dan antrean tersedia; endpoint/kredensial organisasi serta acceptance live masih diperlukan. Lihat [panduan Phase 3](docs/PHASE-3.md) untuk perhitungan, permission, batas model, dan kontrak integrasi.

## Phase 4 — Autonomous Agent

Buka **[Autonomous Agent](http://127.0.0.1:3000/#agents)** sebagai Buyer/Analyst untuk membuat monitor berkala delapan domain, meninjau perubahan sebelum/sesudah, risk signals, cakupan sumber, dan intelligence alert dalam aplikasi. Tersedia input/impor data operasional, internal MCP terkontrol, histori run, pause/cancel, sharing, dan kontrol penghentian Admin pada **Administration → Autonomous control**.

**Energy intelligence watch** sudah aktif dengan interval harian dan baseline dari Brent EIA nyata. Cakupan awal **Price 1/8**, status **PARTIAL**, risiko **UNKNOWN**: data demand/inventory/PO/supplier organisasi belum tersedia. Agent memantau data yang tersimpan; sync EIA terjadwal tetap memerlukan key organisasi. Perhitungan memakai aturan eksplisit, tidak memerlukan LLM, dan tidak melakukan transaksi procurement otomatis. Lihat [panduan Phase 4](docs/PHASE-4.md) untuk policy, kontrak MCP, akses, dan operasional worker.

## Integrasi Azure OpenAI

Gunakan **Admin → Azure OpenAI**: endpoint resource Azure, API key, deployment reasoning, deployment embedding, timeout, token limit, dan enable. Simpan, kemudian **Test saved connection**.

Kredensial dienkripsi menggunakan Fernet sebelum disimpan. `APP_MASTER_KEY` harus berasal dari environment production. API tidak mengembalikan secret ke browser. Deployment model tidak di-hardcode. Implementasi menggunakan Azure OpenAI REST v1, sesuai [referensi resmi Microsoft](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat).

Tanpa kredensial, aplikasi tidak membuat jawaban AI atau embeddings palsu. Pencarian kata kunci tetap berfungsi. Koneksi Azure live belum diverifikasi karena kredensial belum diberikan.

## Integrasi internal MCP

Daftarkan hostname gateway pada `MCP_ALLOWED_HOSTS` (comma-separated), kemudian atur HTTPS endpoint dan token melalui Admin. Client menggunakan MCP Streamable HTTP: initialization, session header, initialized notification, dan `tools/call`. Mendukung respons JSON dan SSE untuk hasil tool.

Tools yang diizinkan: `get_demand_history`, `get_inventory_position`, `get_po_history`, `get_supplier_spend`, `get_lead_time_history`, `get_open_purchase_orders`. Parameter `user_id` dan `region` ditetapkan backend; permintaan lintas region dan tool SQL generik ditolak. Gateway harus memverifikasi identity yang dikirim aplikasi tepercaya dan menerapkan row authorization pada database enterprise. Tidak ada write-back ERP.

MCP nyata belum dikoneksikan. Data demand/PO/inventory tidak disimulasikan sebagai hasil enterprise yang asli.

## Production VPS — mi.greta.id

Source deployment: [irulface/greta-mi](https://github.com/irulface/greta-mi). Jalankan dari root project:

```bash
./scripts/deploy-production.sh --dry-run
./scripts/deploy-production.sh --repo irulface/greta-mi
```

Script memeriksa source/history, commit dan push ke GitHub, kemudian meminta host/user/password SSH VPS serta kredensial admin/database/SMTP saat instalasi pertama. VPS mengambil commit GitHub yang sama, memasang Docker Compose bila diperlukan, membuat backup sebelum update, menjalankan migrasi, dan memverifikasi HTTPS production. `.env`, data lokal, backup, dan kredensial tidak diunggah ke GitHub. Repo yang ditetapkan saat ini publik; visibility repo yang sudah ada dipertahankan.

Lihat [panduan deployment](docs/DEPLOYMENT.md) untuk DNS, persyaratan Ubuntu, SSH key, repo privat, pengoperasian service, backup, serta pemulihan kegagalan. Paket ini menyiapkan instalasi production baru; data localhost tidak dipindahkan otomatis. Workflow GitHub memeriksa container tanpa melakukan deployment VPS.

## Ubuntu / PostgreSQL

`compose.yaml` menyediakan PostgreSQL 16 + pgvector, API Python 3.12, worker indexing/workflow, worker autonomous agent, dan frontend NGINX. Sediakan environment di `.env` root (jangan commit):

```dotenv
POSTGRES_PASSWORD=<password kuat, URL-safe>
APP_MASTER_KEY=<Fernet key>
BOOTSTRAP_ADMIN_EMAIL=admin@perusahaan.co.id
BOOTSTRAP_ADMIN_PASSWORD=<minimal 14 karakter>
MCP_ALLOWED_HOSTS=mcp.perusahaan.co.id
```

Generate master key dengan interpreter backend:

```bash
backend/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
docker compose up --build -d
```

Web di-bind ke `127.0.0.1:8080`, untuk ditempatkan di belakang reverse proxy HTTPS perusahaan. Production memakai cookie `Secure`, sehingga login melalui HTTPS diperlukan. Set `Host` asli saat reverse proxy; proteksi origin membandingkan origin dan host. Account Admin pertama dibuat dari bootstrap environment; data contoh tidak dibuat di production. Setelah user pertama dibuat, bootstrap password tidak mengubah akun yang sudah ada.

Migration Alembic `0001` membuat schema, full-text GIN index, dan HNSW vector index (default 1536 dimensi); `0002` menambahkan email outbox; `0003` menambahkan market observations dan automation runs; `0004` menambahkan supplier accounts/sessions dan workflow delivery queue; `0005` menambahkan durable agent runs dan evidence snapshots. Sesuaikan `EMBEDDING_DIMENSIONS` dengan embedding deployment. Production menolak SQLite. DBA perlu mengaktifkan `CREATE EXTENSION IF NOT EXISTS vector` sebelum migration jika role aplikasi tidak berhak memasang extension; aplikasi tidak memerlukan superuser.

Deployment native tanpa container juga dapat menggunakan unit systemd di `deploy/`. Sesuaikan user, working directory, dan environment; gunakan `alembic upgrade head` sebelum menjalankan API. Frontend hasil static export berada di `dist/client/`.

Backup perlu mencakup database, volume `app_data` (dokumen), dan master encryption key secara terpisah. Jangan menghapus master key karena secret konfigurasi tidak dapat didekripsi tanpanya. Jalankan satu worker indexing dan satu worker agent pada instalasi awal; klaim antrean memakai row lock pada PostgreSQL.

## Verifikasi

```bash
cd backend
.venv/bin/python -m pytest -q tests
cd ..
npx tsc --noEmit
npm run build
```

Tes mencakup lifecycle RFI, negative authorization, scope retrieval, immutable submission, attachment, amendment, conditional question, template version, encrypted secret, path guard, deduplikasi, SMTP SSL/STARTTLS, antrean idempotent, pembatalan, dan retry. Tes menggunakan database terisolasi serta SMTP/HTTP mock. PostgreSQL lokal beserta migration dan index sudah diuji; Docker/Ubuntu, Azure live, dan MCP enterprise masih memerlukan acceptance test. Browser visual/interaction QA belum dilakukan. 90 tes PostgreSQL lulus; 84 SQLite lulus dan enam tes khusus PostgreSQL di-skip. Jalankan `backend/.venv/bin/python scripts/test-postgres.py` dari root untuk migrasi penuh dan seluruh tes pada database PostgreSQL sementara.

## Batas implementasi saat ini

Lihat [cakupan PRD dan pekerjaan lanjutan](docs/PRD-COVERAGE.md). Fondasi MVP dan fitur Phase 2–4 dapat dijalankan lokal; seluruh persyaratan enterprise belum lulus acceptance. SSO/OIDC, streaming AI, document indexing scheduler/watcher, OCR, dan benchmark transaksi enterprise live masih terbuka. Scheduler Phase 2 sudah menangani market brief, market API sync dan alert. SMTP memerlukan URL aplikasi publik untuk undangan supplier. Phase 3 memerlukan kalibrasi model, UAT dan acceptance external MCP/workflow dengan endpoint organisasi. Phase 4 sudah menjalankan evaluasi berkala dan alert berbukti; pemantauan enterprise lengkap masih memerlukan sumber operasional organisasi, acceptance MCP, serta kalibrasi policy.
