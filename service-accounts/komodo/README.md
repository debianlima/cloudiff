# PGH CloudIFF — identidade de serviço do Komodo

**Situação atual: PENDING_ADMIN_CREATION.** Esta pasta descreve um cadastro solicitado e auditável. **NÃO comprova que existe uma conta no Komodo, nem concede permissões.** A conta ainda deve ser criada por administrador legítimo do Komodo Core.

## Conta planejada

- **Login/identificador sugerido:** `svc-pgh-cloudiff`
- **Tipo:** `Service User` nativo do Komodo; não uma conta humana e não um usuário Linux.
- **Escopo inicial:** exclusivamente recurso `Stack` `cloudif-agenda-unica`, nível `Read`, sem `Terminal`, `Inspect`, `Logs` sensíveis, acesso a outros recursos, funções de administração, servidor, build nem repo.
- **Uso:** observabilidade e consultas não sensíveis dos agentes PGH. Essa conta **não deve** editar a Agenda ou reiniciar containers.
- **Autenticação:** uma chave de API **distinta por agente**, com expiração em até 24h; valores devem entrar **diretamente no gerenciador institucional de segredos**. Nunca registrar valores de chaves/senhas em arquivos de memória, documentação, logs, GitHub ou no chat. O cadastro contém apenas um padrão de `secret_ref` e não representa segredo ativo.
- **Atenção:** todas as chaves da mesma Service User herdam as permissões da conta. Portanto, **não elevar esta conta compartilhada a `Write`**. Mudanças da API Agenda exigem uma identidade de manutenção **separada**, Stack-specific, temporária, criada pelo administrador após verificação de G0/G1 e rollback. `Write` é capaz de excluir o recurso.

## Fluxo do administrador Komodo

1. Confirmar a identidade do administrador e o domínio oficial do **Komodo Core**. Não usar SSH/Docker/Mongo para contornar a autenticação normal de usuário.
2. Usar a interface administrativa ou API oficial `CreateServiceUser` para criar `svc-pgh-cloudiff` com descrição `PGH CloudIFF — leitura auditada de recursos CloudIFF; sem operação produtiva`. Se já existir, reconciliar a identidade e **não recriar** nem apagar.
3. Garantir `enabled=true`, `admin=false`, `super_admin=false`, `create_server_permissions=false`, `create_build_permissions=false`, sem grupo `Everyone` ampliado nem promoção por Authentik. O sincronizador CloudIFF promove membros `CloudIF-Tenants-Admin` e `CloudIF-Professor`; **não associar essa identidade a esses grupos**.
4. Em permissões do Komodo, conceder somente `Stack: cloudif-agenda-unica → Read`. Não adicionar `Terminal`, `Inspect`, nem herança global; `Other resources → None`.
5. Pelo mecanismo oficial `CreateApiKeyForServiceUser`, emitir credenciais **individuais por agente** e prazo curto. Armazenar diretamente no gerenciador de segredos configurado pelo administrador. Não retornar segredos ao PGH. Revogar chaves antigas ou expostas.
6. Com a credencial de teste recebida pelo broker (sem expor valor), verificar `GetStack/ListStacks` somente para a stack autorizada; ações de escrita/execução, acesso a outra stack, inventário de servidor e terminal devem falhar por autorização. Registrar apenas `pass/fail`, ID de cadastro, expiração, identidade do operador e protocolo de mudança, **sem payloads privados**.
7. Atualizar este manifesto e o `access-ref` PGH **somente após** as provas de criação, ACL e entrega da chave via broker. Remover/expirar permissão imediatamente após a janela autorizada, se houver.

## Acesso de manutenção (fluxo distinto)

Para a correção de `DATABASE_URL` da Agenda (`5432` → `54402`), uma conta de leitura não basta. O administrador pode conceder temporariamente a **outro Service User**, específico do operador de manutenção, nível `Write` apenas na stack `cloudif-agenda-unica`, durante janela controlada e com backup/rollback testados. A criação dessa identidade e emissão de chave exigem aprovação/controle independentes; nunca ampliar o usuário compartilhado de auditoria.

## Procedimento para os agentes PGH

Identidades: `infraestrutura/cloudiff/infra-01`, `desenvolvimento/cloudiff/dev-01` e `dev-02`, `auditoria/cloudiff/aud-01`, `documentacao/cloudiff/doc-01`, `testes/cloudiff/surface-01`.

- Consultar `service-accounts/komodo/svc-pgh-cloudiff.json` e o `access-ref` da memória PGH antes de tentar uma ação.
- Enquanto `state=PENDING_ADMIN_CREATION`, **não usar** a identidade como se estivesse ativa e não inventar token nem privilégios.
- A conta inicialmente é de leitura: se uma operação requer permissão `Execute/Write`, encaminhar ao proprietário do Komodo e registrar evidência de autorização G0/G1.
- Cada agente usa apenas sua `secret_ref` específica, sem copiar chaves ou compartilhá-las com outros agentes.
- Registrar na memória o resultado e identificador de auditoria, jamais segredos. Revogar as chaves ao encerrar a janela ou na suspeita de exposição.

**Fonte do modelo:** permissão nativa Komodo (`None`, `Read`, `Execute`, `Write`), API `CreateServiceUser`/`CreateApiKeyForServiceUser`, verificação de usuário e permissões via admin. Documentação oficial Komodo: https://komo.do/docs/configuration/permissioning e https://komo.do/docs/ecosystem/api.
