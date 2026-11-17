# Conciliação CloudIFF ↔ Atlas ↔ GitHub ↔ PGH

Observação operacional: 14/11/2026. Agente: documentacao/cloudiff/doc-01.
A execução deste runbook NÃO autoriza alterações no runtime, publicação de código
funcional, modificação de ACL, exclusão de itens ou reconfiguração de conectores.

## Baseline de observações
- 13:33 UTC: Portal CloudIFF possuía oito tenants conforme snapshot somente leitura.
- 13:41 UTC: Atlas possuía 205 itens após inclusão de oito fichas CloudIFF; importação idempotente.
- 13:56 UTC: consulta real à API local Atlas retornou 213 itens, sendo 23 project,
  43 service, 16 tool e 131 repo.
- Entre as 213 fichas, oito IDs cloudiff.project.* e oito IDs cloudiff.repo.*
  referenciam os mesmos oito slugs do Portal. As oito fichas repo adicionais
  têm categoria CloudIFF / Forgejo, estado 'referenciado (Portal)'.
- Esse aumento NÃO comprova que links, HEAD Git, health ou ACL efetivas funcionem.
  Contagens são fotografias temporais, não invariantes rígidas de manutenção.

## Modelo de integridade
1. A fonte atual de tenants é o Portal, não uma lista de oito slugs hardcoded.
2. Para cada tenant descoberto, exigir exatamente uma ficha de projeto com ID
   cloudiff.project.<slug_com_underscore> e, quando existir repositório Forgejo
   confirmado, exatamente uma ficha repo cloudiff.repo.<slug_com_underscore>.
3. As fichas de projetos e repositórios devem preservar URL, dono e fonte,
   sem trocar URLs de Forgejo pelas da plataforma GitHub.
4. A aplicação CloudIFF usa github.com/debianlima/cloudiff; o Dotfiles usa
   github.com/debianlima/dotfiles; Atlas possui Git próprio separado.
5. Mudanças em W1/Hn/Pn, runtime, banco, ACL, links de proxy, SHA e containers
   devem estar associadas a evidência de origem e data.
6. O status administrativo published/draft não equivale à saúde funcional.
7. Não assumir sincronização bidirecional nem versionar segredos.

## Procedimento somente leitura para detecção de diferenças
- Atualizar snapshot Portal de modo ro com fonte e timestamp.
- Exportar somente metadados autorizados da API Atlas; proteger exportações
  que contenham endpoints internos e política de acesso.
- Executar scripts/check_atlas_cloudiff.py com dois arquivos JSON.
- Analisar ausências, duplicidades, divergência de nome ou referência Forgejo
  e novos slugs; novos registros devem gerar decisão em vez de inserção implícita.
- Consultar de forma independente git ls-remote para branch e SHA e comparar
  com revisão de produção COMPROVADA; sem expor credenciais.
- Ao encontrar divergência, abrir evento PGH com data, fonte, evidência,
  severidade, responsável e correção proposta.

Exemplo, no ambiente autorizado que disponha das duas exportações:

    python3 scripts/check_atlas_cloudiff.py \
      --portal-json /caminho/BASELINE-ATLAS-CLOUDIFF.json \
      --atlas-json /caminho/atlas-items-export.json

O comando apenas lê os arquivos e reporta diferenças. Não acessa a rede,
não imprime campos de segredo e não modifica os arquivos.

## Gatilhos e tratamento
| Evento | Ação documental | Evidência mínima | Aprovador |
| --- | --- | --- | --- |
| Novo tenant | Adicionar ficha, relações e runbook | Portal + Forgejo + owner | doc-01 |
| Repo ou branch muda | Atualizar origem e SHA verificadas | git ls-remote e commit | dev-01 |
| Publicação W1/Hn/Pn | Atualizar versionamento e topologia | digest, health, rollback | dev-01 |
| ACL/colaborador muda | Atualizar mapeamento de papéis | acesso efetivo verificado | aud-01 |
| Incidente de produção | Criar registro, impacto e resolução | log sem segredo e cronologia | aud-01 |
| Alteração Atlas | Revisar campos, vínculos e código Git | diff, backup, teste idempotente | doc-01 |
| Divergência periódica | Abrir tarefa PGH e encaminhar correção | resumo estruturado e data | aud-01 |

A varredura diária e o resumo semanal são uma proposta, NÃO um agendamento
instalado. Um serviço automático só pode ser habilitado após autorização de
identidade de leitura, quotas, locks, logs, teste e rollback.

## Fluxo de mudança e aceite
- doc-01 prepara atualização do inventário e documentação em branch isolada.
- dev-01 revisa qualquer mudança em código ou integração funcional.
- aud-01 verifica proveniência, integridade, backup, segredos e divergências.
- Pull request ou mecanismo equivalente revisado antes do merge.
- Após merge, coletar SHA remota e conferir links e documentação resultante.
- Escrever nota e handoff no PGH; marcar tarefa done apenas com evidência.
- Em conflito de versões ou leases, interromper a mutação e preservar artefatos.

## Divergências pendentes em 14/11
- Confirmar SHA realmente implantado da plataforma CloudIFF.
- Reconciliar Atlas live server.py / ontology.py / ui.js com Git Atlas bare.
- Verificar ACL efetiva, acesso aos terminais Komodo e W1/Hn/Pn por tenant.
- Investigar estados administrativos distintos da saúde em Paperclip,
  MSHA, Agenda Única, MVPlanner e SilviPro.

Referências: ATLAS-CLOUDIFF-PGH-OPERACAO.md,
INVENTARIO-CLOUDIFF-PARA-ATLAS-2026-11-14.md no LabIFF,
memória PGH documentacao/cloudiff/doc-01 e auditoria de 13/11/2026.
