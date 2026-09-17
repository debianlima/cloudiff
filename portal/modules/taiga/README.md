# Taiga — visão acadêmica por projeto

Superfície v2 independente para acompanhamento do Taiga no CloudIFF.

## Autoridades preservadas

- **Projetos/ACL CloudIFF** continuam sendo a autoridade de visibilidade e membership.
- Este módulo não cria projetos nem adiciona/remove usuários no Taiga.
- `portal.core.project_visibility.visible_projects()` é compartilhado com o módulo Projetos.

## Fontes

- Taiga público: saúde da API e, quando configurado, leitura server-side por projeto.
- Faro: telemetria do `node_metrics_cache`, filtrada para containers Taiga.
- Forgejo/Forja Agent: atividade sanitizada (`push`, `pull_request`, `release`, deploy), sem e-mail/payload bruto.
- Academic Audit: timeline acadêmica com escopo por projeto e por ator.

## Privacidade

- Admin/professor podem consolidar membros dos projetos que conseguem visualizar.
- Usuários comuns recebem apenas atividade associada ao próprio username institucional.
- Tokens, cookies, senhas e referências de credencial não fazem parte do read-model.
- Tempo de atividade, quando houver, é estimativa baseada em eventos autenticados; não significa horas trabalhadas.

## Credencial privada do Taiga

`CLOUDIF_TAIGA_API_TOKEN` é opcional e deve ser materializada server-side por provedor de segredos. Sem ela, a tela degrada de forma segura e continua exibindo projetos, saúde, Faro, Forgejo e Academic Audit.
