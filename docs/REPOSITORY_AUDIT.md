# Auditoria de integridade do repositório

O repositório foi comparado com os três nós ativos da plataforma.

## Cobertura confirmada

### Control plane

- 42 arquivos dos releases atuais;
- 68 scripts ativos em `/usr/local/sbin`;
- 114 units/timers/paths ativos;
- 25 módulos compartilhados em `/srv/cloudif/lib`;
- 30 utilitários em `/srv/cloudif/bin`;
- testes e Portal de staging.

### Runtime

- 9 arquivos dos releases atuais;
- 11 scripts ativos;
- 19 units/timers ativos;
- stacks Komodo versionáveis;
- fixture completa do pipeline Node 24.

### Proxy

- 4 arquivos dos releases atuais;
- 10 scripts ativos;
- 21 units/timers ativos;
- configuração customizada atual `http.conf`.

### Configuração

- 38 modelos `*.env.example`;
- políticas JSON versionáveis;
- chaves públicas de verificação;
- nenhum valor secreto real.

## Validações automatizadas

O script `scripts/validate.sh` verifica:

- estrutura obrigatória;
- sintaxe Python;
- imports internos `cloudif_*`;
- sintaxe shell;
- JSON e YAML/Compose;
- referências de executáveis nas units systemd;
- arquivos de runtime proibidos;
- padrões de segredo, JWT, token e chave privada.

O mesmo script é executado pelo workflow `.github/workflows/validate.yml` em pushes e pull requests.

## Exclusões intencionais

Não são versionados:

- valores reais de `.env`;
- tokens, senhas e credenciais;
- chaves privadas e certificados;
- bancos, logs e volumes;
- backups e releases históricos;
- cache e relatórios gerados pelo Trivy;
- snapshots de publicação e dados dos tenants.

Essas exclusões não removem código-fonte necessário para editar monitoramento, agentes, Portal, publicação, proxy ou templates de tenants.

## Promoção para produção

O GitHub contém a fonte editável e validável. A atualização dos hosts deve continuar passando pelo processo de release imutável, smoke tests e rollback descrito em `docs/MAINTENANCE.md`. O repositório não faz cópia automática direta para produção.

## Portal de staging

A auditoria online identificou que o serviço `cloudif-admin-portal-staging` utiliza uma biblioteca própria em `/srv/cloudif/staging/lib`. Os módulos ativos dessa biblioteca também são versionados em:

```text
components/control-plane/srv/cloudif/staging/lib/
```

Cópias de backup e arquivos quebrados continuam excluídos.
