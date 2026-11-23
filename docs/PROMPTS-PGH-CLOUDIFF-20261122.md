# CloudIFF — catálogo de prompts PGH e autoridade operacional

Data de consolidação: 22/11/2026.

Este documento registra **quais prompts/instruções foram fornecidos pelo operador**, qual é o papel de cada um, sua ordem de autoridade e como devem ser carregados por agentes que retomem CloudIFF.

Ele é uma **projeção documental**. Não substitui a fonte original do prompt, não transforma proposta em norma e não deve conter credenciais.

## 1. Fontes enviadas pelo operador

### 1.1 `Meu-Terminal-Oracle-Instrucoes-PGH-1.2.0.md`

Papel: instrução operacional PGH 1.2.0 para agentes que executam administração de sistemas/engenharia de software.

Pontos obrigatórios da fonte:

- provar estado real, contrato e gates independentes em vez de assumir o comportamento típico;
- executar diretamente operações reversíveis de verificação, diagnóstico, instalação, configuração, reconciliação e reinício;
- parar diante de destruição sem rollback, lacuna de contrato que determina resultado, bootstrap ambíguo ou reconciliação que exige apagar/mover/renomear árvore;
- carregar fontes/skills específicas conforme o gatilho do trabalho;
- projeto é prescritivo e ambiente é descritivo;
- uma fonte de verdade por área; cópia é backup/projeção, não nova autoridade;
- não inventar estado de máquina a partir de inventário desatualizado.

O cabeçalho da projeção enviada informa:

- `origem_core: dotfiles:base/agentes/meu-terminal-oracle-core.md`;
- `sha256_core: 4be4beb679813db99c30e9fdae4c9bbe1c25a447318ae21ace8c9806f50b788f`;
- `origem_ontologia: competencias-catalogo:metodo/governanca-ontologica-de-skills/SKILL.md`;
- `sha256_ontologia: ee32db11ce71e3d2c831559e9af6d6de807702df8ac7c3d4941530732721c6ab`.

Esses digests pertencem às origens declaradas dentro da projeção; **não são apresentados aqui como SHA do arquivo completo enviado**.

### 1.2 `Prompt-Mantenedor-PGH-1.2.0.md`

Papel: manter a camada não estatística do projeto — estrutura, documentação, memória, fronteiras, nomes, ordem, critérios e rastreabilidade.

Pontos obrigatórios da fonte:

- carregar a competência de método antes do bootstrap/retomada;
- Fase 0 antes de escrita estrutural e Fase R em retomada;
- separar decisão, hipótese/discussão e estado observado;
- buscar/reconciliar antes de criar novo arquivo/função;
- reserva antes de alterar caminhos compartilhados;
- uma fonte de verdade por área; cópia não vira espelho canônico;
- reconciliação incremental precede normalização;
- exigir `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS` antes de normalizar prompt, instrução, catálogo, skill ou workflow;
- release exige fecho reconciliado e referências de dependência válidas;
- telemetria abre e fecha toda unidade PGH 1.2.0;
- token não observado é `indisponivel`, nunca estimado como se fosse medido;
- substituição de prompt/instrução não ocorre silenciosamente: revisão e emenda precisam ser registradas.

Para CloudIFF, este prompt governa a atualização de normas, runbooks, Atlas, memórias e catálogos, mas **não substitui a prova do runtime real** exigida pelo `Meu-Terminal`.

### 1.3 `PGH-DWP-Agent-Instructions.txt`

Metadados declarados pela fonte enviada:

- `Status: PROPOSED`;
- `Versão: 0.1.0`;
- `Alvo: PGH 3.0 candidate`;
- efeito de autoridade: **nenhum até aceite formal**.

Portanto, no estado atual do projeto CloudIFF:

`DWP_NOT_ACTIVE`

A documentação deve preservar o DWP como especificação de revisão, sem tratá-lo como grant de execução.

Se/Quando houver aceite formal e DWP ativo, a própria fonte exige:

1. decisão/contrato humano válido;
2. PGA/PGH/PGD e contratos canônicos;
3. assignment/lease/fencing/locks válidos;
4. DWP ativo/revisão vigente;
5. WCB/contexto operacional;
6. memória/advisory/inferência.

Também é obrigatório lembrar que `ACKED` significa leitura/reconhecimento da revisão, e **não** significa lease, assignment, permissão de escrita ou gate aprovado.

## 2. Prompt operacional local WORK SSH / CloudIFF — projeção sanitizada

Além dos três arquivos acima, o ambiente de trabalho CloudIFF possui instruções locais fornecidas pelo operador. Esta projeção registra apenas o contrato operacional não sensível:

- operar a infraestrutura CloudIFF por VPS/helpers autorizados;
- seguir PGH 1.2.0 em todas as mutações;
- usar o nó Samba4 somente para algoritmos/simulações quando esse contrato for aplicável;
- alimentar o ambiente WebDev/readiness com testes/hardness para permitir acompanhamento;
- usar Atlas e memórias PGH como continuidade entre agentes;
- tratar Faro como preferência para **novos serviços autônomos** quando gates de capacidade/rede/backup/observabilidade permitirem;
- preservar o lifecycle global `Forgejo → Preview fixo Wn → clone integral Hn → promoção da mesma instância para Pn`;
- manter o SQLite do read-model como hot path de interface, nunca filesystem/Docker/Komodo no request normal.

### Segredos deliberadamente omitidos

Credenciais, tokens, senhas, chaves e valores de secret fornecidos pelo operador **não são reproduzidos** neste documento, Atlas, memória, telemetria ou Git.

Agente futuro deve resolver credenciais pelo mecanismo autorizado do ambiente (wrapper/secret store/arquivo privado já existente), nunca por documentação pública do projeto.

## 3. Ordem de carregamento para um agente CloudIFF

Ao iniciar ou retomar unidade:

1. resolver identidade real do agente/área/projeto/tarefa/lease;
2. ler `docs/PROMPTS-PGH-CLOUDIFF-20261122.md`;
3. carregar/reler `Meu-Terminal-Oracle-Instrucoes-PGH-1.2.0.md` vigente;
4. para manutenção estrutural/documental, carregar `Prompt-Mantenedor-PGH-1.2.0.md`;
5. carregar skill de projeto/método/competências requeridas e conferir versão/delta;
6. ler `estado.md`, Atlas e auditoria individual do projeto;
7. carregar normas CloudIFF específicas da unidade (W/H/P, read-model, banco, segurança etc.);
8. conferir DWP ativo somente se houver aceite/referência canônica; na ausência, registrar `DWP_NOT_ACTIVE`;
9. adquirir/revalidar lease e demais gates antes de escrita/mutação;
10. executar, provar estado real, atualizar documentação/Atlas/memórias e fechar telemetria.

## 4. Regra de precedência CloudIFF

Em conflito, usar esta ordem prática:

1. decisão humana atual válida;
2. contratos PGH/PGA/PGD e prompt canônico vigente;
3. estado real comprovado da máquina/runtime para fatos operacionais;
4. norma específica CloudIFF vigente e manifesto do projeto;
5. assignment/lease/gates válidos;
6. Atlas/read-model como índice/projeção;
7. memória/advisory/histórico.

Nenhum índice, prompt antigo ou memória pode transformar estado histórico em estado real.

## 5. Mudança de prompt

Toda mudança de prompt/instrução compartilhada deve:

1. inventariar fonte vigente, nova fonte e deltas;
2. classificar o que é norma, proposta, histórico ou projeção;
3. preservar aprendizado homologado ainda válido;
4. registrar `DELTA_INVENTORY` e `LEARNING_PRESERVED` antes de normalizar;
5. atualizar este catálogo, `PGH-AGENTES-CLOUDIFF.md`, Atlas e memórias;
6. registrar commit/evidência e data;
7. nunca elevar `PROPOSED` para ativo sem decisão humana formal.

## 6. Relação com o Atlas

O Atlas deve mostrar para CloudIFF:

- prompt/instrução vigente;
- versão/status conhecido;
- efeito de autoridade;
- referência a este catálogo;
- norma W/H/P e norma de read-model;
- data da última reconciliação;
- aviso de que secrets não fazem parte da projeção.

O Atlas é índice humano e não substitui as fontes originais.

## 7. Referências CloudIFF

- `docs/PGH-AGENTES-CLOUDIFF.md`;
- `docs/ATLAS-CLOUDIFF-PGH-OPERACAO.md`;
- `docs/ATLAS-CLOUDIFF-CONCILIACAO.md`;
- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`;
- `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`;
- `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`;
- `estado.md`.
