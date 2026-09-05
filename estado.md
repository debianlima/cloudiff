# Estado — 2026-09-05 — contrato v53

## Decisões vigentes
- A WAN pública do CloudIFF permite somente TCP/80 e TCP/443.
- SSH administrativo permanece apenas nas redes internas/VPN; não existe WAN/NAT público para 22.
- Conexões remotas de alunos usam **relay 443-only**: HTTPS e SSH compartilham a 443 pública; nenhuma porta de PostgreSQL, Forgejo SSH ou container é publicada.
- O botão **Conexões remotas** permanece como único acréscimo visual em Conectores e abre um `<dialog>`; a arquitetura de navegação não foi alterada.
- O Portal Authentik/ACL é a fonte de autorização. Cada ativação cria lease curta e chave Ed25519 temporária entregue uma única vez; o servidor armazena somente chave pública/fingerprint.
- Forgejo SSH usa destino interno direto `10.62.91.2:2222` pelo gateway.
- PostgreSQL/Supabase usa conector reverso da Hospedagem pela própria 443; o forward do tenant existe apenas enquanto há lease ativa e fica em loopback no proxy.
- Faro permanece fora do caminho e não foi modificado.
- A skill de projeto vigente é `cloudiff@0.1.28`.

## Decisões superadas
- FRP-Panel + faixa pública `24000-24999` — superado e removido; a regra NAT experimental e os runtimes FRP foram eliminados.
- Tratar porta dinâmica como superfície WAN — superado. A porta pública é sempre 443; o objeto temporário é a autorização/forward interno.
- Consultar o Portal a cada autenticação SSH — superado por cache local de leases atualizado em segundo plano, fail-closed.

## Evidências U19
- pfSense: removida regra legada WAN `Allow all ipv4+ipv6 via pfSsh.php`; permanecem apenas regras WAN TCP/80 e TCP/443.
- Sonda externa independente: 80/443 abertas; 22 e portas de serviço testadas fechadas/filtradas.
- HTTPS público continuou válido após multiplexação 443 (`cloudiff`, Forgejo e projeto 1010).
- SSH pelo mesmo `cloudiff.duckdns.org:443` alcançou Forgejo e devolveu `SSH-2.0-Go`.
- PostgreSQL do Teste Sofá respondeu ao SSLRequest através de SSH/443 + reverse relay da Hospedagem.
- Destino não declarado foi negado por `permitopen=`.
- Release de lease eliminou sessão já estabelecida em 21 segundos e cancelou o listener reverso de PostgreSQL.
- Browser Chromium móvel/dark: Conectores → Conexões remotas abriu overlay, Teste Sofá exibiu somente gateway público `:443`, entregou chave uma vez e voltou a “Ativar acesso” após Encerrar, sem erro JS.
- Teste Sofá foi devolvido a zero containers em execução ao final da homologação.

## Pendências fora do escopo
- U14: drawer vazio de **Gerenciar permissões** do Teste Sofá permanece separado.
- P2 do Teste Sofá continua dependente de duas aprovações humanas distintas admin/professor.

## Trabalho compartilhado
- Deve estar vazio em `manifesto.yaml` após fechamento da U19.

## Competências ativas na U19
- `cloudiff@0.1.28`.
- `desenvolvedor-de-software@15`.
- `github-incremental-reconciliation@7`.
- `governanca-ontologica-de-skills@1.0.5`.
- `network-ssh-operations@1`.
- `operational-ui-truth@1`.
- `telemetry-data-visualization@2`.
