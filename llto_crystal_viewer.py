import sys
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PyQt6 import QtWidgets, QtCore, QtGui
import random
import os
from language_driver import _

# LLTO composition (approximate)
# La: ~55%, Li: ~35%, Vacancy: ~10%
A_SITE_PROBS = {'La': 0.55, 'Li': 0.35, 'Vac': 0.10}

# Standartinis (schematinis) modelis - naudojame 0.30 koeficientą nuo joninių spindulių,
# kad geriau matytųsi gardelės struktūra ir ryšiai.
ATOM_STYLE = {
    'La':  {'color': '#2ecc40', 'radius': (1.36 / 3.9) * 0.30, 'name': 'La'},
    'Li':  {'color': '#9b59b6', 'radius': (0.76 / 3.9) * 0.30, 'name': 'Li'},
    'Ti':  {'color': '#2c5fb3', 'radius': (0.61 / 3.9) * 0.30, 'name': 'Ti'},
    'O':   {'color': '#e74c3c', 'radius': (1.40 / 3.9) * 0.30, 'name': 'O'},
    'Vac': {'color': '#cccccc', 'radius': 0.120, 'opacity': 0.25, 'name': 'Vakansija'},
}

# Šanono joniniai spinduliai (atstumas Å skalėje paverstas į gardelės vienetus a=3.9A)
# Mastelis: r_unit = r_angstrom / 3.9
IONIC_RADII_STYLE = {
    'La':  {'color': '#2ecc40', 'radius': 1.36 / 3.9, 'name': 'La'},
    'Li':  {'color': '#9b59b6', 'radius': 0.76 / 3.9, 'name': 'Li'},
    'Ti':  {'color': '#2c5fb3', 'radius': 0.61 / 3.9, 'name': 'Ti'},
    'O':   {'color': '#e74c3c', 'radius': 1.40 / 3.9, 'name': 'O'},
    'Vac': {'color': '#cccccc', 'radius': 0.25 / 3.9, 'opacity': 0.15, 'name': 'Vakansija'},
}

class LLTOCrystalData:
    def __init__(self, nx=2, ny=2, nz=2):
        self.nx = nx
        self.ny = ny
        self.nz = nz
        self.atoms = []
        self.bonds = []
        self.a_sites = {} # (x,y,z) -> type
        self.ti_sites = {} # (x,y,z) -> index in atoms list
        self.o_sites = []

    def build(self, phase='Cubic', la_frac=0.55, li_frac=0.35, twinned=False):
        self.atoms = []
        self.bonds = []
        self.a_sites = {}
        self.ti_sites = {}
        self.o_sites = []
        
        # Sukuriame atsitiktinę rotaciją antram domenui
        rot_matrix = np.eye(3)
        if twinned:
            from scipy.spatial.transform import Rotation
            # Atsitiktinis pasukimas iki 10 laipsnių visomis ašimis
            angles = np.random.uniform(-10, 10, 3)
            rot_matrix = Rotation.from_euler('xyz', angles, degrees=True).as_matrix()
        
        nx_half = self.nx / 2.0 if twinned else self.nx + 1
        boundary_x = nx_half
        
        # 1. A-sites (Corners)
        for x in range(self.nx + 1):
            for y in range(self.ny + 1):
                for z in range(self.nz + 1):
                    if phase in ['Cubic', 'Monoclinic', 'Amorphous']:
                        # Random assignment based on probabilities
                        r = random.random()
                        if r < la_frac:
                            atype = 'La'
                        elif r < la_frac + li_frac:
                            atype = 'Li'
                        else:
                            atype = 'Vac'
                    elif phase in ['Tetragonal', 'Orthorhombic']:
                        if z % 2 == 0:
                            atype = 'La'
                        else:
                            li_prob = min(1.0, li_frac / 0.5)
                            atype = 'Li' if random.random() < li_prob else 'Vac'
                    elif phase == 'Twinned Domains':
                        if x < self.nx / 2.0:
                            is_la_layer = (z % 2 == 0)
                        else:
                            is_la_layer = (y % 2 == 0)
                        
                        if is_la_layer:
                            atype = 'La'
                        else:
                            li_prob = min(1.0, li_frac / 0.5)
                            atype = 'Li' if random.random() < li_prob else 'Vac'

                    elif phase == 'Ruddlesden-Popper':
                        # n=3 RP structure stacking along Z
                        # Triple layer of Ti: z=0,1,2. Interlayer: z=3.
                        z_mod = z % 4
                        if z_mod == 1 or z_mod == 2:
                            atype = 'La' # Perovskite A-sites
                        else:
                            atype = 'Li' # Interlayer A-sites
                    
                    # Pozicija su galima rotacija
                    pos = np.array([x, y, z], dtype=float)
                    if phase == 'Ruddlesden-Popper':
                        # Apply (0.5, 0.5) shift every second triple-block for I-centering style
                        if (z // 4) % 2 == 1:
                            pos[0] += 0.5
                            pos[1] += 0.5
                    
                    if twinned and x >= nx_half:
                        local_pos = pos - np.array([boundary_x, self.ny/2.0, self.nz/2.0])
                        pos = np.array([boundary_x, self.ny/2.0, self.nz/2.0]) + np.dot(rot_matrix, local_pos)
                        
                    self.a_sites[(x,y,z)] = atype
                    self.atoms.append({'type': atype, 'pos': pos, 'original_pos': pos.copy()})

        # 2. B-sites (Ti at body center) and X-sites (O at face centers)
        for x in range(self.nx):
            for y in range(self.ny):
                for z in range(self.nz):
                    orig_ti_pos = np.array([x + 0.5, y + 0.5, z + 0.5], dtype=float)
                    ti_pos = orig_ti_pos.copy()
                    
                    if phase == 'Ruddlesden-Popper':
                        if (z // 4) % 2 == 1:
                            ti_pos[0] += 0.5
                            ti_pos[1] += 0.5
                            
                    if twinned and (x + 0.5) >= nx_half:
                        local_pos = ti_pos - np.array([boundary_x, self.ny/2.0, self.nz/2.0])
                        ti_pos = np.array([boundary_x, self.ny/2.0, self.nz/2.0]) + np.dot(rot_matrix, local_pos)

                    if phase == 'Ruddlesden-Popper':
                        # Skip Ti every 4th layer to create the RP gap
                        if z % 4 == 3: continue
                        
                    ti_idx = len(self.atoms)
                    self.atoms.append({'type': 'Ti', 'pos': ti_pos, 'original_pos': ti_pos})
                    self.ti_sites[(x,y,z)] = ti_idx

                    # 6 Oxygen atoms around this Ti
                    o_offsets = [
                        (0.5, 0, 0), (-0.5, 0, 0),
                        (0, 0.5, 0), (0, -0.5, 0),
                        (0, 0, 0.5), (0, 0, -0.5)
                    ]
                    
                    if phase == 'Ruddlesden-Popper':
                        # Remove vertical oxygens pointing into the gap
                        z_mod = z % 4
                        if z_mod == 0: # bottom layer of triple
                            o_offsets = [(0.5, 0, 0), (-0.5, 0, 0), (0, 0.5, 0), (0, -0.5, 0), (0, 0, 0.5)]
                        elif z_mod == 2: # top layer of triple
                            o_offsets = [(0.5, 0, 0), (-0.5, 0, 0), (0, 0.5, 0), (0, -0.5, 0), (0, 0, -0.5)]
                        elif z_mod == 3: # gap layer (should not happen due to skip)
                            continue

                    for ox, oy, oz in o_offsets:
                        orig_o_pos = np.array([x + 0.5 + ox, y + 0.5 + oy, z + 0.5 + oz], dtype=float)
                        o_pos = orig_o_pos.copy()
                        
                        if phase == 'Ruddlesden-Popper':
                            # Check layer of the Ti it belongs to
                            if (z // 4) % 2 == 1:
                                o_pos[0] += 0.5
                                o_pos[1] += 0.5
                                
                        if twinned and (x + 0.5 + ox) >= nx_half:
                            local_pos = o_pos - np.array([boundary_x, self.ny/2.0, self.nz/2.0])
                            o_pos = np.array([boundary_x, self.ny/2.0, self.nz/2.0]) + np.dot(rot_matrix, local_pos)
                        
                        # Check if O already exists (shared faces)
                        existing_o_idx = -1
                        for i, a in enumerate(self.atoms):
                            if a['type'] == 'O' and np.linalg.norm(a['pos'] - o_pos) < 0.01:
                                existing_o_idx = i
                                break
                        
                        if existing_o_idx == -1:
                            o_idx = len(self.atoms)
                            self.atoms.append({'type': 'O', 'pos': o_pos, 'original_pos': o_pos})
                            self.o_sites.append(o_idx)
                        else:
                            o_idx = existing_o_idx
                            
                        self.bonds.append((ti_idx, o_idx))

        if phase == 'Monoclinic':
            from scipy.spatial.transform import Rotation
            for idx in self.o_sites:
                atom = self.atoms[idx]
                orig_pos = atom['original_pos']
                
                min_dist = 999
                nearest_ti_pos = None
                for ti_idx in self.ti_sites.values():
                    ti_pos = self.atoms[ti_idx]['original_pos']
                    dist = np.linalg.norm(orig_pos - ti_pos)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_ti_pos = ti_pos
                
                if nearest_ti_pos is not None:
                    dx, dy, dz = orig_pos - nearest_ti_pos
                    layer_x = round(nearest_ti_pos[0] - 0.5)
                    layer_y = round(nearest_ti_pos[1] - 0.5)
                    layer_z = round(nearest_ti_pos[2] - 0.5)
                    
                    sign_x = 1 if layer_x % 2 == 0 else -1
                    sign_y = 1 if layer_y % 2 == 0 else -1
                    sign_z = 1 if layer_z % 2 == 0 else -1
                    
                    rot = Rotation.from_euler('xyz', [sign_x * 8, sign_y * 12, sign_z * 10], degrees=True)
                    new_offset = rot.apply([dx, dy, dz])
                    atom['pos'] = nearest_ti_pos + new_offset
                    atom['original_pos'] = atom['pos'].copy()

        if phase == 'Amorphous':
            for atom in self.atoms:
                offset = (np.random.rand(3) - 0.5) * 0.4
                atom['pos'] += offset
                atom['original_pos'] = atom['pos'].copy()

        if phase == 'Orthorhombic':
            # Single-axis in-phase tilt around X axis only 
            # All octahedra in a row tilt the same direction (in-phase = +/-+/-)
            from scipy.spatial.transform import Rotation
            for idx in self.o_sites:
                atom = self.atoms[idx]
                orig_pos = atom['original_pos']
                min_dist = 999
                nearest_ti_pos = None
                for ti_idx in self.ti_sites.values():
                    ti_pos = self.atoms[ti_idx]['original_pos']
                    dist = np.linalg.norm(orig_pos - ti_pos)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_ti_pos = ti_pos
                if nearest_ti_pos is not None:
                    dx, dy, dz = orig_pos - nearest_ti_pos
                    # Only tilt oxygens in the XY equatorial plane around X axis
                    if abs(dz) < 0.1:  # equatorial oxygens
                        layer_z = round(nearest_ti_pos[2] - 0.5)
                        layer_x = round(nearest_ti_pos[0] - 0.5)
                        sign = 1 if (layer_z + layer_x) % 2 == 0 else -1
                        rot = Rotation.from_euler('x', sign * 10, degrees=True)
                        new_offset = rot.apply([dx, dy, dz])
                        atom['pos'] = nearest_ti_pos + new_offset
                        atom['original_pos'] = atom['pos'].copy()

class CrystalViewerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = LLTOCrystalData(nx=2, ny=2, nz=2)
        self.actors = []
        self.bond_actors = []
        self.domain_boundary_actor = None
        self.li_jump_timer = QtCore.QTimer()
        self.li_jump_timer.timeout.connect(self._jump_step)
        self.jump_frame = 0
        self.jump_source_idx = -1
        self.jump_target_idx = -1
        self.jump_actor = None
        self.continuous_jumping = False
        self.temperature = 300
        self.a_site_actors = {} # Store the persistent clouds
        self.window_actors = [] # Store migration window planes
        
        self.setup_ui()
        self.apply_phase()

    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Left Panel
        panel = QtWidgets.QFrame()
        panel.setFixedWidth(280)
        panel.setStyleSheet("background-color: #16213e; color: white; font-family: Arial;")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        
        title = QtWidgets.QLabel(_("crystal_view_title", "🔷 LLTO Crystal Structure\n3D Visualization"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 10px; color: #e94560;")
        panel_layout.addWidget(title)
        
        # Fazė
        # Lietuviski pavadinimai -> angliski raktai
        self.PHASE_MAP = {
            _("crystal_phase_cubic", "Kubinė"): "Cubic",
            _("crystal_phase_tetragonal", "Tetragoninė"): "Tetragonal",
            _("crystal_phase_orthorhombic", "Ortorombinė"): "Orthorhombic",
            _("crystal_phase_monoclinic", "Monoklinė"): "Monoclinic",
            _("crystal_phase_twinned", "Dvynių domenai"): "Twinned Domains",
            _("crystal_phase_amorphous", "Amorfinė"): "Amorphous",
            _("crystal_phase_rp", "Ruddlesden-Popper"): "Ruddlesden-Popper",
        }
        panel_layout.addWidget(QtWidgets.QLabel(_("crystal_phase_label", "Crystallographic phase:")))
        self.phase_combo = QtWidgets.QComboBox()
        self.phase_combo.addItems(list(self.PHASE_MAP.keys()))
        self.phase_combo.setStyleSheet("background-color: #1a1a2e; color: white; padding: 5px; border: 1px solid #e94560;")
        self.phase_combo.currentIndexChanged.connect(self.apply_phase)
        panel_layout.addWidget(self.phase_combo)
 
        # Gardelės dydis
        panel_layout.addWidget(QtWidgets.QLabel(_("crystal_cell_label", "Supercell size:")))
        self.cell_combo = QtWidgets.QComboBox()
        self.cell_combo.addItems(["1×1×1", "2×2×2", "3×3×3", "6×2×2", "6×3×3"])
        self.cell_combo.setCurrentIndex(1)
        self.cell_combo.setStyleSheet("background-color: #1a1a2e; color: white; padding: 5px; border: 1px solid #e94560;")
        self.cell_combo.currentIndexChanged.connect(self.apply_phase)
        panel_layout.addWidget(self.cell_combo)
 
        # Domenų riba
        self.domain_check = QtWidgets.QCheckBox(_("crystal_show_boundary", "Show domain boundary"))
        self.domain_check.setChecked(True)
        self.domain_check.setStyleSheet("color: #f39c12; font-weight: bold;")
        self.domain_check.stateChanged.connect(self.apply_phase)
        panel_layout.addWidget(self.domain_check)
 
        # Deguonies langai
        self.window_check = QtWidgets.QCheckBox(_("crystal_show_windows", "Show oxygen windows"))
        self.window_check.setChecked(False)
        self.window_check.setStyleSheet("color: #00f2ff; font-weight: bold;")
        self.window_check.stateChanged.connect(self._toggle_oxygen_windows)
        panel_layout.addWidget(self.window_check)
 
        # Joniniai spinduliai (Realus modelis)
        self.realistic_check = QtWidgets.QCheckBox(_("crystal_show_radii", "Show ionic radii"))
        self.realistic_check.setChecked(False)
        self.realistic_check.setStyleSheet("color: white; font-weight: bold; margin-bottom: 5px;")
        self.realistic_check.stateChanged.connect(self._rebuild_scene)
        panel_layout.addWidget(self.realistic_check)
        
        # Stechiometrija
        stoich_group = QtWidgets.QGroupBox(_("crystal_stoichiometry", "Stoichiometry"))
        stoich_group.setStyleSheet("color: white; border: 1px solid #444; margin-top: 5px;")
        stoich_layout = QtWidgets.QVBoxLayout()
        def create_custom_spin(label_text, initial_value, callback):
            layout = QtWidgets.QHBoxLayout()
            layout.addWidget(QtWidgets.QLabel(label_text))
            
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0, 100.0)
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setValue(initial_value)
            spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setFixedWidth(65)
            spin.setStyleSheet("background-color: #1a1a2e; color: white; border: 1px solid #555; padding: 2px;")
            spin.valueChanged.connect(callback)
            
            btn_style = "QPushButton { background-color: #2e2e4a; color: #e94560; font-weight: bold; border: 1px solid #555; width: 25px; height: 25px; } QPushButton:hover { background-color: #3e3e5a; }"
            
            btn_minus = QtWidgets.QPushButton("-")
            btn_minus.setStyleSheet(btn_style)
            btn_minus.clicked.connect(spin.stepDown)
            
            btn_plus = QtWidgets.QPushButton("+")
            btn_plus.setStyleSheet(btn_style)
            btn_plus.clicked.connect(spin.stepUp)
            
            layout.addWidget(btn_minus)
            layout.addWidget(spin)
            layout.addWidget(btn_plus)
            return spin, layout
 
        self.spin_la, la_layout = create_custom_spin("La (%):", 55.7, self.update_stoichiometry)
        stoich_layout.addLayout(la_layout)
        
        self.spin_li, li_layout = create_custom_spin("Li (%):", 33.0, self.update_stoichiometry)
        stoich_layout.addLayout(li_layout)
        
        self.lbl_vac = QtWidgets.QLabel(f"{_('crystal_atom_Vac', 'Vacancy')} (%): 11.3")
        stoich_layout.addWidget(self.lbl_vac)
        stoich_group.setLayout(stoich_layout)
        panel_layout.addWidget(stoich_group)
        
        self.apply_btn = QtWidgets.QPushButton(_("crystal_apply_btn", "Apply Phase & Stoichiometry"))
        self.apply_btn.setStyleSheet("background-color: #e94560; color: white; padding: 5px; font-weight: bold;")
        self.apply_btn.clicked.connect(self.apply_phase)
        panel_layout.addWidget(self.apply_btn)
        
        panel_layout.addSpacing(10)
        
        # Temperatūra
        self.temp_label = QtWidgets.QLabel(_("crystal_temp_label", "Temperature: {} K").format(300))
        panel_layout.addWidget(self.temp_label)
        self.temp_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.temp_slider.setRange(145, 1060)
        self.temp_slider.setValue(300)
        self.temp_slider.valueChanged.connect(self.on_temp_changed)
        panel_layout.addWidget(self.temp_slider)
 
        panel_layout.addSpacing(10)
        
        # Oktaedro pasvirimas
        self.tilt_label = QtWidgets.QLabel(_("crystal_tilt_label", "Octahedron tilt: {}°").format(0))
        panel_layout.addWidget(self.tilt_label)
        self.tilt_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.tilt_slider.setRange(-15, 15)
        self.tilt_slider.setValue(0)
        self.tilt_slider.valueChanged.connect(self.on_tilt_changed)
        panel_layout.addWidget(self.tilt_slider)
        
        panel_layout.addSpacing(20)
        
        # Jono šuolis
        self.jump_btn = QtWidgets.QPushButton(_("crystal_jump_start", "▶ Start Li Hop Animation"))
        self.jump_btn.setStyleSheet("background-color: #2ecc40; color: white; padding: 8px; font-weight: bold;")
        self.jump_btn.clicked.connect(self.toggle_jump_animation)
        panel_layout.addWidget(self.jump_btn)
 
        panel_layout.addSpacing(10)
        
        # Elektrinis laukas
        field_group = QtWidgets.QGroupBox(_("crystal_field_group", "⚡ Electric Field"))
        field_group.setStyleSheet("color: #f1c40f; border: 1px solid #f1c40f; margin-top: 5px;")
        field_layout = QtWidgets.QVBoxLayout()
        
        self.field_check = QtWidgets.QCheckBox(_("crystal_field_check", "Enable electric field effect"))
        self.field_check.setStyleSheet("color: white;")
        field_layout.addWidget(self.field_check)
        
        field_group.setLayout(field_layout)
        panel_layout.addWidget(field_group)
 
 
        # Fono spalva
        self.bg_check = QtWidgets.QCheckBox(_("crystal_white_bg", "White Background"))
        self.bg_check.setChecked(True)
        self.bg_check.setStyleSheet("color: white; font-weight: bold;")
        self.bg_check.stateChanged.connect(self.toggle_background)
        panel_layout.addWidget(self.bg_check)
 
        # Eksportuoti ekrano nuotrauką
        self.export_btn = QtWidgets.QPushButton(_("crystal_export_png", "📷 Export PNG"))
        self.export_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 8px; font-weight: bold;")
        self.export_btn.clicked.connect(self.export_screenshot)
        panel_layout.addWidget(self.export_btn)
        
        layout.addWidget(panel)
        
        # Right Panel (PyVista)
        self.plotter_container = QtWidgets.QFrame()
        self.plotter_layout = QtWidgets.QVBoxLayout(self.plotter_container)
        self.plotter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.plotter = QtInteractor(self)
        self.plotter.set_background('white')
        self.plotter_layout.addWidget(self.plotter.interactor)
        
        # Sukuriame legendos perdangą (Overlay) per Qt
        self.legend_overlay = QtWidgets.QFrame(self.plotter.interactor)
        self.legend_overlay.setStyleSheet("background-color: white; border: 2px solid black; border-radius: 3px;")
        self.legend_overlay.setFixedWidth(140)
        overlay_layout = QtWidgets.QVBoxLayout(self.legend_overlay)
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(5)
        
        for atype, style in ATOM_STYLE.items():
            row = QtWidgets.QHBoxLayout()
            # Spalvotas burbuliukas per CSS
            circle = QtWidgets.QLabel()
            circle.setFixedSize(16, 16)
            circle.setStyleSheet(f"background-color: {style['color']}; border-radius: 8px; border: none;")
            
            label = QtWidgets.QLabel(_(f"crystal_atom_{atype}", style['name']))
            label.setStyleSheet("color: black; font-weight: bold; font-family: Arial; font-size: 13px; border: none;")
            
            row.addWidget(circle)
            row.addSpacing(10)
            row.addWidget(label)
            row.addStretch()
            overlay_layout.addLayout(row)
            
        # Pozicionuojame legendą viršuje dešinėje
        self.legend_overlay.move(10, 10) # Pradinė pozicija
        
        layout.addWidget(self.plotter_container)
        
        # "Vieno pikselio" atnaujinimas, kad legenda atsirastų tinkamoje vietoje po užkrovimo
        QtCore.QTimer.singleShot(100, lambda: self.resizeEvent(None))
 
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Visada laikome legendą dešiniajame viduryje
        if hasattr(self, 'legend_overlay'):
            pw = self.plotter.interactor.width()
            ph = self.plotter.interactor.height()
            lw = self.legend_overlay.width()
            lh = self.legend_overlay.height()
            self.legend_overlay.move(pw - lw - 20, (ph - lh) // 2)
 
    def toggle_background(self, state):
        if self.bg_check.isChecked():
            self.plotter.set_background('white')
        else:
            self.plotter.set_background('#0d0d0d', top='#1a1a2e')
        self.plotter.render()

    def export_screenshot(self):
        import datetime
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self, _("crystal_save_png_title", "Save PNG"),
            f"LLTO_crystal_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            _("crystal_png_filetype", "PNG Image (*.png)")
        )
        if path:
            self.plotter.screenshot(path, transparent_background=True)

    def update_stoichiometry(self):
        la = self.spin_la.value()
        li = self.spin_li.value()
        if la + li > 100:
            li = 100 - la
            self.spin_li.blockSignals(True)
            self.spin_li.setValue(li)
            self.spin_li.blockSignals(False)
        vac = 100 - la - li
        self.lbl_vac.setText(f"{_('crystal_atom_Vac', 'Vacancy')} (%): {vac}")

    def on_temp_changed(self, value):
        self.temperature = value
        self.temp_label.setText(_("crystal_temp_label", "Temperature: {} K").format(value))
        if self.continuous_jumping:
            speed = max(5, int(30 * (300 / self.temperature)))
            self.li_jump_timer.setInterval(speed)

    def apply_phase(self):
        # Nustatome supercelės dydį
        cell_text = self.cell_combo.currentText()
        if "6×2×2" in cell_text:
            nx, ny, nz = 6, 2, 2
        elif "6×3×3" in cell_text:
            nx, ny, nz = 6, 3, 3
        else:
            n = self.cell_combo.currentIndex() + 1
            nx = ny = nz = n
        
        phase_lt = self.phase_combo.currentText()
        phase_en = self.PHASE_MAP.get(phase_lt, 'Cubic')
        
        # Jei įjungta domenų riba, dvigubiname nx
        if self.domain_check.isChecked():
            nx = nx * 2
            
        self.data.nx = nx
        self.data.ny = ny
        self.data.nz = nz
        
        la_frac = self.spin_la.value() / 100.0
        li_frac = self.spin_li.value() / 100.0
        
        # Sustabdome animaciją, jei ji veikia, kad išvengtume klaidų perkuriant gardelę
        self.li_jump_timer.stop()
        self.continuous_jumping = False
        self.jump_btn.setText(_("crystal_jump_start", "▶ Start Li Hop Animation"))
        self.jump_btn.setStyleSheet("background-color: #2ecc40; color: white; padding: 8px; font-weight: bold;")
        
        if self.jump_actor:
            try:
                self.plotter.remove_actor(self.jump_actor)
            except:
                pass
            self.jump_actor = None
        self.jump_source_idx = -1
        self.jump_target_idx = -1

        self.data.build(phase=phase_en, la_frac=la_frac, li_frac=li_frac, twinned=self.domain_check.isChecked())
        
        # Saugiai nunuliname posvyrį be signalų, kad išvengtume IndexError (Index out of range) kol aktoriai dar neperkurti
        self.tilt_slider.blockSignals(True)
        self.tilt_slider.setValue(0)
        self.tilt_slider.blockSignals(False)
        
        self.tilt_label.setText(_("crystal_tilt_label", "Octahedron tilt: {}°").format(0))
        self._rebuild_scene()

    def _rebuild_scene(self):
        self.plotter.clear()
        self.actors = []
        self.bond_actors = []
        self.domain_boundary_actor = None
        
        # Draw bonds first
        for i, (idx1, idx2) in enumerate(self.data.bonds):
            p1 = self.data.atoms[idx1]['pos']
            p2 = self.data.atoms[idx2]['pos']
            cyl = pv.Cylinder(center=(p1+p2)/2, direction=p2-p1, radius=0.024, height=np.linalg.norm(p2-p1))
            actor = self.plotter.add_mesh(cyl, color='#aaaaaa', smooth_shading=True)
            self.bond_actors.append(actor)
            
        # Parenkame stilių pagal parinktį
        current_style = IONIC_RADII_STYLE if self.realistic_check.isChecked() else ATOM_STYLE
        
        # Draw atoms
        for i, atom in enumerate(self.data.atoms):
            if atom['type'] in ['Li', 'Vac']:
                # Visada piešiame "debesėlį" (A-site vietą)
                style_v = current_style['Vac']
                sphere_v = pv.Sphere(radius=style_v['radius'], center=atom['pos'], theta_resolution=30, phi_resolution=30)
                v_actor = self.plotter.add_mesh(sphere_v, color=style_v['color'], opacity=style_v.get('opacity', 1.0), smooth_shading=True)
                self.a_site_actors[i] = v_actor
                
                # Jei tai Li, į vidų įdedame kietą sferą
                if atom['type'] == 'Li':
                    style_l = current_style['Li']
                    sphere_l = pv.Sphere(radius=style_l['radius'], center=atom['pos'], theta_resolution=30, phi_resolution=30)
                    l_actor = self.plotter.add_mesh(sphere_l, color=style_l['color'], smooth_shading=True)
                    self.actors.append(l_actor)
                else:
                    self.actors.append(None)
            else:
                style = current_style[atom['type']]
                sphere = pv.Sphere(radius=style['radius'], center=atom['pos'], theta_resolution=30, phi_resolution=30)
                actor = self.plotter.add_mesh(sphere, color=style['color'], opacity=style.get('opacity', 1.0), smooth_shading=True)
                self.actors.append(actor)

        # Domenų riba (pagal varnelę)
        if self.domain_check.isChecked():
            self._draw_domain_boundary()
            
        # Deguonies langai
        if self.window_check.isChecked():
            self._draw_oxygen_windows()

        self.plotter.reset_camera()

    def _draw_domain_boundary(self):
        nx = self.data.nx
        ny = self.data.ny
        nz = self.data.nz
        # Plokštuma ties x = nx/2 (vidurys)
        x_mid = nx / 2.0
        plane = pv.Plane(
            center=(x_mid, ny / 2.0, nz / 2.0),
            direction=(1, 0, 0),
            i_size=ny + 0.5,
            j_size=nz + 0.5
        )
        self.domain_boundary_actor = self.plotter.add_mesh(plane, color='#f39c12', opacity=0.4, label=_("crystal_domain_boundary_label", "Domain boundary"), style='surface', show_edges=True, edge_color='#e67e22')
        visible = self.domain_check.isChecked()
        self.domain_boundary_actor.SetVisibility(visible)

    def _toggle_domain_boundary(self):
        if self.domain_boundary_actor is not None:
            self.domain_boundary_actor.SetVisibility(self.domain_check.isChecked())
            self.plotter.render()

    def _toggle_oxygen_windows(self):
        if self.window_check.isChecked():
            self._draw_oxygen_windows()
        else:
            for actor in self.window_actors:
                self.plotter.remove_actor(actor)
            self.window_actors = []
        self.plotter.render()

    def _draw_oxygen_windows(self):
        # Išvalome senus langus
        for actor in self.window_actors:
            self.plotter.remove_actor(actor)
        self.window_actors = []

        o_map = {tuple(np.round(self.data.atoms[idx]['original_pos'], 2)): idx for idx in self.data.o_sites}
        nx, ny, nz = self.data.nx, self.data.ny, self.data.nz
        
        def add_window(p_origs):
            indices = []
            for p in p_origs:
                key = tuple(np.round(p, 2))
                if key in o_map:
                    indices.append(o_map[key])
                else:
                    return # Trūksta deguonies atomo ribose
            
            if len(indices) == 4:
                # Naudojame esamas (pasisukusias) pozicijas
                pts = np.array([self.data.atoms[idx]['pos'] for idx in indices])
                # Sukuriame poligoną (kvadratą/romba)
                # Reikia surikiuoti taškus, kad nebūtų persisukę (O1 ir O2 yra viena ašis, O3 ir O4 - kita)
                # Surikiuojame: O1, O3, O2, O4
                poly_pts = np.array([pts[0], pts[2], pts[1], pts[3]])
                face = [4, 0, 1, 2, 3]
                mesh = pv.PolyData(poly_pts, face)
                actor = self.plotter.add_mesh(mesh, color='#00f2ff', opacity=0.3, smooth_shading=True)
                self.window_actors.append(actor)

        # X krypties langai
        for x in np.arange(0.5, nx, 1.0):
            for y in range(ny + 1):
                for z in range(nz + 1):
                    add_window([(x, y-0.5, z), (x, y+0.5, z), (x, y, z-0.5), (x, y, z+0.5)])
        
        # Y krypties langai
        for y in np.arange(0.5, ny, 1.0):
            for x in range(nx + 1):
                for z in range(nz + 1):
                    add_window([(x-0.5, y, z), (x+0.5, y, z), (x, y, z-0.5), (x, y, z+0.5)])
                    
        # Z krypties langai
        for z in np.arange(0.5, nz, 1.0):
            for x in range(nx + 1):
                for y in range(ny + 1):
                    add_window([(x-0.5, y, z), (x+0.5, y, z), (x, y-0.5, z), (x, y+0.5, z)])

    def on_tilt_changed(self, value):
        # Ti-O-Ti kampas yra maždaug 180 - 2 * tilt
        ti_o_ti = 180 - 2 * abs(value)
        self.tilt_label.setText(_("crystal_tilt_format", "Octahedron tilt: {}° (Ti-O-Ti: {}°)").format(value, ti_o_ti))
        self._apply_tilt(value)

    def _apply_tilt(self, angle_deg):
        angle_rad = np.radians(angle_deg)
        phase_lt = self.phase_combo.currentText()
        phase_en = self.PHASE_MAP.get(phase_lt, 'Cubic')
        
        for idx in self.data.o_sites:
            atom = self.data.atoms[idx]
            orig_pos = atom['original_pos']
            
            # Find nearest Ti
            min_dist = 999
            nearest_ti_idx = -1
            for ti_coord, ti_idx in self.data.ti_sites.items():
                dist = np.linalg.norm(orig_pos - self.data.atoms[ti_idx]['original_pos'])
                if dist < min_dist:
                    min_dist = dist
                    nearest_ti_idx = ti_idx
            
            if nearest_ti_idx != -1:
                ti_pos = self.data.atoms[nearest_ti_idx]['original_pos']
                dx, dy, dz = orig_pos - ti_pos
                
                # Nustatome pasvirimą pagal domeną
                if phase_en == 'Twinned Domains':
                    if ti_pos[0] < self.data.nx / 2.0:
                        # Pirmas domenas: sukam aplink X
                        if abs(dz) < 0.1: # equatorial
                            c, s = np.cos(angle_rad), np.sin(angle_rad)
                            # Supaprastinta rotacija aplink X
                            new_dy = dy * c - dz * s
                            new_dz = dy * s + dz * c
                            atom['pos'] = ti_pos + [dx, new_dy, new_dz]
                        else: # axial
                            atom['pos'] = orig_pos.copy()
                    else:
                        # Antras domenas: sukam aplink Y
                        if abs(dz) < 0.1: # equatorial
                            c, s = np.cos(angle_rad), np.sin(angle_rad)
                            new_dx = dx * c - dz * s
                            new_dz = dx * s + dz * c
                            atom['pos'] = ti_pos + [new_dx, dy, new_dz]
                        else:
                            atom['pos'] = orig_pos.copy()
                else:
                    # Standartinis posvyris aplink Z
                    if abs(orig_pos[2] - ti_pos[2]) < 0.1:
                        layer_z = round(ti_pos[2] - 0.5)
                        sign = 1 if layer_z % 2 == 0 else -1
                        theta = sign * angle_rad
                        c, s = np.cos(theta), np.sin(theta)
                        new_dx = dx * c - dy * s
                        new_dy = dx * s + dy * c
                        atom['pos'] = ti_pos + [new_dx, new_dy, dz]
                    else:
                        atom['pos'] = orig_pos.copy()
            
        # Atnaujiname vizualizaciją (aktorių pozicijas)
        for idx, atom in enumerate(self.data.atoms):
            if idx < len(self.actors) and self.actors[idx]:
                p = atom['pos']
                orig = atom['original_pos']
                self.actors[idx].SetPosition(p[0]-orig[0], p[1]-orig[1], p[2]-orig[2])
            
        # Atnaujiname ryšius
        for actor in self.bond_actors:
            self.plotter.remove_actor(actor)
        self.bond_actors = []
        
        # Tik mažoms sistemoms rodome ryšius realiu laiku
        if self.data.nx * self.data.ny * self.data.nz <= 64:
            for start_idx, end_idx in self.data.bonds:
                p1 = self.data.atoms[start_idx]['pos']
                p2 = self.data.atoms[end_idx]['pos']
                line = pv.Line(p1, p2)
                actor = self.plotter.add_mesh(line, color='grey', line_width=2, opacity=0.4, reset_camera=False)
                self.bond_actors.append(actor)
            
        # Atnaujiname deguonies langus
        if self.window_check.isChecked():
            self._draw_oxygen_windows()
            
        self.plotter.render()

    def update_stoichiometry(self):
        la = self.spin_la.value()
        li = self.spin_li.value()
        vac = 100.0 - la - li
        if vac < 0: vac = 0
        self.lbl_vac.setText(f"{_('crystal_atom_Vac', 'Vacancy')} (%): {vac:.1f}")

    def toggle_jump_animation(self):
        if self.continuous_jumping:
            self.continuous_jumping = False
            self.jump_btn.setText(_("crystal_jump_start", "▶ Start Li Hop Animation"))
            self.jump_btn.setStyleSheet("background-color: #2ecc40; color: white; padding: 8px; font-weight: bold;")
            # Sustabdome laikmatį, bet NIEKO nenaikiname - jonas lieka ten, kur yra
            self.li_jump_timer.stop()
        else:
            self.continuous_jumping = True
            self.jump_btn.setText(_("crystal_jump_stop", "⏸ Stop Jump Animation"))
            self.jump_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
            # Jei jau buvo pradėtas šuolis (yra jump_actor), tiesiog pratęsiame laikmatį
            if self.jump_source_idx != -1:
                speed = max(5, int(30 * (300 / self.temperature)))
                self.li_jump_timer.start(speed)
            else:
                self._start_next_jump()

    def _start_next_jump(self):
        li_indices = [i for i, a in enumerate(self.data.atoms) if a['type'] == 'Li']
        vac_indices = [i for i, a in enumerate(self.data.atoms) if a['type'] == 'Vac']
        
        field_active = self.field_check.isChecked()
        target_vec = np.array([1, 0, 0])
        
        possible_pairs = []
        for li_idx in li_indices:
            p1 = self.data.atoms[li_idx]['pos']
            for vac_idx in vac_indices:
                p2 = self.data.atoms[vac_idx]['pos']
                
                dist = np.linalg.norm(p1 - p2)
                is_pbc = False
                
                # PBC "wrap" check
                if field_active and abs(p1[1]-p2[1]) < 0.1 and abs(p1[2]-p2[2]) < 0.1:
                    if p1[0] >= self.data.nx - 0.1 and p2[0] <= 0.1:
                        is_pbc = True
                        dist = 1.0
                
                if abs(dist - 1.0) < 0.25:
                    weight = 1.0
                    move_vec = p2 - p1
                    if is_pbc: move_vec = np.array([1, 0, 0])
                    
                    if field_active:
                        dot = np.dot(move_vec, target_vec)
                        if dot > 0.5: weight = 20.0 # Stiprus polinkis judėti su lauku
                        elif dot < -0.5: weight = 0.05 # Maža tikimybė judėti prieš lauką
                        else: weight = 2.0 # Šoninis judėjimas
                        
                    possible_pairs.append({
                        'li': li_idx, 'vac': vac_idx, 
                        'weight': weight, 'pbc': is_pbc, 'outflow': False
                    })
        
        # PRIDEDAME: Galimybė iššokti į erdvę iš dešiniojo krašto
        if field_active:
            for li_idx in li_indices:
                p1 = self.data.atoms[li_idx]['pos']
                if p1[0] >= self.data.nx - 0.1:
                    possible_pairs.append({
                        'li': li_idx, 'vac': -1, # Virtuali vakansija lauke
                        'weight': 15.0, 'pbc': False, 'outflow': True
                    })
        
        if possible_pairs:
            # Parenkame šuolį pagal svorius
            weights = [p['weight'] for p in possible_pairs]
            choice = random.choices(possible_pairs, weights=weights, k=1)[0]
            self.jump_source_idx = choice['li']
            self.jump_target_idx = choice['vac']
            self.is_pbc_jump = choice.get('pbc', False)
            self.is_outflow = choice.get('outflow', False)
        else:
            self.jump_source_idx = -1
            self.jump_target_idx = -1
            self.is_pbc_jump = False
            self.is_outflow = False
        
        if self.jump_source_idx == -1:
            self.continuous_jumping = False
            self.jump_btn.setText(_("crystal_jump_field_active", "▶ Start Hop (Field Active)") if field_active else _("crystal_jump_start", "▶ Start Li Hop Animation"))
            self.jump_btn.setStyleSheet("background-color: #2ecc40; color: white; padding: 8px; font-weight: bold;")
            if not field_active:
                QtWidgets.QMessageBox.information(self, _("msg_info", "Information"), _("crystal_no_pairs", "No adjacent Li-Vacancy pairs found for animation."))
            return
            
        self.jump_frame = 0
        p1 = self.data.atoms[self.jump_source_idx]['pos']
        
        current_style = IONIC_RADII_STYLE if self.realistic_check.isChecked() else ATOM_STYLE
        style = current_style['Li']
        sphere = pv.Sphere(radius=style['radius'], center=p1, theta_resolution=30, phi_resolution=30)
        self.jump_actor = self.plotter.add_mesh(sphere, color=style['color'], smooth_shading=True, reset_camera=False)
        
        # Paslepiame pradinį Li atomą tik PO to, kai sukūrėme animacinį "vaiduoklį" (kad nebūtų mirgėjimo)
        if self.actors[self.jump_source_idx]:
            self.actors[self.jump_source_idx].SetVisibility(False)
        
        self.plotter.render()
        
        speed = max(5, int(30 * (300 / self.temperature)))
        self.li_jump_timer.start(speed)

    def _jump_step(self):
        if self.jump_source_idx == -1 or self.jump_actor is None:
            self.li_jump_timer.stop()
            return
            
        self.jump_frame += 1
        total_frames = 30
        
        if self.jump_frame > total_frames:
            self._finish_current_jump()
            return # Visada baigiame šią funkciją, jei šuolis baigtas
            
        p1 = self.data.atoms[self.jump_source_idx]['pos']
        
        if getattr(self, 'is_outflow', False):
            # Juda tiesiai iš gardelės į erdvę (+X kryptimi)
            p2_virtual = p1 + np.array([1.2, 0, 0])
            new_pos = p1 + (p2_virtual - p1) * (self.jump_frame / total_frames)
        elif getattr(self, 'is_pbc_jump', False):
            # PBC šuolis
            p2_virtual = p1 + np.array([1.0, 0, 0])
            new_pos = p1 + (p2_virtual - p1) * (self.jump_frame / total_frames)
        else:
            p2 = self.data.atoms[self.jump_target_idx]['pos']
            new_pos = p1 + (p2 - p1) * (self.jump_frame / total_frames)
            
        translation = new_pos - p1
        self.jump_actor.SetPosition(translation[0], translation[1], translation[2])
        self.plotter.render()

    def _finish_current_jump(self):
        if self.jump_source_idx == -1:
            return
            
        self.li_jump_timer.stop()
        
        if getattr(self, 'is_outflow', False):
            # JONAS IŠSKRIDO
            self.data.atoms[self.jump_source_idx]['type'] = 'Vac'
            if self.actors[self.jump_source_idx]:
                self.plotter.remove_actor(self.actors[self.jump_source_idx])
            self.actors[self.jump_source_idx] = None
            
            if self.jump_actor:
                self.plotter.remove_actor(self.jump_actor)
                self.jump_actor = None
            
            # Įtekėjimas iš kitos pusės (kad palaikytume srautą)
            left_vacs = [i for i, a in enumerate(self.data.atoms) if a['type'] == 'Vac' and a['pos'][0] <= 0.1]
            if left_vacs:
                new_li_idx = random.choice(left_vacs)
                self.data.atoms[new_li_idx]['type'] = 'Li'
                current_style = IONIC_RADII_STYLE if self.realistic_check.isChecked() else ATOM_STYLE
                style = current_style['Li']
                sphere = pv.Sphere(radius=style['radius'], center=self.data.atoms[new_li_idx]['pos'], theta_resolution=30, phi_resolution=30)
                self.actors[new_li_idx] = self.plotter.add_mesh(sphere, color=style['color'], smooth_shading=True, reset_camera=False)
        else:
            # Standartinis arba PBC šuolis
            self.data.atoms[self.jump_source_idx]['type'] = 'Vac'
            self.data.atoms[self.jump_target_idx]['type'] = 'Li'
            
            p2 = self.data.atoms[self.jump_target_idx]['pos']
            p1 = self.data.atoms[self.jump_source_idx]['pos']
            
            self.jump_actor.SetPosition(p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])
            self.actors[self.jump_target_idx] = self.jump_actor
            self.jump_actor = None
            
            if self.actors[self.jump_source_idx]:
                self.plotter.remove_actor(self.actors[self.jump_source_idx])
            self.actors[self.jump_source_idx] = None
        
        self.jump_source_idx = -1
        self.jump_target_idx = -1
        self.is_outflow = False
        self.is_pbc_jump = False
        self.plotter.render()
        
        # Jei įjungtas nuolatinis režimas, pradedame kitą šuolį
        if self.continuous_jumping:
            self._start_next_jump()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    window.setWindowTitle(_("crystal_title", "LLTO Crystal Structure (3D)"))
    window.resize(1200, 800)
    
    viewer = CrystalViewerWidget()
    window.setCentralWidget(viewer)
    
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
