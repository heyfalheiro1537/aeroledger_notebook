# Experimentos — dados aeroportuários auditáveis (SBSJ)

Cinco experimentos com a pista do aeroporto de São José dos Campos (SBSJ) para responder a uma pergunta:

> É possível tornar dados aeroportuários geolocalizados auditáveis — cada valor atribuível, guardado, recalculável a partir das premissas e com adulteração evidente? E onde estão os limites dessa garantia?

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

| | Pergunta | O que o notebook faz | Contra o quê se compara |
|---|---|---|---|
| **E1** | Qual é o problema nas publicações de hoje? | registra a pista "como o AIXM faria" com duas edições oficiais (2022 e 2026) e compara | as próprias publicações |
| **E2** | O número se refaz a partir das premissas? | grava só as cabeceiras e as larguras; calcula comprimento, rumos e distâncias declaradas; depois remede a cabeceira 34 | AIP (AD 2.12 e AD 2.13); um cálculo geodésico em outro código |
| **E3** | Como estava em *t*, quem afirmou e por quê? | reconstrói o estado antes e depois da remedição; registra uma interdição temporária; lê quem afirmou cada coisa e a trilha de auditoria | o roteiro, conhecido de antemão |
| **E4** | Alguém consegue adulterar o banco sem ser visto? | quatro ataques diretos ao banco (alterar, apagar, inserir, reescrever tudo), cada um numa cópia | o que cada ataque deveria provocar |
| **E5** | Dois produtos do mesmo banco podem divergir? A prova é verificável por terceiros? | gera a tabela do AIP e a carta do mesmo banco; exporta os eventos e os confere com um verificador que não usa a biblioteca | PANS-AIM 2.1.3.2 (consistência entre produtos); RFC 8785 |

### Como foram pensados

**Cada experimento responde a uma pergunta que um auditor faria**, e eles seguem uma história: o problema (E1), a solução recalculando os números (E2), a auditoria no tempo (E3), a segurança (E4) e a confiança de quem recebe os dados (E5).

**Os dados são reais.** Premissas e valores de comparação vêm do AIP Brasil (eAIP edição 20-2026, seções AD 2.12 e AD 2.13), da Carta de Aeródromo AIRAC 2604 e da Carta de Obstáculos AIRAC 2213. Só a remedição da cabeceira 34 e a interdição temporária são simuladas, porque não aconteceram de verdade.

**Nada valida a si mesmo.** As coordenadas das cabeceiras entram como premissa; o comprimento, os rumos e as distâncias calculados são comparados com outros campos do AIP, que não entraram no modelo. Onde não há valor publicado (a remedição), a comparação é com o mesmo cálculo feito por outro código (`geodesia.py`, fórmulas de Vincenty).

**As margens não foram escolhidas.** Elas saem da precisão com que o AIP publica cada número (o PANS-AIM define as casas decimais) ou da exatidão conhecida do cálculo de referência. Exemplo: o comprimento é publicado ao metro e as coordenadas a 0,01", então o calculado pode diferir do publicado em até 0,919 m (0,5 m do arredondamento + 0,419 m do efeito das coordenadas).

**A segurança segue o PANS-AIM.** O documento da ICAO recomenda garantir a integridade com criptografia (2.2.1) e exige consistência entre produtos (2.1.3.2), mas deixa a distribuição em aberto (2.1.4, "*to be developed*"). O E4 testa a primeira; o E5 testa a segunda e ataca a terceira, mostrando que a prova de integridade viaja com os dados e pode ser conferida por quem os recebe.

**As verificações foram escritas antes de rodar.** Os `assert` estão no fim do notebook, cada um com o valor esperado, a margem e a origem no comentário. O histórico do git mostra que eles entraram antes da primeira execução.

### Limites declarados

- **O banco registra quem afirmou, mas não prova.** Não há assinatura digital por evento.
- **Quem controla o banco inteiro pode reescrever toda a cadeia;** só uma âncora guardada fora do banco o denuncia (o E4 mostra isso).
- **Nenhum sistema torna uma medição verdadeira.** Se a fonte mede errado, o banco só atribui o erro a quem mediu.
- **Um estudo de caso:** uma pista. A composição de várias pistas é argumentada, não medida.
- **Interoperabilidade entre organizações diferentes** não é testável aqui; o E5 mostra as condições para ela.

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
| `experimentos.ipynb` | o notebook: resultados de E1 a E5 e, no fim, as verificações |
| `fontes.py` | os dados do SBSJ, com a fonte de cada um |
| `apoio.py` | funções pequenas usadas pelo notebook (banco, referencial, exportação) |
| `ataques.py` | os ataques do E4 |
| `geodesia.py` | cálculo geodésico de referência (Vincenty), sem a biblioteca |
| `verificador_independente.py` | confere a cadeia e o comprimento a partir do JSON exportado, sem a biblioteca |
| `tests/` | roda o notebook; confere o gabarito no caso publicado de Vincenty; compara a forma canônica do verificador com a da biblioteca |

## Ressalva

Dados do AIP Brasil (DECEA) usados para pesquisa. Nada aqui substitui a publicação oficial.
