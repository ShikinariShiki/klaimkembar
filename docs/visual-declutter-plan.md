# Visual Declutter & Whitespace Redesign Plan: KlaimKembar Landing Page

**Target File:** `/home/shiki/.gemini/antigravity/scratch/klaimkembar/frontend/landing.html`  
**Executor:** Subagent C  
**Design Reference:** Apple Pro Editorial (`apple.com/id`) + High-End Agency Soft UI (`design-aesthetic-and-brand-engine`)  
**Core Objective:** Menghilangkan kesan kaku, "super baku / scientific abstract", dan "wall of text" pada antarmuka publik, menggantikannya dengan tata letak lapang (visual whitespace), tipografi bernapas, angka tipografis besar (giant stats), dan interaksi bersih tanpa mengurangi keabsahan teknis sistem.

---

## 1. Diagnosis Visual & Akar Masalah

Saat ini, `landing.html` memindahkan seluruh muatan riset akademis dan spesifikasi PRD secara mentah ke atas layar:
1. **Hero Section (Above the Fold):** Kolom kiri memuat badge panjang, headline besar, paragraf pengantar 5 baris, 4 kotak metrik bertumpuk (`.stat-box`) dengan 3 baris teks di tiap kotak, serta tabel perbandingan kasus 5 baris dengan keterangan warna. Total tinggi kolom kiri melebihi 1.200px, menciptakan kemacetan visual parah tepat di samping kartu login.
2. **Section `#sorotan`:** Kartu-kartu sorotan menyerupai abstrak jurnal ilmiah dengan 3–4 kalimat per paragraf ditambah catatan kaki panjang, menenggelamkan metrik utama yang seharusnya menonjol.
3. **Section `#arsitektur` (Scrollytelling):** Kolom kiri menggunakan kartu berbingkai tebal dengan 3 blok teks panjang, 6 chip bertumpuk, dan callout bergradasi. Langkah yang tidak aktif tetap terasa berat, mengaburkan hierarki penceritaan vertikal.
4. **Section `#evaluasi`:** Kolom kiri dipenuhi evaluasi multi-paragraf di bawah setiap progress bar; kolom kanan memuat penjelasan panjang mengenai kriptografi dan regulasi yang membuat pembaca enggan menelaah.

---

## 2. Rencana Eksekusi Terperinci (Section-by-Section)

### A. Hero Section: Napas Visual & Pemadatan Above the Fold

#### 1. Hirarki Kolom Kiri Baru
Gantikan tumpukan vertikal yang padat dengan urutan 5 elemen bernapas:
1. **Subtle Pill Badge:**
   ```html
   <div class="hero-badge">
     <span class="badge-dot"></span>
     BPJS Kesehatan Healthkathon 2026
   </div>
   ```
2. **Short 2-Line Display Headline:**
   ```html
   <h1 class="hero-headline">
     <span class="tone-ink">Telaah klaim ganda.</span><br>
     <span class="tone-muted">Lindungi terapi rutin pasien.</span>
   </h1>
   ```
3. **Short 2-Line Subtitle (`max-width: 48ch`):**
   ```html
   <p class="hero-subtitle">
     Sistem pra-audit hibrida yang memisahkan duplikasi administratif dari jadwal perawatan fisioterapi berkala secara presisi.
   </p>
   ```
4. **Clean Inline 4-Stat Strip (Gantikan 4 Kotak Berat):**
   Hapus grid 4 `.stat-box` yang berat. Gunakan pita horizontal borderless / ultra-light pill row:
   ```html
   <div class="hero-stat-strip">
     <div class="strip-item">
       <span class="strip-val mono green-text">91,5%</span>
       <span class="strip-lbl">F1 Sintetis</span>
     </div>
     <div class="strip-divider"></div>
     <div class="strip-item">
       <span class="strip-val mono green-text">96,1%</span>
       <span class="strip-lbl">F1 BPJS</span>
     </div>
     <div class="strip-divider"></div>
     <div class="strip-item">
       <span class="strip-val mono">87,2%</span>
       <span class="strip-lbl">Reduksi FP</span>
     </div>
     <div class="strip-divider"></div>
     <div class="strip-item">
       <span class="strip-val mono primary-text">0</span>
       <span class="strip-lbl">Label Fraud</span>
     </div>
   </div>
   ```
5. **Compact Visual Case Preview Card (Hanya 3 Baris Kunci):**
   Sederhanakan tabel perbandingan dari 5 baris menjadi 3 baris berdampak tinggi (`Peserta`, `Tindakan`, `Nilai Klaim`), serta buang teks penjelas yang berlebihan:
   ```html
   <div class="interactive-preview" id="hero-preview-card">
     <div class="preview-badge-row">
       <div class="tags">
         <span class="pill high">Prioritas Telaah</span>
         <span class="pill">SYN-7F3A92D1</span>
       </div>
       <div class="preview-ml-badge mono">
         Skor Hibrida: 84,0
       </div>
     </div>

     <div class="compact-case-grid">
       <div class="case-data-col">
         <span class="case-field-title">PESERTA</span>
         <span class="case-field-val mono">000182947192</span>
         <span class="field-status same">Identik (Pasien Sama)</span>
       </div>
       <div class="case-data-col">
         <span class="case-field-title">TINDAKAN</span>
         <span class="case-field-val">Fisioterapi (93.39)</span>
         <span class="field-status same">Identik di Hari Sama</span>
       </div>
       <div class="case-data-col">
         <span class="case-field-title">NILAI KLAIM</span>
         <span class="case-field-val mono">Rp 185.000</span>
         <span class="field-status same">Nilai Sama</span>
       </div>
     </div>
   </div>
   ```

#### 2. CSS yang Perlu Diperbarui
- `.hero-headline`: `font-size: clamp(34px, 4vw, 54px); line-height: 1.1; margin-bottom: 16px;`
- `.hero-subtitle`: `max-width: 46ch; font-size: 17px; line-height: 1.5; color: var(--text-muted); margin-bottom: 24px;`
- `.hero-stat-strip`:
  ```css
  .hero-stat-strip {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 18px;
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 980px;
    width: fit-content;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(30, 34, 66, 0.03);
  }
  .strip-item {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }
  .strip-val {
    font-size: 17px;
    font-weight: 800;
  }
  .strip-lbl {
    font-size: 11.5px;
    color: var(--text-muted);
    font-weight: 600;
  }
  .strip-divider {
    width: 1px;
    height: 14px;
    background: var(--border);
  }
  ```
- `.compact-case-grid`:
  ```css
  .compact-case-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    background: #fafbfe;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 14px 16px;
  }
  .case-data-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .case-field-title {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.05em;
  }
  .case-field-val {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-ink);
  }
  .field-status.same {
    font-size: 11px;
    color: var(--red);
    font-weight: 600;
  }
  ```

---

### B. Section `#sorotan`: Kartu Produk ala Apple, Bukan Abstrak Riset

#### 1. Perubahan Struktur Kartu
Setiap kartu di `#sorotan` diubah menjadi kartu produk minimalis dengan:
- **Padding Lapang:** `36px 32px`
- **Atas:** Badge kategori + Judul singkat maksimal **2 baris**.
- **Bawah:** Angka tipografis raksasa (`clamp(48px, 5vw, 68px)`) + subjudul metrik 1 baris.
- **Hapus Total:** Seluruh paragraf penjelasan panjang (`.card-body`) dan footer berikon (`.card-footer`).

#### 2. Spesifikasi Konten 4 Kartu
- **Kartu 1 (Reduksi FP):**
  - Badge: `Pencegahan Salah Tuduh`
  - Headline: `Pangkas alarm keliru.<br>Amankan arus klaim.`
  - Giant Stat: `87,2%` (warna: `var(--green)`)
  - Subtext: `Penurunan False Positive per 1.000 klaim (menjadi 6,36)`
- **Kartu 2 (Dataset BPJS):**
  - Badge: `Validasi Data Terbuka`
  - Headline: `Divalidasi skala besar.<br>Bukan sekadar simulasi.`
  - Giant Stat: `1,69 Jt` (warna: `var(--primary)`)
  - Subtext: `Baris data klaim FKRTL BPJS Kesehatan 2025`
- **Kartu 3 (Proteksi Kunjungan Sah):**
  - Badge: `Integritas Rekam Medis`
  - Headline: `Kunjungan sah berbeda.<br>Risiko dikunci nol.`
  - Giant Stat: `0,0` (warna: `var(--green)`)
  - Subtext: `Skor risiko seketika saat visit_id terbukti valid`
- **Kartu 4 (Akurasi Model):**
  - Badge: `Pembelajaran Mesin Terbuka`
  - Headline: `Kombinasi terkalibrasi.<br>CatBoost dan Regresi Logistik.`
  - Giant Stat: `96,1%` (warna: `#0071e3`)
  - Subtext: `Skor F1 kalibrasi empiris (Presisi 94,8% · Recall 97,3%)`

#### 3. CSS untuk Apple Product Cards
```css
.highlight-card {
  flex: 0 0 clamp(320px, 78vw, 400px);
  scroll-snap-align: center;
  border-radius: 32px;
  background: var(--surface-bg);
  border: 1px solid var(--border);
  padding: 36px 32px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 380px;
  transition: transform 0.3s var(--ease-apple-spring), box-shadow 0.3s var(--ease-apple-spring);
}
.highlight-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 36px rgba(30, 34, 66, 0.07);
}
.card-top {
  margin-bottom: 32px;
}
.card-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 980px;
  background: #ffffff;
  border: 1px solid var(--border);
  color: var(--primary);
  display: inline-block;
  margin-bottom: 16px;
}
.card-headline {
  font-size: 24px;
  line-height: 1.18;
  letter-spacing: -0.03em;
  margin: 0;
  font-weight: 700;
}
.card-giant-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.giant-number {
  font-size: clamp(48px, 5vw, 68px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
}
.giant-caption {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  line-height: 1.4;
}
```

---

### C. Section `#arsitektur`: 3-Step Scrollytelling Minimalis & Bersih

#### 1. Kolom Kiri: Minimal Floating Captions
- **Hapus Bingkai Kartu Kaku:** Saat tidak aktif, elemen `.scrolly-step` harus transparan tanpa border atau bayangan, dengan `opacity: 0.35`.
- **Transisi Halus ke Aktif:** Ketika `.scrolly-step.is-active`, tingkatkan `opacity: 1.0` secara mulus tanpa membuat kotak tebal yang memutus alur pandang.
- **Format Konten:**
  - Pill nomor langkah minimalis (`01`, `02`, `03`).
  - Judul tegas berukuran 24px.
  - Teks narasi maksimal 1–2 kalimat padat (`max-width: 40ch`).
  - Maksimal 2 visual chip ringkas (bukan 6 chip bertumpuk!).

#### 2. Spesifikasi Konten 3 Langkah (Kolom Kiri)
- **Langkah 01 (`data-step="0"`):**
  - Badge: `LANGKAH 01`
  - Judul: `Penyaringan 6 Dimensi Cepat`
  - Narasi: `Mendeteksi kemiripan klinis dan administratif berbobot 100 poin dengan pemblokiran O(N) tanpa beban komputasi berlebih.`
  - Chips:
    - `Token Pasien O(N)`
    - `Matriks Klinis 100 Poin`
- **Langkah 02 (`data-step="1"`):**
  - Badge: `LANGKAH 02`
  - Judul: `Guardrail Klinis Deterministik`
  - Narasi: `Kunjungan rawat jalan berkala langsung dikunci pada skor risiko nol saat nomor registrasi rekam medis terbukti terpisah.`
  - Chips:
    - `Distinct Visits (-100)`
    - `Status Protected Aktif`
- **Langkah 03 (`data-step="2"`):**
  - Badge: `LANGKAH 03`
  - Judul: `Ensemble CatBoost & LogReg`
  - Narasi: `Membantu verifikator menyusun prioritas telaah pada berkas tanpa guardrail menggunakan probabilitas non-linear transparan.`
  - Chips:
    - `CatBoost (0,62)`
    - `LogReg L2 (0,38)`

#### 3. Kolom Kanan (Inspector Stage): Pemangkasan 50% Teks
- **State 0 (Matriks):** Tampilkan hanya 4 dimensi utama (Identitas, Fasilitas, Tanggal, Tindakan) dengan bar persentase yang jelas. Buang dimensi redundant.
- **State 1 (Guardrail):** Pertahankan badge `PROTECTED ACTIVE`, nilai `0,0`, dan perbandingan 2 nomor encounter sederhana tanpa teks paragraf berulang.
- **State 2 (ML):** Tampilkan 2 kotak perbandingan bersih (CatBoost 91,2% vs LogReg 86,4%) dan keluaran skor hibrida `84,0`.

#### 4. CSS untuk Scrollytelling
```css
.scrolly-step {
  min-height: 60dvh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 24px 0;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  opacity: 0.32;
  transition: opacity 0.4s var(--ease-apple-smooth);
}
.scrolly-step.is-active {
  opacity: 1.0;
}
.step-badge {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--primary);
  margin-bottom: 12px;
}
.step-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.025em;
  margin: 0 0 12px;
  color: var(--text-ink);
}
.step-narrative {
  font-size: 15px;
  line-height: 1.55;
  color: var(--text-muted);
  max-width: 40ch;
  margin: 0 0 18px;
}
.step-chips-row {
  display: flex;
  gap: 8px;
}
.step-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 980px;
  background: #ffffff;
  border: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-ink);
}
```

---

### D. Section `#evaluasi`: Visual Benchmark & Kartu Prinsip Ringkas

#### 1. Kolom Kiri: Visual Comparison Card Bersih
Gantikan 3 blok teks tebal dengan 1 kartu visual yang hanya memuat judul, 3 progress bar bertingkat, dan label ringkas:
```html
<div class="benchmark-bars-card">
  <h3 class="bm-card-title">Perbandingan Akurasi Deteksi (F1-Score)</h3>
  <p class="bm-card-sub">Evaluasi 5-seed benchmark pada data berlabel.</p>

  <div class="clean-bar-stack">
    <!-- Bar 1 -->
    <div class="bar-group">
      <div class="bar-info-row">
        <span class="bar-name">Pencocokan Persis (Exact Match)</span>
        <span class="bar-val mono">29,3%</span>
      </div>
      <div class="bar-track">
        <div class="bar method0" data-width="29.3%"></div>
      </div>
    </div>

    <!-- Bar 2 -->
    <div class="bar-group">
      <div class="bar-info-row">
        <span class="bar-name">Kemiripan Biasa Tanpa Guardrail</span>
        <span class="bar-val mono">67,0%</span>
      </div>
      <div class="bar-track">
        <div class="bar method1" data-width="67.0%"></div>
      </div>
    </div>

    <!-- Bar 3 -->
    <div class="bar-group featured">
      <div class="bar-info-row">
        <span class="bar-name featured-text">KlaimKembar Hibrida (Guardrail + ML)</span>
        <span class="bar-val mono featured-text">91,5% · 96,1% BPJS</span>
      </div>
      <div class="bar-track featured-track">
        <div class="bar method2" data-width="96.1%"></div>
      </div>
    </div>
  </div>
</div>
```
*Catatan:* Hapus seluruh blok teks `.bm-critique` yang panjang!

#### 2. Kolom Kanan: 3 Kartu Tata Kelola Ikonik (Maksimal 15 Kata)
Gantikan penjelasan teknis panjang dengan 3 kartu ringkas:
```html
<div class="ethics-bento-card">
  <h3 class="ethics-card-title">Prinsip Tata Kelola &amp; Etika</h3>
  <p class="ethics-card-sub">Dirancang patuh regulasi privasi data medis.</p>

  <div class="compact-ethics-stack">
    <div class="compact-ethics-item">
      <div class="ethics-mini-icon">
        <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/><path d="M12 6a4 4 0 1 0 4 4 4 4 0 0 0-4-4z"/></svg>
      </div>
      <div>
        <h4>Privasi Kriptografis</h4>
        <p>Tokenisasi HMAC-SHA256 menyamarkan identitas pasien secara ireversibel.</p>
      </div>
    </div>

    <div class="compact-ethics-item">
      <div class="ethics-mini-icon">
        <svg viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg>
      </div>
      <div>
        <h4>Jejak Audit UTC</h4>
        <p>Log permanen mencatat setiap riwayat telaah verifikator secara transparan.</p>
      </div>
    </div>

    <div class="compact-ethics-item">
      <div class="ethics-mini-icon">
        <svg viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg>
      </div>
      <div>
        <h4>Keputusan di Tangan Manusia</h4>
        <p>Nol label kecurangan otomatis; petugas verifikator memiliki keputusan final.</p>
      </div>
    </div>
  </div>
</div>
```

---

## 3. Kompatibilitas Interaksi & JavaScript Guardrails

Agar Subagent C tidak merusak fungsionalitas interaktif yang ada:
1. **Atribut Scrollytelling Wajib Dipertahankan:**
   - Atribut container: `data-scrolly-container`
   - Elemen langkah kiri: `.scrolly-step[data-step="0"]`, `data-step="1"`, `data-step="2"`
   - Kartu panggung kanan: `.stage-card[data-stage-card="0"]`, `data-stage-card="1"`, `data-stage-card="2"`
   - Tombol tab panggung: `.stage-nav-pill[data-goto="0"]`, `data-goto="1"`, `data-goto="2"`
2. **Carousel & Switcher Sorotan:**
   - Pertahankan `#highlights-rail`, `.highlight-card`, `#rail-prev`, `#rail-next`, dan `.capsule-dot[data-target="0..3"]`.
3. **Benchmark Animation:**
   - Pertahankan `.bar[data-width="..."]` agar animasi progress bar saat terdeteksi oleh `IntersectionObserver` tetap berjalan lancar.
4. **Auth Portal:**
   - Jangan menyentuh ID form login, register, input fields, atau tab triggers (`tab-login`, `tab-register`, `panel-login`, `panel-register`, `form-demo`).

---

## 4. Checklist Verifikasi Akhir untuk Subagent C

- [ ] Tidak ada kalimat terpotong-potong kaku (staccato) atau jargon AI generik.
- [ ] Above the fold terasa ringan, luas, dan modern tanpa tumpukan 4 box berat.
- [ ] Section `#sorotan` memiliki angka raksasa (`clamp(48px, 5vw, 68px)`) dan bebas dari dinding teks paragraf.
- [ ] Section `#arsitektur` langkah kiri melayang bersih (floating caption) dengan perpindahan opacity `0.32 -> 1.0`.
- [ ] Section `#evaluasi` ringkas, rapi, dan mudah dicerna dalam 5 detik.
- [ ] Seluruh tombol navigasi, smooth scroll, tab auth, dan animasi scroll tetap berfungsi sempurna di desktop maupun mobile.
