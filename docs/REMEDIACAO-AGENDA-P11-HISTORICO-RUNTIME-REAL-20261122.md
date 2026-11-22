# Agenda Única P1020 — P11: estado real de Produções históricas

Data: 22/11/2026.

## Sintoma

Após P11 assumir Produção, P10 aparecia como `Offline` no modal, mas o usuário ainda conseguia clicar `Abrir` na tabela principal. O endereço antigo respondia rapidamente, dando impressão de container ainda ligado.

## Prova do estado real

- P11: `dep_77c8800218b8ddf20d17bc7a`, `production/running`; api/db/web `Up/healthy`.
- P10: `dep_00b101221eb813f671146b98`, `production/inactive`; api/db/web `Exited`.
- O Publisher não possui estágio `1020-p10-publication` ativo.
- `https://1020-p10-publication.cloudiff.duckdns.org/` responde 302 para `/cloudiff/portal/`; isso é fallback/roteamento, não conteúdo do runtime P10.

## Correção de semântica

`online` e `healthy` são estados independentes:

- `online=true`: container/runtime está executando e pode consumir memória;
- `healthy=true`: runtime online passou o healthcheck;
- `online=true, healthy=false`: mostrar **Online · atenção** e manter botão **Desligar**;
- `online=false`: mostrar **Offline** e botão **Subir**;
- `deleted`: mostrar **Containers excluídos**.

Nunca inferir Offline apenas porque a versão não é a Produção ativa, nem porque health falhou.

## Tabela principal

`Alternar entre Publicações` não exibe mais `Abrir` para uma P histórica antes de conhecer seu runtime real. A linha começa como `Consultando runtime…`; o `release-flow` já carregado pela página atualiza a linha:

- Online → `Abrir`;
- Offline → `Offline · suba para abrir`;
- estado indisponível → orientação para verificar no Ambiente de publicação;
- containers excluídos → sem link de abertura.

Isso reutiliza a mesma fonte de verdade usada pelo modal e não adiciona leitura de filesystem/Docker ao render inicial.

## Modal de Produção

O botão `Desligar` é exibido sempre que `runtimeState.online=true`, mesmo que `healthy=false`. O botão `Subir` aparece somente quando `online=false`.

Asset: `publication-release.js?v=20261122-runtime-state-v12`.
