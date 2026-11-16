# PGH CloudIFF — G4, contencao reversivel de modos Git config

Data: 16/11/2026 UTC. Identidade: documentacao/cloudiff/doc-01.
Status: utilitario preparado e validado exclusivamente em sandbox.
Nenhum config remoto dos 22 afetados foi alterado.

## Risco e escopo

Aud-01 detectou 22 arquivos .git/config com URLs HTTP(S)
contendo userinfo/credenciais legiveis por outros usuarios:
21 nos caminhos monitorados em Forja e 1 em Hospedagem.
Isto NAO significa 22 tokens unicos. Os valores jamais
devem ser copiados para tickets, logs, prompts ou Git.

O arquivo separado .git-credentials do proprio LabIFF
ja tem modo 0600 dentro de pasta 0700, sem mudanca.

## Utilitario entregue

scripts/owner_git_config_containment.py

Comandos disponiveis:
- plan: conta repositorios elegiveis e modes inseguros,
  sem imprimir path, usuario, URL nem token.
- apply: SOMENTE proprietario root autorizado; exige
  diretorios confiaveis e service-user correto para
  continuar lendo o arquivo apos a operacao, quantidade
  autenticada exata (--expect-count), manifesto imutavel
  root-only antes da mudanca, verificacao de inode e SHA,
  e torna configs selecionados modo 0600. Recusa
  symlinks, hardlinks, owners inesperados e arquivo alterado.
- rollback: revalida todos os arquivos antes de restaurar,
  exige manifesto root-only e confirmacao explicita
  --confirm-world-readable-rollback, pois recolocar
  permissao antiga pode reabrir a exposicao de segredos.

Manifesto contem metadados de arquivo e SHA, nao token.
O utilitario NAO edita origin URL, NAO troca credenciais,
NAO confere validade dos tokens e NAO executa git fetch.
Configuracoes com donos distintos devem ser inspecionadas
separadamente, jamais corrigidas com chown indiscriminado.

## Preflight para o administrador autorizado

1. Confirmar acesso seguro ao servidor, owner G0, horario,
   locks e plano de rollback. Executar apenas em hosts
   sob sua responsabilidade, nunca via senha no chat.
2. Identificar o usuario do processo que realiza git pull
   ou Komodo e conferir que corresponde ao dono dos configs.
3. Selecionar raiz especifica de repositorios, por exemplo
   /etc/komodo/stacks ou /srv/cloudif, e realizar plan.
4. Verificar a contagem observada antes de aplicar; a
   referencia inicial auditada e 21 Forja + 1 Hospedagem,
   porem qualquer divergencia exige nova analise.
5. Criar previamente diretorio de manifesto root-owned 0700
   em local aprovado e protegido (sem segredos no caminho).
6. Executar apply com a contagem exata, manifest e
   service-user conferidos. Verificar acesso do processo
   Git apos a mudanca, sem mostrar URL/token.
7. Rotacionar/revogar realmente as credenciais no OpenBao
   ou broker autorizado, atualizar origins sem userinfo,
   verificar fetch com secret_ref, reauditar G5.

Nao considerar G4 concluido so por chmod: ainda ha token
antigo na configuracao, embora menos acessivel.

## Evidencia validada

- 12/12 testes Python usando repositorios sinteticos.
- Compilacao da fonte e scripts/validate.sh sem erros.
- Teste real de CLI restrito a fixture descartavel
  no LabIFF: plan contou um Git config ficticio,
  apply 0644->0600, manifesto root-owned 0600,
  rollback sem confirmacao NEGADO, rollback confirmado
  restaurou 0644. Nenhum host externo acessado.
- Nao foi usado segredo real, senha, token ou conta
  produtiva no teste; a fixture contem dados invalidos.

## Gates restantes

Acesso SSH cti nao interativo a Hospedagem falhou
por ausencia de autenticacao disponivel. Sem owner
operacional e secret_ref, G4 remoto nao pode avancar.
G1 backup PostgreSQL+volumes precisa restore isolado,
G2 OpenBao produtivo precisa grants/TTL/identidade,
G3 Docker Hn->Pn exige lease e verificador real,
G5 reauditoria so depois da rotacao/revogacao.
O release CloudIFF v145.1 permanece bloqueado.
