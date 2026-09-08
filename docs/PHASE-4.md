# Phase 4 — Autonomous Agent

Implementasi fungsional §117 PRD: agent terjadwal membaca delapan domain, membandingkan bukti dengan baseline terakhir, menilai risiko melalui kebijakan eksplisit, dan menerbitkan intelligence alert dalam aplikasi. UI tersedia pada **Autonomous Agent** bagi Buyer dan Market Intelligence Analyst. Eksekusi otomatis memakai aturan deterministik **Evidence rules v1**; tidak memerlukan Azure atau model LLM untuk beroperasi.

## Penggunaan

1. **Operational evidence**: buat seri Demand, Inventory, Open PO value, Overdue PO count, atau Supplier lead time. Isi kategori, sumber, scope, unit, dan horizon demand. Tambahkan observasi bertanggal atau impor CSV/XLSX. Gunakan angka organisasi yang dapat ditelusuri ke sumbernya.
2. **Agent workspace → Create agent**: pilih kategori dan seri operasional. RFI, supplier, dokumen/bukti pasar, harga, dan event dalam kategori serta hak akses pemilik dibaca otomatis. Opsional: aktifkan pembacaan enterprise melalui internal MCP yang sudah dikonfigurasi Admin.
3. Atur interval 15–10.080 menit, batas umur observasi 1–730 hari, minimum confidence 0–1, waktu eksekusi 15–300 detik, dan ambang risiko. Default: harian, umur 90 hari, confidence 0,5, runtime 150 detik. **Enable periodic evaluation** mengaktifkan jadwal; agent paused tetap dapat dijalankan dengan **Run once**.
4. Run pertama menyimpan baseline dan level risiko teramati. Alert perubahan baru dibuat setelah baseline. **Inspect evidence** memuat sebelum/sesudah, tanggal observasi, sumber, cakupan, alasan risiko, langkah eksekusi, dan ekspor JSON.
5. **Intelligence alerts** atau ikon notifikasi membuka alert. Pemilik dan penerima dapat acknowledge/resolve dengan catatan; histori tetap tersimpan. Sharing memberikan akses baca kepada Buyer/Analyst aktif di region sama. Hanya pemilik dapat mengubah policy/sumber, menjalankan, pause, atau cancel agent.
6. Admin dapat menghentikan seluruh eksekusi agent di region melalui **Administration → Autonomous control**. Kontrol ini tidak memberikan Admin akses ke isi intelligence procurement.

Alert Phase 4 menggunakan kanal **in-app**. Tidak mengirim email, membuat PO, melakukan supplier award, atau mengirim workflow enterprise otomatis. Workflow yang telah tersedia pada Phase 3 tetap melalui approval Buyer tersendiri.

## Delapan domain dan cakupan

| Domain | Bukti yang dievaluasi |
|---|---|
| Demand | Projected demand quantity menurut scope dan horizon tetap; seri operasional atau internal MCP |
| Inventory | Inventory coverage, satuan `months`; seri operasional atau internal MCP |
| PO | Open PO value menurut currency dan overdue PO count; seri operasional atau internal MCP |
| RFI | Status, versi, penutupan, judul/pertanyaan, supplier yang diundang, jumlah respons submitted |
| Market Data | Metadata dan checksum perubahan dokumen serta snapshot external evidence yang terotorisasi |
| Supplier Data | Profil/landscape supplier dan supplier lead time dalam `weeks` |
| Price | Dua observasi terbaru setiap seri harga/index pada kategori |
| Market Events | Perubahan tanggal, impact, probability, assessment, description, dan sumber event |

- **AVAILABLE**: ada bukti pada domain dan seluruh observasi yang dikumpulkan masih memenuhi kualitas/freshness.
- **MISSING**: belum ada sumber/observasi yang bisa digunakan.
- **DEGRADED**: sumber gagal, seri kosong, data terlalu lama, confidence rendah, tanggal mundur, atau batas jumlah sumber terlampaui.
- **COMPLETED** berarti kedelapan domain AVAILABLE. **PARTIAL** tetap menghasilkan baseline dan perubahan yang dapat dibuktikan, sambil menampilkan gap. Cakupan Supplier Data bisa berasal dari profil saja; kelengkapan metrik risiko diperiksa terpisah.
- Umur sumber berlaku untuk observasi numerik. Untuk dokumen/RFI/supplier/event, agent memantau state record saat ini; keberadaan record tidak membuktikan isi dokumen atau kondisi supplier sudah diverifikasi independen.
- Maksimum 30 seri operasional terpilih, 200 record per jenis/kategori dan 200 respons per RFI dalam satu evaluasi, dan 100 observasi per respons tool MCP. Jika jenis sumber melewati batas 200, jenis tersebut tidak dievaluasi dan cakupan menjadi DEGRADED. API histori menampilkan 50 run terbaru; inbox menampilkan hingga 100 alert yang dapat diakses. Riwayat database tidak dihapus otomatis.
- Seri operasional lokal dapat dibaca Buyer/Analyst dalam region sesuai classification. Pemilik atau Analyst dapat menambah/koreksi observasi. Kontrak unit/scope tetap; perubahan basis sebaiknya dibuat sebagai seri baru.

## Perbandingan dan penilaian risiko

Perubahan nilai dihitung hanya bila key, metric, unit, currency, scope, dan horizon sesuai. `delta_pct = (current − previous) / abs(previous) × 100`. Baseline nol menghasilkan selisih nilai tanpa persentase. Perubahan basis ditampilkan sebagai **BASIS_CHANGED**, tanpa persentase lintas unit. Tanggal yang sama dengan nilai berubah menjadi **Historical correction**. Dokumen besar dilacak dengan checksum; teks dokumen/pertanyaan lengkap tidak disalin ke alert.

Agent membandingkan nilai terhadap baseline run sebelumnya untuk **what changed**. Penilaian tren risiko menggunakan dua tanggal observasi terakhir yang memenuhi confidence; untuk MCP tanpa previous value, observasi baseline sebelumnya dapat menjadi pembanding. Tanggal pembanding selalu dicatat. Perubahan risk akibat bergesernya periode observasi juga menghasilkan alert meskipun nilai terkini tetap.

| Kebijakan awal | Dampak |
|---|---|
| Demand naik ≥15% | Indikator MEDIUM |
| Lead time naik ≥20% | Indikator MEDIUM |
| Price naik ≥10% | Indikator MEDIUM |
| Open PO value naik ≥15% | Indikator MEDIUM |
| Inventory coverage <3 bulan | Indikator HIGH |
| Inventory coverage 3–<6 bulan | Indikator MEDIUM |
| Overdue PO count >0 | Indikator MEDIUM |

Risiko teramati menjadi **HIGH** jika ada indikator HIGH atau sedikitnya tiga jenis metrik MEDIUM/HIGH. **MEDIUM** jika ada indikator MEDIUM. **LOW** hanya bila demand, inventory, dan lead time mempunyai bukti risiko yang cukup dan tidak ada indikator meningkat. Jika syarat tersebut tidak terpenuhi, **UNKNOWN**. Risiko HIGH/MEDIUM dapat terdeteksi dari bukti parsial; field `complete` serta daftar metrik belum tersedia tetap ditampilkan.

Ambang perubahan alert memakai nilai absolut persentase, sehingga perubahan material ke kedua arah dilaporkan. Inventory dan overdue PO melaporkan setiap perubahan nilai valid. Penambahan sumber, perubahan record, perubahan cakupan, serta perubahan risiko juga dapat menerbitkan alert. Satu run menerbitkan paling banyak satu alert; run berikutnya dengan bukti sama tidak mengulangi alert. Episode koreksi berulang tetap memiliki alert terpisah.

Tidak ada imputasi data hilang menjadi nol atau klaim bahwa supplier hilang saat sumber gagal dibaca. Baseline sumber yang tidak tersedia, rendah confidence, atau bertanggal mundur dipertahankan; sumber yang tidak layak tidak dipakai untuk menyatakan risiko rendah. Bukti demo dikecualikan secara default dan selalu dikecualikan dari perhitungan risiko live. Mode illustrative melabeli hasil/alert sebagai contoh.

Ambang ini adalah kebijakan awal yang dapat ditinjau pengguna, belum model risiko yang dikalibrasi untuk organisasi. Angka agregat lintas scope tidak dijumlahkan atau dikonversi otomatis. Rule engine mengidentifikasi sinyal teramati; korelasi beberapa indikator belum membuktikan hubungan sebab akibat.

## Kontrak internal MCP

Gunakan **Administration → Enterprise MCP** serta `MCP_ALLOWED_HOSTS` yang sama pada API dan agent worker. Endpoint harus HTTPS dan allowlisted; redirect tidak diikuti. Token terenkripsi memakai kunci aplikasi. Gateway bertanggung jawab memverifikasi identitas aplikasi/pengguna dan scope baris enterprise.

Agent hanya memanggil empat read tool tetap:

| Tool | Metric yang diterima |
|---|---|
| `get_demand_history` | `demand_quantity` |
| `get_inventory_position` | `inventory_coverage` |
| `get_open_purchase_orders` | `po_open_value`, `po_overdue_count` |
| `get_lead_time_history` | `supplier_lead_time` |

Arguments: `category` = ID kategori Greta; `region` dan `user_id` ditambahkan backend berdasarkan pemilik agent. Tidak ada parameter SQL atau instruksi dari isi dokumen. Adapter internal memakai initialize/initialized dan tools/call melalui Streamable HTTP, JSON atau SSE, protocol version `2025-03-26` sebagaimana integrasi internal yang sudah ada. Setiap tool call mempunyai timeout HTTP 30 detik, respons maksimum 2 MB, serta batas total runtime agent. Endpoint/allowlist diperiksa ulang setiap call.

Gateway mengembalikan MCP `result.structuredContent` berikut, atau satu blok `content` bertipe `text` yang berisi JSON sama. Ini contoh kontrak; tanggal dan nilai harus berasal dari sistem sumber aktual:

```json
{
  "category_id": "<Greta category ID>",
  "region": "Region 1",
  "observations": [{
    "key": "octg-region1-demand-30d",
    "metric": "demand_quantity",
    "value": 118,
    "as_of": "2026-09-08",
    "previous_value": 100,
    "previous_as_of": "2026-08-08",
    "unit": "MT",
    "currency": "",
    "scope": "OCTG Region 1",
    "horizon_days": 30,
    "source": "Organization planning system / demand ledger",
    "confidence": 1
  }]
}
```

`key` harus stabil dan unik per tool. Previous value/date opsional tetapi harus berpasangan; tanggal previous harus lebih awal. Tanggal masa depan, region/kategori berbeda, metric di luar kontrak, confidence di luar 0–1, atau nilai negatif ditolak. Unit wajib `months`/`weeks`/`orders`/`currency` untuk inventory/lead time/PO count/PO value. PO count integer; PO value membutuhkan kode currency tiga huruf kapital. Demand memakai unit yang ditetapkan sumber. Payload JSON yang dinormalisasi dibatasi 200.000 karakter. Respons kosong berarti tidak ada observasi, bukan saldo nol.

MCP organisasi belum terhubung; otomatisasi membaca data lokal tetap berfungsi. Phase 4 membaca snapshot external MCP yang sudah disimpan Phase 3 sebagai Market Data; tidak memanggil sembarang external tool atau menjalankan autonomous web research.

## Worker, transaksi, dan akses

- Migration **0005** menambah `agent_runs`: konfigurasi saat run, snapshot sumber, baseline, hasil, langkah, lease, trigger, status dan waktu. Agent/signal/alert tersimpan pada `records`; observasi memakai `market_points`.
- Worker khusus `python -m app.agent_worker` memeriksa antrean setiap lima detik. `scripts/dev.sh`, Compose service `agent`, dan `deploy/greta-agent.service` sudah menyertakannya. Worker indexing/SMTP/market/workflow tetap terpisah agar tool lambat tidak menahan pekerja tersebut.
- PostgreSQL row locks dan `SKIP LOCKED` memastikan run hanya diklaim satu worker. Permintaan run bersamaan untuk agent aktif mengembalikan run yang sama. Satu agent tidak memiliki dua run aktif. Jadwal yang tertinggal dieksekusi sekali dan next run diatur dari waktu kini; tidak ada catch-up burst.
- Config revision membatalkan pekerjaan aktif, menaikkan versi, dan mereset baseline; histori lama dipertahankan. Pause/cancel/Admin stop mencabut lease. Hak pemilik, region, category, versi dan stop control diperiksa setiap checkpoint serta saat publikasi.
- Alert, baseline, dan status akhir di-commit atomik. Kegagalan/timeout/cancel tidak menerbitkan hasil parsial dari run gagal. Deadline diperiksa pada checkpoint dan sebelum commit; pembacaan lokal sinkron yang melewati budget juga dibuang sebelum publikasi. Lease worker yang terhenti menjadi FAILED setelah runtime +30 detik; scheduler dapat membuat run baru pada jadwal berikutnya. Tidak ada retry langsung tanpa batas.
- Admin stop mempertahankan konfigurasi jadwal. Selama stop, due schedule digeser tanpa dieksekusi; sesudah enable kembali, agent menunggu jadwal berikutnya atau **Run once** dari pemilik.
- Sharing mengikuti ACL agent saat ini. Sumber snapshot **dan** baseline, termasuk respons RFI yang berkontribusi ke hitungan submitted, diperiksa ketika report/alert dibaca. Pencabutan hak atas sumber menyembunyikan report yang mengandungnya. Agent tidak menggunakan histori yang tak lagi boleh dibaca pemilik; baseline dimulai ulang jika otorisasi histori berubah.
- Audit merekam perubahan konfigurasi/sharing, queue, call MCP, terminal status, publikasi dan disposition alert. Input sumber adalah data; tidak dapat mengganti policy maupun daftar tool.

## Instalasi lokal dan acceptance

Monitor awal menggunakan seri nyata **Brent crude — EIA monthly** yang sudah tersimpan. Demand/inventory/PO/lead time organisasi belum diberikan. Agent dapat memantau perubahan harga yang diimpor berikutnya, tetapi tidak boleh dianggap telah memantau kedelapan domain dengan data enterprise live. Key EIA organisasi tetap diperlukan untuk sync harga terjadwal; agent tidak mengubah kebijakan konektor tersebut.

Pengujian mencakup skenario contoh PRD, delapan domain lengkap, missing/stale/low-confidence evidence, koreksi dan basis unit, outage/recovery MCP, scope/sharing/revocation, cancel/deadline/lease recovery, scheduler, deduplication, dan konkurensi PostgreSQL. Hasil migrasi, pengujian akhir serta monitor live dicatat di [VALIDATION.md](VALIDATION.md).

UAT organisasi, koneksi enterprise aktual, kalibrasi ambang, retensi snapshot, beban besar, observability/monitoring worker, dan deployment Ubuntu masih memerlukan acceptance. Implementasi ini adalah agent pemantauan berkala dengan langkah serta tindakan terbatas; tidak menyediakan perencanaan bebas oleh LLM, trading, atau keputusan pengadaan otomatis.
