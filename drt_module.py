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
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from scipy.signal import find_peaks
from scipy.integrate import simpson
from scipy.interpolate import interp1d
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
import matplotlib.pyplot as plt

from language_driver import _


# ─── DRT PAGALBINĖS IR MATEMATINĖS FUNKCIJOS ───────────────────────────────

def _parse_temp(label):
    match = re.search(r"(\d+\.?\d*)", label)
    return float(match.group(1)) if match else 0.0

def _find_tau_gamma_in_dict(d):
    if not isinstance(d, dict): return None, None
    
    # 1. Potencialūs laiko/dažnio raktai
    t_keys = [k for k in d.keys() if any(x in k.lower() for x in ['tau', 'relaxation', 'time_constant', 'times'])]
    f_keys = [k for k in d.keys() if 'freq' in k.lower()]
    
    # 2. Potencialūs gamma raktai
    all_g_keys = [k for k in d.keys() if any(x in k.lower() for x in ['gamma', 'distrib', 'g_val', 'df']) or k.lower() == 'g']
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
        for tk in t_keys:
            res = try_extract(tk, gk, False)
            if res: return res
        for fk in f_keys:
            res = try_extract(fk, gk, True)
            if res: return res
            
    return None, None

def _extract_drt_from_json(proj, ds_uuid):
    # 1. Tikriname fits (dažniausia vieta)
    fits = proj.get('fits', {}).get(ds_uuid, [])
    for f in reversed(fits):
        # Tikriname 'results' viduje
        res = f.get('results', {})
        t, g = _find_tau_gamma_in_dict(res)
        if t is not None: return t, g
        
        # Tikriname pačiame fit objekte
        t, g = _find_tau_gamma_in_dict(f)
        if t is not None: return t, g

    # 2. Tikriname specializuotus DRT blokus (įskaitant 'drts')
    for key in ['drts', 'drt_results', 'drt', 'drt_data']:
        root = proj.get(key, {}).get(ds_uuid, [])
        if isinstance(root, list):
            for item in reversed(root):
                t, g = _find_tau_gamma_in_dict(item)
                if t is not None: return t, g
        else:
            t, g = _find_tau_gamma_in_dict(root)
            if t is not None: return t, g
    
    # Debug išvedimas pagalbai
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


# ─── DRT CALLBACKS IR SĄSAJA ───────────────────────────────────────────────

def _refresh_drt_datasets(app, show_popup=True):
    proj = app.arr_state['project']
    if not proj:
        if show_popup:
            messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_no_project', 'Please load a project in the Arrhenius tab first.'))
        return
    
    app.drt_state['ds_list'] = []
    labels = []
    for ds in proj.get('data_sets', []):
        uuid = ds.get('uuid')
        tau, _ignore = _extract_drt_from_json(proj, uuid)
        if tau is not None and len(tau) > 0:
            label = ds.get('label', uuid)
            app.drt_state['ds_list'].append((uuid, label))
            labels.append(label)
    
    app.drt_ds_combo['values'] = labels
    if labels: 
        app.drt_ds_combo.current(0)
        if show_popup:
            messagebox.showinfo(_('msg_success', 'Success'), _('drt_found_datasets', 'Found datasets with DRT results: {}').format(len(labels)))
    else:
        app.drt_ds_var.set('')
        app.drt_ds_combo['values'] = []
        if show_popup:
            messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_no_datasets', 'No DRT results found in project. Please perform DRT calculations in dearEIS.'))

def run_drt_analysis(app):
    proj = app.arr_state['project']
    if not proj:
        messagebox.showerror(_('msg_error', 'Error'), _('no_project_loaded', 'No project loaded.'))
        return
    
    ds_idx = app.drt_ds_combo.current()
    if ds_idx < 0:
        messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_no_selected_ds', 'Please select a dataset.'))
        return
    
    uuid, label = app.drt_state['ds_list'][ds_idx]
    
    tau, gamma = _extract_drt_from_json(proj, uuid)
    if tau is None or len(tau) == 0:
        messagebox.showerror(_('msg_error', 'Error'), _('drt_missing_data', "Dataset '{}' has no DRT data.").format(label))
        return

    tmin = tmax = None
    try:
        if app.drt_tau_min_var.get().strip(): tmin = float(app.drt_tau_min_var.get())
        if app.drt_tau_max_var.get().strip(): tmax = float(app.drt_tau_max_var.get())
    except ValueError:
        messagebox.showerror(_('msg_error', 'Error'), _('drt_invalid_bounds', 'Invalid tau bounds.'))
        return

    ln_tau = np.log(tau)
    if tmin is not None and tmax is not None:
        mask = (tau >= tmin) & (tau <= tmax)
    else:
        # Automatinis piko radimas
        peaks, _properties = find_peaks(gamma, height=np.max(gamma)*0.1)
        if len(peaks) == 0:
            messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_no_auto_peak', 'No peak found automatically. Please specify bounds manually.'))
            return
        peak_idx = peaks[np.argmax(gamma[peaks])]
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
        messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_few_points', 'Too few points in the specified range.'))
        return

    R = simpson(y=g_slice, x=ln_t_slice)
    tau_p = t_slice[np.argmax(g_slice)]
    C = tau_p / R if R != 0 else 0
    
    app.drt_results_var.set(f"R = {R:.4f} Ω  |  C = {C:.4E} F  |  τ_p = {tau_p:.2E} s")

    _plot_drt_popup(app, tau, gamma, label)

def plot_3d_drt(app):
    proj = app.arr_state['project']
    if not proj:
        messagebox.showerror(_('msg_error', 'Error'), _('no_project_loaded', 'No project loaded.'))
        return
        
    drt_data = []
    for uuid, label in app.drt_state['ds_list']:
        tau, gamma = _extract_drt_from_json(proj, uuid)
        if tau is not None and len(tau) > 0:
            temp = _parse_temp(label)
            freqs = 1.0 / (2 * np.pi * tau)
            drt_data.append((temp, freqs, gamma))
    
    if not drt_data:
        messagebox.showwarning(_('msg_warning', 'Warning'), _('drt_no_data_in_project', 'No DRT data found in project.'))
        return

    drt_data.sort(key=lambda x: x[0])
    
    all_f = np.concatenate([d[1] for d in drt_data])
    f_min, f_max = np.min(all_f), np.max(all_f)
    f_grid = np.geomspace(f_min, f_max, 200)
    log_f_grid = np.log10(f_grid)
    
    X_vals, Y_vals, Z_vals = [], [], []
    for temp, f_vals, g_vals in drt_data:
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
    
    sw = tk.Toplevel(app.root)
    sw.title(_('drt_3d_map_title', '3D DRT Map'))
    app.center_window(sw, 1400, 1001)
    
    fig = Figure(figsize=(12, 9), dpi=100, facecolor='white')
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none', alpha=0.9, antialiased=True)
    
    ax.set_xlabel('log₁₀(f), Hz', labelpad=15, rotation=0)
    ax.set_ylabel(_('drt_3d_temp_axis', 'Temperature, K'), labelpad=15, rotation=0)
    ax.set_zlabel(_('drt_3d_gamma_axis', 'γ(ln τ), Ω'), labelpad=15, rotation=90)
    ax.xaxis.set_rotate_label(False)
    ax.yaxis.set_rotate_label(False)
    ax.zaxis.set_rotate_label(False)
    ax.set_title(_('drt_3d_title', 'DRT Distribution vs Temperature and Frequency'), pad=20, fontweight='bold')
    
    ax.view_init(elev=30, azim=-120)
    
    tb_frame = tk.Frame(sw)
    tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
    
    canvas = FigureCanvasTkAgg(fig, master=sw)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar = NavigationToolbar2Tk(canvas, tb_frame)
    toolbar.update()
    
    canvas.mpl_connect('button_press_event', app.on_plot_click)
    
    sw.update()
    app.center_window(sw, 1400, 1001)
    sw.update()
    app.center_window(sw, 1400, 1000)
    canvas.draw()

def _plot_drt_popup(app, tau, gamma, label):
    win = tk.Toplevel(app.root)
    win.title(_('drt_popup_title', 'DRT Analysis - {}').format(label))
    app.center_window(win, 1560, 1106)
    win.configure(bg='white')

    app._drt_temp_peak = None
    app._drt_saved_peaks = []
    
    ctrl_f = tk.Frame(win, bg='white', pady=10)
    ctrl_f.pack(fill=tk.X)
    
    info_label = tk.Label(ctrl_f, text=_('drt_mark_info', 'Mark a peak region on the chart (drag a rectangle)'), 
                          font=('Segoe UI', 10, 'italic'), bg='white', fg='#555')
    info_label.pack()
    
    btn_f = tk.Frame(win, bg='white', pady=5)
    btn_f.pack(fill=tk.X)
    
    if app.is_normalized_var.get():
        res_var = tk.StringVar(value="ρ_p = --- | C_p = ---")
        r_unit = "Ω·m"
        r_name = "ρ"
    else:
        res_var = tk.StringVar(value="R_p = --- | C_p = ---")
        r_unit = "Ω"
        r_name = "R"
        
    tk.Label(btn_f, textvariable=res_var, font=('Segoe UI', 12, 'bold'), bg='white', fg='#2E7D32').pack(side=tk.LEFT, padx=20)
    
    def save_peak():
        if app._drt_temp_peak:
            app._drt_saved_peaks.append(app._drt_temp_peak)
            app._drt_temp_peak = None
            redraw()
    
    def clear_peaks():
        app._drt_saved_peaks.clear()
        app._drt_temp_peak = None
        redraw()

    tk.Button(btn_f, text=_('drt_save_peak', '➕ Save Peak'), command=save_peak, bg="#43A047", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_f, text=_('drt_clear_peaks', '🧹 Clear All'), command=clear_peaks, bg="#E53935", fg="white", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)

    fig = Figure(figsize=(14, 9), dpi=100, facecolor='white')
    ax = fig.add_subplot(111)
    
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    tb_frame = tk.Frame(win, bg='white')
    tb_frame.pack(side=tk.BOTTOM, fill=tk.X)
    NavigationToolbar2Tk(canvas, tb_frame)
    
    win.update()
    app.center_window(win, 1560, 1105)
    canvas.draw()

    app._drt_popup_artists = []
    ax.semilogx(tau, gamma, 'k-', lw=1.5, label=_('drt_spectrum_label', 'DRT Spectrum'), alpha=0.8)

    def redraw():
        for art in app._drt_popup_artists:
            try: art.remove()
            except: pass
        app._drt_popup_artists = []
        
        cmap = plt.colormaps.get_cmap('Set1')
        
        for i, p in enumerate(app._drt_saved_peaks):
            color = cmap(i % 9)
            legend_txt = _('drt_saved_peak_legend', 'Peak {}: {}={:.3f} {}, C={:.2E} F').format(i+1, r_name, p['R'], r_unit, p['C'])
            f = ax.fill_between(p['ts'], p['gs'], color=color, alpha=0.4, label=legend_txt)
            s = ax.scatter(p['tp'], np.max(p['gs']), color=color, s=40, edgecolors='black')
            app._drt_popup_artists.extend([f, s])

        if app._drt_temp_peak:
            p = app._drt_temp_peak
            f_temp = ax.fill_between(p['ts'], p['gs'], color='gray', alpha=0.3, linestyle='--', label=_('drt_current_peak', 'Current Selection'))
            app._drt_popup_artists.append(f_temp)
            res_var.set(f"{r_name}_p = {p['R']:.4f} {r_unit} | C_p = {p['C']:.4E} F")
        else:
            res_var.set(f"{r_name}_p = --- | C_p = ---")

        ax.set_xlabel(r'Relaxation Time $\tau$, s')
        ax.set_ylabel(r'Distribution Function $\gamma$, \Omega')
        ax.set_title(_('drt_analysis_title', 'DRT Analysis: {}').format(label))
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
        
        app._drt_temp_peak = {'ts': ts, 'gs': gs, 'R': R, 'C': C, 'tp': tp}
        redraw()

    props = dict(facecolor='#1565C0', alpha=0.2, edgecolor='black', linewidth=1)
    win.rs = RectangleSelector(ax, on_select, useblit=False, button=[1, 3], 
                               minspanx=0, minspany=0, interactive=True, props=props)
    redraw()


# ─── DRT TAB SETUP ENTRYPOINT ────────────────────────────────────────────────

def setup_drt_tab(app):
    main_f = ttk.Frame(app.tab_drt, padding=20)
    main_f.pack(fill=tk.BOTH, expand=True)

    # 1. Projekto pasirinkimas
    pf = ttk.LabelFrame(main_f, text=_('drt_project_section', 'DearEIS Project File (shared with Arrhenius tab)'), padding=10)
    pf.pack(fill=tk.X, pady=5)
    ttk.Label(pf, textvariable=app.arr_project_path_var, font=('Segoe UI', 8), foreground='#555', wraplength=800).pack(fill=tk.X, expand=True)
    tk.Button(pf, text=_('refresh_drt_btn', '🔄 Refresh Datasets from Project'), command=lambda: _refresh_drt_datasets(app), 
              bg="#E0E0E0", relief="raised", bd=2).pack(pady=5)

    # 2. Dataseto pasirinkimas
    ds_f = ttk.LabelFrame(main_f, text=_('drt_select_temp', 'Select Temperature (Dataset)'), padding=10)
    ds_f.pack(fill=tk.X, pady=5)
    app.drt_ds_combo = ttk.Combobox(ds_f, textvariable=app.drt_ds_var, state='readonly', width=50)
    app.drt_ds_combo.pack(side=tk.LEFT, padx=5)
    
    # 3. Piko rėžiai
    lim_f = ttk.LabelFrame(main_f, text=_('drt_limits', 'Peak Integration Bounds (Optional)'), padding=10)
    lim_f.pack(fill=tk.X, pady=5)
    ttk.Label(lim_f, text='tau min (s):').grid(row=0, column=0, padx=5)
    ttk.Entry(lim_f, textvariable=app.drt_tau_min_var, width=15).grid(row=0, column=1, padx=5)
    ttk.Label(lim_f, text='tau max (s):').grid(row=0, column=2, padx=5)
    ttk.Entry(lim_f, textvariable=app.drt_tau_max_var, width=15).grid(row=0, column=3, padx=5)
    ttk.Label(lim_f, text=_('drt_auto_bounds_placeholder', '(leave empty for automatic detection)'), font=('Segoe UI', 8, 'italic')).grid(row=0, column=4, padx=10)

    # 4. Rezultatai
    res_f = ttk.LabelFrame(main_f, text=_('drt_results', 'Results'), padding=10)
    res_f.pack(fill=tk.X, pady=10)
    ttk.Label(res_f, textvariable=app.drt_results_var, font=('Segoe UI', 11, 'bold'), foreground='#2E7D32').pack()

    # 5. Mygtukai
    btn_f = ttk.Frame(main_f)
    btn_f.pack(pady=20)
    tk.Button(btn_f, text=_('analyze_drt_btn', '📈 Analyze and Plot DRT'), command=lambda: run_drt_analysis(app),
              bg="#2E7D32", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(pady=5)
    
    tk.Button(btn_f, text=_('plot_3d_drt_btn', '🗺️ Plot 3D DRT (T vs f)'), command=lambda: plot_3d_drt(app),
              bg="#1565C0", fg="white", font=('Arial', 11, 'bold'), width=30, relief="raised", bd=3).pack(pady=5)
