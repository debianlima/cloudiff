# Contrato projeto ↔ competência do CloudIFF

O CloudIFF é uma **aplicação** que também expõe competências. As competências são uma forma adicional de acessar conhecimento e operações do projeto; elas não substituem o software de origem.

## Invariantes

- `project_kind=application`.
- `capability_mode=additive`.
- Portal, API, CLI, rotas, contratos e fluxo operacional nativos permanecem utilizáveis independentemente do runtime de competências.
- A competência não reimplementa algoritmos que já pertencem ao núcleo CloudIFF; ela delega ao núcleo autoritativo.
- Autenticação, autorização, isolamento, validações e regras de negócio do projeto continuam obrigatórias quando a operação é chamada por uma competência.
- Registrar, atualizar, desabilitar ou remover uma competência não pode impedir o uso normal do CloudIFF.
- Transformar uma aplicação em projeto exclusivamente de competência exige migração explícita; descoberta ou registro automático nunca fazem essa conversão.

## Exceção

Um projeto criado exclusivamente para ser uma competência pode declarar `project_kind=capability` e `capability_mode=native_only`. Nesse caso não é obrigatório inventar Portal, API ou CLI independentes.

## Autoridade

O contrato executável canônico está em `config/project-capability-contract.json` e é validado contra `contratos/project-capability-preservation.schema.json` por `tests/test_project_capability_preservation.py`.

Para reconciliação nativa, a autoridade algorítmica permanece em `include/cloudiff/reconciliation.hpp` e `src/common/reconciliation.cpp`; consumidores e competências devem chamar esse núcleo em vez de manter uma cópia divergente.
