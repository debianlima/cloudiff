# Agenda Única P1020 — procedimento vigente de gerenciamento de publicações

**Vigência:** 22/11/2026. **Escopo:** `agenda-unica` / public number 1020. **Norma global:** `PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`. **Runbook:** `RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`.

Este documento descreve como aplicar o padrão CloudIFF especificamente à Agenda Única. Em divergência, a norma global e o estado vivo comprovado vencem este resumo.

## 1. Estado operacional de referência

- Preview fixo: **W3** — `1020-w3-preview.cloudiff.duckdns.org`.
- Produção ativa: **P8** — mesma instância promovida de H8.
- Alias principal: `agendaunica.cloudiff.duckdns.org`.
- Revisão observada em W3/P8/alias no fechamento: `18416127cdf9`.
- P2/P3/P6/P7: `archived`, fora do histórico operacional e sem containers/volumes ativos.
- Publisher mantém somente W3 e P8 para P1020.

## 2. Preview W3 é o ambiente vivo

Forgejo sincroniza o **mesmo W3**. Não renumerar W3 para W1 e não criar novo Preview por commit.

O estado real do W3 inclui mais que o Git:

- código sincronizado;
- filesystem/rootfs atual dos containers;
- configuração de runtime;
- variáveis e referências de secrets do estágio Preview;
- volumes persistentes do projeto;
- alterações manuais feitas no runtime enquanto o container continuar sendo o que será clonado.

### Instalações manuais pelo Terminal

O Terminal do Preview linked-compose abre no Stack Agenda, serviço `api`, container `cloudif-agenda-unica-api-1`.

Se um usuário autorizado instalar manualmente uma tecnologia ou pacote dentro do container W3, por exemplo PHP, e **homologar antes de o container ser recriado**, os arquivos instalados na camada gravável/rootfs entram no clone integral W→H. Portanto a H recebe aquela instalação e, se aprovada, a mesma H promovida mantém a instalação em P.

Regras:

1. `restart` do mesmo container não apaga a camada gravável;
2. `recreate` do Preview a partir da imagem/Compose original pode apagar instalação manual que não esteja em imagem, volume ou configuração durável;
3. alteração feita depois da criação de H não modifica a H já congelada; é preciso criar nova H;
4. para mudança permanente/repetível, preferir código, imagem, pacote declarado ou configuração versionável/gerenciada em vez de depender somente de alteração manual;
5. nunca instalar runtime apenas para fazer uma aba do Portal parecer preenchida.

## 3. PHP, Node.js e diagnóstico

No fechamento desta versão, W3 não possui PHP nem Node.js. O runtime observado usa Python no serviço API e frontend no serviço web.

As abas PHP/Node.js são **diagnóstico do estágio**, não catálogo obrigatório. Ausência retorna HTTP 200 com `available=false` e lista os binários realmente detectados. Se PHP for instalado manualmente no W3, a aba PHP deve passar a mostrar a versão detectada; ao clonar W3→H, essa versão acompanha o rootfs capturado.

## 4. Variáveis e secrets

Variáveis pertencem ao estágio selecionado:

- Preview edita W3;
- Homologação edita a H ativa;
- Produção edita P8/Pn ativa.

Herança:

```text
W3 corrente --clone--> Hn corrente --promoção da mesma instância--> Pn
```

A H recebe as variáveis/configuração existentes no W3 no momento do clone. Alterações explícitas feitas em H passam a fazer parte do estado homologado. P recebe o estado corrente da própria H promovida. Depois da promoção, alterações explícitas em P afetam somente P.

No Portal humano, sessão autenticada + CSRF + ACL de escrita autorizam o salvamento. Não abrir approval MCP separado para edição humana de variável. Secrets permanecem mascarados; campo secreto vazio mantém o valor, novo valor rotaciona/aplica sem devolver plaintext ao navegador.

## 5. Homologação

`Enviar Preview para homologação` clona o runtime W3, não reconstrói do Forgejo.

O clone integral deve preservar:

- rootfs/camada gravável dos serviços;
- imagens e identidade dos serviços;
- configuração runtime;
- referências protegidas de secrets;
- volumes/dados persistentes pertencentes ao projeto;
- revisão/proveniência do Preview.

Depois de criada, H não acompanha novos commits do Forgejo. Nova alteração no W3 exige nova H para ser homologada.

## 6. Produção

`Enviar para Produção` não faz rebuild, não cria equivalente novo e não reclona do Git. A **mesma instância H homologada** passa a ser P por mudança controlada de estado/rota/alias.

A promoção não pode modificar o rootfs que foi testado em H. Isso inclui pacotes instalados manualmente que estavam presentes no W3 quando a H foi capturada.

## 7. Histórico, rollback e exclusão

A P ativa nunca pode ser excluída.

P histórica pode existir operacionalmente enquanto houver runtime reativável:

- **Subir**: disponibiliza a Pn versionada para teste sem mudar o alias principal;
- **Desligar**: deixa a Pn Offline;
- **Ativar no endereço principal**: somente após health, troca o alias estável;
- **Excluir container**: remove o runtime histórico e arquiva a publicação, retirando-a da lista operacional.

Modos de exclusão:

- `compose-snapshot`: runtime é removido, snapshot/auditoria permanecem; reidratação pode ser possível;
- `legacy-final`: apenas P legada inativa, com validação Komodo de identidade/labels/alias; remove o container, arquiva a P e `canRehydrate=false`.

No estado atual da Agenda, apenas P8 permanece operacional; P2/P3/P6/P7 são auditoria arquivada.

## 8. Read-model e desempenho da interface

A interface não deve varrer filesystem, Komodo e serviços remotos a cada clique. O Portal usa `portal_readmodel_cache` em SQLite para índices descartáveis de Projetos, tenants, estados/runtime, contexto de Publicação, Conectores e Aprovações.

- timer existente faz prewarm a cada 60 s;
- mutações invalidam o namespace/chave afetado e disparam refresh assíncrono;
- o índice nunca substitui a fonte de verdade;
- as listas de Publicação usam somente registros operacionais `status='published'`; `archived` permanece apenas em auditoria.

## 9. Conta administrativa

A conta ADMIN ativa do projeto usa o e-mail `agendaunica@iff.edu.br`. Credenciais secretas não são documentadas. Senhas são armazenadas somente como hash nativo da aplicação e não entram em Git, Atlas, memória PGH ou backup textual.

## 10. Checklist antes de homologar

- W3 responde health e revisão esperada;
- Terminal abre o runtime correto no Komodo;
- PHP/Node mostram o diagnóstico real do W3;
- alterações manuais necessárias ainda estão no container que será clonado;
- variáveis/secrets do Preview correspondem ao que deve seguir para H;
- banco/volumes estão íntegros;
- proveniência Forgejo/Preview está reconciliada;
- nenhuma H anterior está sendo confundida com o estado atual.

## 11. Checklist antes de promover

- H é a candidata efetivamente testada;
- código/rootfs/config/volumes correspondem ao estado homologado;
- variáveis da H estão corretas;
- health/readback de H passou;
- a promoção usa o mesmo `deployment_id` da H;
- alias principal só muda depois do health da nova P;
- H deixa de ser runtime H após promoção;
- Produção anterior segue a política de histórico/exclusão, sem runtime residual desnecessário.
