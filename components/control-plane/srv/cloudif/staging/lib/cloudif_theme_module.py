# CloudIF v138a-safe — tema empresarial global

def render_theme_css():
    return """
<style>
:root{
  --cloudif-bg:#f5f8f5;
  --cloudif-surface:#ffffff;
  --cloudif-surface-soft:#f8fbf8;
  --cloudif-line:#d9e5dc;
  --cloudif-text:#1f2933;
  --cloudif-muted:#647067;
  --cloudif-brand:#168821;
  --cloudif-brand-dark:#0f6f1a;
  --cloudif-danger:#b42318;
  --cloudif-amber:#b45309;
  --cloudif-blue:#1d4ed8;
  --cloudif-radius:18px;
  --cloudif-shadow:0 14px 38px rgba(16,24,40,.08);
  --cloudif-shadow-soft:0 8px 24px rgba(16,24,40,.055);
}

body{
  background:
    radial-gradient(circle at top left, rgba(22,136,33,.08), transparent 34rem),
    linear-gradient(180deg,#f8fbf8 0%,#eef4ef 100%) !important;
  color:var(--cloudif-text) !important;
}

.header{
  background:rgba(255,255,255,.94) !important;
  backdrop-filter:blur(10px);
  border-bottom:1px solid rgba(22,136,33,.22) !important;
  box-shadow:0 10px 30px rgba(16,24,40,.06);
}

.tabs{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  background:rgba(255,255,255,.76);
  border:1px solid var(--cloudif-line);
  border-radius:18px;
  padding:8px;
  box-shadow:var(--cloudif-shadow-soft);
}

.tabs a{
  border-radius:13px !important;
  border:0 !important;
  color:#304138 !important;
  font-weight:850;
}

.tabs a.active{
  background:linear-gradient(135deg,var(--cloudif-brand),var(--cloudif-brand-dark)) !important;
  color:white !important;
  box-shadow:0 10px 24px rgba(22,136,33,.24);
}

.card,
.project-card,
.cm-card,
.ci-project-card,
.cm-section,
.ci-section{
  border:1px solid var(--cloudif-line) !important;
  border-radius:var(--cloudif-radius) !important;
  background:rgba(255,255,255,.96) !important;
  box-shadow:var(--cloudif-shadow-soft) !important;
}

.card:hover,
.project-card:hover,
.cm-card:hover,
.ci-project-card:hover{
  transform:translateY(-1px);
  box-shadow:var(--cloudif-shadow) !important;
  transition:.18s ease;
}

.btn,
.ci-btn,
.cm-btn,
button.btn{
  border-radius:12px !important;
  padding:9px 13px !important;
  font-weight:850 !important;
  border:1px solid var(--cloudif-line) !important;
  text-decoration:none !important;
}

.ci-btn-primary,
.btn.blue,
.cm-primary{
  background:linear-gradient(135deg,var(--cloudif-brand),var(--cloudif-brand-dark)) !important;
  color:white !important;
  border-color:transparent !important;
}

.btn.light,
.ci-btn-secondary,
.cm-secondary{
  background:#fff !important;
  color:#24352c !important;
}

.btn.gray{
  background:#f4f7f5 !important;
  color:#33443a !important;
}

.btn.amber{
  background:#fff7ed !important;
  color:#9a3412 !important;
  border-color:#fed7aa !important;
}

.pill,
.badge,
.ci-pill{
  border-radius:999px !important;
  padding:6px 10px !important;
  font-weight:900 !important;
  border:1px solid #dce9df;
  background:#f7fbf8;
}

.cm-grid,
.ci-card-grid,
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:16px;
  align-items:stretch;
}

.ci-menu-body,
.cm-menu-body{
  border:1px solid var(--cloudif-line) !important;
  border-radius:14px !important;
  background:white !important;
  box-shadow:0 18px 45px rgba(16,24,40,.16) !important;
  padding:8px !important;
}

.ci-menu-body a,
.ci-menu-item{
  display:block !important;
  width:100% !important;
  border:0 !important;
  border-radius:10px !important;
  background:transparent !important;
  color:#20312a !important;
  font-weight:800 !important;
  padding:10px 12px !important;
  text-align:left !important;
  text-decoration:none !important;
  cursor:pointer;
}

.ci-menu-body a:hover,
.ci-menu-item:hover{
  background:#eef8f0 !important;
}

.ci-menu-danger{
  color:var(--cloudif-danger) !important;
  background:#fff5f5 !important;
}

/* Remoções globais de elementos redundantes */
.cm-banner,
.ci-hero,
.ci-section:has(.ci-step-grid),
.ci-section:has(.ci-step-card),
.ci-section:has(input[name="setup_git"]),
.ci-section:has(input[name="setup_komodo"]),
.ci-menu-body a[href*="tab=git"][href*="project="]{
  display:none !important;
}
</style>
"""
