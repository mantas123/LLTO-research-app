# 📊 SEM Globali Statistika
### Excel Duomenų Apjungimo ir Bendrosios Analizės Posistemė (`sem_stats_module.py`)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Data Pipeline](https://img.shields.io/badge/Pipeline-Pandas%20%2F%20NumPy-green.svg)](https://pandas.pydata.org/)
[![Math & Stats](https://img.shields.io/badge/Statistics-SciPy%20(KDE%20%2F%20Peaks)-orange.svg)](https://scipy.org/)
[![Reporting](https://img.shields.io/badge/Exporter-OpenPyXL%20%2F%20Matplotlib-blueviolet.svg)](https://openpyxl.readthedocs.io/)

---

**`sem_stats_module.py`** – tai specializuotas programinės įrangos modulis, veikiantis kaip globalus duomenų agregatorius. Jis yra skirtas apjungti individualius mikromorfologinius duomenis (grūdelių parametrus), eksportuotus iš SAM 2.1 ar SAM 3.1 vaizdų analizatorių, ir atlikti apibendrintą kelių skirtingų pavyzdžių (iki 10-ies Excel failų) statistinį vertinimą bei braižyti mokslinės kokybės grafikus.

---

## ⚙️ Pagrindinis Funkcionalumas ir Architektūra

Modulio darbas susideda iš trijų pagrindinių etapų: išmaniojo failų nuskaitymo, statistinio agregavimo bei lietuviškai lokalizuotos grafinės / lentelinės ataskaitos generavimo.

```mermaid
graph TD
    A[Pasirinkti Excel failai 1..10] --> B[1. Stulpelių Sinonimų Identifikavimas]
    A --> C[2. Makro Parametrų Išgavimas per Regex]
    B --> D[3. Mikro Duomenų Apjungimas į Pandas DataFrame]
    C --> E[4. Bendra Mikro & Makro Statistika]
    D --> E
    E --> F[5. Lokalizuotas Matplotlib Visualizer]
    E --> G[6. OpenPyXL Stilizuotas Eksportas]
```

### 1. Išmanusis stulpelių sinonimų žemėlapis (`_COL_SYNONYMS`)
Kadangi skirtingose SAM versijose ar atskiruose tyrimuose Excel stulpelių pavadinimai gali nežymiai skirtis (priklausomai nuo kalbos ar naudotojo konfigūracijos), modulyje įdiegtas lankstus stulpelių atpažinimo žodynas:
*   **diameter**: `equiv. diameter`, `eqdiameter`, `mean diameter`, `diametras`, `equivalent diameter`.
*   **area**: `area`, `plotas`, `grain area`, `area_um2`, `vid. plotas`.
*   **ff (Sferiškumas)**: `circularity`, `form factor`, `sphericity`, `formos faktorius`.
*   **aspect (Anizotropija)**: `aspect ratio`, `anisotropy`, `anizotropija`, `aspect_ratio`.
*   **perimeter**: `perimeter`, `perimetras`, `perimeter_um`.
*   **area_3d**: `area_3d_um2`, `3d area`, `surface area`.
*   **roughness**: `roughness ra`, `ra`, `siurkstumas`, `vid. ra šiurkštumas`.

Sistema automatiškai nuskaito visų įkeltų failų stulpelių antraštes, jas konvertuoja į mažąsias raides, atlieka dalinį teksto palyginimą ir pasiūlo vartotojui automatiškai aptiktus priskyrimus GUI sąsajoje.

### 2. Maksimaliai stabili Makro parametrų paieška (`_find_macro_val`)
Didelė dalis SAM eksportuojamų parametrų (pvz., globalus šiurkštumas Ra, grūdelių ribų tankis) Excel lape yra įrašomi ne stulpeliuose, o specialiose dešiniosios pusės lentelėse arba tam tikruose informaciniuose langeliuose. Kad nuskaitymas būtų 100% stabilus (ir būtų išvengta klaidų, kai pavyzdžiui įkėlus 6 failus statistikoje atvaizduojami tik 4):
*   **Regex paieška per visą matricą**: Funkcija `_find_macro_val` skenuoja visą Excel lapo matricą (kiekvieną stulpelį ir eilutę), ieškodama tikslių parametrų sinonimų.
*   **Tarpų ir taškų ignoravimas**: Naudojamas specialiai sukonstruotas reguliariųjų išraiškų (regex) šablonas:
    ```python
    clean_target = re.escape(target_str).replace(r'\ ', r'\s*').replace(r'\.', r'\.?\s*')
    ```
    Tai reiškia, kad ieškant „Vid. Ra“ bus sėkmingai atpažintas bet kuris iš šių variantų: `Vid Ra`, `Vid.Ra`, `Vid.   Ra`, `vidurkis ra`.
*   **Matavimo vienetų išvalymas**: Suradus vertę sekančiame langelyje, iš teksto pašalinami visi pašaliniai simboliai (pvz., $\mu\text{m}$, $\mu\text{m}^{-1}$), o skaičius paverčiamas grynuoju `float` formatu.

---

## 📈 Statistikos ir Grafikos Variklis

### 1. Mikro ir Makro parametrų atskyrimas
Rezultatai yra suskirstomi į dvi kategorijas, kurios Treeview lentelėje vizualiai išskiriamos skirtingomis spalvomis:
*   🟢 **Mikro parametrai (Žalia spalva)**: Individualūs matavimai, paimti iš kiekvieno grūdelio kaukės atskirai (pvz., kiekvieno grūdelio ekvivalentinis diametras, plotas, sferiškumas). Priklausomai nuo pavyzdžio, bendras grūdelių skaičius ($N$) apjungtame faile gali siekti nuo kelių šimtų iki tūkstančių.
*   🔵 **Makro parametrai (Mėlyna spalva)**: Globalūs pavyzdžio parametrai (pvz., bendras pavyzdžio paviršiaus šiurkštumas $Ra$, grūdelių ribų tankis, lūžio tipas), kurių vertė skaičiuojama kaip vienas skaičius visam failui. Pavyzdžiui, įkėlus 6 failus, šiems parametrams $N = 6$.

### 2. Bimodalė histograma su branduolio tankio (KDE) įverčiu
Spustelėjus mygtuką **„📊 Bimodalė histograma + KDE“**, sukuriamas itin aukštos kokybės grafikas:
*   **Lietuviškų linksnių taikymas**: Kad grafiko antraštės ir ašys skambėtų taisyklingai, programoje dinamiškai atskiriamas vardininkas ašims ir kilmininkas antraštėms.
    *   *Ašis*: Ekvivalentinis diametras, $\mu\text{m}$ (Vardininkas)
    *   *Antraštė*: LLTO grūdelių **ekvivalentinio diametro** pasiskirstymas (Kilmininkas)
*   **Gausinis Branduolio Tankio Įvertis (Gaussian KDE)**: Braižoma tolydi pasiskirstymo kreivė. Glotnumo juostos plotis (bandwidth) parenkamas naudojant *Silverman* taisyklę, kad kreivė nebūtų nei triukšminga, nei per daug nuslopinta.
*   **Automatinė pikų paieška**: Naudojant `scipy.signal.find_peaks`, ant KDE kreivės surandami visi pasiskirstymo pikai (maksimai). Tai leidžia kiekybiškai patvirtinti, ar grūdelių pasiskirstymas yra bimodalus (būdingas netolygiam antriniam grūdelių augimui kietajame elektrolite), ar unimodalus.

---

## 💾 Eksportas į Profesionalų Excel (.xlsx) formatą

Modulyje įdiegta tiesioginė sąveika su **openpyxl** biblioteka, kuri sugeneruoja reprezentacinį rezultatų failą:
1.  **Stilizuoti lakštai (Sheets)**:
    *   `Apibendrinta statistika`: Pagrindinis lapas su gražiai sumaketuotomis mikro ir makro parametrų lentelėmis, vidurkiais, standartiniais nuokrypiais bei $N$ reikšmėmis.
    *   `Apjungti grūdelių duomenys`: Pilnas Pandas DataFrame su visais individualiais tūkstančių grūdelių matavimais, puikiai tinkantis tolesnei mokslinei analizei Origin ar Matlab programose.
2.  **Dizaino elementai**:
    *   **Zebra-striping**: Eilutės nuspalvintos šviesiai pilka ir balta spalvomis, kad duomenis būtų lengva skaityti.
    *   **Automatinis stulpelių plotis**: Programa automatiškai pamatuoja ilgiausią tekstą kiekviename stulpelyje ir nustato optimalų plotį, kad niekas nebūtų paslėpta.
    *   **Spalvinis akcentavimas**: Lentelių antraštės nudažomos tamsiai mėlyna (`#1A237E`) spalva su baltu riebiu (bold) šriftu.
