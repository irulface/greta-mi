# Phase 2 — Market Intelligence

Implementasi fungsional lokal berdasarkan PRD §115 serta §9–14, §26, §82–86. Integrasi model AI live dan acceptance pengguna tetap diperlukan sebelum production.

## Cakupan

| Area | Implementasi |
|---|---|
| Price series | Metadata category/commodity/geography/currency/unit/frequency/source; input manual, CSV/XLSX, koreksi tercatat, ekspor CSV, grafik interaktif dan tabel observasi |
| Price calculations | MoM, QoQ, YoY, CAGR, moving average 7/30 observasi, volatilitas return, high/low, confidence dan tanggal data; regional comparison 2–4 seri |
| Market events | Create/edit tanggal, kategori, geography, supplier, type, description, impact, probability, source dan analyst assessment |
| Supplier landscape | Tujuh klasifikasi PRD, approval analyst dengan rationale dan riwayat; tidak menerapkan klasifikasi AI otomatis |
| Research workspace | Notes, charts/datasets, saved searches, RFIs, suppliers, documents, reports, conversations; read-only sharing dalam region yang sama; optimistic version check |
| Advanced RFI analysis | Respons final, missing answers, min/median/max, numerical deviation flags; supplier/market/internal evidence; mode evidence dan Azure AI |
| Alert engine | Percentage change, above/below threshold, benchmark premium, new document/event; worker setiap menit; deduplikasi; acknowledge/resolve; notifikasi dalam aplikasi |
| External API | EIA Brent/WTI monthly; key terenkripsi; connection test dan sync idempotent; adapter JSON untuk host HTTPS yang diizinkan |
| Automated brief | Sembilan bagian PRD, sumber tersimpan, missing-data markers, evidence digest/Azure AI, review, sharing, Markdown export; jadwal dan riwayat run |
| Advanced dashboard | Price trend/volatility, observation count, events, alerts, supplier landscape, RFI/document coverage per kategori; filter data contoh |

## Penggunaan

1. Buka **Market Intelligence**. Data contoh dikecualikan secara default; gunakan **Include illustrative records** untuk melihatnya.
2. Role **Market Intelligence Analyst** mengelola seri, observasi, event dan klasifikasi supplier. **Buyer** juga dapat membuat workspace, brief, alert dan jadwal riset.
3. **Price series**: buat metadata, lalu input/import observasi. Header CSV/XLSX: `date,value,confidence,source,notes`. Date dan value wajib; tanggal ISO `YYYY-MM-DD`, confidence 0–1. Maksimum 10.000 baris / 5 MB; formula Excel ditolak; ukuran workbook hasil dekompresi maksimum 50 MB.
4. **Research workspaces**: pin sumber dan grafik, isi notes, pilih penerima read access. Sumber yang tidak boleh diakses penerima disembunyikan. Percakapan pribadi tetap hanya dapat dibaca pemiliknya.
5. **Briefs**: *Evidence digest* menyusun data dan perhitungan; *Azure AI analysis* memerlukan Azure aktif. Semua penerima brief harus memiliki akses ke setiap sumber. Analyst dapat menandai report sebagai reviewed.
6. **Alerts**: contoh rule `change_pct > 10`, lead time `change_pct > 20`, inventory coverage `below 3`, atau `new_document`. Metrik operasional dapat dicatat dalam seri `lead_time` atau `inventory_coverage` dari data organisasi.
7. **Sources & schedules**: Admin mengatur API; Analyst menjalankan sync. Buyer/Analyst dapat menjadwalkan brief atau evaluasi alert. Jadwal dapat dipause; **Run now** diproses worker dan statusnya dicatat.
8. **RFI → AI analysis**: **Analyze evidence** untuk perhitungan deterministik; **Analyze with Azure AI** untuk interpretasi dengan sumber tambahan.

## Data yang sudah disiapkan

- **Brent crude — EIA monthly**: 120 observasi nyata, periode terakhir Agustus 2026. Data diterima melalui API dan disimpan di PostgreSQL.
- **Energy market watch**: workspace Buyer, dibagikan read-only ke Analyst, memuat grafik Brent dan brief bersumber.
- **Energy market brief — daily**: jadwal evidence digest setiap 24 jam, disiapkan dalam status **paused**. Satu eksekusi manual melalui worker sudah berstatus **COMPLETED**.
- **Brent MoM increase above 10%**: rule pribadi Buyer; mengevaluasi observasi nyata dan menampilkan tanggal sumber.

## API dan konfigurasi

Konektor menggunakan [API EIA v2](https://www.eia.gov/opendata/documentation.php), petroleum spot prices, monthly frequency, seri `RBRTE`/`RWTC`. Target harus seri harga USD/BBL monthly. Observasi diberi tanggal pertama bulan dan merupakan rata-rata bulanan, bukan harga pada hari itu.

Tanpa key tersimpan, sync manual memakai `DEMO_KEY` untuk eksplorasi. [Kuota exploration key dibatasi](https://api.data.gov/docs/developer-manual/); aplikasi mensyaratkan key organisasi untuk sync EIA terjadwal. Simpan melalui **Admin → Market APIs → Manage market API sources**. Key tidak dikembalikan ke browser.

Untuk provider JSON, tetapkan `MARKET_API_ALLOWED_HOSTS` pada environment API dan worker. Endpoint wajib HTTPS, tanpa query/credential dalam URL; redirect ditolak. Token disimpan terenkripsi dan dikirim sebagai Bearer header. Kontrak respons:

```json
{"observations":[{"date":"2026-08-01","value":"100.50","confidence":0.9,"source":"Nama publikasi","notes":"Catatan analyst"}]}
```

Nilai mengikuti unit/currency seri target; tidak ada konversi otomatis. Respons tidak valid ditolak sebelum disimpan.

## Definisi dan batas implementasi

- MoM/QoQ/YoY membandingkan observasi terakhir dengan observasi pada/sebelum offset kalender 1/3/12 bulan, dengan gap baseline maksimum 40 hari. Tanggal baseline tersedia di API.
- CAGR membutuhkan minimal 365 hari serta nilai awal/akhir positif; annualization 365,25 hari. Moving average membutuhkan 7/30 observasi. Volatilitas adalah sample standard deviation persentase perubahan berurutan, tidak diannualisasi. Histori kurang/denominator nol menghasilkan nilai kosong.
- Regional comparison dan benchmark alerts memerlukan commodity/currency/unit/metrik yang sama; premium alert memerlukan tanggal observasi yang sama.
- Numerical deviation RFI: lebih dari 50% dari median pertanyaan, minimum tiga respons numerik. Ini flag review, bukan supplier ranking.
- Struktur dan ID citation AI divalidasi; ini belum membuktikan kebenaran setiap klaim. Review analyst tetap diperlukan.
- Hak akses sumber diperiksa lagi saat brief/analysis dibaca atau diekspor. Sharing workspace tidak mengubah hak akses dokumen asal.
- Alert bersifat pribadi dan tampil dalam aplikasi; tidak mengirim email.
- Worker memakai row lock PostgreSQL. Run terinterupsi lebih dari 15 menit ditandai failed untuk diperiksa. Owner yang tidak aktif/tidak berhak tidak dapat menjalankan tugas.
- Azure AI dan MCP enterprise belum diuji live; evidence digest dan perhitungan tetap bekerja tanpa koneksi tersebut. Pemakaian sync EIA terjadwal memerlukan key organisasi.

## Validasi dan migrasi

Migration `0003` menambahkan `market_points` dan `market_runs`, mempertahankan observasi contoh lama. Snapshot sebelumnya: `backend/data/backups/greta-before-phase2-20260908T033614Z.dump` (mode `0600`).

42 tes PostgreSQL lulus; 40 tes SQLite lulus dengan dua tes concurrency PostgreSQL di-skip. TypeScript dan build lulus. Browser/UAT belum dilakukan. Build memperingatkan ukuran bundle; temuan lint baseline masih terbuka.

Phase 3 dilanjutkan pada [PHASE-3.md](PHASE-3.md). Phase 4 autonomous agent belum diimplementasikan.
