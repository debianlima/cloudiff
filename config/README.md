# Configuração

Os arquivos `*.env.example` listam somente as variáveis esperadas pelos serviços. Valores reais não são versionados.

- `<required-secret>`: deve vir de cofre de segredos ou arquivo protegido no host;
- `<configure>`: parâmetro de ambiente a ser definido para o ambiente de destino.

Arquivos JSON nesta pasta são políticas versionáveis. Chaves `*.pub` são públicas e usadas apenas para verificação de assinatura.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `config`

Configurações por nó e contratos declarativos.

| Item | Tipo | Finalidade |
|---|---|---|
| [`control-plane/`](control-plane/) | Diretório | Configurações por nó e contratos declarativos. |
| [`proxy/`](proxy/) | Diretório | Configurações por nó e contratos declarativos. |
| [`runtime/`](runtime/) | Diretório | Configurações por nó e contratos declarativos. |
| [`portal-quality-baseline.json`](portal-quality-baseline.json) | `.json` | Configuração, inventário, evidência ou estado serializado em JSON. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
