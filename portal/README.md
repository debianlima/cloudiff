# Portal v2 — fundação incremental

Esta árvore implementa as Fases 0 e 1 do plano de migração.

- `legacy/` é o snapshot imutável do Portal no início da migração;
- `registry.py` inicia sem rotas, portanto todo tráfego permanece no legado;
- `design/` é a única fonte de tokens e componentes visuais da v2;
- `modules/` recebe um módulo por vez, começando por `health`;
- `docs/portal-v2/prototipo.html` é a referência visual executável.

Não adicione novas camadas ao CSS legado. Mudanças visuais novas pertencem a
`design/`, e toda rota nova deve declarar permissão antes do registro.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`config/`](config/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`core/`](core/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`design/`](design/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`legacy/`](legacy/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`modules/`](modules/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`tests/`](tests/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`ui/`](ui/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`__init__.py`](__init__.py) | `.py` | CloudIFF Portal v2 foundation; legacy remains the production fallback. |
| [`app.py`](app.py) | `.py` | Coexistence entry point for Portal v2 |
| [`FROZEN_SURFACES.md`](FROZEN_SURFACES.md) | `.md` | Documento técnico ou operacional. |
| [`registry.py`](registry.py) | `.py` | Route registry for the incremental Portal v2 migration |
| [`wiring.py`](wiring.py) | `.py` | Install every migrated module into the registry |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
