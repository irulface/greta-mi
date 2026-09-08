# Phase 3 — Advanced Intelligence

Implementasi fungsional lokal untuk delapan area §116 PRD tersedia. Aplikasi tetap memakai PostgreSQL `gretamidb` dengan role `gretami`. Konektor external MCP dan workflow enterprise mempunyai kontrak, konfigurasi, UI, dan pengujian mock; penerimaan oleh sistem organisasi belum dapat dinyatakan selesai tanpa endpoint dan kredensial tujuan.

## Fitur dan alur penggunaan

| Area PRD | Implementasi | Lokasi |
|---|---|---|
| Supplier Portal | Akun perusahaan, aktivasi sekali pakai 48 jam, password, sesi terpisah, profil, kuesioner 12 tipe, draft/final, attachment, klarifikasi privat, histori amendment | Buyer → Suppliers → Supplier portal access; supplier membuka `/?portal=1` |
| Should-cost modeling | Komponen bahan baku/labor/energy/logistics/other, quantity × rate × FX, margin markup/gross margin, kategori/output unit, basis sumber, tanggal asumsi, revisi immutable | Advanced Intelligence → Should-cost |
| Price forecasting | Cutoff observasi, naïve/drift/seasonal-naïve, rolling-origin backtest, MAE/RMSE, interval prediksi 80/95%, chart, histori tersimpan, indikator data lama | Advanced Intelligence → Forecasting |
| Advanced supplier risk | Lima faktor berbobot, bukti dan rationale per faktor, coverage, expiry, score sementara untuk data tidak lengkap, approval Analyst | Advanced Intelligence → Supplier risk |
| Scenario analysis | Shock per komponen, FX, margin, volume, perbandingan baseline/budget, sensitivitas ±10% | Advanced Intelligence → Scenarios |
| Procurement recommendation engine | Aturan deterministik berdasarkan forecast/scenario/risk, sumber setiap action, gap data, status draft, review Buyer | Advanced Intelligence → Recommendations |
| External MCP | Streamable HTTP, initialize/tool discovery/call, tool read-only allowlist, schema parameter, snapshot bukti eksternal, sharing | Admin → External & workflows; Buyer/Analyst → External & workflow |
| Enterprise workflow integrations | Paket review task, preview payload, approval Buyer, antrean persisten, idempotency key, receipt, status ambiguity dan rekonsiliasi | Advanced Intelligence → External & workflow |

### Supplier Portal

1. Buyer memilih supplier dan kontak pada **Suppliers → Supplier portal access**, lalu **Create activation link**. Link ditampilkan sekali; kredensial disimpan sebagai hash. Akun supplier tidak mempunyai role internal atau akses login demo.
2. Supplier membuka link, menetapkan password minimum 12 karakter, lalu login. Sesi supplier memakai cookie HTTP-only tersendiri. Profil capabilities/certifications ditandai **supplier-reported**; nama perusahaan/master classification tetap dikelola internal.
3. Buyer menerbitkan RFI dan membuat undangan melalui alur RFI yang sudah ada. Hanya perusahaan yang diundang dapat membuka questionnaire. Satu akun dapat melihat seluruh undangan untuk perusahaannya; perusahaan lain tidak dapat melihat respons atau attachment tersebut.
4. Supplier menyimpan draft, mengunggah attachment, lalu submit final. Final terkunci dan amendment mempertahankan versi sebelumnya. Riwayat memuat teks pertanyaan serta lampiran yang sesuai versinya.
5. Supplier mengajukan klarifikasi melalui portal. Buyer menjawab di **Suppliers → Supplier clarifications**; percakapan hanya terlihat bagi perusahaan terkait dan Buyer berwenang.
6. Buyer dapat menonaktifkan akun atau mereset password; sesi sebelumnya dicabut. Activation/reset link tidak dikirim melalui email otomatis. URL publik HTTPS masih diperlukan agar supplier di luar komputer lokal dapat mengakses aplikasi.

### Model biaya dan skenario

- Satu model menghitung biaya untuk **satu output unit** yang ditetapkan pengguna. Quantity adalah input yang diperlukan per output unit, bukan volume pengadaan.
- FX = jumlah target currency untuk 1 source currency. Mata uang yang sama harus memakai FX 1. Tidak ada konversi unit atau kurs pasar implisit.
- `component_cost = quantity × rate × FX`; `subtotal = Σcomponent_cost`.
- Markup: `total = subtotal × (1 + margin_pct/100)`.
- Gross margin: `total = subtotal ÷ (1 − margin_pct/100)`.
- Skenario menerapkan persentase perubahan bucket dan FX secara multiplikatif; perubahan FX hanya mengenai komponen berdenominasi asing. Volume hanya mengalikan budget, tidak mengubah unit cost.
- Sensitivitas ±10% mengubah satu bucket terhadap model baseline pada satu waktu.
- Perhitungan komponen menggunakan Decimal; snapshot output menyimpan enam desimal. Model tidak melengkapi pajak, overhead, conversion loss, atau freight yang belum diinput. Gunakan komponen `other` dan jelaskan basisnya bila diperlukan.
- Revisi menyimpan record baru yang merujuk model sebelumnya. Skenario tetap merujuk versi baseline yang dipilih.

### Forecast dan batas statistik

Implementasi mengikuti [benchmark methods](https://otexts.com/fpp3/simple-methods.html), [rolling-origin validation](https://otexts.com/fpp3/tscv.html), dan [prediction intervals](https://otexts.com/fpp3/prediction-intervals.html) dari *Forecasting: Principles and Practice* oleh Hyndman dan Athanasopoulos.

- Minimum 18 observasi reguler, horizon 1–24 periode. Daily berarti hari kalender berturut-turut, weekly selisih tujuh hari; monthly/quarterly memerlukan bulan berturut-turut sesuai frekuensi. Data hilang/duplikat periode ditolak, tidak diimputasi diam-diam. Seri trading-day/irregular perlu dipersiapkan sebelum forecasting.
- Metode naïve dan drift selalu dibandingkan. Seasonal naïve tersedia bila cukup data untuk dua musim dan enam observasi validasi; periode musiman 12/4/7/52 untuk monthly/quarterly/daily/weekly.
- Expanding-window backtest memakai paling banyak 24 origin terakhir. Masing-masing memprediksi hingga horizon pilihan sepanjang actual sudah tersedia. Model dipilih dengan MAE terendah; RMSE dan jumlah origin/evaluasi ditampilkan. Data sesudah origin tidak masuk training pada origin tersebut.
- Interval 80/95% memakai normal residual approximation dan simpangan sesuai horizon untuk baseline terpilih. Interval mengasumsikan residual tidak berkorelasi, belum mencakup ketidakpastian pemilihan model, dan tidak menjamin coverage empiris.
- Backtesting tersebut digunakan untuk pemilihan model; belum merupakan final holdout independen. Model masih baseline statistik, belum ARIMA/ML/causal forecast ataupun kalibrasi produksi per komoditas.
- Cutoff membatasi **tanggal observasi**, bukan vintage publikasi. Koreksi historis dan tanggal rilis sumber belum mempunyai penyimpanan vintage tersendiri; hasil bukan simulasi informasi yang pasti tersedia pada masa lampau.
- Prediksi dapat negatif; aplikasi tidak mengubah distribusi dengan clipping. Seri dan confidence sumber tetap disertakan. Data demo/lama tidak menghasilkan action procurement berdasarkan forecast.

Forecast nyata yang sudah disimpan: **Brent crude — EIA monthly — forecast**, Buyer-owned, **DRAFT**, 120 observasi training, enam periode mendatang. Hasil pemilihan model: naïve. Analyst mendapat read access. Tidak dibuat model biaya atau penilaian supplier dengan angka organisasi yang belum diberikan.

### Risiko dan rekomendasi

Faktor risiko: financial 25%, delivery 25%, quality 20%, geopolitical 15%, concentration 15%. Score 0–100 berarti makin tinggi makin berisiko; LOW <40, MEDIUM 40–<70, HIGH ≥70. Angka ini adalah kebijakan awal aplikasi, belum model risiko organisasi yang dikalibrasi.

Faktor tanpa score, sumber, atau tanggal bukti yang masih berlaku dikecualikan dari coverage. Score parsial memakai bobot faktor yang tersedia tetapi rating menjadi **INCOMPLETE**, bukan low risk. Analyst meninjau dan menyetujui bukti; keberadaan ID sumber saja tidak membuktikan bahwa rationale benar. Validity default 90 hari dapat diatur 1–365 hari.

Rekomendasi menggunakan aturan yang transparan, bukan hasil LLM terselubung. Forecast membandingkan rentang 80% dengan harga observasi terakhir; skenario menyoroti perubahan budget; risiko tinggi yang lengkap, masih berlaku, dan disetujui Analyst menghasilkan opsi mitigasi. Data yang tidak memadai menjadi gap. Data contoh ditandai dan tidak menjadi action procurement live. Tidak ada supplier award, PO otomatis, atau keputusan pembelian tanpa pengguna.

### External MCP dan workflow enterprise

Tetapkan `ENTERPRISE_ALLOWED_HOSTS` untuk API **dan worker**, lalu simpan endpoint dan Bearer token di Admin. Compose sudah meneruskan variabel tersebut. Token dienkripsi dengan kunci aplikasi; tidak dikembalikan ke browser.

External adapter mendukung MCP **2025-06-18**, sesuai [lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle) dan [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports). Adapter mengirim initialize/initialized, tools/list, lalu tools/call; JSON dan SSE diterima. Discovery saat ini membaca halaman pertama tools/list; jika provider memakai pagination, tool yang dipakai perlu tersedia di halaman tersebut. Protocol version lain, OAuth flow, server sampling, resources/prompts, dan session resumption belum didukung. Tool harus disetujui Admin serta mempunyai `readOnlyHint: true`; annotation bukan jaminan independen bahwa provider tidak punya efek samping.

Allowlist tool menggunakan JSON berikut (contoh kontrak, bukan koneksi yang sudah diaktifkan):

```json
[{"name":"search_market","description":"Read public benchmark evidence","parameters":{"query":"string"},"required":["query"]}]
```

Hanya parameter eksplisit bertipe string/number/boolean yang dikirim. Region, supplier master, dokumen, dan conversation internal tidak disertakan otomatis. Endpoint wajib HTTPS port 443, host allowlisted, tanpa credential/query/fragment; redirect ditolak. DNS harus menghasilkan IP publik, kemudian koneksi dipin ke IP tervalidasi dengan TLS hostname asli. Maksimum respons 2 MB, timeout 25 detik. Konten tersimpan sebagai bukti eksternal dan tidak dieksekusi sebagai instruksi.

Workflow memakai adapter HTTP **CREATE_REVIEW_TASK**, yang dapat dipetakan ke sistem organisasi oleh gateway penerima. Ini belum native SAP/ServiceNow connector. Paket memuat judul, justification, kategori, action/gap, dan referensi sumber dari rekomendasi yang sudah disetujui; pengguna melihat JSON persis sebelum approval eksternal. Attachment dan teks dokumen tidak dikirim otomatis.

Penerima harus menghormati `Idempotency-Key: <request_id>` dan mengembalikan HTTP 200/201/202 dengan:

```json
{"request_id":"<request_id dari paket>","accepted":true,"receipt_id":"<ID task di sistem penerima>"}
```

Antrean hanya dibuat lewat tombol **Send approved review task** milik Buyer. Worker memeriksa hak akses, approval dan versi konektor lagi. Duplikasi klik atau request bersamaan mengembalikan delivery yang sama. **ACKNOWLEDGED** berarti penerima mengakui review task, bukan procurement selesai. Timeout, receipt tidak valid, HTTP ambigu, atau worker terhenti menjadi **UNKNOWN**; tidak ada retry otomatis. Buyer harus memeriksa penerima lalu merekam receipt/evidence melalui rekonsiliasi. Perubahan konektor setelah antrean dibuat menghasilkan **BLOCKED**. Kontrak idempotency penerima dan mapping field tetap memerlukan integration acceptance.

## Akses, migrasi, dan validasi

- Analisis bersifat privat, dapat dibagikan read-only ke Buyer/Analyst aktif dalam region sama. Semua sumber upstream diperiksa lagi ketika dibaca. Sharing tidak membuka dokumen RESTRICTED. External evidence mempunyai sharing tersendiri agar dapat direview bersama.
- Migration `0004` menambahkan `supplier_accounts`, `supplier_sessions`, dan `workflow_deliveries`. Domain analytical snapshots tetap memakai `records` JSON.
- Snapshot sebelum migrasi: `backend/data/backups/greta-before-phase3-20260908T044132Z.dump`, mode `0600`. Data RFI, supplier, dokumen dan konfigurasi sebelumnya dipertahankan.
- 66 tes PostgreSQL lulus; 61 SQLite lulus dan lima tes konkurensi PostgreSQL di-skip. Migrasi penuh dijalankan pada database pengujian terpisah yang dihapus sesudah tes. `backend/.venv/bin/python scripts/test-postgres.py` mengulangi tes lokal PostgreSQL tanpa memakai `gretamidb`.
- TypeScript, lint empat komponen baru, dan build production lulus. Temuan lint baseline pada modul lama belum ditutup. Pemeriksaan HTTP melalui frontend port 3000 mencakup login, forecast nyata, sharing Analyst, isolasi portal, dan endpoint enterprise. Tidak ada email atau workflow eksternal nyata dikirim.
- UAT/browser visual QA, security/load testing, shared rate limiting, supplier MFA/SSO/password recovery mandiri, file malware scanning, kalibrasi model dan integration live masih terbuka. Build masih memperingatkan ukuran bundle. Phase 4 kemudian ditambahkan; lihat [PHASE-4.md](PHASE-4.md) untuk status terbaru.
