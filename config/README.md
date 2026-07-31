# Configuração

Os arquivos `*.env.example` listam somente as variáveis esperadas pelos serviços. Valores reais não são versionados.

- `<required-secret>`: deve vir de cofre de segredos ou arquivo protegido no host;
- `<configure>`: parâmetro de ambiente a ser definido para o ambiente de destino.

Arquivos JSON nesta pasta são políticas versionáveis. Chaves `*.pub` são públicas e usadas apenas para verificação de assinatura.
