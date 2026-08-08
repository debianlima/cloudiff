# Delivery

Arquitetura modular, interface, configuração e testes do Portal.


## Entrega vigente

A entrega do projeto segue **W → H → P**:

- W é o Preview vivo e recebe o terminal padrão do projeto;
- H é o candidato imutável para homologação;
- P é a release de Produção criada do mesmo digest de H;
- rollback reativa uma P anterior saudável;
- `dN` permanece somente como identificação técnica/legada durante a migração.

Veja [`docs/FLUXO-WHP-PUBLICACAO.md`](../../../docs/FLUXO-WHP-PUBLICACAO.md).

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/modules/delivery`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`__init__.py`](__init__.py) | `.py` | delivery module: Entrega: terminal de projeto e histórico de promoções |
| [`routes.py`](routes.py) | `.py` | delivery module — route table |
| [`service.py`](service.py) | `.py` | delivery — dados de entrega |
| [`views.py`](views.py) | `.py` | delivery — HTML via portal.ui |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
