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

import os
import re
import json
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from scipy import stats
from math import pi, sqrt, log, isnan, isinf
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from language_driver import _, get_config_val

DEFAULT_PROJECT_PATH = get_config_val('default_deareis_project', r"C:/Users/bigma/OneDrive/BAKALAURAS fiz/4 KURSAS/Bakalauras/rezultatai/dearEIS LLTO nuo 145k iki 1060K.json")
EPS_0_SI = 8.854187817e-14  # F/cm

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

def format_comma(value, decimals=2, add_degree=False):
    """Konvertuoja float į dešimtainį su kableliu."""
    res = ("{:." + str(decimals) + "f}").format(value).replace('.', ',')
    return f"{res}°" if add_degree else res

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


# ─── ARENIJAUS TABUI IR GRAFIKAMS REIKALINGOS FUNKCIJOS ─────────────────────

def setup_arrhenius_tab(app):
    # UI kintamieji
    app.arr_project_path_var = tk.StringVar()
    app.arr_status_var = tk.StringVar(value=_('arr_status_waiting', 'Waiting for project...'))
    app.arr_fit_mode_var = tk.StringVar(value='last')
    app.arr_fit_index_var = tk.StringVar(value='0')
    app.arr_fit_info_var = tk.StringVar(value=_('arr_load_proj_placeholder', '(load project)'))
    app.arr_ea_label_var = tk.StringVar(value='')
    app.arr_reg_params = [None, None]
    app.arr_point_info_var = tk.StringVar(value=_('arr_click_point_info', 'Click a point for details'))
    app.arr_r_check_vars = {}

    # Pagrindinis konteineris
    main_arr_f = ttk.Frame(app.tab_arr, padding=20)
    main_arr_f.pack(fill=tk.BOTH, expand=True)

    # --- Nustatymai ---
    pf = ttk.LabelFrame(main_arr_f, text=_('arr_project_section', 'DearEIS Project File (.json)'), padding=10)
    pf.pack(fill=tk.X, pady=5)
    ttk.Entry(pf, textvariable=app.arr_project_path_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Button(pf, text=_('arr_browse_btn', 'Browse...'), command=lambda: browse_dear_project(app), bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=6)

    fit_f = ttk.LabelFrame(main_arr_f, text=_('arr_fit_select_title', 'Fitting Result Selection'), padding=10)
    fit_f.pack(fill=tk.X, pady=5)
    rb_f = ttk.Frame(fit_f)
    rb_f.pack(fill=tk.X)
    ttk.Radiobutton(rb_f, text=_('arr_fit_last', 'Last'), variable=app.arr_fit_mode_var, value='last').pack(side=tk.LEFT, padx=6)
    ttk.Radiobutton(rb_f, text=_('arr_fit_first', 'First'), variable=app.arr_fit_mode_var, value='first').pack(side=tk.LEFT, padx=6)
    ttk.Radiobutton(rb_f, text=_('arr_fit_index_label', 'By Index:'), variable=app.arr_fit_mode_var, value='index').pack(side=tk.LEFT, padx=6)
    ttk.Entry(rb_f, textvariable=app.arr_fit_index_var, width=5).pack(side=tk.LEFT)
    ttk.Label(fit_f, textvariable=app.arr_fit_info_var, foreground='#555', font=('Segoe UI', 8), wraplength=700).pack(anchor=tk.W, padx=4, pady=2)

    app.arr_r_outer = ttk.LabelFrame(main_arr_f, text=_('arr_component_sel', 'Resistance Component Selection for Arrhenius Fit'), padding=10)
    app.arr_r_outer.pack(fill=tk.X, pady=5)
    app.arr_r_inner = ttk.Frame(app.arr_r_outer)
    app.arr_r_inner.pack(fill=tk.X)
    ttk.Label(app.arr_r_inner, text=_('arr_load_proj_placeholder', '(load project)')).pack()

    ttk.Label(main_arr_f, textvariable=app.arr_status_var, foreground='#1565C0', font=('Segoe UI', 10, 'bold')).pack(pady=10)

    btn_f = ttk.Frame(main_arr_f)
    btn_f.pack(pady=20)
    tk.Button(btn_f, text=_('arr_plot_btn', '📈 Plot Arrhenius Graph'), command=lambda: draw_arrhenius_plot(app),
              bg="#2E7D32", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_f, text=_('arr_export_btn', '📊 Export Data to CSV'), command=lambda: export_arrhenius_csv(app),
              bg="#1565C0", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_f, text=_('arr_save_btn', '💾 Save Project Changes'), command=lambda: save_arrhenius_project(app),
              bg="#D84315", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(side=tk.LEFT, padx=10)

    app._arr_scatter_sel = None
    app._arr_scatter_unsel = None
    app._arr_reg_line = None
    app._arr_saved_artists = []
    app._arr_active_idx = None
    app._arr_active_marker = None


def browse_dear_project(app):
    init_file = get_config_val('default_deareis_project', '')
    init_dir = None
    if init_file and os.path.exists(init_file):
        init_dir = os.path.dirname(init_file)
    elif init_file and os.path.isdir(init_file):
        init_dir = init_file
        
    p = filedialog.askopenfilename(
        title=_('arr_select_proj_title', 'Select dearEIS Project'),
        filetypes=[(_('arr_proj_filetype', 'dearEIS Project'), '*.json'), (_('filetype_all', 'All Files'), '*.*')],
        initialdir=init_dir
    )
    if not p: return
    app.arr_project_path_var.set(p)
    try:
        proj = load_dear_project(p)
        app.arr_state['project'] = proj
        app.arr_state['all_r_keys'] = get_all_r_keys(proj)
        app.arr_state['fit_labels'] = get_fit_labels(proj)
        _refresh_arr_r_checkboxes(app)
        _refresh_arr_fit_info(app)
        n_ds = len(proj.get('data_sets', []))
        app.arr_status_var.set(_('arr_proj_loaded', 'Project loaded. Datasets: {}').format(n_ds))
        # Atnaujiname DRT rezultatus
        app._refresh_drt_datasets(show_popup=True)
    except Exception as e:
        messagebox.showerror(_('msg_error', 'Error'), _('error_loading_proj', 'Failed to load project:\n{}').format(e))


def _refresh_arr_fit_info(app):
    fl = app.arr_state['fit_labels']
    if not fl:
        app.arr_fit_info_var.set(_('arr_no_fits', '(no fitting results)'))
        return
    first_uuid = next(iter(fl))
    entries = fl[first_uuid]
    lines = ['  - ' + desc for _ignore, desc in entries[:5]]
    if len(entries) > 5: lines.append(_('arr_and_more', '  ... and {} more').format(len(entries)-5))
    app.arr_fit_info_var.set(_('arr_fit_results_header', 'Fitting results (first dataset):\n') + '\n'.join(lines))


def _refresh_arr_r_checkboxes(app):
    for w in app.arr_r_inner.winfo_children(): w.destroy()
    app.arr_r_check_vars.clear()
    keys = app.arr_state['all_r_keys']
    if not keys:
        ttk.Label(app.arr_r_inner, text=_('arr_load_proj_placeholder', '(load project)')).pack()
        return
    for i, rk in enumerate(keys):
        var = tk.BooleanVar(value=True)
        app.arr_r_check_vars[rk] = var
        ttk.Checkbutton(app.arr_r_inner, text=rk, variable=var).grid(row=0, column=i, padx=8, pady=2, sticky=tk.W)


def load_default_project(app):
    """Automatiškai įkelia numatytąjį projektą, jei jis egzistuoja."""
    if os.path.exists(DEFAULT_PROJECT_PATH):
        app.arr_project_path_var.set(DEFAULT_PROJECT_PATH)
        try:
            proj = load_dear_project(DEFAULT_PROJECT_PATH)
            app.arr_state['project'] = proj
            app.arr_state['all_r_keys'] = get_all_r_keys(proj)
            app.arr_state['fit_labels'] = get_fit_labels(proj)
            _refresh_arr_r_checkboxes(app)
            _refresh_arr_fit_info(app)
            n_ds = len(proj.get('data_sets', []))
            app.arr_status_var.set(_('arr_proj_loaded_auto', 'Project loaded automatically. Datasets: {}').format(n_ds))
            app._refresh_drt_datasets(show_popup=False)
        except Exception:
            pass


def _update_arr_extrapolation(app, *args):
    # Prioritetas aktyviam taškui (burbuliukui)
    active_params = getattr(app, '_arr_active_reg_params', (None, None))
    active_color = getattr(app, '_arr_active_bubble_color', '#1565C0')
    
    slope, intercept = active_params
    ea, sigma0 = None, None

    if slope is not None:
        kB = 8.617333e-5
        ea = -slope * kB * 1000
        sigma0 = np.exp(intercept)
    else:
        # Jei aktyvaus nėra, imam dabartinę regresiją
        slope, intercept = getattr(app, 'arr_reg_params', (None, None))
        active_color = '#1565C0'
        if slope is not None:
            kB = 8.617333e-5
            ea = -slope * kB * 1000
            sigma0 = np.exp(intercept)
    
    if ea is None:
        if hasattr(app, 'arr_extrap_res_var'):
            app.arr_extrap_res_var.set(_('arr_select_point_or_reg', 'Select a point or regression'))
        return

    try:
        val_str = app.arr_extrap_t_var.get().strip()
        if not val_str: return
        tc = float(val_str.replace(',', '.'))
        tk_val = tc + 273.15
        if tk_val <= 0: raise ValueError
        
        # sigma = (sigma0 / T) * exp(-Ea / (kB * T))
        kB = 8.617333e-5
        sigma = (sigma0 / tk_val) * np.exp(-ea / (kB * tk_val))
        
        # Atnaujiname tekstą ir spalvą
        app.arr_extrap_res_var.set(f"σ({tc}°C) = {to_sci_unicode(sigma, 4)} S/cm")
        if hasattr(app, 'arr_extrap_res_label'):
            app.arr_extrap_res_label.config(fg=active_color)
    except (ValueError, Exception):
        app.arr_extrap_res_var.set(_('arr_invalid_temp', 'Invalid temperature'))


def _compute_arr_df(app):
    proj = app.arr_state['project']
    if proj is None:
        messagebox.showerror(_('msg_error', 'Error'), _('no_project_loaded', 'No project loaded.'))
        return None
    try:
        if app.is_normalized_var.get():
            L_cm = 1.0
            A_cm2 = 100.0 # sigma(S/cm) = 1/(rho(Ohm*m)*100)
        else:
            # Imam iš pagrindinio lango (ten mm ir mm2)
            L_mm = float(app.thickness_var.get())
            A_mm2 = float(app.area_var.get())
            
            # extract_fit_data tikisi cm ir cm2
            L_cm = L_mm / 10.0
            A_cm2 = A_mm2 / 100.0
    except ValueError:
        messagebox.showerror(_('msg_error', 'Error'), _('invalid_geometry', 'Invalid geometry data in the main window.'))
        return None
    r_sel = [rk for rk, var in app.arr_r_check_vars.items() if var.get()]
    if not r_sel: r_sel = app.arr_state['all_r_keys'] or []
    mode = app.arr_fit_mode_var.get()
    fi = app.arr_fit_index_var.get().strip() if mode == 'index' else mode
    df = extract_fit_data(proj, L_cm, A_cm2, r_sel, fi)
    if df.empty:
        messagebox.showwarning(_('msg_warning', 'Warning'), _('arr_no_data_found', 'No suitable data found.'))
        return None
    return df


def draw_arrhenius_plot(app):
    df = _compute_arr_df(app)
    if df is None: return

    app._arr_df_cache[0] = df
    app._arr_point_selected.clear()
    app.arr_point_info_var.set(_('arr_click_point_info', 'Click a point for details'))

    # Sukuriame naują langą grafikui
    arr_win = tk.Toplevel(app.root)
    
    # Nustatome dinaminį pavadinimą pagal parinktas varžas
    r_sel = [rk for rk, var in app.arr_r_check_vars.items() if var.get()]
    if len(r_sel) == 2:
        arr_win.title(_('arr_plot_title_r', 'Arrhenius Plot ($R$=$R_{t}$+$R_{gr}$)'))
    elif len(r_sel) == 1:
        arr_win.title(f"{_('arr_plot_title_prefix', 'Arrhenius Plot')} ({r_sel[0]})")
    else:
        arr_win.title(_('arr_analysis_title', 'Arrhenius Analysis'))
        
    app.center_window(arr_win, 1200, 900)

    # Ea label ir pasirinkimo mygtukai viršuje
    ctrl_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
    ctrl_f.pack(fill=tk.X)
    
    tk.Label(ctrl_f, textvariable=app.arr_ea_label_var, foreground='#B71C1C', 
             font=('Segoe UI', 12, 'bold'), bg='white').pack(side=tk.LEFT)
             
    tk.Label(ctrl_f, textvariable=app.arr_point_info_var, foreground='#2E7D32',
             font=('Segoe UI', 10, 'bold'), bg='white').pack(side=tk.RIGHT, padx=20)
    
    # Ekstrapoliacijos sekcija
    extrap_f = tk.LabelFrame(arr_win, text=_('arr_extrapolate_title', 'Conductivity Extrapolation'), bg='white', padx=10, pady=5)
    extrap_f.pack(fill=tk.X, padx=10, pady=5)
    
    tk.Label(extrap_f, text=_('arr_temp_target', 'Target Temp (°C):'), bg='white').pack(side=tk.LEFT, padx=5)
    app.arr_extrap_t_var = tk.StringVar(value='25')
    ext_t_entry = ttk.Entry(extrap_f, textvariable=app.arr_extrap_t_var, width=8)
    ext_t_entry.pack(side=tk.LEFT, padx=5)
    tk.Label(extrap_f, text='°C', bg='white').pack(side=tk.LEFT)
    
    app.arr_extrap_res_var = tk.StringVar(value='')
    app.arr_extrap_res_label = tk.Label(extrap_f, textvariable=app.arr_extrap_res_var, foreground='#1565C0',
             font=('Segoe UI', 10, 'bold'), bg='white')
    app.arr_extrap_res_label.pack(side=tk.LEFT, padx=30)
    
    app.arr_extrap_t_var.trace_add('write', lambda *args: _update_arr_extrapolation(app, *args))
    
    btn_sel_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
    btn_sel_f.pack(fill=tk.X)
    tk.Label(btn_sel_f, text=_('arr_regression_label', 'Regression:'), bg='white', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_sel_f, text=_('arr_select_all', 'Select All Points'), command=lambda: _select_all_arr_points(app), 
              bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_sel_f, text=_('arr_deselect_all', 'Deselect All Points'), command=lambda: _clear_arr_sel(app), 
              bg="#E0E0E0", relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
    
    # Nauji mygtukai kelioms linijoms
    line_ctrl_f = tk.Frame(arr_win, bg='white', padx=10, pady=5)
    line_ctrl_f.pack(fill=tk.X)
    tk.Button(line_ctrl_f, text=_('arr_save_line_btn', '➕ Save Regression Line'), command=lambda: _save_arr_line(app),
              bg="#43A047", fg="white", font=('Segoe UI', 9, 'bold'), relief="raised", bd=2).pack(side=tk.LEFT, padx=5)
    tk.Button(line_ctrl_f, text=_('arr_clear_lines_btn', '🧹 Clear Saved Lines'), command=lambda: _clear_saved_arr_lines(app),
              bg="#E53935", fg="white", font=('Segoe UI', 9, 'bold'), relief="raised", bd=2).pack(side=tk.LEFT, padx=5)

    app.arr_fig = Figure(figsize=(9, 6), dpi=100, facecolor='white')
    app.arr_ax = app.arr_fig.add_subplot(111)
    app.arr_ax.grid(True, alpha=0.3)
    
    app.arr_canvas = FigureCanvasTkAgg(app.arr_fig, master=arr_win)
    
    # Toolbar pridedame į apačią PRIEŠ canvas, kad jo nenustumtų už ekrano
    tb_frame = tk.Frame(arr_win)
    tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
    app.arr_toolbar = NavigationToolbar2Tk(app.arr_canvas, tb_frame)
    app.arr_toolbar.update()

    app._arr_saved_artists = []
    app._arr_saved_lines = []

    def on_arr_select(eclick, erelease):
        df = app._arr_df_cache[0]
        if df is None: return
        xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
        valid = ~(np.isnan(xall) | np.isnan(yall))
        x_v, y_v = xall[valid], yall[valid]
        xmin, xmax = sorted([eclick.xdata, erelease.xdata])
        ymin, ymax = sorted([eclick.ydata, erelease.ydata])
        is_select = (eclick.button == 1)
        for i in range(len(x_v)):
            if xmin <= x_v[i] <= xmax and ymin <= y_v[i] <= ymax:
                app._arr_point_selected[i] = is_select
        _recompute_arr_regression(app)

    props = dict(facecolor='#1565C0', alpha=0.2, edgecolor='black', linewidth=1)
    app.arr_rs = RectangleSelector(app.arr_ax, on_arr_select,
                                    useblit=False, button=[1, 3],
                                    minspanx=0, minspany=0,
                                    interactive=False, props=props)
    
    app.arr_canvas.mpl_connect('button_press_event', lambda ev: _on_arr_plot_click(app, ev))
    app.arr_canvas.mpl_connect('key_press_event', lambda ev: _on_arr_key_press(app, ev))
    
    # Priverčiame canvas gauti klaviatūros fokusą, kai pelė užvedama
    app.arr_canvas.get_tk_widget().bind("<Enter>", lambda e: app.arr_canvas.get_tk_widget().focus_set())

    xall = df['1000/T'].values
    yall = df['ln(Sigma*T)'].values
    yerr = df['ln_err'].values
    valid = ~(np.isnan(xall) | np.isnan(yall))
    x_v, y_v = xall[valid], yall[valid]

    for i in range(len(x_v)): app._arr_point_selected[i] = True
    
    r_sel = [rk for rk, var in app.arr_r_check_vars.items() if var.get()]
    all_keys = app.arr_state.get('all_r_keys', [])
    
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
        
    app.arr_ax.set_xlabel('1000/T, 1/K')
    app.arr_ax.set_ylabel(r'$\ln(\sigma \cdot T)$, S$\cdot$K/cm')
    app.arr_ax.set_title(f"{_('arr_plot_title_formula', 'Arrhenius Plot')} (${r_type_str}$)", pad=20)
    
    # Pridedame antrinę X ašį su Kelvino temperatūra viršuje
    def t_forward(x):
        x = np.array(x, dtype=float)
        x[np.abs(x) < 1e-10] = 1e-10 # Išvengiame dalybos iš nulio
        return 1000.0 / x

    def t_inverse(t):
        t = np.array(t, dtype=float)
        t[np.abs(t) < 1e-10] = 1e-10
        return 1000.0 / t

    secax = app.arr_ax.secondary_xaxis('top', functions=(t_forward, t_inverse))
    secax.set_xlabel('T, K')
    
    if len(x_v) > 0:
        xmin, xmax = min(x_v), max(x_v)
        pad_x = (xmax - xmin) * 0.05 if xmax > xmin else 0.1
        xmin, xmax = xmin - pad_x, xmax + pad_x
        app.arr_ax.set_xlim(xmin, xmax)
        
        ymin, ymax = min(y_v), max(y_v)
        pad_y = (ymax - ymin) * 0.05 if ymax > ymin else 0.1
        app.arr_ax.set_ylim(ymin - pad_y, ymax + pad_y)
        
        # Priverčiame sugeneruoti apatinės ašies padalas
        app.arr_fig.canvas.draw()
        xticks = app.arr_ax.get_xticks()
        
        # Paliekame tik tas padalas, kurios yra matomame rėžyje
        valid_xticks = xticks[(xticks >= xmin) & (xticks <= xmax) & (xticks > 1e-5)]
        
        if len(valid_xticks) > 0:
            # Nustatome viršutinės ašies padalas tose pačiose vertikaliose linijose
            secax.set_xticks(1000.0 / valid_xticks)
            import matplotlib.ticker as ticker
            secax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f"{val:.1f}".rstrip('0').rstrip('.')))
    
    # Instrukcijų label apačioje
    tk.Label(arr_win, text=_('arr_instructions', "🖱️ Drag selection box (left/right click) to select/deselect points. 🎯 Click a point for info."), 
             bg='#f0f0f0', font=('Segoe UI', 9, 'italic'), pady=3).pack(side=tk.BOTTOM, fill=tk.X)

    # Galiausiai supakuojame canvas, kad jis užimtų likusią laisvą vietą
    app.arr_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    app.arr_fig.tight_layout()
    _recompute_arr_regression(app)
    app.arr_status_var.set(_('arr_plot_ready', 'Plot ready. Points: {}').format(len(x_v)))

    # Vieno pikselio "refresh" triukas, kad grafikas persipieštų ir teisingai pritaikytų layout'ą
    def force_refresh():
        w, h = arr_win.winfo_width(), arr_win.winfo_height()
        if w > 100:
            arr_win.geometry(f"{w+1}x{h}")
            arr_win.after(50, lambda: arr_win.geometry(f"{w}x{h}"))
    arr_win.after(200, force_refresh)


def _recompute_arr_regression(app):
    df = app._arr_df_cache[0]
    if df is None: return
    xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
    yerr = df['ln_err'].values
    valid = ~(np.isnan(xall) | np.isnan(yall))
    x_v, y_v, ye_v = xall[valid], yall[valid], yerr[valid]
    n = len(x_v)

    sel_idx = [i for i in range(n) if app._arr_point_selected.get(i, True)]
    unsel_idx = [i for i in range(n) if not app._arr_point_selected.get(i, True)]

    if app._arr_scatter_sel is not None: app._arr_scatter_sel.remove()
    if app._arr_scatter_unsel is not None: app._arr_scatter_unsel.remove()
    if app._arr_reg_line is not None:
        try: app._arr_reg_line[0].remove()
        except: pass
    
    for art in app._arr_saved_artists:
        try: art.remove()
        except: pass
    app._arr_saved_artists = []
    
    if not hasattr(app, '_arr_errorbars'): app._arr_errorbars = []
    for container in app._arr_errorbars:
        try: container.remove()
        except: pass
    app._arr_errorbars = []

    app._arr_scatter_sel = app._arr_scatter_unsel = app._arr_reg_line = None

    if sel_idx:
        app._arr_scatter_sel = app.arr_ax.scatter(x_v[sel_idx], y_v[sel_idx], c='#1565C0', s=70, zorder=5, label=f"{_('arr_current_pts', 'Current')} ({len(sel_idx)})")
    if unsel_idx:
        app._arr_scatter_unsel = app.arr_ax.scatter(x_v[unsel_idx], y_v[unsel_idx], facecolors='none', edgecolors='#aaa', s=70, zorder=4)
        
    for xi, yi, yei in zip(x_v, y_v, ye_v):
        if not np.isnan(yei) and yei > 0:
            container = app.arr_ax.errorbar(xi, yi, yerr=yei, fmt='none', ecolor='#90CAF9', capsize=3, zorder=2)
            app._arr_errorbars.append(container)
    
    # Braižome išsaugotas linijas ir jų taškus
    cmap = plt.cm.Set1
    for i, ld in enumerate(app._arr_saved_lines):
        color = cmap(i % 9)
        art = app.arr_ax.plot(ld['xfit'], ld['yfit'], '--', color=color, lw=1.5, zorder=3,
                              label=fr"$E_a$ {i+1}: {format_comma(ld['ea'], 4)} eV, $\sigma_0$: {to_sci_unicode(ld['sigma0'], 3)} S·K/cm ($R^2$={format_comma(ld['r2'], 4)})")
        app._arr_saved_artists.extend(art)
        if 'sel_idx' in ld:
            idx = ld['sel_idx']
            pts = app.arr_ax.scatter(x_v[idx], y_v[idx], color=color, s=50, zorder=6, alpha=0.8)
            app._arr_saved_artists.append(pts)

    if len(sel_idx) >= 2:
        xs, ys = x_v[sel_idx], y_v[sel_idx]
        slope, intercept, r_val, p, se = stats.linregress(xs, ys)
        xfit = np.linspace(xs.min(), xs.max(), 300)
        kB = 8.617333e-5
        ea_now = -slope * kB * 1000
        sigma0_now = np.exp(intercept)
        app.arr_reg_params[0], app.arr_reg_params[1] = slope, intercept
        app._arr_reg_line = app.arr_ax.plot(xfit, slope * xfit + intercept, 'r-', lw=2, zorder=3,
                                             label=fr"{_('active_regression', 'Current')}: $E_a$={format_comma(ea_now, 4)} eV, $\sigma_0$={to_sci_unicode(sigma0_now, 3)} S·K/cm ($R^2$={format_comma(r_val**2, 4)})")
        app.arr_ea_label_var.set(f'Eₐ = {format_comma(ea_now, 4)} eV  |  σ₀ = {to_sci_unicode(sigma0_now, 3)} S·K/cm  |  R² = {format_comma(r_val**2, 4)}')
        _update_arr_extrapolation(app)
    else:
        app.arr_reg_params[0] = None
        app.arr_ea_label_var.set(_('arr_select_pts_for_reg', '(select points for regression)'))
        _update_arr_extrapolation(app)

    handles, labels = app.arr_ax.get_legend_handles_labels()
    if labels:
        app.arr_ax.legend(fontsize=8, loc='center right')
    app.arr_canvas.draw_idle()


def _save_arr_line(app):
    df = app._arr_df_cache[0]
    if df is None: return
    xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
    valid = ~(np.isnan(xall) | np.isnan(yall))
    x_v, y_v = xall[valid], yall[valid]
    sel_idx = [i for i in range(len(x_v)) if app._arr_point_selected.get(i, True)]
    
    if len(sel_idx) < 2:
        messagebox.showwarning(_('msg_warning', 'Warning'), _('arr_need_2_points', 'At least 2 selected points are required to save a regression line.'))
        return
        
    xs, ys = x_v[sel_idx], y_v[sel_idx]
    slope, intercept, r_val, p, se = stats.linregress(xs, ys)
    xfit = np.linspace(xs.min(), xs.max(), 300)
    kB = 8.617333e-5
    ea = -slope * kB * 1000
    
    app._arr_saved_lines.append({
        'xfit': xfit, 'yfit': slope * xfit + intercept,
        'ea': ea, 'r2': r_val**2,
        'sigma0': np.exp(intercept),
        'slope': slope,
        'intercept': intercept,
        'sel_idx': list(sel_idx)
    })
    for i in range(len(x_v)): app._arr_point_selected[i] = False
    _recompute_arr_regression(app)


def _clear_saved_arr_lines(app):
    app._arr_saved_lines = []
    _recompute_arr_regression(app)


def _on_arr_plot_click(app, event):
    if event.inaxes != getattr(app, 'arr_ax', None): return
    
    if event.button == 3:
        app.on_plot_click(event)
        return
        
    if event.button != 1: return # Tik kairysis pelės klavišas
    
    df = app._arr_df_cache[0]
    if df is None: return
    
    xall, yall = df['1000/T'].values, df['ln(Sigma*T)'].values
    valid = ~(np.isnan(xall) | np.isnan(yall))
    xv, yv = xall[valid], yall[valid]
    valid_indices = np.where(valid)[0]
    
    if len(xv) == 0: return
    
    # Randame arčiausiai pelės esantį tašką pikselių atstumu
    click_disp = app.arr_ax.transData.transform((event.xdata, event.ydata))
    points_disp = app.arr_ax.transData.transform(np.c_[xv, yv])
    dists = np.linalg.norm(points_disp - click_disp, axis=1)
    
    min_idx = np.argmin(dists)
    if dists[min_idx] < 15: # 15 pikselių tolerancija
        # Atnaujiname aktyvų indeksą ir pašaliname seną žymeklį
        active_idx = valid_indices[min_idx]
        app._arr_active_idx = active_idx
        
        if getattr(app, '_arr_active_marker', None) is not None:
            try: app._arr_active_marker.remove()
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
        source_info = _('arr_source_data_point', 'Data Point')
        
        # Tikriname priklausomybę regresijoms (išsaugotoms ir dabartinei)
        # Pirmiausia tikriname išsaugotas (nes jos turi specifines spalvas)
        found_saved = False
        if hasattr(app, '_arr_saved_lines'):
            cmap = plt.cm.Set1
            for i, ld in reversed(list(enumerate(app._arr_saved_lines))):
                if active_idx in ld.get('sel_idx', []):
                    bubble_color = cmap(i % 9)
                    if 'slope' in ld and 'intercept' in ld:
                        calc_y = ld['slope'] * x + ld['intercept']
                        active_params = (ld['slope'], ld['intercept'])
                    else:
                        calc_y = y_data
                        active_params = (None, None)
                    source_info = f"{_('arr_source_line', 'Line')} {i+1}"
                    found_saved = True
                    break
        
        # Jei nerasta išsaugotose arba taškas yra aktyvioje parinktyje, pirmenybė dabartinei
        if app._arr_point_selected.get(active_idx, True):
            slope, intercept = getattr(app, 'arr_reg_params', (None, None))
            if slope is not None:
                bubble_color = '#1565C0'
                calc_y = slope * x + intercept
                active_params = (slope, intercept)
                source_info = _('arr_source_active', 'Active Regression')
                found_saved = False # Prioritetas aktyviai
        elif not found_saved:
            bubble_color = '#777777' # Pilka jei niekur nepriklauso
            active_params = (None, None)
        
        # Išsaugome ekstrapoliacijai
        app._arr_active_reg_params = active_params
        app._arr_active_bubble_color = bubble_color
        
        app._arr_active_marker = app.arr_ax.plot(
            [x], [y_data], 
            'o', color='none', mec=bubble_color, mew=2.5, ms=15, zorder=10
        )[0]
        
        # Paskaičiuojame σ pagal parinktą y
        try:
            sigma_fit = np.exp(calc_y) / T_K
            
            if getattr(app, '_arr_legend_point', None):
                try: app._arr_legend_point.remove()
                except: pass
            
            leg_label = fr"{_('arr_point_label', 'Point')}: {T_C:.2f} °C | $\sigma$ = {to_sci_unicode(sigma_fit, 2)} S/cm"
            app._arr_legend_point = app.arr_ax.plot([], [], 'o', color='none', 
                                                     mec=bubble_color, mew=2, ms=10, 
                                                     label=leg_label)[0]
            app.arr_ax.legend(fontsize=8, loc='best')
            
            app.arr_fig.canvas.draw_idle()
            _update_arr_extrapolation(app)
        except Exception as e:
            pass

        # Paskaičiuojame varžą pagal dabartinę poziciją
        x = xall[app._arr_active_idx]
        y = yall[app._arr_active_idx]
        T = 1000.0 / x
        try:
            if app.is_normalized_var.get():
                L_cm = 1.0
                A_cm2 = 100.0
                val_name = "ρ"
                val_unit = "Ω·m"
            else:
                L_cm = float(str(app.thickness_var.get()).replace(',', '.')) * 0.1
                A_cm2 = float(str(app.area_var.get()).replace(',', '.')) * 0.01
                val_name = "R"
                val_unit = "Ω"
                
            sigma = sigma_fit
            R = (L_cm / A_cm2) / sigma
            
            app.arr_point_info_var.set(f"{_('arr_point_label', 'Point')} ({source_info}): {T_C:.2f} °C | \u03c3 = {to_sci_unicode(sigma, 4)} S/cm")
            app.arr_status_var.set(_('arr_selected_point_status', 'Selected point {temp_k:.1f} K ({source}). {name} = {val} {unit} | \u03c3 = {sigma} S/cm').format(
                temp_k=T_K, source=source_info, name=val_name, val=to_sci_unicode(R, 3), unit=val_unit, sigma=to_sci_unicode(sigma, 4)
            ))
        except Exception as e:
            app.arr_status_var.set(_('arr_selected_point_simple_status', 'Selected point {temp_k:.1f} K.').format(temp_k=T))


def _on_arr_key_press(app, event):
    return # Funkcija išjungta naudotojo prašymu


def _select_all_arr_points(app):
    df = app._arr_df_cache[0]
    if df is None: return
    n = int(np.sum(~(np.isnan(df['1000/T'].values) | np.isnan(df['ln(Sigma*T)'].values))))
    for i in range(n): app._arr_point_selected[i] = True
    _recompute_arr_regression(app)


def _clear_arr_sel(app):
    df = app._arr_df_cache[0]
    if df is None: return
    n = int(np.sum(~(np.isnan(df['1000/T'].values) | np.isnan(df['ln(Sigma*T)'].values))))
    for i in range(n): app._arr_point_selected[i] = False
    
    if getattr(app, '_arr_active_marker', None) is not None:
        try: app._arr_active_marker.remove()
        except: pass
        app._arr_active_marker = None
    
    if getattr(app, '_arr_legend_point', None) is not None:
        try: app._arr_legend_point.remove()
        except: pass
        app._arr_legend_point = None
        app.arr_ax.legend(fontsize=8, loc='best')
        
    app._arr_active_idx = None
    app.arr_status_var.set(_('arr_all_deselected', 'All points deselected.'))
    
    _recompute_arr_regression(app)


def save_arrhenius_project(app):
    proj = app.arr_state.get('project')
    if not proj:
        messagebox.showwarning(_('msg_warning', 'Warning'), _('no_project_loaded', 'No project loaded.'))
        return
        
    filepath = app.arr_project_path_var.get()
    if not filepath or not os.path.exists(filepath):
        messagebox.showwarning(_('msg_warning', 'Warning'), _('arr_original_file_missing', 'Original project file not found.'))
        return
        
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(proj, f, indent=4)
        app.arr_status_var.set(_('proj_saved_success', 'Project changes saved successfully to {}!').format(os.path.basename(filepath)))
        messagebox.showinfo(_('msg_success', 'Success'), _('arr_proj_updated_saved', 'Project updated and saved successfully.'))
    except Exception as e:
        messagebox.showerror(_('msg_error', 'Error'), _('arr_error_saving_proj', 'Error saving project:\n{}').format(e))


def export_arrhenius_csv(app):
    df = _compute_arr_df(app)
    if df is None: return
    out = filedialog.asksaveasfilename(
        title=_('arr_save_csv_title', 'Save CSV'),
        defaultextension='.csv',
        initialfile='arrhenius_data.csv',
        filetypes=[(_('arr_csv_filetype', 'CSV File'), '*.csv'), (_('filetype_all', 'All Files'), '*.*')]
    )
    if not out: return
    df.to_csv(out, index=False, float_format='%.6g')
    messagebox.showinfo(_('msg_success', 'Success'), _('arr_csv_saved', 'CSV saved to:\n{}').format(out))
