# Estado — 2026-09-04 — contrato v48

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; alterações de navegação e aprovação desta sequência foram emendas explícitas de homologação.
- `teste-sofa` continua projeto descartável de QA do owner `iff1742962`, tenant `iff1742962-testesofa`, publicação estável P1/1010, Preview W3 e candidato H2 homologado.
- P2 continua vinculada ao candidato H2 e só pode ser ativada depois de **duas aprovações humanas distintas de admin/professor**, nenhuma delas pertencente ao mesmo usuário que solicitou a ativação.
- Identidades humanas namespaced como `portal:<username>` são a mesma pessoa que `<username>` para separação de funções; o namespace continua preservado nos registros de auditoria.
- A UI de Aprovações e a seção correspondente em Conectores exibem ações conforme o ator e o estágio (`pending`/`pending_second`), não apenas conforme o papel global.
- A skill de projeto vigente passa a `cloudiff@0.1.10`.

## Decisões superadas
- Comparar `requested_by` e `approved_by` como strings cruas — superado após `portal:iff1742962` ter sido tratado como diferente de `iff1742962` na primeira decisão P2.
- Interpretar a primeira aprovação registrada em `apr_4f9b40c9a80a4611bdcf` como válida — superado: ela explorou involuntariamente a divergência de namespace do próprio solicitante e expirou sem segunda aprovação.
- Oferecer `Aprovar/Aceitar` novamente ao primeiro aprovador em `pending_second` e devolver erro genérico após o clique — superado por renderização consciente do ator e mensagens de conflito específicas.

## Decisões humanas pendentes
- H001 P2 do `teste-sofa`: autorização vigente `apr_dd84dba1cc5f49219d67` está `pending`, sem primeiro/segundo aprovador. Precisa de dois usuários humanos distintos com perfil admin/professor; o solicitante `iff1742962` não pode ser um deles.

## Decisões fechadas nesta emenda
- O Approval Service normaliza o prefixo humano `portal:` antes das comparações de segregação de funções.
- O mesmo normalizador protege também a distinção entre primeiro e segundo aprovador.
- O Portal não oferece decisão ao solicitante de ativação crítica, nem novamente ao primeiro aprovador durante `pending_second`.
- O estado `pending_second` oferece somente a segunda aprovação suportada pelo contrato atual; não mostra uma rejeição que o backend recusaria.
- Formulário obsoleto/double submit retorna “Decisão não registrada” com motivo específico em vez de “Acesso negado” genérico para conflitos conhecidos.
- `versao_contrato` avançou para 48 e a entrada regressiva 1516 fixa a consistência ator/UI.

## Pendências técnicas não humanas
- Nenhuma pendência técnica conhecida permanece no gate de identidade/UI após os testes e deploys da U13.
- Após H001: executar P2, validar artefato/HTTPS/terminal/stable URL e então exercitar rollback real para P1.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U13; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.10` — skill raiz, atualizada com L020/L021 após homologação.
- `desenvolvedor-de-software@15` — método PGH vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.5` — política vigente.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `seguranca/aprovacao`: separação requester/approver podia ser burlada pela diferença textual `portal:user` versus `user`.
- `interface/aprovacao`: primeiro aprovador recebia novamente ação impossível e via erro genérico ao tentar cumprir a segunda aprovação.

## Divergências da última reconciliação
### Corrigidas
- Approval API: comparações de identidade humana usam equivalência de `portal:<user>` e `<user>`.
- Portal Aprovações e Conectores: requester e primeiro aprovador recebem mensagem explícita sem botões inválidos.
- Handler de decisão: conflitos conhecidos de dupla aprovação exibem motivo específico.
- Deploy Portal: `portal-approval-actor-u13-5f8c7f2-20260904` ativo.
- Deploy Approval Service: `approval-identity-u13-47f1996-20260904` ativo.
- Teste vivo sintético de identidade passou e sua pendência foi cancelada no final.
- P2 foi renovada após o fix: `apr_dd84dba1cc5f49219d67`, `pending`, `publicationNumber=2`, sem aprovadores.
- Reteste real da UI como solicitante: aprovação visível em Aprovações e no card Teste Sofá em Conectores, mensagem “Você solicitou esta ativação”, nenhum botão de decisão; API independente confirma zero aprovadores.

### Pendentes de autorização
- H001: duas decisões humanas distintas admin/professor, ambas diferentes do solicitante `iff1742962`.

## Entradas aceitas nesta unidade
- 1516 — regressão de consistência ator/UI para dupla aprovação.
- 391 — Conectores: ações humanas coerentes com solicitante e primeiro aprovador.
- 392 — painel dedicado de Aprovações: ações coerentes com o ator.
- 389 — handler Portal: conflitos de decisão com mensagens específicas e identidade passada aos renderers.
- Approval Service vigente — normalização de identidade humana para segregação de funções.
- `skills/cloudiff/SKILL.md` — L020/L021 e versão 0.1.10.
- `competencias.yaml` — versão da skill 0.1.10.

## Portões da unidade
- `APPROVAL_UI_TESTS=PASS`: 30/30.
- `APPROVAL_IDENTITY_TESTS=PASS`: 31/31.
- `LIVE_IDENTITY_NAMESPACE_GATE=PASS`: requester namespaced não aprova a própria ativação e primeiro aprovador não pode reaparecer como segundo via namespace.
- `LIVE_REQUESTER_UI=PASS`: P2 real renovada aparece sem botões para o solicitante em ambas as superfícies.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `DELTA_INVENTORY=PASS`, `LEARNING_PRESERVED=PASS`, `RECONCILIATION_CLOSURE=PASS`, `DEPENDENCY_REFERENCES=PASS` após fechamento.

## Próxima unidade
- Observar a primeira aprovação humana da nova P2 por um admin/professor diferente de `iff1742962`; confirmar `pending_second`; depois observar a segunda aprovação por outro usuário distinto e executar P2 + smoke + rollback.
