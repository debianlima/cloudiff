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
