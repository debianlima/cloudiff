# Paperclip W1 — metadados Docker com identidade de owner (PGH T-011)

A execução de portal/tools/owner_paperclip_w1_runtime_readonly.py
se destina exclusivamente à identidade administrativa previamente
delegada e auditada no host Forja. O script não eleva privilégios,
não altera Docker/Komodo, não importa senhas, não faz deploy e não lê
variáveis ou arquivos de segredo.

O executável exige EUID 0 no host correto e valida exclusivamente o
container cloudif-p1025-preview-web. Ele consulta apenas nome da
imagem, estado do container, mount de /var/www/html e metadados de
identidade das labels org.cloudiff.*, incluindo project=paperclip,
public-number=1025, stage=preview, stage-number=1, marcador Preview
e presença sintaticamente válida de um SHA Git imutável.

A presença do SHA não prova que uma imagem foi construída a partir
dele. O check do filesystem usa apenas test -f para caminhos fixos
(não lê conteúdo). Os valores dos labels de commit e os ambientes
Docker não são registrados; a saída JSON informa somente verificações
booleanas, caminhos sanitizados e estado reduzido.

Exemplo somente para owner autorizado, executado em Forja:

    python3 portal/tools/owner_paperclip_w1_runtime_readonly.py

Em qualquer outro host, conta não privilegiada ou sem acesso Docker,
o retorno é BLOCKED_*. Uma saída METADATA_ONLY_NOT_A_RUNTIME_FIX
não é autorização de produção, não comprova backup, rollback ou
segredos isolados e não implica que a interface Paperclip funcione.

A necessidade restante é validar G0–G5 com evidência institucional:
owner/ACL, lock, backup/restauração, OpenBao secret_ref, build nativo
Node24 por commit Forgejo, atualização contínua e E2E autenticado
no W1 sem impacto em homologação/produção. Não instalar permissões
amplas na conta cti nem contornar o sudo restrito existente.

Teste offline:

    python3 -m unittest discover -s portal/tests -p test_owner_paperclip_w1_runtime_readonly.py -v
