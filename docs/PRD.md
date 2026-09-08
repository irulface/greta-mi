# PRODUCT REQUIREMENT DOCUMENT

## AI Driven Market Intelligence & RFI Repository

**Document Version:** 1.0  
**Status:** Product Baseline  
**Application Type:** Enterprise Web Application  
**Primary Platform:** Web  
**Backend:** Python 3.12 preferred, Python 3.11 supported  
**Frontend:** React + TypeScript  
**Database:** PostgreSQL + pgvector  
**Production OS:** Ubuntu Server 24.04 LTS  
**Development OS:** macOS  
**LLM Provider:** Azure OpenAI  
**AI Configuration:** Managed through Admin UI  
**Primary Users:** Admin, Fungsi Pengguna, Buyer, Market Intelligence Analyst  

---

# 1. Executive Summary

AI Driven Market Intelligence & RFI Repository adalah platform enterprise yang mengintegrasikan:

1. Market Intelligence.
2. Request for Information / RFI management.
3. Historical RFI repository.
4. AI-based document intelligence.
5. Historical procurement and supply-chain intelligence.
6. Internal enterprise data melalui Model Context Protocol / MCP.
7. Azure OpenAI sebagai reasoning dan natural-language layer.
8. Analytical workspace untuk buyer dan Market Intelligence Analyst.
9. Supplier information dan market benchmarking.
10. Knowledge repository yang terus bertambah setiap kali RFI dilakukan.

Platform tidak dirancang hanya sebagai chatbot.

Platform harus menjadi **Decision Intelligence Platform** yang memungkinkan pengguna berpindah dari:

**data → information → insight → recommendation → procurement action.**

Target pengalaman pengguna:

> “Saya membutuhkan compressor package 3–5 MW untuk Region X. Tampilkan historical demand, PO, inventory, RFI sebelumnya, supplier yang pernah berpartisipasi, historical quotation, market trend, lead time, dan rekomendasikan informasi apa yang perlu saya tanyakan dalam RFI baru.”

Sistem kemudian dapat menggabungkan:

- Historical RFI.
- Historical PO.
- Demand.
- Inventory.
- Supplier information.
- Previous quotation.
- Market intelligence.
- External market data.
- Internal market analysis.
- AI reasoning.

Hasil akhirnya dapat menjadi:

- Market brief.
- Procurement insight.
- Suggested RFI.
- Supplier shortlist.
- Price benchmark.
- Lead-time benchmark.
- Supply-risk indication.
- Negotiation preparation.

---

# 2. Product Vision

## 2.1 Vision Statement

Membangun centralized AI-powered market intelligence platform yang menjadi **single source of intelligence** untuk market research, supplier discovery, RFI, historical procurement intelligence, dan sourcing decision support.

## 2.2 North Star

Setiap keputusan sourcing strategis seharusnya dapat dijawab dengan menghubungkan:

**What do we need?**

Historical Demand + Future Demand

↓

**What do we already have?**

Inventory + Open PO + Existing Contract

↓

**What have we purchased before?**

PO History + Contract + Historical Price

↓

**What did the market tell us before?**

Historical RFI + Supplier Responses

↓

**What is happening in the market now?**

Market Intelligence + Price Index + Supplier Capacity + Market Events

↓

**What should we do?**

AI-assisted Procurement Recommendation

---

# 3. Product Principles

## 3.1 Data First, AI Second

AI tidak boleh menjadi sumber kebenaran utama.

Sumber kebenaran berasal dari:

- database;
- RFI;
- supplier response;
- procurement records;
- market intelligence source;
- analyst report;
- approved external datasets.

LLM hanya berfungsi sebagai:

- reasoning layer;
- summarization layer;
- query interface;
- extraction engine;
- classification engine;
- recommendation assistant.

---

## 3.2 Evidence Before Recommendation

Setiap recommendation yang dihasilkan AI harus menyertakan sumber pendukung.

Contoh:

> OCTG demand berpotensi meningkat dalam 12 bulan mendatang.

**Evidence**

- Internal demand plan: +21%.
- Historical consumption: +14%.
- RFI Supplier A: lead time meningkat dari 16 menjadi 22 minggu.
- Market report: regional mill utilization meningkat.

---

## 3.3 Human-in-the-Loop

AI tidak boleh secara otomatis:

- memilih pemenang;
- melakukan award;
- mengirim RFI final tanpa approval;
- mengubah procurement master data;
- melakukan write-back terhadap ERP;
- menetapkan supplier recommendation sebagai keputusan final.

AI menghasilkan **recommendation**, bukan keputusan.

---

## 3.4 Auditability

Setiap:

- AI request;
- AI response;
- document retrieval;
- MCP tool call;
- configuration change;
- RFI revision;
- supplier response;
- user action

harus mempunyai audit trail.

---

# 4. Product Scope

Platform terdiri dari tujuh domain utama.

### Domain A — Market Intelligence

Market research dan price/supplier intelligence.

### Domain B — RFI Management

End-to-end creation sampai analysis.

### Domain C — RFI Knowledge Repository

Repository RFI historical dan supplier response.

### Domain D — Enterprise MCP

Akses terkontrol terhadap internal database.

### Domain E — AI Intelligence

Azure OpenAI orchestration.

### Domain F — Analytics

Dashboard, comparison, trends, benchmark.

### Domain G — Administration

Users, roles, models, MCP, indexing, taxonomy, security, audit.

---

# 5. User Roles

Empat role minimum.

## 5.1 Admin

Admin mengelola platform.

Hak utama:

- manage users;
- manage roles;
- manage permission;
- Azure OpenAI configuration;
- MCP configuration;
- indexing configuration;
- directory sources;
- category taxonomy;
- supplier master;
- system configuration;
- prompt template;
- AI model deployment;
- audit log;
- system health.

Admin tidak secara otomatis memiliki hak melakukan procurement approval kecuali diberikan permission tambahan.

---

# 5.2 Fungsi Pengguna

Fungsi pengguna adalah internal requester/business user.

Kemampuan:

- create RFI request;
- mengisi business requirement;
- upload specification;
- melihat status RFI miliknya;
- melihat response yang diperbolehkan;
- memberikan technical clarification;
- memberikan technical evaluation;
- menggunakan AI assistant sesuai data authorization;
- mencari historical RFI sesuai hak akses.

Default restriction:

Tidak dapat mengirim RFI langsung ke supplier.

---

# 5.3 Buyer

Buyer mengelola commercial RFI lifecycle.

Kemampuan:

- menerima RFI request;
- review requirement;
- menentukan supplier;
- mengedit RFI;
- generate RFI menggunakan AI;
- issue RFI;
- manage clarification;
- close RFI;
- compare response;
- commercial evaluation;
- create sourcing summary;
- melihat procurement historical data.

---

# 5.4 Market Intelligence Analyst

Market Intelligence Analyst fokus pada intelligence.

Kemampuan:

- create market research;
- maintain market data;
- price analysis;
- supplier landscape;
- category outlook;
- RFI analysis;
- publish market intelligence report;
- validate AI-generated intelligence;
- manage market events;
- create price benchmark;
- create category intelligence.

---

# 6. Optional Future Role

## Supplier / External Respondent

Supplier account tidak diwajibkan pada MVP.

Pada MVP supplier dapat menerima:

**secure invitation link + token + expiration.**

Future version dapat menyediakan Supplier Portal dengan:

- authentication;
- company profile;
- questionnaire;
- attachment;
- clarification;
- submission history.

---

# 7. Core Product Modules

# 7.1 Home Dashboard

Dashboard disesuaikan dengan role.

Contoh informasi:

### Buyer

- Open RFI.
- RFI awaiting action.
- Supplier response status.
- RFI closing soon.
- Recent historical purchase.
- Price movement.
- AI-generated alerts.

### Market Intelligence Analyst

- Categories monitored.
- Price index movement.
- Market events.
- New RFI requiring analysis.
- Supplier activity.
- Recently indexed reports.

### Fungsi Pengguna

- My requests.
- Awaiting clarification.
- Completed RFI.
- Recent recommendation.

### Admin

- Active users.
- Indexing jobs.
- AI usage.
- Failed MCP calls.
- Storage.
- system health.

---

# 7.2 Global Intelligence Search

Satu search bar harus dapat mencari lintas:

- RFI;
- RFI response;
- supplier;
- document;
- price data;
- market report;
- material;
- category;
- PO;
- demand;
- inventory.

Search harus mempunyai dua mode:

### Keyword Search

Exact dan lexical search.

### Semantic Search

Meaning-based search menggunakan embeddings.

Contoh:

> gas engine maintenance

dapat menemukan dokumen bertuliskan:

> overhaul Waukesha engine

walaupun exact term berbeda.

---

# 7.3 AI Research Assistant

Interface conversational seperti:

**Ask Market Intelligence**

User dapat bertanya:

> What do we know about OCTG 13-3/8" casing?

AI menjalankan:

1. identify user intent;
2. identify category;
3. retrieve historical RFI;
4. call internal MCP;
5. retrieve relevant market reports;
6. retrieve supplier information;
7. synthesize answer;
8. attach citations.

Contoh output:

### Historical Internal Market

PO volume  
Historical price  
Number of suppliers  
Lead time

### Current Inventory

Available inventory  
Reserved inventory  
Open PO

### Historical RFI

Last RFI date  
Participating suppliers  
Lead time offered  
Commercial range

### Market Intelligence

Raw-material trend  
Supply condition  
Market risk

### Recommended Action

RFI recommended / not required  
Potential supplier list  
Suggested information required

---

# 8. Market Intelligence Module

## 8.1 Category Intelligence

Setiap category mempunyai halaman intelligence sendiri.

Contoh:

**Rotating Equipment → Gas Compressor**

Informasi:

- market overview;
- historical spend;
- historical demand;
- suppliers;
- previous RFI;
- existing contracts;
- price evolution;
- lead-time evolution;
- market events;
- demand outlook;
- analyst reports;
- associated documents.

---

## 8.2 Category Taxonomy

Minimum hierarchy:

Level 1  
Category Group

Level 2  
Category

Level 3  
Subcategory

Level 4  
Commodity / Material / Service

Contoh:

Equipment

→ Rotating Equipment

→ Compressor

→ Centrifugal Compressor

atau:

Material

→ Tubular

→ OCTG

→ Casing 13-3/8"

---

# 9. Market Data

System harus dapat menerima market data dari:

### Manual entry

Analyst memasukkan index/value.

### Excel/CSV upload

Untuk price series.

### API

Future external intelligence provider.

### Internal database

MCP.

### Report extraction

AI mengambil structured information dari report.

---

# 10. Price Intelligence

Data minimum:

- category;
- commodity;
- index name;
- geographic region;
- currency;
- unit;
- date;
- price/index value;
- source;
- confidence;
- analyst notes.

System harus menyediakan:

- time-series chart;
- MoM;
- QoQ;
- YoY;
- CAGR;
- moving average;
- volatility;
- high/low;
- regional comparison.

---

# 11. Price Benchmark

Untuk satu material/service:

Internal Purchase Price

vs.

Historical RFI

vs.

Latest Supplier Quote

vs.

Market Index

vs.

Should Cost

Tujuan:

menghasilkan **Price Position Indicator**.

Contoh:

Market Benchmark = 100

Company Historical Price = 103

Latest Supplier Quote = 118

Result:

> Latest quotation is approximately 15% above the internal historical price and 18% above market benchmark.

AI wajib menunjukkan calculation source.

---

# 12. Supplier Intelligence

Supplier profile terdiri dari:

### Identity

- supplier code;
- supplier name;
- country;
- website;
- manufacturer/distributor/service provider.

### Capabilities

- category;
- product;
- service;
- manufacturing location;
- certification.

### Historical Interaction

- RFIs received;
- RFI participation;
- PO history;
- response rate;
- quotation history.

### Performance

Jika datanya tersedia:

- delivery performance;
- quality;
- lead time;
- commercial competitiveness.

---

# 13. Supplier Landscape

Untuk setiap category:

Leader

Challenger

Specialist

Emerging Supplier

New Entrant

Local Supplier

Global Supplier

Classification dilakukan analyst.

AI boleh menyarankan classification, tetapi analyst melakukan approval.

---

# 14. Market Event Intelligence

Market Intelligence Analyst dapat mencatat event seperti:

- steel price movement;
- sanctions;
- import restriction;
- currency movement;
- plant shutdown;
- refinery shutdown;
- mill expansion;
- supplier merger;
- logistics disruption;
- geopolitical event;
- regulation;
- technology development.

Fields:

- title;
- event date;
- category;
- geography;
- supplier;
- event type;
- description;
- expected impact;
- probability;
- source;
- analyst assessment.

---

# 15. RFI Management Module

RFI menjadi salah satu core workflow utama.

Lifecycle:

**Draft**

↓

**Internal Review**

↓

**Approved**

↓

**Issued**

↓

**Open**

↓

**Response Received**

↓

**Closed**

↓

**Analysis**

↓

**Completed**

↓

**Archived**

Alternative:

**Cancelled**

---

# 16. Creating RFI

User dapat memulai dengan:

### Blank RFI

Manual.

### Template

Template berdasarkan category.

### Copy Previous RFI

Clone historical RFI.

### AI Generate

Generate berdasarkan requirement.

---

# 17. AI Generated RFI

Contoh input:

> Need market information for 5 MW gas compressor package for offshore application.

AI mencari:

- historical RFIs;
- similar equipment;
- technical requirements;
- previous supplier answers.

Kemudian membuat draft section:

### Company / Supplier Information

### Technical Capability

### Product Specification

### Manufacturing Capacity

### Lead Time

### Commercial Information

### Local Content

### After-Sales Support

### Warranty

### Technology

### Sustainability

### Risks

### Future Capacity

Buyer memilih:

Accept

Edit

Regenerate

Delete

---

# 18. RFI Question Types

System harus mendukung:

- short text;
- long text;
- integer;
- decimal;
- currency;
- percentage;
- date;
- yes/no;
- single choice;
- multiple choice;
- table;
- file attachment.

---

# 19. Conditional RFI Questions

Contoh:

Question:

Are you the OEM?

If:

NO

display:

Provide OEM authorization letter.

---

# 20. RFI Template Library

Template disimpan berdasarkan:

- category;
- subcategory;
- region;
- RFI type;
- business objective.

Version controlled.

---

# 21. RFI Supplier Selection

Buyer dapat:

- search supplier;
- filter by category;
- view previous participation;
- select multiple suppliers;
- add new potential supplier;
- request analyst recommendation.

AI dapat menghasilkan:

**Suggested Suppliers**

beserta alasan.

AI tidak boleh otomatis mengirim RFI.

---

# 22. Issuing RFI

Saat Issue:

System menghasilkan unique invitation.

Email berisi:

- RFI title;
- reference number;
- closing date;
- secure response link.

Link menggunakan:

- signed token;
- expiration;
- one-time/controlled access.

Future:

Supplier authenticated portal.

---

# 23. Supplier Response

Supplier dapat:

- fill questionnaire;
- save draft;
- upload attachment;
- submit response.

Setelah submit:

response menjadi immutable.

Jika perubahan diperlukan:

buyer membuka revision cycle.

---

# 24. RFI Clarification

Buyer dapat membuat clarification.

Status:

OPEN

ANSWERED

CLOSED

Semua clarification disimpan dalam audit history.

---

# 25. RFI Response Comparison

System menghasilkan supplier comparison matrix.

Contoh:

| Attribute | Supplier A | Supplier B | Supplier C |
|---|---|---|---|
| Capacity | ... | ... | ... |
| Lead Time | ... | ... | ... |
| Country | ... | ... | ... |
| Price indication | ... | ... | ... |
| Warranty | ... | ... | ... |

AI dapat:

- summarize differences;
- detect missing response;
- identify outlier;
- highlight risk.

---

# 26. AI RFI Analysis

Contoh:

> Compare suppliers based on manufacturing capacity, lead time, commercial competitiveness and previous delivery performance.

AI mengambil:

RFI response

+

PO history

+

supplier master

+

internal performance

+

market intelligence.

Output harus menyertakan evidence.

---

# 27. RFI Final Report

System dapat membuat RFI summary:

1. Executive summary.
2. Business requirement.
3. Market participants.
4. Supplier comparison.
5. Price indication.
6. Lead-time comparison.
7. Capacity assessment.
8. Market risks.
9. Key findings.
10. Recommendation.
11. Source references.

---

# 28. Historical RFI Repository

Repository harus menyimpan:

- RFI;
- questions;
- supplier responses;
- attachments;
- analysis;
- report;
- clarification;
- supplier metadata.

Semua RFI otomatis menjadi knowledge source setelah selesai.

---

# 29. External Historical RFI Directory Indexing

Salah satu critical capability:

Admin dapat menentukan server directory seperti:

`/data/rfi_repository/`

Contoh struktur:

`/2022/OCTG/`

`/2023/Rotating-Equipment/`

`/2024/Drilling-Services/`

Indexing Service harus membaca directory secara recursive.

---

# 30. Supported Document Formats

Minimum:

- PDF;
- DOCX;
- XLSX;
- PPTX;
- TXT;
- CSV;
- HTML.

Optional:

- EML;
- MSG;
- ZIP.

Untuk scanned PDF:

status dapat diberi:

**OCR REQUIRED**

OCR pipeline dapat ditambahkan sebagai enhancement.

---

# 31. Indexing Pipeline

Directory

↓

File Discovery

↓

Checksum

↓

Duplicate Detection

↓

File Parsing

↓

Text Extraction

↓

Metadata Extraction

↓

Document Classification

↓

Chunking

↓

Embedding

↓

PostgreSQL + pgvector

↓

Search Index

---

# 32. Directory Watch

Tiga mode:

### Manual Scan

Admin menekan:

**Scan Directory**

### Scheduled Scan

Contoh:

daily.

### File System Watcher

Detect:

create/change/delete.

---

# 33. Duplicate Detection

Gunakan:

SHA-256.

Jika checksum sama:

tidak melakukan embedding ulang.

Jika file berubah:

buat Document Version baru.

---

# 34. Document Metadata

Minimum:

- document ID;
- filename;
- original path;
- file type;
- checksum;
- size;
- created date;
- modified date;
- indexed date;
- category;
- RFI number;
- supplier;
- year;
- owner;
- security classification;
- document status.

---

# 35. AI Metadata Extraction

AI dapat mendeteksi:

- RFI number;
- category;
- supplier;
- product;
- manufacturer;
- price;
- currency;
- lead time;
- region;
- technical specification.

Extraction menghasilkan structured JSON.

Confidence harus dicatat.

Low-confidence extraction → Analyst review.

---

# 36. Semantic Repository

Document harus dipecah menjadi chunks.

Contoh metadata chunk:

`document_id`

`page`

`section`

`category`

`supplier`

`year`

`rfi_id`

`access_scope`

`embedding`

---

# 37. Search Architecture

Gunakan hybrid search:

**PostgreSQL Full Text Search**

+

**pgvector semantic search**

+

metadata filters.

Result kemudian dapat di-rerank.

---

# 38. Vector Database

Tetap menggunakan PostgreSQL.

Extension:

**pgvector**

Recommended initial index:

**HNSW**

untuk semantic retrieval.

Vector store tidak perlu database terpisah pada tahap awal.

---

# 39. RAG Architecture

User Question

↓

Intent Classification

↓

Query Rewrite

↓

Hybrid Retrieval

├── RFI Repository

├── Market Reports

├── Supplier Information

└── MCP Tools

↓

Reranking

↓

Context Assembly

↓

Azure OpenAI

↓

Grounded Answer

↓

Citations

---

# 40. Citation Requirements

AI response tidak boleh hanya menampilkan:

> Based on our historical RFI...

Harus menjadi:

> Supplier A historically indicated 16–18 weeks lead time.

**Sources**

RFI-2025-0042  
Supplier A Response  
Page 14  
Indexed 22 May 2026

Untuk MCP:

Demand Database  
Material: XXXXX  
Retrieved: timestamp

---

# 41. Internal Enterprise MCP

MCP menjadi standardized interface antara AI dan internal enterprise data.

Concept:

AI Application

↓

MCP Client

↓

Internal MCP Gateway

↓

Approved MCP Tools

↓

Internal Databases

---

# 42. Internal Data Domains

Minimum support:

### Demand

Historical demand.

### Purchase Order

Historical PO.

### Inventory

Stock position.

### Procurement

Supplier transaction history.

Future:

- contracts;
- work orders;
- supplier performance;
- maintenance;
- production plan.

---

# 43. MCP Design Principle

LLM **tidak diperbolehkan menjalankan arbitrary SQL.**

Jangan menyediakan:

`execute_sql(query)`

kepada model.

Gunakan parameterized domain tools.

---

# 44. Initial MCP Tools

Recommended tools:

### Demand

`get_demand_history`

Parameters:

- item/category;
- organizational unit;
- start_date;
- end_date;
- aggregation.

---

### Inventory

`get_inventory_position`

Return:

- unrestricted;
- reserved;
- available;
- safety stock;
- location.

---

### Historical PO

`get_po_history`

Parameters:

- material;
- supplier;
- region;
- period.

Return:

- PO date;
- supplier;
- quantity;
- price;
- currency;
- delivery date.

---

### Supplier Spend

`get_supplier_spend`

Return:

- yearly spend;
- category;
- transaction count.

---

### Lead Time

`get_lead_time_history`

Return:

- average;
- median;
- P90;
- supplier distribution.

---

### Open Purchase Order

`get_open_purchase_orders`

Return:

- quantity;
- supplier;
- expected delivery.

---

# 45. MCP Security

MCP tool calls wajib mengikuti user identity.

Contoh:

User A hanya mempunyai akses Region X.

AI meminta:

`get_inventory_position(region="Y")`

MCP harus menolak.

Authorization dilakukan server-side.

Tidak bergantung pada prompt.

---

# 46. MCP Authorization Layers

User

↓

Role

↓

Business Unit

↓

Data Scope

↓

Tool Permission

↓

Row-Level Authorization

---

# 47. MCP Default Access

Default:

**READ ONLY**

Write operation tidak menjadi bagian MVP.

---

# 48. MCP Audit Log

Setiap call mencatat:

- user;
- tool;
- parameter;
- timestamp;
- duration;
- returned row count;
- status;
- AI conversation;
- correlation ID.

Sensitive returned data tidak harus disimpan seluruhnya dalam audit log.

---

# 49. AI Layer

AI provider:

**Azure OpenAI**

Architecture harus model-agnostic pada level aplikasi.

Jangan hardcode deployment name di source code.

---

# 50. Azure OpenAI Admin Configuration

Admin UI:

**Administration → AI → Azure OpenAI**

Fields:

- configuration name;
- Azure endpoint;
- authentication type;
- API credential;
- model deployment;
- embedding deployment;
- fallback deployment;
- timeout;
- token limit;
- temperature/default reasoning settings where applicable;
- enabled/disabled.

---

# 51. Secret Management

API key tidak boleh disimpan plaintext.

Recommended MVP:

Admin inputs key.

↓

Backend encrypts secret menggunakan application master key.

↓

Encrypted credential disimpan.

Master encryption key berada di OS/environment.

↓

UI selanjutnya hanya menampilkan:

`••••••••••32A9`

Future:

Azure Key Vault.

Preferred enterprise authentication:

Microsoft Entra ID jika environment memungkinkan.

---

# 52. AI Connection Testing

Admin dapat menekan:

**Test Connection**

System menampilkan:

- endpoint status;
- model deployment;
- authentication;
- latency;
- test result.

Tidak pernah menampilkan API key.

---

# 53. AI Model Registry

System menggunakan logical model purpose.

Contoh:

`PRIMARY_REASONING`

`FAST_CHAT`

`DOCUMENT_EXTRACTION`

`EMBEDDING`

`FALLBACK`

Logical model kemudian dipetakan oleh Admin ke Azure deployment.

Dengan demikian model dapat diganti tanpa code changes.

---

# 54. AI Prompt Registry

Prompt tidak boleh semuanya hardcoded.

Database menyediakan:

- prompt name;
- version;
- purpose;
- system instruction;
- active version;
- owner;
- changed by;
- updated at.

Contoh:

`RFI_GENERATION_V3`

`RFI_COMPARE_V2`

`MARKET_RESEARCH_V4`

---

# 55. AI Use Cases

Minimum:

### Market Research

Generate category intelligence.

### RFI Drafting

Generate questions.

### Historical RFI Search

Find relevant RFI.

### Supplier Comparison

Compare response.

### Document Extraction

Extract structured data.

### Data Explanation

Explain MCP results.

### Market Summary

Summarize market report.

### Procurement Intelligence

Combine internal and external sources.

---

# 56. AI Tool Orchestration

AI Assistant sebaiknya menggunakan:

**planner → tool calls → synthesis**

Contoh:

User:

> Is now a good time to purchase OCTG?

Planner identifies:

1. demand;
2. inventory;
3. open PO;
4. historical price;
5. historical RFI;
6. market index.

Kemudian memanggil tools yang diperlukan.

---

# 57. Source Priority

Default intelligence priority:

1. Approved internal master data.
2. Internal MCP transaction data.
3. Approved RFI response.
4. Approved market intelligence report.
5. Licensed external intelligence.
6. Analyst input.
7. AI inference.

AI inference harus diberi label:

**AI Assessment**

dan bukan dianggap data source.

---

# 58. Confidence Indicator

AI answer dapat mempunyai:

**High Confidence**

Multiple validated sources.

**Medium Confidence**

Limited or older source.

**Low Confidence**

Insufficient supporting information.

---

# 59. Freshness Indicator

Setiap insight harus memungkinkan user melihat:

- data date;
- source date;
- indexed date;
- last refresh.

Contoh:

> Inventory: refreshed 08 Sep 2026 06:00 WIB.

---

# 60. AI Conversation Workspace

Conversation disimpan sebagai workspace.

User dapat:

- rename conversation;
- pin;
- archive;
- share internally subject to permission;
- export result.

Conversation dapat mempunyai context:

- category;
- supplier;
- RFI;
- project.

---

# 61. Suggested AI Queries

Homepage dapat menampilkan:

- Compare latest prices against historical PO.
- Show suppliers for this category.
- Find similar RFI.
- Generate an RFI.
- Analyze current inventory against demand.
- Summarize market risk.
- Compare supplier responses.

---

# 62. Functional Architecture

Recommended application architecture:

```text
                         USER
                           │
                    React Frontend
                           │
                       HTTPS
                           │
                        NGINX
                           │
                    FastAPI Backend
                           │
       ┌───────────────────┼────────────────────┐
       │                   │                    │
       ▼                   ▼                    ▼
 Market Intelligence   RFI Service        AI Orchestrator
       │                   │                    │
       │                   │             ┌──────┴───────┐
       │                   │             │              │
       ▼                   ▼             ▼              ▼
 PostgreSQL            PostgreSQL   Repository RAG   MCP Client
       │                   │             │              │
       │                   │             │              ▼
       │                   │             │       Internal MCP
       │                   │             │              │
       │                   │             │       Enterprise DB
       │                   │             │
       │                   │             ▼
       │                   │        Azure OpenAI
       │                   │
       └──────────────┬────┘
                      ▼
                Object Storage
                  / File Store
```

---

# 63. Recommended Technology Stack

## Backend

Python **3.12** as production baseline.

Python 3.11 supported.

Framework:

**FastAPI**

Recommended components:

- FastAPI;
- Pydantic;
- SQLAlchemy;
- Alembic;
- psycopg;
- httpx.

---

# 64. Frontend

React + TypeScript.

Recommended:

- React;
- TypeScript;
- Vite;
- React Router;
- TanStack Query;
- component library such as Material UI.

State separation:

Server state → TanStack Query.

UI state → lightweight local store.

---

# 65. Database

PostgreSQL.

Extensions:

`pgvector`

Recommended additional capabilities:

- full-text search;
- JSONB;
- Row Level Security where useful.

---

# 66. File Storage

Large files jangan disimpan sebagai PostgreSQL BLOB.

Use:

### MVP

Server filesystem.

Example:

`/srv/market-intelligence/files`

### Enterprise

S3-compatible object storage / enterprise object store.

Database menyimpan metadata dan object reference.

---

# 67. Background Processing

Heavy jobs tidak berjalan di HTTP request.

Contoh:

- document parsing;
- embedding;
- directory indexing;
- bulk import;
- report generation.

Recommended architecture:

API

↓

Task Queue

↓

Worker.

Redis dapat digunakan sebagai queue/cache infrastructure.

Alternative queue implementation dapat ditentukan pada technical design.

---

# 68. Backend Modules

Suggested Python structure:

```text
app/
  api/
  auth/
  users/
  market/
  suppliers/
  rfi/
  repository/
  ingestion/
  ai/
  mcp/
  analytics/
  administration/
  audit/
  common/
```

---

# 69. PostgreSQL Logical Schema

Recommended logical separation:

`iam`

`market`

`rfi`

`repository`

`ai`

`integration`

`audit`

---

# 70. Core Database Entities

## IAM

`users`

`roles`

`permissions`

`user_roles`

`role_permissions`

`organizational_units`

`user_data_scopes`

---

## Market

`categories`

`commodities`

`suppliers`

`supplier_categories`

`market_data_sources`

`price_series`

`price_points`

`market_events`

`market_reports`

---

## RFI

`rfis`

`rfi_versions`

`rfi_sections`

`rfi_questions`

`rfi_suppliers`

`rfi_invitations`

`rfi_responses`

`rfi_response_items`

`rfi_clarifications`

`rfi_evaluations`

`rfi_status_history`

---

## Repository

`documents`

`document_versions`

`document_chunks`

`document_entities`

`ingestion_sources`

`ingestion_jobs`

`ingestion_errors`

---

## AI

`ai_provider_configs`

`ai_model_registry`

`prompt_templates`

`prompt_versions`

`conversations`

`messages`

`ai_runs`

`tool_calls`

`citations`

`ai_feedback`

---

## Integration

`mcp_servers`

`mcp_tools`

`mcp_access_policies`

`external_sources`

---

## Audit

`audit_events`

---

# 71. Example RFI Entity

Fields:

`id`

`rfi_number`

`title`

`category_id`

`requesting_function`

`buyer_id`

`analyst_id`

`purpose`

`business_requirement`

`status`

`issue_date`

`closing_date`

`confidentiality`

`created_by`

`created_at`

`updated_at`

---

# 72. Example Document Entity

Fields:

`id`

`document_type`

`original_filename`

`storage_uri`

`source_path`

`mime_type`

`checksum_sha256`

`category_id`

`rfi_id`

`supplier_id`

`security_classification`

`document_date`

`indexed_at`

`index_status`

---

# 73. REST API

Backend API versioned.

Base:

`/api/v1/`

Examples:

### RFI

`GET /rfis`

`POST /rfis`

`GET /rfis/{id}`

`PUT /rfis/{id}`

`POST /rfis/{id}/issue`

`POST /rfis/{id}/close`

`GET /rfis/{id}/responses`

`POST /rfis/{id}/analyze`

---

### Supplier

`GET /suppliers`

`GET /suppliers/{id}`

`GET /suppliers/{id}/history`

---

### Market

`GET /market/categories/{id}`

`GET /market/prices`

`GET /market/events`

---

### Repository

`POST /repository/search`

`POST /repository/index`

`GET /repository/documents`

---

### AI

`POST /ai/chat`

`POST /ai/rfi/generate`

`POST /ai/rfi/compare`

`POST /ai/market/analyze`

---

### Admin

`GET /admin/ai-config`

`PUT /admin/ai-config`

`POST /admin/ai-config/test`

`GET /admin/indexing`

---

# 74. Authentication

Recommended enterprise architecture:

OAuth2/OIDC capable.

Initial implementation dapat menggunakan secure enterprise identity provider.

Application session:

short-lived access token

+

controlled refresh session.

---

# 75. Authorization

Gunakan:

**RBAC + Data Scope**

RBAC menjawab:

> What can this user do?

Data Scope menjawab:

> Which data can this user access?

Contoh:

Buyer dapat melihat PO.

Tetapi hanya:

Region 2.

---

# 76. Security Classification

Documents dapat diberi:

PUBLIC INTERNAL

INTERNAL

CONFIDENTIAL

RESTRICTED

Access inheritance harus mengikuti classification.

---

# 77. Prompt Injection Protection

Historical documents dan supplier documents merupakan untrusted content.

Instruksi di dalam document seperti:

> Ignore previous instructions...

tidak boleh dieksekusi.

Document selalu diperlakukan sebagai:

**data**, bukan system instruction.

---

# 78. AI Security Boundaries

LLM tidak boleh menerima:

- database credentials;
- API keys;
- connection strings;
- unrestricted filesystem paths;
- arbitrary shell access.

MCP menjadi controlled data access layer.

---

# 79. Audit

Minimum audited events:

- login;
- logout;
- failed login;
- document view;
- document download;
- RFI create;
- RFI edit;
- RFI issue;
- supplier response;
- RFI close;
- AI request;
- AI tool call;
- admin config;
- model change;
- permission change;
- indexing job.

---

# 80. AI Audit

Setiap AI Run mempunyai:

`run_id`

`user_id`

`conversation_id`

`model`

`prompt_version`

`input_hash`

`retrieved_documents`

`tool_calls`

`output`

`token_usage`

`latency`

`timestamp`

---

# 81. AI Feedback

User dapat memberikan:

👍 Useful

👎 Not useful

Optional reason:

- incorrect;
- insufficient source;
- outdated;
- hallucination;
- irrelevant;
- missing data.

Data digunakan untuk AI quality evaluation.

---

# 82. Analytics Module

Dashboard minimum:

### RFI Analytics

- number of RFI;
- RFI/category;
- cycle status;
- response rate;
- suppliers/RFI.

### Market Analytics

- price trend;
- volatility;
- market event count;
- supplier landscape.

### Procurement Intelligence

- historical spend;
- price variance;
- lead-time trend;
- demand vs inventory.

### Knowledge Analytics

- indexed documents;
- search usage;
- top categories;
- failed ingestion.

---

# 83. Market Intelligence Workspace

Analyst dapat membuat workspace.

Contoh:

**2027 OCTG Market Outlook**

Workspace mengandung:

- charts;
- saved searches;
- RFI;
- suppliers;
- reports;
- notes;
- AI conversation;
- datasets.

Workspace dapat di-share ke authorized users.

---

# 84. Saved Intelligence View

User dapat menyimpan filter/query.

Contoh:

**ASEAN OCTG Suppliers**

Filters:

Category: OCTG

Region: ASEAN

Supplier type: Manufacturer

RFI participation: Last 3 years.

---

# 85. Alert Engine

Recommended enhancement setelah MVP.

Alert example:

> Latest supplier indication is >10% above historical benchmark.

> Average lead time increased >20%.

> Inventory coverage <3 months.

> New market report indexed for Category X.

---

# 86. AI Market Brief

System dapat menghasilkan:

**Market Intelligence Brief**

### Market Situation

### Demand Outlook

### Supply Outlook

### Price Trend

### Supplier Landscape

### Internal Position

### Risks

### Opportunities

### Recommended Procurement Action

Semua section mempunyai citations.

---

# 87. Intelligence Scorecard

Future analytical feature.

Example:

### Supply Risk

High

### Price Risk

Medium

### Demand Pressure

High

### Supplier Competition

Low

### Inventory Coverage

Medium

Output:

**Procurement Market Position**

SELLER ADVANTAGE

atau:

BUYER ADVANTAGE.

---

# 88. Should-Cost Capability

Phase lanjutan.

Should cost dapat menghubungkan:

Raw Material

+

Labor

+

Energy

+

Logistics

+

FX

+

Supplier Margin.

User dapat membuat cost model per category.

---

# 89. Data Ingestion Framework

Semua datasource harus mempunyai common ingestion contract:

Source

↓

Extract

↓

Validate

↓

Normalize

↓

Store

↓

Index

↓

Publish.

Status:

PENDING

PROCESSING

VALIDATING

COMPLETED

FAILED

---

# 90. Data Quality

Setiap dataset memiliki:

- source;
- owner;
- last refresh;
- completeness;
- validity;
- freshness.

Data tanpa source tidak boleh dianggap authoritative.

---

# 91. RFI Versioning

RFI harus versioned.

Contoh:

RFI v1.

Review.

RFI v2.

Issued.

Setelah issue:

questionnaire locked.

Perubahan → amendment version.

---

# 92. Document Versioning

File dengan path sama tetapi checksum berubah:

Document

↓

Version 1

Version 2

Version 3.

Semantic index menunjuk version terbaru secara default.

Historical version tetap tersedia.

---

# 93. Search Filters

Minimum:

- category;
- year;
- supplier;
- RFI;
- document type;
- geography;
- organizational unit;
- file type;
- confidentiality;
- source.

---

# 94. Search Result

Result card:

**RFI-2025-0041 — Gas Compressor**

Supplier A Response

2025

Match: 92%

Snippet:

“Manufacturing lead time is approximately...”

Buttons:

Open

Ask AI

Related Documents.

---

# 95. Related Intelligence

Untuk setiap document:

System menampilkan:

**Related RFI**

**Related Suppliers**

**Related PO**

**Related Market Reports**

**Related Categories**

berdasarkan metadata + semantic similarity.

---

# 96. UI Information Architecture

Primary navigation:

**Home**

**Ask Intelligence**

**Market Intelligence**

**RFI**

**Suppliers**

**Repository**

**Analytics**

**Administration**

Admin menu hanya muncul sesuai permission.

---

# 97. RFI Workspace UI

Header:

RFI Number  
Status  
Owner  
Closing Date

Tabs:

Overview

Questions

Suppliers

Responses

Comparison

Clarification

AI Analysis

Documents

Activity

---

# 98. Market Intelligence UI

Category page:

Overview

Price

Demand

Internal Spend

Suppliers

Historical RFI

Market Events

Reports

AI Insights

---

# 99. Responsive Design

Primary use:

Desktop.

Minimum support:

Laptop and tablet.

Mobile:

read/review oriented.

Complex analyst workflows tidak perlu dioptimalkan penuh untuk mobile pada MVP.

---

# 100. Non-Functional Requirements

## Performance

Typical API:

P95 < 2 seconds excluding AI/external integrations.

Search:

P95 < 3 seconds.

Dashboard:

initial usable view < 5 seconds pada corporate network.

AI:

stream response agar user melihat hasil secara progresif.

---

# 101. Scalability

Initial design target harus mendukung pertumbuhan tanpa major rearchitecture.

Indicative architecture:

100k+ documents.

Millions of document chunks.

Millions of transaction references.

Hundreds of concurrent internal users.

Scale dilakukan melalui:

- PostgreSQL optimization;
- connection pooling;
- workers;
- caching;
- read replicas;
- horizontal backend instances.

---

# 102. Availability

Services harus stateless sebisa mungkin.

Frontend tidak menyimpan critical state.

Application sessions dan persistent data berada di backend/database.

---

# 103. Backup

Minimum:

PostgreSQL daily backup.

Point-in-time recovery recommended.

File/object storage backup.

Configuration backup.

Periodic restore test.

---

# 104. Observability

Application harus mempunyai:

### Logs

Structured logs.

### Metrics

CPU

Memory

API latency

DB connection

AI latency

AI errors

MCP failures

Index queue.

### Health endpoints

`/health/live`

`/health/ready`

---

# 105. Correlation ID

Setiap request mempunyai:

`correlation_id`

yang diteruskan ke:

API

AI run

MCP call

background job

audit log.

Mempermudah troubleshooting.

---

# 106. Development Environment

macOS.

Recommended:

Python 3.12 virtual environment.

Node.js LTS.

Local PostgreSQL.

pgvector.

Frontend dev server.

Backend dev server.

Configuration menggunakan:

`.env`

untuk local development.

Secrets tidak committed ke Git.

---

# 107. Production Environment

Ubuntu Server 24.04 LTS.

Recommended structure:

NGINX

↓

React static build

+

FastAPI service.

Backend dijalankan sebagai managed system service.

Workers dijalankan sebagai separate service.

PostgreSQL dapat:

- berada di server tersendiri;
- atau managed enterprise PostgreSQL.

Production sebaiknya memisahkan DB dari application host jika scale/security membutuhkannya.

---

# 108. Production Directory Example

```text
/srv/market-intelligence/
  backend/
  frontend/
  uploads/
  repository/
  logs/
  temp/
```

---

# 109. CI/CD

Repository minimum:

`main`

`develop`

feature branches.

Pipeline:

Lint

↓

Unit Test

↓

Build

↓

Security Scan

↓

Deploy Staging

↓

Acceptance

↓

Production.

---

# 110. Testing Strategy

### Unit Tests

Business rules.

### API Tests

Endpoint behavior.

### Integration Tests

PostgreSQL.

Azure OpenAI.

MCP.

### RAG Evaluation

Retrieval relevance.

Citation correctness.

### Security Tests

Authorization.

Data isolation.

### End-to-End Tests

React → backend → database.

---

# 111. AI Evaluation Dataset

Sebelum production, buat golden question dataset.

Contoh:

> What was our average price for Material X in 2025?

Known answer disimpan.

System kemudian dievaluasi:

- correct data?
- correct citation?
- correct calculation?
- correct authorization?

---

# 112. AI Quality Metrics

Minimum:

Retrieval precision.

Citation accuracy.

Answer groundedness.

Tool-call success.

User acceptance.

Hallucination rate.

Response latency.

---

# 113. Data Leakage Test

Wajib mempunyai negative authorization tests.

Contoh:

Region A user bertanya:

> Show Region B purchase prices.

Expected:

**Access denied / insufficient authorization.**

Model tidak boleh menerima data Region B sejak awal.

---

# 114. MVP Scope

MVP harus fokus pada fondasi yang memberikan nilai langsung.

### Included

Authentication.

4 internal roles.

RBAC.

Category taxonomy.

Supplier master.

RFI creation.

RFI template.

Supplier invitation.

Supplier response.

RFI comparison.

Historical RFI repository.

Directory indexing.

Document extraction.

Semantic search.

PostgreSQL + pgvector.

Azure OpenAI admin configuration.

AI chat.

RAG.

Internal MCP.

Demand tool.

PO tool.

Inventory tool.

Audit.

Basic analytics.

---

# 115. Phase 2

Tambahkan:

Market price series.

Market events.

Supplier landscape.

Market research workspace.

Advanced RFI AI analysis.

Alert engine.

External market intelligence API.

Automated intelligence brief.

Advanced dashboards.

---

# 116. Phase 3

Tambahkan:

Supplier Portal.

Should-cost modeling.

Price forecasting.

Advanced supplier risk.

Scenario analysis.

Procurement recommendation engine.

External MCP.

Enterprise workflow integrations.

---

# 117. Phase 4

Target evolution:

**Autonomous Market Intelligence Agent**

Agent secara periodik mengevaluasi:

Demand

Inventory

PO

RFI

Market Data

Supplier Data

Price

Market Events.

Agent kemudian menemukan:

**What changed?**

dan mengirimkan intelligence alert.

Contoh:

> OCTG procurement risk has increased from Medium to High because projected demand increased by 18%, inventory coverage dropped to 2.3 months, and supplier lead time increased by 25%.

---

# 118. Success Metrics

## RFI Efficiency

RFI preparation effort reduction.

Historical RFI reuse rate.

Supplier response rate.

---

## Intelligence

Percentage of sourcing decisions supported by market intelligence.

Number of active intelligence categories.

Search success rate.

---

## Procurement

Price benchmark utilization.

Number of sourcing activities using historical intelligence.

Identified cost avoidance/opportunity.

---

## AI

AI recommendation acceptance rate.

Citation accuracy.

AI answer satisfaction.

Tool-call success rate.

---

# 119. Key Product Risks

## Risk 1 — AI Hallucination

Mitigation:

grounded RAG + citations + MCP.

---

## Risk 2 — Sensitive Data Leakage

Mitigation:

RBAC + data scope + MCP enforcement.

---

## Risk 3 — Incorrect Historical Documents

Mitigation:

source classification + analyst verification.

---

## Risk 4 — Poor Metadata

Mitigation:

AI extraction + confidence score + human review.

---

## Risk 5 — Arbitrary Database Access

Mitigation:

parameterized MCP tools.

Never expose unrestricted SQL.

---

## Risk 6 — Old Market Information

Mitigation:

freshness metadata.

---

## Risk 7 — Excessive LLM Cost

Mitigation:

model routing.

Caching.

Prompt optimization.

Retrieval before generation.

---

# 120. Product Decisions Recommended

Several architectural decisions should be fixed from the beginning.

### Decision 1

**Python 3.12 as canonical runtime.**

Support 3.11 only for compatibility.

Do not run mixed Python versions across production services.

### Decision 2

**FastAPI as backend.**

### Decision 3

**React + TypeScript as frontend.**

### Decision 4

**PostgreSQL + pgvector as primary and vector database.**

Avoid introducing a separate vector database until volume proves it necessary.

### Decision 5

**MCP is the only AI-facing interface for transactional enterprise data.**

### Decision 6

**Do not expose generic SQL tool to LLM.**

### Decision 7

**AI configurations are stored dynamically, not hardcoded.**

### Decision 8

**Azure credentials are encrypted and never returned to frontend.**

### Decision 9

**Historical RFI becomes knowledge automatically after completion.**

### Decision 10

**Every AI conclusion needs traceable evidence.**

---

# 121. Target End-to-End Scenario

User enters:

> We plan to procure 40 units of gas engines next year. Give me market intelligence and determine whether we should issue a new RFI.

System executes:

### Step 1 — Demand MCP

Retrieve historical and future demand.

### Step 2 — Inventory MCP

Retrieve current inventory.

### Step 3 — PO MCP

Retrieve historical purchases.

### Step 4 — Repository

Find previous gas engine RFI.

### Step 5 — Supplier Intelligence

Retrieve historical suppliers.

### Step 6 — Market Intelligence

Retrieve latest analyst report and market events.

### Step 7 — AI Analysis

Analyze all data.

Output:

**Demand Position**

40 units projected.

**Inventory**

8 units available.

**Open PO**

5 units.

**Supply Gap**

27 units.

**Historical Price**

USD X.

**Latest RFI**

18 months old.

**Historical Lead Time**

32 weeks.

**Market Condition**

Lead time increasing.

**Recommendation**

> Issue a new RFI because the previous market information is no longer sufficiently current and projected demand materially exceeds available inventory and confirmed incoming supply.

**Suggested Suppliers**

Supplier A  
Supplier B  
Supplier C

**Suggested RFI Scope**

Capacity

Price indication

Lead time

Manufacturing slot

Warranty

Localization

Service support.

Button:

**Create RFI from Recommendation**

---

# 122. Target Strategic Architecture

Ultimately, the platform should evolve into:

```text
                     AI MARKET INTELLIGENCE
                              │
             ┌────────────────┼─────────────────┐
             │                │                 │
             ▼                ▼                 ▼
      MARKET KNOWLEDGE   INTERNAL DATA      RFI MARKET
             │                │                 │
        Reports/Data         MCP             Suppliers
        Price Index          │               Responses
        Market Event         │               Capability
             │               │                 │
             └───────────────┼─────────────────┘
                             ▼
                     INTELLIGENCE GRAPH
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
             PRICE        SUPPLY        DEMAND
          INTELLIGENCE   INTELLIGENCE  INTELLIGENCE
                │            │            │
                └────────────┼────────────┘
                             ▼
                     DECISION ENGINE
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           RFI ACTION    SOURCING ACTION   MARKET ALERT
```

---

# 123. Product Differentiation

Platform ini tidak hanya menjadi:

**RFI Repository**

dan bukan hanya:

**Market Intelligence Dashboard**

dan bukan hanya:

**Enterprise Chatbot.**

Keunggulan utamanya adalah menghubungkan:

**External Market Intelligence**

+

**Supplier Market Intelligence**

+

**Historical RFI**

+

**Internal Demand**

+

**Internal Inventory**

+

**Historical PO**

+

**Enterprise Knowledge**

+

**AI Reasoning**

sehingga menciptakan:

# Procurement Decision Intelligence

---

# 124. Definition of Done for Initial Product

Initial product dianggap berhasil ketika authorized user dapat melakukan workflow berikut dalam satu aplikasi:

**Ask**

“Find our previous RFI for centrifugal compressor.”

↓

**Retrieve**

RFI dan supplier responses.

↓

**Analyze**

Historical supplier information.

↓

**Connect**

PO + demand + inventory melalui MCP.

↓

**Generate**

New RFI draft.

↓

**Review**

Buyer review.

↓

**Issue**

RFI ke supplier.

↓

**Collect**

Supplier responses.

↓

**Compare**

Responses menggunakan AI + structured comparison.

↓

**Conclude**

Market intelligence summary.

↓

**Archive**

RFI otomatis menjadi bagian dari institutional knowledge.

Dengan demikian terbentuk closed intelligence loop:

**Demand → Research → RFI → Supplier Information → Procurement → Historical Data → New Intelligence.**

---

# 125. Final Product Objective

Tujuan akhir aplikasi adalah mengubah procurement intelligence dari kondisi:

**fragmented**

**document-based**

**person-dependent**

**reactive**

menjadi:

**centralized**

**data-driven**

**institutionalized**

**AI-assisted**

**traceable**

**proactive**

sehingga knowledge mengenai harga, supplier, demand, inventory, historical procurement dan kondisi pasar tidak hilang ketika personel berubah dan dapat terus digunakan untuk pengambilan keputusan procurement berikutnya.