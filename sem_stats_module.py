# -*- coding: utf-8 -*-
"""
sem_stats_module.py
───────────────────
LLTO SEM Excel vaizdų bendra statistinė analizė.

Naudojimas iš programele.py:
    from sem_stats_module import attach_sem_stats
    attach_sem_stats(app)   # app – LLTOComprehensiveApp egzempliorius
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.stats import gaussian_kde
from scipy.signal import find_peaks

# ─── Stulpelių sinonimų žodynas ────────────────────────────────────────────────
_COL_SYNONYMS = {
    "diameter":   ["equiv. diameter", "eqdiameter", "diameter", "feret",
                   "mean diameter", "diametras", "equivalent diameter",
                   "eq. diameter", "eq diameter", "eq_diameter_um", "vid. diametras"],
    "area":       ["area", "plotas", "grain area", "particle area", "area_um2", "vid. plotas"],
    "ff":         ["circularity", "form factor", "shape factor", "ff",
                   "roundness", "formos faktorius", "sphericity", "vid. sferiškumas"],
    "aspect":     ["aspect ratio", "anisotropy", "anizotropija", "aspect_ratio", "aspect", "vid. anizotropija"],
    "perimeter":  ["perimeter", "perimetras", "perimeter_um"],
    "area_3d":    ["area_3d_um2", "area 3d", "3d area", "surface area"],
    "gb_density": ["gb density", "boundary density", "gb tankis", "grainu ribu tankis", "ribų tankis", "ribu tankis"],
    "roughness":  ["roughness ra", "surface roughness", "ra", "siurkstumas",
                   "roughness", "ra (nm)", "ra (um)", "ra_um", "vid. ra šiurkštumas"],
    "fracture":   ["fracture topology", "fracture index", "topology index",
                   "luzio indeksas", "fracture", "topology", "lūžio indeksas",
                   "lūžio topologijos indeksas", "luzio topologijos indeksas"],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGRINDINIS ĮTERPIMO TAŠKAS
# ═══════════════════════════════════════════════════════════════════════════════

def attach_sem_stats(app):
    """
    Inicializuoja SEM statistikos posistemę ir prijungia ją prie `app`.
    Turi būti iškviesta po `app.tab_sem_stats` sukūrimo.
    """
    # Būsenos žodynas
    app.sem_stats_state = {
        'files':       [],
        'raw_dfs':     [],
        'combined_df': None,
        'results':     {},
    }
    app.sem_col_vars = {}

    _build_gui(app)


# ═══════════════════════════════════════════════════════════════════════════════
#  GUI KŪRIMAS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_gui(app):
    parent = app.tab_sem_stats

    # ── Antraštė ──────────────────────────────────────────────────────────────
    hdr = tk.Frame(parent, bg="#1A237E", pady=8)
    hdr.pack(fill=tk.X)
    tk.Label(hdr, text="\U0001f4ca  LLTO SEM Vaizdų bendra Statistinė Analizė",
             bg="#1A237E", fg="white",
             font=("Segoe UI", 13, "bold")).pack()
    tk.Label(hdr,
             text="Apjungia iki 10 Excel failų grūdelių duomenis ir atlieka pilną statistiką",
             bg="#1A237E", fg="#C5CAE9",
             font=("Segoe UI", 9)).pack()

    body = tk.Frame(parent)
    body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

    # ── Kairė ─────────────────────────────────────────────────────────────────
    left = tk.Frame(body)
    left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

    # Failų sąrašas
    files_lf = tk.LabelFrame(left, text="Excel failai (iki 10)", padx=6, pady=6,
                              font=("Segoe UI", 9, "bold"))
    files_lf.pack(fill=tk.X, pady=(0, 6))

    app.sem_files_listbox = tk.Listbox(files_lf, height=8, width=45,
                                       font=("Segoe UI", 8),
                                       selectmode=tk.EXTENDED)
    app.sem_files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb = ttk.Scrollbar(files_lf, orient=tk.VERTICAL,
                       command=app.sem_files_listbox.yview)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    app.sem_files_listbox.configure(yscrollcommand=sb.set)

    fb = tk.Frame(left)
    fb.pack(fill=tk.X, pady=3)
    tk.Button(fb, text="\u2795 Pridėti failus",
              command=lambda: _add_files(app),
              bg="#1976D2", fg="white",
              font=("Segoe UI", 9, "bold"), width=15).pack(side=tk.LEFT, padx=2)
    tk.Button(fb, text="\U0001f5d1 Pašalinti",
              command=lambda: _remove_files(app),
              bg="#C62828", fg="white",
              font=("Segoe UI", 9, "bold"), width=12).pack(side=tk.LEFT, padx=2)
    tk.Button(fb, text="\u2716 Išvalyti viską",
              command=lambda: _clear_files(app),
              bg="#555", fg="white",
              font=("Segoe UI", 9, "bold"), width=14).pack(side=tk.LEFT, padx=2)

    # Stulpelių priskyrimas
    col_lf = tk.LabelFrame(left, text="Stulpelių priskyrimas",
                            padx=6, pady=6,
                            font=("Segoe UI", 9, "bold"))
    col_lf.pack(fill=tk.X, pady=(0, 6))

    col_defs = [
        ("diameter",   "Ekv. diametras, µm:"),
        ("area",       "Plotas, µm²:"),
        ("ff",         "Sferiškumas (Form factor):"),
        ("aspect",     "Anizotropija (Aspect):"),
        ("perimeter",  "Perimetras, µm:"),
        ("area_3d",    "3D Plotas, µm²:"),
        ("roughness",  "Pavirš. šiurkštumas Ra (mikro):"),
    ]
    for key, label in col_defs:
        row_f = tk.Frame(col_lf)
        row_f.pack(fill=tk.X, pady=1)
        tk.Label(row_f, text=label, width=28, anchor="w",
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)
        var = tk.StringVar()
        app.sem_col_vars[key] = var
        cb = ttk.Combobox(row_f, textvariable=var, width=22,
                          state="normal", font=("Segoe UI", 8))
        cb.pack(side=tk.LEFT, padx=3)
        setattr(app, f"_sem_cb_{key}", cb)

    tk.Button(left, text="\U0001f50d Aptikti stulpelius automatiškai",
              command=lambda: _auto_detect_cols(app),
              bg="#00695C", fg="white",
              font=("Segoe UI", 9, "bold")).pack(fill=tk.X, pady=3)

    # Analizės mygtukai
    tk.Button(left, text="\u25b6  PRADĖTI ANALIZĘ",
              command=lambda: _run_analysis(app),
              bg="#2E7D32", fg="white",
              font=("Segoe UI", 11, "bold"), pady=8).pack(fill=tk.X, pady=4)
    tk.Button(left, text="\U0001f4c8 Bimodalė histograma + KDE",
              command=lambda: _show_histogram(app),
              bg="#6A1B9A", fg="white",
              font=("Segoe UI", 9, "bold")).pack(fill=tk.X, pady=2)
    tk.Button(left, text="\U0001f4be Eksportuoti rezultatus (.xlsx)",
              command=lambda: _export_results(app),
              bg="#E65100", fg="white",
              font=("Segoe UI", 9, "bold")).pack(fill=tk.X, pady=2)

    # Statusas
    app.sem_status_var = tk.StringVar(
        value="Įkelkite Excel failus ir pradėkite analizę.")
    tk.Label(left, textvariable=app.sem_status_var,
             fg="#1565C0", font=("Segoe UI", 8, "italic"),
             wraplength=350, justify="left").pack(anchor="w", pady=4)

    # ── Dešinė: rezultatų lentelė ─────────────────────────────────────────────
    right = tk.Frame(body)
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    res_lf = tk.LabelFrame(right, text="Statistikos rezultatai",
                            padx=4, pady=4,
                            font=("Segoe UI", 9, "bold"))
    res_lf.pack(fill=tk.BOTH, expand=True)

    # Lentelės stilius (kad nesusispaustų eilutės)
    style = ttk.Style()
    style.configure("Treeview", rowheight=30, font=("Segoe UI", 9))
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    tree_cols = ("Parametras", "Vidurkis \u00b1 St.nuokrypis", "Vienetai", "N")
    app.sem_results_tree = ttk.Treeview(res_lf, columns=tree_cols,
                                         show="headings", height=30)
    col_widths = [260, 200, 100, 60]
    for c, w in zip(tree_cols, col_widths):
        app.sem_results_tree.heading(c, text=c)
        app.sem_results_tree.column(c, width=w, anchor="center")

    vsb = ttk.Scrollbar(res_lf, orient=tk.VERTICAL,
                        command=app.sem_results_tree.yview)
    app.sem_results_tree.configure(yscrollcommand=vsb.set)
    app.sem_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    app.sem_results_tree.tag_configure("micro", background="#E8F5E9")
    app.sem_results_tree.tag_configure("macro", background="#E3F2FD")
    app.sem_results_tree.tag_configure("section",
                                        background="#B0BEC5",
                                        font=("Segoe UI", 9, "bold"))


# ═══════════════════════════════════════════════════════════════════════════════
#  FAILŲ VALDYMAS
# ═══════════════════════════════════════════════════════════════════════════════

def _add_files(app):
    paths = filedialog.askopenfilenames(
        title="Pasirinkite SEM duomenų failus (Excel arba CSV)",
        filetypes=[("Duomenų failai", "*.xlsx *.xls *.csv"), ("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Visi failai", "*.*")])
    for p in paths:
        if p not in app.sem_stats_state['files']:
            if len(app.sem_stats_state['files']) >= 10:
                messagebox.showwarning("Dėmesio",
                                       "Galima įkelti daugiausiai 10 failų.")
                break
            app.sem_stats_state['files'].append(p)
            app.sem_files_listbox.insert(tk.END, os.path.basename(p))
    _try_load_all(app)


def _remove_files(app):
    sel = list(app.sem_files_listbox.curselection())
    for i in reversed(sel):
        app.sem_files_listbox.delete(i)
        app.sem_stats_state['files'].pop(i)
    app.sem_stats_state['raw_dfs'] = []


def _clear_files(app):
    app.sem_files_listbox.delete(0, tk.END)
    app.sem_stats_state.update(
        files=[], raw_dfs=[], combined_df=None, results={})
    for row in app.sem_results_tree.get_children():
        app.sem_results_tree.delete(row)
    app.sem_status_var.set("Išvalyta. Įkelkite failus.")


def _try_load_all(app):
    """Nuskaito visus pasirinktus failus į raw_dfs."""
    dfs, errors = [], []
    for p in app.sem_stats_state['files']:
        try:
            if p.lower().endswith('.csv'):
                df = pd.read_csv(p)
            else:
                df = pd.read_excel(p)
            df['_source_file'] = os.path.basename(p)
            dfs.append(df)
        except Exception as e:
            errors.append(f"{os.path.basename(p)}: {e}")
    app.sem_stats_state['raw_dfs'] = dfs
    if errors:
        messagebox.showwarning("Įkėlimo klaidos", "\n".join(errors))
    if dfs:
        _auto_detect_cols(app)
        app.sem_status_var.set(
            f"Įkelta {len(dfs)} failų. Tikrinkite stulpelių priskyrimus ir "
            "paspauskite 'PRADĖTI ANALIZĘ'.")


# ═══════════════════════════════════════════════════════════════════════════════
#  STULPELIŲ APTIKIMAS
# ═══════════════════════════════════════════════════════════════════════════════

def _auto_detect_cols(app):
    dfs = app.sem_stats_state['raw_dfs']
    if not dfs:
        return
    all_cols = []
    for df in dfs:
        for c in df.columns:
            if c not in all_cols and c != '_source_file' and "Unnamed" not in str(c):
                all_cols.append(c)

    # Prioritizuojame SAM analyzer stulpelius B, C, D...
    sam_naming = {
        "area": "Area_um2", "diameter": "Eq_Diameter_um", "perimeter": "Perimeter_um",
        "ff": "Sphericity", "aspect": "Aspect_Ratio", "area_3d": "Area_3D_um2", "roughness": "Ra_um"
    }

    for key, synonyms in _COL_SYNONYMS.items():
        cb = getattr(app, f"_sem_cb_{key}", None)
        if cb is None: continue
        cb['values'] = all_cols
        
        # 1. Bandom pagal SAM pavadinimą
        sam_name = sam_naming.get(key)
        if sam_name and sam_name in all_cols:
            app.sem_col_vars[key].set(sam_name)
            continue
            
        # 2. Bandom pagal sinonimus
        matched = ""
        for col in all_cols:
            col_lower = str(col).lower().strip()
            for syn in synonyms:
                if syn == col_lower or syn in col_lower or col_lower in syn:
                    matched = col; break
            if matched: break
        if matched: app.sem_col_vars[key].set(matched)

    app.sem_status_var.set(
        "Stulpeliai aptikti. Patikrinkite priskyrimus ir "
        "paspauskite 'PRADĖTI ANALIZĘ'.")


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALIZĖ
# ═══════════════════════════════════════════════════════════════════════════════

def _run_analysis(app):
    dfs = app.sem_stats_state['raw_dfs']
    if not dfs:
        messagebox.showwarning("Dėmesio", "Pirmiausia įkelkite Excel failus.")
        return

    col = {k: v.get().strip() for k, v in app.sem_col_vars.items()}

    # 3. Makro statistika (vidurkis per failus)
    macro_meta = {
        "gb_density": ("Grūdelių ribų tankis", "1/\u03bcm"),
        "roughness_macro": ("Paviršiaus šiurkštumas Ra (globalus)", "\u03bcm"),
        "fracture":   ("Lūžio topologijos indeksas", "bvnt."),
    }

    def _find_macro_val(df, param_key):
        """Ieško makro parametro reikšmės faile ieškant raktažodžio tarp sinonimų."""
        import re
        try:
            # Dar platesnis sinonimų sąrašas maksimaliam suderinamumui
            synonyms_map = {
                "gb_density": ["Ribų tankis", "gb density", "boundary density", "ribų tankis"],
                "roughness_macro": [
                    "Vid. Ra", "Vidurkis Ra", "Ra šiurkštumas", "Paviršiaus šiurkštumas", 
                    "Ra (globalus)", "Ra (µm)", "Average Ra", "Global Ra", "Ra (um)"
                ],
                "fracture": ["Lūžio indeksas", "fracture index", "topology index", "lūžio indeksas"],
                "fracture_type": ["Lūžio tipas", "fracture type", "lūžio tipas", "dominant fracture"]
            }
            
            targets = synonyms_map.get(param_key, [])
            if not targets: return None

            # Ieškome per visus stulpelius
            for col_idx in range(df.shape[1]):
                col_data = df.iloc[:, col_idx].astype(str)
                
                for target_str in targets:
                    # Lankstus regex: taškas neprivalomas, tarpų kiekis nesvarbus
                    # Pvz. "Vid. Ra" atitiks "Vid Ra", "Vid.Ra", "Vid.   Ra" ir t.t.
                    clean_target = re.escape(target_str).replace(r'\ ', r'\s*').replace(r'\.', r'\.?\s*')
                    matches = col_data[col_data.str.contains(clean_target, na=False, case=False)]
                    
                    for row_idx in matches.index:
                        # Prioritizuojame eilutes po antraštės
                        if row_idx == 0 and len(matches) > 1: continue
                        
                        # Vertė turėtų būti sekančiame stulpelyje (col_idx + 1)
                        if col_idx + 1 < df.shape[1]:
                            val = df.iloc[row_idx, col_idx + 1]
                            if param_key == "fracture_type":
                                res = str(val).strip()
                                if res and res.lower() != "nan" and "reikšmė" not in res.lower():
                                    return res
                                continue
                            
                            if val is not None and str(val).lower() != "nan":
                                s_val = str(val).replace(',', '.')
                                match = re.search(r"[-+]?\d*\.?\d+", s_val)
                                if match: return float(match.group())
            
        except: pass
        return None

    # 1. Apjungti mikro duomenis
    micro_keys = ["diameter", "area", "ff", "aspect", "perimeter", "area_3d", "roughness"]
    combined_parts = []
    for df in dfs:
        part = {}
        for k in micro_keys:
            c_name = col.get(k)
            if c_name and c_name in df.columns:
                vals = pd.to_numeric(df[c_name], errors='coerce').dropna().values.astype(float)
                part[k] = vals
        if part:
            max_len = max(len(v) for v in part.values())
            data = {}
            for k, v in part.items():
                padded = np.full(max_len, np.nan)
                padded[:len(v)] = v
                data[k] = padded
            row_df = pd.DataFrame(data)
            combined_parts.append(row_df)

    combined = pd.concat(combined_parts, ignore_index=True) if combined_parts else pd.DataFrame()
    app.sem_stats_state['combined_df'] = combined

    # 2. Mikro statistika
    results = {}
    micro_meta = {
        "diameter": ("ekvivalentinio diametro", "\u03bcm"),
        "area":     ("ploto", "\u03bcm\u00b2"),
        "ff":       ("sferiškumo", "bvnt."),
        "aspect":   ("anizotropijos", "bvnt."),
        "perimeter": ("perimetro", "\u03bcm"),
        "area_3d":  ("3D ploto", "\u03bcm\u00b2"),
        "roughness": ("Ra šiurkštumo", "\u03bcm"),
    }
    # Pavadinimai ašims (vardininkas)
    axis_labels = {
        "diameter": "Ekvivalentinis diametras",
        "area": "Plotas",
        "ff": "Sferiškumas",
        "aspect": "Anizotropija",
        "perimeter": "Perimetras",
        "area_3d": "3D plotas",
        "roughness": "Ra šiurkštumas"
    }

    for k, (genitive_label, unit) in micro_meta.items():
        if k in combined.columns:
            arr = combined[k].dropna().values
            if len(arr) > 0:
                results[k] = {
                    "label": genitive_label, 
                    "axis_label": axis_labels.get(k, genitive_label),
                    "unit": unit,
                    "mean": float(np.mean(arr)),
                    "std":  float(np.std(arr, ddof=1)) if len(arr)>1 else 0,
                    "n": len(arr), "type": "micro", "arr": arr,
                }

    # 3. Makro rezultatai
    f_types = []
    for k, (label, unit) in macro_meta.items():
        per_file = []
        for df in dfs:
            val = _find_macro_val(df, k)
            if val is not None: per_file.append(val)
            if k == "fracture":
                ft = _find_macro_val(df, "fracture_type")
                if ft: f_types.append(ft)
                
        if per_file:
            arr = np.array(per_file)
            results[k] = {
                "label": label, "unit": unit,
                "mean": float(np.mean(arr)),
                "std":  float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                "n": len(arr), "type": "macro",
            }
    
    if f_types:
        most_common = max(set(f_types), key=f_types.count)
        results["fracture_type"] = {
            "label": "Lūžio tipas (vyraujantis)", "unit": "-",
            "mean_str": most_common, "n": len(f_types), "type": "macro"
        }

    app.sem_stats_state['results'] = results
    _populate_tree(app, results)

    n_micro = len(results.get("diameter", {}).get("arr", []))
    n_macro_types = sum(1 for r in results.values() if r['type'] == 'macro')
    
    app.sem_status_var.set(
        f"\u2705 Analizė baigta ({len(dfs)} failai). Grūdelių: {n_micro}. Makro parametrų: {n_macro_types}.")


def _populate_tree(app, results):
    tree = app.sem_results_tree
    for row in tree.get_children():
        tree.delete(row)

    tree.insert("", tk.END, iid="hdr_micro",
                values=("\u2500\u2500 MIKRO parametrai (globalus masyvas) \u2500\u2500",
                        "", "", ""),
                tags=("section",))
    for k in ["diameter", "area", "ff", "aspect", "perimeter", "area_3d", "roughness"]:
        r = results.get(k)
        if r:
            tree.insert("", tk.END,
                        values=(r['axis_label'],
                                f"{r['mean']:.4f} \u00b1 {r['std']:.4f}",
                                r['unit'], r['n']),
                        tags=("micro",))

    tree.insert("", tk.END, iid="hdr_macro",
                values=("\u2500\u2500 MAKRO parametrai (vidurkis per failus) \u2500\u2500",
                        "", "", ""),
                tags=("section",))
    for k in ["gb_density", "roughness_macro", "fracture", "fracture_type"]:
        r = results.get(k)
        if r:
            if "mean_str" in r:
                val_str = r["mean_str"]
            else:
                val_str = f"{r['mean']:.4f} \u00b1 {r['std']:.4f}"
            tree.insert("", tk.END,
                        values=(r['label'], val_str, r['unit'], r['n']),
                        tags=("macro",))


# ═══════════════════════════════════════════════════════════════════════════════
#  HISTOGRAMA + KDE
# ═══════════════════════════════════════════════════════════════════════════════

def _show_histogram(app):
    results = app.sem_stats_state['results']
    if "diameter" not in results and "area" not in results:
        messagebox.showwarning(
            "Dėmesio",
            "Pirmiausia atlikite analizę (reikalingi 'diameter' arba 'area' duomenys).")
        return

    win = tk.Toplevel(app.root)
    win.title("Grūdelių pasiskirstymo analizė")
    app.center_window(win, 950, 650)

    # Viršutinė juosta pasirinkimui
    top_bar = tk.Frame(win, pady=5)
    top_bar.pack(fill=tk.X)
    
    tk.Label(top_bar, text="Pasirinkite parametrą: ", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10)
    
    # Surandame pirmą prieinamą parametrą numatytajai reikšmei
    available_micro = [k for k in ["diameter", "area", "ff", "aspect", "perimeter", "area_3d", "roughness"] if k in results]
    default_param = available_micro[0] if available_micro else "diameter"
    param_var = tk.StringVar(value=default_param)
    
    def update_plot():
        ax.clear()
        p_key = param_var.get()
        if p_key not in results: return
        
        arr = results[p_key]["arr"]
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0: return

        label = results[p_key]["label"]
        axis_label = results[p_key]["axis_label"]
        unit = results[p_key]["unit"]
        
        # Freedman-Diaconis bin plotis
        q75, q25 = np.percentile(arr, [75, 25])
        iqr = q75 - q25
        bin_width = 2.0 * iqr * (len(arr) ** (-1.0 / 3.0)) if iqr > 0 else 0.1
        bin_width = max(bin_width, 1e-6)
        bins = np.arange(arr.min(), arr.max() + bin_width, bin_width)

        ax.hist(arr, bins=bins, density=True,
                color="#90CAF9", edgecolor="#1565C0",
                linewidth=0.5, alpha=0.7)

        kde = gaussian_kde(arr, bw_method='silverman')
        x_kde = np.linspace(arr.min(), arr.max(), 500)
        y_kde = kde(x_kde)
        ax.plot(x_kde, y_kde, 'r-', lw=2.5, label="KDE (Silverman)")

        # Pikai
        try:
            peaks_idx, _ = find_peaks(y_kde, height=0.01 * y_kde.max(), distance=len(x_kde) // 20)
            peak_vals = [x_kde[pi] for pi in peaks_idx]
            if peak_vals:
                peaks_str = ", ".join([f"{v:.2f}" for v in peak_vals])
                ax.axvline(peak_vals[0], color='brown', lw=1.5, linestyle='--', alpha=0.7, 
                           label=f"Pikai: {peaks_str} {unit}")
                for pv in peak_vals[1:]:
                    ax.axvline(pv, color='brown', lw=1.5, linestyle='--', alpha=0.7)
        except: pass

        mean_v = results[p_key]["mean"]
        std_v  = results[p_key]["std"]
        ax.axvline(mean_v, color='navy', lw=2.5, linestyle=':', 
                   label=f"Vidurkis: {mean_v:.3f} \u00b1 {std_v:.3f} {unit}")

        ax.set_xlabel(f"{axis_label}, {unit}", fontsize=11)
        ax.set_ylabel("Tikimybės tankis", fontsize=11)
        ax.set_title(f"LLTO grūdelių {label} pasiskirstymas (N={len(arr)})", fontsize=12, fontweight='bold')
        ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        canvas.draw()

    # Dinaminis radio button'ų kūrimas pagal turimus parametrus
    micro_params = {
        "diameter": "Diametras",
        "area": "Plotas",
        "ff": "Sferiškumas",
        "aspect": "Anizotropija",
        "perimeter": "Perimetras",
        "area_3d": "3D Plotas",
        "roughness": "Šiurkštumas Ra"
    }
    
    for key, label in micro_params.items():
        if key in results:
            tk.Radiobutton(top_bar, text=label, variable=param_var, value=key, 
                           command=update_plot, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)

    fig = Figure(figsize=(8.5, 5.5), dpi=100, facecolor="white")
    ax = fig.add_subplot(111)
    
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    NavigationToolbar2Tk(canvas, win)
    
    update_plot()


# ═══════════════════════════════════════════════════════════════════════════════
#  EKSPORTAS
# ═══════════════════════════════════════════════════════════════════════════════

def _export_results(app):
    results = app.sem_stats_state['results']
    if not results:
        messagebox.showwarning("Dėmesio", "Pirmiausia atlikite analizę.")
        return
    out = filedialog.asksaveasfilename(
        title="Išsaugoti SEM statistiką",
        defaultextension=".xlsx",
        initialfile="LLTO_SEM_statistika.xlsx",
        filetypes=[("Excel failas", "*.xlsx"), ("Visi failai", "*.*")])
    if not out:
        return
    rows = []
    for r in results.values():
        if "mean_str" in r:
            # Tekstiniams parametrams (pvz. Lūžio tipas)
            m_val = r["mean_str"]
            s_val = ""
            combined = r["mean_str"]
        else:
            # Skaitiniams parametrams
            m_val = r.get("mean", 0.0)
            s_val = r.get("std", 0.0)
            combined = f"{m_val:.4f} \u00b1 {s_val:.4f}"

        rows.append({
            "Parametras":              r["label"],
            "Vidurkis":                m_val,
            "Standartinis nuokrypis":  s_val,
            "Vidurkis \u00b1 St.nuokrypis": combined,
            "Vienetai":                r["unit"],
            "N":                       r["n"],
            "Tipas":                   r["type"],
        })
    df_out = pd.DataFrame(rows)
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df_out.to_excel(writer, sheet_name="Statistika", index=False)
        cdf = app.sem_stats_state.get('combined_df')
        if cdf is not None and not cdf.empty:
            cdf.to_excel(writer, sheet_name="Apjungti_duomenys", index=False)
    messagebox.showinfo("Sėkmė", f"Rezultatai išsaugoti:\n{out}")
