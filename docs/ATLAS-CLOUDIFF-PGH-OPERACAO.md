# Runbook — Atlas, CloudIFF, GitHub e PGH

Data da observação: 14/11/2026. Responsável: documentacao/cloudiff/doc-01.
Os estados administrativos e dados históricos não comprovam a saúde atual.

## Responsabilidades e fontes da verdade
- Atlas: catálogo consultável de projetos, hosts, dependências, ambientes, repositórios e evidências.
- CloudIFF Portal, Forgejo, Komodo e hosts: fontes operacionais para confirmação de estado.
- GitHub debianlima/cloudiff: código-fonte da plataforma, alterações funcionais sob dev-01.
- GitHub debianlima/dotfiles: inventário e procedimentos de infraestrutura; NÃO é o repositório do código da plataforma.
- PGH LabIFF: memória canônica append-only e handoffs, usando agent-memory-v2.py.
- Aud-01: validação de rastreabilidade, cobertura, backups, permissões e segurança.

## Inventário dos oito tenants no Portal
Fonte: leitura SQLite em 14/11/2026T13:33:54Z, evidência INVENTARIO-CLOUDIFF-PARA-ATLAS-2026-11-14.md.

| Projeto | Estado administrativo | ACLs | Organização Forgejo |
| --- | --- | ---: | --- |
| agenda-unica | published | 8 | iff1742962 |
| cadales | published | 15 | iff1742962 |
| cpuhub | published | 9 | iff1742962 |
| laboratorio-de-hardware | published | 3 | iff1742962 |
| msha | draft | 1 | iff3546365 |
| mvplanner | draft | 3 | iff1860746 |
| paperclip | published | 1 | iff1742962 |
| silvipro | published | 8 | iff1860746 |

O repositório Forgejo de cada tenant usa o padrão cloudif-<slug> na organização indicada.
Confirmar novas inclusões diretamente no Portal, sem depender desta lista fixa.

## Infraestrutura no escopo
Forja (10.62.91.2): Git/Komodo e agentes. Hospedagem (10.62.92.7):
Portal, containers e serviços tenants. Maurício (10.62.91.3): proxy e distribuição.
Faro (10.62.91.5): Taiga e reconciliação. LabIFF pghd-server: memória e evidências.
IPsec: instalação Atlas, cuja API local foi observada na porta 8792.
A leitura Docker nos hosts além de Hospedagem não foi autorizada na auditoria.

## Estado Atlas registrado na memória PGH
- Importados oito registros CloudIFF novos por API autorizada.
- Itens: 197 antes, 205 depois; grafo: 236 nós antes, 244 depois.
- Reexecução de idempotência: 8 skip, 0 update.
- Arquivo de evidência LabIFF: evidencias/BASELINE-ATLAS-CLOUDIFF-2026-11-14.json.
- Auditoria no IPsec: /srv/mcp-workspace/atlas-cloudiff-import-audit-2026-11-14.json.
- Backup no IPsec: /var/backups/mapa-projetos/portal-pre-cloudiff-20261114T133951Z.sqlite.
- IDs de projeto Atlas: cloudiff.project.<slug_com_underscore>.
- Código Atlas em execução difere da revisão Git bare 724d24b: NÃO fazer reset, checkout,
  deploy ou substituição antes de reconciliar server.py, ontology.py e ui.js.

## Campos mínimos Atlas
ID estável, nome, slug, tipo project, categoria, status com fonte e timestamp,
repo_url Forgejo, URL de serviço confirmada, host, ambiente, localização, finalidade,
tags, links a runbooks, relacionamentos e referências de segurança sem credenciais.
Indicar NAO VERIFICADO quando não houver fonte; nunca inventar health ou SHA.

## W1 / Hn / Pn
Documentar por projeto W1 preview (fonte sincronizada aprovada),
Hn homologação isolada e congelada e Pn produção promovida por artefato rastreável.
Conferir SHA, digest, volumes, banco, ACL, proxy, health, dependências e rollback.
Não presumir que esta arquitetura está funcional em todos os tenants.

## Procedimento para cada atualização
1. Retomar doc-01 pelo CLI PGH v2, ler tarefas e verificar locks e concorrência.
2. Levantar alterações reais no Portal, Forgejo, GitHub, Komodo e hosts; registrar fonte,
   horário, IDs, commit, versão e limites do acesso.
3. Calcular diff no Atlas; criar backup/export com possibilidade de restauração.
4. Aplicar upsert idempotente somente por API autorizada; não excluir itens desconhecidos.
5. Reler registros e conferir relacionamentos, contagens, backup e divergências.
6. Atualizar documentação em worktree/branch independente com reserva de arquivos.
7. Verificar links, diffs, dados sigilosos e documentação; publicar via revisão/PR
   no repositório correto, jamais force-push ou alterações silenciosas de produção.
8. Registrar commits, evidências, falhas e handoff no PGH, solicitar auditoria aud-01.
9. Eventos acionadores: projeto novo, mudança de Git, release, alteração de infraestrutura,
   ACL, incidente ou correção. Agendamento só após homologar autenticação, limites e logs.

## Bloqueios e observações relevantes
- Ainda é preciso conferir ACL efetiva/terminal no Komodo e saúde dos tenants.
- Publicado no Portal não significa container saudável.
- Verificar divergências MVPlanner, Paperclip, SilviPro, MSHA e Agenda Única.
- Não presumir que HEAD do GitHub corresponde ao código implantado.
- Separar versões de plataforma CloudIFF, repos Forgejo de tenants e Dotfiles.
- O código instalado Atlas diverge do Git: conciliar antes de automatizar.
- Nunca incluir .env, tokens, credenciais ou chaves em Atlas, GitHub, PGH ou logs.

## Critérios de aceite
Cobertura de 100% dos projetos confirmados no Portal ou divergência registrada;
sem dados secretos; vínculos Git comprovados; Atlas idempotente; evidências com horário;
mudanças de documentação rastreadas por SHA/PR; revisões de aud-01 nas inconformidades.

## Evidências e referências de execução
- LabIFF cloudiff-admin/evidencias/INVENTARIO-CLOUDIFF-PARA-ATLAS-2026-11-14.md
- LabIFF cloudiff-admin/PLANO-ATLAS-GITHUB-CLOUDIFF-PGH-2026-11-14.md
- LabIFF cloudiff-admin/evidencias/AUDITORIA-GERAL-CLOUDIFF-2026-11-13.md
- Memória PGH documentacao/cloudiff/doc-01, tarefas T-004 a T-011

## Atualização de inventário — 14/11/2026T13:56Z
Consulta read-only à API local Atlas na VPS IPsec retornou 213 itens; além das oito fichas cloudiff.project.*, existem oito fichas cloudiff.repo.* (CloudIFF / Forgejo) referenciando os tenants. As 205 fichas anteriores são baseline histórico, não o total atual. Ver [procedimento de conciliação](ATLAS-CLOUDIFF-CONCILIACAO.md) para verificações e gatilhos.

## Equipe PGH de seis agentes

A equipe operacional do projeto CloudIFF possui aud-01, dev-01, dev-02, doc-01, infra-01 e surface-01. Infra-01 cuida de segurança/infraestrutura; surface-01 testa interfaces como usuário autorizado. Ambos usam finding-dispatch para distribuir achados; aud-01 utiliza audit-dispatch. As seis identidades operacionais CloudIFF e a identidade Dotfiles estão registradas no Atlas. Veja [catálogo de agentes e roteamento](PGH-AGENTES-CLOUDIFF.md). Sempre consultar o catálogo online do LabIFF em vez de fixar a lista no plugin.

## Como localizar a plataforma CloudIFF e seus projetos no Atlas

Observação da publicação: 14/11/2026, aproximadamente 19:22 UTC.
- Acesse o Atlas autenticado em https://atlas.limaeducation.duckdns.org/#projetos-repositorios
- No menu Projetos & Repositórios, a seção **CloudIFF — Projetos** aparece
  antes da lista geral de repositórios. Ela mostra a ficha da plataforma e
  os oito projetos registrados no Portal: Agenda Única, Cadales, CPUHub,
  Laboratório de Hardware, MSHA, MVPlanner, Paperclip e SilviPro.
- A seção é formada a partir dos vínculos explícitos da ontologia Atlas,
  onde cada ficha cloudiff.project.<slug> possui relação partOf com
  cloudiff.project.platform. Outros tipos de item não entram na grade.
- Os projetos podem ser acessados pelo cartão e a plataforma pelo botão
  Abrir ficha CloudIFF. A visualização semântica também mostra esses vínculos.
- O estado published/draft representa apenas o cadastro no Portal, e
  não a disponibilidade operacional dos containers.

Correção técnica registrada no Git local do Atlas: branch
fix/doc01-cloudiff-platform-projects-20261114, commit
9faf001077e833bcb48e0631a117ed074c565f68.
A versão foi ativada no caminho real /opt/mapa-projetos/ui.js, sem reiniciar
o serviço; arquivo servido e oito vínculos foram validados por HTTP/API.
Backup operacional root e registro de auditoria foram mantidos no IPsec.
Teste visual com navegador autenticado permanece sob responsabilidade de
surface-01 e não deve ser declarado concluído sem evidência.

## Visualização dos arquivos Markdown de controle no Atlas

**Atualização de 14/11/2026:** acesse o [painel de documentos CloudIFF](https://atlas.limaeducation.duckdns.org/acompanhamento?project=cloudiff.project.platform&tab=arquivos). Na guia **Arquivos .md**, escolha um documento na lista vertical; o conteúdo é mostrado em texto e pode ser baixado em .md para consulta humana.

O portal gera **projeções sanitizadas**, não o conteúdo original completo do PGH. Para CloudIFF com feed associado, as fichas incluem PROJECT.md, SOURCES.md, TASKS.md, HISTORY.md, MEMORY.md, INSTRUCTIONS.md, AUDITS.md e BACKUPS.md. Referências históricas REVISIONS.md são oferecidas quando houver fonte documentada. Os arquivos originais ACCESS.md, evidências sensíveis, backups binários, segredos e logs privados **não são disponibilizados**.

Para cada um dos oito tenants, a ficha própria mostra projeto e fonte (PROJECT.md, SOURCES.md), com acesso ao controle transversal CloudIFF. Não são inventadas tarefas, eventos ou memórias particulares de tenants sem journal vinculado. O catálogo Atlas apresenta 24 projetos, mas apenas CloudIFF e Dotfiles têm feed PGH vinculado no snapshot atual.

O snapshot PGH foi atualizado manualmente às **21h19 UTC de 14/11/2026**, incluindo 242 eventos CloudIFF e 12 de Dotfiles. Não há sincronização automática aprovada: conferir sempre o horário da coleta antes de usar o documento como evidência de estado. A página é protegida por autenticação Nginx (HTTP 401 sem credenciais).

A primeira entrega da aba é o commit Atlas ddd305670f30a49c15282d49c9abdcbdba139271 na branch feature/doc01-control-md-human-viewer-20261114. Foi publicada também uma revisão de segurança (352c4dcb4cc5742ec979447903ce789698dc35c8, branch fix/doc01-control-md-download-safety-20261114) que neutraliza HTML e padrões de credenciais em Markdown exportado, com testes automatizados aprovados. A entrega permaneceu no Git bare interno do Atlas; promover para o ramo principal só após reconciliação e gates. O teste headless confirmou a renderização da aba, mas a automação interativa de cliques/download ainda não foi concluída. Surface-01 deve executar o aceite autenticado no navegador.
