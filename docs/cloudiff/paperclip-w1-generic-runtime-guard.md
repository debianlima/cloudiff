# PGH T-011: bloquear publicação genérica do Paperclip W1

O Preview 1025 do Paperclip é um monorepositório Node24/pnpm/Vite.
O caminho genérico da versão v144 do executor Komodo monta o checkout
em /var/www/html e usa launcher Apache/PHP, que não compila nem executa
o Paperclip. HTTP200 no health é falso positivo quando a raiz responde
403 e o HTML Vite cru aponta recursos JS404.

Esta alteração de código NÃO faz deploy ou corrige a interface sozinha.
Ela torna o caminho genérico fail-closed:

- Requisições autenticadas ensure e recreate do projeto paperclip
  respondem HTTP409 paperclip_native_runtime_required antes de atualizar
  ambiente, schema, Git, Docker ou Komodo.
- A função v144 de criação do Preview também recusa chamadas diretas
  para Paperclip, fechando outra via de publicação incompatível.
- O sync genérico v144 deixa de reiniciar o Apache legado do Paperclip
  após mudança de Git. O controlador nativo deverá compilar um commit,
  verificar imagem/stamp e fazer rollout com lock e rollback.
- Outros projetos não são interceptados. A consulta status permanece
  disponível, mas health genérico não atesta aplicação real.

O controlador nativo futuro deve oferecer caminho separado, não
contornar esta recusa. Exige G0 proprietário/lock; G1 backup/restauração
integral; G2 OpenBao secret_ref com ACL/TTL; G3 imagem Node24 e canary
real; G4 sincronização Forgejo->W1 isolada de Hn/Pn; G5 navegador,
JavaScript, API, login e negações de autorização auditadas.

Este commit fonte isolado não autoriza publicação em produção, exposição
da instância Paperclip privada na porta 3100 ou reutilização de banco.

Teste offline: python3 -m unittest discover -s portal/tests -p test_paperclip_w1_generic_runtime_guard.py
