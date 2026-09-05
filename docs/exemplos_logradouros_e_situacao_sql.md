# Anomalias de Logradouros e o Campo "Situação do SQL"

> **Documentação Complementar de Engenharia de Dados**  
> **Base Analisada:** `GUIAS DE ITBI PAGAS (27082026) XLS.xlsx` (135.655 registros de 2026).

---

## 1. Exemplos Reais de Ruas Preenchidas Incorretamente / Anômalas

Embora o campo `Nome do Logradouro` venha automaticamente do cadastro do IPTU da PMSP, o cadastro histórico da cidade de São Paulo acumula particularidades, siglas de projetos habitacionais e truncamentos:

### A. Códigos e Siglas Internas Embutidos no Nome da Rua
Em conjuntos habitacionais da CDHU, COHAB e loteamentos de interesse social (CHIS), o cadastro oficial da prefeitura inclui o código do projeto entre parênteses:

| SQL | Nome do Logradouro na Planilha | Número | Bairro na Planilha | O que realmente significa |
| :--- | :--- | :---: | :--- | :--- |
| `3915200311` | **`PS SEM DENOMINACAO (VMN)`** | `99999` | VILA MARIANA | *Passagem Sem Denominação* na Vila Mariana (rua sem nome oficial). |
| `11738100676` | **`PS SEM DENOMINACAO (SAP)`** | `153` | VL CARVALHO SANTOS | *Passagem Sem Denominação* em Sapopemba. |
| `16723901011` | **`R SEM DENOMINACAO (CRE)`** | `580` | COHAB ADVENTISTA | *Rua Sem Denominação* no Caxingui / Rio Pequeno. |
| `15709625018` | **`R UM (CHIS SACOMA A)`** | `250` | TORRE B - LOTE 3 | *Rua Um* no Conjunto Habitacional de Interesse Social Sacomã A. |
| `19703900061` | **`R B (PI. TOMAS EDSON-BFU)`** | `500` | PACAEMBU | *Rua B* no Projeto Integrado Tomas Edson - Barra Funda. |
| `21601000055` | **`R A (CJH. JD. DAMASCENO-JAR)`** | `99999` | AV DEP C SAMPAIO 4822 | *Rua A* no Conjunto Habitacional Jardim Damasceno - Jaraguá. |
| `18811503311` | **`AL DAS PITANGUEIRAS (SEGUNDO TRECHO)`** | `176` | CJ RES ALPES DO JARAGU | Observação de fase da obra ("SEGUNDO TRECHO") virou nome de rua. |
| `20112000035` | **`R CIRCULAR (CHIS BUTANTA D)`** | `471` | — | *Rua Circular* no CHIS Butantã D. |

---

### B. O Caso Crítico: O Endereço Inteiro Foi Parar no Campo `Bairro`
Na linha **6.964 de Janeiro/2026** (SQL `21601000055`), ocorreu um deslocamento grave de preenchimento cadastral:
* **Logradouro:** `R A (CJH. JD. DAMASCENO-JAR)`
* **Número:** `99999`
* **Bairro Cadastrado:** **`AV DEP C SAMPAIO 4822`** ⚠️
* *Diagnóstico:* O cadastrador inseriu a via principal de acesso e a numeração predial (*Avenida Deputado Cantídio Sampaio, 4822*) dentro da coluna destinada ao Bairro.

---

### C. Abreviações Severas do IPTU (Que Quebram Buscas Textuais Comuns)
Para caber em sistemas de mainframe com limite de caracteres, a PMSP abreviou nomes históricos. Uma busca exata sem normalização falha:

* `AV CDSSA ELISABETH DE ROBIANO` (em vez de *Avenida Condessa Elisabeth de Robiano*).
* `AV DRA RUTH CARDOSO` (em vez de *Avenida Doutora Ruth Cardoso*).
* `R CAP JOSE INACIO DO ROSARIO` (em vez de *Rua Capitão José Inácio do Rosário*).
* `R CEL JOAO DENTE` (em vez de *Rua Coronel João Dente*).
* `AV PRES WILSON` (em vez de *Avenida Presidente Wilson*).

---

## 2. O que significa o campo: `Situação do SQL`?

O campo **`Situação do SQL`** informa o estado da inscrição do imóvel no **Cadastro Imobiliário Fiscal da Prefeitura de São Paulo** perante o IPTU no momento da extração.

### Os 5 Status Possíveis e Seus Significados:

| Status na Planilha | Ocorrências em JUL-2026 | Significado Urbanístico e Fiscal |
| :--- | :---: | :--- |
| **`Ativo Predial`** | **17.355** (76,9%) | **Imóvel construído e regularizado.** Existe uma edificação averbada (casa, apartamento, loja, galpão) com Habite-se ou notificação de lançamento de IPTU predial. |
| **`Ativo Territorial`** | **4.315** (19,1%) | **Terreno vago ou obra em andamento.** Não há construção concluída averbada perante a prefeitura. Paga imposto territorial urbano. |
| **`Cancelado Predial`** | **421** (1,9%) | **Construção que foi demolida ou desdobrada.** Acontece quando uma casa antiga foi demolida para dar lugar a um prédio novo, ou quando salas comerciais foram unificadas. O SQL antigo foi baixado. |
| **`Cancelado Territorial`** | **350** (1,6%) | **Gleba/Lote original que deixou de existir.** Ocorre quando um grande terreno foi loteado ou fracionado em dezenas de novos lotes fiscais (desdobro/desmembramento). |
| **`Não_Existe_Exercício`** | **119** (0,5%) | O SQL existia em exercícios anteriores ou foi cancelado antes do ano corrente, não tendo lançamento ativo de IPTU no ano vigente da extração. |

---

### 3. Como o `Situação do SQL` é Usado no Radar da Moradia

No pipeline do projeto (`radar/carga/mineracao.py`), esse campo desempenha **duas funções de segurança vitais**:

#### 1. Detecção de Colunas Deslocadas (`linha_deslocada`)
Na nossa auditoria, descobrimos que em **Fevereiro, Março e Abril de 2026**, exatamente uma linha por mês teve colunas escorregadas para a direita. Nesses casos, o campo `Situação do SQL` recebeu um valor do tipo **`datetime.date`** (que era, na verdade, a data da transação que deslizou de coluna).  
A regra do projeto pega isso imediatamente:
```python
if isinstance(situacao_sql_bruto, (dt.datetime, dt.date)):
    return True  # Linha descartada ou marcada com qualidade ruim
```

#### 2. Identificação de Imóveis na Planta (`flag_cadastro_defasado`)
Quando alguém compra um apartamento novo em condomínio que ainda não teve o desdobro de IPTU concluído pela prefeitura:
* A transação é de um apartamento pronto ou na planta (via *Minha Casa Minha Vida* ou *SFH*);
* Mas o SQL informado ainda consta com a situação **`Ativo Territorial`** (terreno da obra) e `Área Construída = 0`.
* Isso permite ao Radar saber que o IPTU está defasado em relação à realidade do imóvel negociado.
