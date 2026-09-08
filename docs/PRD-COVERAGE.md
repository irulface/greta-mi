# Cakupan PRD v1.0

## Implementasi fungsional

| Domain | Cakupan |
|---|---|
| Authentication | Login password, scrypt hash, session HTTP-only 8 jam, logout/revoke; demo role switching hanya development |
| Authorization | 4 role, permission server-side, region scope, document classification, requester hanya RFI miliknya; negative tests |
| Dashboard | Angka dihitung dari data tersimpan; market signals dan harga contoh dilabeli demo |
| Global search | RFI, supplier, kategori, harga, event, dokumen dalam scope pengguna |
| Category taxonomy | Hierarki group → category → subcategory → commodity; halaman kategori, historical RFI, supplier |
| Supplier | Direktori, filter, profil, pembuatan supplier, kapabilitas, riwayat RFI; kinerja contoh dilabeli |
| RFI | Draft/manual, template tersimpan dan versioned, clone, AI questions, supplier selection, lifecycle, questionnaire locking, amendment |
| Questions | 12 tipe; validasi numerik/tanggal/pilihan, kondisi pada jawaban pertanyaan sebelumnya; tabel sebagai baris teks/CSV |
| Invitations | Token acak kriptografis, hash pada record undangan, expiry/revoke; berbagi manual atau SMTP setelah konfirmasi Buyer; antrean terenkripsi, status, retry eksplisit |
| Responses | Save draft, submit, immutable, attachment access control, amendment mempertahankan histori |
| Analysis | Matrix per pertanyaan, ekspor CSV, clarification status, aktivitas, AI comparison bersumber |
| Repository | Upload 7 format, filesystem storage, text parsing, metadata dasar, chunking, SHA-256 dedup, file versions, OCR REQUIRED |
| Indexing | Antrean durable, worker terpisah, manual recursive scan, allowlisted directory root, per-file failure status |
| Search | Lexical; PostgreSQL full text GIN dan pgvector similarity; Azure embeddings; metadata category/year/format filter |
| RAG / AI | Sumber terotorisasi, Azure REST v1, evidence citations, prompt version, saved conversations, export, feedback, per-run audit |
| MCP | Streamable HTTP client, approved read tools, identity/region parameters, disallowed tool/parameter rejection, call audit, planner→calls→synthesis |
| Admin | Azure encrypted config, test connection, MCP config, status/tes autentikasi SMTP, prompt versions, create/list/update user API, indexing jobs, audit log |
| Analytics | RFI distribution, response rate, suppliers, category and repository coverage, CSV export |
| Phase 2 market data | Manual/CSV/XLSX/API observations, sourced metadata, corrections, date-based indicators, interactive charts, compatible regional comparison |
| Phase 2 research | Analyst landscape approval, complete event fields, shared workspaces, saved views, evidence/AI RFI analysis, reviewed/shared briefs with citations |
| Phase 2 automation | Personal alert rules, notifications, EIA/allowlisted JSON connectors, encrypted credentials, durable schedules and run history |
| Phase 3 decision support | Should-cost and immutable revisions, cost/FX scenarios and sensitivity, backtested baseline forecasts, evidence-weighted supplier risk, reviewed procurement recommendations |
| Phase 3 external access | Isolated supplier accounts/profile/questionnaire/files/clarification/history; read-only external MCP adapter; approved review-task delivery, receipts and reconciliation |
| Phase 4 autonomous monitoring | Scheduled eight-domain evidence agent, what-changed snapshots, explicit risk rules, typed operational/MCP inputs, in-app alerts, review/sharing, cancellation and Admin stop, durable separate worker |
| Deployment | Docker Compose, Python 3.12 image, PostgreSQL + pgvector, Alembic migration, NGINX, systemd examples, local runner |

## Memerlukan konfigurasi dan acceptance integration

- Azure resource endpoint, API credential, model deployment, embedding deployment.
- MCP enterprise gateway dengan tool/schema yang cocok dan enforcement row scope pada sumber.
- PostgreSQL lokal + pgvector sudah terhubung, migration dan indeks sudah diuji, serta data SQLite dimigrasikan dengan snapshot. Backup terjadwal dan recovery production tetap perlu acceptance.
- URL HTTPS aplikasi publik untuk tautan supplier. SMTP SSL sudah terautentikasi; belum ada pengujian pengiriman ke mailbox nyata.
- HTTPS dan reverse proxy untuk session production.
- Dokumen historis asli, taxonomy organisasi, supplier master, dan pengguna production.

## Belum lengkap terhadap baseline enterprise

- Microsoft Entra/OIDC SSO dan refresh session terkontrol; login lokal saat ini sebagai initial authentication.
- Bounce/delivery tracking SMTP dan pemulihan worker yang terhenti saat mengirim; penerimaan SMTP belum membuktikan delivery inbox.
- Streaming token AI, fallback model routing, cancellation, caching, dan evaluasi golden dataset.
- AI metadata entity extraction dengan confidence per field; saat ini text parsing + metadata dasar dan status analyst review.
- Scheduler/watcher, failed-job retries, interrupted-job recovery, parser sandbox per file, incremental deletion tombstones, OCR.
- Evidence citation validation otomatis per klaim; respons LLM tetap memerlukan analyst review.
- Supplier editing UI belum lengkap; taxonomy create, user role/status management, dan create supplier sudah tersedia.
- Full relational domain schema PRD: domain masih memakai `records` JSON; users/sessions/chunks/config/audit/email_outbox/market_points/market_runs/supplier_accounts/supplier_sessions/workflow_deliveries/agent_runs mempunyai tabel khusus. Normalisasi domain lainnya diperlukan saat reporting/scale bertambah.
- 100k+ dokumen, jutaan chunks, load test, HA, disaster recovery, observability terpusat, rate limiter terdistribusi, malware scanning, penetration test.
- Akses attachment requester dibatasi; berbagi percakapan lintas pengguna dan granular role customization belum tersedia.
- Field tabel questionnaire belum memiliki spreadsheet editor; input berupa baris teks/CSV.

## Phase 2

Implementasi fungsional lokal tersedia untuk seluruh area §115: price series, events, supplier landscape, research workspace, advanced RFI analysis, alert engine, external API, automated brief, dan advanced dashboards. EIA live sudah menyimpan 120 observasi Brent; worker menghasilkan sourced brief. Rincian, formula, alur, dan batas ada di [PHASE-2.md](PHASE-2.md). Azure AI/MCP live, key EIA organisasi untuk sync terjadwal, dan UAT tetap belum ditutup.

## Phase 3

Implementasi lokal untuk delapan area §116 tersedia. Portal supplier dan analisis dapat dijalankan; forecasting memakai baseline statistik dengan backtesting, risk memakai kebijakan bobot awal, dan rekomendasi memakai aturan deterministik. External MCP dan workflow mempunyai adapter/kontrak yang diuji mock, belum acceptance dengan sistem organisasi. Lihat [PHASE-3.md](PHASE-3.md) untuk alur, batas, dan konfigurasi.

## Phase 4

Implementasi lokal §117 tersedia: evaluasi periodik delapan domain, baseline dan perubahan berbukti, risk signals dengan ambang eksplisit, intelligence alert in-app, histori, sharing, cancel/pause/Admin stop, dan worker terpisah. **Energy intelligence watch** aktif harian dengan Brent nyata, cakupan Price 1/8 dan status PARTIAL; sumber enterprise operasional masih diperlukan. Agent memakai aturan deterministik terbatas, bukan autonomous procurement decision atau planner LLM bebas. Lihat [PHASE-4.md](PHASE-4.md).

## Catatan verifikasi

90 tes PostgreSQL lulus; 84 tes SQLite lulus dengan enam tes concurrency PostgreSQL di-skip. EIA live, impor 120 observasi, dan brief melalui worker sudah diverifikasi. Azure/MCP/SMTP delivery memakai mock; autentikasi SMTP live pernah diverifikasi tanpa mengirim email. Aplikasi memakai `gretamidb` dengan user `gretami`. Rincian ada di [VALIDATION.md](VALIDATION.md).
