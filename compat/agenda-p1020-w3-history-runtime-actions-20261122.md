# Agenda P1020 — W3 fixo e ações de histórico (2026-11-22 UTC)

## Contrato observado

- O Preview do Agenda é um slot fixo existente: **W3**.
- Alterações do Forgejo atualizam o mesmo Preview; não criam W novo por commit.
- Produções históricas permanecem **Offline** até ação humana.
- **Subir** liga uma P histórica apenas no hostname versionado e não altera o endereço principal.
- **Ativar no endereço principal** é uma ação separada e é a única que faz cutover.
- **Desligar** para a P histórica e preserva os recursos para rollback posterior.

## Correções aplicadas

1. Formulário de variáveis: removida a chamada quebrada `envLabel(...)` do caminho de save e mantido label seguro pelo mapa `envLabels`.
2. Preview Compose vinculado: geração fixa passa a ser derivada do histórico do projeto; no Agenda, W3.
3. Metadados H4–H7 corrigidos para `preview_generation=3` / `sourcePreviewStageCode=W3`.
4. W1 bridge/rota removidos somente depois de W3 responder saudável.
5. Histórico de Produção: estado real `active|online|offline`, ações `Subir`, `Desligar` e `Ativar no endereço principal` separadas.
6. Legado P2: `prepare` e `status` próprios, sem aplicar `cloudif-p1020-active-web`; tolera uma reinicialização controlada no cold-start.
7. Metadado legado P2 `is_active` reconciliado para 0 quando parado.

## Evidência de runtime

- Preview W3: `https://1020-w3-preview.cloudiff.duckdns.org/` — saudável.
- Produção ativa P7: `https://1020-p7-publication.cloudiff.duckdns.org/` — saudável.
- Endereço principal: `https://agendaunica.cloudiff.duckdns.org/` — mesma revisão de P7.
- Revisão atual W3/P7/principal: `18416127cdf9`.
- P6 foi subida em modo histórico e respondeu revisão `e32213d0b4d2`; durante todo o teste o domínio principal permaneceu em `18416127cdf9`; em seguida P6 voltou a Offline.
- P2 foi subida em modo histórico, respondeu no hostname P2, permaneceu sem alias ativo e com `is_active=0`; o domínio principal permaneceu em P7; em seguida P2 voltou a Offline.
- P3/P6: deployments internos `inactive`, serviços `exited`.
- P7: único deployment de Produção `running`, três serviços saudáveis.
- H4: runtime removido; H5/H6 correspondem às P3/P6 históricas paradas; H7 é a mesma instância promovida que sustenta P7.

## Testes

- `portal.tests.test_release_flow_v144`: 11/11 PASS.
- `portal.tests.test_project_publication_configuration_v1`: 7/7 PASS com `PYTHONPATH` do projeto.
- JavaScript `publication-release.js`: `node --jitless --check` PASS.
- Python live: `py_compile` PASS nos módulos alterados.
- W3, P7 e domínio principal: HTTP 200 após reinício final do Portal.

## Rollback

- W3 cutover: backups em `agenda-preview-w3-20261121T234416Z` nos hosts envolvidos.
- Runtimes legados da Hospedagem: inspect backups em `agenda-legacy-runtimes-20261121T233402Z`; containers foram apenas parados, não removidos.
- Komodo antes das ações de histórico: `/srv/cloudif/backups/agenda-history-actions-20261121T234701Z/`.
- O patch `agenda-p1020-history-runtime-actions-live-komodo.patch` registra um delta reproduzível do Komodo desta unidade.

## Reconciliação canônica

Os deltas desta unidade para `portal_publications`, overview, Komodo, UI e Histórico foram incorporados à árvore canônica com testes de regressão. O patch `agenda-p1020-history-runtime-actions-live-komodo.patch` permanece como evidência incremental do runtime live anterior à consolidação; não contém secrets.
