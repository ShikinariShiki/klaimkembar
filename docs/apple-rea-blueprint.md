# Apple Flagship Design Reverse-Engineering Blueprint
## Reverse-Engineered from Apple Indonesia (`apple.com/id/iphone-18-pro/`) for KlaimKembar

- **Target Origin**: `https://www.apple.com/id/iphone-18-pro/` & `https://www.apple.com/id/iphone/`
- **Extracted Source Artifacts**:
  - `ac-localnav.built.css` (Apple Local Navigation Framework v9)
  - `overview.built.css` (`/v/iphone-18-pro/c/built/styles/overview.built.css`, 1.62 MB production bundle)
  - Live Indonesian locale DOM hierarchy (`apple.com/id/iphone-18-pro/`)
- **Consumer**: Frontend Specialist Subagents refactoring `frontend/landing.html` and `frontend/style.css`.
- **Governing Guidelines**: `/home/shiki/.gemini/config/skills/reverse-engineer-anything/SKILL.md` & `/home/shiki/.gemini/config/skills/design-aesthetic-and-brand-engine/SKILL.md`.

---

## 1. Executive Summary & Design DNA

Apple's Pro flagship experience is characterized by three core pillars:
1. **Unwavering Focal Discipline**: Heavy optical hierarchy, hairline structural separation, and uncluttered negative space.
2. **Two-Tone Typography Cadence**: Assertive high-contrast opening declarations followed by muted contextual support in a single balanced flow.
3. **Physical-Metaphor Motion & Stage Scrollytelling**: Sticky viewport stages where cards and interactive telemetry slide and morph smoothly using calibrated spring deceleration curves (`cubic-bezier(0.16, 1, 0.3, 1)`).

This blueprint adapts Apple's flagship architecture to **KlaimKembar**, Indonesia's clinical pre-audit system for BPJS Kesehatan JKN claims, mapping Apple's design language onto KlaimKembar's existing token palette (`#5141ed`, `#1e2242`, `#f5f6fb`, `Plus Jakarta Sans`, `JetBrains Mono`).

---

## 2. Sticky Local Navigation (`ac-localnav`) Architecture

### 2.1 Technical Specifications

| Parameter | Desktop (`> 834px`) | Mobile (`<= 833px`) | Apple Source Reference |
| :--- | :--- | :--- | :--- |
| **Height** | `52px` | `48px` | `--r-localnav-height: calc(52px * var(--r-localnav-text-zoom-factor))` |
| **Max Width** | `1024px` | `100%` | `--localnav-max-width: 1024px` |
| **Surface Scrim** | `rgba(255, 255, 255, 0.72)` | `rgba(255, 255, 255, 0.88)` | `--localnav-body-alpha: rgba(255,255,255,0.8)` |
| **Backdrop Filter** | `saturate(180%) blur(20px)` | `saturate(180%) blur(20px)` | `backdrop-filter: blur(20px)` |
| **Hairline Border** | `1px solid rgba(0, 0, 0, 0.08)` | `1px solid rgba(0, 0, 0, 0.12)` | `box-shadow: 0 0 0 1px var(--localnav-outline)` |
| **Z-Index** | `9997` / `9998` | `9997` / `9998` | `z-index: 9998` |
| **Product Title** | `19px` (600, tracking `-0.015em`) | `17px` (600, line-height `1.41`) | `.typography-localnav-product-name` (`19px`, `1.21lh`) |
| **Nav Links** | `12px` (400, tracking `-0.01em`) | Drawer items `14px` (`400`) | `#ac-localnav .ac-ln-menu` (`12px`, `letter-spacing: -0.01em`) |
| **Pill Action CTA** | `12px`, padding `4px 11px` | `12px`, padding `4px 11px` | `#ac-localnav .ac-ln-button` (`border-radius: 980px`) |

### 2.2 DOM Structure Blueprint

```html
<!-- KlaimKembar Local Navigation (Apple ac-localnav Implementation) -->
<nav id="ac-localnav" class="ac-localnav-sticky" aria-label="Navigasi Lokal KlaimKembar">
  <div class="ac-ln-wrapper">
    <div class="ac-ln-content">
      <!-- Left: Product Brand Anchor -->
      <div class="ac-ln-title">
        <a href="#hero" class="ac-ln-title-link">
          <svg class="ac-ln-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3 5 6v6c0 4 7 8 7 8s7-4 7-8V6z"/>
            <path d="m9 11 2 2 4-4"/>
          </svg>
          <span class="ac-ln-product-name">KlaimKembar</span>
        </a>
      </div>

      <!-- Center: Section Anchors -->
      <div class="ac-ln-menu">
        <ul class="ac-ln-menu-items" role="list">
          <li class="ac-ln-menu-item"><a href="#sorotan" class="ac-ln-menu-link current">Sorotan</a></li>
          <li class="ac-ln-menu-item"><a href="#arsitektur" class="ac-ln-menu-link">Arsitektur</a></li>
          <li class="ac-ln-menu-item"><a href="#guardrail" class="ac-ln-menu-link">Guardrail Klinis</a></li>
          <li class="ac-ln-menu-item"><a href="#kalibrasi-bpjs" class="ac-ln-menu-link">Kalibrasi BPJS</a></li>
          <li class="ac-ln-menu-item"><a href="#evaluasi" class="ac-ln-menu-link">Benchmark</a></li>
        </ul>
      </div>

      <!-- Right: Action CTA Button -->
      <div class="ac-ln-actions">
        <a href="/login" class="ac-ln-button ac-ln-button--ghost">Masuk</a>
        <a href="#portal" class="ac-ln-button ac-ln-button--primary">Daftar Akun</a>
      </div>
    </div>
  </div>
  <div class="ac-ln-keyline" aria-hidden="true"></div>
</nav>
```

### 2.3 CSS Specification

```css
/* ==========================================================================
   Apple Localnav (ac-localnav) Specification for KlaimKembar
   ========================================================================== */
:root {
  --r-localnav-height: 52px;
  --r-localnav-padding: 22px;
  --r-localnav-max-width: 1040px;
  --localnav-bg: rgba(255, 255, 255, 0.76);
  --localnav-outline: rgba(30, 34, 66, 0.08);
  --localnav-ease: cubic-bezier(0.28, 0.11, 0.32, 1);
}

.ac-localnav-sticky {
  position: sticky;
  top: 0;
  left: 0;
  width: 100%;
  height: var(--r-localnav-height);
  z-index: 9990;
  background: var(--localnav-bg);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  transition: background 0.3s var(--localnav-ease), border-color 0.3s var(--localnav-ease);
}

.ac-localnav-sticky .ac-ln-wrapper {
  max-width: var(--r-localnav-max-width);
  margin: 0 auto;
  height: 100%;
  padding: 0 var(--r-localnav-padding);
}

.ac-localnav-sticky .ac-ln-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  gap: 16px;
}

/* Left Brand Title */
.ac-ln-title {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.ac-ln-title-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text-ink, #1e2242);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.ac-ln-icon {
  width: 18px;
  height: 18px;
  color: var(--primary, #5141ed);
}

/* Center Menu Links */
.ac-ln-menu {
  display: flex;
  align-items: center;
}

.ac-ln-menu-items {
  display: flex;
  align-items: center;
  gap: 24px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.ac-ln-menu-link {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: -0.01em;
  color: rgba(30, 34, 66, 0.72);
  text-decoration: none;
  transition: color 0.24s var(--localnav-ease), opacity 0.24s var(--localnav-ease);
  position: relative;
  padding: 4px 0;
}

.ac-ln-menu-link:hover {
  color: var(--text-ink, #1e2242);
  opacity: 1;
}

.ac-ln-menu-link.current {
  color: var(--primary, #5141ed);
  font-weight: 600;
}

.ac-ln-menu-link.current::after {
  content: "";
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 1.5px;
  background: var(--primary, #5141ed);
  border-radius: 1px;
}

/* Right Actions */
.ac-ln-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ac-ln-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -0.01em;
  padding: 4px 12px;
  min-height: 28px;
  border-radius: 980px;
  text-decoration: none;
  white-space: nowrap;
  transition: all 0.2s var(--localnav-ease);
}

.ac-ln-button--ghost {
  color: var(--text-ink, #1e2242);
  background: transparent;
}
.ac-ln-button--ghost:hover {
  background: rgba(81, 65, 237, 0.08);
  color: var(--primary, #5141ed);
}

.ac-ln-button--primary {
  background: var(--primary, #5141ed);
  color: #ffffff;
  box-shadow: 0 1px 2px rgba(81, 65, 237, 0.2);
}
.ac-ln-button--primary:hover {
  background: var(--primary-hover, #4335d6);
  transform: translateY(-0.5px);
}

/* Hairline bottom keyline */
.ac-ln-keyline {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 1px;
  background: var(--localnav-outline);
}

@media (max-width: 833px) {
  :root {
    --r-localnav-height: 48px;
    --r-localnav-padding: 16px;
  }
  .ac-ln-menu {
    display: none; /* Collapses to clean mobile layout */
  }
  .ac-ln-title-link {
    font-size: 17px;
  }
}
```

---

## 3. Typography & Hierarchy (The Two-Tone Cadence)

### 3.1 Fluid Clamp Formulas & Scale

Apple's display headlines enforce a very tight tracking (`-0.035em` to `-0.045em`) and strict line height (`1.04` to `1.08`) so that massive Indonesian headings wrap crisply without sprawling across the viewport.

| Scale Token | Fluid Clamp Formula | Line Height | Tracking | Weight | Semantic Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display Super** | `clamp(44px, 5.5vw + 12px, 80px)` | `1.05` | `-0.04em` | `800` | Hero Title / Chapter Statement |
| **Headline Elevated** | `clamp(32px, 3.8vw + 8px, 54px)` | `1.08` | `-0.035em` | `700` | Section Primary Title (`H2`) |
| **Headline Reduced** | `clamp(24px, 2.5vw + 4px, 36px)` | `1.14` | `-0.025em` | `700` | Scrollytelling Step Header |
| **Card / Rail Title** | `clamp(20px, 1.8vw + 4px, 26px)` | `1.18` | `-0.02em` | `650` | Highlights Gallery Card Title |
| **Lead Paragraph** | `clamp(17px, 1.2vw + 12px, 21px)` | `1.40` | `-0.015em` | `500` | Section Lead / Subtitle |
| **Telemetry / Metric** | `clamp(28px, 3vw, 44px)` | `1.00` | `-0.02em` | `700` | Quantitative Benchmarks (`tabular-nums`) |
| **Caption / Sosumi** | `12px` | `1.33` | `0.00em` | `400` | Footnotes, legal & methodology notes |

### 3.2 Signature Two-Tone Inline Text System

Apple's Pro product pages universally implement the **two-tone sentence lockup**:
1. **The Assertion (`.tone-ink`)**: High contrast, authoritative, punchy (80–100% optical black or bright white in dark mode).
2. **The Contextual Horizon (`.tone-muted`)**: Softened secondary tone (56–65% opacity), providing explanatory depth without competing for primary focal attention.

#### Token Implementation:
```css
/* Two-Tone Text Treatment */
.tone-ink {
  color: var(--text-ink, #1e2242);
  font-weight: 700;
}

.tone-muted {
  color: var(--text-muted, #7d86ad);
  font-weight: 500;
}

/* In Dark/Inverted Contexts (e.g. Hero Marquee or Dark Bento) */
.theme-dark .tone-ink {
  color: #f7f7ff;
}

.theme-dark .tone-muted {
  color: rgba(247, 247, 255, 0.64);
}
```

#### Content Application Pattern:
```html
<h2 class="display-headline">
  <span class="tone-ink">Ketelitian tingkat klinis.</span>
  <span class="tone-muted">Dirancang untuk melindungi setiap kunjungan terapi yang sah dari kesalahan sistem.</span>
</h2>

<p class="section-lead">
  <span class="tone-ink">Bukan sekadar pencocokan teks sederhana.</span>
  <span class="tone-muted">KlaimKembar menganalisis 6 dimensi fitur klinis dan riwayat FKRTL sebelum memberikan rekomendasi telaah.</span>
</p>
```

---

## 4. Scrollytelling Mechanics: Sticky Viewport Stage

### 4.1 Architecture & Physics

Apple's flagship interactive demonstrations (e.g., Apple Intelligence engine, Camera Control, A20 Pro Thermal dissipation) decouple the **visual viewport stage** from the **scrolling trigger column**:
- **Sticky Stage (`.scrolly-stage`)**: Fixed in place inside the viewport (`position: sticky; top: 72px; height: calc(100dvh - 96px)`), rendering the interactive UI, interactive case comparison, and live ML telemetry cards.
- **Scroll Triggers (`.scrolly-steps`)**: A vertical sequence of step triggers (`min-height: 75dvh`), driving step transitions and updating a CSS progress variable `--scroll-p` (`0.0` to `1.0`).
- **Observer Mechanism**: High-frequency step sensing via `IntersectionObserver` thresholds `[0.15, 0.50, 0.85]` combined with `requestAnimationFrame` for jitter-free interpolation.

```
┌────────────────────────────────────────────────────────────────┐
│  ac-localnav (Sticky 52px)                                      │
├──────────────────────────────┬─────────────────────────────────┤
│  SCROLLING NARRATIVE COLUMN  │  STICKY VIEWPORT STAGE          │
│  (Trigger Steps min-h 75dvh) │  (position: sticky; top: 72px)  │
│                              │                                 │
│  ┌────────────────────────┐  │  ┌───────────────────────────┐  │
│  │ Step 1: Ekstraksi      │  │  │ Interactive Live Case     │  │
│  │ 6-Fitur Kemiripan      │  │  │ Visualizer Stage          │  │
│  └────────────────────────┘  │  │                           │  │
│                              │  │ [Morphs dynamically based│  │
│  ┌────────────────────────┐  │  │  on active step index &   │  │
│  │ Step 2: Guardrail      │  │  │  --scroll-p variable]     │  │
│  │ Fisioterapi Sah        │  │  │                           │  │
│  └────────────────────────┘  │  │                           │  │
│                              │  │                           │  │
│  ┌────────────────────────┐  │  │                           │  │
│  │ Step 3: Kalibrasi      │  │  │                           │  │
│  │ CatBoost + LogReg      │  │  └───────────────────────────┘  │
│  └────────────────────────┘  │                                 │
└──────────────────────────────┴─────────────────────────────────┘
```

### 4.2 Easing Curves

```css
:root {
  /* Apple Spring-Out (Used for card reveals, stage element transitions) */
  --ease-apple-spring: cubic-bezier(0.16, 1, 0.3, 1);
  
  /* Apple Drawer/Localnav (Used for nav drawer, sticky reveals, hairline shifts) */
  --ease-apple-drawer: cubic-bezier(0.28, 0.11, 0.32, 1);
  
  /* Apple Scrub (Direct 1:1 tactile responsiveness) */
  --ease-apple-scrub: linear;
}
```

### 4.3 Production Scrollytelling DOM Blueprint

```html
<section class="section section-scrolly" id="arsitektur" data-scrolly-container>
  <div class="scrolly-grid">
    <!-- Left Column: Sticky Stage -->
    <div class="scrolly-stage-col">
      <div class="scrolly-stage" id="scrolly-stage-view">
        <!-- Interactive Mockup / Telemetry Stage -->
        <div class="stage-card" data-stage-card="1">
          <div class="stage-header">
            <span class="pill pill-primary">Fitur 1: Analisis 6-Dimensi</span>
            <span class="mono text-muted">ID Klaim: #CLM-2025-094</span>
          </div>
          <div class="stage-body">
            <!-- Dynamic comparison cards illustrating claim collision -->
            <div class="case-diff-grid">
              <div class="case-card">
                <div class="case-badge">Klaim A (08:30 WIB)</div>
                <div class="case-detail">Poli Saraf · Z50.1 (Fisioterapi Saraf)</div>
              </div>
              <div class="case-card">
                <div class="case-badge">Klaim B (11:15 WIB)</div>
                <div class="case-detail">Poli Rehab Medik · Z50.1 (Kunjungan Terjadwal)</div>
              </div>
            </div>
          </div>
        </div>

        <div class="stage-card" data-stage-card="2">
          <div class="stage-header">
            <span class="pill pill-green">Guardrail Klinis Aktif</span>
            <span class="mono text-green">Pencegahan False Positive</span>
          </div>
          <div class="stage-body">
            <div class="guardrail-callout">
              <strong>Aturan Klinis Terpenuhi:</strong>
              <p>Jadwal siklus fisioterapi sah nomor registrasi seri 3 dari 8 kunjungan rawat jalan bulanan.</p>
            </div>
          </div>
        </div>

        <div class="stage-card" data-stage-card="3">
          <div class="stage-header">
            <span class="pill pill-amber">Penilai Hibrida</span>
            <span class="mono text-muted">CatBoost 91,2% · LogReg 86,4%</span>
          </div>
          <div class="stage-body">
            <div class="hybrid-meter">
              <div class="meter-bar" style="--val: 84%"></div>
              <div class="meter-labels">
                <span>Skor Prioritas: <strong>84,0 / 100</strong></span>
                <span class="text-amber">Rekomendasi Telaah Prioritas Sedang</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Column: Narrative Trigger Steps -->
    <div class="scrolly-steps-col">
      <article class="scrolly-step" data-step="1">
        <div class="step-badge mono">01 / DETEKSI AWAL</div>
        <h3 class="step-headline">
          <span class="tone-ink">Pencocokan 6 Fitur Kemiripan.</span>
          <span class="tone-muted">Bukan hanya nomor peserta, sistem membedah kode diagnosa, jam layanan, dokter penanggung jawab, dan tindakan sekunder.</span>
        </h3>
        <p class="step-desc">
          Setiap pasangan klaim dianalisis kemiripannya dalam ruang multidimensi untuk memastikan klaim kembar identik maupun variasi pengajuan ganda segera terpetakan.
        </p>
      </article>

      <article class="scrolly-step" data-step="2">
        <div class="step-badge mono">02 / GUARDRAIL KLINIS</div>
        <h3 class="step-headline">
          <span class="tone-ink">Melindungi Kunjungan Sah.</span>
          <span class="tone-muted">Pasien stroke dan rehabilitasi medik membutuhkan terapi berulang yang sah secara medis.</span>
        </h3>
        <p class="step-desc">
          Guardrail memotong false positive hingga 87% (dari 48,9 menjadi 6,36 per 1.000 klaim) sehingga staf verifikator tidak membuang waktu menelaah kunjungan legal.
        </p>
      </article>

      <article class="scrolly-step" data-step="3">
        <div class="step-badge mono">03 / KALIBRASI FKRTL</div>
        <h3 class="step-headline">
          <span class="tone-ink">Dikalibrasi pada 1,69 Juta Baris.</span>
          <span class="tone-muted">Hasil uji CatBoost dan Logistic Regression pada data terbuka BPJS Kesehatan 2025.</span>
        </h3>
        <p class="step-desc">
          Model menghasilkan skor prioritas tanpa pernah menggunakan label spekulatif. Semua temuan disajikan dalam bahasa telaah netral yang siap dipertanggungjawabkan.
        </p>
      </article>
    </div>
  </div>
</section>
```

### 4.4 Scrollytelling CSS Implementation

```css
/* Scrollytelling Layout */
.section-scrolly {
  padding: 80px 0;
  position: relative;
  background: var(--surface-bg, #f5f6fb);
}

.scrolly-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 48px;
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

/* Sticky Stage */
.scrolly-stage-col {
  position: relative;
}

.scrolly-stage {
  position: sticky;
  top: calc(var(--r-localnav-height, 52px) + 24px);
  height: calc(100dvh - 120px);
  max-height: 640px;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid var(--border, #e4e6f6);
  box-shadow: 0 12px 36px rgba(30, 34, 66, 0.06);
  padding: 24px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.stage-card {
  position: absolute;
  inset: 24px;
  display: flex;
  flex-direction: column;
  opacity: 0;
  transform: translateY(20px) scale(0.98);
  pointer-events: none;
  transition: opacity 0.5s var(--ease-apple-spring),
              transform 0.5s var(--ease-apple-spring);
}

.stage-card.is-active {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}

/* Narrative Triggers */
.scrolly-steps-col {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.scrolly-step {
  min-height: 75dvh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 32px;
  border-radius: 20px;
  background: transparent;
  transition: background 0.3s ease;
}

.scrolly-step.is-active {
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 4px 20px rgba(30, 34, 66, 0.04);
}

.step-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--primary, #5141ed);
  margin-bottom: 12px;
}

.step-headline {
  font-size: clamp(24px, 2.2vw, 32px);
  line-height: 1.15;
  letter-spacing: -0.025em;
  margin: 0 0 16px;
}

.step-desc {
  font-size: 15px;
  line-height: 1.5;
  color: var(--text-muted, #7d86ad);
  margin: 0;
}

@media (max-width: 833px) {
  .scrolly-grid {
    grid-template-columns: 1fr;
    gap: 32px;
  }
  .scrolly-stage {
    position: static;
    height: 380px;
  }
  .scrolly-step {
    min-height: auto;
    padding: 20px 0;
  }
}
```

### 4.5 Zero-Dependency Scrollytelling Controller (`scrolly.js`)

```javascript
// Lightweight Apple-Style Scrolly Controller
export function initScrollytelling() {
  const container = document.querySelector('[data-scrolly-container]');
  if (!container) return;

  const steps = container.querySelectorAll('.scrolly-step');
  const cards = container.querySelectorAll('.stage-card');

  // 1. Intersection Observer for Step Activation
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const stepNum = entry.target.getAttribute('data-step');
        
        // Update Step Classes
        steps.forEach(s => s.classList.toggle('is-active', s === entry.target));
        
        // Update Stage Visuals
        cards.forEach(c => {
          c.classList.toggle('is-active', c.getAttribute('data-stage-card') === stepNum);
        });
      }
    });
  }, {
    threshold: [0.2, 0.5, 0.8],
    rootMargin: "-15% 0px -25% 0px"
  });

  steps.forEach(step => observer.observe(step));

  // 2. rAF Scroll Progress Metric
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        const rect = container.getBoundingClientRect();
        const winHeight = window.innerHeight;
        const totalDist = rect.height - winHeight;
        const currentDist = -rect.top;
        const progress = Math.min(Math.max(currentDist / totalDist, 0), 1);
        
        container.style.setProperty('--scroll-p', progress.toFixed(3));
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
}
```

---

## 5. "Sorotan Utama" (Highlights) Horizontal Card Rail & Pill Switcher

### 5.1 Structural Blueprint

In `https://www.apple.com/id/iphone-18-pro/`, the `section-highlights` ("Sorotan Utama") is a prominent full-bleed card carousel with:
1. An editorial header with headline and modal CTA (`Keunggulan demi keunggulan.`).
2. A horizontal card rail using native CSS scroll-snapping (`scroll-snap-type: x mandatory`).
3. Large rounded bento cards (`border-radius: 28px` or `32px`, `tile-rounded`).
4. A floating capsule/pill switcher (`dotnav`) anchored at the bottom with a blur scrim backdrop.

### 5.2 Highlights DOM Blueprint for KlaimKembar

```html
<!-- KlaimKembar Sorotan Utama (Apple Highlights Rail Implementation) -->
<section class="section section-highlights" id="sorotan">
  <div class="highlights-header">
    <div class="highlights-eyebrow">Sorotan Utama</div>
    <h2 class="highlights-headline">
      <span class="tone-ink">Keunggulan demi keunggulan.</span>
      <span class="tone-muted">Solusi teruji untuk integritas klaim JKN.</span>
    </h2>
  </div>

  <!-- Horizontal Scroll Rail Container -->
  <div class="highlights-rail-wrap">
    <div class="highlights-rail" id="highlights-rail" role="region" aria-label="Sorotan Fitur">
      
      <!-- Card 1: 6-Dimensi Kemiripan -->
      <article class="highlight-card" data-highlight-index="0" id="sorotan-card-1">
        <div class="card-media">
          <div class="card-tag">Pencocokan Presisi</div>
          <div class="card-telemetry mono">6/6 Fitur</div>
        </div>
        <div class="card-content">
          <h3 class="card-title">Deteksi Multi-Fitur Komprehensif</h3>
          <p class="card-desc">
            Bukan sekadar kemiripan teks, sistem memeriksa tanggal kunjungan, diagnosis sekunder, tarif INA-CBG, dan kode dokter.
          </p>
        </div>
      </article>

      <!-- Card 2: Guardrail Klinis -->
      <article class="highlight-card" data-highlight-index="1" id="sorotan-card-2">
        <div class="card-media card-media--green">
          <div class="card-tag">Perlindungan Pasien</div>
          <div class="card-telemetry mono">-87% FP</div>
        </div>
        <div class="card-content">
          <h3 class="card-title">Pencegahan Salah Tuduh Pasien Fisioterapi</h3>
          <p class="card-desc">
            Membedakan secara otomatis jadwal rehabilitasi medik multi-kunjungan yang sah dari duplikasi klaim yang tidak wajar.
          </p>
        </div>
      </article>

      <!-- Card 3: Kalibrasi 1,69M Baris FKRTL -->
      <article class="highlight-card" data-highlight-index="2" id="sorotan-card-3">
        <div class="card-media card-media--purple">
          <div class="card-tag">Kalibrasi Data Terbuka</div>
          <div class="card-telemetry mono">96,1% F1</div>
        </div>
        <div class="card-content">
          <h3 class="card-title">Skor Hibrida CatBoost + Logistic Regression</h3>
          <p class="card-desc">
            Divalidasi langsung pada dataset terbuka BPJS Kesehatan FKRTL 2025 untuk menjamin akurasi di lingkungan rumah sakit riil.
          </p>
        </div>
      </article>

      <!-- Card 4: Bahasa Telaah Netral -->
      <article class="highlight-card" data-highlight-index="3" id="sorotan-card-4">
        <div class="card-media card-media--blue">
          <div class="card-tag">Akuntabilitas Hukum</div>
          <div class="card-telemetry mono">0 Label Spekulatif</div>
        </div>
        <div class="card-content">
          <h3 class="card-title">Telaah Objektif Siap Audit</h3>
          <p class="card-desc">
            Menghilangkan cap 'fraud' subjektif, menggantikannya dengan catatan audit klinis yang terstruktur dan bermartabat.
          </p>
        </div>
      </article>

    </div>
  </div>

  <!-- Floating Capsule Pill Switcher (Apple Dotnav Capsule) -->
  <div class="highlights-pill-bar">
    <div class="capsule-switcher" role="tablist" aria-label="Kendali Sorotan">
      <button role="tab" class="capsule-dot is-active" aria-label="Sorotan 1" data-target="0"></button>
      <button role="tab" class="capsule-dot" aria-label="Sorotan 2" data-target="1"></button>
      <button role="tab" class="capsule-dot" aria-label="Sorotan 3" data-target="2"></button>
      <button role="tab" class="capsule-dot" aria-label="Sorotan 4" data-target="3"></button>
    </div>
  </div>
</section>
```

### 5.3 Highlights CSS Specification

```css
/* Highlights Section */
.section-highlights {
  padding: 80px 0 100px;
  background: #ffffff;
  overflow: hidden;
}

.highlights-header {
  max-width: 1040px;
  margin: 0 auto 40px;
  padding: 0 24px;
}

.highlights-eyebrow {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--primary, #5141ed);
  margin-bottom: 8px;
}

.highlights-headline {
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.08;
  letter-spacing: -0.03em;
  margin: 0;
}

/* Horizontal Card Rail */
.highlights-rail-wrap {
  width: 100%;
  position: relative;
}

.highlights-rail {
  display: flex;
  gap: 24px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  padding: 16px max(24px, calc((100vw - 1040px) / 2)) 40px;
  scrollbar-width: none; /* Hide default scrollbar */
}
.highlights-rail::-webkit-scrollbar {
  display: none;
}

/* Highlight Cards */
.highlight-card {
  flex: 0 0 clamp(300px, 78vw, 400px);
  scroll-snap-align: center;
  border-radius: 28px;
  background: var(--surface-bg, #f5f6fb);
  border: 1px solid var(--border, #e4e6f6);
  padding: 32px 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 420px;
  box-shadow: 0 4px 20px rgba(30, 34, 66, 0.04);
  transition: transform 0.3s var(--ease-apple-spring), box-shadow 0.3s var(--ease-apple-spring);
}

.highlight-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(81, 65, 237, 0.08);
}

.card-media {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
}

.card-tag {
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 980px;
  background: #ffffff;
  color: var(--text-ink, #1e2242);
  border: 1px solid var(--border, #e4e6f6);
}

.card-telemetry {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary, #5141ed);
  font-variant-numeric: tabular-nums;
}

.card-media--green .card-telemetry { color: var(--green, #108260); }
.card-media--purple .card-telemetry { color: var(--primary-deep, #3428b6); }
.card-media--blue .card-telemetry { color: #0071e3; }

.card-title {
  font-size: 22px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  font-weight: 700;
  margin: 0 0 12px;
  color: var(--text-ink, #1e2242);
}

.card-desc {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-muted, #7d86ad);
  margin: 0;
}

/* Floating Capsule Pill Switcher */
.highlights-pill-bar {
  display: flex;
  justify-content: center;
  margin-top: -12px;
}

.capsule-switcher {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  border-radius: 980px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(30, 34, 66, 0.1);
  box-shadow: 0 4px 16px rgba(30, 34, 66, 0.06);
}

.capsule-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: none;
  background: rgba(30, 34, 66, 0.25);
  cursor: pointer;
  padding: 0;
  transition: all 0.25s var(--ease-apple-spring);
}

.capsule-dot.is-active {
  width: 24px;
  border-radius: 4px;
  background: var(--primary, #5141ed);
}
```

---

## 6. Design System Mapping Matrix (Apple -> KlaimKembar)

To ensure pixel-level harmony with KlaimKembar's existing application suite, every Apple design token is systematically mapped to KlaimKembar tokens:

| Apple Design Primitive | Apple Source Spec | KlaimKembar Token | Hex / Value | KlaimKembar Usage Role |
| :--- | :--- | :--- | :--- | :--- |
| **Accent Primary** | `#0071e3` (Apple Blue) | `--primary` | `#5141ed` | Primary CTAs, active highlights, badges |
| **Accent Hover** | `#0076DF` | `--primary-hover` | `#4335d6` | Interactive hover states |
| **Accent Deep** | `#006EDB` | `--primary-deep` | `#3428b6` | Active selection, heavy contrast pill |
| **Surface Canvas** | `#F5F5F7` / `#000000` | `--surface-bg` | `#f5f6fb` | Landing page canvas background |
| **Surface Card** | `#FFFFFF` / `#161617` | `--surface-card` | `#ffffff` | Floating bento & scrolly cards |
| **Text Ink** | `#1D1D1F` | `--text-ink` | `#1e2242` | High-conviction headlines & assertions |
| **Text Muted** | `#86868B` | `--text-muted` | `#7d86ad` | Contextual subtitles & secondary clauses |
| **Hairline Border** | `rgba(0,0,0,0.12)` | `--border` | `#e4e6f6` | 1px hairline separation grid |
| **Tinted Hairline**| `rgba(0,113,227,0.2)` | `--border-tint` | `#cbc8ff` | Focus rings & primary container outlines |
| **Success / Green** | `#34C759` | `--green` | `#108260` | Guardrail validation, F1 benchmark scores |
| **Warning / Amber** | `#FF9500` | `--amber` | `#b55c00` | Prioritas Sedang, batas ambang telaah |
| **Danger / Red** | `#FF3B30` | `--red` | `#d83239` | Prioritas Tinggi (klaim identik terdeteksi) |
| **Primary Sans** | `SF Pro Display / Text` | `Plus Jakarta Sans` | sans-serif | System-wide display & body copy |
| **Telemetry Mono** | `SF Mono / tabular-nums`| `JetBrains Mono` | monospace | Numeric metrics, IDs, timestamps (`tabular-nums`) |

---

## 7. Implementation Checklist for Specialist Subagent

When implementing this blueprint into `frontend/landing.html` and `frontend/style.css`, the specialist subagent should follow this strict order of operations:

1. **Local Navigation Migration**:
   - Replace the legacy `<header class="landing-nav-wrap">` with the `<nav id="ac-localnav" class="ac-localnav-sticky">` markup.
   - Enforce `height: 52px`, `backdrop-filter: saturate(180%) blur(20px)`, `border-bottom: 1px solid var(--border)`.
   - Implement pill button CTAs (`border-radius: 980px`, `12px` font size).
2. **Typography Refinement**:
   - Apply fluid clamp formulas to Hero `H1` and section titles (`clamp(40px, 5vw, 68px)`).
   - Inject the two-tone structure (`<span class="tone-ink">...</span> <span class="tone-muted">...</span>`) across key declarations.
   - Restrict body line lengths to `60–65ch` using `max-width` containers.
3. **Sorotan Utama (Highlights) Rail Integration**:
   - Insert the horizontal card rail under the Hero section (`#sorotan`).
   - Implement the `tile-rounded` cards (`28px` radius) with `scroll-snap-type: x mandatory`.
   - Add the floating capsule dot switcher with active pill width expansion (`width: 24px` for active dot).
4. **Scrollytelling Engine Deployment**:
   - Convert `#arsitektur` into the 2-column sticky stage (`.scrolly-grid`).
   - Ensure left stage is `position: sticky; top: 76px; height: calc(100dvh - 120px)`.
   - Wire `IntersectionObserver` thresholds `[0.2, 0.5, 0.8]` to switch stage cards with `cubic-bezier(0.16, 1, 0.3, 1)`.
5. **Anti-Slop & Quality Assurance**:
   - Ensure all numeric telemetry uses `JetBrains Mono` with `font-variant-numeric: tabular-nums`.
   - Verify zero layout shift during sticky localnav pinning.
   - Test responsive breakpoints at `1280px` (desktop), `834px` (tablet), and `390px` (mobile).
