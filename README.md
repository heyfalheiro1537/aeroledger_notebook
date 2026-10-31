# Experimentos — dados aeroportuários auditáveis (SBSJ)

Seis experimentos com a pista do aeroporto de São José dos Campos (SBSJ) para responder a uma pergunta sobre a arquitetura:

> Uma arquitetura baseada em *event sourcing* garante que dados aeroportuários geolocalizados sejam **rastreáveis até a causa**, **recalculáveis a partir das premissas**, **reconstruíveis no tempo**, com **adulteração evidente** e **consistentes entre produtos**, também para **quem lê sem acesso ao banco**? Onde estão os limites?

Cada experimento testa uma dessas propriedades, e a resposta é dada pelo código: os `assert` no fim do notebook dizem sim ou não.

Os experimentos usam a biblioteca [**aeroledger**](https://github.com/heyfalheiro1537/aeroledger), cujo manual está no repositório dela. Este repositório é só a avaliação: um notebook que usa a biblioteca passo a passo, como qualquer usuário faria.

---

## O problema

Hoje um dado de aeroporto é publicado como um número final: "a pista tem 2675 m". Quando a edição seguinte traz 2676, não há como saber se a pista foi remedida, se houve erro de digitação ou se a pista mudou. O valor antigo deixa de circular e não há como refazer o caminho até o novo.

O AIXM, padrão de troca de dados aeronáuticos, tem disciplina para corrigir dados, mas não garante que o histórico fique guardado nem que uma alteração indevida apareça, e guarda o número sem as premissas que o geraram.

## A proposta, em três ideias

1. **Um registro em que só se escreve.** Toda afirmação é um evento com autor, motivo e causa. Nada se apaga; corrigir é escrever de novo. Os eventos são encadeados por hash: alterar um evento antigo quebra a cadeia dali em diante.
2. **Posições apoiadas em poucos pontos medidos.** A pista não é guardada como um desenho, e sim como "da cabeceira 16 até a cabeceira 34". As coordenadas das cabeceiras (do AIP) são as premissas; tudo o mais é posicionado em relação a elas.
3. **O que é derivável é calculado, nunca guardado.** Comprimento, rumo e distâncias declaradas saem das premissas na hora da leitura. Se uma premissa muda, tudo o que depende dela muda junto.

## Os experimentos

| | Propriedade | Pergunta | O que o notebook faz | Resposta |
|---|---|---|---|---|
| **E1** | causa (contraste) | Um modelo que guarda só o valor final, como o AIXM, registra por que um valor mudou? | registra a pista "como o AIXM faria" com duas edições oficiais (2022 e 2026) e compara | não: 12 campos mudam, nenhum com causa |
| **E2** | derivação | Guardando só as premissas, os valores publicados se recalculam dentro da precisão do AIP? Trocar uma premissa obriga a reescrever algum outro dado? | grava só as cabeceiras e as larguras; calcula comprimento, rumos e distâncias declaradas; depois remede a cabeceira 34 | sim; e a troca escreve só o levantamento e o novo referencial |
| **E3** | reconstrução no tempo | O histórico guardado basta para reconstruir o estado de qualquer instante, com autor, motivo e causa de cada mudança? | reconstrói o estado antes e depois da remedição; registra uma interdição temporária; lê o envelope e a trilha de auditoria | sim |
| **E4** | evidência de adulteração | Uma alteração feita direto no banco, sem passar pela biblioteca, é detectada? Qual escapa, e o que a detecta? | quatro ataques diretos ao banco (alterar, apagar, inserir, reescrever tudo), cada um numa cópia | alterar, apagar e inserir: sim; reescrever tudo escapa ao banco e só a âncora externa detecta |
| **E5** | consistência e verificação | Dois produtos gerados do mesmo banco podem divergir? Um terceiro consegue verificar a integridade sem usar a biblioteca? | gera a tabela do AIP e a carta do mesmo banco; exporta os eventos e os confere com um verificador que não usa a biblioteca | não divergem; e o verificador independente chega ao mesmo resultado |
| **E6** | leitura separada | Quem lê por um tópico, sem acesso ao banco, chega à mesma resposta, nunca vê uma mudança pela metade e percebe um canal adulterado? Qual adulteração escapa? | publica o ledger num tópico (CDC); compara consumidores com o banco em cada corte; corta no meio da carga do eAIP; recorta pela THR16; pergunta antes de receber e com o banco fechado; compara seis consumidores; ataca o canal de seis jeitos | sim em tudo; no meio do tópico, toda adulteração para o consumidor; cortar ou anexar no fim escapa ao elo e só a âncora detecta |

Os valores comparados vêm do AIP (AD 2.12 e AD 2.13), de um cálculo geodésico em outro código (`geodesia.py`) e do PANS-AIM (2.2.1 para integridade, 2.1.3.2 para consistência entre produtos).

### Como foram pensados

**Cada experimento testa uma propriedade da arquitetura**, formulada como pergunta que o código responde com sim ou não. Juntos, eles seguem uma história: o problema no modelo de hoje (E1), os números recalculados das premissas (E2), a auditoria no tempo (E3), a segurança (E4) e a confiança de quem recebe os dados (E5).

**Os dados são reais.** Premissas e valores de comparação vêm do AIP Brasil (eAIP edição 20-2026, seções AD 2.12 e AD 2.13), da Carta de Aeródromo AIRAC 2604 e da Carta de Obstáculos AIRAC 2213. Só a remedição da cabeceira 34 e a interdição temporária são simuladas, porque não aconteceram de verdade.

**Nada valida a si mesmo.** As coordenadas das cabeceiras entram como premissa; o comprimento, os rumos e as distâncias calculados são comparados com outros campos do AIP, que não entraram no modelo. Onde não há valor publicado (a remedição), a comparação é com o mesmo cálculo feito por outro código (`geodesia.py`, fórmulas de Vincenty).

**As margens não foram escolhidas.** Elas saem da precisão com que o AIP publica cada número (o PANS-AIM define as casas decimais) ou da exatidão conhecida do cálculo de referência. Exemplo: o comprimento é publicado ao metro e as coordenadas a 0,01", então o calculado pode diferir do publicado em até 0,919 m (0,5 m do arredondamento + 0,419 m do efeito das coordenadas).

**A segurança segue o PANS-AIM.** O documento da ICAO recomenda garantir a integridade com criptografia (2.2.1) e exige consistência entre produtos (2.1.3.2), mas deixa a distribuição em aberto (2.1.4, "*to be developed*"). O E4 testa a primeira; o E5 testa a segunda e ataca a terceira, mostrando que a prova de integridade viaja com os dados e pode ser conferida por quem os recebe. O E6 vai além na terceira: propõe a distribuição (escrita no ledger, leitura por um tópico geral e consumidores, como em CQRS) e testa se ela preserva o que E3 a E5 mostraram.

**A leitura separada (E6).** O ledger é publicado num tópico — o log ordenado do run — e cada consumidor lê tudo, confere hash e elo de cada mensagem, monta do lado dele só o fecho de dependência do que assinou e responde sempre com um limite explícito (um `event_id` ou um instante; não existe "agora"). A carga do eAIP entra no E2 como um grupo de cinco eventos, e o E6 mostra o motivo: o banco, cortado no meio dela, dá ASDA 16 = 2675 m sem acusar nada; o consumidor nunca corta ali. Os ataques ao canal repetem a lógica do E4, agora com o atacante no broker e o banco intocado.

**As verificações foram escritas antes de rodar.** Os `assert` estão no fim do notebook, cada um com o valor esperado, a margem e a origem no comentário. O histórico do git mostra que eles entraram antes da primeira execução.

### Limites declarados

- **O banco registra quem afirmou, mas não prova.** Não há assinatura digital por evento.
- **Quem controla o banco inteiro pode reescrever toda a cadeia;** só uma âncora guardada fora do banco o denuncia (o E4 mostra isso).
- **Nenhum sistema torna uma medição verdadeira.** Se a fonte mede errado, o banco só atribui o erro a quem mediu.
- **Um estudo de caso:** uma pista. A composição de várias pistas é argumentada, não medida.
- **Interoperabilidade entre organizações diferentes** não é testável aqui; o E5 mostra as condições para ela.
- **Quem lê pelo tópico sabe que nada foi alterado, não que recebeu tudo.** Cortar o fim do tópico parece atraso, e um evento falso anexado no fim passa pelo elo; só a âncora detecta (o E6 mostra isso).
- **O tópico é em memória.** O transporte real (Kafka) e o custo em escala não são medidos; tópicos por nó, confidencialidade e mais de um aeroporto ficam argumentados.

---

## Como rodar

Precisa de Python 3.12+ e PostgreSQL 14+ (PostGIS não é necessário).

```sh
git clone https://github.com/heyfalheiro1537/aeroledger_notebook && cd aeroledger_notebook
pip install -r requirements.txt          # instala a biblioteca direto do GitHub

scripts/pg_local.sh                      # PostgreSQL local em localhost:54329
# ou: docker compose up -d

jupyter lab experimentos.ipynb           # e "Run All"
```

Sem interface:

```sh
scripts/rodar.sh                         # executa o notebook e grava as saídas nele
python3 -m pytest -q                     # roda o notebook e os testes do gabarito e do verificador
```

O notebook recria do zero um banco chamado `aeroledger_experimentos` a cada execução. Para outro servidor, defina `AEROLEDGER_DSN_ADMIN` (conexão ao banco `postgres`, com permissão para criar bancos).

## Arquivos

| Arquivo | O que é |
|---|---|
| `experimentos.ipynb` | o notebook: resultados de E1 a E6 e, no fim, as verificações |
| `fontes.py` | os dados do SBSJ, com a fonte de cada um |
| `apoio.py` | funções pequenas usadas pelo notebook (banco, referencial, exportação) |
| `ataques.py` | os ataques do E4 (ao banco) e do E6 (ao tópico) |
| `geodesia.py` | cálculo geodésico de referência (Vincenty), sem a biblioteca |
| `verificador_independente.py` | confere a cadeia e o comprimento a partir do JSON exportado, sem a biblioteca |
| `tests/` | roda o notebook; confere o gabarito no caso publicado de Vincenty; compara a forma canônica do verificador com a da biblioteca |

## Ressalva

Dados do AIP Brasil (DECEA) usados para pesquisa. Nada aqui substitui a publicação oficial.
