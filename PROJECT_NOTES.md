# Visby Weather Lab — Project Notes

## 1. Projektets mål

Visby Weather Lab är ett projekt för att bygga en komplett data- och ML-baserad vädertjänst.

Det långsiktiga målet är att kunna svara på:

> Vad blir det för temperatur i Visby imorgon mitt på dagen?

Projektet ska använda historiska observationer från SMHI, lagra data i PostgreSQL och använda maskininlärning för att göra temperaturprognoser.

Planerad teknik:

- React
- Java / Spring Boot
- PostgreSQL
- Python
- scikit-learn
- Docker
- CI/CD
- Azure

Projektet byggs stegvis från rådata till en fungerande, distribuerad tjänst.

---

# 2. Projektets arkitektur

Den långsiktiga riktningen är:

```text
SMHI
  ↓
Data ingestion
  ↓
PostgreSQL
  ↓
Java / Spring Boot API
  ↓
React frontend

Python / ML
  ↓
träning + prognoser
  ↓
PostgreSQL
```

Python används primärt för dataanalys och ML.

Java / Spring Boot ska senare fungera som backend/API mot frontend och databas.

---

# 3. SMHI – datakälla

Projektets primära datakälla är SMHI:s öppna observationsdata.

## Station

Visby Flygplats:

- Station ID: `78400`

Stationen används som projektets primära väderstation.

## Temperatur

- Parameter ID: `1`
- Lufttemperatur
- momentanvärde
- 1 observation per timme

Detta är projektets primära temperaturkälla.

---

# 4. SMHI – API och URL-struktur

Nuvarande observations-API använder URL-strukturen:

```text
https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/{parameter_id}/station/{station_id}/period/{period}/data.{format}
```

Exempel för temperatur från Visby Flygplats:

```text
parameter/1/station/78400/period/corrected-archive/data.csv
```

Perioder som har använts:

- `corrected-archive` — historiskt korrigerat arkiv
- `latest-months`
- `latest-day`
- `latest-hour`

SMHI:s aktuella API-version bör inte antas vara permanent. Projektet bör senare använda SMHI:s katalog/upptäckts-URL för att kunna hitta aktuell API-struktur om versionerade URL:er ändras.

---

# 5. SMHI-parametrar som undersökts

Följande parametrar har identifierats som intressanta för framtida ML-modeller:

| Parameter | ID | Beskrivning |
|---|---:|---|
| Lufttemperatur | 1 | momentanvärde |
| Vindhastighet | 4 | momentanvärde |
| Vindriktning | 3 | momentanvärde |
| Luftfuktighet | 6 | relativ luftfuktighet |
| Lufttryck | 9 | lufttryck |
| Nederbörd | 7 | nederbörd |
| Total molnmängd | 16 | total molnighet |
| Solskenstid | 10 | solsken |
| Byvind | 21 | vindby/maximal vind |
| Daggpunkt | 39 | daggpunktstemperatur |

SMHI-katalogen innehåller även många andra parametrar, exempelvis olika temperatur-, nederbörds-, moln-, sikt-, snö- och vindparametrar.

De ska inte automatiskt läggas till i modellen. Varje feature ska testas och motiveras.

---

# 6. Tidszon

SMHI:s CSV-observationer använder UTC.

Projektet konverterar därför observationerna till svensk lokal tid:

```python
ZoneInfo("Europe/Stockholm")
```

Detta är viktigt eftersom projektets definition av "mitt på dagen" baseras på svensk lokal tid.

Det innebär också att sommar-/vintertid hanteras av tidszonsbiblioteket istället för manuella `+1` / `+2`-beräkningar.

På Windows behövdes `tzdata` för att `ZoneInfo("Europe/Stockholm")` skulle fungera korrekt.

---

# 7. Historisk datatäckning

Temperaturarkivet för station `78400` går tillbaka till:

```text
1945-10-01
```

Den historiska datamängden innehåller cirka:

```text
581 119 temperaturobservationer
```

I den genomförda täckningsanalysen fanns:

```text
29 464 dagar totalt
23 741 dagar med 12:00
27 422 dagar med 12:00 eller 13:00
```

Om endast 12:00 används förloras:

```text
5 723 dagar
```

Med regeln 12:00 → 13:00 som fallback förloras:

```text
2 042 dagar
```

Detta var en viktig anledning till att välja fallback-regeln.

---

# 8. Definition av "mitt på dagen"

Projektet använder följande definition:

1. Försök hitta observationen kl. 12:00.
2. Om 12:00 saknas används 13:00.
3. Om både 12:00 och 13:00 saknas saknas observationen för dagen.

14:00 används inte.

## Varför?

12:00 är den primära och mest naturliga definitionen av mitt på dagen.

13:00 används som fallback eftersom historisk datatäckning förbättras kraftigt.

Beslutet är nu låst och ska användas konsekvent i resten av projektet.

---

# 9. Analys av 12:00 jämfört med 13:00

Vi analyserade dagar där både 12:00 och 13:00 fanns.

Antal dagar:

```text
23 652
```

Genomsnittlig skillnad:

```text
13:00 − 12:00 = +0,16 °C
```

Median:

```text
+0,10 °C
```

13:00 var varmare:

```text
13 056 dagar
```

13:00 var kallare:

```text
8 005 dagar
```

Oförändrat:

```text
2 591 dagar
```

## Absolut temperaturskillnad

| Absolut skillnad | Antal dagar | Andel |
|---|---:|---:|
| ≥ 0,5 °C | 9 472 | 40,05 % |
| ≥ 1,0 °C | 3 588 | 15,17 % |
| ≥ 2,0 °C | 566 | 2,39 % |
| ≥ 3,0 °C | 140 | 0,59 % |
| ≥ 5,0 °C | 19 | 0,08 % |

Detta visar att 13:00 inte är identiskt med 12:00. Skillnaden är ibland betydande, men 12 → 13 ger en bra kompromiss mellan datatäckning och en konsekvent definition.

---

# 10. Viktigt om målvariabeln

Projektets initiala målvariabel är:

> Temperatur mitt på dagen i Visby.

Det innebär i praktiken den observation som väljs enligt:

```text
12:00 → 13:00 fallback
```

Det är viktigt att målvariabeln definieras konsekvent.

Om modellen senare börjar använda exempelvis ett medelvärde mellan 12:00 och 13:00 ska detta betraktas som ett nytt experiment och dokumenteras separat.

---

# 11. Historiskt medelvärde – baseline

Det historiska medelvärdet används som första baseline.

För ett visst kalenderdatum, exempelvis 6 september, hämtas tidigare observationer för samma månad och dag.

Exempel:

```text
Alla tidigare 6 september
        ↓
temperaturer
        ↓
medelvärde
        ↓
baseline prediction
```

Detta är medvetet en mycket enkel modell.

Vi behöver först veta hur bra en enkel metod fungerar innan vi kan avgöra om en ML-modell faktiskt förbättrar resultatet.

---

# 12. Baseline MAE

Baseline har testats på perioden:

```text
2010–2020
```

Resultat:

```text
MAE ≈ 2,78 °C
```

Detta ska användas som referenspunkt när framtida ML-modeller utvärderas.

En mer avancerad modell är inte automatiskt bättre.

Om en ML-modell exempelvis får MAE 2,90 °C är den sämre än baseline, även om modellen tekniskt sett är mycket mer avancerad.

---

# 13. MAE

MAE betyder:

> Mean Absolute Error

Det mäter det genomsnittliga absoluta felet mellan prognos och faktisk temperatur.

Exempel:

```text
Prediction: 15,0 °C
Actual:     17,0 °C

Error:       2,0 °C
```

MAE är lämpligt för projektet eftersom resultatet är lätt att tolka:

```text
MAE = 2,0 °C
```

betyder ungefär att prognosen i genomsnitt ligger 2 grader från det faktiska värdet.

---

# 14. Data leakage

En av projektets viktigaste regler:

> Modellen får bara använda information som fanns tillgänglig vid tidpunkten då prognosen gjordes.

Exempel:

Om vi kl. 13:00 den 8 september gör en prognos för 9 september får modellen inte använda observationer från 9 september.

Det skulle vara data leakage.

Däremot kan observationer från 8 september fram till prognostillfället användas om de är tillgängliga och relevanta.

---

# 15. Train / test split

Eftersom detta är tidsseriedata ska vi inte använda en vanlig slumpmässig train/test-split.

Vi vill simulera verkligheten:

```text
Förfluten tid                     Framtid

2010 ─────────────────── 2023 | 2024 ───── 2025
             TRAIN            |    TEST
```

Modellen tränas på historiska data och testas sedan på senare data som modellen inte har sett.

Detta minskar risken för att testresultatet blir orealistiskt bra.

---

# 16. API-modeller och domänmodeller

En viktig arkitekturprincip:

> API-modellen är inte samma sak som domänmodellen.

SMHI:s JSON-svar ska inte spridas genom hela applikationen.

SMHI kan exempelvis returnera ett komplext objekt med:

- parameter
- station
- metadata
- value
- quality
- tidsinformation

Vår applikation behöver kanske bara:

```python
WeatherObservation(
    timestamp=...,
    temperature=...,
    quality=...,
)
```

Tanken är:

```text
SMHI API response
        ↓
API/data model
        ↓
Domain model
        ↓
Business logic / ML
```

Det gör applikationen mindre beroende av exakt hur SMHI:s API är strukturerat.

---

# 17. Python typing

Vi använder type hints konsekvent.

## Parametrar och returvärden

Exempel:

```python
def fetch_weather_archive(url: str) -> str:
```

Det betyder:

- `url` ska vara en `str`
- funktionen returnerar en `str`

## Listor

```python
def get_midday_observations(
    observations: list[WeatherObservation],
) -> list[WeatherObservation]:
```

## Dictionary

Tidigt i projektet har generella dictionaries använts:

```python
list[dict]
```

Detta är acceptabelt under utforskningen, men när API-lagret blir mer etablerat bör vi använda mer specifika typer.

Exempel:

```python
@dataclass
class SmhiParameter:
    id: int
    name: str
    unit: str
```

eller Pydantic-modeller för externa API-svar.

---

# 18. `None` och saknade värden

Funktioner som kan sakna ett resultat använder:

```python
WeatherObservation | None
```

eller:

```python
float | None
```

Exempel:

```python
def get_midday_observation(...) -> WeatherObservation | None:
```

Det betyder att funktionen kan returnera:

- en `WeatherObservation`
- eller `None`

Det är viktigt att skilja "saknas" från ett faktiskt värde.

Exempelvis är:

```text
0 °C
```

ett giltigt temperaturvärde och får därför inte användas för att representera "ingen data".

---

# 19. SMHI:s kvalitetskod

Observationerna innehåller en kvalitetskod.

Den lagras tillsammans med observationen:

```python
@dataclass
class WeatherObservation:
    timestamp: datetime
    temperature: float
    quality: str
```

Kvalitetsinformationen ska inte ignoreras permanent.

När vi bygger den riktiga databehandlingen behöver vi ta ställning till vilka kvalitetskoder som ska accepteras i ML-datasetet.

---

# 20. Databas

PostgreSQL ska senare lagra historiska observationer och prognoser.

## Weather observations

Planerade fält:

- id
- station
- timestamp
- temperature
- quality
- eventuellt andra väderparametrar

## Predictions

Planerade fält:

- id
- prediction timestamp
- target date/time
- predicted temperature
- model version

## Evaluation

Planerade fält:

- prediction
- actual temperature
- error
- model version
- evaluation timestamp

Gamla observationer och prognoser ska inte raderas.

Historiken behövs för analys och modellutvärdering.

---

# 21. Dagligt arbetsflöde

Det långsiktiga systemet ska ungefär fungera så här.

## Data ingestion

Hämta nya SMHI-observationer och spara dem i databasen.

Detta kan köras flera gånger per dag.

## Daily forecast

Ungefär kl. 13:00:

1. Hämta senaste data.
2. Spara nya observationer.
3. Utvärdera tidigare prognos.
4. Träna om modellen.
5. Skapa prognos för nästa dag.
6. Spara prognosen.

Frontend visar sedan den senaste relevanta prognosen.

---

# 22. Prognoslogik

När dagens data har blivit tillgänglig ska systemet kunna visa:

- vad modellen förutspådde
- vad den historiska normalen är
- vad den faktiska temperaturen blev
- hur stort felet var

Efter midnatt blir nästa dag den nya aktuella target-dagen.

Gamla prognoser och observationer ligger kvar i databasen.

---

# 23. `fit()` och "lära sig över tid"

Scikit-learns:

```python
model.fit(X, y)
```

innebär inte automatiskt incremental learning.

Om modellen tränas med `fit()` tränas den på det dataset som skickas in.

För vårt projekt är det helt okej att modellen varje dag tränas om från början på det ackumulerade datasetet.

Exempel:

```text
Dag 1:
historisk data → train → model

Dag 2:
historisk data + ny data → train → ny model

Dag 3:
historisk data + ännu mer data → train → ny model
```

Detta är den initiala strategin.

Incremental learning kan undersökas senare.

---

# 24. ML-strategi

Vi ska börja enkelt.

Plan:

1. Historiskt medelvärde
2. Naiv persistence-baseline
3. Linear Regression
4. Random Forest
5. Eventuellt Gradient Boosting
6. Jämförelse av modeller

Alla modeller ska jämföras på samma testperiod och med samma huvudsakliga mått:

```text
MAE
```

---

# 25. Features

Möjliga features är bland annat:

- månad
- dag på året
- tidigare temperatur
- historisk temperatur
- vindhastighet
- vindriktning
- lufttryck
- luftfuktighet
- nederbörd
- molnighet
- solskenstid
- daggpunkt

Vi ska inte lägga till alla samtidigt.

Varje feature ska kunna motiveras och testas.

Om en feature inte förbättrar modellen behöver den inte behållas.

---

# 26. Experimentprincip

När vi börjar bygga ML-modeller ska vi dokumentera:

- vilken modell som testades
- vilka features som användes
- vilken träningsperiod som användes
- vilken testperiod som användes
- MAE
- eventuella andra relevanta mått
- slutsats

Exempel:

```text
Model: Linear Regression
Features: day_of_year, previous_temperature
Train: 2010–2023
Test: 2024–2025
MAE: X.XX °C

Resultat:
Bättre/sämre än baseline.
```

På så sätt blir projektet ett riktigt experiment snarare än att vi bara provar modeller på måfå.

---

# 27. Frontend

Frontendens primära fråga:

> Vad blir det för temperatur i Visby imorgon mitt på dagen?

Frontend ska senare kunna visa:

- ML-prognos
- historiskt medel
- historiskt maximum
- historiskt minimum
- faktisk temperatur när dagen har passerat
- prognosens fel
- modellens MAE
- eventuell prognoshistorik

---

# 28. Viktig princip: behåll historiken

Vi ska inte radera data när en ny dag börjar.

Databasen ska behålla:

- historiska observationer
- prognoser
- utvärderingar
- modellversioner

Frontendens aktuella vy kan byta target-dag utan att historisk data påverkas.

Det gör att vi senare kan analysera:

> Hur bra var modellen för tre månader sedan?

och:

> Har modellen blivit bättre över tid?

---

# 29. Nuvarande Python-kod

Den första versionen av Python-koden innehåller funktioner för:

- att hämta SMHI-arkiv
- att hämta SMHI JSON-data
- att hämta SMHI-katalogen
- att parsa temperaturdata
- att konvertera UTC till svensk tid
- att hitta mitt-på-dagen-observation
- att beräkna historiskt medel
- att beräkna baseline MAE

Under den första utvecklingsfasen fanns även flera experiment- och inspektionsfunktioner.

De ska inte ligga kvar i huvudflödet när projektet går vidare.

---

# 30. Städprincip

Vi ska inte refaktorera bara för refaktoreringens skull.

Prioritet:

1. Koden ska vara begriplig.
2. Funktionaliteten ska fungera.
3. Tester ska skydda viktiga funktioner.
4. Sedan går vi vidare.

Vi ska undvika att fastna i små kosmetiska förbättringar när projektet har ett större mål.

---

# 31. Projektets utvecklingsordning

Planerad ordning:

```text
1. Förstå och hämta SMHI-data
2. Strukturera Python-koden
3. Skriva tester
4. PostgreSQL
5. Java / Spring Boot API
6. ML-baseline
7. ML-modeller
8. Modellutvärdering
9. Docker
10. React
11. Integration
12. CI/CD
13. Azure deployment
```

Varje större steg ska fungera innan nästa större steg påbörjas.

---

# 32. Viktiga designbeslut

## Temperaturkälla

SMHI station:

```text
78400 – Visby Flygplats
```

## Temperaturparameter

```text
1 – Lufttemperatur
```

## Målvärde

Temperatur mitt på dagen.

Definition:

```text
12:00 → 13:00 fallback
```

## Historisk baseline

Historiskt medelvärde för samma kalenderdag.

## Utvärderingsmått

Primärt:

```text
MAE
```

## Databas

```text
PostgreSQL
```

## ML

```text
Python + scikit-learn
```

## Backend

```text
Java + Spring Boot
```

## Frontend

```text
React
```

## Deployment

```text
Docker + Azure
```

---

# 33. Saker att undersöka senare

Följande är medvetet inte lösta ännu:

- exakt databasmodell
- migrationsverktyg
- exakt Spring Boot API-design
- hur Python och Java ska kommunicera
- hur ML-modellen ska paketeras/deployas
- modellversionering
- exakt feature engineering
- incremental learning
- hur SMHI:s API ska hanteras vid förändringar
- kvalitetskodernas exakta betydelse för vårt dataset
- hur saknade observationer ska hanteras
- hur ofta nya SMHI-observationer ska hämtas
- hur modellens prestanda ska visualiseras
- eventuell automatiserad retraining
- CI/CD-pipeline
- Azure-arkitektur

Dessa beslut tas när vi kommer till respektive del av projektet.

---

# 34. Nästa steg

Efter denna dokumentation ska vi inte fortsätta refaktorera i onödan.

Nästa konkreta steg är:

> Skriva riktiga tester för de viktigaste Python-funktionerna.

Därefter går vi vidare mot PostgreSQL och börjar bygga den riktiga datadelen av systemet.
