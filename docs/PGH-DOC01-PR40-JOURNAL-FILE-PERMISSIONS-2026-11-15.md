# PGH / CloudIFF — revisão independente das permissões do journal PR #40

**Data:** 15/11/2026. **Revisor:** documentacao/cloudiff/doc-01.
**Escopo:** protótipo standalone do PR #40, base commit 05d3978;
nenhum banco, serviço ou arquivo de produção foi alterado.

## Achado reproduzido

O SQLite com sqlite3.connect(db_path) cria o arquivo principal
e o WAL conforme o umask do processo. Em um diretório temporário
traversável 0755, executando com umask 022, foram observados
**0644** tanto no SQLite quanto no WAL; com umask 077,
**0600**. O código original não fixava nem validava esse modo.
O conteúdo atual do journal contém apenas metadados e
identificadores de operação, sem credenciais; o risco de
leitura indevida depende do diretório e dos privilégios
efetivos. **Não é evidência de exposição produtiva.**

## Correção proposta, apenas em branch de revisão

- Abrir/criar banco principal com os.open e modo 0600
  antes de conectar via SQLite; rejeitar symlink final
  (O_NOFOLLOW, no Linux) e arquivo não regular.
- Apertar para 0600 o banco existente e eventuais
  sidecars WAL/SHM já presentes, sem modificar o umask
  global — que afetaria outras threads.
- Mantém o contrato existente de fases, fencing SQLite,
  verificador externo e exigência de lease Docker.

Os diretórios de dados devem ser **controlados pelo
serviço** e sem escrita por terceiros. A verificação de
symlinks no componente final não protege contra troca
de componentes do caminho por um adversário que
controle diretórios ancestrais. O owner deve validar
a localização final, identidade e ACL do serviço ao
integrar o PR #40 ao worker.

## Validação

- portal/tests/test_doc01_publication_journal_private_files.py:
  5 testes independentes usando somente TemporaryDirectory.
- Criação sob umask 022: SQLite e WAL 0600.
- Banco legado 0644 ajustado para 0600.
- Sidecars WAL/SHM legados 0644 ajustados para 0600.
- Caminho symlink rejeitado sem modificar o alvo.
- Caminho diretório, não arquivo regular, rejeitado.
- test_dev01_publication_recovery_journal.py: 22 testes
  de contrato original PASS, inclusive concorrência,
  verificador externo e retry.
- scripts/validate.sh: OK, sem violações.
- Suíte completa: consultar evidência de CI/testes anexada
  antes de promover a mudança.

## Gate de integração

Este commit é **uma proposta em branch isolada**,
não um merge no PR #40 e não um deploy. Dev-01 deve
revisar comportamento no diretório real do worker;
infra-01/aud-01 devem verificar ACL/dono, rollback,
uma possível migração de modos legados e ausência
de symlink path traversal. Exigir ainda G0/G1,
OpenBao produtivo, teste Docker crash/rollback e
verificador de evidência confiável antes de qualquer
publicação Hn -> Pn.

O P0 original de 22 configurações Git com credenciais
continua não resolvido por este patch.
