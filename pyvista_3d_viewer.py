import sys
import numpy as np
import pyvista as pv
import tempfile
import os
import re

def to_sci_unicode(value):
    """Konvertuoja skaičių į 10ⁿ formatą su Unicode laipsniais ir kableliu."""
    if abs(value) < 1e-15: return "0"
    if 0.1 <= abs(value) < 1000:
        return f"{value:.2f}".replace('.', ',')
    s = "{:.2E}".format(value)
    base, exp = s.split('E')
    base = base.replace('.', ',')
    exp_int = int(exp)
    superscripts = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻','+':''}
    unicode_exp = "".join(superscripts.get(c, c) for c in str(exp_int))
    return f"{base}×10{unicode_exp}"

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("data_file", help="Path to npz data file")
    parser.add_argument("--plot_id", type=int, default=-1, help="ID of the plot to show (0-7)")
    args = parser.parse_args()
    
    data = np.load(args.data_file)
    plot_id = args.plot_id
    
    log_f_common = data['log_f_common']
    temps_valid = data['temps_valid']
    Z_real_grid = data['Z_real_grid']
    Z_imag_grid = data['Z_imag_grid']
    Sigma_grid = data['Sigma_grid']
    M_imag_grid = data['M_imag_grid']
    Pseudo_drt_grid = data['Pseudo_drt_grid']
    Ep_grid = data['Ep_grid']
    Edp_grid = data['Edp_grid']
    Th_grid = data['Th_grid']
    T_grid = data['T_grid']
    F_grid = data['F_grid']
    T_inv_grid = data['T_inv_grid']

    pv.global_theme.background = 'white'
    pv.global_theme.font.color = 'black'
    
    plotter = pv.Plotter(window_size=[1200, 800])
    plotter.add_axes() # Pridedame ašių indikatorių

    titles = [
        "3D Naikvisto-Bodė spiralė", "Naikvisto evoliucija", "Cole-Cole 3D", "Fazės kampo 3D (-Θ)",
        "3D Kintamosios Srovės Laidumas", "Elektrinio Modulio Paviršius (M'')", 
        "Pseudo-DRT Temperatūrinis Reljefas", "Laidumo Žemėlapis (1000/T)",
        "Normalizuotas Z'' paviršius", "Normalizuotas M'' paviršius"
    ]

    def apply_cube_aspect(x_arr, y_arr, z_arr):
        x_ptp = max(np.nanmax(x_arr) - np.nanmin(x_arr), 1e-9)
        y_ptp = max(np.nanmax(y_arr) - np.nanmin(y_arr), 1e-9)
        z_ptp = max(np.nanmax(z_arr) - np.nanmin(z_arr), 1e-9)
        # Vizualiai suvienodiname mastelį į kubą
        plotter.set_scale(xscale=1.0/x_ptp, yscale=1.0/y_ptp, zscale=1.0/z_ptp)

    def get_auto_scale(arr):
        """Apskaičiuoja mastelį ir grąžina (scaled_arr, multiplier_str)."""
        v_max = np.nanmax(np.abs(arr))
        if v_max == 0 or (0.1 <= v_max < 1000):
            return arr, ""
        
        exp = int(np.floor(np.log10(v_max)))
        # Suapvaliname iki 3-jų kartotinio arba tiesiog naudojame exp
        multiplier = 10**exp
        superscripts = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻','+':''}
        unicode_exp = "".join(superscripts.get(c, c) for c in str(exp))
        return arr / multiplier, f" (×10{unicode_exp})"

    def build_lines(X, Y, Z, xlabel, ylabel, zlabel):
        X_s, x_mul = get_auto_scale(X)
        Y_s, y_mul = get_auto_scale(Y)
        Z_s, z_mul = get_auto_scale(Z)
        
        all_blocks = pv.MultiBlock()
        for i, temp in enumerate(temps_valid):
            pts = np.column_stack((X_s[i], Y_s[i], Z_s[i]))
            valid_idx = ~np.isnan(pts).any(axis=1)
            pts = pts[valid_idx]
            if len(pts) < 2: continue
                
            pd = pv.PolyData(pts)
            pd.lines = np.hstack([[len(pts)] + list(range(len(pts)))])
            pd.point_data['Temperatūra, K'] = np.full(len(pts), temp)
            all_blocks.append(pd)
            
        merged = all_blocks.combine()
        apply_cube_aspect(X_s, Y_s, Z_s)
        plotter.add_mesh(merged, scalars='Temperatūra, K', cmap='inferno', line_width=4, render_lines_as_tubes=True, show_scalar_bar=False)
        plotter.show_bounds(all_edges=False, grid=True, 
                            xtitle=xlabel + x_mul, ytitle=ylabel + y_mul, ztitle=zlabel + z_mul, 
                            font_size=10, fmt="%.2f")

    def build_surface(X, Y, Z, xlabel, ylabel, zlabel, scalar_name):
        X_s, x_mul = get_auto_scale(X)
        Y_s, y_mul = get_auto_scale(Y)
        Z_s, z_mul = get_auto_scale(Z)
        
        x_2d = X_s if X_s.ndim == 2 else np.broadcast_to(X_s, Z_s.shape)
        y_2d = Y_s if Y_s.ndim == 2 else np.broadcast_to(Y_s, Z_s.shape)
        
        grid = pv.StructuredGrid(x_2d, y_2d, Z_s)
        grid.point_data[scalar_name] = Z_s.flatten(order='F')
        
        apply_cube_aspect(x_2d, y_2d, Z_s)
        plotter.add_mesh(grid, scalars=scalar_name, cmap='inferno', show_scalar_bar=False)
        plotter.show_bounds(all_edges=False, grid=True, 
                            xtitle=xlabel + x_mul, ytitle=ylabel + y_mul, ztitle=zlabel + z_mul, 
                            font_size=10, fmt="%.2f")

    if plot_id == 0:
        Z = np.array([np.full_like(Z_real_grid[0], log_f_common) for _ in temps_valid])
        build_lines(Z_real_grid, -Z_imag_grid, Z, "Z', Ω·m", "-Z'', Ω·m", "log(f), Hz")
    elif plot_id == 1:
        Z = np.array([np.full_like(Z_real_grid[i], temp) for i, temp in enumerate(temps_valid)])
        build_lines(Z_real_grid, -Z_imag_grid, Z, "Z', Ω·m", "-Z'', Ω·m", "T, K")
    elif plot_id == 2:
        Z = np.array([np.full_like(Ep_grid[i], temp) for i, temp in enumerate(temps_valid)])
        build_lines(Ep_grid, Edp_grid, Z, "ε', vnt.", "ε'', vnt.", "T, K")
    elif plot_id == 3:
        X = np.array([np.full_like(Th_grid[i], log_f_common) for i in range(len(temps_valid))])
        Z = np.array([np.full_like(Th_grid[i], temp) for i, temp in enumerate(temps_valid)])
        build_lines(X, Th_grid, Z, "log(f), Hz", "-Θ, °", "T, K")
    elif plot_id == 4:
        build_surface(F_grid, T_grid, Sigma_grid, "log(f), Hz", "T, K", "log(σ'), S/m", "log(σ')")
    elif plot_id == 5:
        build_surface(F_grid, T_grid, M_imag_grid, "log(f), Hz", "T, K", "M'', vnt.", "M''")
    elif plot_id == 6:
        build_surface(F_grid, T_grid, Pseudo_drt_grid, "log(f), Hz", "T, K", "-dZ'/d(log f)", "DRT")
    elif plot_id == 7:
        build_surface(F_grid, T_inv_grid, Sigma_grid, "log(f), Hz", "1000/T, K⁻¹", "log(σ'), S/m", "log(σ')")
    elif plot_id == 8:
        build_surface(F_grid, T_grid, data['Z_norm_grid'], "log(f), Hz", "T, K", "Z''/Z''max", "Z_norm")
    elif plot_id == 9:
        build_surface(F_grid, T_grid, data['M_norm_grid'], "log(f), Hz", "T, K", "M''/M''max", "M_norm")

    if 0 <= plot_id < len(titles):
        plotter.add_text(titles[plot_id], position='upper_edge', font_size=14, color='black')

    plotter.show()

if __name__ == '__main__':
    main()
