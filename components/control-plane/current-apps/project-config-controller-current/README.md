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
