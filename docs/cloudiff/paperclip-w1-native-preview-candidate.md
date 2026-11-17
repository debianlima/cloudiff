# Paperclip W1 1025 — candidato de runtime nativo isolado (T-011 / T-013)

**Estado:** design e gerador Compose testados offline; **não implantado nem aceito para produção**.

## Problema confirmado em 17/11/2026

O Preview W1 1025 publica checkout de um monorepositório `pnpm` como raiz de um Apache genérico. `/` retorna HTTP 403, `/ui/` entrega HTML bruto com `src=/src/main.tsx` e essa URL retorna 404. `/.cloudif-health` retorna 200 por um PHP genérico — não comprova site funcional. O serviço Paperclip privado na Forja, porta 3100, é independente, e **não deve ser exposto como atalho**.

## Contrato do candidato

O script `portal/tools/cloudif_paperclip_w1_plan.py` gera somente JSON Compose e configuração de proxy, sem deploy ou leitura de credenciais. O argumento opcional --output-dir candidato-w1 cria dois arquivos locais sem sobrescrever conteudo existente: compose.json e proxy.conf. É uma peça de projeto para revisão/inclusão posterior no executor de publicação W1; **não substitui automaticamente** o runtime atual.

- App `cloudif-p1025-preview-app`: imagem nativa do Dockerfile Paperclip construída pelo executor autorizado de um commit Forgejo completo e autenticado, com ID imutável verificado; não usa o container Paperclip privado. A porta 3100 fica somente na rede interna sem mapeamentos `ports`.
- Web `cloudif-p1025-preview-web`: proxy nginx exclusivo para o app W1 isolado, porta 80 interna na rede já utilizada pelo gateway, sem porta no host.
- Os dados de `/paperclip` usam o volume nomeado exclusivo `cloudif-p1025-w1-paperclip-data`; nome/volumes existentes devem ser inventariados antes do deploy para impedir reaproveitamento acidental.
- Modo autenticado e exposição privada. Variáveis ou segredos reais devem ser obtidos via OpenBao `secret_ref`, com ACL e TTL; não estão no gerador.
- Imagens devem vir de compilação revisada e pinagem imutável; o gerador valida sintaxe, **não prova** proveniência do build, proprietário do digest, scanner de vulnerabilidades ou que uma imagem já esteja disponível localmente.
- Preview requer fluxo de atualização seguro Forgejo commit novo → build independente → testes → troca atômica reversível do container W1. O gerador **ainda não implementa** esse fluxo, lock, backup, Hn/Pn, nem automação de credenciais.
- O health do nginx exige sucesso HTTP tanto na raiz quanto em /api/health. Isso nao substitui teste funcional de JavaScript, login, tela e banco. O nginx usa o serviço `app` no namespace privado. É proibido apontar o proxy para a porta privada `10.62.91.2:3100` ou usar o mesmo banco/volume da produção.

## Passos obrigatórios antes de usar

1. Confirmar owner/identidade e delegação Docker no host correto, inventário de stacks, labels, redes e aliases e lock por projeto.
2. Backup e ensaio de restauração isolado do Preview com rollback, sem interromper Pn/Hn. Confirmar que o volume nomeado W1 não existe com dados de produção.
3. Confirmar com dev-02 o commit Forgejo canônico e com dev-01 o Dockerfile nativo e sua build reproduzível; verificar imagem real e seus metadados de origem, sem tokens em logs.
4. Injetar segredos apenas por `secret_ref` com permissões do projeto, negar acesso cruzado e testar TTL/revogação.
5. Validar sintaxe do Compose e `nginx -t` em ambiente descartável, disponibilidade da imagem pinada, rede externa, recursos e health da app real. Adaptar a configuração de proxy a HTTP/Upgrade conforme testes E2E.
6. Validar W1 independente com `GET /` retornando HTML da app, assets compilados 200, `/api/health` real, testes de login e acesso negado, TLS/SNI estrito, sincronização contínua e rollback; aud-01 e surface-01 revalidam.
7. Somente após G0–G5 e revisão independente integrar o plano ao executor e aplicar uma migração controlada do projeto 1025; não fazer promoção Hn/Pn neste PR.

## Testes

`python3 -m unittest discover -v -s portal/tests -p 'test_infra02_paperclip_w1_native_plan.py'`

O gerador exige argumentos `--source-commit` (40 hex), `--native-image-id` (ID `sha256` verificável) e `--nginx-image` (imagem nginx com digest). Não use valores sintéticos para deploy.

**PGH:** `infraestrutura/cloudiff/infra-02 T-011` é subtarefa de `desenvolvimento/cloudiff/dev-02 T-013`; diagnóstico registrado no LabIFF em `evidencias/INFRA02-T011-PAPERCLIP-W1-RUNTIME-CORRECAO-20261117.md`.
