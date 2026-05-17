import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors
from matplotlib.cm import ScalarMappable
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import os
import re
import traceback
from datetime import datetime
from lmfit import minimize, Parameters
from scipy.interpolate import interp1d
from mpl_toolkits.mplot3d import Axes3D
import time
import subprocess
import tempfile
import json
import random
from pathlib import Path
from math import pi, sqrt, log, isnan, isinf
from scipy import stats
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
from scipy.integrate import simpson
from scipy.signal import find_peaks

GRAPH_TYPES = {
    "Z' vs f": "Z_real_f",
    "-Z'' vs f": "Z_imag_f",
    "ε' vs f": "eps_real_f",
    "ε'' vs f": "eps_imag_f",
    "σ' vs f": "sigma_f",
    "M'' vs f": "M_imag_f",
    "tan δ vs f": "tan_delta_f",
    "Norm. Z'' ir M'' vs f": "norm_z_m_f",
    "Z''/Z''max vs f": "norm_z_f",
    "M''/M''max vs f": "norm_m_f",
    "Summerfield skalavimas": "summerfield",
    "Pseudo-DRT (-dZ'/dlogf)": "pseudo_drt",
    "Naikvisto grafikas": "nyquist",
    "Pilnutinė varža (|Z|) vs f": "abs_Z_f",
    "Fazės kampas (-Θ) vs f": "phase_f",
    "Z' ir -Z'' vs f": "z_real_imag_f",
    "Bodė grafikas (|Z| ir -Θ)": "bode_dual",
    "Cole-Cole grafikas (ε' vs ε'')": "cole_cole",
}

# --- KONFIGŪRACIJA ---
FILE_PATH = r"C:\Users\bigma\OneDrive\BAKALAURAS fiz\4 KURSAS\Bakalauras\rezultatai\LLTO visos sutvarkytos temperaturos pilname spektre.xlsx"
AUTHOR = "Mantas Jonas Marcinkevičius"
DEFAULT_PROJECT_PATH = r"C:/Users/bigma/OneDrive/BAKALAURAS fiz/4 KURSAS/Bakalauras/rezultatai/dearEIS LLTO nuo 145k iki 1060K.json"
EPSILON_0 = 8.85418782e-12 
EPS_0_SI = 8.854187817e-14  # F/cm

# --- TERMINĖS PALETĖS (Custom Thermal Colormaps - Clipped to avoid black/white) ---
IRONBOW_COLORS = ['#100060', '#500080', '#b03060', '#e07040', '#f0b000']
ARCTIC_COLORS  = ['#000080', '#0000ff', '#0080ff', '#00ffff']
ironbow_cmap = mcolors.LinearSegmentedColormap.from_list('ironbow', IRONBOW_COLORS)
arctic_cmap  = mcolors.LinearSegmentedColormap.from_list('arctic', ARCTIC_COLORS)
def to_sci_unicode(value, decimals=2):
    """Konvertuoja skaičių į 10ⁿ formatą su Unicode laipsniais ir kableliu."""
    if abs(value) < 1e-25: return "0"
    s = ("{:.%dE}" % decimals).format(value)
    base, exp = s.split('E')
    base = base.replace('.', ',')
    exp_int = int(exp)
    superscripts = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻','+':''}
    unicode_exp = "".join(superscripts.get(c, c) for c in str(exp_int))
    return f"{base}·10{unicode_exp}"

# ─── ARENIJAUS PAGALBINĖS FUNKCIJOS ─────────────────────────────────────────

def _find_element_keys(parameters: dict, element_type: str):
    pattern = re.compile(r"^" + re.escape(element_type) + r"_\d+$", re.IGNORECASE)
    return sorted([k for k in parameters.keys() if pattern.match(k)])

def _extract_element_params(parameters: dict, element_key: str):
    result = {}
    if element_key in parameters:
        for pk, pdata in parameters[element_key].items():
            val = pdata.get("value", float("nan"))
            err = pdata.get("stderr", float("nan"))
            result[pk] = (val, float("nan") if err is None else err)
    return result

def calc_c_eff(R, Q, n):
    if any(isnan(x) or isinf(x) for x in [R, Q, n]) or R <= 0 or Q <= 0 or n <= 0:
        return float("nan")
    try:
        return (Q * R ** (1 - n)) ** (1 / n)
    except Exception:
        return float("nan")

def calc_eps_r(C_eff, L_cm, A_cm2):
    if isnan(C_eff) or C_eff <= 0:
        return float("nan")
    return C_eff * L_cm / (EPS_0_SI * A_cm2)

def calc_sigma(R_total, L_cm, A_cm2):
    if isnan(R_total) or R_total <= 0:
        return float("nan")
    return L_cm / (R_total * A_cm2)

def parse_temp_arr(label: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*[kK](?!\w)", label)
    if m: return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:°C|degC|C\b)", label)
    if m: return float(m.group(1)) + 273.15
    m = re.search(r"(\d{3,4}(?:\.\d+)?)", label)
    if m:
        val = float(m.group(1))
        if 100 <= val <= 2000: return val
    return float("nan")

def load_dear_project(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_all_r_keys(project: dict) -> list:
    keys = set()
    for fit_list in project.get("fits", {}).values():
        for fit in fit_list:
            for rk in _find_element_keys(fit.get("parameters", {}), "R"):
                keys.add(rk)
    return sorted(keys)

def get_fit_labels(project: dict) -> dict:
    result = {}
    ds_by_uuid = {ds["uuid"]: ds.get("label", ds["uuid"])
                  for ds in project.get("data_sets", [])}
    for uuid, fit_list in project.get("fits", {}).items():
        ds_label = ds_by_uuid.get(uuid, uuid)
        entries = []
        for i, fit in enumerate(fit_list):
            cdc = fit.get("circuit_description_code", "?")
            label = fit.get("label", "") or f"Fit #{i+1}"
            entries.append((i, f"#{i+1} [{cdc}] {label}"))
        if entries:
            result[uuid] = entries
    return result

def extract_fit_data(project: dict, L_cm: float, A_cm2: float,
                     r_keys_selected: list, fit_index: str = "last") -> pd.DataFrame:
    data_sets = project.get("data_sets", [])
    fits_by_data = project.get("fits", {})
    rows = []
    for ds in data_sets:
        ds_uuid = ds.get("uuid", "")
        ds_label = ds.get("label", "")
        T_K = parse_temp_arr(ds_label)
        fit_list = fits_by_data.get(ds_uuid, [])
        if not fit_list: continue
        
        if fit_index == "last": fit = fit_list[0]
        elif fit_index == "first": fit = fit_list[-1]
        else:
            try:
                idx = int(fit_index)
                fit = fit_list[min(idx, len(fit_list) - 1)]
            except (ValueError, IndexError):
                fit = fit_list[0]

        parameters = fit.get("parameters", {})
        R_vals, R_errs = [], []
        for rk in r_keys_selected:
            params = _extract_element_params(parameters, rk)
            R_val, R_err = params.get("R", (float("nan"), float("nan")))
            R_vals.append(R_val)
            R_errs.append(R_err)

        if R_vals and not any(isnan(v) for v in R_vals):
            R_total = sum(R_vals)
            R_total_err = sqrt(sum(e**2 for e in R_errs if not isnan(e)))
        else:
            R_total = R_total_err = float("nan")

        sigma = calc_sigma(R_total, L_cm, A_cm2)
        sigma_err = (sigma * (R_total_err / R_total)
                     if not isnan(sigma) and not isnan(R_total_err) and R_total > 0
                     else float("nan"))
        ln_sT = (log(sigma * T_K) if not isnan(sigma) and sigma > 0 and T_K > 0
                 else float("nan"))
        ln_sT_err = (sigma_err / sigma if not isnan(sigma) and sigma > 0 and not isnan(sigma_err)
                     else float("nan"))

        row = {
            "Dataset": ds_label, "T_K": T_K, "ds_uuid": ds_uuid,
            "1000/T": 1000.0 / T_K if T_K > 0 else float("nan"),
            "R_total (Ohm)": R_total, "R_total_err (Ohm)": R_total_err,
            "Sigma (S/cm)": sigma, "Sigma_err (S/cm)": sigma_err,
            "ln(Sigma*T)": ln_sT, "ln_err": ln_sT_err,
        }
        for rk, R_val, R_err in zip(r_keys_selected, R_vals, R_errs):
            row[f"{rk}_R (Ohm)"] = R_val
            row[f"{rk}_R_err (Ohm)"] = R_err

        q_keys = _find_element_keys(parameters, "Q")
        for i, qk in enumerate(q_keys, 1):
            q_params = _extract_element_params(parameters, qk)
            Q_val, Q_err = q_params.get("Q", (float("nan"), float("nan")))
            n_val, n_err = q_params.get("n", (float("nan"), float("nan")))
            row[f"{qk}_Q"] = Q_val
            row[f"{qk}_n"] = n_val
            matched_R = R_vals[i-1] if i <= len(R_vals) else float("nan")
            C_eff = calc_c_eff(matched_R, Q_val, n_val)
            row[f"{qk}_C_eff (F)"] = C_eff
            row[f"{qk}_eps_r"] = calc_eps_r(C_eff, L_cm, A_cm2)
        rows.append(row)

    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values("T_K").reset_index(drop=True)
    return df

def format_comma(value, decimals=2, add_degree=False):
    """Konvertuoja float į dešimtainį su kableliu."""
    res = ("{:." + str(decimals) + "f}").format(value).replace('.', ',')
    return f"{res}°" if add_degree else res

def parse_complex(s):
    try: return complex(s.strip('()').replace(' ', ''))
    except: return 0j

def format_freq_with_units(f):
    """Konvertuoja dažnį į skaitomą formatą su vienetais."""
    if f >= 1e9: return f"{f/1e9:.3f} GHz"
    if f >= 1e6: return f"{f/1e6:.3f} MHz"
    if f >= 1e3: return f"{f/1e3:.3f} kHz"
    return f"{f:.3f} Hz"

def parse_freq_with_units(s):
    """Konvertuoja tekstą su vienetais atgal į float (Hz)."""
    if not s: return None
    try:
        parts = s.split()
        val = float(parts[0].replace(',', '.'))
        if len(parts) < 2: return val
        unit = parts[1].lower()
        if 'ghz' in unit: return val * 1e9
        if 'mhz' in unit: return val * 1e6
        if 'khz' in unit: return val * 1e3
        return val
    except:
        return None

class LLTOComprehensiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Duomenų valdymas - {AUTHOR}")
        self.root.geometry("1300x1450")
        self.center_window(self.root, 1300, 1450)
        
        # Set tick direction to 'in' globally
        plt.rcParams['xtick.direction'] = 'in'
        plt.rcParams['ytick.direction'] = 'in'
        plt.rcParams['xtick.top'] = True
        plt.rcParams['ytick.right'] = True

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_arr = ttk.Frame(self.notebook)
        self.tab_drt = ttk.Frame(self.notebook)
        self.tab_fit = ttk.Frame(self.notebook)
        self.tab_arc = ttk.Frame(self.notebook)
        self.tab_sem = ttk.Frame(self.notebook)
        self.tab_sem_stats = ttk.Frame(self.notebook)
        self.tab_crystal = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="EIS Analizė")
        self.notebook.add(self.tab_arc, text="Lanko pločio analizė")
        self.notebook.add(self.tab_arr, text="Arenijaus analizė")
        self.notebook.add(self.tab_drt, text="DRT Analizė")
        self.notebook.add(self.tab_fit, text="Modeliavimas")
        self.notebook.add(self.tab_sem, text="SEM Analizė (AI)")
        self.notebook.add(self.tab_sem_stats, text="📊 SEM Statistika")
        self.notebook.add(self.tab_crystal, text="💎 3D Kristalas")

        self.frequencies, self.data_dict, self.vars = [], {}, {}
        self.t_min_var = tk.StringVar(value="")
        self.t_max_var = tk.StringVar(value="")
        self.fitted_params = {}
        self.fitted_curves = {}
        
        self.f_min_var = tk.StringVar(value="")
        self.f_max_var = tk.StringVar(value="")
        
        # Bandinio geometrija (numatytoji pagal naudotoją: 1.5 mm ir 0.51 mm²)
        self.thickness_var = tk.StringVar(value="1.5")
        self.area_var = tk.StringVar(value="0.51")
        self.is_normalized_var = tk.BooleanVar(value=True)
        
        # DRT būsena
        self.drt_state = {'project': None, 'ds_list': []}
        self.drt_tau_min_var = tk.StringVar()
        self.drt_tau_max_var = tk.StringVar()
        self.drt_ds_var = tk.StringVar()
        self.drt_results_var = tk.StringVar(value='(pasirinkite datasetą ir rėžius)')
        self._drt_saved_peaks = [] # Čia saugosime išsaugotus pikus
        
        # Arenijaus būsena
        self.arr_state = {'project': None, 'all_r_keys': [], 'fit_labels': {}}
        self._arr_df_cache = [None]
        self._arr_point_selected = {}
        self._arr_saved_lines = []
        
        # SEM Statistikos posistemės būsena
        self.sem_stats_state = {
            'files': [],          # Įkeltų failų sąrašas (iki 7)
            'file_labels': [],    # Failų etiketės GUI
            'raw_dfs': [],        # DataFrame sąrašas po nuskaitymo
            'combined_df': None,  # Apjungtas DataFrame
            'results': {},        # Skaičiavimų rezultatai
        }
        self.sem_col_vars = {}    # Stulpelių priskyrimo StringVar kintamieji
        
        self.current_file_var = tk.StringVar(value="Nepasirinktas joks failas")
        self.current_filepath = FILE_PATH
        self.click_count = 0
        self.last_click_time = 0
        self.right_click_count = 0
        self.last_right_click_time = 0

        self.setup_gui()
        self.setup_arrhenius_tab()
        self.setup_drt_tab()
        self.setup_sem_stats_tab()

        if os.path.exists(self.current_filepath):
            self.load_file(self.current_filepath)
            
        self.load_default_project()

    def open_file_dialog(self):
        filetypes = (
            ("Palaikomi failai", "*.txt *.z *.xlsx"),
            ("Tekstiniai failai", "*.txt"),
            ("ZView failai", "*.z"),
            ("Excel failai", "*.xlsx"),
            ("Visi failai", "*.*")
        )
        filepath = filedialog.askopenfilename(title="Atidaryti failą", filetypes=filetypes)
        if filepath:
            self.load_file(filepath)

    def load_file(self, filepath):
        try:
            self.frequencies = []
            self.data_dict = {}
            self.vars = {}
            self.fitted_curves = {}
            self.current_filepath = filepath
            
            ext = os.path.splitext(filepath)[1].lower()
            
            if ext == '.xlsx':
                xls = pd.ExcelFile(filepath)
                first_freqs = None
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    if 'Freq (Hz)' in df.columns and 'Z_real' in df.columns and 'Z_imag' in df.columns:
                        freqs = df['Freq (Hz)'].values
                        z_vals = df['Z_real'].values + 1j * df['Z_imag'].values
                        
                        # Išvalome tarpus ir kablelius, kad teisingai nuskaitytume pvz. '1059. 9K'
                        clean_name = sheet_name.replace(" ", "").replace(",", ".")
                        match = re.search(r"(\d+(?:\.\d+)?)", clean_name)
                        temp = float(match.group(1)) if match else 298.0
                        
                        if first_freqs is None:
                            first_freqs = freqs
                        self.data_dict[temp] = (np.array(freqs), np.array(z_vals))
                if first_freqs is not None:
                    self.frequencies = np.array(first_freqs)
                    
            elif ext == '.z':
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                freqs = []
                z_vals = []
                for line in lines:
                    parts = [p.strip() for p in line.split(',') if p.strip()]
                    if len(parts) >= 6:
                        try:
                            freq = float(parts[0])
                            z_real = float(parts[4])
                            z_imag = -float(parts[5]) # Atstatome -Z'' į Z_imag
                            freqs.append(freq)
                            z_vals.append(z_real + 1j * z_imag)
                        except ValueError:
                            continue
                if freqs:
                    temp = 298.0 # Default
                    clean_name = os.path.basename(filepath).replace(" ", "").replace(",", ".")
                    match = re.search(r"(\d+(?:\.\d+)?)", clean_name)
                    if match: temp = float(match.group(1))
                    
                    self.frequencies = np.array(freqs)
                    self.data_dict[temp] = (self.frequencies, np.array(z_vals))
                    
            else: # .txt ar kt. numatytasis
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                data_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
                if data_lines:
                    freq_row = [f for f in data_lines[0].replace('\t', '  ').split('  ') if f]
                    self.frequencies = np.array([parse_complex(f).real for f in freq_row[1:]])
                    
                    for line in data_lines[1:]:
                        parts = [p for p in line.replace('\t', '  ').split('  ') if p]
                        if parts:
                            clean_part = parts[0].replace(" ", "").replace(",", ".")
                            temp = round(parse_complex(clean_part).real, 2)
                            self.data_dict[temp] = (self.frequencies, np.array([parse_complex(v) for v in parts[1:]]))
                            
            self.current_file_var.set(os.path.basename(filepath))
            self.update_gui_after_load()
            
        except Exception as e:
            messagebox.showerror("Klaida skaitant failą", f"Klaida: {e}")

    def center_window(self, win, w, h):
        """Centruoja langą ekrane, apribojant pagal ekrano dydį."""
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        
        # Apribojame plotį ir aukštį, kad neviršytų ekrano
        w = min(w, int(sw * 0.95))
        h = min(h, int(sh * 0.9))
        
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        return w, h

    def setup_gui(self):
        tk.Label(self.tab_main, text="LLTO Spektroskopija", font=('Arial', 12, 'bold')).pack(pady=10)
        tk.Label(self.tab_main, text=f"Autorius: {AUTHOR}", fg="#555").pack()
        
        file_frame = tk.Frame(self.tab_main)
        file_frame.pack(pady=5, fill="x", padx=20)
        tk.Button(file_frame, text="📂 Pasirinkti failą...", command=self.open_file_dialog, bg="#E0E0E0").pack(side="left")
        tk.Label(file_frame, textvariable=self.current_file_var, fg="blue", wraplength=250, justify="left").pack(side="left", padx=10)
        
        # --- KONFIGŪRACIJOS KONTEINERIS (Grafikai + Geometrija) ---
        config_container = tk.Frame(self.tab_main)
        config_container.pack(pady=5, padx=20, fill="x")

        # --- GRAFIKŲ KONFIGŪRACIJA ---
        graph_frame = tk.LabelFrame(config_container, text="Grafikų išdėstymas (3x3 matrica)", padx=10, pady=10)
        graph_frame.pack(side="left", fill="both", expand=True)
        
        self.graph_vars = [tk.StringVar() for _ in range(9)]
        default_graphs = [
            "Z' vs f", "-Z'' vs f", "ε' vs f",
            "Naikvisto grafikas", "Pilnutinė varža (|Z|) vs f", "Fazės kampas (-Θ) vs f",
            "ε'' vs f", "σ' vs f", "M'' vs f"
        ]
        
        for i, default in enumerate(default_graphs):
            self.graph_vars[i].set(default)
            row = i // 3
            col = i % 3
            cb = ttk.Combobox(graph_frame, textvariable=self.graph_vars[i], width=20, state="readonly")
            cb['values'] = list(GRAPH_TYPES.keys())
            cb.grid(row=row, column=col, padx=5, pady=2)

        # --- GEOMETRIJA (Šone, 1x2 stiliaus lentelė) ---
        geo_frame = tk.LabelFrame(config_container, text="Bandinio geometrija", padx=15, pady=10)
        geo_frame.pack(side="right", fill="y", padx=(10, 0))
        
        tk.Label(geo_frame, text="Storis L (mm):", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(geo_frame, textvariable=self.thickness_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(geo_frame, text="Plotas A (mm²):", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(geo_frame, textvariable=self.area_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        tk.Checkbutton(geo_frame, text="Duomenys jau normalizuoti (Ω·m)", 
                       variable=self.is_normalized_var, bg='#f0f0f0', font=('Arial', 9)).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10,0))

        # --- TEMPERATŪRŲ ŽYMĖJIMAS ---
        selection_frame = tk.Frame(self.tab_main)
        selection_frame.pack(pady=5)
        tk.Button(selection_frame, text="Pažymėti viską", command=self.select_all).pack(side="left", padx=5)
        tk.Button(selection_frame, text="Atžymėti visus", command=self.deselect_all).pack(side="left", padx=5)

        # --- DIAPAZONŲ KONTEINERIS ---
        range_container = tk.Frame(self.tab_main)
        range_container.pack(pady=5, padx=20, fill="x")

        # --- TEMPERATŪRŲ ŽYMĖJIMAS IR DIAPAZONAS ---
        temp_range_frame = tk.LabelFrame(range_container, text="Temperatūrų diapazonas (K)", padx=5, pady=5)
        temp_range_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(temp_range_frame, text="Nuo:").pack(side="left")
        self.t_min_combo = ttk.Combobox(temp_range_frame, textvariable=self.t_min_var, width=8)
        self.t_min_combo.pack(side="left", padx=5)

        tk.Label(temp_range_frame, text="Iki:").pack(side="left")
        self.t_max_combo = ttk.Combobox(temp_range_frame, textvariable=self.t_max_var, width=8)
        self.t_max_combo.pack(side="left", padx=5)
        
        if len(self.data_dict) > 0:
            temps = [str(t) for t in sorted(self.data_dict.keys())]
            self.t_min_combo['values'] = temps
            self.t_max_combo['values'] = temps

        tk.Button(temp_range_frame, text="Pasirinkti", command=self.select_temp_range).pack(side="left", padx=5)

        # --- FILTRACIJA (Dažnių intervalas) ---
        filter_frame = tk.LabelFrame(range_container, text="Dažnių intervalas (Hz)", padx=5, pady=5)
        filter_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        tk.Label(filter_frame, text="Nuo:").pack(side="left")
        self.f_min_combo = ttk.Combobox(filter_frame, textvariable=self.f_min_var, width=10)
        self.f_min_combo.pack(side="left", padx=2)
        
        tk.Label(filter_frame, text="Iki:").pack(side="left")
        self.f_max_combo = ttk.Combobox(filter_frame, textvariable=self.f_max_var, width=10)
        self.f_max_combo.pack(side="left", padx=2)


        container = tk.Frame(self.tab_main, highlightbackground="#CCCCCC", highlightthickness=1, bd=0)
        canvas = tk.Canvas(container, width=380, height=350, highlightthickness=0)
        self.temp_list_canvas = canvas
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Slenkamas ratukas tiesiogiai ant konteinerio elementų
        canvas.bind("<MouseWheel>", self._on_temp_list_mousewheel)
        canvas.bind("<Button-4>", self._on_temp_list_mousewheel)
        canvas.bind("<Button-5>", self._on_temp_list_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", self._on_temp_list_mousewheel)
        self.scrollable_frame.bind("<Button-4>", self._on_temp_list_mousewheel)
        self.scrollable_frame.bind("<Button-5>", self._on_temp_list_mousewheel)
        
        container.pack(expand=True, fill="both", padx=20)
        canvas.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")
        
        btn_frame = tk.Frame(self.tab_main)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="📈 Analizuoti spektrus", command=self.open_plot, 
                  bg="#2E7D32", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text="🚀 3D Analizė", command=self.open_3d_plots, 
                  bg="#9C27B0", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text="⚡ Greitaveikis 3D grafikas (GPU)", command=self.open_fast_3d_plot, 
                  bg="#E64A19", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text="🗺️ Individualus grafikas", command=self.open_custom_plot, 
                  bg="#00695C", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text="📊 Eksportuoti į Excel (.xlsx)", command=self.export_excel, 
                  bg="#1B5E20", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text="📂 Eksportuoti ZView (.z)", command=self.export_zview, 
                  bg="#0D47A1", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)

        # ── Modeliavimo skirtuko turinys ──────────────────────────────────
        fit_top = ttk.Frame(self.tab_fit, padding=20)
        fit_top.pack(fill="both", expand=True)
        tk.Label(fit_top, text="Grandinės Modeliavimas", font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(fit_top, text="Pasirinkite grandinės tipą ir paspauskite 'Derinti modelį'.",
                 fg="#555").pack()
        fit_frame = tk.LabelFrame(fit_top, text="Modeliavimas", padx=15, pady=15)
        fit_frame.pack(pady=20, padx=40, fill="x")
        self.circuit_var = tk.StringVar(value="R-RQ-RQ-Q")
        self.circuit_combo = ttk.Combobox(fit_frame, textvariable=self.circuit_var, width=20)
        self.circuit_combo['values'] = ("R-RC", "R-RQ", "R-RQ-RQ", "R-RQ-W")
        self.circuit_combo.pack(side="left", padx=5)
        tk.Button(fit_frame, text="Derinti modelį", command=self.fit_data,
                  bg="#F57C00", fg="white", font=('Arial', 10, 'bold'), relief="raised", bd=3, padx=15).pack(side="left", padx=10)
        # Laikinai paslėptas – funkcijos išlieka
        self.notebook.hide(self.tab_fit)

        # ── Lanko Pločio skirtuko turinys ──────────────────────────────────
        arc_top = ttk.Frame(self.tab_arc, padding=20)
        arc_top.pack(fill="both", expand=True)
        tk.Label(arc_top, text="Lanko Pločio Skaičiavimas", font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(arc_top, text="Skaičiuoja Naikvisto kreivės lanko plotį bei varžą.",
                 fg="#555").pack()
        tk.Button(arc_top, text="📏 Skaičiuoti lanko plotį (R)", command=self.show_arc_width_info,
                  bg="#FF8F00", fg="white", font=('Arial', 11, 'bold'), width=35, relief="raised", bd=3).pack(pady=30)

        # ── SEM Analizės skirtuko turinys ──────────────────────────────────
        sem_top = ttk.Frame(self.tab_sem, padding=20)
        sem_top.pack(fill="both", expand=True)
        tk.Label(sem_top, text="SEM Mikrostruktūros Analizė (AI)",
                 font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(sem_top,
                 text=("Naudoja SAM 2 (Segment Anything Model 2) automatiniam grūdelių segmentavimui\n"
                       "ir išgaunamą 2D+3D morfologinę statistiką (diametras, sferiškumas, \n"
                       "anizotropija, ribų tankis, šiurkštumas Ra, lūžio topologijos indeksas)."),
                 fg="#444", justify="center").pack(pady=5)
        tk.Button(sem_top, text="🔬 Paleisti SEM Analizę (AI)", command=self.open_sam_analyzer,
                  bg="#4527A0", fg="white", font=('Arial', 11, 'bold'), width=35, relief="raised", bd=3).pack(pady=30)
                  
        # ── Kristalų Struktūros skirtuko turinys ──────────────────────────────────
        cryst_top = ttk.Frame(self.tab_crystal, padding=20)
        cryst_top.pack(fill="both", expand=True)
        tk.Label(cryst_top, text="LLTO Kristalų Struktūra (3D)",
                 font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(cryst_top,
                 text=("Interaktyvi 3D vizualizacija, skirta LLTO perovskito struktūrai.\n"
                       "Palaikomas nepertraukiamas Li jonų šuolių animavimas, \n"
                       "stechiometrijos konfigūravimas ir fazių (Cubic/Tetragonal) perjungimas."),
                 fg="#444", justify="center").pack(pady=5)
        tk.Button(cryst_top, text="💎 Paleisti 3D Kristalų Vizualizaciją", command=self.open_crystal_viewer,
                  bg="#6A1B9A", fg="white", font=('Arial', 11, 'bold'), width=35, relief="raised", bd=3).pack(pady=30)
        
    def update_gui_after_load(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        def get_sort_key(k):
            try:
                # Ištraukiame pirmą skaičių iš bet kokio formato (pvz. '1059. 9K')
                s = str(k).replace(',', '.').replace(' ', '')
                match = re.search(r"(\d+(?:\.\d+)?)", s)
                if match:
                    return float(match.group(1))
                return float(k)
            except:
                return 0.0
            
        for temp in sorted(self.data_dict.keys(), key=get_sort_key):
            var = tk.BooleanVar()
            cb = tk.Checkbutton(self.scrollable_frame, text=f"{temp:g} K", variable=var)
            cb.pack(anchor='w', padx=60)
            cb.bind("<MouseWheel>", self._on_temp_list_mousewheel)
            cb.bind("<Button-4>", self._on_temp_list_mousewheel)
            cb.bind("<Button-5>", self._on_temp_list_mousewheel)
            self.vars[temp] = var
            
        if len(self.frequencies) > 0:
            formatted_freqs = [format_freq_with_units(f) for f in sorted(self.frequencies)]
            self.f_min_combo['values'] = formatted_freqs
            self.f_max_combo['values'] = formatted_freqs
            self.f_min_combo.set(formatted_freqs[0])
            self.f_max_combo.set(formatted_freqs[-1])
            
        if len(self.data_dict) > 0:
            temps = [str(t) for t in sorted(self.data_dict.keys(), key=get_sort_key)]
            self.t_min_combo['values'] = temps
            self.t_max_combo['values'] = temps
            self.t_min_combo.set(temps[0])
            self.t_max_combo.set(temps[-1])

    def _on_temp_list_mousewheel(self, event):
        if not hasattr(self, 'temp_list_canvas') or not self.temp_list_canvas:
            return
        if event.num == 4:
            self.temp_list_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.temp_list_canvas.yview_scroll(1, "units")
        else:
            self.temp_list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def select_all(self):
        for var in self.vars.values():
            var.set(True)

    def deselect_all(self):
        for var in self.vars.values():
            var.set(False)

    def select_temp_range(self):
        try:
            t_min = float(self.t_min_var.get())
            t_max = float(self.t_max_var.get())
            for temp, var in self.vars.items():
                if t_min <= temp <= t_max:
                    var.set(True)
                else:
                    var.set(False)
        except ValueError:
            messagebox.showwarning("Klaida", "Įveskite teisingas temperatūras!")

    def _get_geometric_factors(self):
        """Grąžina L/A ir A/L faktorius (SI vienetais: m ir m²)."""
        if self.is_normalized_var.get():
            return 1.0, 1.0
        try:
            L_mm = float(self.thickness_var.get())
            A_mm2 = float(self.area_var.get())
            
            L_m = L_mm * 1e-3
            A_m2 = A_mm2 * 1e-6
            
            if L_m <= 0 or A_m2 <= 0: return 1.0, 1.0
            
            return L_m / A_m2, A_m2 / L_m
        except (ValueError, ZeroDivisionError):
            return 1.0, 1.0

    def get_filtered_data(self, temp):
        """Grąžina dažnius ir duomenis pagal pasirinktą intervalą."""
        f, z = self.data_dict[temp]
        
        try:
            f_min_val = parse_freq_with_units(self.f_min_var.get())
            f_max_val = parse_freq_with_units(self.f_max_var.get())
            
            f_min = f_min_val if f_min_val is not None else -np.inf
            f_max = f_max_val if f_max_val is not None else np.inf
        except Exception:
            f_min, f_max = -np.inf, np.inf
            
        mask = (f >= f_min) & (f <= f_max)
        return f[mask], z[mask]

    def eval_custom_circuit(self, circuit_str, params, w):
        elements = [el.strip().upper() for el in circuit_str.split('-') if el.strip()]
        Z_total = 0
        for i, el in enumerate(elements):
            if el == 'R': Z_total += params[f'R_{i}']
            elif el == 'Q': Z_total += 1 / (params[f'Q_{i}'] * (w * 1j)**params[f'n_{i}'])
            elif el == 'RQ':
                R_v, Q_v, n_v = params[f'R_{i}'], params[f'Q_{i}'], params[f'n_{i}']
                Z_total += 1 / (1/R_v + Q_v * (w * 1j)**n_v)
        return Z_total

    def fit_data(self):
        selected = [t for t, v in self.vars.items() if v.get()]
        if not selected: return
        circuit = self.circuit_var.get().strip().upper()
        elements = [el.strip() for el in circuit.split('-') if el.strip()]
        f, w = self.frequencies, 2 * np.pi * self.frequencies

        def residual(params, w, z_exp, circuit_str):
            z_sim = self.eval_custom_circuit(circuit_str, params, w)
            return np.concatenate(((z_sim.real - z_exp.real) / np.abs(z_exp), 
                                   (z_sim.imag - z_exp.imag) / np.abs(z_exp)))

        for temp in selected:
            f, z = self.get_filtered_data(temp)
            if len(f) == 0: continue
            w = 2 * np.pi * f
            
            params = Parameters()
            for i, el in enumerate(elements):
                if 'R' in el: params.add(f'R_{i}', value=100, min=1e-3)
                if 'Q' in el: 
                    params.add(f'Q_{i}', value=1e-10, min=1e-15)
                    params.add(f'n_{i}', value=0.9, min=0.5, max=1.0)
            
            minimize(residual, params, args=(w, z, circuit))
            self.fitted_curves[temp] = (f, self.eval_custom_circuit(circuit, params, w))
        messagebox.showinfo("Sėkmė", "Modelis priderintas!")

    # ─── ARENIJAUS ANALIZĖS METODAI ──────────────────────────────────────────

    def setup_arrhenius_tab(self):
        # UI kintamieji
        self.arr_project_path_var = tk.StringVar()
        self.arr_status_var = tk.StringVar(value='Laukiama projekto...')
        self.arr_fit_mode_var = tk.StringVar(value='last')
        self.arr_fit_index_var = tk.StringVar(value='0')
        self.arr_fit_info_var = tk.StringVar(value='(ikelkite projektą)')
        self.arr_ea_label_var = tk.StringVar(value='')
        self.arr_reg_params = [None, None]
        self.arr_point_info_var = tk.StringVar(value='Spauskite tašką info')
        self.arr_r_check_vars = {}

        # Pagrindinis konteineris
        main_arr_f = ttk.Frame(self.tab_arr, padding=20)
        main_arr_f.pack(fill=tk.BOTH, expand=True)

        # --- Nustatymai ---
        pf = ttk.LabelFrame(main_arr_f, text='DearEIS projekto failas (.json)', padding=10)
        pf.pack(fill=tk.X, pady=5)
        ttk.Entry(pf, textvariable=self.arr_project_path_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(pf, text='Naršyti...', command=self.browse_dear_project, bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=6)

        fit_f = ttk.LabelFrame(main_arr_f, text='Fitting rezultato pasirinkimas', padding=10)
        fit_f.pack(fill=tk.X, pady=5)
        rb_f = ttk.Frame(fit_f)
        rb_f.pack(fill=tk.X)
        ttk.Radiobutton(rb_f, text='Paskutinis', variable=self.arr_fit_mode_var, value='last').pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(rb_f, text='Pirmas', variable=self.arr_fit_mode_var, value='first').pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(rb_f, text='Pagal indeksą:', variable=self.arr_fit_mode_var, value='index').pack(side=tk.LEFT, padx=6)
        ttk.Entry(rb_f, textvariable=self.arr_fit_index_var, width=5).pack(side=tk.LEFT)
        ttk.Label(fit_f, textvariable=self.arr_fit_info_var, foreground='#555', font=('Segoe UI', 8), wraplength=700).pack(anchor=tk.W, padx=4, pady=2)

        self.arr_r_outer = ttk.LabelFrame(main_arr_f, text='R komponentai (pažymėkite kurie sudaro R_total)', padding=10)
        self.arr_r_outer.pack(fill=tk.X, pady=5)
        self.arr_r_inner = ttk.Frame(self.arr_r_outer)
        self.arr_r_inner.pack(fill=tk.X)
        ttk.Label(self.arr_r_inner, text='(ikelkite projektą)').pack()

        ttk.Label(main_arr_f, textvariable=self.arr_status_var, foreground='#1565C0', font=('Segoe UI', 10, 'bold')).pack(pady=10)

        btn_f = ttk.Frame(main_arr_f)
        btn_f.pack(pady=20)
        tk.Button(btn_f, text='📉 Braižyti Arenijaus grafiką', command=self.draw_arrhenius_plot,
                  bg="#2E7D32", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_f, text='📊 Eksportuoti CSV', command=self.export_arrhenius_csv,
                  bg="#1565C0", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_f, text='💾 Įrašyti projektą', command=self.save_arrhenius_project,
                  bg="#D84315", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)

        self._arr_scatter_sel = None
        self._arr_scatter_unsel = None
        self._arr_reg_line = None
        self._arr_saved_artists = []
        self._arr_active_idx = None
        self._arr_active_marker = None

    def browse_dear_project(self):
        p = filedialog.askopenfilename(
            title='Pasirinkite DearEIS projektą',
            filetypes=[('DearEIS projektas', '*.json'), ('Visi failai', '*.*')]
        )
        if not p: return
        self.arr_project_path_var.set(p)
        try:
            proj = load_dear_project(p)
            self.arr_state['project'] = proj
            self.arr_state['all_r_keys'] = get_all_r_keys(proj)
            self.arr_state['fit_labels'] = get_fit_labels(proj)
            self._refresh_arr_r_checkboxes()
            self._refresh_arr_fit_info()
            n_ds = len(proj.get('data_sets', []))
            self.arr_status_var.set(f'Projektas įkeltas. Datasetai: {n_ds}')
            # Atnaujiname DRT rezultatus ir parodome sėkmės pranešimą, nes failas įkeltas rankiniu būdu
            self._refresh_drt_datasets(show_popup=True)
        except Exception as e:
            messagebox.showerror('Klaida', f'Nepavyko įkelti projekto:\n{e}')

    def _refresh_arr_fit_info(self):
        fl = self.arr_state['fit_labels']
        if not fl:
            self.arr_fit_info_var.set('(nėra fitting rezultatų)')
            return
        first_uuid = next(iter(fl))
        entries = fl[first_uuid]
        lines = ['  - ' + desc for _, desc in entries[:5]]
        if len(entries) > 5: lines.append(f'  ... ir dar {len(entries)-5}')
        self.arr_fit_info_var.set('Fitting rezultatai (pirmas datasetas):\n' + '\n'.join(lines))

    def _refresh_arr_r_checkboxes(self):
        for w in self.arr_r_inner.winfo_children(): w.destroy()
        self.arr_r_check_vars.clear()
        keys = self.arr_state['all_r_keys']
        if not keys:
            ttk.Label(self.arr_r_inner, text='(ikelkite projektą)').pack()
            return
        for i, rk in enumerate(keys):
            var = tk.BooleanVar(value=True)
            self.arr_r_check_vars[rk] = var
            ttk.Checkbutton(self.arr_r_inner, text=rk, variable=var).grid(row=0, column=i, padx=8, pady=2, sticky=tk.W)

    def load_default_project(self):
        """Automatiškai įkelia numatytąjį projektą, jei jis egzistuoja."""
        if os.path.exists(DEFAULT_PROJECT_PATH):
            self.arr_project_path_var.set(DEFAULT_PROJECT_PATH)
            try:
                proj = load_dear_project(DEFAULT_PROJECT_PATH)
                self.arr_state['project'] = proj
                self.arr_state['all_r_keys'] = get_all_r_keys(proj)
                self.arr_state['fit_labels'] = get_fit_labels(proj)
                self._refresh_arr_r_checkboxes()
                self._refresh_arr_fit_info()
                n_ds = len(proj.get('data_sets', []))
                self.arr_status_var.set(f'Projektas įkeltas (automatiškai). Datasetai: {n_ds}')
                # Užkraunant automatiškai pradiniame ekrane, DRT pranešimo nerodome
                self._refresh_drt_datasets(show_popup=False)
            except Exception:
                pass

    # ─── DRT ANALIZĖS METODAI ────────────────────────────────────────────────

    def setup_drt_tab(self):
        main_f = ttk.Frame(self.tab_drt, padding=20)
        main_f.pack(fill=tk.BOTH, expand=True)

        # 1. Projekto pasirinkimas
        pf = ttk.LabelFrame(main_f, text='DearEIS projekto failas (bendras su Arenijaus skirtuku)', padding=10)
        pf.pack(fill=tk.X, pady=5)
        ttk.Label(pf, textvariable=self.arr_project_path_var, font=('Segoe UI', 8), foreground='#555', wraplength=800).pack(fill=tk.X, expand=True)
        tk.Button(pf, text='🔄 Atnaujinti datasetų sąrašą iš projekto', command=self._refresh_drt_datasets, 
                  bg="#E0E0E0", relief="raised", bd=2).pack(pady=5)

        # 2. Dataseto pasirinkimas
        ds_f = ttk.LabelFrame(main_f, text='Pasirinkite temperatūrą (Datasetą)', padding=10)
        ds_f.pack(fill=tk.X, pady=5)
        self.drt_ds_combo = ttk.Combobox(ds_f, textvariable=self.drt_ds_var, state='readonly', width=50)
        self.drt_ds_combo.pack(side=tk.LEFT, padx=5)
        
        # 3. Piko rėžiai
        lim_f = ttk.LabelFrame(main_f, text='Piko ribos integracijai (neprivaloma)', padding=10)
        lim_f.pack(fill=tk.X, pady=5)
        ttk.Label(lim_f, text='tau min (s):').grid(row=0, column=0, padx=5)
        ttk.Entry(lim_f, textvariable=self.drt_tau_min_var, width=15).grid(row=0, column=1, padx=5)
        ttk.Label(lim_f, text='tau max (s):').grid(row=0, column=2, padx=5)
        ttk.Entry(lim_f, textvariable=self.drt_tau_max_var, width=15).grid(row=0, column=3, padx=5)
        ttk.Label(lim_f, text='(palikite tuščia automatiniam radimui)', font=('Segoe UI', 8, 'italic')).grid(row=0, column=4, padx=10)

        # 4. Rezultatai
        res_f = ttk.LabelFrame(main_f, text='Rezultatai', padding=10)
        res_f.pack(fill=tk.X, pady=10)
        ttk.Label(res_f, textvariable=self.drt_results_var, font=('Segoe UI', 11, 'bold'), foreground='#2E7D32').pack()

        # 5. Mygtukai
        btn_f = ttk.Frame(main_f)
        btn_f.pack(pady=20)
        tk.Button(btn_f, text='📈 Analizuoti ir braižyti DRT', command=self.run_drt_analysis,
                  bg="#2E7D32", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(pady=5)
        
        tk.Button(btn_f, text='🗺️ Braižyti 3D DRT (T vs f)', command=self.plot_3d_drt,
                  bg="#1565C0", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(pady=5)

    def _refresh_drt_datasets(self, show_popup=True):
        proj = self.arr_state['project']
        if not proj:
            if show_popup:
                messagebox.showwarning("Dėmesio", "Pirmiausia įkelkite projektą Arenijaus skirtuke.")
            return
        
        self.drt_state['ds_list'] = []
        labels = []
        for ds in proj.get('data_sets', []):
            uuid = ds.get('uuid')
            # Tikriname ar šis datasetas turi DRT duomenis
            tau, _ = self._extract_drt_from_json(proj, uuid)
            if tau is not None and len(tau) > 0:
                label = ds.get('label', uuid)
                self.drt_state['ds_list'].append((uuid, label))
                labels.append(label)
        
        self.drt_ds_combo['values'] = labels
        if labels: 
            self.drt_ds_combo.current(0)
            if show_popup:
                messagebox.showinfo("Sėkmė", f"Rasta datasetų su DRT rezultatais: {len(labels)}")
        else:
            self.drt_ds_var.set('')
            self.drt_ds_combo['values'] = []
            if show_popup:
                messagebox.showwarning("Dėmesio", "Projekte nerasta jokių DRT rezultatų. Atlikite DRT skaičiavimą dearEIS programoje.")

    def run_drt_analysis(self):
        proj = self.arr_state['project']
        if not proj:
            messagebox.showerror("Klaida", "Nėra įkelto projekto.")
            return
        
        ds_idx = self.drt_ds_combo.current()
        if ds_idx < 0:
            messagebox.showwarning("Dėmesio", "Pasirinkite datasetą.")
            return
        
        uuid, label = self.drt_state['ds_list'][ds_idx]
        
        # 1. Ištraukiame DRT duomenis
        tau, gamma = self._extract_drt_from_json(proj, uuid)
        if tau is None or len(tau) == 0:
            messagebox.showerror("Klaida", f"Datasetas '{label}' neturi DRT rezultatų dearEIS faile.")
            return

        # 2. Nuskaitome rėžius
        tmin = tmax = None
        try:
            if self.drt_tau_min_var.get().strip(): tmin = float(self.drt_tau_min_var.get())
            if self.drt_tau_max_var.get().strip(): tmax = float(self.drt_tau_max_var.get())
        except ValueError:
            messagebox.showerror("Klaida", "Neteisingi tau rėžiai.")
            return

        # 3. Atliekame analizę (integracija R = ∫ gamma d(ln(tau)))
        ln_tau = np.log(tau)
        if tmin is not None and tmax is not None:
            mask = (tau >= tmin) & (tau <= tmax)
        else:
            # Automatinis piko radimas
            peaks, _ = find_peaks(gamma, height=np.max(gamma)*0.1)
            if len(peaks) == 0:
                messagebox.showwarning("Dėmesio", "Nepavyko automatiškai rasti piko. Nurodykite rėžius rankiniu būdu.")
                return
            peak_idx = peaks[np.argmax(gamma[peaks])]
            # Piko papėdės radimas
            thresh = gamma[peak_idx] * 0.05
            start = peak_idx
            while start > 0 and gamma[start] > thresh: start -= 1
            end = peak_idx
            while end < len(gamma)-1 and gamma[end] > thresh: end += 1
            mask = np.zeros_like(gamma, dtype=bool)
            mask[start:end+1] = True

        t_slice = tau[mask]
        g_slice = gamma[mask]
        ln_t_slice = ln_tau[mask]

        if len(t_slice) < 3:
            messagebox.showwarning("Dėmesio", "Per mažai taškų nurodytame rėžyje.")
            return

        R = simpson(y=g_slice, x=ln_t_slice)
        tau_p = t_slice[np.argmax(g_slice)]
        C = tau_p / R if R != 0 else 0
        
        self.drt_results_var.set(f"R = {R:.4f} Ω  |  C = {C:.4E} F  |  τ_p = {tau_p:.2E} s")

        # 4. Braižome grafiką
        self._plot_drt_popup(tau, gamma, label)

    def _parse_temp(self, label):
        match = re.search(r"(\d+\.?\d*)", label)
        return float(match.group(1)) if match else 0.0

    def plot_3d_drt(self):
        proj = self.arr_state['project']
        if not proj:
            messagebox.showerror("Klaida", "Nėra įkelto projekto.")
            return
            
        drt_data = []
        for uuid, label in self.drt_state['ds_list']:
            tau, gamma = self._extract_drt_from_json(proj, uuid)
            if tau is not None and len(tau) > 0:
                temp = self._parse_temp(label)
                # Dažnis f = 1 / (2 * pi * tau)
                freqs = 1.0 / (2 * np.pi * tau)
                drt_data.append((temp, freqs, gamma))
        
        if not drt_data:
            messagebox.showwarning("Dėmesio", "Nerasta jokių DRT duomenų projekte.")
            return

        # Rūšiuojame pagal temperatūrą
        drt_data.sort(key=lambda x: x[0])
        
        # Sukuriame bendrą log-dažnių ašį interpoliacijai
        all_f = np.concatenate([d[1] for d in drt_data])
        f_min, f_max = np.min(all_f), np.max(all_f)
        f_grid = np.geomspace(f_min, f_max, 200)
        log_f_grid = np.log10(f_grid)
        
        X_vals, Y_vals, Z_vals = [], [], []
        for temp, f_vals, g_vals in drt_data:
            # Rūšiuojame pagal dažnį (interp1d reikalauja didėjančio x)
            idx = np.argsort(f_vals)
            f_s, g_s = f_vals[idx], g_vals[idx]
            
            f_interp = interp1d(np.log10(f_s), g_s, bounds_error=False, fill_value=0)
            g_interp = f_interp(log_f_grid)
            
            X_vals.append(log_f_grid)
            Y_vals.append([temp] * len(log_f_grid))
            Z_vals.append(g_interp)
            
        X = np.array(X_vals)
        Y = np.array(Y_vals)
        Z = np.array(Z_vals)
        
        # Braižome 3D
        sw = tk.Toplevel(self.root)
        sw.title("3D DRT Žemėlapis")
        self.center_window(sw, 1400, 1001) # Pradinis +1px layoutui
        
        fig = Figure(figsize=(12, 9), dpi=100, facecolor='white')
        ax = fig.add_subplot(111, projection='3d')
        surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none', alpha=0.9, antialiased=True)
        
        ax.set_xlabel('log₁₀(f), Hz', labelpad=15, rotation=0)
        ax.set_ylabel('Temperatūra, K', labelpad=15, rotation=0)
        ax.set_zlabel('γ(ln τ), Ω', labelpad=15, rotation=90)
        ax.xaxis.set_rotate_label(False)
        ax.yaxis.set_rotate_label(False)
        ax.zaxis.set_rotate_label(False)
        ax.set_title("DRT pasiskirstymas nuo temperatūros ir dažnio", pad=20, fontweight='bold')
        
        
        # Pridinis pasukimas geresniam vaizdui
        ax.view_init(elev=30, azim=-120)
        
        # Toolbaras ir Canvas
        tb_frame = tk.Frame(sw)
        tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        canvas = FigureCanvasTkAgg(fig, master=sw)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar = NavigationToolbar2Tk(canvas, tb_frame)
        toolbar.update()
        
        canvas.mpl_connect('button_press_event', self.on_plot_click)
        
        sw.update()
        self.center_window(sw, 1400, 1001) # Pirmas šuolis
        sw.update()
        self.center_window(sw, 1400, 1000) # Galutinis fiksavimas
        canvas.draw()

    def _extract_drt_from_json(self, proj, ds_uuid):
        # 1. Tikriname fits (dažniausia vieta)
        fits = proj.get('fits', {}).get(ds_uuid, [])
        for f in reversed(fits):
            # Tikriname 'results' viduje
            res = f.get('results', {})
            t, g = self._find_tau_gamma_in_dict(res)
            if t is not None: return t, g
            
            # Tikriname pačiame fit objekte
            t, g = self._find_tau_gamma_in_dict(f)
            if t is not None: return t, g

        # 2. Tikriname specializuotus DRT blokus (įskaitant 'drts')
        for key in ['drts', 'drt_results', 'drt', 'drt_data']:
            root = proj.get(key, {}).get(ds_uuid, [])
            # Jei tai sąrašas (kaip vartotojo pavyzdyje), tikriname kiekvieną elementą
            if isinstance(root, list):
                for item in reversed(root):
                    t, g = self._find_tau_gamma_in_dict(item)
                    if t is not None: return t, g
            else:
                t, g = self._find_tau_gamma_in_dict(root)
                if t is not None: return t, g
        
        # Debug: jei nieko neradome, atspausdiname raktus į terminalą pagalbai
        if ds_uuid in proj.get('drts', {}):
            drt_list = proj['drts'][ds_uuid]
            if drt_list and isinstance(drt_list, list):
                print(f"DEBUG: 'drts' bloke rasti raktai UUID {ds_uuid}: {list(drt_list[0].keys())}")
            
        if ds_uuid in proj.get('fits', {}) and len(proj['fits'].get(ds_uuid, [])) > 0:
            fit0 = proj['fits'][ds_uuid][0]
            print(f"DEBUG: Nerasta DRT duomenu UUID {ds_uuid}. Fit 0 raktai: {list(fit0.keys())}")
            if 'results' in fit0:
                print(f"DEBUG: Results raktai: {list(fit0['results'].keys())}")
        else:
            print(f"DEBUG: Nerasta DRT duomenu UUID {ds_uuid}. Fit duomenu nera.")
            
        return None, None

    def _find_tau_gamma_in_dict(self, d):
        if not isinstance(d, dict): return None, None
        
        # 1. Potencialūs laiko/dažnio raktai
        # Pridedame 'time_constants', kurį matome debug'e
        t_keys = [k for k in d.keys() if any(x in k.lower() for x in ['tau', 'relaxation', 'time_constant', 'times'])]
        f_keys = [k for k in d.keys() if 'freq' in k.lower()]
        
        # 2. Potencialūs gamma raktai
        # Pridedame 'mean_gammas' ir 'real_gammas'
        all_g_keys = [k for k in d.keys() if any(x in k.lower() for x in ['gamma', 'distrib', 'g_val', 'df']) or k.lower() == 'g']
        # Prioritetas: real_gammas, mean_gammas, gammas...
        g_keys = sorted(all_g_keys, key=lambda x: ('imaginary' in x.lower(), 'real' not in x.lower(), 'mean' not in x.lower()))

        def try_extract(tk, gk, is_freq=False):
            t_val, g_val = d[tk], d[gk]
            if isinstance(t_val, (list, np.ndarray)) and isinstance(g_val, (list, np.ndarray)):
                if len(t_val) > 5 and len(t_val) == len(g_val):
                    try:
                        t_arr = np.array(t_val, dtype=float)
                        g_arr = np.array(g_val, dtype=float)
                        if is_freq: t_arr = 1.0 / (2 * np.pi * t_arr)
                        idx = np.argsort(t_arr)
                        return t_arr[idx], g_arr[idx]
                    except: return None
            return None

        # Bandome visas kombinacijas
        for gk in g_keys:
            # Pirmiausia bandome su tiesioginiais laiko raktais (tau, time_constants)
            for tk in t_keys:
                res = try_extract(tk, gk, False)
                if res: return res
            # Tada su dažniais
            for fk in f_keys:
                res = try_extract(fk, gk, True)
                if res: return res
                
        return None, None

    def _plot_drt_popup(self, tau, gamma, label):
        win = tk.Toplevel(self.root)
        win.title(f"DRT Analizė - {label}")
        self.center_window(win, 1560, 1106) # Pradinis +1px layoutui
        win.configure(bg='white')

        self._drt_temp_peak = None # Dabartinis nebaigtas pikas
        self._drt_saved_peaks = [] # Išvalome senus pikus naujam langui
        
        # Valdymo panelė viršuje
        ctrl_f = tk.Frame(win, bg='white', pady=10)
        ctrl_f.pack(fill=tk.X)
        
        info_label = tk.Label(ctrl_f, text="Pažymėkite piko sritį grafike (stačiakampiu)", 
                              font=('Segoe UI', 10, 'italic'), bg='white', fg='#555')
        info_label.pack()
        
        btn_f = tk.Frame(win, bg='white', pady=5)
        btn_f.pack(fill=tk.X)
        
        if self.is_normalized_var.get():
            res_var = tk.StringVar(value="ρ_p = --- | C_p = ---")
            r_unit = "Ω·m"
            r_name = "ρ"
        else:
            res_var = tk.StringVar(value="R_p = --- | C_p = ---")
            r_unit = "Ω"
            r_name = "R"
            
        tk.Label(btn_f, textvariable=res_var, font=('Segoe UI', 12, 'bold'), bg='white', fg='#2E7D32').pack(side=tk.LEFT, padx=20)
        
        def save_peak():
            if self._drt_temp_peak:
                self._drt_saved_peaks.append(self._drt_temp_peak)
                self._drt_temp_peak = None
                redraw()
        
        def clear_peaks():
            self._drt_saved_peaks.clear()
            self._drt_temp_peak = None
            redraw()

        tk.Button(btn_f, text='➕ Išsaugoti piką', command=save_peak, bg="#43A047", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text='🧹 Išvalyti visus', command=clear_peaks, bg="#E53935", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        fig = Figure(figsize=(14, 9), dpi=100, facecolor='white')
        ax = fig.add_subplot(111)
        
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Toolbaras apačioje
        tb_frame = tk.Frame(win, bg='white')
        tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(canvas, tb_frame)
        
        win.update()
        self.center_window(win, 1560, 1105) # Galutinis dydis
        canvas.draw()

        self._drt_popup_artists = []
        ax.semilogx(tau, gamma, 'k-', lw=1.5, label='DRT spektas', alpha=0.8)

        def redraw():
            # Pašaliname tik pikus, ne visą ašį (kad neišsitrintų parinkiklis)
            for art in self._drt_popup_artists:
                try: art.remove()
                except: pass
            self._drt_popup_artists = []
            
            cmap = plt.colormaps.get_cmap('Set1')
            
            # Piešiame išsaugotus pikus
            for i, p in enumerate(self._drt_saved_peaks):
                color = cmap(i % 9)
                f = ax.fill_between(p['ts'], p['gs'], color=color, alpha=0.4, 
                                   label=f"Pikas {i+1}: {r_name}={p['R']:.3f} {r_unit}, C={p['C']:.2E} F")
                s = ax.scatter(p['tp'], np.max(p['gs']), color=color, s=40, edgecolors='black')
                self._drt_popup_artists.extend([f, s])

            # Piešiame dabartinį pasirinkimą
            if self._drt_temp_peak:
                p = self._drt_temp_peak
                f_temp = ax.fill_between(p['ts'], p['gs'], color='gray', alpha=0.3, linestyle='--', label='Dabartinis')
                self._drt_popup_artists.append(f_temp)
                res_var.set(f"R_p = {p['R']:.4f} Ω | C_p = {p['C']:.4E} F")
            else:
                res_var.set("R_p = --- | C_p = ---")

            ax.set_xlabel(r'Relaxation Time $\tau$, s')
            ax.set_ylabel(r'Distribution Function $\gamma$, \Omega')
            ax.set_title(f"DRT Analizė: {label}")
            ax.grid(True, which="both", alpha=0.2)
            
            handles, labels = ax.get_legend_handles_labels()
            if labels:
                ax.legend(fontsize=8, loc='best')
            canvas.draw_idle()

        def on_select(eclick, erelease):
            tmin, tmax = sorted([eclick.xdata, erelease.xdata])
            mask = (tau >= tmin) & (tau <= tmax)
            ts = tau[mask]
            gs = gamma[mask]
            if len(ts) < 3: return
            
            ln_t = np.log(tau)
            ln_ts = ln_t[mask]
            R = simpson(y=gs, x=ln_ts)
            tp = ts[np.argmax(gs)]
            C = tp / R if R != 0 else 0
            
            self._drt_temp_peak = {'ts': ts, 'gs': gs, 'R': R, 'C': C, 'tp': tp}
            redraw()

        # Stilius žymėjimo stačiakampiui
        props = dict(facecolor='#1565C0', alpha=0.2, edgecolor='black', linewidth=1)
        win.rs = RectangleSelector(ax, on_select, useblit=False, button=[1, 3], 
                                   minspanx=0, minspany=0, interactive=True, props=props)
        redraw()

    def _update_arr_extrapolation(self, *args):
        # Prioritetas aktyviam taškui (burbuliukui)
        active_params = getattr(self, '_arr_active_reg_params', (None, None))
        active_color = getattr(self, '_arr_active_bubble_color', '#1565C0')
        
        slope, intercept = active_params
        ea, sigma0 = None, None
        source_label = ""

        if slope is not None:
            kB = 8.617333e-5
            ea = -slope * kB * 1000
            sigma0 = np.exp(intercept)
        else:
            # Jei aktyvaus nėra, imam dabartinę regresiją
            slope, intercept = getattr(self, 'arr_reg_params', (None, None))
            active_color = '#1565C0'
            if slope is not None:
                kB = 8.617333e-5
                ea = -slope * kB * 1000
                sigma0 = np.exp(intercept)
        
        if ea is None:
            if hasattr(self, 'arr_extrap_res_var'):
                self.arr_extrap_res_var.set('Pasirinkite tašką arba regresiją')
            return

        try:
            val_str = self.arr_extrap_t_var.get().strip()
            if not val_str: return
            tc = float(val_str.replace(',', '.'))
            tk_val = tc + 273.15
            if tk_val <= 0: raise ValueError
            
            # sigma = (sigma0 / T) * exp(-Ea / (kB * T))
            kB = 8.617333e-5
            sigma = (sigma0 / tk_val) * np.exp(-ea / (kB * tk_val))
            
            # Atnaujiname tekstą ir spalvą
            self.arr_extrap_res_var.set(f"σ({tc}°C) = {to_sci_unicode(sigma, 4)} S/cm")
            if hasattr(self, 'arr_extrap_res_label'):
                self.arr_extrap_res_label.config(fg=active_color)
        except (ValueError, Exception):
            self.arr_extrap_res_var.set('Neteisinga T')

    def _compute_arr_df(self):
        proj = self.arr_state['project']
        if proj is None:
            messagebox.showerror('Klaida', 'Įkelkite projektą.')
            return None
        try:
            if self.is_normalized_var.get():
                L_cm = 1.0
                A_cm2 = 100.0 # sigma(S/cm) = 1/(rho(Ohm*m)*100)
            else:
                # Imam iš pagrindinio lango (ten mm ir mm2)
                L_mm = float(self.thickness_var.get())
                A_mm2 = float(self.area_var.get())
                
                # extract_fit_data tikisi cm ir cm2
                L_cm = L_mm / 10.0
                A_cm2 = A_mm2 / 100.0
        except ValueError:
            messagebox.showerror('Klaida', 'Neteisingi geometrijos duomenys pagrindiniame lange.')
            return None
        A = A_cm2
        r_sel = [rk for rk, var in self.arr_r_check_vars.items() if var.get()]
        if not r_sel: r_sel = self.arr_state['all_r_keys'] or []
        mode = self.arr_fit_mode_var.get()
        fi = self.arr_fit_index_var.get().strip() if mode == 'index' else mode
        df = extract_fit_data(proj, L_cm, A_cm2, r_sel, fi)
        if df.empty:
            messagebox.showwarning('Įspėjimas', 'Nerasta tinkamų duomenų.')
            return None
        return df

    def draw_arrhenius_plot(self):
        df = self._compute_arr_df()
        if df is None: return
        self._arr_df_cache[0] = df
        self._arr_point_selected.clear()
        self.arr_point_info_var.set('Spauskite tašką info')

        # Sukuriame naują langą grafikui
        arr_win = tk.Toplevel(self.root)
        
        # Nustatome dinaminį pavadinimą pagal parinktas varžas
        r_sel = [rk for rk, var in self.arr_r_check_vars.items() if var.get()]
        if len(r_sel) == 2:
            arr_win.title("Arenijaus grafikas ($R$=$R_{t}$+$R_{gr}$)")
        elif len(r_sel) == 1:
            arr_win.title(f"Arenijaus grafikas ({r_sel[0]})")
        else:
            arr_win.title("Arenijaus analizė")
            
        self.center_window(arr_win, 1200, 900)

        # Ea label ir pasirinkimo mygtukai viršuje
        ctrl_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
        ctrl_f.pack(fill=tk.X)
        
        tk.Label(ctrl_f, textvariable=self.arr_ea_label_var, foreground='#B71C1C', 
                 font=('Segoe UI', 12, 'bold'), bg='white').pack(side=tk.LEFT)
                 
        tk.Label(ctrl_f, textvariable=self.arr_point_info_var, foreground='#2E7D32',
                 font=('Segoe UI', 10, 'bold'), bg='white').pack(side=tk.RIGHT, padx=20)
        
        # Ekstrapoliacijos sekcija
        extrap_f = tk.LabelFrame(arr_win, text='Ekstrapoliacija (iš regresijos)', bg='white', padx=10, pady=5)
        extrap_f.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(extrap_f, text='Temperatūra:', bg='white').pack(side=tk.LEFT, padx=5)
        self.arr_extrap_t_var = tk.StringVar(value='25')
        ext_t_entry = ttk.Entry(extrap_f, textvariable=self.arr_extrap_t_var, width=8)
        ext_t_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(extrap_f, text='°C', bg='white').pack(side=tk.LEFT)
        
        self.arr_extrap_res_var = tk.StringVar(value='')
        self.arr_extrap_res_label = tk.Label(extrap_f, textvariable=self.arr_extrap_res_var, foreground='#1565C0',
                 font=('Segoe UI', 10, 'bold'), bg='white')
        self.arr_extrap_res_label.pack(side=tk.LEFT, padx=30)
        
        self.arr_extrap_t_var.trace_add('write', self._update_arr_extrapolation)
        
        btn_sel_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
        btn_sel_f.pack(fill=tk.X)
        tk.Label(btn_sel_f, text="Regresija:", bg='white', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_sel_f, text='Visi taškai', command=self._select_all_arr_points, 
                  bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_sel_f, text='Atžymėti visus', command=self._clear_arr_sel, 
                  bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
        
        # Nauji mygtukai kelioms linijoms
        line_ctrl_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
        line_ctrl_f.pack(fill=tk.X)
        tk.Button(line_ctrl_f, text='➕ Išsaugoti liniją', command=self._save_arr_line,
                  bg="#43A047", fg="white", font=('Segoe UI', 9, 'bold'), relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
        tk.Button(line_ctrl_f, text='🧹 Išvalyti visas linijas', command=self._clear_saved_arr_lines,
                  bg="#E53935", fg="white", font=('Segoe UI', 9, 'bold'), relief="raised", bd=2).pack(side=tk.LEFT, padx=5)

        self.arr_fig = Figure(figsize=(9, 6), dpi=100, facecolor='white')
        self.arr_ax = self.arr_fig.add_subplot(111)
        self.arr_ax.grid(True, alpha=0.3)
        
        self.arr_canvas = FigureCanvasTkAgg(self.arr_fig, master=arr_win)
        
        # Toolbar pridedame į apačią PRIEŠ canvas, kad jo nenustumtų už ekrano
        tb_frame = tk.Frame(arr_win)
        tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.arr_toolbar = NavigationToolbar2Tk(self.arr_canvas, tb_frame)
        self.arr_toolbar.update()

        self._arr_saved_artists = []
        self._arr_saved_lines = []

        def on_arr_select(eclick, erelease):
            df = self._arr_df_cache[0]
            if df is None: return
            xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
            valid = ~(np.isnan(xall) | np.isnan(yall))
            x_v, y_v = xall[valid], yall[valid]
            xmin, xmax = sorted([eclick.xdata, erelease.xdata])
            ymin, ymax = sorted([eclick.ydata, erelease.ydata])
            is_select = (eclick.button == 1)
            for i in range(len(x_v)):
                if xmin <= x_v[i] <= xmax and ymin <= y_v[i] <= ymax:
                    self._arr_point_selected[i] = is_select
            self._recompute_arr_regression()

        self.arr_rs = RectangleSelector(self.arr_ax, on_arr_select,
                                        useblit=False, button=[1, 3],
                                        minspanx=0, minspany=0,
                                        interactive=False)
        
        self.arr_canvas.mpl_connect('button_press_event', self._on_arr_plot_click)
        self.arr_canvas.mpl_connect('key_press_event', self._on_arr_key_press)
        
        # Priverčiame canvas gauti klaviatūros fokusą, kai pelė užvedama
        self.arr_canvas.get_tk_widget().bind("<Enter>", lambda e: self.arr_canvas.get_tk_widget().focus_set())

        xall = df['1000/T'].values
        yall = df['ln(Sigma*T)'].values
        yerr = df['ln_err'].values
        valid = ~(np.isnan(xall) | np.isnan(yall))
        x_v, y_v, ye_v = xall[valid], yall[valid], yerr[valid]

        for i in range(len(x_v)): self._arr_point_selected[i] = True
        
        r_sel = [rk for rk, var in self.arr_r_check_vars.items() if var.get()]
        all_keys = self.arr_state.get('all_r_keys', [])
        
        if len(r_sel) == 1 and len(all_keys) >= 2:
            if r_sel[0] == all_keys[0]:
                r_type_str = "R_{gr}"
            elif r_sel[0] == all_keys[1]:
                r_type_str = "R_{t}"
            else:
                r_type_str = f"R_{{{r_sel[0]}}}"
        elif not r_sel:
            r_type_str = "R_{total}"
        else:
            r_type_str = "R_{total}"
            
        self.arr_ax.set_xlabel('1000/T, 1/K')
        self.arr_ax.set_ylabel(r'$\ln(\sigma \cdot T)$, S$\cdot$K/cm')
        self.arr_ax.set_title(f'Arenijaus grafikas (${r_type_str}$)', pad=20)
        
        # Pridedame antrinę X ašį su Kelvino temperatūra viršuje
        def t_forward(x):
            x = np.array(x, dtype=float)
            x[np.abs(x) < 1e-10] = 1e-10 # Išvengiame dalybos iš nulio
            return 1000.0 / x

        def t_inverse(t):
            t = np.array(t, dtype=float)
            t[np.abs(t) < 1e-10] = 1e-10
            return 1000.0 / t

        secax = self.arr_ax.secondary_xaxis('top', functions=(t_forward, t_inverse))
        secax.set_xlabel('T, K')
        
        if len(x_v) > 0:
            xmin, xmax = min(x_v), max(x_v)
            pad_x = (xmax - xmin) * 0.05 if xmax > xmin else 0.1
            xmin, xmax = xmin - pad_x, xmax + pad_x
            self.arr_ax.set_xlim(xmin, xmax)
            
            ymin, ymax = min(y_v), max(y_v)
            pad_y = (ymax - ymin) * 0.05 if ymax > ymin else 0.1
            self.arr_ax.set_ylim(ymin - pad_y, ymax + pad_y)
            
            # Priverčiame sugeneruoti apatinės ašies padalas
            self.arr_fig.canvas.draw()
            xticks = self.arr_ax.get_xticks()
            
            # Paliekame tik tas padalas, kurios yra matomame rėžyje
            valid_xticks = xticks[(xticks >= xmin) & (xticks <= xmax) & (xticks > 1e-5)]
            
            if len(valid_xticks) > 0:
                # Nustatome viršutinės ašies padalas tose pačiose vertikaliose linijose
                secax.set_xticks(1000.0 / valid_xticks)
                import matplotlib.ticker as ticker
                secax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f"{val:.1f}".rstrip('0').rstrip('.')))
        
        # Instrukcijų label apačioje
        tk.Label(arr_win, text="🖱️ Žymėti/atžymėti su rėmeliu (kair./deš. pelytė). 🎯 Paspauskite tašką informacijai.", 
                 bg='#f0f0f0', font=('Segoe UI', 9, 'italic'), pady=3).pack(side=tk.BOTTOM, fill=tk.X)

        # Galiausiai supakuojame canvas, kad jis užimtų likusią laisvą vietą
        self.arr_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.arr_fig.tight_layout()
        self._recompute_arr_regression()
        self.arr_status_var.set(f'Grafikas paruoštas. Taškų: {len(x_v)}')

        # Vieno pikselio "refresh" triukas, kad grafikas persipieštų ir teisingai pritaikytų layout'ą
        def force_refresh():
            w, h = arr_win.winfo_width(), arr_win.winfo_height()
            if w > 100:
                arr_win.geometry(f"{w+1}x{h}")
                arr_win.after(50, lambda: arr_win.geometry(f"{w}x{h}"))
        arr_win.after(200, force_refresh)

    def _recompute_arr_regression(self):
        df = self._arr_df_cache[0]
        if df is None: return
        xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
        yerr = df['ln_err'].values
        valid = ~(np.isnan(xall) | np.isnan(yall))
        x_v, y_v, ye_v = xall[valid], yall[valid], yerr[valid]
        n = len(x_v)

        sel_idx = [i for i in range(n) if self._arr_point_selected.get(i, True)]
        unsel_idx = [i for i in range(n) if not self._arr_point_selected.get(i, True)]

        if self._arr_scatter_sel is not None: self._arr_scatter_sel.remove()
        if self._arr_scatter_unsel is not None: self._arr_scatter_unsel.remove()
        if self._arr_reg_line is not None:
            try: self._arr_reg_line[0].remove()
            except: pass
        
        for art in self._arr_saved_artists:
            try: art.remove()
            except: pass
        self._arr_saved_artists = []
        
        if not hasattr(self, '_arr_errorbars'): self._arr_errorbars = []
        for container in self._arr_errorbars:
            try: container.remove()
            except: pass
        self._arr_errorbars = []

        self._arr_scatter_sel = self._arr_scatter_unsel = self._arr_reg_line = None

        if sel_idx:
            self._arr_scatter_sel = self.arr_ax.scatter(x_v[sel_idx], y_v[sel_idx], c='#1565C0', s=70, zorder=5, label=f'Dabartiniai ({len(sel_idx)})')
        if unsel_idx:
            self._arr_scatter_unsel = self.arr_ax.scatter(x_v[unsel_idx], y_v[unsel_idx], facecolors='none', edgecolors='#aaa', s=70, zorder=4)
            
        for xi, yi, yei in zip(x_v, y_v, ye_v):
            if not np.isnan(yei) and yei > 0:
                container = self.arr_ax.errorbar(xi, yi, yerr=yei, fmt='none', ecolor='#90CAF9', capsize=3, zorder=2)
                self._arr_errorbars.append(container)
        
        # Braižome išsaugotas linijas ir jų taškus
        cmap = plt.cm.Set1
        for i, ld in enumerate(self._arr_saved_lines):
            color = cmap(i % 9)
            art = self.arr_ax.plot(ld['xfit'], ld['yfit'], '--', color=color, lw=1.5, zorder=3,
                                  label=f"$E_a$ {i+1}: {format_comma(ld['ea'], 4)} eV, σ₀: {to_sci_unicode(ld['sigma0'], 3)} S·K/cm ($R^2$={format_comma(ld['r2'], 4)})")
            self._arr_saved_artists.extend(art)
            if 'sel_idx' in ld:
                idx = ld['sel_idx']
                pts = self.arr_ax.scatter(x_v[idx], y_v[idx], color=color, s=50, zorder=6, alpha=0.8)
                self._arr_saved_artists.append(pts)

        if len(sel_idx) >= 2:
            xs, ys = x_v[sel_idx], y_v[sel_idx]
            slope, intercept, r_val, p, se = stats.linregress(xs, ys)
            xfit = np.linspace(xs.min(), xs.max(), 300)
            kB = 8.617333e-5
            ea_now = -slope * kB * 1000
            sigma0_now = np.exp(intercept)
            self.arr_reg_params[0], self.arr_reg_params[1] = slope, intercept
            self._arr_reg_line = self.arr_ax.plot(xfit, slope * xfit + intercept, 'r-', lw=2, zorder=3,
                                                 label=f'Dabartinė: $E_a$={format_comma(ea_now, 4)} eV, σ₀={to_sci_unicode(sigma0_now, 3)} S·K/cm ($R^2$={format_comma(r_val**2, 4)})')
            self.arr_ea_label_var.set(f'Eₐ = {format_comma(ea_now, 4)} eV  |  σ₀ = {to_sci_unicode(sigma0_now, 3)} S·K/cm  |  R² = {format_comma(r_val**2, 4)}')
            self._update_arr_extrapolation()
        else:
            self.arr_reg_params[0] = None
            self.arr_ea_label_var.set('(pažymėkite taškus regresijai)')
            self._update_arr_extrapolation()

        handles, labels = self.arr_ax.get_legend_handles_labels()
        if labels:
            self.arr_ax.legend(fontsize=8, loc='center right')
        self.arr_canvas.draw_idle()

    def _save_arr_line(self):
        df = self._arr_df_cache[0]
        if df is None: return
        xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
        valid = ~(np.isnan(xall) | np.isnan(yall))
        x_v, y_v = xall[valid], yall[valid]
        sel_idx = [i for i in range(len(x_v)) if self._arr_point_selected.get(i, True)]
        
        if len(sel_idx) < 2:
            messagebox.showwarning("Dėmesio", "Linijai išsaugoti reikia bent 2 pažymėtų taškų.")
            return
            
        xs, ys = x_v[sel_idx], y_v[sel_idx]
        slope, intercept, r_val, p, se = stats.linregress(xs, ys)
        xfit = np.linspace(xs.min(), xs.max(), 300)
        kB = 8.617333e-5
        ea = -slope * kB * 1000
        
        self._arr_saved_lines.append({
            'xfit': xfit, 'yfit': slope * xfit + intercept,
            'ea': ea, 'r2': r_val**2,
            'sigma0': np.exp(intercept),
            'slope': slope,
            'intercept': intercept,
            'sel_idx': list(sel_idx)
        })
        for i in range(len(x_v)): self._arr_point_selected[i] = False
        self._recompute_arr_regression()

    def _clear_saved_arr_lines(self):
        self._arr_saved_lines = []
        self._recompute_arr_regression()

    def _on_arr_plot_click(self, event):
        if event.inaxes != getattr(self, 'arr_ax', None): return
        
        if event.button == 3:
            self.on_plot_click(event)
            return
            
        if event.button != 1: return # Tik kairysis pelės klavišas
        
        df = self._arr_df_cache[0]
        if df is None: return
        
        xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
        valid = ~(np.isnan(xall) | np.isnan(yall))
        xv, yv = xall[valid], yall[valid]
        valid_indices = np.where(valid)[0]
        
        if len(xv) == 0: return
        
        # Randame arčiausiai pelės esantį tašką pikselių atstumu
        click_disp = self.arr_ax.transData.transform((event.xdata, event.ydata))
        points_disp = self.arr_ax.transData.transform(np.c_[xv, yv])
        dists = np.linalg.norm(points_disp - click_disp, axis=1)
        
        min_idx = np.argmin(dists)
        if dists[min_idx] < 15: # 15 pikselių tolerancija
            # Atnaujiname aktyvų indeksą ir pašaliname seną žymeklį
            active_idx = valid_indices[min_idx]
            self._arr_active_idx = active_idx
            
            if getattr(self, '_arr_active_marker', None) is not None:
                try: self._arr_active_marker.remove()
                except: pass

            # Nustatome burbuliuko spalvą ir skaičiavimo parametrus pagal tai, kuriai regresijai priklauso taškas
            bubble_color = '#1565C0' # Numatytoji (mėlyna - dabartinė)
            
            x = xall[active_idx]
            y_data = yall[active_idx]
            T_K = 1000.0 / x
            T_C = T_K - 273.15
            
            # Numatytasis skaičiavimas iš duomenų taško, jei nėra regresijos
            calc_y = y_data
            active_params = (None, None)
            source_info = "Duomenų taškas"
            
            # Tikriname priklausomybę regresijoms (išsaugotoms ir dabartinei)
            # Pirmiausia tikriname išsaugotas (nes jos turi specifines spalvas)
            found_saved = False
            if hasattr(self, '_arr_saved_lines'):
                cmap = plt.cm.Set1
                for i, ld in reversed(list(enumerate(self._arr_saved_lines))):
                    if active_idx in ld.get('sel_idx', []):
                        bubble_color = cmap(i % 9)
                        if 'slope' in ld and 'intercept' in ld:
                            calc_y = ld['slope'] * x + ld['intercept']
                            active_params = (ld['slope'], ld['intercept'])
                        else:
                            # Atsarginis variantas jei trūksta parametrų
                            calc_y = y_data
                            active_params = (None, None)
                        source_info = f"Linija {i+1}"
                        found_saved = True
                        break
            
            # Jei nerasta išsaugotose arba taškas yra aktyvioje parinktyje, pirmenybė dabartinei
            if self._arr_point_selected.get(active_idx, True):
                slope, intercept = getattr(self, 'arr_reg_params', (None, None))
                if slope is not None:
                    bubble_color = '#1565C0'
                    calc_y = slope * x + intercept
                    active_params = (slope, intercept)
                    source_info = "Dabartinė regresija"
                    found_saved = False # Prioritetas aktyviai
            elif not found_saved:
                bubble_color = '#777777' # Pilka jei niekur nepriklauso (neatliekama analizė)
                active_params = (None, None)
            
            # Išsaugome ekstrapoliacijai
            self._arr_active_reg_params = active_params
            self._arr_active_bubble_color = bubble_color
            
            self._arr_active_marker = self.arr_ax.plot(
                [x], [y_data], 
                'o', color='none', mec=bubble_color, mew=2.5, ms=15, zorder=10
            )[0]
            
            # Paskaičiuojame σ pagal parinktą y (iš regresijos arba taško)
            try:
                sigma_fit = np.exp(calc_y) / T_K
                
                # Pridedame informaciją į legendą
                if getattr(self, '_arr_legend_point', None):
                    try: self._arr_legend_point.remove()
                    except: pass
                
                leg_label = f"Taškas: {T_C:.2f} °C | σ = {to_sci_unicode(sigma_fit, 2)} S/cm"
                self._arr_legend_point = self.arr_ax.plot([], [], 'o', color='none', 
                                                         mec=bubble_color, mew=2, ms=10, 
                                                         label=leg_label)[0]
                self.arr_ax.legend(fontsize=8, loc='best')
                
                self.arr_fig.canvas.draw_idle()
                self._update_arr_extrapolation()
            except Exception as e:
                pass
            # Paskaičiuojame varžą pagal dabartinę poziciją
            x = xall[self._arr_active_idx]
            y = yall[self._arr_active_idx]
            T = 1000.0 / x
            try:
                if self.is_normalized_var.get():
                    L_cm = 1.0
                    A_cm2 = 100.0
                    val_name = "ρ"
                    val_unit = "Ω·m"
                else:
                    L_cm = float(str(self.thickness_var.get()).replace(',', '.')) * 0.1
                    A_cm2 = float(str(self.area_var.get()).replace(',', '.')) * 0.01
                    val_name = "R"
                    val_unit = "Ω"
                    
                sigma = sigma_fit # Naudojame tą, kurį apskaičiavome aukščiau iš regresijos
                # Paskaičiuojame atitinkamą varžą (arba ρ) iš modelio
                R = (L_cm / A_cm2) / sigma
                
                self.arr_point_info_var.set(f"Taškas ({source_info}): {T_C:.2f} °C | σ = {to_sci_unicode(sigma, 4)} S/cm")
                self.arr_status_var.set(f"Pasirinktas taškas {T_K:.1f} K ({source_info}). {val_name} = {to_sci_unicode(R, 3)} {val_unit} | σ = {to_sci_unicode(sigma, 4)} S/cm")
            except Exception as e:
                self.arr_status_var.set(f"Pasirinktas taškas {T:.1f} K.")

    def _on_arr_key_press(self, event):
        return # Funkcija išjungta naudotojo prašymu
        
        r_sel = [rk for rk, var in self.arr_r_check_vars.items() if var.get()]
        if not r_sel: r_sel = self.arr_state['all_r_keys'] or []
        
        if len(r_sel) != 1:
            self.arr_status_var.set("Perstūmimas galimas tik pasirinkus lygiai VIENĄ varžos komponentą!")
            return
            
        df = self._arr_df_cache[0]
        if df is None: return
        
        # Keičiame Y poziciją (ln(Sigma*T))
        step = 0.05
        if k == 'up':
            df.at[self._arr_active_idx, 'ln(Sigma*T)'] += step
        elif k == 'down':
            df.at[self._arr_active_idx, 'ln(Sigma*T)'] -= step
            
        x = df.at[self._arr_active_idx, '1000/T']
        y = df.at[self._arr_active_idx, 'ln(Sigma*T)']
        T = 1000.0 / x
        
        try:
            L_cm = float(str(self.thickness_var.get()).replace(',', '.')) * 0.1
            A_cm2 = float(str(self.area_var.get()).replace(',', '.')) * 0.01
            R_new = (L_cm * T) / (A_cm2 * np.exp(y))
            
            # Įrašome atgal į projekto būseną (tik tam vienam R elementui)
            ds_uuid = df.at[self._arr_active_idx, 'ds_uuid']
            fit_idx_str = self.arr_fit_index_var.get().strip()
            fit_list = self.arr_state['project'].get("fits", {}).get(ds_uuid, [])
            
            if fit_list:
                if fit_idx_str == "last": fit = fit_list[-1]
                elif fit_idx_str == "first": fit = fit_list[0]
                else:
                    try:
                        idx = int(fit_idx_str)
                        fit = fit_list[min(idx, len(fit_list) - 1)]
                    except:
                        fit = fit_list[-1]
                
                parameters = fit.get("parameters", {})
                rk = r_sel[0]
                
                if rk in parameters and "R" in parameters[rk]:
                    parameters[rk]["R"]["value"] = R_new
                    
            self.arr_status_var.set(f"Perstumta atmintyje! Nauja varža {T:.1f} K: {to_sci_unicode(R_new)} Ω. (Nepamirškite įrašyti projekto)")
        except Exception as e:
            self.arr_status_var.set(f"Perstumta! (Klaida: {e})")
            
        if getattr(self, '_arr_active_marker', None) is not None:
            self._arr_active_marker.set_data([x], [y])
            
        self._recompute_arr_regression()
        self.arr_fig.canvas.draw_idle()


    def _select_all_arr_points(self):
        df = self._arr_df_cache[0]
        if df is None: return
        n = int(np.sum(~(np.isnan(df['1000/T'].values) | np.isnan(df['ln(Sigma*T)'].values))))
        for i in range(n): self._arr_point_selected[i] = True
        self._recompute_arr_regression()

    def _clear_arr_sel(self):
        df = self._arr_df_cache[0]
        if df is None: return
        n = int(np.sum(~(np.isnan(df['1000/T'].values) | np.isnan(df['ln(Sigma*T)'].values))))
        for i in range(n): self._arr_point_selected[i] = False
        
        # Pašaliname ir raudoną burbuliuką (aktyvų tašką)
        if getattr(self, '_arr_active_marker', None) is not None:
            try: self._arr_active_marker.remove()
            except: pass
            self._arr_active_marker = None
        
        if getattr(self, '_arr_legend_point', None) is not None:
            try: self._arr_legend_point.remove()
            except: pass
            self._arr_legend_point = None
            self.arr_ax.legend(fontsize=8, loc='best')
            
        self._arr_active_idx = None
        self.arr_status_var.set("Visi taškai atžymėti.")
        
        self._recompute_arr_regression()

    def save_arrhenius_project(self):
        proj = self.arr_state.get('project')
        if not proj:
            messagebox.showwarning('Įspėjimas', 'Nėra atidaryto projekto.')
            return
            
        filepath = self.arr_project_path_var.get()
        if not filepath or not os.path.exists(filepath):
            messagebox.showwarning('Įspėjimas', 'Nerastas originalus projekto failas.')
            return
            
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(proj, f, indent=4)
            self.arr_status_var.set(f"Pakeitimai sėkmingai išsaugoti į {os.path.basename(filepath)}!")
            messagebox.showinfo('Sėkmė', 'Projektas sėkmingai atnaujintas ir išsaugotas.')
        except Exception as e:
            messagebox.showerror('Klaida', f'Klaida išsaugant projektą:\n{e}')

    def export_arrhenius_csv(self):
        df = self._compute_arr_df()
        if df is None: return
        out = filedialog.asksaveasfilename(title='Išsaugoti CSV', defaultextension='.csv', initialfile='arenijaus_duomenys.csv', filetypes=[('CSV failas', '*.csv'), ('Visi failai', '*.*')])
        if not out: return
        df.to_csv(out, index=False, float_format='%.6g')
        messagebox.showinfo('Sėkmė', f'CSV išsaugotas:\n{out}')

    def open_crystal_viewer(self):
        import subprocess
        viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llto_crystal_viewer.py')
        subprocess.Popen([sys.executable, viewer_path])

    def open_plot(self):
        try:
            selected = [t for t, v in self.vars.items() if v.get()]
            if not selected:
                messagebox.showwarning("Dėmesio", "Pasirinkite bent vieną temperatūrą kairiajame sąraše!")
                return
                
            n = len(selected)
            ms, lw = max(0.3, 3.5 - (n / 12)), max(0.2, 0.7 - (n / 30))
            
            # Sukuriame Toplevel langą
            plot_window = tk.Toplevel(self.root)
            plot_window.title("LLTO impedanso spektroskopija")
            plot_window.attributes('-topmost', True) # Laikinai iškeliam į priekį
            
            # Naudojame adaptyvų lango dydį (maksimalus, bet telpa ekrane)
            w, h = self.center_window(plot_window, 3500, 1901)
            
            # Panoraminis vaizdas - prideriname figsize pagal gautą lango dydį (coliais)
            dpi = 100
            fig_w, fig_h = w / dpi, h / dpi
            self.fig = Figure(figsize=(fig_w, fig_h), dpi=dpi, facecolor='white')
            self.axes = self.fig.subplots(3, 3)
            self.fig.subplots_adjust(top=0.96, bottom=0.14, left=0.04, right=0.96, hspace=0.3, wspace=0.3)
            self.table_text = self.fig.text(0.5, 0.03, "Kairiuoju pelės mygtuku spauskite ant taško, kad jį pažymėtumėte analizei | Du kartus spauskite dešiniuoju pelės mygtuku, kad redaguotumėte grafiką", 
                                           ha="center", fontsize=11, fontweight='bold', bbox=dict(facecolor='white', alpha=0.9))
            self.data_plots, self.highlight_markers = [], []
            
            all_data = {}
            k_LA, k_AL = self._get_geometric_factors()
            
            for temp in selected:
                f, z = self.get_filtered_data(temp)
                if len(f) == 0: continue
                
                # Normalizuojame impedansą į savitąją varžą [Ω·m]
                z_n = z * k_AL
                
                w_rad = 2 * np.pi * f
                mod_sq_n = z_n.real**2 + z_n.imag**2
                abs_Z_n = np.sqrt(mod_sq_n)
                
                ep, edp = -z_n.imag / (w_rad * EPSILON_0 * mod_sq_n), z_n.real / (w_rad * EPSILON_0 * mod_sq_n)
                sp, mdp = z_n.real / mod_sq_n, (w_rad * EPSILON_0 * z_n.real)
                th = np.degrees(np.arctan2(z_n.imag, z_n.real))
                
                tan_delta = edp / ep if len(ep) > 0 else np.zeros_like(f)
                
                max_z_imag = max(abs(-z_n.imag)) if len(z_n) > 0 and max(abs(-z_n.imag)) > 0 else 1
                max_mdp = max(mdp) if len(mdp) > 0 and max(mdp) > 0 else 1
                z_norm = -z_n.imag / max_z_imag
                m_norm = mdp / max_mdp
                
                log_f = np.log10(f)
                if len(f) > 1:
                    pseudo_drt = -np.gradient(z_n.real, log_f)
                else:
                    pseudo_drt = np.zeros_like(f)
                    
                sigma_dc = min(sp) if len(sp) > 0 else 1
                sum_x = f / (sigma_dc * temp)
                sum_y = sp / sigma_dc
                
                all_data[temp] = {
                    'f': f, 'z': z_n, 'abs_Z': abs_Z_n, 'ep': ep, 'edp': edp, 'sp': sp, 'mdp': mdp, 'th': th,
                    'tan_delta': tan_delta, 'z_norm': z_norm, 'm_norm': m_norm, 
                    'pseudo_drt': pseudo_drt, 'sum_x': sum_x, 'sum_y': sum_y
                }
                
            selected_graphs = [GRAPH_TYPES[var.get()] for var in self.graph_vars]
            
            GRAPH_META = {
                "Z_real_f": ("Z' priklausomybė nuo dažnio", "f, Hz", "Z', Ω·m", "log", "log"),
                "Z_imag_f": ("-Z'' priklausomybė nuo dažnio", "f, Hz", "-Z'', Ω·m", "log", "log"),
                "eps_real_f": ("Dielektrinė skvarba (ε')", "f, Hz", "ε', vnt.", "log", "log"),
                "eps_imag_f": ("Dielektriniai nuostoliai (ε'')", "f, Hz", "ε'', vnt.", "log", "log"),
                "sigma_f": ("Savitasis laidumas (σ')", "f, Hz", "σ', S/m", "log", "log"),
                "M_imag_f": ("Elektrinis modulis (M'')", "f, Hz", "M'', vnt.", "log", "linear"),
                "tan_delta_f": ("Nuostolių tangentas (tan δ)", "f, Hz", "tan δ", "log", "log"),
                "norm_z_m_f": (r"Normalizuoti $Z''/Z''_{max}$ ir $M''/M''_{max}$", "f, Hz", "Norm. vertė", "log", "linear"),
                "norm_z_f": (r"Normalizuotas $Z''/Z''_{max}$", "f, Hz", r"$Z''/Z''_{max}$", "log", "linear"),
                "norm_m_f": (r"Normalizuotas $M''/M''_{max}$", "f, Hz", r"$M''/M''_{max}$", "log", "linear"),
                "summerfield": ("Summerfield skalavimas", r"$f / (\sigma_{dc} \cdot T)$ [K·Hz·Ω·m]", r"$\sigma_{ac} / \sigma_{dc}$", "log", "log"),
                "pseudo_drt": (r"Pseudo-DRT ($-dZ'/d\log f$)", "f, Hz", r"$-dZ'/d(\log f)$", "log", "linear"),
                "nyquist": ("Naikvisto grafikas (Z'' nuo Z')", "Z', Ω·m", "-Z'', Ω·m", "linear", "linear"),
                "z_real_imag_f": ("Z' ir -Z'' priklausomybė nuo dažnio", "f, Hz", "Z' ir -Z'', Ω·m", "log", "log"),
                "abs_Z_f": ("Bodė grafikas (|Z|)", "f, Hz", "|Z|, Ω·m", "log", "log"),
                "phase_f": ("Fazės kampas (-Θ)", "f, Hz", "-Θ, °", "log", "linear"),
                "bode_dual": ("Bodė grafikas (|Z| ir -Θ)", "f, Hz", "|Z|, Ω·m", "log", "log"),
                "cole_cole": ("Cole-Cole grafikas", "ε', vnt.", "ε'', vnt.", "log", "log")
            }

            ax_f = self.axes.flat
            
            # Spalvų parinkimas pagal temperatūrą (jei pasirinkta daugiau nei 1)
            # Standartinės "stock" spalvos (C0, C1, ...)
            temp_to_color = {t: f"C{i % 10}" for i, t in enumerate(selected)}

            for temp in selected:
                if temp not in all_data: continue
                d = all_data[temp]
                color = temp_to_color[temp] if len(selected) > 1 else '#1f77b4'
                
                for idx, g_type in zip(range(9), selected_graphs):
                    ax = ax_f[idx]
                    lbl = f"{temp:g} K"
                    if g_type == "Z_real_f": ax.loglog(d['f'], d['z'].real, 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "Z_imag_f": ax.loglog(d['f'], -d['z'].imag, 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "z_real_imag_f":
                        ax.loglog(d['f'], d['z'].real, 'o-', ms=ms, lw=lw, label=f"{lbl} (Z')", color=color, picker=5)
                        ax.loglog(d['f'], -d['z'].imag, 'v--', ms=ms, lw=lw*0.7, label=f"{lbl} (-Z'')", color=color, alpha=0.6, picker=5)
                    elif g_type == "eps_real_f": ax.loglog(d['f'], d['ep'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "eps_imag_f": ax.loglog(d['f'], d['edp'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "sigma_f": ax.loglog(d['f'], d['sp'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "M_imag_f": ax.semilogx(d['f'], d['mdp'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "tan_delta_f": ax.loglog(d['f'], d['tan_delta'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "norm_z_m_f":
                        ax.semilogx(d['f'], d['z_norm'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                        ax.semilogx(d['f'], d['m_norm'], 's--', ms=ms, lw=lw, color=color, alpha=0.5, picker=5)
                    elif g_type == "norm_z_f":
                        ax.semilogx(d['f'], d['z_norm'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "norm_m_f":
                        ax.semilogx(d['f'], d['m_norm'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "summerfield": ax.loglog(d['sum_x'], d['sum_y'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "pseudo_drt": ax.semilogx(d['f'], d['pseudo_drt'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "nyquist": 
                        ax.plot(d['z'].real, -d['z'].imag, 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                        if temp in self.fitted_curves:
                            ff, zf = self.fitted_curves[temp]
                            ax.plot(zf.real, -zf.imag, '-', color=color, alpha=0.4, lw=1.5)
                    elif g_type == "abs_Z_f": ax.loglog(d['f'], d['abs_Z'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                    elif g_type == "phase_f": 
                        ax.semilogx(d['f'], d['th'], 's-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                        ax.invert_yaxis()
                    elif g_type == "bode_dual":
                        # Z modulis - rutuliukai
                        ax.loglog(d['f'], d['abs_Z'], 'o-', ms=ms, lw=lw, label=f"{temp:g} K (|Z|)", color=color, picker=5)
                        # Dešinė ašis fazei - kvadratukai, sujungti ištisine linija
                        if not hasattr(ax, '_ax_th'):
                            ax._ax_th = ax.twinx()
                            ax._ax_th._ax_primary = ax
                            ax._ax_th.set_ylabel("-Θ, °", color='#555555')
                            ax._ax_th.invert_yaxis() # Invertuojame fazės ašį (kad -90 būtų viršuje)
                        ax._ax_th.semilogx(d['f'], d['th'], 's-', ms=ms*0.8, lw=lw*0.8, color=color, alpha=0.8, label=f"{temp:g} K (-Θ)")
                    elif g_type == "cole_cole": ax.plot(d['ep'], d['edp'], 'o-', ms=ms, lw=lw, label=lbl, color=color, picker=5)
                
                for ax in ax_f:
                    for line in ax.get_lines():
                        if line.get_gid() is None:
                            line.set_gid(temp)
                
                self.data_plots.append({'temp': temp, **d})

            for idx, g_type in zip(range(9), selected_graphs):
                meta = GRAPH_META[g_type]
                ax = ax_f[idx]
                ax.set(title=meta[0], xlabel=meta[1], ylabel=meta[2])
                
                if meta[3] == 'log': ax.set_xscale('log')
                else: ax.set_xscale('linear')
                
                if meta[4] == 'log': ax.set_yscale('log')
                else: ax.set_yscale('linear')

            for i, ax in enumerate(ax_f):
                if ax.get_xscale() == 'log':
                    ax.xaxis.set_major_formatter(ticker.LogFormatterSciNotation())
                else:
                    ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                    # Naudojame didesnį diapazoną (iki 10^6), kad rodytų pilnus skaičius
                    ax.ticklabel_format(style='sci', scilimits=(-3, 6), axis='x')
                
                if ax.get_yscale() == 'log':
                    pass 
                elif selected_graphs[i] in ["phase_f", "nyquist", "cole_cole", "bode_dual"]: 
                    # Šiems grafikams visada naudojame pilnus skaičius
                    ax.ticklabel_format(style='plain', axis='y')
                    if hasattr(ax, '_ax_th'):
                        ax._ax_th.ticklabel_format(style='plain', axis='y')
                else: 
                    ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                    ax.ticklabel_format(style='sci', scilimits=(-3, 6), axis='y')
                
                ax.grid(True, which='both', alpha=0.2)

            # Viena bendra legenda matricai dešinėje pusėje
            legend_drawn = False
            for i, g in enumerate(selected_graphs):
                # Naudojame pirmą tinkamą grafiką legendos rodymui
                if g in ["nyquist", "bode_dual", "z_real_imag_f"]:
                    target_ax = ax_f[i]
                    handles, labels = target_ax.get_legend_handles_labels()
                    # Jei yra dešinioji ašis, pridedame jos įrašus į legendą
                    if hasattr(target_ax, '_ax_th'):
                        h2, l2 = target_ax._ax_th.get_legend_handles_labels()
                        handles += h2
                        labels += l2
                    if handles:
                        target_ax.legend(handles, labels, fontsize='7', loc='center left', bbox_to_anchor=(1.05, 0.5))
                        legend_drawn = True
                    break
            
            # Jei neradome prioritetinių grafikų, dedame ant pirmo ašies
            if not legend_drawn:
                for ax in ax_f:
                    handles, labels = ax.get_legend_handles_labels()
                    if hasattr(ax, '_ax_th'):
                        h2, l2 = ax._ax_th.get_legend_handles_labels()
                        handles += h2
                        labels += l2
                    if handles:
                        ax.legend(handles, labels, fontsize='7', loc='center left', bbox_to_anchor=(1.05, 0.5))
                        legend_drawn = True
                        break

            # Canvas ir Toolbar (Pakeista krovimo tvarka, kad matytųsi)
            toolbar_frame = tk.Frame(plot_window)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
            
            canvas_agg = FigureCanvasTkAgg(self.fig, master=plot_window)
            canvas_agg.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            toolbar = NavigationToolbar2Tk(canvas_agg, toolbar_frame)
            toolbar.update()

            canvas_agg.mpl_connect('pick_event', self.on_point_pick)
            canvas_agg.mpl_connect('button_press_event', self.on_plot_click)
            
            # Išsaugome nuorodą į canvas, kad draw() veiktų
            self.fig.canvas = canvas_agg
            plot_window.update()
            # 1px refreshas
            plot_window.geometry(f"{w}x{h+1}")
            plot_window.update()
            plot_window.geometry(f"{w}x{h}")
            canvas_agg.draw()
            
            plot_window.attributes('-topmost', False) # Atstatome
            plot_window.lift()
            plot_window.focus_force()
            
        except Exception as e:
            messagebox.showerror("Grafiko klaida", f"Nepavyko atidaryti grafiko:\n{str(e)}\n\n{traceback.format_exc()}")


    def on_point_pick(self, event):
        # Point picker veikia tik su kairiuoju pelės mygtuku (button 1)
        if event.mouseevent.button != 1:
            return
            
        temp_gid, ind = event.artist.get_gid(), event.ind[0]
        temp_val = float(temp_gid)
        for m in self.highlight_markers: m.remove()
        self.highlight_markers = []
        try:
            d = next(x for x in self.data_plots if abs(float(x['temp']) - temp_val) < 0.01)
        except StopIteration:
            return
        
        info = (f"T={format_comma(temp_val,2)}K | f={to_sci_unicode(d['f'][ind])}Hz | Θ={format_comma(d['th'][ind], 2, True)}\n"
                f"Z'={to_sci_unicode(d['z'][ind].real)} | Z''={to_sci_unicode(d['z'][ind].imag)} | |Z|={to_sci_unicode(d['abs_Z'][ind])}\n"
                f"ε'={to_sci_unicode(d['ep'][ind])} | ε''={to_sci_unicode(d['edp'][ind])} | σ'={to_sci_unicode(d['sp'][ind])} | M''={to_sci_unicode(d['mdp'][ind])}\n"
                f"tan δ={to_sci_unicode(d['tan_delta'][ind])} | dZ'={to_sci_unicode(d['pseudo_drt'][ind])}\n"
                f"Lanko R ≈ {to_sci_unicode(self.estimate_arc_width(d['z']))} Ω·m")
        self.table_text.set_text(info)
        
        # --- SINCHRONIZUOTAS TAŠKO ŽYMĖJIMAS VISUOSE 9 GRAFIKUOSE ---
        targets = []
        selected_graphs = [GRAPH_TYPES[var.get()] for var in self.graph_vars]
        
        for idx, g_type in zip(range(9), selected_graphs):
            ax = self.axes.flat[idx]
            if g_type == "Z_real_f": targets.append((ax, d['f'][ind], d['z'][ind].real))
            elif g_type == "Z_imag_f": targets.append((ax, d['f'][ind], -d['z'][ind].imag))
            elif g_type == "eps_real_f": targets.append((ax, d['f'][ind], d['ep'][ind]))
            elif g_type == "eps_imag_f": targets.append((ax, d['f'][ind], d['edp'][ind]))
            elif g_type == "sigma_f": targets.append((ax, d['f'][ind], d['sp'][ind]))
            elif g_type == "M_imag_f": targets.append((ax, d['f'][ind], d['mdp'][ind]))
            elif g_type == "tan_delta_f": targets.append((ax, d['f'][ind], d['tan_delta'][ind]))
            elif g_type == "norm_z_m_f": 
                targets.append((ax, d['f'][ind], d['z_norm'][ind]))
                targets.append((ax, d['f'][ind], d['m_norm'][ind]))
            elif g_type == "norm_z_f": targets.append((ax, d['f'][ind], d['z_norm'][ind]))
            elif g_type == "norm_m_f": targets.append((ax, d['f'][ind], d['m_norm'][ind]))
            elif g_type == "summerfield": targets.append((ax, d['sum_x'][ind], d['sum_y'][ind]))
            elif g_type == "pseudo_drt": targets.append((ax, d['f'][ind], d['pseudo_drt'][ind]))
            elif g_type == "nyquist": targets.append((ax, d['z'][ind].real, -d['z'][ind].imag))
            elif g_type == "abs_Z_f": targets.append((ax, d['f'][ind], d['abs_Z'][ind]))
            elif g_type == "phase_f": targets.append((ax, d['f'][ind], d['th'][ind]))
            elif g_type == "cole_cole": targets.append((ax, d['ep'][ind], d['edp'][ind]))

        for ax, x, y in targets:
            self.highlight_markers.append(ax.plot(x, y, 'ro', ms=10, mfc='none', mew=1.5)[0])
        self.fig.canvas.draw()

    def on_plot_click(self, event):
        if event.inaxes is None:
            return
            
        # Atidaro redagavimo meniu paspaudus DVIGUBĄ dešinį pelės mygtuką (button 3)
        if event.button == 3:
            current_time = time.time()
            if current_time - self.last_right_click_time < 0.5:
                self.right_click_count += 1
            else:
                self.right_click_count = 1
            self.last_right_click_time = current_time
            
            if self.right_click_count == 2:
                self.right_click_count = 0
                self.open_edit_graph_dialog(event.inaxes)

    def apply_thermal_palette(self, ax, palette_name, show_colorbar=True, custom_colors=None):
        """Pritaiko terminę spalvų paletę grafikui pagal temperatūrą (gid)."""
        ax._pyeis_palette = palette_name
        ax._pyeis_custom_colors = custom_colors
        lines_data = []
        all_lines = list(ax.get_lines())
        if hasattr(ax, '_ax_th'):
            all_lines.extend(ax._ax_th.get_lines())
            
        for line in all_lines:
            gid = line.get_gid()
            if gid is not None:
                try:
                    t = float(gid)
                    if not hasattr(line, '_original_color'):
                        line._original_color = line.get_color()
                    lines_data.append((line, t))
                except (ValueError, TypeError):
                    continue
        
        if not lines_data:
            return
            
        if palette_name == "original":
            for line, t in lines_data:
                if hasattr(line, '_original_color'):
                    line.set_color(line._original_color)
            if hasattr(ax, '_pyeis_colorbar_axes'):
                try:
                    ax._pyeis_colorbar_axes.remove()
                    delattr(ax, '_pyeis_colorbar_axes')
                except: pass
            return

        temps = [d[1] for d in lines_data]
        t_min, t_max = min(temps), max(temps)
        norm = mcolors.Normalize(vmin=t_min, vmax=t_max)
        
        if palette_name == 'ironbow':
            cmap = ironbow_cmap
        elif palette_name == 'arctic':
            cmap = arctic_cmap
        elif palette_name == 'custom' and custom_colors:
            cmap = mcolors.LinearSegmentedColormap.from_list('custom_thermal', [custom_colors[0], custom_colors[1]])
        else: # rainbow
            cmap = plt.get_cmap('turbo')
            
        for line, t in lines_data:
            line.set_color(cmap(norm(t)))
            
        if hasattr(ax, '_pyeis_colorbar_axes'):
            try:
                ax._pyeis_colorbar_axes.remove()
                delattr(ax, '_pyeis_colorbar_axes')
            except: pass
            
        if show_colorbar:
            # Naudojame inset_axes už grafiko ribų, kad nesumažėtų pagrindinis grafikas
            from mpl_toolkits.axes_grid1.inset_locator import inset_axes
            cb_ax = ax.inset_axes([1.02, 0, 0.04, 1.0], transform=ax.transAxes)
            
            sm = ScalarMappable(norm=norm, cmap=cmap)
            sm.set_array([])
            cb = ax.figure.colorbar(sm, cax=cb_ax, orientation='vertical')
            cb.set_label('Temperatūra, K', fontsize=9)
            cb.ax.tick_params(labelsize=8)
            ax._pyeis_colorbar_axes = cb_ax


    def open_edit_graph_dialog(self, ax):
        if hasattr(ax, '_ax_primary'):
            ax = ax._ax_primary
            
        dlg = tk.Toplevel(self.root)
        dlg.title("Redaguoti ir eksportuoti grafiką")
        self.center_window(dlg, 600, 800)
        
        # Fiksuotas rėmelis mygtukams apačioje (pakuojame pirmą)
        bottom_frame = tk.Frame(dlg, pady=20, bg="#dddddd")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Funkcijų aprašymai (perkelti į viršų, kad būtų saugiau)
        def apply_changes():
            try:
                ax.set_title(title_var.get())
                ax.set_xlabel(xlabel_var.get())
                ax.set_ylabel(ylabel_var.get())
                if is_3d:
                    ax.set_zlabel(zlabel_var.get())
                
                ax.set_xlim(float(xmin_var.get()), float(xmax_var.get()))
                ax.set_ylim(float(ymin_var.get()), float(ymax_var.get()))
                if is_3d:
                    ax.set_zlim(float(zmin_var.get()), float(zmax_var.get()))
                    
                ax.set_xscale(xscale_var.get())
                ax.set_yscale(yscale_var.get())
                
                # Invertuojame ašis jei reikia
                if inv_x_var.get() != ax.xaxis_inverted():
                    ax.invert_xaxis()
                if inv_y_var.get() != ax.yaxis_inverted():
                    ax.invert_yaxis()
                if is_3d:
                    if inv_z_var.get() != ax.zaxis_inverted():
                        ax.invert_zaxis()
                
                # Nustatome labelpad
                lp = labelpad_var.get()
                ax.xaxis.labelpad = lp
                ax.yaxis.labelpad = lp
                if is_3d:
                    ax.zaxis.labelpad = lp
                    
                    # 3D Stabilizacija
                    if stabilize_var.get():
                        ax.xaxis.set_rotate_label(False)
                        ax.yaxis.set_rotate_label(False)
                        ax.zaxis.set_rotate_label(False)
                
                if ax.get_xscale() == 'log':
                    ax.xaxis.set_major_formatter(ticker.LogFormatterSciNotation())
                else:
                    ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                    ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='x')
                
                if ax.get_yscale() == 'log':
                    pass
                else:
                    if ylabel_var.get() == "Θ [°]":
                        ax.ticklabel_format(style='plain', axis='y')
                    else:
                        ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                        ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='y')

                if legend_var.get():
                    handles, labels = ax.get_legend_handles_labels()
                    if hasattr(ax, '_ax_th'):
                        h2, l2 = ax._ax_th.get_legend_handles_labels()
                        handles += h2
                        labels += l2
                    if handles:
                        handles_labels = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]
                        if handles_labels:
                            hl, ll = zip(*handles_labels)
                            ax.legend(hl, ll, fontsize=8, loc='best')
                else:
                    leg = ax.get_legend()
                    if leg:
                        leg.remove()

                pal = palette_var.get()
                cb = colorbar_var.get()
                cust = (min_color.get(), max_color.get())
                if apply_all_var.get():
                    for a in ax.figure.axes:
                        if a.get_lines() and not hasattr(a, '_colorbar_ax'):
                            self.apply_thermal_palette(a, pal, cb, cust)
                else:
                    self.apply_thermal_palette(ax, pal, cb, cust)
                    
                ax.figure.canvas.draw_idle()
                # Sėkmės indikacija ant mygtuko
                update_btn.config(bg="#43A047", text="Atnaujinta! ✅")
                dlg.after(2000, lambda: update_btn.config(bg="#1976D2", text="Atnaujinti"))
            except Exception as e:
                messagebox.showerror("Klaida", f"Klaida atnaujinant: {e}", parent=dlg)

        def export_graph():
            filetypes = (
                ("PNG paveikslėlis", "*.png"), ("PDF dokumentas", "*.pdf"),
                ("SVG vektorinis", "*.svg"), ("EPS formatas", "*.eps"), ("Visi failai", "*.*")
            )
            filepath = filedialog.asksaveasfilename(title="Eksportuoti grafiką", defaultextension=".png", filetypes=filetypes, parent=dlg)
            if not filepath: return
            try:
                apply_changes()
                fig = ax.figure
                orig_size = fig.get_size_inches()
                orig_pos = ax.get_position()
                orig_axes_vis = {a: a.get_visible() for a in fig.axes}
                cb_ax = getattr(ax, '_pyeis_colorbar_axes', None)
                twin_ax = getattr(ax, '_ax_th', None)
                for other_ax in fig.axes:
                    if other_ax != ax and other_ax != cb_ax and other_ax != twin_ax: 
                        other_ax.set_visible(False)
                orig_texts_vis = {t: t.get_visible() for t in fig.texts}
                for t in fig.texts: t.set_visible(False)
                try:
                    ew, eh = float(width_var.get()), float(height_var.get())
                except: ew, eh = 8.0, 6.0
                fig.set_size_inches((ew, eh))
                if cb_ax: 
                    new_pos = [0.12, 0.12, 0.73, 0.80]
                else: 
                    new_pos = [0.12, 0.12, 0.80, 0.80]
                
                ax.set_position(new_pos)
                if twin_ax:
                    twin_ax.set_position(new_pos)
                    twin_ax.patch.set_visible(False) # Užtikriname skaidrumą
                
                fig.savefig(filepath, dpi=300, bbox_inches='tight', pad_inches=0.08)
                fig.set_size_inches(orig_size)
                ax.set_position(orig_pos)
                if twin_ax: twin_ax.set_position(orig_pos)
                for a in fig.axes: a.set_visible(orig_axes_vis[a])
                for t in fig.texts: t.set_visible(orig_texts_vis[t])
                fig.canvas.draw_idle()
                
                # Sėkmės indikacija ant mygtuko vietoj popup lango
                export_btn.config(bg="#43A047", text="Eksportuota! ✅")
                dlg.after(3000, lambda: export_btn.config(bg="#546E7A", text="Eksportuoti..."))
            except Exception as e:
                messagebox.showerror("Eksporto klaida", f"Klaida: {e}", parent=dlg)

        def copy_to_clipboard():
            try:
                apply_changes()
                fig = ax.figure
                orig_size = fig.get_size_inches()
                orig_pos = ax.get_position()
                orig_axes_vis = {a: a.get_visible() for a in fig.axes}
                cb_ax = getattr(ax, '_pyeis_colorbar_axes', None)
                twin_ax = getattr(ax, '_ax_th', None)
                for other_ax in fig.axes:
                    if other_ax != ax and other_ax != cb_ax and other_ax != twin_ax: 
                        other_ax.set_visible(False)
                orig_texts_vis = {t: t.get_visible() for t in fig.texts}
                for t in fig.texts: t.set_visible(False)
                try: ew, eh = float(width_var.get()), float(height_var.get())
                except: ew, eh = 8.0, 6.0
                fig.set_size_inches((ew, eh))
                if cb_ax: 
                    new_pos = [0.12, 0.12, 0.73, 0.80]
                else: 
                    new_pos = [0.12, 0.12, 0.80, 0.80]
                
                ax.set_position(new_pos)
                if twin_ax:
                    twin_ax.set_position(new_pos)
                    twin_ax.patch.set_visible(False)
                    
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp: tmp_path = tmp.name
                fig.savefig(tmp_path, dpi=300, bbox_inches='tight', pad_inches=0.08)
                ps_cmd = f'powershell -command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile(\'{tmp_path}\'))"'
                subprocess.run(ps_cmd, shell=True)
                fig.set_size_inches(orig_size)
                ax.set_position(orig_pos)
                if twin_ax: twin_ax.set_position(orig_pos)
                for a in fig.axes: a.set_visible(orig_axes_vis[a])
                for t in fig.texts: t.set_visible(orig_texts_vis[t])
                fig.canvas.draw_idle()
                if os.path.exists(tmp_path): os.remove(tmp_path)
                
                # Sėkmės indikacija ant mygtuko vietoj popup lango
                copy_btn.config(bg="#43A047", text="Nukopijuota! ✅")
                dlg.after(2000, lambda: copy_btn.config(bg="#FF8F00", text="Kopijuoti (📋)"))
            except Exception as e:
                messagebox.showerror("Klaida", f"Klaida: {e}", parent=dlg)

        # Mygtukų kūrimas
        update_btn = tk.Button(bottom_frame, text="Atnaujinti", command=apply_changes, bg="#1976D2", fg="white", font=('Arial', 10, 'bold'), width=12)
        update_btn.pack(side="left", padx=20)
        copy_btn = tk.Button(bottom_frame, text="Kopijuoti (📋)", command=copy_to_clipboard, bg="#FF8F00", fg="white", font=('Arial', 10, 'bold'), width=12)
        copy_btn.pack(side="left", padx=5)
        export_btn = tk.Button(bottom_frame, text="Eksportuoti...", command=export_graph, bg="#546E7A", fg="white", font=('Arial', 10, 'bold'), width=15)
        export_btn.pack(side="left", padx=5)

        # Pagrindinis konteineris likusiai vietai
        main_container = tk.Frame(dlg)
        main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Scrollable sritis nustatymams
        canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas)
        
        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_content, anchor="nw", width=580)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Pelės ratuko palaikymas (su apsauga nuo klaidų uždarius langą)
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass
        dlg.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Pagrindinis rėmelis turiniui
        content = scroll_content
        
        is_3d = hasattr(ax, 'get_zlim')

        # Title
        tk.Label(content, text="Grafiko pavadinimas:", font=('Arial', 9, 'bold')).pack(pady=(10, 0), anchor='w', padx=20)
        title_var = tk.StringVar(value=ax.get_title())
        tk.Entry(content, textvariable=title_var, width=50).pack(padx=20)

        # X Label
        tk.Label(content, text="X ašies pavadinimas:", font=('Arial', 9, 'bold')).pack(pady=(10, 0), anchor='w', padx=20)
        xlabel_var = tk.StringVar(value=ax.get_xlabel())
        tk.Entry(content, textvariable=xlabel_var, width=50).pack(padx=20)

        # Y Label
        tk.Label(content, text="Y ašies pavadinimas:", font=('Arial', 9, 'bold')).pack(pady=(10, 0), anchor='w', padx=20)
        ylabel_var = tk.StringVar(value=ax.get_ylabel())
        tk.Entry(content, textvariable=ylabel_var, width=50).pack(padx=20)
        
        # Z Label
        if is_3d:
            tk.Label(content, text="Z ašies pavadinimas:", font=('Arial', 9, 'bold')).pack(pady=(10, 0), anchor='w', padx=20)
            zlabel_var = tk.StringVar(value=ax.get_zlabel())
            tk.Entry(content, textvariable=zlabel_var, width=50).pack(padx=20)

        # Label distance (labelpad)
        tk.Label(content, text="Pavadinimų atstumas nuo ašies (Labelpad):", font=('Arial', 9, 'bold')).pack(pady=(10, 0), anchor='w', padx=20)
        try:
            current_pad = ax.xaxis.labelpad
        except:
            current_pad = 10.0
        labelpad_var = tk.DoubleVar(value=current_pad)
        tk.Entry(content, textvariable=labelpad_var, width=10).pack(padx=20, anchor='w')

        # Limits
        lim_frame = tk.Frame(content)
        lim_frame.pack(pady=10, padx=20, fill='x')

        tk.Label(lim_frame, text="X min:").grid(row=0, column=0, sticky='e', padx=5, pady=2)
        xmin_var = tk.StringVar(value=str(ax.get_xlim()[0]))
        tk.Entry(lim_frame, textvariable=xmin_var, width=12).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(lim_frame, text="X max:").grid(row=0, column=2, sticky='e', padx=5, pady=2)
        xmax_var = tk.StringVar(value=str(ax.get_xlim()[1]))
        tk.Entry(lim_frame, textvariable=xmax_var, width=12).grid(row=0, column=3, padx=5, pady=2)

        tk.Label(lim_frame, text="Y min:").grid(row=1, column=0, sticky='e', padx=5, pady=2)
        ymin_var = tk.StringVar(value=str(ax.get_ylim()[0]))
        tk.Entry(lim_frame, textvariable=ymin_var, width=12).grid(row=1, column=1, padx=5, pady=2)

        tk.Label(lim_frame, text="Y max:").grid(row=1, column=2, sticky='e', padx=5, pady=2)
        ymax_var = tk.StringVar(value=str(ax.get_ylim()[1]))
        tk.Entry(lim_frame, textvariable=ymax_var, width=12).grid(row=1, column=3, padx=5, pady=2)
        
        if is_3d:
            tk.Label(lim_frame, text="Z min:").grid(row=2, column=0, sticky='e', padx=5, pady=2)
            zmin_var = tk.StringVar(value=str(ax.get_zlim()[0]))
            tk.Entry(lim_frame, textvariable=zmin_var, width=12).grid(row=2, column=1, padx=5, pady=2)
            
            tk.Label(lim_frame, text="Z max:").grid(row=2, column=2, sticky='e', padx=5, pady=2)
            zmax_var = tk.StringVar(value=str(ax.get_zlim()[1]))
            tk.Entry(lim_frame, textvariable=zmax_var, width=12).grid(row=2, column=3, padx=5, pady=2)

        # Scales
        scale_frame = tk.Frame(content)
        scale_frame.pack(pady=5, padx=20, fill='x')
        
        tk.Label(scale_frame, text="X ašies skalė:").grid(row=0, column=0, sticky='e', padx=5)
        xscale_var = tk.StringVar(value=ax.get_xscale())
        ttk.Combobox(scale_frame, textvariable=xscale_var, values=["linear", "log"], width=10, state="readonly").grid(row=0, column=1, padx=5)
        
        tk.Label(scale_frame, text="Y ašies skalė:").grid(row=0, column=2, sticky='e', padx=5)
        yscale_var = tk.StringVar(value=ax.get_yscale())
        ttk.Combobox(scale_frame, textvariable=yscale_var, values=["linear", "log"], width=10, state="readonly").grid(row=0, column=3, padx=5)

        # Inversion Frame
        inv_frame = tk.LabelFrame(content, text="Ašių kryptis (Invertuoti)", font=('Arial', 9, 'bold'), padx=10, pady=5)
        inv_frame.pack(pady=5, padx=20, fill='x')
        
        inv_x_var = tk.BooleanVar(value=bool(ax.xaxis_inverted()))
        tk.Checkbutton(inv_frame, text="Invertuoti X", variable=inv_x_var).grid(row=0, column=0, sticky='w', padx=5)
        
        inv_y_var = tk.BooleanVar(value=bool(ax.yaxis_inverted()))
        tk.Checkbutton(inv_frame, text="Invertuoti Y", variable=inv_y_var).grid(row=0, column=1, sticky='w', padx=5)
        
        if is_3d:
            inv_z_var = tk.BooleanVar(value=bool(ax.zaxis_inverted()))
            tk.Checkbutton(inv_frame, text="Invertuoti Z", variable=inv_z_var).grid(row=0, column=2, sticky='w', padx=5)

        # Legend
        legend_var = tk.BooleanVar(value=ax.get_legend() is not None)
        tk.Checkbutton(content, text="Rodyti legendą grafike", variable=legend_var, font=('Arial', 9, 'bold')).pack(pady=5, anchor='w', padx=20)

        # 3D Settings Frame
        if is_3d:
            threed_frame = tk.LabelFrame(content, text="3D grafiko nustatymai", font=('Arial', 9, 'bold'), padx=10, pady=10)
            threed_frame.pack(pady=10, padx=20, fill='x')
            
            stabilize_var = tk.BooleanVar(value=True)
            tk.Checkbutton(threed_frame, text="Stabilizuoti ašių vietas (fiksuoti)", variable=stabilize_var).grid(row=0, column=0, sticky='w')
            
            tk.Label(threed_frame, text="Z ašies pusė:").grid(row=1, column=0, sticky='w', pady=(5,0))
            z_pos_var = tk.StringVar(value="left")
            ttk.Combobox(threed_frame, textvariable=z_pos_var, values=["left", "right"], width=10, state="readonly").grid(row=1, column=1, sticky='w', pady=(5,0))

        # Palette Frame
        pal_frame = tk.LabelFrame(content, text="Terminės paletės (pagal temperatūrą)", font=('Arial', 9, 'bold'), padx=10, pady=10)
        pal_frame.pack(pady=10, padx=20, fill='x')
        
        palette_var = tk.StringVar(value=getattr(ax, '_pyeis_palette', 'original'))
        ttk.Radiobutton(pal_frame, text="Originalios spalvos", variable=palette_var, value="original").grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(pal_frame, text="Ironbow", variable=palette_var, value="ironbow").grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(pal_frame, text="Rainbow", variable=palette_var, value="rainbow").grid(row=1, column=0, sticky='w')
        ttk.Radiobutton(pal_frame, text="Arctic", variable=palette_var, value="arctic").grid(row=1, column=1, sticky='w')
        ttk.Radiobutton(pal_frame, text="Jūsų paletė", variable=palette_var, value="custom").grid(row=2, column=0, sticky='w')
        
        # Custom color pickers
        custom_frame = tk.Frame(pal_frame)
        custom_frame.grid(row=2, column=1, sticky='w')
        
        cust_colors = getattr(ax, '_pyeis_custom_colors', ("#0000FF", "#FF0000"))
        if not cust_colors: cust_colors = ("#0000FF", "#FF0000")
        min_color = tk.StringVar(value=cust_colors[0])
        max_color = tk.StringVar(value=cust_colors[1])
        
        def choose_min():
            color = colorchooser.askcolor(title="Zemiausios T spalva", parent=dlg)[1]
            if color: 
                min_color.set(color)
                min_btn.config(bg=color)
                
        def choose_max():
            color = colorchooser.askcolor(title="Auksciausios T spalva", parent=dlg)[1]
            if color: 
                max_color.set(color)
                max_btn.config(bg=color)

        min_btn = tk.Button(custom_frame, text="Min T", bg=min_color.get(), width=5, command=choose_min)
        min_btn.pack(side=tk.LEFT, padx=2)
        max_btn = tk.Button(custom_frame, text="Max T", bg=max_color.get(), width=5, command=choose_max)
        max_btn.pack(side=tk.LEFT, padx=2)

        colorbar_var = tk.BooleanVar(value=hasattr(ax, '_pyeis_colorbar_axes'))
        tk.Checkbutton(pal_frame, text="Rodyti spalvų skalę (Colorbar)", variable=colorbar_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=(5,0))
        
        apply_all_var = tk.BooleanVar(value=False)
        tk.Checkbutton(pal_frame, text="Taikyti visiems lango polankiams", variable=apply_all_var).grid(row=4, column=0, columnspan=2, sticky='w')

        # Export Size
        size_frame = tk.Frame(content)
        size_frame.pack(pady=10, padx=20, fill='x')
        tk.Label(size_frame, text="Eksportuojamo grafiko dydis (coliais):", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 5))
        
        tk.Label(size_frame, text="Plotis:").grid(row=1, column=0, sticky='e', padx=5)
        width_var = tk.StringVar(value="8.0")
        tk.Entry(size_frame, textvariable=width_var, width=8).grid(row=1, column=1, padx=5)
        
        tk.Label(size_frame, text="Aukštis:").grid(row=1, column=2, sticky='e', padx=5)
        height_var = tk.StringVar(value="6.0")
        tk.Entry(size_frame, textvariable=height_var, width=8).grid(row=1, column=3, padx=5)


    # ─── AŠIŲ RINKINYS ────────────────────────────────────────────────────────
    AXIS_OPTIONS = {
        "f – dažnio": "f",
        "Z' – realiosios": "Zr",
        "-Z'' – menamosios": "Zi",
        "|Z| – modulio": "absZ",
        "ε' – dielektrinės": "ep",
        "ε'' – nuostolių": "edp",
        "σ' – laidumo": "sp",
        "M'' – modulio": "mdp",
        "-Θ – fazės kampo": "th",
        "tanδ – nuostolių tang.": "tan_delta",
        "Z''/Z''max": "z_norm",
        "M''/M''max": "m_norm",
        "Pseudo-DRT": "pseudo_drt",
        "T – temperatūra": "T",
        "1000/T": "T_inv",
    }

    AXIS_LABELS = {
        "f":          "f [Hz]",
        "Zr":         "Z' [Ω·m]",
        "Zi":         "-Z'' [Ω·m]",
        "absZ":       "|Z| [Ω·m]",
        "ep":         "ε' [vnt.]",
        "edp":        "ε'' [vnt.]",
        "sp":         "σ' [S/m]",
        "mdp":        "M'' [vnt.]",
        "th":         "-Θ [°]",
        "tan_delta":  "tanδ",
        "z_norm":     r"$Z''/Z''_{max}$",
        "m_norm":     r"$M''/M''_{max}$",
        "pseudo_drt": "-dZ'/d(log f)",
        "T":          "T [K]",
        "T_inv":      "1000/T [K⁻¹]",
    }

    def _get_axis_data(self, key, f, z, d):
        """Grąžina duomenų vektoriuš pagal riešutinį."""
        if key == "f":          return f
        if key == "Zr":         return z.real
        if key == "Zi":         return -z.imag
        if key == "absZ":       return np.abs(z)
        if key == "ep":         return d['ep']
        if key == "edp":        return d['edp']
        if key == "sp":         return d['sp']
        if key == "mdp":        return d['mdp']
        if key == "th":         return d['th']
        if key == "tan_delta":  return d['tan_delta']
        if key == "z_norm":     return d['z_norm']
        if key == "m_norm":     return d['m_norm']
        if key == "pseudo_drt": return d['pseudo_drt']
        return None  # T ir T_inv tvarkomi aukščiau

    def open_custom_plot(self):
        selected = sorted([t for t, v in self.vars.items() if v.get()])
        if not selected:
            messagebox.showwarning("Dėmesio", "Pasirinkite bent vieną temperatūrą!")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Savo grafiko kūrimas")
        self.center_window(dlg, 700, 400)
        dlg.resizable(False, False)

        axis_names = list(self.AXIS_OPTIONS.keys())

        tk.Label(dlg, text="X ašis:", font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=10, pady=6, sticky='e')
        x_var = tk.StringVar(value=axis_names[0])
        ttk.Combobox(dlg, textvariable=x_var, values=axis_names, width=26, state='readonly').grid(row=0, column=1, padx=10, pady=6)

        tk.Label(dlg, text="Y ašis:", font=('Arial', 9, 'bold')).grid(row=1, column=0, padx=10, pady=6, sticky='e')
        y_var = tk.StringVar(value=axis_names[2])
        ttk.Combobox(dlg, textvariable=y_var, values=axis_names, width=26, state='readonly').grid(row=1, column=1, padx=10, pady=6)

        tk.Label(dlg, text="Z ašis (3D, nebūtina):", font=('Arial', 9, 'bold')).grid(row=2, column=0, padx=10, pady=6, sticky='e')
        z_var = tk.StringVar(value="– nėra –")
        ttk.Combobox(dlg, textvariable=z_var, values=["– nėra –"] + axis_names, width=26, state='readonly').grid(row=2, column=1, padx=10, pady=6)

        def draw():
            xk = self.AXIS_OPTIONS[x_var.get()]
            yk = self.AXIS_OPTIONS[y_var.get()]
            use_z = z_var.get() != "– nėra –"
            zk = self.AXIS_OPTIONS.get(z_var.get()) if use_z else None

            k_LA, k_AL = self._get_geometric_factors()
            
            # Apskaičiuojame duomenis kiekvienai temperatūrai
            datasets = []
            for temp in selected:
                f, z = self.get_filtered_data(temp)
                if len(f) < 1: continue
                
                z_n = z * k_AL
                w = 2 * np.pi * f
                mod_sq_n = z_n.real**2 + z_n.imag**2
                
                ep  = -z_n.imag / (w * EPSILON_0 * mod_sq_n)
                edp =  z_n.real / (w * EPSILON_0 * mod_sq_n)
                sp  =  z_n.real / mod_sq_n
                mdp =  w * EPSILON_0 * z_n.real
                th  =  np.degrees(np.arctan2(z_n.imag, z_n.real))
                tan_d = np.where(ep != 0, edp / ep, 0.0)
                z_n_abs_imag = np.abs(z_n.imag)
                z_n_max_imag = np.max(z_n_abs_imag) if np.max(z_n_abs_imag) != 0 else 1
                z_n_plot = z_n_abs_imag / z_n_max_imag
                m_n = mdp / (np.max(mdp) if np.max(mdp) != 0 else 1)
                logf = np.log10(f)
                pseudo_drt = -np.gradient(z_n.real, logf)

                d = dict(ep=ep, edp=edp, sp=sp, mdp=mdp, th=th,
                         tan_delta=tan_d, z_norm=z_n_plot, m_norm=m_n, pseudo_drt=pseudo_drt)

                def get(key):
                    if key == "f":      return f
                    if key == "Zr":     return z.real
                    if key == "Zi":     return -z.imag
                    if key == "absZ":   return np.abs(z)
                    if key == "T":      return np.full(len(f), temp)
                    if key == "T_inv":  return np.full(len(f), 1000.0 / temp)
                    return d.get(key, f)

                xd, yd = get(xk), get(yk)
                zd = get(zk) if use_z else None
                datasets.append((temp, xd, yd, zd))

            if not datasets:
                messagebox.showwarning("Dėmesio", "Nėra duomenų braižymui.", parent=dlg)
                return

            # Sukuriame naują langą
            sw = tk.Toplevel(self.root)
            sw.title("Savęs grafikas")
            self.center_window(sw, 1000, 750)

            fig = Figure(figsize=(9, 6), dpi=100, facecolor='white')
            xlabel = self.AXIS_LABELS[xk]
            ylabel = self.AXIS_LABELS[yk]

            if use_z:
                ax = fig.add_subplot(111, projection='3d')
                zlabel = self.AXIS_LABELS[zk]
                # Stock spalvos (C0, C1, ...)
                temp_to_color = {t: f"C{i % 10}" for i, t in enumerate(selected)}
                for temp, xd, yd, zd in datasets:
                    color = temp_to_color[temp] if len(selected) > 1 else '#1f77b4'
                    ax.plot(xd, yd, zd, 'o-', ms=2, lw=0.8, color=color, label=f"{temp:g} K")
                ax.set_zlabel(zlabel)
                ax.set_title(f"{xlabel} / {ylabel} / {zlabel}")
            else:
                ax = fig.add_subplot(111)
                # Stock spalvos (C0, C1, ...)
                temp_to_color = {t: f"C{i % 10}" for i, t in enumerate(selected)}
                for temp, xd, yd, _ in datasets:
                    color = temp_to_color[temp] if len(selected) > 1 else '#1f77b4'
                    ax.plot(xd, yd, 'o-', ms=2, lw=0.8, color=color, label=f"{temp:g} K")
                ax.set_title(f"{xlabel} vs {ylabel}")

            ax.set_xlabel(xlabel, labelpad=15, rotation=0)
            ax.set_ylabel(ylabel, labelpad=15, rotation=0)
            if use_z:
                ax.set_zlabel(zlabel, labelpad=15, rotation=90)
                ax.xaxis.set_rotate_label(False)
                ax.yaxis.set_rotate_label(False)
                ax.zaxis.set_rotate_label(False)
            ax.grid(True, alpha=0.3)
            if len(selected) <= 20:
                ax.legend(fontsize=7, loc='best')
            fig.tight_layout()
            
            canvas = FigureCanvasTkAgg(fig, master=sw)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            toolbar = NavigationToolbar2Tk(canvas, sw)
            toolbar.update()
            sw.update()
            # 1px refreshas
            sw.geometry(f"1001x751")
            sw.update()
            sw.geometry(f"1000x750")
            canvas.draw()

        tk.Button(dlg, text="Braižyti", command=draw,
                  bg="#00695C", fg="white", font=('Arial', 10, 'bold'), width=20).grid(
                  row=3, column=0, columnspan=2, pady=12)

    def open_3d_plots(self):
        try:
            selected = sorted([t for t, v in self.vars.items() if v.get()])
            if len(selected) < 2:
                messagebox.showwarning("Dėmesio", "3D analizei reikia pasirinkti bent 2 temperatūras!")
                return
                
            all_f_min = max([min(self.get_filtered_data(t)[0]) for t in selected if len(self.get_filtered_data(t)[0]) > 0])
            all_f_max = min([max(self.get_filtered_data(t)[0]) for t in selected if len(self.get_filtered_data(t)[0]) > 0])
            
            n_pts = min(60, max(30, 200 // max(len(selected), 1)))
            f_common = np.logspace(np.log10(all_f_min), np.log10(all_f_max), n_pts)
            log_f_common = np.log10(f_common)
            
            Z_real_grid = []
            Z_imag_grid = []
            M_imag_grid = []
            Sigma_grid = []
            Pseudo_drt_grid = []
            Z_norm_grid = []
            M_norm_grid = []
            Ep_grid = []
            Edp_grid = []
            Th_grid = []
            temps_valid = []
            
            k_LA, k_AL = self._get_geometric_factors()
            for temp in selected:
                f, z = self.get_filtered_data(temp)
                if len(f) < 2: continue
                
                # Normalizuojame impedansą pagal geometriją [Ω·m]
                z_n = z * k_AL
                
                w_rad = 2 * np.pi * f
                mod_sq_n = z_n.real**2 + z_n.imag**2
                sp = z_n.real / mod_sq_n
                mdp = (w_rad * EPSILON_0 * z_n.real)
                
                f_log_orig = np.log10(f)
                interp_zr_n = interp1d(f_log_orig, z_n.real, kind='linear', fill_value='extrapolate')
                interp_zi_n = interp1d(f_log_orig, z_n.imag, kind='linear', fill_value='extrapolate')
                interp_sp = interp1d(f_log_orig, np.log10(np.maximum(sp, 1e-15)), kind='linear', fill_value='extrapolate')
                interp_mdp = interp1d(f_log_orig, mdp, kind='linear', fill_value='extrapolate')
                
                zr_cn = interp_zr_n(log_f_common)
                zi_cn = interp_zi_n(log_f_common)
                sp_c = 10**interp_sp(log_f_common)
                mdp_c = interp_mdp(log_f_common)
                
                pseudo_drt_c = -np.gradient(zr_cn, log_f_common)
                
                w_c = 2 * np.pi * f_common
                mod_sq_cn = zr_cn**2 + zi_cn**2
                
                # Normalizacija paviršiams
                max_zi = np.max(np.abs(zi_cn)) if np.max(np.abs(zi_cn)) > 0 else 1
                z_norm_c = -zi_cn / max_zi
                mdp_cn = w_c * EPSILON_0 * zr_cn
                max_mdp = np.max(mdp_cn) if np.max(mdp_cn) > 0 else 1
                m_norm_c = mdp_cn / max_mdp
                
                ep_c = -zi_cn / (w_c * EPSILON_0 * mod_sq_cn)
                edp_c = zr_cn / (w_c * EPSILON_0 * mod_sq_cn)
                th_c = np.degrees(np.arctan2(zi_cn, zr_cn))
                
                Z_real_grid.append(zr_cn)
                Z_imag_grid.append(zi_cn)
                Sigma_grid.append(np.log10(np.maximum(sp_c, 1e-15)))
                M_imag_grid.append(mdp_cn)
                Pseudo_drt_grid.append(pseudo_drt_c)
                Z_norm_grid.append(z_norm_c)
                M_norm_grid.append(m_norm_c)
                Ep_grid.append(ep_c)
                Edp_grid.append(edp_c)
                Th_grid.append(th_c)
                temps_valid.append(temp)
                
            if not temps_valid: return
                
            T_grid, F_grid = np.meshgrid(temps_valid, log_f_common, indexing='ij')
            
            Z_real_grid = np.array(Z_real_grid)
            Z_imag_grid = np.array(Z_imag_grid)
            M_imag_grid = np.array(M_imag_grid)
            Sigma_grid = np.array(Sigma_grid)
            Pseudo_drt_grid = np.array(Pseudo_drt_grid)
            Z_norm_grid = np.array(Z_norm_grid)
            M_norm_grid = np.array(M_norm_grid)
            Ep_grid = np.array(Ep_grid)
            Edp_grid = np.array(Edp_grid)
            Th_grid = np.array(Th_grid)
            
            fig = Figure(figsize=(22, 12), dpi=100, facecolor='white')
            
            # 1. 3D Naikvisto-Bodė grafikas (Dažnio spiralė)
            ax1 = fig.add_subplot(251, projection='3d')
            t_min, t_max = min(temps_valid), max(temps_valid)
            norm = mcolors.Normalize(vmin=t_min, vmax=t_max)
            cmap_v = plt.cm.viridis
            for i, temp in enumerate(temps_valid):
                ax1.plot(Z_real_grid[i], -Z_imag_grid[i], log_f_common, label=f"{temp} K", color=cmap_v(norm(temp)))
            ax1.set_title("3D Naikvisto-Bodė spiralė")
            ax1.set_xlabel("Z', Ω·m")
            ax1.set_ylabel("-Z'', Ω·m")
            ax1.set_zlabel("log(f), Hz")
            
            # 2. Naikvisto evoliucija 3D
            ax2 = fig.add_subplot(252, projection='3d')
            for i, temp in enumerate(temps_valid):
                T_arr = np.full_like(Z_real_grid[i], temp)
                ax2.plot(Z_real_grid[i], -Z_imag_grid[i], T_arr, color=cmap_v(norm(temp)))
            ax2.set_title("Naikvisto evoliucija")
            ax2.set_xlabel("Z', Ω·m")
            ax2.set_ylabel("-Z'', Ω·m")
            ax2.set_zlabel("T, K")
            
            # 3. Cole-Cole 3D grafikas
            ax3 = fig.add_subplot(253, projection='3d')
            cmap_p = plt.cm.plasma
            for i, temp in enumerate(temps_valid):
                T_arr = np.full_like(Ep_grid[i], temp)
                ax3.plot(Ep_grid[i], Edp_grid[i], T_arr, color=cmap_p(norm(temp)))
            ax3.set_title("Cole-Cole 3D")
            ax3.set_xlabel("ε', vnt.")
            ax3.set_ylabel("ε'', vnt.")
            ax3.set_zlabel("T, K")
            
            # 4. Fazės kampo 3D grafikas
            ax4 = fig.add_subplot(254, projection='3d')
            cmap_i = plt.cm.inferno
            for i, temp in enumerate(temps_valid):
                T_arr = np.full_like(Th_grid[i], temp)
                ax4.plot(log_f_common, Th_grid[i], T_arr, color=cmap_i(norm(temp)))
            ax4.set_title("Fazės kampo 3D (-Θ)")
            ax4.set_xlabel("log(f), Hz")
            ax4.set_ylabel("-Θ, °")
            ax4.set_zlabel("T, K")
            
            # 5. Laidumo paviršius
            ax5 = fig.add_subplot(255, projection='3d')
            surf5 = ax5.plot_surface(F_grid, T_grid, Sigma_grid, cmap='viridis', edgecolor='none', shade=False, rcount=40, ccount=40)
            ax5.set_title("3D Kintamosios Srovės Laidumas")
            ax5.set_xlabel("log(f), Hz")
            ax5.set_ylabel("T, K")
            ax5.set_zlabel("log(σ'), S/m")
            
            # 6. Modulio paviršius
            ax6 = fig.add_subplot(256, projection='3d')
            surf6 = ax6.plot_surface(F_grid, T_grid, M_imag_grid, cmap='plasma', edgecolor='none', shade=False, rcount=40, ccount=40)
            ax6.set_title("Elektrinio Modulio Paviršius (M'')")
            ax6.set_xlabel("log(f), Hz")
            ax6.set_ylabel("T, K")
            ax6.set_zlabel("M'', vnt.")
            
            # 7. Pseudo-DRT paviršius
            ax7 = fig.add_subplot(257, projection='3d')
            surf7 = ax7.plot_surface(F_grid, T_grid, Pseudo_drt_grid, cmap='inferno', edgecolor='none', shade=False, rcount=40, ccount=40)
            ax7.set_title("Pseudo-DRT Temperatūrinis Reljefas")
            ax7.set_xlabel("log(f), Hz")
            ax7.set_ylabel("T, K")
            ax7.set_zlabel("-dZ'/d(log f)")
            
            T_inv_grid = 1000.0 / T_grid
            ax8 = fig.add_subplot(258, projection='3d')
            surf8 = ax8.plot_surface(F_grid, T_inv_grid, Sigma_grid, cmap='viridis', edgecolor='none', shade=False, rcount=40, ccount=40)
            ax8.set_title("Laidumo Žemėlapis")
            ax8.set_xlabel("log(f), Hz")
            ax8.set_ylabel("1000/T, K⁻¹")
            ax8.set_zlabel("log(σ'), S/m")
            
            # 9. Normalizuotas Z'' paviršius
            ax9 = fig.add_subplot(259, projection='3d')
            ax9.plot_surface(F_grid, T_grid, Z_norm_grid, cmap='viridis', edgecolor='none', alpha=0.8)
            ax9.set_title("Normalizuotas Z'' paviršius")
            ax9.set_xlabel("log(f), Hz")
            ax9.set_ylabel("T, K")
            ax9.set_zlabel("Z''/Z''max")
            
            # 10. Normalizuotas M'' paviršius
            ax10 = fig.add_subplot(2, 5, 10, projection='3d')
            ax10.plot_surface(F_grid, T_grid, M_norm_grid, cmap='plasma', edgecolor='none', alpha=0.8)
            ax10.set_title("Normalizuotas M'' paviršius")
            ax10.set_xlabel("log(f), Hz")
            ax10.set_ylabel("T, K")
            ax10.set_zlabel("M''/M''max")
            
            # --- 3D ašių nustatymai ---
            for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9, ax10]:
                ax.xaxis.labelpad = 12
                ax.yaxis.labelpad = 12
                ax.zaxis.labelpad = 12
                # Nustatome 10ⁿ formatą skaliems
                ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.zaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
                ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='both')
            
            # Sukuriame Toplevel langą
            sw = tk.Toplevel(self.root)
            sw.title("3D Išplėstinė EIS Analizė")
            
            # Naudojame adaptyvų lango dydį
            w, h = self.center_window(sw, 3200, 1800)
            
            dpi = 100
            fig.set_size_inches(w / dpi, h / dpi)
            fig.tight_layout()
            fig.subplots_adjust(top=0.92, bottom=0.08, left=0.05, right=0.95, hspace=0.3, wspace=0.3)
            
            # Toolbaras ir Canvas
            tb_frame = tk.Frame(sw)
            tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
            
            canvas = FigureCanvasTkAgg(fig, master=sw)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            tb = NavigationToolbar2Tk(canvas, tb_frame)
            tb.update()
            
            canvas.mpl_connect('button_press_event', self.on_plot_click)
            
            # Vieno pikselio "refresh" triukas lango išdėstymui (layout fix)
            sw.update()
            sw.geometry(f"{w}x{h+1}")
            sw.update()
            sw.geometry(f"{w}x{h}")
            canvas.draw()
            
        except Exception as e:
            messagebox.showerror("3D Analizės klaida", f"Nepavyko atidaryti 3D grafiko:\n{str(e)}\n\n{traceback.format_exc()}")

    def open_fast_3d_plot(self):
        selected = sorted([t for t, v in self.vars.items() if v.get()])
        if len(selected) < 2:
            messagebox.showwarning("Dėmesio", "3D analizei reikia pasirinkti bent 2 temperatūras!")
            return
            
        dlg = tk.Toplevel(self.root)
        dlg.title("Pasirinkite 3D Grafiką")
        self.center_window(dlg, 450, 200)
        
        tk.Label(dlg, text="Pasirinkite, kurį grafiką norite atidaryti greitos veikos režimu:", font=('Arial', 10)).pack(pady=10)
        
        plot_names = [
            "3D Naikvisto-Bodė spiralė", "Naikvisto evoliucija", "Cole-Cole 3D", "Fazės kampo 3D (-Θ)",
            "3D Kintamosios Srovės Laidumas", "Elektrinio Modulio Paviršius (M'')", 
            "Pseudo-DRT Temperatūrinis Reljefas", "Laidumo Žemėlapis (1000/T)",
            "Normalizuotas Z'' paviršius", "Normalizuotas M'' paviršius"
        ]
        
        combo = ttk.Combobox(dlg, values=plot_names, state="readonly", width=40)
        combo.current(0)
        combo.pack(pady=10)
        
        def run_fast_plot():
            plot_id = combo.current()
            dlg.destroy()
            self._launch_fast_3d_plot(selected, plot_id)
            
        tk.Button(dlg, text="Atidaryti GPU lange", command=run_fast_plot,
                  bg="#E64A19", fg="white", font=('Arial', 10, 'bold')).pack(pady=15)

    def _launch_fast_3d_plot(self, selected, plot_id):
        all_f_min = max([min(self.get_filtered_data(t)[0]) for t in selected if len(self.get_filtered_data(t)[0]) > 0])
        all_f_max = min([max(self.get_filtered_data(t)[0]) for t in selected if len(self.get_filtered_data(t)[0]) > 0])
        
        n_pts = min(60, max(30, 200 // max(len(selected), 1)))
        f_common = np.logspace(np.log10(all_f_min), np.log10(all_f_max), n_pts)
        log_f_common = np.log10(f_common)
        
        Z_real_grid = []
        Z_imag_grid = []
        M_imag_grid = []
        Sigma_grid = []
        Pseudo_drt_grid = []
        Z_norm_grid = []
        M_norm_grid = []
        Ep_grid = []
        Edp_grid = []
        Th_grid = []
        temps_valid = []
        
        for temp in selected:
            f, z = self.get_filtered_data(temp)
            if len(f) < 2: continue
            
            w = 2 * np.pi * f
            mod_sq = z.real**2 + z.imag**2
            sp = z.real / mod_sq
            mdp = (w * EPSILON_0 * z.real)
            
            f_log_orig = np.log10(f)
            interp_zr = interp1d(f_log_orig, z.real, kind='linear', fill_value='extrapolate')
            interp_zi = interp1d(f_log_orig, z.imag, kind='linear', fill_value='extrapolate')
            interp_sp = interp1d(f_log_orig, np.log10(np.maximum(sp, 1e-15)), kind='linear', fill_value='extrapolate')
            interp_mdp = interp1d(f_log_orig, mdp, kind='linear', fill_value='extrapolate')
            
            zr_c = interp_zr(log_f_common)
            zi_c = interp_zi(log_f_common)
            sp_c = 10**interp_sp(log_f_common)
            mdp_c = interp_mdp(log_f_common)
            
            pseudo_drt_c = -np.gradient(zr_c, log_f_common)
            
            k_LA, k_AL = self._get_geometric_factors()
            zr_cn, zi_cn = zr_c * k_AL, zi_c * k_AL
            w_c = 2 * np.pi * f_common
            mod_sq_cn = zr_cn**2 + zi_cn**2
            
            # Normalizacija paviršiams
            max_zi = np.max(np.abs(zi_cn)) if np.max(np.abs(zi_cn)) > 0 else 1
            z_norm_c = -zi_cn / max_zi
            mdp_cn = w_c * EPSILON_0 * zr_cn
            max_mdp = np.max(mdp_cn) if np.max(mdp_cn) > 0 else 1
            m_norm_c = mdp_cn / max_mdp
            
            ep_c = -zi_cn / (w_c * EPSILON_0 * mod_sq_cn)
            edp_c = zr_cn / (w_c * EPSILON_0 * mod_sq_cn)
            th_c = np.degrees(np.arctan2(zi_cn, zr_cn))
            
            Z_real_grid.append(zr_cn)
            Z_imag_grid.append(zi_cn)
            Sigma_grid.append(np.log10(np.maximum(zr_cn / mod_sq_cn, 1e-15)))
            M_imag_grid.append(mdp_cn)
            Pseudo_drt_grid.append(-np.gradient(zr_cn, log_f_common))
            Z_norm_grid.append(z_norm_c)
            M_norm_grid.append(m_norm_c)
            Ep_grid.append(ep_c)
            Edp_grid.append(edp_c)
            Th_grid.append(th_c)
            temps_valid.append(temp)
            
        if not temps_valid: return
            
        T_grid, F_grid = np.meshgrid(temps_valid, log_f_common, indexing='ij')
        
        Z_real_grid = np.array(Z_real_grid)
        Z_imag_grid = np.array(Z_imag_grid)
        M_imag_grid = np.array(M_imag_grid)
        Sigma_grid = np.array(Sigma_grid)
        Pseudo_drt_grid = np.array(Pseudo_drt_grid)
        Z_norm_grid = np.array(Z_norm_grid)
        M_norm_grid = np.array(M_norm_grid)
        Ep_grid = np.array(Ep_grid)
        Edp_grid = np.array(Edp_grid)
        Th_grid = np.array(Th_grid)
        T_inv_grid = 1000.0 / T_grid
        
        temp_file = os.path.join(tempfile.gettempdir(), 'pyeis_3d_data.npz')
        np.savez(temp_file, 
                 temps_valid=temps_valid, log_f_common=log_f_common,
                 Z_real_grid=Z_real_grid, Z_imag_grid=Z_imag_grid,
                 Sigma_grid=Sigma_grid, M_imag_grid=M_imag_grid,
                 Pseudo_drt_grid=Pseudo_drt_grid, 
                 Z_norm_grid=Z_norm_grid, M_norm_grid=M_norm_grid,
                 Ep_grid=Ep_grid, Edp_grid=Edp_grid, Th_grid=Th_grid,
                 T_grid=T_grid, F_grid=F_grid, T_inv_grid=T_inv_grid)
                 
        script_path = os.path.join(os.path.dirname(__file__), 'pyvista_3d_viewer.py')
        if os.path.exists(script_path):
            import sys
            subprocess.Popen([sys.executable, script_path, temp_file, '--plot_id', str(plot_id)])
        else:
            messagebox.showerror("Klaida", "Nerastas 'pyvista_3d_viewer.py' failas.")

    def open_sam_analyzer(self):
        script_path = os.path.join(os.path.dirname(__file__), 'sam2_sem_analyzer.py')
        if os.path.exists(script_path):
            import sys
            subprocess.Popen([sys.executable, script_path])
        else:
            messagebox.showerror("Klaida", "Nerastas 'sam2_sem_analyzer.py' failas.")

    def estimate_arc_width(self, z):
        if len(z) < 3: return 0.0
        z_real = z.real
        z_imag = -z.imag
        max_imag = np.max(z_imag)
        if max_imag <= 0: return 0.0
        mask = z_imag > (0.05 * max_imag)
        if not np.any(mask): return 0.0
        arc_real = z_real[mask]
        return np.max(arc_real) - np.min(arc_real)

    def show_arc_width_info(self):
        selected = sorted([t for t, v in self.vars.items() if v.get()])
        if not selected:
            messagebox.showwarning("Dėmesio", "Pasirinkite bent vieną temperatūrą kairiajame sąraše.")
            return
        
        # Toplevel langas
        sw = tk.Toplevel(self.root)
        sw.title(f"Lanko analizė (stačiakampis žymėjimas)")
        w, h = self.center_window(sw, 1600, 1001) # Pradinis +1px layoutui

        dpi = 100
        fig = Figure(figsize=(w / dpi, h / dpi), dpi=dpi, facecolor='white')
        ax = fig.add_subplot(111)
        
        all_datasets = {}
        cmap = plt.cm.viridis
        n_sel = len(selected)
        
        k_LA, k_AL = self._get_geometric_factors()
        for i, temp in enumerate(selected):
            f, z = self.get_filtered_data(temp)
            if len(z) < 2: continue
            
            # Normalizuojame į SI vienetus [Ω·m] prieš braižant
            z_n = z * k_AL
            
            color = cmap(i / max(n_sel - 1, 1)) if n_sel > 1 else '#1f77b4'
            ax.plot(z_n.real, -z_n.imag, 'o-', markersize=6, color=color, alpha=0.7, label=f"{temp}K")
            all_datasets[temp] = (f, z_n, color)

        ax.set_xlabel("Z', Ω·m")
        ax.set_ylabel("-Z'', Ω·m")
        ax.set_title(f"Dešiniuoju klavišu apveskite lanką (stačiakampis)\nPažymėta temperatūrų: {len(all_datasets)}")
        ax.grid(True, linestyle='--', alpha=0.6)
        
        # Formatuotė mažoms vertėms (aukšta T)
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
        ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='both')
        
        # 'box' yra stabilesnis Naikvisto grafikams su 'equal' aspektu
        ax.set_aspect('equal', adjustable='box')
        
        self.selector_markers = []

        def on_select(eclick, erelease):
            for m in self.selector_markers:
                try: m.remove()
                except: pass
            self.selector_markers.clear()
            
            x1, y1 = eclick.xdata, eclick.ydata
            x2, y2 = erelease.xdata, erelease.ydata
            xmin, xmax = min(x1, x2), max(x1, x2)
            ymin, ymax = min(y1, y2), max(y1, y2)
            
            results_text = []
            k_LA, k_AL = self._get_geometric_factors()
            
            for temp, (f_data, z_n, color) in all_datasets.items():
                mask = (z_n.real >= xmin) & (z_n.real <= xmax) & \
                       (-z_n.imag >= ymin) & (-z_n.imag <= ymax)
                
                if np.any(mask):
                    sel_f = f_data[mask]
                    sel_zr = z_n.real[mask]
                    sel_zi = -z_n.imag[mask]
                    
                    m = ax.plot(sel_zr, sel_zi, 'o', color=color, mec='red', mew=1.5, ms=6, alpha=0.8)[0]
                    self.selector_markers.append(m)
                    
                    r_simple = np.max(sel_zr) - np.min(sel_zr)
                    p_idx = np.argmax(sel_zi)
                    fp = sel_f[p_idx]
                    
                    # Aproksimuojame lanką apskritimu (Least Squares), jei yra bent 3 taškai
                    if len(sel_zr) >= 3:
                        A = np.c_[2 * sel_zr, 2 * sel_zi, np.ones_like(sel_zr)]
                        B = sel_zr**2 + sel_zi**2
                        C_sol, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
                        xc, yc = C_sol[0], C_sol[1]
                        R_circ2 = C_sol[2] + xc**2 + yc**2
                        
                        if R_circ2 > yc**2:
                            # Susikirtimai su y=0 (X ašimi)
                            dx = np.sqrt(R_circ2 - yc**2)
                            x_int1, x_int2 = xc - dx, xc + dx
                            r_fit = x_int2 - x_int1
                            
                            # RQ lanko analizė: CPE parametro n skaičiavimas
                            phi = np.arcsin(min(1.0, abs(yc) / np.sqrt(R_circ2)))
                            n_cpe = 1.0 - (2.0 * phi / np.pi)
                            
                            # Nupiešiame aproksimuotą lanką
                            x_arc = np.linspace(x_int1, x_int2, 100)
                            y_arc = yc + np.sqrt(np.clip(R_circ2 - (x_arc - xc)**2, 0, None))
                            arc_line = ax.plot(x_arc, y_arc, '--', color=color, lw=2)[0]
                            int_pts = ax.plot([x_int1, x_int2], [0, 0], 'x', color='black', ms=8, mew=2, zorder=5)[0]
                            self.selector_markers.extend([arc_line, int_pts])
                            
                            if fp > 0 and r_fit > 0:
                                omega_p = 2 * np.pi * fp
                                q_cpe = 1 / (r_fit * (omega_p ** n_cpe))
                                c_eq = 1 / (omega_p * r_fit)
                            else:
                                q_cpe, c_eq = 0, 0
                                
                            res_str = (f"{temp}K: R={to_sci_unicode(r_fit)} Ω·m, n={n_cpe:.3f}, Q={to_sci_unicode(q_cpe)}\n"
                                       f"   C_eq={to_sci_unicode(c_eq)} F/m, Int:[{to_sci_unicode(x_int1)}, {to_sci_unicode(x_int2)}]")
                            results_text.append(res_str)
                        else:
                            c_simple = 1 / (2 * np.pi * fp * r_simple) if fp > 0 and r_simple > 0 else 0
                            results_text.append(f"{temp}K: Max-Min R={to_sci_unicode(r_simple)} Ω·m, C={to_sci_unicode(c_simple)} F/m (Aproks. nepavyko)")
                    else:
                        c_simple = 1 / (2 * np.pi * fp * r_simple) if fp > 0 and r_simple > 0 else 0
                        results_text.append(f"{temp}K: Max-Min R={to_sci_unicode(r_simple)} Ω·m, C={to_sci_unicode(c_simple)} F/m")
            
            if not results_text:
                ax.set_title("Pasirinktoje srityje nėra taškų!")
            else:
                display_limit = 6
                display_text = "Rezultatai:\n" + "\n".join(results_text[:display_limit])
                if len(results_text) > display_limit:
                    display_text += f"\n... ir dar {len(results_text)-display_limit}"
                ax.set_title(display_text, fontsize=10, fontweight='bold')
            
            fig.canvas.draw()

        self.rs = RectangleSelector(ax, on_select,
                                     useblit=False,
                                     button=[1, 3], 
                                     minspanx=0, minspany=0,
                                     interactive=True)
        if len(all_datasets) <= 15:
            ax.legend(fontsize=8)
        
        # Toolbaras ir Canvas
        tb_frame = tk.Frame(sw)
        tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        canvas = FigureCanvasTkAgg(fig, master=sw)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar = NavigationToolbar2Tk(canvas, tb_frame)
        toolbar.update()
        
        fig.subplots_adjust(left=0.07, bottom=0.073, right=0.954, top=0.905, wspace=0.197, hspace=0.183)
        sw.update()
        canvas.draw()
        
        # Vieno pikselio "refresh" triukas
        def force_refresh():
            w, h = sw.winfo_width(), sw.winfo_height()
            if w > 100:
                sw.geometry(f"{w+1}x{h}")
                sw.after(50, lambda: sw.geometry(f"{w}x{h}"))
        sw.after(200, force_refresh)

    def export_excel(self):
        selected = [t for t, v in self.vars.items() if v.get()]
        if not selected: return
        file_dir = os.path.dirname(self.current_filepath)
        excel_path = os.path.join(file_dir, f"LLTO Rezultatai {datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                summary = []
                k_LA, k_AL = self._get_geometric_factors()
                for t in selected:
                    f, z = self.get_filtered_data(t)
                    if len(f) == 0: continue
                    
                    z_n = z * k_AL
                    w = 2 * np.pi * f
                    mod_sq_n = z_n.real**2 + z_n.imag**2
                    
                    df = pd.DataFrame({
                        'Freq (Hz)': f, 
                        'Z_real (Ohm*m)': z_n.real, 
                        'Z_imag (Ohm*m)': z_n.imag,
                        'eps_real': -z_n.imag / (w * EPSILON_0 * mod_sq_n),
                        'eps_imag': z_n.real / (w * EPSILON_0 * mod_sq_n),
                        'sigma (S/m)': z_n.real / mod_sq_n, 
                        'M_imag': w * EPSILON_0 * z_n.real,
                        'Theta (deg)': np.degrees(np.arctan2(z_n.imag, z_n.real))
                    })
                    df.to_excel(writer, sheet_name=f"{t}K", index=False)
            messagebox.showinfo("Sėkmė", f"Failas sukurtas aplanke:\n{file_dir}")
        except Exception as e: messagebox.showerror("Klaida", str(e))

    def export_zview(self):
        selected = [t for t, v in self.vars.items() if v.get()]
        if not selected: 
            messagebox.showwarning("Dėmesio", "Pasirinkite temperatūras eksportui.")
            return
            
        for t in selected:
            f_filtered, z_filtered = self.get_filtered_data(t)
            if len(f_filtered) == 0: continue
            
            # Rikiuojame nuo mažiausių dažnių iki didžiausių
            sort_idx = np.argsort(f_filtered)
            f_filtered = f_filtered[sort_idx]
            z_filtered = z_filtered[sort_idx]
            
            # Sukuriamas failo pavadinimas su temperatūra
            f_p = os.path.join(os.path.dirname(self.current_filepath), f"LLTO {t}K zview.z")
            
            try:
                with open(f_p, 'w', encoding='utf-8') as f:
                    # 1. Standartinė ZView antraštė
                    f.write('ZView Calculated Data File: Version 1.1"\n')
                    f.write('"Raw Data"\n')
                    f.write('"Sweep Frequency: Control Voltage"\n')
                    # 2. Informacinė eilutė apie autorių ir bandinį
                    f.write(f'"Sukurta: {AUTHOR}"    "Data: {datetime.now().strftime("%Y-%m-%d")}"\n')

                    # 3. STULPELIŲ PAAIŠKINIMAS (ZView formatas)
                    # ZView tikisi: Freq, 0, 0, Time, Z', Z'', 0, 0, 0
                    # 1: Dažnis, 2: Ampl, 3: Bias, 4: Indeksas, 5: Z_real, 6: Z_imag, 7-9: Tušti
                    f.write(f'  Freq (Hz), Ampl, Bias, Time(Sec), Z\'(a), Z\'\'(b), GD, Err, Range\n')
                    # 4. Duomenų įrašymas (rikiuota nuo mažiausio iki didžiausio dažnio)
                    for i, freq in enumerate(f_filtered):
                        z_real = z_filtered[i].real
                        z_imag = z_filtered[i].imag
                        f.write(f" {freq:.6E}, 0.0, 0.0, {float(i+1):.1E}, {z_real:.6E}, {z_imag:.6E}, 0, 0, 0\n")
                                
            except Exception as e:
                messagebox.showerror("Klaida", f"Nepavyko sukurti failo temperatūrai {t}K:\n{str(e)}")
                return

        messagebox.showinfo("Sėkmė", f"Sėkmingai eksportuoti {len(selected)} ZView failai su stulpelių antraštėmis.")

    # ═══════════════════════════════════════════════════════════════
    #  SEM EXCEL STATISTIKOS POSISTEMĖ  →  sem_stats_module.py
    # ═══════════════════════════════════════════════════════════════

    def setup_sem_stats_tab(self):
        """Deleguoja SEM statistikos GUI sukurima i sem_stats_module."""
        from sem_stats_module import attach_sem_stats
        attach_sem_stats(self)

if __name__ == "__main__":

    import ctypes
    # DPI awareness Windows 4K ekranams
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    
    # Padidiname bazini srifta visai programai
    default_font = ("Segoe UI", 10)
    root.option_add("*Font", default_font)
    style = ttk.Style(root)
    style.configure(".", font=default_font)
    
    app = LLTOComprehensiveApp(root)
    root.mainloop()