(() => {
  if (document.getElementById('cloudif-release-flow')) return;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const mount = document.querySelector('.legacy-content') || document.body;
  const layer = document.createElement('div');
  layer.id = 'cloudif-release-flow';
  layer.setAttribute('role', 'dialog');
  layer.setAttribute('aria-modal', 'true');
  layer.setAttribute('aria-labelledby', 'release-wizard-title');
  layer.innerHTML = `
    <section class="release-wizard">
      <header>
        <div>
          <span class="release-kicker">Publicação</span>
          <h2 id="release-wizard-title">Gerenciar publicação</h2>
          <p data-release-project></p>
        </div>
        <button type="button" class="release-wizard-close" aria-label="Fechar">×</button>
      </header>
      <nav class="release-tabs" aria-label="Etapas da publicação">
        <button type="button" data-release-tab="preview">Preview</button>
        <button type="button" data-release-tab="homologation">Homologação</button>
        <button type="button" data-release-tab="publication">Produção</button>
      </nav>
      <main class="release-wizard-body" data-release-body><p>Carregando fluxo…</p></main>
      <footer class="release-wizard-footer">
        <span>Promova o mesmo artefato do Preview até Produção.</span>
        <div>
          <button type="button" class="btn light" data-release-refresh>Atualizar</button>
          <button type="button" class="btn light" data-release-close>Fechar</button>
        </div>
      </footer>
    </section>`;
  mount.appendChild(layer);

  const model = {
    slug: '', tab: 'preview', data: null, csrf: '', approval: null,
    poll: null, busy: false, opener: null, autoPreviewAttempted: false,
    previewPreparing: false, previewError: ''
  };
  const body = layer.querySelector('[data-release-body]');

  function apiBase() {
    return '/cloudiff/portal/api/projects/' + encodeURIComponent(model.slug) + '/release-flow';
  }

  async function call(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(options.headers || {}) },
      ...options
    });
    const data = await response.json().catch(() => ({ ok: false, error: { message: 'Resposta inválida da plataforma.' } }));
    if (!response.ok || !data.ok) {
      const error = data.error || {};
      throw new Error(String(error.message || error.code || data.message || 'Operação indisponível.'));
    }
    return data;
  }

  function post(operation, payload = {}) {
    return call(apiBase() + '/' + operation, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': model.csrf },
      body: JSON.stringify(payload)
    });
  }

  function close() {
    layer.classList.remove('is-open');
    document.body.classList.remove('cloudif-modal-open');
    clearTimeout(model.poll);
    model.poll = null;
    const opener = model.opener;
    model.opener = null;
    if (opener && document.contains(opener)) opener.focus();
  }

  function selectTab(name) {
    model.tab = ['preview', 'homologation', 'publication'].includes(name) ? name : 'preview';
    layer.querySelectorAll('[data-release-tab]').forEach(button => {
      button.classList.toggle('is-active', button.dataset.releaseTab === model.tab);
    });
    render();
  }

  function activeRelease() {
    const data = model.data || {};
    return (data.releases || []).find(item => Number(item.is_active) === 1) || data.legacyProduction || null;
  }

  function latestCandidate() {
    return ((model.data || {}).candidates || [])[0] || null;
  }

  function activationFor(candidate) {
    return ((model.data || {}).activationRequests || []).find(
      item => Number(item.candidate_number) === Number(candidate && candidate.candidate_number)
    ) || null;
  }

  function jobHtml() {
    const job = model.data && model.data.job;
    if (!job || !['queued', 'running'].includes(job.status)) return '';
    const labels = {
      homologation_candidate: 'Preparando Homologação',
      production_release: 'Publicando em Produção'
    };
    return `<div class="release-job"><strong>${esc(labels[job.operation] || 'Operação em andamento')}</strong><span>${esc(job.message || 'Processando…')}</span><progress></progress></div>`;
  }

  function stageIntro(code, title, text, badge, badgeClass = '') {
    return `<div class="release-stage-head"><div><span class="release-kicker">${esc(code)}</span><h3>${esc(title)}</h3><p>${esc(text)}</p></div><span class="release-badge ${badgeClass}">${esc(badge)}</span></div>`;
  }

  function renderPreview() {
    const data = model.data || {};
    const preview = data.preview || {};
    const ready = Boolean(preview.configured && preview.healthy);
    const code = preview.stageCode || 'W1';
    const git = preview.git || {};
    let action = '';
    if (model.previewPreparing) {
      action = '<button class="btn" type="button" disabled>Preparando Preview automaticamente…</button>';
    } else if (ready && data.canWrite) {
      action = '<button class="btn" type="button" data-release-action="homologation-create">Enviar Preview para homologação</button>';
    } else if (model.previewError && data.canWrite) {
      action = '<button class="btn light" type="button" data-release-action="preview-auto-retry">Tentar preparar Preview</button>';
    }
    const note = model.previewError
      ? `<div class="release-note"><strong>Preview ainda não ficou pronto.</strong><span>${esc(model.previewError)}</span></div>`
      : '';
    return jobHtml() + `<section class="release-stage">${stageIntro(
      code + ' · Preview',
      ready ? 'Preview pronto' : (model.previewPreparing ? 'Preparando Preview' : 'Preview em preparação'),
      'O Preview acompanha automaticamente o que está em desenvolvimento. Quando estiver pronto, envie o mesmo estado para Homologação.',
      ready ? 'Pronto' : (model.previewPreparing ? 'Preparando' : 'Pendente'),
      ready ? 'ok' : ''
    )}${note}<div class="release-grid"><div class="release-box"><span>Estado</span><strong>${ready ? 'Online' : 'Preparação automática'}</strong></div><div class="release-box"><span>Git atual</span><strong>${esc(git.status || 'Aguardando')}</strong><small>${esc((git.head || '').slice(0, 12))}</small></div></div><div class="release-primary-action">${action}</div></section>`;
  }

  function renderHomologation() {
    const data = model.data || {};
    const candidate = latestCandidate();
    const preview = data.preview || {};
    const previewReady = Boolean(preview.configured && preview.healthy);
    if (!candidate) {
      const action = previewReady && data.canWrite
        ? '<button class="btn" type="button" data-release-action="homologation-create">Enviar Preview para homologação</button>'
        : '<button class="btn" type="button" disabled>Aguardando Preview</button>';
      return jobHtml() + `<section class="release-stage">${stageIntro(
        'H · Homologação', 'Aguardando candidato',
        'Homologação recebe uma cópia imutável do Preview atual.',
        'Sem candidato'
      )}<div class="release-primary-action">${action}</div></section>`;
    }

    const labels = {
      awaiting_homologation: 'Aguardando homologação',
      homologated: 'Homologado', rejected: 'Rejeitado', published: 'Publicado'
    };
    let actions = '';
    if (candidate.status === 'awaiting_homologation' && data.canHomologate) {
      actions = `<button class="btn" type="button" data-release-action="homologation-approve" data-candidate="${Number(candidate.candidate_number)}">Homologar</button><button class="btn light" type="button" data-release-action="homologation-reject" data-candidate="${Number(candidate.candidate_number)}">Rejeitar</button>`;
    } else if (candidate.status === 'homologated') {
      actions = '<button class="btn" type="button" data-release-action="go-production">Ir para Produção</button>';
    } else if (['rejected', 'published'].includes(candidate.status) && data.canWrite) {
      actions = '<button class="btn" type="button" data-release-action="homologation-create">Enviar novo Preview para homologação</button>';
    }
    return jobHtml() + `<section class="release-stage">${stageIntro(
      (candidate.stage_code || 'H') + ' · Homologação',
      labels[candidate.status] || candidate.status,
      'Este candidato é imutável. Homologue ou rejeite; o Preview pode continuar evoluindo em paralelo.',
      labels[candidate.status] || candidate.status,
      ['homologated', 'published'].includes(candidate.status) ? 'ok' : ''
    )}<div class="release-grid"><div class="release-box"><span>Commit congelado</span><code>${esc((candidate.commit_sha || '').slice(0, 12))}</code></div><div class="release-box"><span>Origem</span><strong>W${Number(candidate.preview_generation || 0)}</strong></div></div><div class="release-primary-action">${actions}</div></section>`;
  }

  function renderProduction() {
    const data = model.data || {};
    const candidate = (data.candidates || []).find(item => item.status === 'homologated') || latestCandidate();
    const active = activeRelease();
    const activation = activationFor(candidate);
    const live = model.approval;
    let action = '';
    let approval = '';

    if (candidate && candidate.status === 'homologated' && data.canPublish) {
      if (!activation) {
        action = `<button class="btn" type="button" data-release-action="production-request" data-candidate="${Number(candidate.candidate_number)}">Publicar em Produção</button>`;
      } else if (live && live.status === 'approved') {
        action = `<button class="btn" type="button" data-release-action="production-enqueue" data-candidate="${Number(candidate.candidate_number)}" data-approval="${esc(live.approvalId)}" data-digest="${esc(live.activationDigest)}">Publicar em Produção</button>`;
      } else {
        approval = '<div class="release-note"><strong>Publicação aguardando aprovação.</strong><span>A etapa de Produção continua bloqueada até a autorização necessária.</span></div>';
        action = '<a class="btn light" href="/cloudiff/portal/?tab=aprovacoes">Abrir aprovação</a>';
      }
    }

    const current = active
      ? `<div class="release-grid"><div class="release-box"><span>Produção atual</span><strong>${esc(active.stage_code || 'P ativa')}</strong></div><div class="release-box"><span>Endereço</span><strong>${esc(active.stableUrl || active.stable_hostname || active.url || 'Ativo')}</strong></div></div>`
      : '<div class="release-note"><strong>Ainda não há Produção ativa.</strong><span>Homologue um candidato para habilitar a publicação.</span></div>';

    return jobHtml() + `<section class="release-stage">${stageIntro(
      'P · Produção',
      active ? 'Produção ativa' : 'Pronto para publicar',
      'Produção recebe exatamente o artefato homologado, sem reconstrução entre H e P.',
      active ? (active.stage_code || 'Ativa') : 'Sem P ativa',
      active ? 'ok' : ''
    )}${current}${approval}<div class="release-primary-action">${action}</div></section>`;
  }

  function render() {
    if (!model.data) {
      body.innerHTML = '<p>Carregando fluxo…</p>';
      return;
    }
    body.innerHTML = model.tab === 'preview'
      ? renderPreview()
      : model.tab === 'homologation'
        ? renderHomologation()
        : renderProduction();
    bindActions();
  }

  function updateSummary(slug, data) {
    document.querySelectorAll('[data-release-flow-summary="' + CSS.escape(slug) + '"]').forEach(root => {
      const w = root.querySelector('[data-release-summary-w]');
      const h = root.querySelector('[data-release-summary-h]');
      const p = root.querySelector('[data-release-summary-p]');
      const preview = data.preview || {};
      const candidate = (data.candidates || [])[0];
      const release = (data.releases || []).find(item => Number(item.is_active) === 1) || data.legacyProduction;
      w.textContent = preview.configured ? (preview.stageCode + ' · ' + (preview.healthy ? 'online' : 'atenção')) : 'Preparação automática';
      h.textContent = candidate ? (candidate.stage_code + ' · ' + ({ awaiting_homologation: 'aguardando', homologated: 'homologado', rejected: 'rejeitado', published: 'publicado' }[candidate.status] || candidate.status)) : 'Sem candidato';
      p.textContent = release ? (release.stage_code || 'P ativa') : 'Sem publicação';
    });
  }

  async function ensurePreviewAutomatically() {
    if (model.autoPreviewAttempted || model.previewPreparing || !model.data || !model.data.canWrite) return;
    const preview = model.data.preview || {};
    if (preview.configured && preview.healthy) return;
    model.autoPreviewAttempted = true;
    model.previewPreparing = true;
    model.previewError = '';
    render();
    try {
      await post('preview/ensure', {});
      model.previewPreparing = false;
      await load();
    } catch (error) {
      model.previewPreparing = false;
      model.previewError = String(error.message || 'Não foi possível preparar o Preview automaticamente.');
      render();
    }
  }

  async function load() {
    clearTimeout(model.poll);
    try {
      const data = await call(apiBase());
      model.data = data;
      model.csrf = data.csrfToken || model.csrf;
      model.approval = null;
      const activation = (data.activationRequests || [])[0];
      if (activation && activation.approval_id) {
        try {
          model.approval = await call(apiBase() + '/approval/status?approvalId=' + encodeURIComponent(activation.approval_id));
        } catch (_) {}
      }
      render();
      updateSummary(model.slug, data);
      if (!(data.preview || {}).configured && !model.autoPreviewAttempted) {
        void ensurePreviewAutomatically();
      }
      if (data.job && ['queued', 'running'].includes(data.job.status)) model.poll = setTimeout(load, 2200);
    } catch (error) {
      body.innerHTML = `<div class="release-note"><strong>Não foi possível carregar o fluxo.</strong><span>${esc(error.message)}</span></div>`;
    }
  }

  async function act(operation, payload = {}, message = 'Processando…', nextTab = '') {
    if (model.busy) return;
    model.busy = true;
    body.insertAdjacentHTML('afterbegin', `<div class="release-job"><strong>${esc(message)}</strong><progress></progress></div>`);
    try {
      await post(operation, payload);
      if (nextTab) model.tab = nextTab;
      await load();
    } catch (error) {
      await load();
      body.insertAdjacentHTML('afterbegin', `<div class="release-note"><strong>Não foi possível concluir.</strong><span>${esc(error.message)}</span></div>`);
    } finally {
      model.busy = false;
    }
  }

  async function requestProduction(candidate) {
    if (model.busy) return;
    model.busy = true;
    try {
      const result = await post('production/approval/request', {
        candidateNumber: Number(candidate), reason: 'Publicar candidato homologado em Produção'
      });
      if (result.status === 'approved') {
        await post('production/enqueue', {
          candidateNumber: Number(candidate), approvalId: result.approvalId, activationDigest: result.activationDigest
        });
      }
      model.tab = 'publication';
      await load();
    } catch (error) {
      await load();
      body.insertAdjacentHTML('afterbegin', `<div class="release-note"><strong>Publicação não iniciada.</strong><span>${esc(error.message)}</span></div>`);
    } finally {
      model.busy = false;
    }
  }

  function bindActions() {
    body.querySelectorAll('[data-release-action]').forEach(button => {
      button.onclick = async () => {
        const action = button.dataset.releaseAction;
        const candidate = Number(button.dataset.candidate || 0);
        if (action === 'preview-auto-retry') {
          model.autoPreviewAttempted = false;
          return ensurePreviewAutomatically();
        }
        if (action === 'homologation-create') {
          return act('homologation/enqueue', {}, 'Enviando Preview para Homologação…', 'homologation');
        }
        if (action === 'homologation-approve') {
          return act('homologation/approve', { candidateNumber: candidate }, 'Homologando candidato…');
        }
        if (action === 'homologation-reject') {
          const note = prompt('Motivo da rejeição:') || '';
          if (note.trim()) return act('homologation/reject', { candidateNumber: candidate, note }, 'Registrando rejeição…');
          return;
        }
        if (action === 'go-production') return selectTab('publication');
        if (action === 'production-request') return requestProduction(candidate);
        if (action === 'production-enqueue') {
          return act('production/enqueue', {
            candidateNumber: candidate,
            approvalId: button.dataset.approval,
            activationDigest: button.dataset.digest
          }, 'Publicando em Produção…', 'publication');
        }
      };
    });
  }

  function open(button) {
    model.opener = button;
    model.slug = button.dataset.projectSlug || '';
    model.tab = 'preview';
    model.data = null;
    model.approval = null;
    model.autoPreviewAttempted = false;
    model.previewPreparing = false;
    model.previewError = '';
    layer.querySelector('[data-release-project]').textContent = model.slug;
    layer.classList.add('is-open');
    document.body.classList.add('cloudif-modal-open');
    selectTab('preview');
    void load();
    setTimeout(() => layer.querySelector('[data-release-tab].is-active')?.focus(), 0);
  }

  layer.querySelector('.release-wizard-close').onclick = close;
  layer.querySelector('[data-release-close]').onclick = close;
  layer.querySelector('[data-release-refresh]').onclick = load;
  layer.querySelectorAll('[data-release-tab]').forEach(button => button.onclick = () => selectTab(button.dataset.releaseTab));
  layer.addEventListener('click', event => { if (event.target === layer) close(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && layer.classList.contains('is-open')) close(); });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-release-flow-open]');
    if (button) open(button);
  });

  const params = new URLSearchParams(location.search);
  const deepLinkProject = params.get('project') || '';
  if (params.get('tab') === 'publicacao' && deepLinkProject && params.get('open') === 'release') {
    const button = [...document.querySelectorAll('[data-release-flow-open]')].find(item => item.dataset.projectSlug === deepLinkProject);
    if (button) setTimeout(() => open(button), 0);
  }

  const roots = [...document.querySelectorAll('[data-release-flow-summary]')];
  async function loadSummary(root) {
    const slug = root.dataset.releaseFlowSummary;
    if (!slug) return;
    try {
      updateSummary(slug, await call('/cloudiff/portal/api/projects/' + encodeURIComponent(slug) + '/release-flow'));
    } catch (_) {}
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) {
        void loadSummary(entry.target);
        observer.unobserve(entry.target);
      }
    }), { rootMargin: '150px' });
    roots.forEach(root => observer.observe(root));
  } else {
    roots.forEach(root => void loadSummary(root));
  }
})();
