# Política de segurança

Não registre credenciais, tokens, certificados, arquivos `.env`, bancos, logs ou backups neste repositório.

Antes de cada push:

1. execute uma varredura de segredos;
2. revise o diff;
3. confirme que arquivos de runtime não foram adicionados;
4. use referências de ambiente para qualquer valor sensível.

Em caso de exposição acidental, revogue imediatamente a credencial e remova-a do histórico Git.
