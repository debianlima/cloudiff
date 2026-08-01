# Portal v2 — fundação incremental

Esta árvore implementa as Fases 0 e 1 do plano de migração.

- `legacy/` é o snapshot imutável do Portal no início da migração;
- `registry.py` inicia sem rotas, portanto todo tráfego permanece no legado;
- `design/` é a única fonte de tokens e componentes visuais da v2;
- `modules/` recebe um módulo por vez, começando por `health`;
- `docs/portal-v2/prototipo.html` é a referência visual executável.

Não adicione novas camadas ao CSS legado. Mudanças visuais novas pertencem a
`design/`, e toda rota nova deve declarar permissão antes do registro.
