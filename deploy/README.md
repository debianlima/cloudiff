# Deploy — coexistência v1/v2 (substituição incremental)

Artefatos que colocam a v2 no ar em produção sem editar o release do monólito:

- `cloudif_portal_v2_coexist.py` — camada de coexistência. Ativa com
  `CLOUDIF_PORTAL_V2=1` (escopo do processo do portal). Intercepta apenas as
  rotas verificadas idênticas à v1 (lista `READY`) e os assets do v2; todo o
  resto segue no legado. Fail-open: qualquer erro deixa o portal subir no legado.
- `v2_testserver.py` — servidor isolado (porta 18120) para inspeção da v2 sem
  tocar produção. Seletor de perfil por `?perfil=admin|professor|aluno`.

Ativação em produção (não edita o release, §10):
1. copiar o shim para o `sys.path` do portal (`/srv/cloudif/lib`);
2. `.pth` em dist-packages com `import cloudif_portal_v2_coexist`;
3. drop-in de systemd com `Environment=CLOUDIF_PORTAL_V2=1` só no unit do portal.

Reverter: remover o drop-in de env e reiniciar o portal.
