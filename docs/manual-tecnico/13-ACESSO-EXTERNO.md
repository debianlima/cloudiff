# Acesso externo, Git, PostgreSQL, Supabase, MCP e OAuth

Este capítulo descreve o que precisa ser publicado no gateway/firewall chamado **Maurício** para que usuários e ferramentas externas acessem Forgejo, Supabase, PostgreSQL e o MCP CloudIFF.

## Estado validado em 5 de agosto de 2026

| Verificação externa | Resultado |
|---|---|
| `cloudiff.duckdns.org:443` | aberto; HTTPS responde |
| Forgejo em `/git/` | aberto; interface responde |
| Git HTTPS privado sem credencial | `401 Unauthorized`; comportamento esperado |
| `cloudiff.duckdns.org:22` e `:2222` | timeout; Git SSH ainda não está publicado |
| tenant em `:443` | aberto; portal e serviços HTTP respondem |
| tenant em `/mcp` | `404` do aplicativo Next.js; não é a rota MCP da plataforma |
| `cloudiff.duckdns.org/cloudiff/mcp` por `POST` sem credencial | `401 Unauthorized`; endpoint publicado e protegido |
| metadados OAuth do MCP | `200 OK` |
| tenant em `:54400` | timeout; PostgreSQL ainda não está publicado externamente |

Na rede interna foram observados:

| Serviço | Alvo interno |
|---|---|
| Forgejo web | `10.62.91.2:3000` |
| Forgejo SSH | `10.62.91.2:2222` |
| proxy HTTPS | `10.62.91.3:443` |
| PostgreSQL/Supavisor do projeto | `10.62.92.7:54400` |

O endpoint interno `10.62.92.7:54400` respondeu ao protocolo PostgreSQL, mas não aceitou negociação TLS. Por isso, não deve ser exposto sem VPN, allowlist ou uma camada TLS própria.

## Encaminhamentos no Maurício

### Regras mínimas

| Entrada pública | Destino | Finalidade |
|---|---|---|
| `TCP 80` | `10.62.91.3:80` | desafio ACME e redirecionamento HTTP → HTTPS |
| `TCP 443` | `10.62.91.3:443` | Portal, Forgejo HTTPS, Supabase HTTP, MCP e OAuth |
| `TCP 2222` | `10.62.91.2:2222` | clone e push Git por SSH |
| `TCP 54400` | `10.62.92.7:54400` | PostgreSQL do projeto, somente sob proteção adicional |

Use `2222` externamente para não disputar a porta `22` do acesso administrativo do gateway. Libere as mesmas portas no firewall de entrada e confirme que o NAT preserva conexões TCP longas.

### PostgreSQL: publicação segura

Adote uma destas opções, nesta ordem:

1. VPN institucional ou WireGuard;
2. allowlist dos IPs de origem;
3. pooler PostgreSQL com TLS nativo e certificado válido;
4. abertura direta apenas durante teste controlado.

O proxy HTTP da porta `443` não substitui o encaminhamento TCP do PostgreSQL. Um proxy configurado somente para HTTP/HTTPS não encaminha o protocolo PostgreSQL.

## Forgejo HTTPS

O caminho público deve permanecer em `/git/`. Exemplo de configuração do Forgejo:

```ini
[server]
DOMAIN = cloudiff.duckdns.org
ROOT_URL = https://cloudiff.duckdns.org/git/
HTTP_PORT = 3000
PROTOCOL = http
SSH_DOMAIN = cloudiff.duckdns.org
SSH_PORT = 2222
START_SSH_SERVER = true
SSH_LISTEN_HOST = 0.0.0.0
SSH_LISTEN_PORT = 2222
```

No proxy reverso, encaminhe `/git/` para `http://10.62.91.2:3000`, preserve o cabeçalho `Host` e envie `X-Forwarded-Proto: https`. O `ROOT_URL` com o subcaminho é necessário para o Forgejo anunciar URLs corretas de navegação e clone.

### Clone HTTPS

```bash
git clone https://cloudiff.duckdns.org/git/iff1742962/cloudif-laboratorio-de-hardware.git
```

O repositório é privado. O Git solicitará usuário e token pessoal do Forgejo. Uma resposta `401` sem credencial confirma que a requisição chegou ao Forgejo; não significa falha do proxy.

### Clone SSH

Depois de publicar `2222/tcp` e cadastrar a chave pública do usuário no Forgejo:

```bash
git clone ssh://git@cloudiff.duckdns.org:2222/iff1742962/cloudif-laboratorio-de-hardware.git
```

Testes:

```bash
ssh -T -p 2222 git@cloudiff.duckdns.org
git ls-remote ssh://git@cloudiff.duckdns.org:2222/iff1742962/cloudif-laboratorio-de-hardware.git
```

## Supabase e PostgreSQL

### API e Studio

A URL HTTPS do projeto é:

```text
https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org
```

Ela continua passando pelo proxy em `443`. Não é necessário publicar diretamente as portas internas do Kong ou do Studio.

### Conexão do projeto

A CloudIFF usa o slug do tenant como `POOLER_TENANT_ID`. Para o Laboratório de Hardware:

```text
host=iff1742962-laboratoriodehardware.cloudiff.duckdns.org
port=54400
database=postgres
user=postgres.iff1742962-laboratoriodehardware
```

String sem senha:

```text
postgresql://postgres.iff1742962-laboratoriodehardware:[YOUR-PASSWORD]@iff1742962-laboratoriodehardware.cloudiff.duckdns.org:54400/postgres
```

Não grave a senha no histórico do shell, em issue, README, prompt ou commit. Prefira um gerenciador de segredos, `PGPASSWORD` injetado no processo ou um `.pgpass` protegido.

### Testes

```bash
nc -vz iff1742962-laboratoriodehardware.cloudiff.duckdns.org 54400
psql "postgresql://postgres.iff1742962-laboratoriodehardware:[YOUR-PASSWORD]@iff1742962-laboratoriodehardware.cloudiff.duckdns.org:54400/postgres"
```

## MCP remoto

O endpoint público da plataforma é compartilhado; a identidade e a ACL determinam quais projetos e ferramentas cada usuário ou agente pode acessar:

```text
https://cloudiff.duckdns.org/cloudiff/mcp
```

Não use este endereço para MCP:

```text
https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org/mcp
```

Esse caminho pertence ao site do tenant e atualmente responde `404` no Next.js.

O MCP usa `POST`. Um `GET /cloudiff/mcp` pode responder `404`, enquanto um `POST` sem credencial responde `401`, confirmando que a rota está publicada e protegida.

Rotas públicas relacionadas:

```text
/cloudiff/mcp
/cloudiff/mcp/oauth/authorize
/cloudiff/mcp/oauth/token
/cloudiff/mcp/oauth/revoke
/cloudiff/mcp/.well-known/oauth-authorization-server
/.well-known/oauth-authorization-server
/.well-known/oauth-protected-resource/cloudiff/mcp
```

O proxy deve preservar `Authorization`, `Content-Type`, `Accept` e `X-CloudIF-Client`. Não aplique uma segunda autenticação de forward-auth sobre as rotas OAuth/MCP; a autenticação é realizada pelo gateway MCP.

Exemplo para Claude Code:

```bash
claude mcp add --scope project --transport http \
  --client-id "<CLIENT_ID_DO_PROJETO>" --client-secret \
  cloudiff "https://cloudiff.duckdns.org/cloudiff/mcp"

claude mcp login cloudiff
```

O `Client ID` e a chave usada como `Client Secret` devem ser copiados da identidade do projeto no Portal. Não publique esses valores. Caso o cliente exija uma porta fixa, acrescente `--callback-port <PORTA_LOCAL>`; cada usuário pode usar uma porta loopback disponível.

A URL Supabase é uma configuração independente:

```bash
export NEXT_PUBLIC_SUPABASE_URL="https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org"
```

## OAuth e callback local

Este callback é válido para um cliente desktop:

```text
http://127.0.0.1:53858/
```

O cliente abre uma porta temporária no computador do próprio usuário. Depois da autorização, o navegador retorna ao mesmo computador. Portanto:

- não crie NAT para `127.0.0.1` no Maurício;
- não troque o callback por um IP do servidor;
- mantenha PKCE `S256` e o parâmetro `state`;
- permita portas loopback dinâmicas para clientes desktop;
- exija correspondência exata do `redirect_uri` entre autorização e troca do código.

O gateway versionado aceita callbacks HTTP em `127.0.0.1`, `localhost` ou `::1` quando há porta explícita, além dos callbacks HTTPS cadastrados para Claude e ChatGPT.

## Checklist de aceite

- [ ] `80/tcp` e `443/tcp` chegam ao proxy `10.62.91.3`.
- [ ] `/git/` chega ao Forgejo e `ROOT_URL` contém `/git/`.
- [ ] `2222/tcp` chega ao Forgejo SSH e aparece na URL de clone.
- [ ] `54400/tcp` permanece restrita por VPN, allowlist ou TLS.
- [ ] `/cloudiff/mcp` chega ao gateway MCP.
- [ ] o domínio do tenant não anuncia `/mcp` como endpoint do agente.
- [ ] as rotas OAuth não passam por um segundo login de borda.
- [ ] cada projeto usa identidade, token e ACL próprios.
- [ ] logs do proxy não registram tokens, códigos OAuth ou strings PostgreSQL completas.

## Conexões remotas temporárias (U19)

O CloudIFF oferece um painel **Conexões remotas** dentro de **Conectores**, sem nova rota de navegação. O painel reutiliza a sessão Authentik e a ACL já aplicada pelo Portal: um usuário só recebe inventário e leases dos projetos que já consegue visualizar.

Arquitetura homologada:

- FRP-Panel `v0.1.37` é o control plane interno, com Master + FRPS no nó `proxy` e clientes nos papéis `runtime` e `control-plane`;
- o FRPS aceita somente a faixa TCP `24000-24999`;
- o firewall publica a faixa uma única vez para o nó proxy; portas sem lease ativo não possuem listener FRP;
- o Portal reserva a porta transacionalmente, cria o proxy pelo API token de privilégio mínimo e grava TTL no banco do Portal;
- um timer independente revoga leases expirados mesmo que o usuário feche o navegador;
- o aluno não instala cliente FRP: usa diretamente Git/SSH, IDE ou cliente de banco no host/porta exibidos pelo Portal;
- o Faro não participa do caminho e não foi modificado.

### Segurança por serviço

- **Forgejo SSH**: liberado por lease temporário; a autenticação continua sendo a chave SSH cadastrada no Forgejo.
- **PostgreSQL/Supabase raw TCP**: permanece bloqueado (`tls_required`) enquanto não houver gateway TLS homologado. A abertura de FRP não substitui criptografia/autenticação do protocolo.
- **MCP, Studio, Komodo, Forgejo HTTPS e demais aplicações web**: continuam usando seus endpoints HTTPS existentes; o painel apenas apresenta os links, sem criar porta TCP paralela.
- **Preview/Homologação/Produção**: não recebem SSH artificial. Os containers atuais não possuem daemon SSH; acesso administrativo continua pelo terminal/Komodo existente.

A porta é uma **lease**, não uma identidade. Authentik protege o painel; o protocolo remoto mantém sua própria autenticação. Nenhuma senha, token do FRP-Panel ou segredo de banco é retornado pela API do painel.
