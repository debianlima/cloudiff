# Atlas, PGH e CloudIFF — reconciliação documental

> Procedimento de governança documental. Não instala automações, não modifica
> ambientes em produção e não concede permissões de administração.

## Finalidade

O Atlas indexa projetos, repositorios, servicos, ambientes e dependencias do
CloudIFF. A memoria PGH registra os responsaveis, as tarefas, a procedencia das
informacoes e os handoffs entre sessoes. Os dados operacionais continuam tendo
como origem o Portal CloudIFF e os sistemas realmente responsaveis por cada
recurso; nenhum status do Atlas deve ser tratado como health check funcional.

## Fontes e responsabilidades

| Fonte | Autoridade | Observacao |
|---|---|---|
| Portal CloudIFF | Projetos cadastrados, estados administrativos, ACLs declaradas e publicacoes | Validar integridade e data da leitura |
| Forgejo | Repositorios dos projetos/tenants | Nao confundir com o codigo-fonte da plataforma |
| GitHub CloudIFF | Codigo-fonte da plataforma e documentacao versionada | Revisao e testes antes de incorporar alteracoes |
| GitHub Dotfiles | Inventario/configuracoes documentais dos hosts | Nao e o repositório de codigo da plataforma |
| Komodo / Supabase | Containers, releases, bancos e estados operacionais | Validar permissao, titularidade e health reais |
| Atlas | Indice pesquisavel e grafo de relacoes | Preservar procedencia, data e grau de confianca |
| PGH | Diario persistente, contratos, tarefas e handoffs | Eventos canonicos na VPS de controle, nunca credenciais no Git |

O agente `documentacao/cloudiff/doc-01` coordena fichas, inventario e docs;
`desenvolvimento/cloudiff/dev-01` responde por mudancas funcionais no codigo;
`auditoria/cloudiff/aud-01` confere evidencias e criterios de aceite. Mudancas
que afetam mais de uma area devem explicitar dependencias e autorizacoes.

## Contrato minimo da ficha Atlas

Cada projeto do Portal deve ter um identificador Atlas estavel, independente
se o projeto esta publicado, em rascunho ou indisponivel:

- ID: `cloudiff.project.` + slug normalizado com hifens convertidos em `_`;
- tipo: `project`; categoria: `CloudIFF / Projeto`;
- nome e estado administrativo com a qualificacao `(Portal)`;
- `repo_url`: referencia ao Forgejo da unidade de projeto, quando verificada;
- `wiki`: proveniencia, momento da consulta, stack, ACLs agregadas, versoes e
  publicacoes, ressalvas de health, pendencias e fontes de evidencias;
- `source` e `visibility`: origem da coleta e acesso restrito;
- ambientes W1 (preview continuo), Hn (homologacao isolada), Pn (producao
  promovida) e status de cada integracao so quando verificados.

Campos ausentes devem dizer **nao verificado**. Jamais publicar segredos,
conteudo de arquivos `.env`, usuarios individuais, chaves, tokens, dados
pessoais ou enderecos internos sensiveis em documentacao publica.

## Operacao segura e idempotente

1. Confirmar identidade PGH, autorizacoes, tarefas abertas e locks.
2. Coletar o estado corrente das fontes oficiais em modo somente leitura.
3. Produzir baseline com data, escopo, contagens, checksums e limites de acesso.
4. Comparar registros existentes no Atlas por identificador, sem sobrescrever
   fichas sem origem comprovada e sem excluir projetos desconhecidos.
5. Antes de gravar no Atlas, efetuar backup transacional do banco, verificar
   integridade, registrar diff e prever reversao.
6. Realizar apenas upserts declarativos autorizados; validar o retorno da API,
   contagem total, relacoes do grafo, idempotencia e protecao de acesso.
7. Documentar divergencias por gravidade, fonte, horario e responsavel no PGH.
8. Para atualizar GitHub, reservar o caminho, criar branch isolada, executar
   validacoes e revisao, registrar SHA e integrar sem sobrescrever `main`.
9. Atualizar o handoff com evidencias e pendencias. Nao declarar sucesso de
   runtime com base apenas em status administrativos.

## Gatilhos de revisao

Reconciliar Atlas, documentacao e memoria quando surgir ou for removido um
projeto, repositorio, servico, ambiente, banco, dependencia, permissao ou
publicacao; tambem apos incidentes e releases. Reconciliacao programada so
deve ser ligada apos validacao de permissão, limites, retries, locks e logs.

## Baseline inicial — 14/11/2026

A leitura do Portal identificou oito projetos. O Atlas recebeu oito fichas
aditivas e foi validado quanto a ausencia de duplicacoes e a integridade do
banco; o relatorio detalhado e o backup ficam em armazenamento operacional
protegido, nao neste repositório publico. A API e o Portal exigem controles
de acesso correspondentes ao ambiente.

Este documento descreve o procedimento; nao comprova que os oito projetos
estejam operacionalmente saudaveis nem que cada pipeline W1/Hn/Pn esteja
homologado. Essas verificacoes pertencem ao ciclo de auditoria.
