# CloudIFF Project Configuration Controller

Serviço interno responsável por validar o `cloudiff.yaml`, calcular revisões e digests e registrar eventos de reconciliação.

A primeira versão opera em **modo observação**: nenhuma imagem, container, variável de runtime ou publicação é alterada pelo controlador. Alterações persistentes exigem plano, digest e confirmação explícita de aprovação.

## Endpoints

- `GET /health`
- `GET /v1/schema`
- `POST /v1/manifest/validate`
- `GET /v1/projects/<slug>/configuration`
- `POST /v1/projects/<slug>/configuration/plan`
- `POST /v1/projects/<slug>/configuration/apply`
- `POST /v1/projects/<slug>/events`

## Contrato declarativo v1

O manifesto aceita, de forma aditiva e compatível com projetos existentes:

```yaml
version: 1

environment:
  APP_NAME:
    value: demo
    required: true
    secret: false

  JWT_SECRET:
    required: true
    secret: true

services:
  web:
    runtime: static
    publish: dist
    environment:
      PUBLIC_API_URL:
        required: true
        exposeToClient: true

  api:
    runtime: node
    version: "24"
    start: [node, server.js]
    port: 3000
    environment:
      JWT_SECRET:
        required: true
        secret: true

toolchain:
  architecture: amd64
  systemPackages:
    - git
    - name: imagemagick
      version: "6.9"
  tools:
    - name: pnpm
      version: "10"
      installMethod: corepack
  provision:
    script: scripts/cloudiff-provision.sh
    timeoutSeconds: 600
    network: restricted
```

Valores secretos nunca são aceitos em `value` ou `default`. O manifesto armazena somente metadados; vínculos reais de segredos pertencem à API protegida da plataforma.

O formato legado com `environment.variables` e `environment.required` continua válido. A normalização efetiva preserva esses campos para compatibilidade e acrescenta `environment.definitions` com os metadados declarativos.

Campos antigos no nível raiz retornam erro acionável:

- `env` → `environment`;
- `systemPackages` → `toolchain.systemPackages`;
- `provision` → `toolchain.provision`.


## API de ambiente

Leitura:

- `GET /v1/projects/<slug>/environment`
- `GET /v1/projects/<slug>/environment/history`
- `GET /v1/projects/<slug>/environment/missing`
- `GET /v1/projects/<slug>/environment/plans/<digest>`

Planejamento e execução:

- `POST /v1/projects/<slug>/environment/validate`
- `POST /v1/projects/<slug>/environment/change/plan`
- `POST /v1/projects/<slug>/environment/change/apply`
- `POST /v1/projects/<slug>/environment/promote/plan`
- `POST /v1/projects/<slug>/environment/promote/apply`

A API persiste valores públicos, metadados e referências opacas de segredo. Valores secretos diretos são rejeitados. A aplicação registra revisão e histórico, mas não reinicia containers nesta fase; a resposta informa `requiredAction`, `affectedServices` e `reconciliationPending`.

A API Web do Portal usa as rotas equivalentes sob `/cloudiff/portal/api/projects/<slug>/environment`. Planejamento, aprovação e execução aplicam a mesma ACL e o mesmo vínculo de aprovação utilizado pelas ferramentas MCP.
