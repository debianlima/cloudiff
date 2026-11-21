# CloudIFF — padrão canônico Preview → Homologação → Produção

**Vigência:** 20/11/2026. **Escopo:** todos os projetos CloudIFF. **Autoridade:** decisão humana explícita do proprietário nesta sessão. Este documento substitui interpretações anteriores que tratem Preview, Homologação ou Produção como rebuilds independentes.

## Regra em uma linha

**Forgejo → Preview fixo sincronizado → clone integral e congelado para Homologação → promoção da mesma instância homologada para Produção.**

## 1. Preview é um slot fixo

Cada projeto possui um único Preview operacional estável, com identidade e URL fixas. Alterar o Forgejo **não cria outro Preview** e não gera W2/W3 ou novas gerações de Preview como mecanismo normal de atualização.

O Preview acompanha o repositório Forgejo canônico. Uma mudança aceita no branch/fonte configurada deve atualizar o **mesmo slot de Preview**. A implementação pode reiniciar ou recriar componentes internos quando tecnicamente necessário, mas não pode mudar a identidade lógica do Preview, seu endereço público nem transformar cada commit em um novo ambiente Preview.

O sincronizador deve validar pelo menos: commit esperado, artefatos/imagens correspondentes, health e resultado real do deploy. Falha de atualização mantém o último estado saudável disponível e registra erro; não declara sucesso apenas porque um job foi aceito.

## 2. Homologação é clone do Preview existente

Ao solicitar Homologação, o CloudIFF deve capturar/clonar **o estado integral necessário para reproduzir o Preview naquele instante**, incluindo os containers/stack, imagens/rootfs, configuração runtime e volumes/dados persistentes pertencentes ao projeto, preservando referências de segredo sem publicar valores.

A Homologação recebe identidade própria (Hn). **Código, imagens e origem Forgejo ficam congelados** no estado clonado: commits novos continuam atualizando somente o Preview e não alteram automaticamente a Hn. A configuração runtime do estágio (variáveis públicas/secrets por referência) pode ser alterada **explicitamente pelo usuário autorizado** durante a homologação; o estado configurado no instante do aceite passa a fazer parte do que foi homologado e é o que segue para Produção.

Criar uma nova Homologação não reconstrói a aplicação a partir do Git. A origem é o Preview saudável que está sendo testado. A nova Hn passa a ser a única Homologação ativa; H anterior não promovida deixa de ser runtime ativo e pode ter containers/bridge removidos depois que snapshot/evidência suficiente estiver preservado. H promovida deixa de existir como ambiente H: a própria instância passa a ser P e o registro H permanece somente como histórico/auditoria.

## 3. Produção promove a própria Homologação aprovada

A aprovação de uma Hn **não autoriza rebuild**. Produção deve receber/promover **a mesma instância/estado de runtime que foi homologado**. O mecanismo preferido é mudança controlada de identidade, roteamento, alias/pointer e estado de ativação; não é permitido reconstruir novamente a aplicação do Forgejo ou gerar outro snapshot logicamente diferente entre aprovação e Produção.

Na promoção, a Produção anterior é desativada e a Hn aprovada torna-se a Produção ativa. A Produção anterior fica parada e preservada enquanto for necessária para rollback exato do seu estado persistente. Bridges/rotas versionadas antigas são reconstruíveis e não precisam permanecer como containers ociosos. O rollback prepara/religa a Produção histórica, valida saúde e rota antes da troca do endereço estável e só então desliga a P que estava ativa; não reconstrói a aplicação a partir do código-fonte.

## 4. Separação entre evolução e aceite

O Preview continua sincronizando o Forgejo mesmo enquanto uma Homologação está sendo testada. Portanto podem coexistir:

- Preview fixo em commit mais novo;
- Homologação congelada em commit anterior;
- Produção ativa em homologação previamente aprovada.

Isso é esperado e não é drift. O vínculo obrigatório é de proveniência: cada Hn registra de qual estado/commit do Preview foi clonada; cada Produção registra qual Hn aprovada foi promovida.

### Edição humana de variáveis e secrets

No Portal humano, autenticação da sessão, CSRF e ACL de escrita do projeto autorizam diretamente a edição de variáveis. Não criar uma aprovação separada para esse salvamento. O Approval Service permanece no caminho MCP/automação e em operações cujo contrato declare approval explicitamente.

Secrets aparecem mascarados. Campo vazio preserva o valor atual; preencher um novo valor rotaciona a referência internamente e aplica no estágio sem devolver plaintext ao navegador. `POSTGRES_PASSWORD` é migrado de forma transacional junto com `DATABASE_URL` e com preservação do volume; `POSTGRES_DB` e `POSTGRES_USER` são mudanças estruturais e exigem operação específica.

## 5. Regras para agentes e serviços

Todos os agentes PGH e componentes CloudIFF (Portal, Forgejo integration, Komodo, deployment broker, executor e reconciliadores) devem tratar este fluxo como contrato global. Antes de mudar pipelines de Preview/Homologação/Produção, consultar este documento.

São **não conformes** por padrão:

1. criar novo Preview para cada commit;
2. mudar a URL/identidade do Preview a cada atualização;
3. homologar reconstruindo do Git em vez de clonar o Preview corrente;
4. deixar Homologação continuar recebendo commits do Forgejo;
5. aprovar Hn e depois reconstruir/reempacotar outra instância para Produção;
6. promover snapshot/artefato diferente daquele efetivamente homologado;
7. manter duas homologações ou duas produções simultaneamente ativas sem decisão humana explícita de exceção;
8. declarar sincronização Forgejo→Preview sem verificar commit e health reais.

## 6. Segurança e segredos

"Clone integral" não significa registrar ou exportar valores secretos para Git, Atlas, logs, prompts ou memória PGH. Segredos continuam protegidos pelo mecanismo de secret reference/cofre do CloudIFF. O clone deve preservar o acesso runtime necessário sem transformar segredo em documentação ou payload público.

## 7. Gates mínimos

- **Preview sync:** Forgejo HEAD/fonte esperada = revisão runtime ativa; health aprovado; URL fixa preservada.
- **Clone H:** Preview saudável; identidade de origem registrada; clone completo; H congelada; nenhuma leitura automática posterior do Forgejo.
- **Aceite H:** testes e aprovação explícita do homologador autorizado.
- **Promoção P:** a própria H aprovada é ativada em Produção; sem build, rebuild ou novo clone intermediário.
- **Troca:** versão ativa anterior desativada somente após nova ativa passar health/readback; rollback continua disponível.

## 8. Legado

Registros históricos continuam válidos como evidência do que aconteceu, mas qualquer texto anterior que prescreva "novo banco de H", "novo container de Produção", "rebuild em Produção", "snapshot H→novo P" ou múltiplos Previews como fluxo normal fica **SUPERADO para decisões futuras** por este contrato.

## 9. Variáveis por estágio, refresh e histórico

- Variáveis pertencem ao runtime do estágio ativo: Preview edita W, Homologação edita H ativa e Produção edita P ativa.
- W→H herda a configuração corrente do Preview; H→P herda a configuração corrente da H. Secrets recebem referências próprias do ambiente de destino e valores não são expostos.
- Editar uma variável depois da criação pode recriar somente o container do serviço afetado, preservando deployment e volumes. Isso não altera a regra de que a promoção H→P em si usa a mesma instância.
- Ao terminar com sucesso o job de criação de H, promoção H→P ou rollback/reativação histórica, o Portal deve atualizar o workspace e recarregar a página inteira, sem exigir clique manual em “Atualizar”. Em falha, o erro deve permanecer visível sem reload automático.
- Uma H `published` é histórico, não ambiente ativo: não deve oferecer Site, Terminal ou Variáveis como H.
- O Histórico de Produção pode reativar uma P anterior somente com autorização do responsável/admin. A P histórica é preparada e validada antes do cutover; em falha, a P atual permanece/restaura-se como ativa.

## 10. Retenção de containers

O alvo operacional é **zero runtime H residual** e apenas um Preview + uma Produção ativos. Produções anteriores podem manter seus containers/volumes **parados** quando necessários para rollback exato. Proxies/bridges e rotas versionadas antigas são descartáveis/reconstruíveis. Containers legados só devem ser removidos depois de comprovar mecanismo equivalente de restauração; diretórios/volumes de dados não são apagados por limpeza de container.
