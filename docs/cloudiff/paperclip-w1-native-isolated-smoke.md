# Paperclip W1 — smoke test local e isolado do servidor Node24

O arquivo portal/tools/owner_paperclip_w1_native_canary_smoke.py executa
somente no host Mauricio, com UID0 já autorizado. A ferramenta só aceita
a fonte do commit dfcaaf831438cf0402d54a5ede388c3dc66bf222 e uma
imagem local de nome fixo cloudif/paperclip-w1-1025-native:dfcaaf831438.

Modo padrão: apenas verifica se a imagem existe, sem criar containers,
volumes, redes, portas ou alterar serviços.

A opção --execute é exclusivamente para o canary de laboratório,
depois de conferir a identidade do operador e do build. Ela falha
se já existirem recursos com os nomes reservados para o teste. Se
puder executar, cria um volume temporário próprio e um único container
Node24 com --network none, sem portas publicadas, limite de CPU, memória
e processos, no-new-privileges e modo de autenticação habilitado.
O processo tenta a raiz HTML, /api/health e até oito recursos JS/CSS,
sem criar usuário de teste, sem copiar senha e sem ler dados privados.

Após o teste, remove somente o container e o volume que criou e cujos
rótulos correspondam ao marcador PGH de laboratório. Não remove nem
altera serviços ou volumes do W1 real, Hn/Pn ou Paperclip privado da
porta 3100. Se ocorrer qualquer conflito de identidade, falha fechada.

O relatório fica exclusivamente em arquivo protegido na pasta de
compilação do Mauricio. Um resultado favorável significa somente
STATIC_BACKEND_HTTP_READY_AUTH_E2E_PENDING; NÃO é teste de login,
permissões, conexão Forgejo, navegador, recuperação de dados ou
liberação do cutover. Não executar enquanto faltar a imagem nativa
com sua origem verificada. O isolamento por --network none também
impede validar integrações externas, deliberadamente.

A passagem para produção exige validação institucional G0-G5,
owner do stack/lock, backup/restauração de DB/roles/volumes, OpenBao
secret_ref e ACL/TTL, integração contínua ao Forgejo, canary com
credenciais de teste próprias, TLS, UI/JS/API e autenticação positiva
e negativa com auditoria independente.
