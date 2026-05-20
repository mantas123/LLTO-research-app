<div align="center">
<img src="logo.png" width="300" alt="CeraMIS Logo">
    
### Ceramic Microstructure & Impedance System
#### **Keramikos Mikrostruktūros ir Impedanso Sistema**
</div>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/UI-Tkinter%20%2F%20Matplotlib-orange.svg)](https://docs.python.org/3/library/tkinter.html)
[![AI Segmentation](https://img.shields.io/badge/AI-Segment%20Anything%20(SAM%202.1%20%2F%203.1)-red.svg)](https://github.com/facebookresearch/segment-anything-2)
[![3D Rendering](https://img.shields.io/badge/3D%20Engine-PyVista%20%2F%20VTK-blueviolet.svg)](https://docs.pyvista.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

---

> [!NOTE]
> **English speakers:** For the English version of the documentation, please see **[README_ENG.md](README_ENG.md)**.

**CeraMIS** – tai programinė įranga, skirta Ličio Lantano Titanato (**LLTO**) kietųjų elektrolitų kompleksinei impedanso spektroskopijos (EIS), relaksacijos trukmės pasiskirstymo (DRT), struktūrinės 3D perovskitų simuliacijos ir SEM mikrostruktūros dirbtinio intelekto analizei.

Programa apjungia mašininio mokymosi algoritmus (Meta SAM 2.1 / 3.1) su klasikiniais elektrocheminiais ir kristalografiniais modeliais. Visa sistema (įskaitant išorinius modulius ir 3D vizualizatorius) yra pilnai pritaikyta lietuvių ir anglų kalboms.

---

## 🗺️ Sistemos Moduliai ir Funkcionalumas

Programa yra padalinta į **8 specializuotus modulius (korteles)**, apimančius visą kietojo kūno elektrolitų tyrimo eigą:

```mermaid
graph TD
    A[Eksperimentiniai EIS Duomenys] --> B[1. EIS Analizė]
    A --> C[2. Lanko Pločio Analizė]
    B --> D[3. Arenijaus Dėsnis]
    B --> E[4. DRT Spektroskopija]
    F[SEM Mikrografijos] --> G[5. SEM AI Segmentacija]
    G --> H[6. SEM Globali Statistika]
    I[Kristalografiniai Parametrai] --> J[7. 3D Kristalo Simuliatorius]
```

### 1. 📈 EIS Analizė (Elektrocheminė Impedanso Spektroskopija)
*   **3x3 Grafinė Matrica**: Vienu metu atvaizduojami 9 skirtingi fizikiniai grafikai pasirinktinai iš 16 galimų tipų (Nyquist, Bode, dielektrinė skvarba, laidumas, modulis, Summerfield ir kt.).
*   **Geometrinis Normalizavimas**: Automatinis matavimų perskaičiavimas į specifinius vienetus įvertinant bandinio geometriją – storį ($L$) ir plotą ($A$).
*   **Palaikomi Formatai**: Tiesioginis eksperimentinių `.txt`, ZView `.z` bei kelių lapų Excel `.xlsx` failų importas.

> [!TIP]
> Detalų EIS modulių aprašymą rasite dokumente: **[README_EIS_PLOTS.md](README_EIS_PLOTS.md)**.

### 2. 🌀 Lanko Pločio Analizė
*   Interaktyvus impedanso puslankių pločio ir jų charakteringųjų dažnių identifikavimas Cole-Cole erdvėje.
*   Vizualus skirtingų laidumo mechanizmų (tūrinio, grūdelių ribų ir poliarizacijos) atskyrimas.

> [!TIP]
> Detalų lanko analizės modulio aprašymą rasite dokumente: **[README_ARC_WIDTH.md](README_ARC_WIDTH.md)**.

### 3. 🌡️ Arenijaus Analizė (Arenijaus dėsnis)
*   **Aktyvacijos Energijos ($E_{a}$) Skaičiavimas**: Automatinis tiesinis parametrų derinimas naudojant $\sigma T = \sigma_{0} \exp\left(-\frac{E_{a}}{k_{B} T}\right)$ sąryšį.
*   **Komponentų Išskyrimas**: Atskiras tūrinio laidumo (Bulk), grūdelių ribų (Grain Boundary) bei pilno laidumo (Total) aktyvacijos energijų (eV) skaičiavimas.
*   **Išmanus Redagavimas**: Interaktyvus taškų įtraukimas / pašalinimas iš regresijos, momentinis $R^2$ ir $E_{a}$ perskaičiavimas bei kelių regresijų overlay grafike.

> [!TIP]
> Detalų Arenijaus modulio aprašymą rasite dokumente: **[README_ARRHENIUS.md](README_ARRHENIUS.md)**.

### 4. ⚡ DRT Analizė (Relaxation Time Distribution)
*   **Aukštos raiškos analizė**: Persidengiančių impedanso puslankių atskyrimas ir analizė laiko (dažnių) skalėje.
*   **Pikų integravimas**: Poliarizacijos varžos ($R$) ir efektyviosios talpos ($C$) skaičiavimas naudojant skaitinę Simpsono integraciją.
*   **Automatinė paieška**: Automatinis viršūnių bei valley rėžių nustatymas ir integravimas.

> [!TIP]
> Detalų DRT modulio aprašymą rasite dokumente: **[README_DRT.md](README_DRT.md)**.

### 5. 🤖 SEM Analizė (AI / SAM 2.1 & 3.1)
*   **Segment Anything Model (SAM)**: Automatinis kietojo elektrolito grūdelių (grains) aptikimas ir kontūrų segmentavimas SEM mikrografijose su Meta SAM 2.1 arba SAM 3.1.
*   **3D Reljefo Rekonstrukcija**: Pilna 3D paviršiaus topografijos vizualizacija naudojant PyVista (VTK pagrindu). Gylis ($z$) rekonstruojamas pagal pilkumo skalės intensyvumą.
*   **Skilimo Analizė**: Kiekybinis lūžio topologijos įvertinimas (Intergranuliarinis vs Transgranuliarinis skilimas) skaičiuojant gylio skirtumus grūdelių viduje ir jų sandūrose.
*   **Šiurkštumo Parametrai**: Kiekvieno grūdelio bei globalaus paviršiaus Ra ir Rq šiurkštumo charakteristikų skaičiavimas.

> [!TIP]
> Detalų dirbtinio intelekto modelio aprašymą rasite dokumente: **[README_SAM.md](README_SAM.md)**.

### 6. 📊 SEM Globali Statistika
*   **Multi-failų Apjungimas**: Apjungia iki 10 Excel failų grūdelių morfologijos matavimus.
*   **Morfologinė Analizė**: Ekvivalentinio diametro, ploto, sferiškumo, anizotropijos, perimetro, 3D ploto bei šiurkštumo pasiskirstymo kreivės.
*   **Bimodalė histogama + KDE**: Automatinė unimodalių / bimodalių pasiskirstymo pikų analizė.

> [!TIP]
> Detalų SEM statistikos modulio aprašymą rasite dokumente: **[README_SEM_STATS.md](README_SEM_STATS.md)**.

### 7. 💎 3D Kristalo Simuliatorius
*   **LLTO Perovskito Struktūra**: Li<sub>3x</sub>La<sub>2/3-x</sub>TiO<sub>3</sub> perovskito gardelės vizualizacija su koordinaciniais oktaedrais.
*   **Ličio Jonų Transporto Simuliacija**: Elektrinio lauko valdomas realaus laiko Li<sup>+</sup> jonų šokinėjimas tarp vakansijų su periodinėmis ribinėmis sąlygomis.
*   **Grūdelių Ribos ir Langai**: Dviejų skirtingai orientuotų kristalinių sričių sujungimas (dvyniai) bei deguonies langų (O<sub>4</sub> transporto kanalų) vizualizavimas.

> [!TIP]
> Detalų kristalo simuliatoriaus modulio aprašymą rasite dokumente: **[README_CRYSTAL.md](README_CRYSTAL.md)**.

### 8. ⚙️ Nustatymai (Settings)
*   **Kalbos Pasirinkimas (Language Selection)**: Vartotojo sąsajos kalbos pasirinkimas (`en` / `lt`). Pakeitus kalbą, visi pagrindiniai moduliai bei išoriniai procesai (SAM segmentavimo korektoriai, 3D PyVista rodytuvai) bus automatiškai išversti.
*   **Programos Mastelis (GUI Scale)**: Lanksus mastelio koeficientas (`0.75x` iki `2.0x`), leidžiantis pritaikyti programos dydį ir tekstų šriftus prie skirtingos monitorių raiškos (pvz., 4K ekranų) bei sisteminių Windows mastelio nustatymų.
*   **SEM AI Modelio Pasirinkimas**: Galimybė nustatymų lange lengvai pasirinkti tarp **SAM 2.1** bei **SAM 3.1** dirbtinio intelekto modelio versijų.
*   **Numatytieji Keliai (Default Paths & Files)**: Automatinis nurodytų failų / katalogų užkrovimas ir failų pasirinkimo langų (file dialogs) pradžios katalogo nustatymas:
    *   **EIS spektro failas** (`default_spectrum_file`).
    *   **dearEIS JSON projektas** (`default_deareis_project`).
    *   **SEM nuotraukų aplankas** (`default_sem_folder`).
    *   **SEM statistikos aplankas** (`default_sem_stats_folder`).

---

## 🛠️ Reikalavimai ir Įdiegimas

Programai paleisti reikalinga **Python 3.11+** versija ir CUDA palaikymas vaizdo plokštėje (rekomenduojama greitam AI kaukės generavimui).

### 1. Virtualios aplinkos paruošimas
```powershell
# Klonuokite arba nukopijuokite projektą į savo aplanką
cd CeraMIS

# Sukurkite virtualią aplinką
python -m venv .venv

# Aktyvuokite aplinką (Windows)
.venv\Scripts\activate
```

### 2. Priklausomybių įdiegimas
Įdiekite visas reikalingas bibliotekas:
```powershell
pip install numpy scipy pandas matplotlib seaborn pyvista pyvistaqt openpyxl lmfit torch torchvision opencv-python PyQt6
```

### 3. Dirbtinio intelekto svorių (Weights) įkėlimas
Norint naudoti SEM AI segmentaciją, į projekto šakninį katalogą būtina įkelti modelio svorius:
*   SAM 3.1 Multiplex modelis: `sam3.1_multiplex.pt` (įkeliamas į pagrindinį aplanką)
*   SAM 2.1 Hiera modelis: `sam2.1_hiera_large.pt` (jei naudojama SAM 2 versija)

---

## 🚀 Programos Paleidimas

Aktyvavę virtualią aplinką, paleiskite pagrindinį failą:

```powershell
python "main CeraMIS.py"
```

> [!NOTE]
> Paleidus programą, ji automatiškai patikrins, ar nurodytuose keliuose yra numatytieji LLTO duomenų failai (`.xlsx` impedanso duomenys ir `.json` dearEIS projektas). Jei failai nerandami, juos galima lengvai įkelti rankiniu būdu per grafinę sąsają naudojant mygtukus **„📂 Pasirinkti failą...“** arba **„📂 Įkelti [dearEIS](https://github.com/vyrjana/DearEIS) projektą...“**.

---

## ⚖️ Licencija ir Autorinės Teises

*   **Programinės įrangos autorius**: Mantas Jonas Marcinkevičius
*   **Licencija**: Licensed under the Apache License, Version 2.0 (see [LICENSE](LICENSE)).
