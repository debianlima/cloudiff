#!/usr/bin/env python3
import html

def h(x):
    return html.escape("" if x is None else str(x))

def css():
    return """
<style>
:root{
  --cm-green:#168821;
  --cm-green-dark:#0b6418;
  --cm-green-soft:#eef8f0;
  --cm-bg:#f3f4f6;
  --cm-card:#ffffff;
  --cm-border:#e5e7eb;
  --cm-text:#1f2937;
  --cm-muted:#667085;
  --cm-disabled-bg:#f2f4f7;
  --cm-disabled-text:#8a94a6;
  --cm-danger:#b42318;
}
.cm-page{
  display:block;
}
.cm-banner{
  background:linear-gradient(180deg,#fff,#f7fbf8);
  border:1px solid var(--cm-border);
  border-radius:18px;
  padding:22px;
  margin-bottom:16px;
}
.cm-banner-top{
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
}
.cm-banner h2{
  margin:0;
  font-size:26px;
  color:var(--cm-text);
}
.cm-banner p{
  margin:8px 0 0;
  color:var(--cm-muted);
}
.cm-toolbar{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  margin-top:14px;
}
.cm-menu-tabs{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  align-items:center;
  border:1px solid var(--cm-border);
  background:#fff;
  border-radius:18px;
  padding:10px;
  margin-bottom:16px;
}
.cm-menu-tabs a{
  text-decoration:none;
  color:var(--cm-text);
  font-weight:800;
  padding:9px 12px;
  border-radius:10px;
}
.cm-menu-tabs a:hover{
  background:#f5faf6;
  color:var(--cm-green-dark);
}
.cm-menu-tabs a.active{
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
}
.cm-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:16px;
}
.cm-card{
  background:#fff;
  border:1px solid var(--cm-border);
  border-radius:18px;
  padding:16px;
  box-shadow:0 8px 20px rgba(20,40,20,.04);
}
.cm-card h3,.cm-card h4{
  margin-top:0;
}
.cm-muted{
  color:var(--cm-muted);
  font-size:14px;
}
.cm-pill{
  display:inline-flex;
  align-items:center;
  border-radius:999px;
  padding:5px 10px;
  font-size:12px;
  font-weight:800;
  margin:2px;
}
.cm-ok{
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
}
.cm-off{
  background:var(--cm-disabled-bg);
  color:var(--cm-muted);
}
.cm-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:9px 12px;
  border-radius:10px;
  font-weight:700;
  font-size:14px;
  text-decoration:none !important;
  border:1px solid transparent;
  margin:3px;
  min-height:38px;
  cursor:pointer;
}
.cm-primary{
  background:var(--cm-green);
  color:#fff !important;
  border-color:var(--cm-green);
}
.cm-secondary{
  background:#fff;
  color:var(--cm-green-dark) !important;
  border-color:var(--cm-border);
}
.cm-disabled{
  background:var(--cm-disabled-bg);
  color:var(--cm-disabled-text) !important;
  border-color:#e5e7eb;
  cursor:not-allowed;
}
.cm-danger{
  background:#fff;
  color:var(--cm-danger) !important;
  border-color:#f2d3d0;
}
.cm-inline{
  display:inline;
}
.cm-inline button{
  border:0;
}
.cm-menu{
  position:relative;
  float:right;
}
.cm-menu summary{
  list-style:none;
  cursor:pointer;
  border:1px solid var(--cm-border);
  border-radius:10px;
  padding:6px 10px;
  color:var(--cm-muted);
  background:#fff;
  font-weight:800;
}
.cm-menu summary::-webkit-details-marker{
  display:none;
}
.cm-menu-body{
  position:absolute;
  right:0;
  top:38px;
  background:#fff;
  border:1px solid var(--cm-border);
  border-radius:12px;
  box-shadow:0 12px 24px rgba(0,0,0,.12);
  padding:8px;
  z-index:5;
  min-width:230px;
}
.cm-menu-body a,.cm-menu-body button{
  display:block;
  width:100%;
  text-align:left;
  background:#fff;
  border:0;
  padding:9px;
  border-radius:8px;
  color:var(--cm-text);
  text-decoration:none;
}
.cm-menu-body a:hover,.cm-menu-body button:hover{
  background:#f5faf6;
}
.cm-resource{
  border-top:1px solid var(--cm-border);
  padding-top:12px;
  margin-top:12px;
}
.cm-resource-title{
  display:flex;
  justify-content:space-between;
  gap:8px;
  align-items:center;
}
.cm-actions{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
  margin-top:10px;
}
.cm-section{
  border:1px solid var(--cm-border);
  border-radius:18px;
  background:#fff;
  padding:18px;
  margin:16px 0;
}
.cm-table{
  width:100%;
  border-collapse:collapse;
  margin-top:10px;
}
.cm-table th,.cm-table td{
  border-bottom:1px solid var(--cm-border);
  padding:10px;
  text-align:left;
}
.cm-table th{
  background:#f5faf6;
  color:var(--cm-green-dark);
}
.cm-footer{
  margin-top:24px;
  padding:18px;
  color:var(--cm-muted);
  text-align:center;
  font-size:13px;
}
.cm-profile-global-host{
  margin-left:auto !important;
  margin-right:0 !important;
  display:flex !important;
  align-items:center !important;
  justify-content:flex-end !important;
  flex:0 0 auto !important;
}
.cm-profile-floating{
  position:fixed !important;
  top:14px !important;
  right:18px !important;
  left:auto !important;
  z-index:9999 !important;
}
.cm-profile-top{
  position:relative !important;
  flex-shrink:0 !important;
}
.cm-profile-top summary{
  list-style:none !important;
  cursor:pointer !important;
  width:42px !important;
  height:42px !important;
  border-radius:999px !important;
  display:flex !important;
  align-items:center !important;
  justify-content:center !important;
  background:#ffffff !important;
  color:var(--cm-green-dark) !important;
  border:1px solid var(--cm-border) !important;
  font-weight:900 !important;
  box-shadow:0 4px 14px rgba(15,23,42,.08) !important;
}
.cm-profile-top summary::-webkit-details-marker{
  display:none !important;
}
.cm-profile-body{
  position:absolute !important;
  right:0 !important;
  left:auto !important;
  top:50px !important;
  width:min(360px, calc(100vw - 40px)) !important;
  background:#fff !important;
  border:1px solid var(--cm-border) !important;
  border-radius:16px !important;
  box-shadow:0 18px 48px rgba(15,23,42,.18) !important;
  padding:14px !important;
  z-index:10000 !important;
}
.cm-profile-name{
  font-weight:900;
  color:var(--cm-text);
}
.cm-profile-email{
  color:var(--cm-muted);
  font-size:13px;
  word-break:break-all;
}
.cm-profile-groups{
  display:flex;
  flex-wrap:wrap;
  gap:5px;
  margin-top:10px;
}
.cm-profile-group{
  display:inline-flex;
  border-radius:999px;
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
  padding:4px 8px;
  font-size:11px;
  font-weight:800;
}
.cm-profile-actions{
  border-top:1px solid var(--cm-border);
  margin-top:12px;
  padding-top:10px;
  display:grid;
  gap:6px;
}
.cm-profile-actions a{
  text-decoration:none;
  color:var(--cm-text);
  padding:8px;
  border-radius:8px;
  font-weight:700;
}
.cm-profile-actions a:hover{
  background:#f5faf6;
}
.cm-profile-source{
  display:none !important;
}
.cm-user-box-hidden,.cm-topbar-hidden-aux{
  display:none !important;
}
.cm-modal{
  display:none;
  position:fixed;
  inset:0;
  background:rgba(15,23,42,.45);
  z-index:9999;
  padding:30px;
  overflow:auto;
}
.cm-modal:target{
  display:block;
}
.cm-modal-card{
  max-width:850px;
  margin:30px auto;
  background:#fff;
  border-radius:20px;
  border:1px solid var(--cm-border);
  box-shadow:0 24px 60px rgba(0,0,0,.25);
  padding:22px;
}
.cm-modal-head{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:start;
}
.cm-close{
  text-decoration:none;
  font-size:24px;
  color:var(--cm-muted);
}
.cm-field{
  margin:12px 0;
}
.cm-field label{
  display:block;
  font-weight:800;
  margin-bottom:5px;
}
.cm-field input,.cm-field textarea,.cm-field select{
  width:100%;
  padding:10px;
  border:1px solid var(--cm-border);
  border-radius:10px;
}
@media(max-width:720px){
  .cm-banner-top{
    flex-direction:column;
  }
  .cm-grid{
    grid-template-columns:1fr;
  }
}

/* CloudIF v70 — ocultar userbar/blocos soltos de usuário fora do perfil */
.userbar,
.user-bar,
.card.userbar,
.card.user-bar,
#userbar,
#user-bar,
[data-component="userbar"],
[data-cloudif-userbar],
.cm-userbar-hidden,
.cm-user-box-hidden{
  display:none !important;
}


/* CloudIF v71 — remover nav modular redundante */
.cm-menu-tabs{
  display:none !important;
}


/* CloudIF v72 — cards de servidores no resumo */
.cm-server-panel{
  margin:18px 0;
  background:#fff;
  border:1px solid var(--cm-border);
  border-radius:18px;
  padding:18px;
  box-shadow:0 8px 20px rgba(20,40,20,.04);
}
.cm-server-panel-head{
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
  flex-wrap:wrap;
  margin-bottom:14px;
}
.cm-server-panel h3{
  margin:0;
}
.cm-server-aggregate{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
}
.cm-server-agg-card{
  background:#f7fbf8;
  border:1px solid var(--cm-border);
  border-radius:14px;
  padding:10px 12px;
  min-width:180px;
}
.cm-server-agg-card strong{
  display:block;
  color:var(--cm-muted);
  font-size:12px;
  margin-bottom:4px;
}
.cm-server-agg-card span{
  font-size:18px;
  font-weight:900;
  color:var(--cm-text);
}
.cm-server-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:14px;
}
.cm-server-card{
  border:1px solid var(--cm-border);
  border-radius:16px;
  padding:14px;
  background:#fff;
}
.cm-server-card-top{
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:center;
  margin-bottom:10px;
}
.cm-server-name{
  font-size:18px;
  font-weight:900;
  color:var(--cm-text);
}
.cm-meter{
  margin:10px 0;
}
.cm-meter-line{
  display:flex;
  justify-content:space-between;
  gap:10px;
  color:var(--cm-muted);
  font-size:13px;
  font-weight:700;
  margin-bottom:6px;
}
.cm-meter-bar{
  height:9px;
  background:#eef2f7;
  border-radius:999px;
  overflow:hidden;
}
.cm-meter-fill{
  height:100%;
  background:var(--cm-green);
  border-radius:999px;
}
.cm-server-meta{
  border-top:1px solid var(--cm-border);
  padding-top:10px;
  margin-top:10px;
  color:var(--cm-muted);
  font-size:13px;
}
.cm-server-source{
  color:var(--cm-muted);
  font-size:12px;
  margin-top:10px;
  word-break:break-all;
}


/* CloudIF v75 — perfil com SVG e grupo principal */
.cm-profile-icon{
  width:24px;
  height:24px;
  display:block;
}
.cm-profile-primary-group{
  color:var(--cm-muted);
  font-size:13px;
  font-weight:800;
  margin-top:2px;
}
.cm-profile-email-secondary{
  color:var(--cm-muted);
  font-size:12px;
  word-break:break-all;
  margin-top:4px;
}


/* CloudIF v76 — rodapé institucional e perfil compacto */
.cm-footer{
  margin-top:24px;
  padding:16px 18px;
  color:var(--cm-muted);
  text-align:center;
  font-size:13px;
  line-height:1.5;
}
.cm-footer strong{
  color:var(--cm-text);
}
.cm-footer-line{
  display:block;
}
.cm-profile-name{
  margin-bottom:8px;
}
.cm-profile-email,
.cm-profile-primary-group,
.cm-profile-email-secondary{
  display:none !important;
}


/* CloudIF v77 — rodapé institucional em div.footer */
.footer{
  margin-top:24px;
  padding:16px 18px;
  color:var(--cm-muted);
  text-align:center;
  font-size:13px;
  line-height:1.5;
  border-top:1px solid var(--cm-border);
}
.footer strong{
  color:var(--cm-text);
}
.footer-line{
  display:block;
}
footer.cm-footer{
  display:none !important;
}


/* CloudIF v78 — footer único oficial */
.footer{
  display:none !important;
}
.footer[data-cloudif-footer="address"]{
  display:block !important;
  margin-top:24px;
  padding:16px 18px;
  color:var(--cm-muted);
  text-align:center;
  font-size:13px;
  line-height:1.5;
  border-top:1px solid var(--cm-border);
}
.footer[data-cloudif-footer="address"] strong{
  color:var(--cm-text);
}
.footer[data-cloudif-footer="address"] .footer-line{
  display:block;
}
footer.cm-footer{
  display:none !important;
}


/* CloudIF v79 — compatibilidade com layout antigo da página Projetos */
.card{
  background:#fff;
  border:1px solid var(--cm-border);
  border-radius:18px;
  padding:18px;
  box-shadow:0 8px 20px rgba(20,40,20,.04);
  margin:16px 0;
}
.section-title{
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
  margin-bottom:16px;
}
.section-title h2{
  margin:0;
  font-size:22px;
  color:var(--cm-text);
}
.small{
  color:var(--cm-muted);
  font-size:13px;
  margin:5px 0;
}
.project-card{
  border:1px solid var(--cm-border);
  border-radius:16px;
  background:#fff;
  padding:16px;
  margin:12px 0;
}
.project-line{
  display:grid;
  grid-template-columns:minmax(260px,2fr) minmax(160px,1fr) minmax(160px,1fr) minmax(190px,1fr);
  gap:16px;
  align-items:start;
}
@media(max-width:980px){
  .project-line{
    grid-template-columns:1fr;
  }
}
.project-line h3{
  margin:0;
  font-size:18px;
  color:var(--cm-text);
}
.project-line b{
  color:var(--cm-text);
}
.btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:9px 12px;
  border-radius:10px;
  font-weight:700;
  font-size:14px;
  text-decoration:none !important;
  border:1px solid transparent;
  margin:3px;
  min-height:38px;
  cursor:pointer;
  background:var(--cm-green);
  color:#fff !important;
}
.btn.light{
  background:#fff;
  color:var(--cm-green-dark) !important;
  border-color:var(--cm-border);
}
.btn.gray{
  background:#f2f4f7;
  color:var(--cm-muted) !important;
  border-color:var(--cm-border);
}
.btn.blue,
.btn.amber{
  background:#fff;
  color:var(--cm-green-dark) !important;
  border-color:var(--cm-border);
}
.pill{
  display:inline-flex;
  align-items:center;
  border-radius:999px;
  padding:5px 10px;
  font-size:12px;
  font-weight:800;
  margin:4px 0;
  background:var(--cm-disabled-bg);
  color:var(--cm-muted);
}
.pill.ok{
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
}
.wizard{
  display:none;
  position:fixed;
  inset:0;
  background:rgba(15,23,42,.45);
  z-index:9999;
  padding:30px;
  overflow:auto;
}
.wizard.show{
  display:block;
}
.wizard .wizard-box{
  max-width:860px;
  margin:30px auto;
  background:#fff;
  border-radius:20px;
  border:1px solid var(--cm-border);
  box-shadow:0 24px 60px rgba(0,0,0,.25);
  padding:22px;
}
.wizard-head{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:flex-start;
}
.wizard-close{
  border:1px solid var(--cm-border);
  background:#fff;
  color:var(--cm-muted);
  border-radius:999px;
  width:38px;
  height:38px;
  cursor:pointer;
  font-size:20px;
}
.wizard-note{
  border:1px solid var(--cm-border);
  border-radius:14px;
  padding:12px;
  background:#f7fbf8;
  margin:12px 0;
}
.wizard-note strong{
  color:var(--cm-green-dark);
}


/* CloudIF v87 — dropdown de resultados reais AD/ACL */
.acl-result-dropdown{
  margin-top:10px;
  border:1px solid var(--cm-border);
  border-radius:14px;
  background:#fff;
  box-shadow:0 12px 28px rgba(15,23,42,.08);
  overflow:hidden;
}
.acl-result-item{
  width:100%;
  display:block;
  text-align:left;
  background:#fff;
  border:0;
  border-bottom:1px solid var(--cm-border);
  padding:12px 14px;
  cursor:pointer;
}
.acl-result-item:last-child{
  border-bottom:0;
}
.acl-result-item:hover{
  background:#f7fbf8;
}
.acl-result-main{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:center;
  margin-bottom:6px;
}
.acl-result-principal{
  font-weight:900;
  color:var(--cm-text);
}
.acl-result-type{
  border-radius:999px;
  padding:3px 8px;
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
  font-size:11px;
  font-weight:900;
}
.acl-result-meta{
  color:var(--cm-muted);
  font-size:12px;
  line-height:1.45;
}
.acl-result-groups{
  margin-top:7px;
  display:flex;
  flex-wrap:wrap;
  gap:5px;
}
.acl-result-group{
  border-radius:999px;
  padding:3px 8px;
  background:#eef2f7;
  color:#475569;
  font-size:11px;
  font-weight:800;
}
.acl-search-help{
  margin-top:7px;
  color:var(--cm-muted);
  font-size:12px;
}


/* CloudIF v88 — dropdown ACL sem tela legada */
.acl-result-dropdown{
  margin-top:10px;
  border:1px solid var(--cm-border);
  border-radius:14px;
  background:#fff;
  box-shadow:0 12px 28px rgba(15,23,42,.08);
  overflow:hidden;
}
.acl-result-item{
  width:100%;
  display:block;
  text-align:left;
  background:#fff;
  border:0;
  border-bottom:1px solid var(--cm-border);
  padding:12px 14px;
  cursor:pointer;
}
.acl-result-item:last-child{
  border-bottom:0;
}
.acl-result-item:hover{
  background:#f7fbf8;
}
.acl-result-main{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:center;
  margin-bottom:6px;
}
.acl-result-principal{
  font-weight:900;
  color:var(--cm-text);
}
.acl-result-type{
  border-radius:999px;
  padding:3px 8px;
  background:var(--cm-green-soft);
  color:var(--cm-green-dark);
  font-size:11px;
  font-weight:900;
}
.acl-result-meta{
  color:var(--cm-muted);
  font-size:12px;
  line-height:1.45;
}
.acl-result-groups{
  margin-top:7px;
  display:flex;
  flex-wrap:wrap;
  gap:5px;
}
.acl-result-group{
  border-radius:999px;
  padding:3px 8px;
  background:#eef2f7;
  color:#475569;
  font-size:11px;
  font-weight:800;
}
.acl-search-help{
  margin-top:7px;
  color:var(--cm-muted);
  font-size:12px;
}

</style>
"""

def btn(label, href="", enabled=True, primary=True, target=False):
    if not enabled:
        return f'<span class="cm-btn cm-disabled">{h(label)}</span>'
    cls = "cm-primary" if primary else "cm-secondary"
    target_attr = ' target="_blank" rel="noopener noreferrer"' if target else ""
    return f'<a class="cm-btn {cls}" href="{h(href)}"{target_attr}>{h(label)}</a>'

def pill(ok, ok_text="Ativo", off_text="Pendente"):
    cls = "cm-ok" if ok else "cm-off"
    return f'<span class="cm-pill {cls}">{h(ok_text if ok else off_text)}</span>'

def menu_tabs(active="resumo"):
    items = [
        ("resumo", "Resumo", "/cloudiff/portal/?tab=resumo"),
        ("projetos", "Projetos", "/cloudiff/portal/?tab=projetos"),
        ("reparo", "Verificação e reparação", "/cloudiff/portal/repair-dashboard"),
        ("bancos", "Bancos / Tenants", "/cloudiff/portal/?tab=bancos"),
        ("git", "Git + Komodo", "/cloudiff/portal/?tab=git"),
        ("admin", "Administração", "/cloudiff/portal/?tab=admin"),
        ("ajuda", "Ajuda", "/cloudiff/portal/?tab=ajuda"),
    ]
    links = []
    for key, label, href in items:
        cls = "active" if key == active else ""
        links.append(f'<a class="{cls}" href="{href}">{h(label)}</a>')
    return '<nav class="cm-menu-tabs">' + "".join(links) + "</nav>"

def banner(title, subtitle="", actions="", profile=""):
    return f"""
<div class="cm-banner">
  <div class="cm-banner-top">
    <div>
      <h2>{h(title)}</h2>
      <p>{h(subtitle)}</p>
    </div>
    {profile}
  </div>
  {f'<div class="cm-toolbar">{actions}</div>' if actions else ''}
</div>
"""

def footer():
    return """
<div class="footer" data-cloudif-footer="address">
  <span class="footer-line"><strong>Campus Bom Jesus do Itabapoana</strong></span>
  <span class="footer-line">Endereço: Av. Dário Viêira Borges, 235 - Lia Márcia, Bom Jesus do Itabapoana - RJ, 28360-000</span>
  <span class="footer-line">Telefone: (22) 3833-9850</span>
</div>

<script>
(function(){
  function ready(fn){
    if(document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function(){
    var official = document.querySelector('.footer[data-cloudif-footer="address"]');

    Array.from(document.querySelectorAll('.footer')).forEach(function(el){
      if(el === official) return;

      var text = (el.innerText || el.textContent || '').trim();

      if(
        text.indexOf('Portal interno CloudIF') >= 0 ||
        text.indexOf('uso didático') >= 0 ||
        text.indexOf('Instituto Federal Fluminense') >= 0
      ){
        el.style.display = 'none';
        el.setAttribute('data-cloudif-hidden-footer', 'legacy');
      }
    });
  });
})();
</script>
"""
def profile(user=None):
    user = user or {}
    username = user.get("username") or user.get("name") or "Usuário CloudIF"
    groups = user.get("groups") or []

    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(",") if g.strip()]

    group_html = "".join(f'<span class="cm-profile-group">{h(g)}</span>' for g in groups[:8])

    if len(groups) > 8:
        group_html += f'<span class="cm-profile-group">+{len(groups)-8}</span>'

    user_tie_svg = """
<svg class="cm-profile-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <circle cx="12" cy="7" r="4"/>
  <path d="M4 21c.7-4.4 3.7-7 8-7s7.3 2.6 8 7"/>
  <path d="M10.2 14.5 12 17l1.8-2.5"/>
  <path d="M12 17l-1.2 4h2.4L12 17z"/>
</svg>
"""

    return f"""
<details class="cm-profile-top">
  <summary title="Perfil">{user_tie_svg}</summary>
  <div class="cm-profile-body">
    <div class="cm-profile-name">{h(username)}</div>

    <div class="cm-profile-groups">
      {group_html or '<span class="cm-profile-group">sem grupo informado</span>'}
    </div>

    <div class="cm-profile-actions">
      <a href="/cloudiff/portal/?tab=ajuda">Ajuda</a>
      <a href="/cloudiff/portal/?tab=hardware">Informações da Plataforma</a>
      <a href="/cloudiff/portal/?tab=resumo&refresh=1">Atualizar cache</a>
    </div>
  </div>
</details>
"""
def profile_mount(user=None):
    prof = profile(user)
    return f"""
<div id="cm-profile-source" class="cm-profile-source">{prof}</div>
<script>
(function(){{
  function ready(fn){{
    if(document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }}
  function textOf(el){{
    return (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
  }}
  function hideLooseUserBox(){{
    var candidates = Array.from(document.querySelectorAll('.card, .cm-card, .panel, .box, section, div'));
    candidates = candidates.filter(function(el){{
      if(el.closest('.cm-profile-top')) return false;
      if(el.closest('.cm-profile-body')) return false;
      if(el.closest('.cm-profile-global-host')) return false;
      var t = textOf(el);
      if(!t || t.length > 500) return false;
      var hasUser = t.indexOf('Usuário:') >= 0 || t.indexOf('Usuario:') >= 0;
      var hasEmail = t.indexOf('Email:') >= 0 || t.indexOf('E-mail:') >= 0;
      var hasProfile = t.indexOf('Perfil:') >= 0;
      var hasGroups = t.indexOf('Grupos Authentik:') >= 0 || t.indexOf('Grupos:') >= 0;
      return hasUser && (hasEmail || hasProfile || hasGroups);
    }}).sort(function(a,b){{ return textOf(a).length - textOf(b).length; }});
    if(candidates.length) candidates[0].classList.add('cm-user-box-hidden');
  }}
  ready(function(){{
    var source = document.getElementById('cm-profile-source');
    if(!source) return;
    var profile = source.querySelector('.cm-profile-top');
    if(!profile) return;
    var already = document.querySelector('.cm-profile-global-host .cm-profile-top, .cm-profile-floating .cm-profile-top');
    if(already){{
      source.remove();
      hideLooseUserBox();
      return;
    }}
    var targets = [
      document.querySelector('header nav'),
      document.querySelector('header .nav'),
      document.querySelector('header .tabs'),
      document.querySelector('header .menu'),
      document.querySelector('header'),
      document.querySelector('.topbar'),
      document.querySelector('.header'),
      document.querySelector('.navbar'),
      document.querySelector('nav')
    ].filter(Boolean);
    var host = document.createElement('div');
    host.className = 'cm-profile-global-host';
    if(targets[0]){{
      targets[0].style.display = 'flex';
      targets[0].style.alignItems = 'center';
      targets[0].style.width = '100%';
      targets[0].appendChild(host);
      host.appendChild(profile);
    }} else {{
      host.className = 'cm-profile-floating';
      document.body.appendChild(host);
      host.appendChild(profile);
    }}
    source.remove();
    hideLooseUserBox();
  }});
}})();
</script>
"""

def layout(active, title, subtitle, content, user=None, actions=""):
    return f"""
{css()}
<div class="cm-page">
  {banner(title, subtitle, actions)}
  {content}
  {profile_mount(user)}
  {footer()}
</div>
"""



# CloudIF v70 safe profile_mount override
def profile_mount(user=None):
    prof = profile(user)
    return f"""
<div id="cm-profile-source" class="cm-profile-source">{prof}</div>
<script>
(function(){{
  function ready(fn){{
    if(document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }}

  function textOf(el){{
    return (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
  }}

  function hideLooseUserBox(){{
    Array.from(document.querySelectorAll('.userbar, .user-bar, #userbar, #user-bar, .card.userbar, .card.user-bar, [data-component="userbar"], [data-cloudif-userbar]')).forEach(function(el){{
      if(!el.closest('.cm-profile-top') && !el.closest('.cm-profile-body')){{
        el.classList.add('cm-userbar-hidden');
      }}
    }});

    var candidates = Array.from(document.querySelectorAll('.card, .cm-card, .panel, .box, section, div'));
    candidates = candidates.filter(function(el){{
      if(el.closest('.cm-profile-top')) return false;
      if(el.closest('.cm-profile-body')) return false;
      if(el.closest('.cm-profile-global-host')) return false;

      var t = textOf(el);
      if(!t || t.length > 500) return false;

      var hasUser = t.indexOf('Usuário:') >= 0 || t.indexOf('Usuario:') >= 0;
      var hasEmail = t.indexOf('Email:') >= 0 || t.indexOf('E-mail:') >= 0;
      var hasProfile = t.indexOf('Perfil:') >= 0;
      var hasGroups = t.indexOf('Grupos Authentik:') >= 0 || t.indexOf('Grupos:') >= 0;

      return hasUser && (hasEmail || hasProfile || hasGroups);
    }}).sort(function(a,b){{
      return textOf(a).length - textOf(b).length;
    }});

    if(candidates.length){{
      candidates[0].classList.add('cm-user-box-hidden');
    }}
  }}

  ready(function(){{
    var source = document.getElementById('cm-profile-source');
    if(!source) return;

    var profile = source.querySelector('.cm-profile-top');
    if(!profile) return;

    var already = document.querySelector('.cm-profile-global-host .cm-profile-top, .cm-profile-floating .cm-profile-top');
    if(already){{
      source.remove();
      hideLooseUserBox();
      return;
    }}

    var targets = [
      document.querySelector('header nav'),
      document.querySelector('header .nav'),
      document.querySelector('header .tabs'),
      document.querySelector('header .menu'),
      document.querySelector('header'),
      document.querySelector('.topbar'),
      document.querySelector('.header'),
      document.querySelector('.navbar'),
      document.querySelector('nav')
    ].filter(Boolean);

    var host = document.createElement('div');
    host.className = 'cm-profile-global-host';

    if(targets[0]){{
      targets[0].style.display = 'flex';
      targets[0].style.alignItems = 'center';
      targets[0].style.width = '100%';
      targets[0].appendChild(host);
      host.appendChild(profile);
    }} else {{
      host.className = 'cm-profile-floating';
      document.body.appendChild(host);
      host.appendChild(profile);
    }}

    source.remove();
    hideLooseUserBox();
  }});
}})();
</script>
"""
