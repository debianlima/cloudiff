# Desenvolvimento e evolução

## Antes de alterar

1. Identifique a superfície congelada e seus testes de contrato.
2. Localize serviço de domínio e adaptador, evitando lógica duplicada na UI.
3. Defina pré-condições, pós-condições e idempotência.
4. Defina lock do recurso quando houver concorrência.
5. Defina auditoria e aprovação humana quando houver efeito.
6. Adicione teste de contrato e teste de falha transitória.

## Validação mínima

```bash
python3 -m py_compile <arquivos-python>
bash -n <scripts-shell>
node --check portal/design/app.js
python3 -m unittest -q portal.tests.test_frozen_surfaces_contract
python3 -m unittest -q portal.tests.test_navigation_information_architecture
git diff --check
```

## Atualizar a documentação de diretórios

```bash
python3 scripts/generate-directory-readmes.py
```

O gerador cria ou atualiza a seção automática de cada README e o inventário global. Conteúdo manual fora dos marcadores é preservado.
