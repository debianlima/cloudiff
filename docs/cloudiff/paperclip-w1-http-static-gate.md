# Paperclip Preview W1 1025 — verificação HTTP estática (PGH T-011)

## Defeito de origem

O Preview W1 em https://1025-w1-preview.cloudiff.duckdns.org/
pode apresentar o healthcheck genérico do Apache como HTTP 200 enquanto
a raiz responde 403 ou o HTML ui/ aponta diretamente para
/src/main.tsx e /@vite/client, indisponíveis no proxy. Esses status
não demonstram que a aplicação Paperclip Node/Vite foi construída e publicada.

O executor de publicação precisa usar uma imagem isolada do Paperclip,
compilada a partir de um commit Forgejo verificado, em vez de apontar o W1
ao serviço privado já existente na Forja.

## Verificador

O script portal/tools/check_paperclip_w1_readonly.py é apenas de leitura.
Ele verifica TLS público com a cadeia de confiança padrão do sistema,
a resposta no gateway interno previamente autorizado, e recursos
CSS/JavaScript estáticos em assets/ (nunca segue redirecionamentos).
Não envia cookies, tokens, senhas ou parâmetros de usuário ao serviço.

Comando para execução de uma estação autorizada que alcance a origem
10.62.91.2:18150, sem usar privilégios Docker:

    python3 portal/tools/check_paperclip_w1_readonly.py

O código de saída é 2 para falha ou prova estática insuficiente.
Saída 0 significa somente STATIC_APP_ASSET_200_AUTH_E2E_PENDING;
não representa autenticação, permissão de acesso, banco de dados,
sincronização Forgejo, healthcheck de container ou operação E2E.

O modo --output gera um JSON novo 0600 em um diretório com acesso
controlado pelo operador. A resposta não inclui corpo de API ou
credenciais, somente status HTTP, content type, título reconhecido e
um caminho estático validado.

## Gates para considerar a T-011 concluída

É indispensável comprovar acesso administrativo restrito ao stack
Paperclip W1, reserva de alteração, backup e restauração isolada,
segredos por secret_ref com ACL/TTL, build do commit correto,
implantação independente, rollback, URL e JS/CSS reais, API,
login autorizado e negação entre projetos, auto-sync Forgejo->W1,
isolamento Hn/Pn e reauditoria por aud-01 e surface-01.

A tarefa infraestrutura/cloudiff/infra-02 T-011 permanece aberta
enquanto esses controles não estiverem comprovados. O verificador
é um instrumento de diagnóstico, não um comando de correção ou deploy.
