# Copyright 2026 Mantas Jonas Marcinkevičius
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the limitations under the License.

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
from PIL import Image, ImageTk
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

# --- KONFIGŪRACIJA ---
from language_driver import _, get_config_val, get_config_bool, set_config_val

FILE_PATH = get_config_val('default_spectrum_file', r"C:\Users\bigma\OneDrive\BAKALAURAS fiz\4 KURSAS\Bakalauras\rezultatai\LLTO 145K - 1060K temperatūros 1Hz - 9Ghz spektre.xlsx")
AUTHOR = get_config_val('author', "Mantas Jonas Marcinkevičius")
DEFAULT_PROJECT_PATH = get_config_val('default_deareis_project', r"C:/Users/bigma/OneDrive/Bakalauras/rezultatai/dearEIS LLTO nuo 145k iki 1060K.json")
EPSILON_0 = 8.85418782e-12 
EPS_0_SI = 8.854187817e-14  # F/cm

GRAPH_TYPES = {
    "Z' vs f": "Z_real_f",
    "-Z'' vs f": "Z_imag_f",
    "ε' vs f": "eps_real_f",
    "ε'' vs f": "eps_imag_f",
    "σ' vs f": "sigma_f",
    "M'' vs f": "M_imag_f",
    "tan δ vs f": "tan_delta_f",
    _("Norm. Z'' ir M'' vs f", "Norm. Z'' and M'' vs f"): "norm_z_m_f",
    "Z''/Z''max vs f": "norm_z_f",
    "M''/M''max vs f": "norm_m_f",
    _("Summerfield skalavimas", "Summerfield scaling"): "summerfield",
    "Pseudo-DRT (-dZ'/dlogf)": "pseudo_drt",
    _("Naikvisto grafikas", "Nyquist Plot"): "nyquist",
    _("Pilnutinė varža (|Z|) vs f", "Impedance Spectroscopy (|Z|) vs f"): "abs_Z_f",
    _("Fazės kampas (-Θ) vs f", "Phase Angle (-Θ) vs f"): "phase_f",
    _("Z' ir -Z'' vs f", "Z' and -Z'' vs f"): "z_real_imag_f",
    _("Bodė grafikas (|Z| ir -Θ)", "Bode Plot (|Z| and -Θ)"): "bode_dual",
    _("Cole-Cole grafikas (ε' vs ε'')", "Cole-Cole Plot (ε' vs ε'')"): "cole_cole",
}

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

# (Migrated Arrhenius helper functions to arrhenius_module.py)

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

class CeraMISApp:
    def __init__(self, root):
        self.root = root
        self.gui_scale = float(get_config_val('gui_scale', '1.0'))
        self.root.title(_('app_title', "CeraMIS - Ceramic Microstructure and Impedance System"))
        
        start_w = int(1300 * self.gui_scale)
        start_h = int(1300 * self.gui_scale)
        self.root.geometry(f"{start_w}x{start_h}")
        self.center_window(self.root, start_w, start_h)
        
        
        try:
            if os.path.exists("logo.ico"):
                self.root.iconbitmap(default="logo.ico")
            elif os.path.exists("logo.png"):
                self.icon_img = tk.PhotoImage(file="logo.png")
                self.root.iconphoto(True, self.icon_img)
        except Exception as e:
            print(f"Nepavyko užkrauti lango ikonos: {e}")
        
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
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=_('tab_eis', "EIS Analysis"))
        self.notebook.add(self.tab_arc, text=_('tab_arc', "Arc Width Analysis"))
        self.notebook.add(self.tab_arr, text=_('tab_arr', "Arrhenius Analysis"))
        self.notebook.add(self.tab_drt, text=_('tab_drt', "DRT Analysis"))
        self.notebook.add(self.tab_fit, text=_('tab_fit', "Circuit Modeling"))
        self.notebook.add(self.tab_sem, text=_('tab_sem', "SEM AI Analysis"))
        self.notebook.add(self.tab_sem_stats, text=_('tab_sem_stats', "📊 SEM Statistics"))
        self.notebook.add(self.tab_crystal, text=_('tab_crystal', "💎 3D Crystal"))
        self.notebook.add(self.tab_settings, text=_('tab_settings', "⚙️ Settings"))

        self.frequencies, self.data_dict, self.vars = [], {}, {}
        self.t_min_var = tk.StringVar(value="")
        self.t_max_var = tk.StringVar(value="")
        self.fitted_params = {}
        self.fitted_curves = {}
        
        self.f_min_var = tk.StringVar(value="")
        self.f_max_var = tk.StringVar(value="")
        self.f_min_var.trace_add("write", lambda *args: self.save_selected_freqs())
        self.f_max_var.trace_add("write", lambda *args: self.save_selected_freqs())
        
        # Bandinio geometrija
        self.thickness_var = tk.StringVar(value=get_config_val('default_thickness', '1.5'))
        self.area_var = tk.StringVar(value=get_config_val('default_area', '0.51'))
        self.is_normalized_var = tk.BooleanVar(value=get_config_bool('default_normalized', True))
        
        # DRT būsena
        self.drt_state = {'project': None, 'ds_list': []}
        self.drt_tau_min_var = tk.StringVar()
        self.drt_tau_max_var = tk.StringVar()
        self.drt_ds_var = tk.StringVar()
        self.drt_results_var = tk.StringVar(value=_('drt_results_placeholder', '(pasirinkite datasetą ir rėžius)'))
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
        
        self.current_file_var = tk.StringVar(value=_('no_file_selected', "No file selected"))
        self.current_filepath = FILE_PATH
        self.click_count = 0
        self.last_click_time = 0
        self.right_click_count = 0
        self.last_right_click_time = 0

        self.setup_gui()
        self.setup_arrhenius_tab()
        self.setup_drt_tab()
        self.setup_sem_stats_tab()
        self.setup_settings_tab()

        if os.path.exists(self.current_filepath):
            self.load_file(self.current_filepath)
            
        self.load_default_project()

    def open_file_dialog(self):
        filetypes = (
            (_('filetype_supported', "Supported files"), "*.txt *.z *.xlsx"),
            (_('filetype_txt', "Text files"), "*.txt"),
            (_('filetype_zview', "ZView files"), "*.z"),
            (_('filetype_excel', "Excel files"), "*.xlsx"),
            (_('filetype_all', "All files"), "*.*")
        )
        init_file = get_config_val('default_spectrum_file', '')
        init_dir = None
        if init_file and os.path.exists(init_file):
            init_dir = os.path.dirname(init_file)
        elif init_file and os.path.isdir(init_file):
            init_dir = init_file
            
        filepath = filedialog.askopenfilename(
            title=_('select_file_btn', "Select File..."),
            filetypes=filetypes,
            initialdir=init_dir
        )
        if filepath:
            self.load_file(filepath)

    def save_selected_temps(self):
        selected = [str(t) for t, v in self.vars.items() if v.get()]
        set_config_val('selected_temperatures', ",".join(selected))

    def save_selected_freqs(self):
        set_config_val('selected_freq_min', self.f_min_var.get())
        set_config_val('selected_freq_max', self.f_max_var.get())

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
            set_config_val('default_spectrum_file', filepath)
            
        except Exception as e:
            messagebox.showerror(_('load_error_title', "Error reading file"), _('load_error_msg', "Error: {}").format(e))

    def center_window(self, win, w, h):
        """Centruoja langą ekrane, apribojant pagal ekrano dydį."""
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        
        # Apribojame plotį ir aukštį, kad neviršytų ekrano
        w = min(w, int(sw * 0.95))
        h = min(h, sh - 60) # 60px paliekame užduočių juostai
        
        x = (sw // 2) - (w // 2)
        y = max(0, (sh // 2) - (h // 2) - 20) # Šiek tiek kilstelime į viršų
        win.geometry(f"{w}x{h}+{max(0, x)}+{y}")
        
        # Nustatome minimalų lango dydį, kuriame dar telpa visa vartotojo sąsaja (GUI) be jokių pasislėpimų
        min_w = int(1200 * getattr(self, 'gui_scale', 1.0))
        min_h = int(800 * getattr(self, 'gui_scale', 1.0))
        win.minsize(min_w, min_h)
        
        return w, h

    def setup_settings_tab(self):
        settings_frame = ttk.Frame(self.tab_settings, padding=20)
        settings_frame.pack(fill="both", expand=True)
        
        tk.Label(settings_frame, text=_('tab_settings', "⚙️ Settings"), font=('Arial', 14, 'bold')).pack(anchor="w", pady=(0, 20))
        
        appearance_lf = ttk.LabelFrame(settings_frame, text=_('appearance_settings', "Appearance & Layout"), padding=15)
        appearance_lf.pack(fill="x", pady=10)
        
        tk.Label(appearance_lf, text=_('gui_scale_label', "GUI Scale (Needs Restart):"), font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.gui_scale_var = tk.StringVar(value=get_config_val('gui_scale', '1.0'))
        scale_cb = ttk.Combobox(appearance_lf, textvariable=self.gui_scale_var, values=['0.75', '0.85', '1.0', '1.15', '1.25', '1.5', '1.75', '2.0'], state="readonly", width=15)
        scale_cb.grid(row=0, column=1, padx=20, pady=5)
        
        def on_scale_change(event):
            set_config_val('gui_scale', self.gui_scale_var.get())
            messagebox.showinfo(_('msg_info', "Information"), _('restart_required_scale', "GUI Scale changed. Please restart CeraMIS to apply changes."))
            
        scale_cb.bind("<<ComboboxSelected>>", on_scale_change)
        
        lang_lf = ttk.LabelFrame(settings_frame, text=_('language_settings', "Language / Kalba"), padding=15)
        lang_lf.pack(fill="x", pady=10)
        
        tk.Label(lang_lf, text=_('language_label', "Select Language (Needs Restart):"), font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.lang_var = tk.StringVar(value=get_config_val('language', 'en'))
        lang_cb = ttk.Combobox(lang_lf, textvariable=self.lang_var, values=['en', 'lt'], state="readonly", width=15)
        lang_cb.grid(row=0, column=1, padx=20, pady=5)
        
        def on_lang_change(event):
            set_config_val('language', self.lang_var.get())
            messagebox.showinfo(_('msg_info', "Information"), _('restart_required_lang', "Language changed. Please restart CeraMIS to apply changes."))
            
        lang_cb.bind("<<ComboboxSelected>>", on_lang_change)
        
        # Paths Section
        paths_lf = ttk.LabelFrame(settings_frame, text=_('paths_settings', "Default Paths / Files"), padding=15)
        paths_lf.pack(fill="x", pady=10)
        
        def create_path_row(parent, row, label_key, default_text, config_key, is_dir=False):
            tk.Label(parent, text=_(label_key, default_text), font=('Arial', 10)).grid(row=row, column=0, sticky="w", pady=5)
            var = tk.StringVar(value=get_config_val(config_key, ''))
            ttk.Entry(parent, textvariable=var, width=50).grid(row=row, column=1, padx=10, pady=5)
            
            def browse_cb():
                if is_dir:
                    path = filedialog.askdirectory(title=_(label_key, default_text))
                else:
                    path = filedialog.askopenfilename(title=_(label_key, default_text))
                if path:
                    var.set(path)
                    set_config_val(config_key, path)
            
            ttk.Button(parent, text=_('browse_btn', "Browse..."), command=browse_cb).grid(row=row, column=2, padx=5, pady=5)

        create_path_row(paths_lf, 0, 'default_eis_file', "Default EIS File:", 'default_spectrum_file')
        create_path_row(paths_lf, 1, 'default_deareis_file', "Default dearEIS File:", 'default_deareis_project')
        create_path_row(paths_lf, 2, 'default_sem_folder', "Default SEM Photos Folder:", 'default_sem_folder', is_dir=True)
        create_path_row(paths_lf, 3, 'default_sem_stats_folder', "Default SEM Stats Folder:", 'default_sem_stats_folder', is_dir=True)

        # SEM AI Settings
        sem_settings_lf = ttk.LabelFrame(settings_frame, text=_('sem_settings_title', "SEM AI Settings"), padding=15)
        sem_settings_lf.pack(fill="x", pady=10)
        
        tk.Label(sem_settings_lf, text=_('sam_model_version_label', "SAM Model Version:"), font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.sam_version_var = tk.StringVar(value=get_config_val('sam_model_version', 'SAM 2.1'))
        sam_cb = ttk.Combobox(sem_settings_lf, textvariable=self.sam_version_var, values=['SAM 2.1', 'SAM 3.1'], state="readonly", width=15)
        sam_cb.grid(row=0, column=1, padx=20, pady=5)
        
        def on_sam_version_change(event):
            set_config_val('sam_model_version', self.sam_version_var.get())
            
        sam_cb.bind("<<ComboboxSelected>>", on_sam_version_change)

    def setup_gui(self):
        try:
            if os.path.exists("logo.png"):
                pil_img = Image.open("logo.png")
                base_height = 220
                hpercent = (base_height / float(pil_img.size[1]))
                wsize = int((float(pil_img.size[0]) * float(hpercent)))
                pil_img = pil_img.resize((wsize, base_height), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                tk.Label(self.tab_main, image=self.logo_img).pack(pady=(15, 0))
        except Exception as e:
            print(f"Nepavyko atvaizduoti logotipo: {e}")

        tk.Label(self.tab_main, text=_('app_title', "CeraMIS - Ceramic Microstructure and Impedance System"), font=('Arial', 14, 'bold')).pack(pady=10)
        tk.Label(self.tab_main, text=f"{_('author', 'Author')}: {AUTHOR}", fg="#555").pack()
        
        file_frame = tk.Frame(self.tab_main)
        file_frame.pack(pady=5, fill="x", padx=20)
        tk.Button(file_frame, text=_('select_file_btn', "📂 Select File..."), command=self.open_file_dialog, bg="#E0E0E0").pack(side="left")
        tk.Label(file_frame, textvariable=self.current_file_var, fg="blue", wraplength=250, justify="left").pack(side="left", padx=10)
        
        # --- KONFIGŪRACIJOS KONTEINERIS (Grafikai + Geometrija) ---
        config_container = tk.Frame(self.tab_main)
        config_container.pack(pady=5, padx=20, fill="x")

        # --- GRAFIKŲ KONFIGŪRACIJA ---
        graph_frame = tk.LabelFrame(config_container, text=_('graph_matrix_title', "Graph Layout (3x3 Matrix)"), padx=10, pady=10)
        graph_frame.pack(side="left", fill="both", expand=True)
        
        self.graph_vars = [tk.StringVar() for _ignore in range(9)]
        default_graphs = [
            "Z' vs f", "-Z'' vs f", "ε' vs f",
            _("Naikvisto grafikas", "Nyquist Plot"), _("Pilnutinė varža (|Z|) vs f", "Impedance Spectroscopy (|Z|) vs f"), _("Fazės kampas (-Θ) vs f", "Phase Angle (-Θ) vs f"),
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
        geo_frame = tk.LabelFrame(config_container, text=_('sample_geometry_title', "Sample Geometry"), padx=15, pady=10)
        geo_frame.pack(side="right", fill="y", padx=(10, 0))
        
        tk.Label(geo_frame, text=_('thickness_label', "Thickness L (mm):"), font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(geo_frame, textvariable=self.thickness_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(geo_frame, text=_('area_label', "Area A (mm²):"), font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(geo_frame, textvariable=self.area_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        tk.Checkbutton(geo_frame, text=_('normalized_checkbox', "Data already normalized (Ω·m)"), 
                       variable=self.is_normalized_var, bg='#f0f0f0', font=('Arial', 9)).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10,0))

        # --- TEMPERATŪRŲ ŽYMĖJIMAS ---
        selection_frame = tk.Frame(self.tab_main)
        selection_frame.pack(pady=5)
        tk.Button(selection_frame, text=_('select_all_btn', "Select All"), command=self.select_all).pack(side="left", padx=5)
        tk.Button(selection_frame, text=_('deselect_all_btn', "Deselect All"), command=self.deselect_all).pack(side="left", padx=5)

        # --- DIAPAZONŲ KONTEINERIS ---
        range_container = tk.Frame(self.tab_main)
        range_container.pack(pady=5, padx=20, fill="x")

        # --- TEMPERATŪRŲ ŽYMĖJIMAS IR DIAPAZONAS ---
        temp_range_frame = tk.LabelFrame(range_container, text=_('temp_range_title', "Temperature Range (K)"), padx=5, pady=5)
        temp_range_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(temp_range_frame, text=_('from_label', "From:")).pack(side="left")
        self.t_min_combo = ttk.Combobox(temp_range_frame, textvariable=self.t_min_var, width=8)
        self.t_min_combo.pack(side="left", padx=5)

        tk.Label(temp_range_frame, text=_('to_label', "To:")).pack(side="left")
        self.t_max_combo = ttk.Combobox(temp_range_frame, textvariable=self.t_max_var, width=8)
        self.t_max_combo.pack(side="left", padx=5)
        
        if len(self.data_dict) > 0:
            temps = [str(t) for t in sorted(self.data_dict.keys())]
            self.t_min_combo['values'] = temps
            self.t_max_combo['values'] = temps

        tk.Button(temp_range_frame, text=_('select_btn', "Select"), command=self.select_temp_range).pack(side="left", padx=5)

        # --- FILTRACIJA (Dažnių intervalas) ---
        filter_frame = tk.LabelFrame(range_container, text=_('freq_range_title', "Frequency Range (Hz)"), padx=5, pady=5)
        filter_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        tk.Label(filter_frame, text=_('from_label', "From:")).pack(side="left")
        self.f_min_combo = ttk.Combobox(filter_frame, textvariable=self.f_min_var, width=10)
        self.f_min_combo.pack(side="left", padx=2)
        
        tk.Label(filter_frame, text=_('to_label', "To:")).pack(side="left")
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
        
        btn_frame = tk.Frame(self.tab_main)
        btn_frame.pack(side="bottom", pady=15)
        
        tk.Button(btn_frame, text=_('analyze_spectra_btn', "📈 Analyze Spectra"), command=self.open_plot, 
                  bg="#2E7D32", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text=_('3d_analysis_btn', "🚀 3D Analysis"), command=self.open_3d_plots, 
                  bg="#9C27B0", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text=_('fast_3d_btn', "⚡ High-Performance 3D Plot (GPU)"), command=self.open_fast_3d_plot, 
                  bg="#E64A19", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text=_('custom_plot_btn', "🗺️ Custom Plot"), command=self.open_custom_plot, 
                  bg="#00695C", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text=_('export_excel_btn', "📊 Export to Excel (.xlsx)"), command=self.export_excel, 
                  bg="#1B5E20", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)
        tk.Button(btn_frame, text=_('export_zview_btn', "📂 Export ZView (.z)"), command=self.export_zview, 
                  bg="#0D47A1", fg="white", font=('Arial', 10, 'bold'), width=35, relief="raised", bd=3).pack(pady=4)

        container.pack(side="top", expand=True, fill="both", padx=20)
        canvas.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")

        # ── Modeliavimo skirtuko turinys ──────────────────────────────────
        fit_top = ttk.Frame(self.tab_fit, padding=20)
        fit_top.pack(fill="both", expand=True)
        tk.Label(fit_top, text=_('circuit_modeling_title', "Circuit Modeling"), font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(fit_top, text=_('circuit_modeling_desc', "Select circuit type and click 'Fit Model'."),
                 fg="#555").pack()
        fit_frame = tk.LabelFrame(fit_top, text=_('circuit_modeling_title', "Circuit Modeling"), padx=15, pady=15)
        fit_frame.pack(pady=20, padx=40, fill="x")
        self.circuit_var = tk.StringVar(value="R-RQ-RQ-Q")
        self.circuit_combo = ttk.Combobox(fit_frame, textvariable=self.circuit_var, width=20)
        self.circuit_combo['values'] = ("R-RC", "R-RQ", "R-RQ-RQ", "R-RQ-W")
        self.circuit_combo.pack(side="left", padx=5)
        tk.Button(fit_frame, text=_('fit_btn', "Fit Model"), command=self.fit_data,
                  bg="#F57C00", fg="white", font=('Arial', 10, 'bold'), relief="raised", bd=3, padx=15).pack(side="left", padx=10)
        # Laikinai paslėptas – funkcijos išlieka
        self.notebook.hide(self.tab_fit)

        # ── Lanko Pločio skirtuko turinys ──────────────────────────────────
        arc_top = ttk.Frame(self.tab_arc, padding=20)
        arc_top.pack(fill="both", expand=True)
        tk.Label(arc_top, text=_('arc_width_title', "Nyquist Arc Width & Resistance Calculation"), font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(arc_top, text=_('arc_width_desc', "Calculates the Nyquist plot arc width and real-axis resistance."),
                 fg="#555").pack()
        tk.Button(arc_top, text=_('calc_arc_btn', "📏 Calculate Arc Width (R)"), command=self.show_arc_width_info,
                  bg="#FF8F00", fg="white", font=('Arial', 11, 'bold'), width=35, relief="raised", bd=3).pack(pady=30)

        # ── SEM Analizės skirtuko turinys ──────────────────────────────────
        sem_top = ttk.Frame(self.tab_sem, padding=20)
        sem_top.pack(fill="both", expand=True)
        tk.Label(sem_top, text=_('sem_ai_title', "SEM Microstructure AI Analysis"),
                 font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(sem_top,
                 text=_('sem_ai_desc', "Uses Segment Anything Model (SAM) for automatic grain segmentation\nin SEM micrographs and extracts 2D+3D morphological statistics\n(diameter, circularity, roughness Ra, fracture topology index)."),
                 fg="#444", justify="center").pack(pady=5)
        tk.Button(sem_top, text=_('run_sem_btn', "🔬 Run SEM AI Analyzer"), command=self.open_sam_analyzer,
                  bg="#4527A0", fg="white", font=('Arial', 11, 'bold'), width=35, relief="raised", bd=3).pack(pady=30)
                  
        # ── Kristalų Struktūros skirtuko turinys ──────────────────────────────────
        cryst_top = ttk.Frame(self.tab_crystal, padding=20)
        cryst_top.pack(fill="both", expand=True)
        tk.Label(cryst_top, text=_('crystal_title', "LLTO Crystal Structure (3D)"),
                 font=('Arial', 13, 'bold')).pack(pady=12)
        tk.Label(cryst_top,
                 text=_('crystal_desc', "Interactive 3D visualization of the LLTO perovskite structure.\nSupports real-time Li+ ion hop animation, stoichiometry config,\nand Cubic/Tetragonal phase switching."),
                 fg="#444", justify="center").pack(pady=5)
        tk.Button(cryst_top, text=_('run_crystal_btn', "💎 Launch 3D Crystal Viewer"), command=self.open_crystal_viewer,
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
            
        saved_temps_str = get_config_val('selected_temperatures', None)
        if saved_temps_str is not None:
            saved_temps = set(saved_temps_str.split(',')) if saved_temps_str else set()
        else:
            saved_temps = None

        for temp in sorted(self.data_dict.keys(), key=get_sort_key):
            var = tk.BooleanVar()
            if saved_temps is None:
                var.set(True)
            else:
                var.set(str(temp) in saved_temps or f"{temp:g}" in saved_temps)
            cb = tk.Checkbutton(self.scrollable_frame, text=f"{temp:g} K", variable=var, command=self.save_selected_temps)
            cb.pack(anchor='w', padx=60)
            cb.bind("<MouseWheel>", self._on_temp_list_mousewheel)
            cb.bind("<Button-4>", self._on_temp_list_mousewheel)
            cb.bind("<Button-5>", self._on_temp_list_mousewheel)
            self.vars[temp] = var
            
        if len(self.frequencies) > 0:
            formatted_freqs = [format_freq_with_units(f) for f in sorted(self.frequencies)]
            self.f_min_combo['values'] = formatted_freqs
            self.f_max_combo['values'] = formatted_freqs
            
            saved_f_min = get_config_val('selected_freq_min', None)
            saved_f_max = get_config_val('selected_freq_max', None)
            
            if saved_f_min in formatted_freqs:
                self.f_min_combo.set(saved_f_min)
            else:
                self.f_min_combo.set(formatted_freqs[0])
                
            if saved_f_max in formatted_freqs:
                self.f_max_combo.set(saved_f_max)
            else:
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
        self.save_selected_temps()

    def deselect_all(self):
        for var in self.vars.values():
            var.set(False)
        self.save_selected_temps()

    def select_temp_range(self):
        try:
            t_min = float(self.t_min_var.get())
            t_max = float(self.t_max_var.get())
            for temp, var in self.vars.items():
                if t_min <= temp <= t_max:
                    var.set(True)
                else:
                    var.set(False)
            self.save_selected_temps()
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
        from arrhenius_module import setup_arrhenius_tab
        setup_arrhenius_tab(self)

    def load_default_project(self):
        from arrhenius_module import load_default_project
        load_default_project(self)

    # ─── DRT ANALIZĖS METODAI ────────────────────────────────────────────────

    def setup_drt_tab(self):
        from drt_module import setup_drt_tab
        setup_drt_tab(self)

    def _refresh_drt_datasets(self, show_popup=True):
        from drt_module import _refresh_drt_datasets
        return _refresh_drt_datasets(self, show_popup)

    def run_drt_analysis(self):
        from drt_module import run_drt_analysis
        return run_drt_analysis(self)

    def plot_3d_drt(self):
        from drt_module import plot_3d_drt
        return plot_3d_drt(self)


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
            plot_window.title("CeraMIS – LLTO keramikos Mikrostruktūros ir Impedanso Analizės Sistema")
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
            sw.title("Savo grafikas")
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
                for temp, xd, yd, _ignore in datasets:
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
            messagebox.showerror(_('msg_error', "Error"), _('script_not_found', "Script {} not found.").format('pyvista_3d_viewer.py'))

    def open_sam_analyzer(self):
        sam_version = get_config_val('sam_model_version', 'SAM 2.1')
        if sam_version == 'SAM 3.1':
            script_name = 'sam3_sem_analyzer.py'
        else:
            script_name = 'sam2_sem_analyzer.py'
            
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        if os.path.exists(script_path):
            import sys
            subprocess.Popen([sys.executable, script_path])
        else:
            messagebox.showerror(_('msg_error', "Error"), _('script_not_found', "Script {} not found.").format(script_name))

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
        """Deleguoja lanko pločio skaičiavimą į išorinį modulį."""
        from arc_width_module import show_arc_width
        show_arc_width(self)

    def export_excel(self):
        selected = [t for t, v in self.vars.items() if v.get()]
        if not selected: return
        file_dir = os.path.dirname(self.current_filepath)
        excel_path = os.path.join(file_dir, f"CeraMIS Rezultatai {datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
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
            f_p = os.path.join(os.path.dirname(self.current_filepath), f"CeraMIS {t}K zview.z")
            
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
    
    try:
        myappid = u'ceramis.llto.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(myappid))
    except Exception:
        pass

    # DPI awareness Windows 4K ekranams
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    
    # Padidiname bazini srifta visai programai pagal GUI masteli
    gui_scale = float(get_config_val('gui_scale', '1.0'))
    try:
        current_scaling = root.tk.call('tk', 'scaling')
        root.tk.call('tk', 'scaling', current_scaling * gui_scale)
    except:
        pass
        
    base_font_size = int(10 * gui_scale)
    default_font = ("Segoe UI", base_font_size)
    root.option_add("*Font", default_font)
    style = ttk.Style(root)
    style.configure(".", font=default_font)
    
    app = CeraMISApp(root)
    root.mainloop()