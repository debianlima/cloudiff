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

A Homologação recebe identidade própria (Hn) e fica **congelada** no estado clonado. Depois do clone, commits novos no Forgejo continuam atualizando somente o Preview e não alteram a Hn já em teste.

Criar uma nova Homologação não reconstrói a aplicação a partir do Git. A origem é o Preview saudável que está sendo testado. A nova Hn passa a ser a homologação ativa; a homologação anterior é desativada, preservada conforme política de rollback/retenção e não permanece concorrendo como ativa.

## 3. Produção promove a própria Homologação aprovada

A aprovação de uma Hn **não autoriza rebuild**. Produção deve receber/promover **a mesma instância/estado de runtime que foi homologado**. O mecanismo preferido é mudança controlada de identidade, roteamento, alias/pointer e estado de ativação; não é permitido reconstruir novamente a aplicação do Forgejo ou gerar outro snapshot logicamente diferente entre aprovação e Produção.

Na promoção, a Produção anterior é desativada e a Hn aprovada torna-se a Produção ativa. A versão anterior deve ser preservada pelo período/política de rollback aplicável. O rollback reativa o estado produtivo anterior; não reconstrói a aplicação a partir do código-fonte.

## 4. Separação entre evolução e aceite

O Preview continua sincronizando o Forgejo mesmo enquanto uma Homologação está sendo testada. Portanto podem coexistir:

- Preview fixo em commit mais novo;
- Homologação congelada em commit anterior;
- Produção ativa em homologação previamente aprovada.

Isso é esperado e não é drift. O vínculo obrigatório é de proveniência: cada Hn registra de qual estado/commit do Preview foi clonada; cada Produção registra qual Hn aprovada foi promovida.

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

