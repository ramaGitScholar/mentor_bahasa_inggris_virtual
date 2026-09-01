# Mentor Bahasa Inggris Virtual

Bot mentor bahasa Inggris berbasis AI (Google Gemini) untuk pembelajar Indonesia.
Pengguna berinteraksi lewat **Telegram** (atau CLI untuk pengembangan) dan bisa:

- Meminta latihan **reading, writing, listening, speaking** — agen memilih jenis latihan yang tepat secara otomatis.
- Mengirim kalimat bahasa Inggris untuk **diperiksa grammar-nya**.
- Meminta **tips belajar**.
- Mengirim **voice note** untuk dievaluasi pelafalannya (speaking).
- Ngobrol bebas untuk melatih writing/speaking.
- Membuat **laporan belajar mingguan** dalam bentuk PDF.
- Menerima **pengingat latihan harian** otomatis.

Latihan listening menghasilkan file audio (TTS dua pembicara) yang dikirim sebagai lampiran.

---

## Arsitektur singkat

```
Telegram / CLI
      │
      ▼
src/app.py (handler Telegram)  ── src/app_cli.py (REPL untuk dev)
      │
      ▼
src/agents/lead.py  ── LeadAgent: kelola history, panggil Gemini + tools
      │
      ├── src/agents/services.py   fungsi tool: klasifikasi skill, generate latihan,
      │                            evaluasi writing/speaking, generate report, TTS listening
      ├── src/core/llm.py          client Gemini
      ├── src/core/prompts.py      loader system instruction (src/agents/instructions/*.md)
      ├── src/core/schemas.py      schema Pydantic untuk output terstruktur
      ├── src/core/artifacts.py    "keranjang" file hasil generate (audio/pdf) per request
      └── src/repository/chat_repository.py  simpan/ambil data ke Supabase
                    │
                    ▼
              Supabase (Postgres): tabel chat_users, chat_histories
```

File output (audio & PDF laporan) ditulis ke `src/output/`, file voice note sementara ke `src/temp/`.

---

## Prasyarat

| Kebutuhan | Keterangan |
|-----------|------------|
| Python | 3.10+ (lihat `.python-version`) |
| [uv](https://docs.astral.sh/uv/) | package & environment manager yang dipakai proyek ini |
| Google Gemini API key | dari [Google AI Studio](https://aistudio.google.com/apikey) |
| Proyek Supabase | URL + anon/service key |
| Bot Telegram | token dari [@BotFather](https://t.me/BotFather) |

---

## Setup

### 1. Clone & install dependency

```bash
git clone https://github.com/ramaGitScholar/mentor_bahasa_inggris_virtual.git
cd mentor_bahasa_inggris_virtual
uv sync
```

`uv sync` membuat virtual environment `.venv/` dan meng-install semua dependency dari `uv.lock`.

### 2. Siapkan file `.env`

Salin contoh lalu isi nilainya:

```bash
cp .env.example .env
```

| Variabel | Contoh / keterangan |
|----------|---------------------|
| `GEMINI_API_KEY` | API key Google Gemini |
| `GEMINI_MODEL` | model teks, mis. `gemini-2.5-flash` |
| `GEMINI_MODEL_TTS` | model text-to-speech, mis. `gemini-2.5-flash-preview-tts` |
| `SUPABASE_URL` | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | anon/service key Supabase |
| `TELEGRAM_BOT_TOKEN` | token dari BotFather |

Semua variabel di atas **wajib** — aplikasi akan gagal start (`RuntimeError: env variabel ... belum di-set`) jika ada yang kosong.

> `.env` sudah masuk `.gitignore`. Jangan pernah commit kredensial asli.

### 3. Siapkan tabel Supabase

Jalankan SQL berikut di **SQL Editor** Supabase:

```sql
create table if not exists chat_users (
    user_id    bigint primary key,
    username   text,
    chat_id    bigint,
    created_at timestamptz not null default now()
);

create table if not exists chat_histories (
    id           bigint generated always as identity primary key,
    user_id      bigint not null,
    role         text   not null check (role in ('user', 'model')),
    message_text text,
    artifact     text,
    created_at   timestamptz not null default now()
);

create index if not exists idx_chat_histories_user_created
    on chat_histories (user_id, created_at);
```

---

## Menjalankan

### Mode Telegram (utama)

```bash
uv run main.py
```

Bot akan mulai polling. Buka chat bot di Telegram, lalu:

| Perintah | Fungsi |
|----------|--------|
| `/start` | daftarkan akun & tampilkan panduan |
| `/report` | buat laporan belajar 7 hari terakhir (PDF) |
| kirim teks | latihan / koreksi / tips / ngobrol |
| kirim voice note | evaluasi pelafalan (speaking) |

Pengingat latihan harian dikirim otomatis setiap hari pukul **10:03 WIB** (`Asia/Jakarta`) ke semua user terdaftar. Ubah di `src/app.py` (`target_time` pada fungsi `run`).

### Mode CLI (pengembangan / uji cepat)

Berguna untuk mencoba `LeadAgent` tanpa Telegram (tetap butuh Supabase & Gemini):

```bash
uv run python -c "import src.app_cli as cli; cli.run()"
```

Ketik pesan pada prompt `[user]:`, ketik `/exit` untuk keluar.

---

## Struktur folder

```
main.py                     entrypoint bot Telegram
src/
├── app.py                   handler & routing Telegram, job pengingat, error handler
├── app_cli.py               REPL CLI
├── agents/
│   ├── lead.py              LeadAgent (orkestrasi Gemini + function calling)
│   ├── services.py          implementasi tool & generator latihan/laporan
│   └── instructions/        system prompt tiap agen (*.md)
├── core/
│   ├── env.py               load & validasi environment variable + path
│   ├── llm.py               client Gemini (cached)
│   ├── supabase.py          client Supabase (cached)
│   ├── prompts.py           loader file instruksi
│   ├── schemas.py           schema Pydantic output terstruktur
│   ├── artifacts.py         pengumpul file hasil generate per request
│   └── format.py            konversi Markdown → Telegram MarkdownV2
├── repository/
│   └── chat_repository.py   akses tabel chat_users & chat_histories
├── output/                  hasil generate (audio .wav, laporan .pdf) — dibuat otomatis
└── temp/                    voice note sementara — dibuat otomatis
```

---

## Cara kerja function calling

`LeadAgent` mendaftarkan tiga tool ke Gemini (automatic function calling):

| Tool | Kapan dipanggil |
|------|-----------------|
| `skill_type_classification` | user minta latihan; menentukan reading/writing/listening/speaking lalu men-generate latihan |
| `evaluate_writing` | user mengirim kalimat Inggris untuk diperiksa |
| `get_learning_tip` | user minta tips belajar |

Evaluasi speaking (`evaluate_speaking`) dan pembuatan laporan (`generate_report`) dipanggil langsung oleh handler, bukan lewat model.

---

## Troubleshooting

| Gejala | Penyebab / solusi |
|--------|-------------------|
| `RuntimeError: env variabel ... belum di-set` | ada variabel `.env` yang kosong |
| `FileNotFoundError: File instruksi tidak ditemukan` | file `.md` di `src/agents/instructions/` hilang atau salah nama |
| Balasan "Mentor sedang sibuk ... kuota ... penuh" | rate limit Gemini (HTTP 429), coba lagi nanti |
| Error tabel / kolom dari Supabase | tabel belum dibuat (lihat langkah 3) |

---

## Lisensi

MIT — lihat [LICENSE](LICENSE).
