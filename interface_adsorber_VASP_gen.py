#!/usr/bin/env python3
"""
Cu / Cu-Ag / Cu-Au slab and adsorbate VASP generator workflow.

Adsorbate site assignments:
  - CO:   hollow
  - CH:   hollow
  - CH2:  hollow
  - CHO:  bridge
  - CHOH: atop
  - CH3:  atop
  - CH4:  atop
  - COCO: two adjacent hollow-site CO
  - OCCO: pair/bridge over metal pair

VASP INCAR supports relax / static / cp modes.
NERSC submit.sh in user-specified format.
"""

import math
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import numpy as np
from scipy.spatial import Delaunay

from ase import Atoms
from ase.build import fcc111
from ase.constraints import FixAtoms
from ase.io import write
from ase.neighborlist import NeighborList


# =========================
# Master config block
# =========================

CONFIG = {
    "bulk": {
        "a_cu": 3.615,
        "a_ag": 4.086,
        "a_au": 4.078,
    },

    "slab": {
        "layers": 4,
        "vacuum_top": 15.0,
        "fix_bottom_layers_pure_cu": 2,
        "fix_bottom_layers_interface": 1,
        "cu_slab_size": (4, 3),
    },

    "interface": {
        "match_mode": "strained_cu",
        "strained_repeats_x_each_side": 4,
        "transverse_repeats": 3,
        "commensurate_pair_cu_ag": (9, 8),
        "commensurate_pair_cu_au": (9, 8),
    },

    "adsorbates": {
        "enabled": True,
        "species_list": [
            "CO", "CHO", "CHOH", "CH", "CH2", "CH3", "CH4",
            "COCO", "OCCO"
        ],

        "placement_default_pure": "terrace",
        "placement_default_interface": "interface",

        "placement_override": None,
        "site_mode_override": None,

        "z_anchor_top": 1.85,
        "z_anchor_bridge": 1.50,
        "z_anchor_hollow": 1.30,

        "neighbor_cutoff": 3.2,

        "bond_CO": 1.16,
        "bond_CC": 1.40,
        "bond_CH": 1.09,
        "bond_OH": 0.97,

        "angle_tetra": 109.5,
        "angle_trig": 120.0,
    },

    "vasp": {
        "incar_mode": "relax",
        "standard": {
            "ISPIN": 2,
            "PREC": "Accurate",
            "ENCUT": 400,
            "EDIFF": 1e-5,
            "EDIFFG": -0.02,
            "NELM": 120,
            "ALGO": "Normal",
            "GGA": "PE",
            "IVDW": 11,
            "LASPH": ".TRUE.",
            "IBRION": 2,
            "NSW": 300,
            "ISIF": 2,
            "ISMEAR": 1,
            "SIGMA": 0.2,
            "LREAL": "Auto",
            "ISYM": 0,
            "ICHARG": 2,
            "LMAXMIX": 4,
            "LWAVE": ".FALSE.",
            "LCHARG": ".FALSE.",
            "LDIPOL": ".TRUE.",
            "IDIPOL": 3,
        },
        "static_overrides": {
            "EDIFF": 1e-6,
            "IBRION": -1,
            "NSW": 0,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "ICHARG": 0,
        },
        "cp_extras": {
            "LSOL": ".TRUE.",
            "EB_K": 78.4,
            "LCEP": ".TRUE.",
            "NESCHEME": 3,
            "FERMICONVERGE": 0.05,
            "TARGETMU": None,
        },
        "kpoints": {
            "Cu111": (5, 3, 1),
            "interface": (1, 1, 1),
        },
    },

    "nersc": {
        "account": "mxxxx",
        "walltime": "8:00:00",
        "nodes": 2,
        "constraint": "cpu",
        "mail_user": "user@example.com",
        "mail_type": "ALL",
        "module": "vasp/6.4.3-cpu",
        "omp_num_threads": 2,
        "omp_places": "threads",
        "omp_proc_bind": "spread",
        "srun_cmd": "srun -n 128 -c 4 --cpu-bind=cores vasp_std",
    },

    "output": {
        "root_dir": "workflow_output",
        "write_metadata_json": True,
        "write_potcar_placeholder": True,
    },
}


# =========================
# Validation
# =========================

def validate_config(cfg: Dict):
    assert cfg["interface"]["match_mode"] in ("strained_cu", "commensurate_1d")
    assert cfg["adsorbates"]["placement_override"] in (
        None, "terrace", "interface")
    assert cfg["adsorbates"]["site_mode_override"] in (
        None, "site_auto", "top", "bridge", "hollow",
        "pair_cu_cu", "pair_interface_cu_cu", "pair_interface_cross")
    assert cfg["nersc"]["constraint"] in ("cpu", "gpu")
    assert cfg["vasp"]["incar_mode"] in ("relax", "static", "cp")


# =========================
# Utilities
# =========================

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def fcc111_surface_lattice(a_fcc: float) -> float:
    return a_fcc / math.sqrt(2.0)


def lattice_mismatch(a1: float, a2: float) -> float:
    return (a2 - a1) / a1


def report_basic_mismatch(a_cu: float, a_other: float, label: str):
    mismatch = lattice_mismatch(a_cu, a_other) * 100.0
    print(f"{label} cubic mismatch: {mismatch:.2f}%")
    print(f"{label} (111) in-plane mismatch: {mismatch:.2f}%")


def apply_bottom_layer_fix(atoms: Atoms, n_layers_to_fix: int):
    z = atoms.positions[:, 2]
    unique_z = np.unique(np.round(z, 6))
    unique_z.sort()
    fixed_layers = unique_z[:n_layers_to_fix]
    mask = np.isin(np.round(z, 6), fixed_layers)
    atoms.set_constraint(FixAtoms(mask=mask))


def shift_to_top_vacuum_only(atoms: Atoms, vacuum_top: float) -> Atoms:
    atoms = atoms.copy()
    z = atoms.positions[:, 2]
    zmin = z.min()
    zmax = z.max()
    atoms.positions[:, 2] -= zmin
    cell = atoms.cell.copy()
    cell[2, 2] = (zmax - zmin) + vacuum_top
    atoms.set_cell(cell, scale_atoms=False)
    atoms.set_pbc([True, True, True])
    return atoms


def rotation_matrix_from_x_to_vec(vec: np.ndarray) -> np.ndarray:
    v = np.array(vec, dtype=float)
    if np.linalg.norm(v[:2]) < 1e-12:
        return np.eye(3)
    v[2] = 0.0
    v = v / np.linalg.norm(v)
    c = v[0]
    s = v[1]
    return np.array([
        [c, -s, 0.0],
        [s,  c, 0.0],
        [0.0, 0.0, 1.0],
    ])


def mic_vector(atoms: Atoms, i: int, j: int) -> np.ndarray:
    """Minimum image convention vector from atom i to atom j."""
    cell = np.array(atoms.cell)
    inv_cell = np.linalg.inv(cell)
    delta = atoms.positions[j] - atoms.positions[i]
    frac = delta @ inv_cell
    frac -= np.round(frac)
    return frac @ cell


def adaptive_cutoff(atoms: Atoms, candidates: List[int],
                    margin: float = 1.20) -> float:
    """
    Compute an adaptive neighbor cutoff from the actual nearest-neighbor
    distance among candidate atoms (using MIC).  Returns
    nn_dist * margin.  Falls back to 3.5 if fewer than 2 candidates.
    """
    if len(candidates) < 2:
        return 3.5
    min_d = None
    for ii in range(len(candidates)):
        for jj in range(ii + 1, len(candidates)):
            d = atoms.get_distance(candidates[ii], candidates[jj], mic=True)
            if min_d is None or d < min_d:
                min_d = d
    if min_d is None or min_d < 0.5:
        return 3.5
    return min_d * margin


# =========================
# POSCAR writer with unique element symbols
# =========================

def sort_atoms_by_unique_elements(atoms: Atoms) -> Atoms:
    """
    Re-order atoms so that each element appears as a single contiguous
    block.  Produces POSCAR lines like 'Cu Au C O H' with one count
    per element instead of 'Cu Au O C O'.
    """
    symbols = atoms.get_chemical_symbols()
    seen = set()
    element_order = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            element_order.append(s)

    sorted_indices = []
    for elem in element_order:
        sorted_indices.extend(
            i for i, s in enumerate(symbols) if s == elem
        )

    new_atoms = atoms[sorted_indices]
    new_atoms.set_cell(atoms.cell)
    new_atoms.set_pbc(atoms.pbc)
    if atoms.constraints:
        old_fixed = set()
        for c in atoms.constraints:
            if isinstance(c, FixAtoms):
                old_fixed.update(c.index)
        if old_fixed:
            inv_map = {old_i: new_i
                       for new_i, old_i in enumerate(sorted_indices)}
            new_fixed = [inv_map[oi] for oi in old_fixed if oi in inv_map]
            new_atoms.set_constraint(FixAtoms(indices=new_fixed))
    return new_atoms


def write_poscar(path, atoms):
    """Write POSCAR with each element listed exactly once."""
    sorted_atoms = sort_atoms_by_unique_elements(atoms)
    write(str(path), sorted_atoms, format="vasp", direct=True, vasp5=True)


# =========================
# Slab builders
# =========================

def build_pure_cu111_slab(cfg: Dict) -> Atoms:
    slab_cfg = cfg["slab"]
    bulk_cfg = cfg["bulk"]
    slab = fcc111(
        "Cu",
        size=(slab_cfg["cu_slab_size"][0], slab_cfg["cu_slab_size"][1],
              slab_cfg["layers"]),
        a=bulk_cfg["a_cu"],
        vacuum=0.0
    )
    slab = shift_to_top_vacuum_only(slab, slab_cfg["vacuum_top"])
    apply_bottom_layer_fix(slab, slab_cfg["fix_bottom_layers_pure_cu"])
    return slab


def build_strained_interface_111(
    left_symbol: str, right_symbol: str,
    a_left: float, a_right: float, cfg: Dict
) -> Tuple[Atoms, Dict]:
    slab_cfg = cfg["slab"]
    int_cfg = cfg["interface"]
    common_a = a_right
    rx = int_cfg["strained_repeats_x_each_side"]
    ry = int_cfg["transverse_repeats"]

    left = fcc111(left_symbol, size=(rx, ry, slab_cfg["layers"]),
                  a=common_a, vacuum=0.0)
    right = fcc111(right_symbol, size=(rx, ry, slab_cfg["layers"]),
                   a=common_a, vacuum=0.0)
    right.positions += np.array(left.cell[0])

    merged = left + right
    new_cell = left.cell.copy()
    new_cell[0] = left.cell[0] + right.cell[0]
    merged.set_cell(new_cell)
    merged.set_pbc([True, True, True])
    merged = shift_to_top_vacuum_only(merged, slab_cfg["vacuum_top"])
    apply_bottom_layer_fix(merged, slab_cfg["fix_bottom_layers_interface"])

    meta = {
        "match_mode": "strained_cu",
        "left_symbol": left_symbol,
        "right_symbol": right_symbol,
        "common_a_fcc": common_a,
        "imposed_strain_on_left_percent":
            (a_right - a_left) / a_left * 100.0,
        "total_atoms": len(merged),
    }
    return merged, meta


def build_1d_commensurate_interface_111(
    left_symbol: str, right_symbol: str,
    a_left: float, a_right: float,
    pair: Tuple[int, int], cfg: Dict
) -> Tuple[Atoms, Dict]:
    slab_cfg = cfg["slab"]
    int_cfg = cfg["interface"]
    m, n = pair
    ry = int_cfg["transverse_repeats"]

    a111_left = fcc111_surface_lattice(a_left)
    a111_right = fcc111_surface_lattice(a_right)
    L_left = m * a111_left
    L_right = n * a111_right
    residual = (L_right - L_left) / L_left
    common_length = 0.5 * (L_left + L_right)

    left = fcc111(left_symbol, size=(m, ry, slab_cfg["layers"]),
                  a=a_left, vacuum=0.0)
    right = fcc111(right_symbol, size=(n, ry, slab_cfg["layers"]),
                   a=a_right, vacuum=0.0)

    left_a_len = np.linalg.norm(left.cell[0])
    right_a_len = np.linalg.norm(right.cell[0])
    left_scale = common_length / left_a_len
    right_scale = common_length / right_a_len

    left_pos = left.positions.copy()
    right_pos = right.positions.copy()
    left_pos[:, 0] *= left_scale
    right_pos[:, 0] *= right_scale
    left.set_positions(left_pos)
    right.set_positions(right_pos)

    left_cell = left.cell.copy()
    right_cell = right.cell.copy()
    left_cell[0] = left.cell[0] * left_scale
    right_cell[0] = right.cell[0] * right_scale
    left.set_cell(left_cell, scale_atoms=False)
    right.set_cell(right_cell, scale_atoms=False)

    right.positions += np.array(left.cell[0])
    merged = left + right
    new_cell = left.cell.copy()
    new_cell[0] = left.cell[0] + right.cell[0]
    merged.set_cell(new_cell)
    merged.set_pbc([True, True, True])
    merged = shift_to_top_vacuum_only(merged, slab_cfg["vacuum_top"])
    apply_bottom_layer_fix(merged, slab_cfg["fix_bottom_layers_interface"])

    meta = {
        "match_mode": "commensurate_1d",
        "left_symbol": left_symbol,
        "right_symbol": right_symbol,
        "pair": [m, n],
        "residual_mismatch_percent": residual * 100.0,
        "common_length": common_length,
        "total_atoms": len(merged),
    }
    return merged, meta


# =========================
# Site finding
# =========================

def get_top_layer_indices(atoms: Atoms, tol: float = 0.5) -> List[int]:
    z = atoms.positions[:, 2]
    zmax = np.max(z)
    return [i for i, zi in enumerate(z) if abs(zi - zmax) < tol]


def get_top_cu_indices(atoms: Atoms, tol: float = 0.5) -> List[int]:
    top = set(get_top_layer_indices(atoms, tol=tol))
    return [i for i, a in enumerate(atoms) if a.symbol == "Cu" and i in top]


def get_interface_cu_indices(
    atoms: Atoms, neighbor_cutoff: float = 3.2, tol: float = 0.5
) -> List[int]:
    """
    Find top-layer Cu atoms that have at least one Ag or Au neighbor
    (in any layer) within neighbor_cutoff.
    """
    top = set(get_top_layer_indices(atoms, tol=tol))
    search_cutoff = max(neighbor_cutoff, 3.5)
    cutoffs = [search_cutoff / 2.0] * len(atoms)
    nl = NeighborList(cutoffs, self_interaction=False, bothways=True)
    nl.update(atoms)
    symbols = atoms.get_chemical_symbols()
    indices = []
    for i, sym in enumerate(symbols):
        if sym != "Cu" or i not in top:
            continue
        neighbors, _ = nl.get_neighbors(i)
        if any(symbols[j] in ("Ag", "Au") for j in neighbors):
            indices.append(i)
    return sorted(set(indices))


def get_interface_region_indices(
    atoms: Atoms, neighbor_cutoff: float = 3.2, tol: float = 0.5
) -> List[int]:
    """
    Find ALL top-layer atoms (Cu, Ag, Au) in the interface region.
    An atom is in the interface region if it is a top-layer Cu with
    an Ag/Au neighbor, OR a top-layer Ag/Au with a Cu neighbor.
    This gives enough atoms to form hollow-site triangles at the
    boundary.
    """
    top = set(get_top_layer_indices(atoms, tol=tol))
    search_cutoff = max(neighbor_cutoff, 3.5)
    cutoffs = [search_cutoff / 2.0] * len(atoms)
    nl = NeighborList(cutoffs, self_interaction=False, bothways=True)
    nl.update(atoms)
    symbols = atoms.get_chemical_symbols()
    indices = set()
    for i in top:
        sym = symbols[i]
        neighbors, _ = nl.get_neighbors(i)
        top_neighbors = [j for j in neighbors if j in top]
        if sym == "Cu":
            if any(symbols[j] in ("Ag", "Au") for j in top_neighbors):
                indices.add(i)
                # Also add the neighboring Ag/Au top-layer atoms
                for j in top_neighbors:
                    if symbols[j] in ("Ag", "Au"):
                        indices.add(j)
        elif sym in ("Ag", "Au"):
            if any(symbols[j] == "Cu" for j in top_neighbors):
                indices.add(i)
                for j in top_neighbors:
                    if symbols[j] == "Cu":
                        indices.add(j)
    return sorted(indices)


def get_terrace_cu_indices(
    atoms: Atoms, neighbor_cutoff: float = 3.2, tol: float = 0.5
) -> List[int]:
    top_cu = set(get_top_cu_indices(atoms, tol=tol))
    interface_cu = set(get_interface_cu_indices(
        atoms, neighbor_cutoff=neighbor_cutoff, tol=tol))
    terrace = sorted(top_cu - interface_cu)
    if terrace:
        return terrace
    return sorted(top_cu)


def choose_central_index(atoms: Atoms, candidates: List[int]) -> int:
    if not candidates:
        raise RuntimeError("No candidate indices provided.")
    a_vec = np.array(atoms.cell[0])
    b_vec = np.array(atoms.cell[1])
    center = 0.5 * (a_vec + b_vec)
    best_i, best_d = None, None
    for i in candidates:
        d = np.linalg.norm(atoms.positions[i][:2] - center[:2])
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return int(best_i)


def get_neighbor_pairs(
    atoms: Atoms, candidates: List[int], max_dist: float = 3.2
) -> List[Tuple[int, int]]:
    pairs = []
    cand = list(candidates)
    for ii, i in enumerate(cand):
        for j in cand[ii + 1:]:
            if atoms.get_distance(i, j, mic=True) <= max_dist:
                pairs.append((i, j))
    return pairs


def choose_central_pair(
    atoms: Atoms, pairs: List[Tuple[int, int]]
) -> Tuple[int, int]:
    if not pairs:
        raise RuntimeError("No candidate pairs provided.")
    a_vec = np.array(atoms.cell[0])
    b_vec = np.array(atoms.cell[1])
    center = 0.5 * (a_vec + b_vec)
    best_pair, best_d = None, None
    for i, j in pairs:
        mid = 0.5 * (atoms.positions[i] + atoms.positions[j])
        d = np.linalg.norm(mid[:2] - center[:2])
        if best_d is None or d < best_d:
            best_d = d
            best_pair = (i, j)
    return best_pair


def get_interface_neighbor_pairs(
    atoms: Atoms, neighbor_cutoff: float = 3.2
) -> List[Tuple[int, int]]:
    cu = get_interface_cu_indices(atoms, neighbor_cutoff=neighbor_cutoff)
    nc = adaptive_cutoff(atoms, cu)
    return get_neighbor_pairs(atoms, cu, max_dist=nc)


def get_terrace_neighbor_pairs(
    atoms: Atoms, neighbor_cutoff: float = 3.2
) -> List[Tuple[int, int]]:
    cu = get_terrace_cu_indices(atoms, neighbor_cutoff=neighbor_cutoff)
    nc = adaptive_cutoff(atoms, cu)
    return get_neighbor_pairs(atoms, cu, max_dist=nc)


def get_cross_boundary_pairs(
    atoms: Atoms, neighbor_cutoff: float = 3.2
) -> List[Tuple[int, int]]:
    top = set(get_top_layer_indices(atoms))
    search_cutoff = max(neighbor_cutoff, 3.5)
    cutoffs = [search_cutoff / 2.0] * len(atoms)
    nl = NeighborList(cutoffs, self_interaction=False, bothways=True)
    nl.update(atoms)
    symbols = atoms.get_chemical_symbols()
    seen = set()
    uniq = []
    for i, sym in enumerate(symbols):
        if sym != "Cu" or i not in top:
            continue
        neighbors, _ = nl.get_neighbors(i)
        for j in neighbors:
            if j not in top:
                continue
            if symbols[j] in ("Ag", "Au"):
                key = tuple(sorted((i, j)))
                if key not in seen:
                    seen.add(key)
                    uniq.append((i, j))
    return uniq


# =========================
# Hollow site via Delaunay triangulation with PBC images
# =========================

def _build_pbc_image_points(
    atoms: Atoms, candidates: List[int]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build 2D points for Delaunay triangulation by replicating candidate
    atoms across the 3x3 periodic images in the xy-plane.
    """
    cell = np.array(atoms.cell)
    a_vec = cell[0, :2]
    b_vec = cell[1, :2]

    pos_xy = atoms.positions[candidates, :2]
    n_cand = len(candidates)

    all_pts = []
    all_orig = []
    for ia in (-1, 0, 1):
        for ib in (-1, 0, 1):
            shift = ia * a_vec + ib * b_vec
            all_pts.append(pos_xy + shift[np.newaxis, :])
            all_orig.append(np.arange(n_cand))

    pts_2d = np.vstack(all_pts)
    orig_indices = np.concatenate(all_orig)
    return pts_2d, orig_indices


def find_hollow_triplets_delaunay(
    atoms: Atoms, candidates: List[int], max_edge: float = 3.2
) -> List[Tuple[int, int, int]]:
    """
    Use Delaunay triangulation on PBC-replicated 2D points to find
    all triangles of mutually neighboring top-layer candidate atoms.
    Automatically adapts the edge cutoff from actual nearest-neighbor
    distances if the provided max_edge is too tight.
    """
    if len(candidates) < 3:
        return []

    auto_cut = adaptive_cutoff(atoms, candidates, margin=1.20)
    effective_max_edge = max(max_edge, auto_cut)

    pts_2d, orig_idx = _build_pbc_image_points(atoms, candidates)
    tri = Delaunay(pts_2d)

    seen = set()
    triplets = []

    for simplex in tri.simplices:
        ci = tuple(sorted(orig_idx[s] for s in simplex))
        if ci[0] == ci[1] or ci[1] == ci[2] or ci[0] == ci[2]:
            continue
        if ci in seen:
            continue
        seen.add(ci)

        i, j, k = candidates[ci[0]], candidates[ci[1]], candidates[ci[2]]

        dij = atoms.get_distance(i, j, mic=True)
        dik = atoms.get_distance(i, k, mic=True)
        djk = atoms.get_distance(j, k, mic=True)
        if dij > effective_max_edge or dik > effective_max_edge or \
                djk > effective_max_edge:
            continue

        vij = mic_vector(atoms, i, j)
        vik = mic_vector(atoms, i, k)
        area = 0.5 * np.linalg.norm(np.cross(vij, vik))
        if area < 0.5:
            continue

        triplets.append((i, j, k))

    return triplets


def get_hollow_site_position(
    atoms: Atoms, triplet: Tuple[int, int, int]
) -> np.ndarray:
    """
    Compute centroid of three atoms using fractional coordinates
    to handle periodic boundary conditions correctly.
    """
    i, j, k = triplet
    cell = np.array(atoms.cell)
    inv_cell = np.linalg.inv(cell)

    fi = atoms.positions[i] @ inv_cell
    fj = atoms.positions[j] @ inv_cell
    fk = atoms.positions[k] @ inv_cell

    dfj = fj - fi
    dfk = fk - fi
    dfj -= np.round(dfj)
    dfk -= np.round(dfk)

    fj_w = fi + dfj
    fk_w = fi + dfk

    f_center = (fi + fj_w + fk_w) / 3.0
    return f_center @ cell


def choose_central_triplet(
    atoms: Atoms, triplets: List[Tuple[int, int, int]]
) -> Tuple[int, int, int]:
    if not triplets:
        raise RuntimeError("No candidate triplets provided.")
    a_vec = np.array(atoms.cell[0])
    b_vec = np.array(atoms.cell[1])
    center = 0.5 * (a_vec + b_vec)
    best, best_d = None, None
    for tri in triplets:
        mid = get_hollow_site_position(atoms, tri)
        d = np.linalg.norm(mid[:2] - center[:2])
        if best_d is None or d < best_d:
            best_d = d
            best = tri
    return best


def choose_central_triplet_containing_cu(
    atoms: Atoms, triplets: List[Tuple[int, int, int]]
) -> Tuple[int, int, int]:
    """
    Among all triplets, prefer those containing at least one Cu atom.
    Among those, pick the most central one.
    """
    if not triplets:
        raise RuntimeError("No candidate triplets provided.")

    symbols = atoms.get_chemical_symbols()
    cu_triplets = [
        tri for tri in triplets
        if any(symbols[idx] == "Cu" for idx in tri)
    ]
    pool = cu_triplets if cu_triplets else triplets

    a_vec = np.array(atoms.cell[0])
    b_vec = np.array(atoms.cell[1])
    center = 0.5 * (a_vec + b_vec)
    best, best_d = None, None
    for tri in pool:
        mid = get_hollow_site_position(atoms, tri)
        d = np.linalg.norm(mid[:2] - center[:2])
        if best_d is None or d < best_d:
            best_d = d
            best = tri
    return best


# =========================
# Adsorbate geometry
# =========================

def build_adsorbate_fragment(
    species: str, cfg_ads: Dict
) -> Tuple[Atoms, str]:
    """
    Build adsorbate fragment in local coordinates.
    C anchor at origin. Surface bond assumed along -z.

    Returns (fragment, anchor_mode):
      'single', 'pair_midpoint', 'two_single_CO'
    """
    d_co = cfg_ads["bond_CO"]
    d_cc = cfg_ads["bond_CC"]
    d_ch = cfg_ads["bond_CH"]
    d_oh = cfg_ads["bond_OH"]

    theta_tet = math.radians(180.0 - cfg_ads["angle_tetra"])
    cos_tet = math.cos(theta_tet)
    sin_tet = math.sin(theta_tet)
    dphi_tet = math.radians(120.0)

    theta_trig = math.radians(180.0 - cfg_ads["angle_trig"])
    cos_trig = math.cos(theta_trig)
    sin_trig = math.sin(theta_trig)

    if species == "CO":
        frag = Atoms(
            symbols=["C", "O"],
            positions=[[0.0, 0.0, 0.0], [0.0, 0.0, d_co]],
        )
        return frag, "single"

    if species == "CH":
        frag = Atoms(
            symbols=["C", "H"],
            positions=[[0.0, 0.0, 0.0], [0.0, 0.0, d_ch]],
        )
        return frag, "single"

    if species == "CH2":
        hz = d_ch * cos_trig
        hr = d_ch * sin_trig
        frag = Atoms(
            symbols=["C", "H", "H"],
            positions=[
                [0.0, 0.0, 0.0],
                [hr, 0.0, hz],
                [-hr, 0.0, hz],
            ],
        )
        return frag, "single"

    if species == "CHO":
        o_x = d_co * sin_tet * math.cos(0.0)
        o_y = d_co * sin_tet * math.sin(0.0)
        o_z = d_co * cos_tet
        h_x = d_ch * sin_tet * math.cos(dphi_tet)
        h_y = d_ch * sin_tet * math.sin(dphi_tet)
        h_z = d_ch * cos_tet

        frag = Atoms(
            symbols=["C", "O", "H"],
            positions=[
                [0.0, 0.0, 0.0],
                [o_x, o_y, o_z],
                [h_x, h_y, h_z],
            ],
        )

        v_co = np.array([o_x, o_y, o_z])
        v_ch = np.array([h_x, h_y, h_z])
        cos_hco = np.dot(v_co, v_ch) / (
            np.linalg.norm(v_co) * np.linalg.norm(v_ch))
        angle_hco = math.degrees(math.acos(np.clip(cos_hco, -1, 1)))

        return frag, "single"

    if species == "CHOH":
        o_x = d_co * sin_tet * math.cos(0.0)
        o_y = d_co * sin_tet * math.sin(0.0)
        o_z = d_co * cos_tet
        hc_x = d_ch * sin_tet * math.cos(dphi_tet)
        hc_y = d_ch * sin_tet * math.sin(dphi_tet)
        hc_z = d_ch * cos_tet

        co_vec = np.array([o_x, o_y, o_z])
        co_hat = co_vec / np.linalg.norm(co_vec)

        if abs(co_hat[2]) < 0.9:
            up = np.array([0.0, 0.0, 1.0])
        else:
            up = np.array([1.0, 0.0, 0.0])
        perp = up - np.dot(up, co_hat) * co_hat
        perp = perp / np.linalg.norm(perp)

        oh_angle = math.radians(180.0 - 109.5)
        ho_vec = d_oh * (
            math.cos(oh_angle) * co_hat
            + math.sin(oh_angle) * perp
        )
        ho_pos = np.array([o_x, o_y, o_z]) + ho_vec

        frag = Atoms(
            symbols=["C", "O", "H", "H"],
            positions=[
                [0.0, 0.0, 0.0],
                [o_x, o_y, o_z],
                [hc_x, hc_y, hc_z],
                ho_pos.tolist(),
            ],
        )

        v_co = np.array([o_x, o_y, o_z])
        v_ch = np.array([hc_x, hc_y, hc_z])
        cos_hco = np.dot(v_co, v_ch) / (
            np.linalg.norm(v_co) * np.linalg.norm(v_ch))
        angle_hco = math.degrees(math.acos(np.clip(cos_hco, -1, 1)))

        return frag, "single"

    if species == "CH3":
        hz = d_ch * cos_tet
        hr = d_ch * sin_tet
        positions = [[0.0, 0.0, 0.0]]
        for k in range(3):
            phi = math.radians(k * 120.0)
            positions.append([
                hr * math.cos(phi),
                hr * math.sin(phi),
                hz
            ])
        frag = Atoms(symbols=["C", "H", "H", "H"], positions=positions)
        return frag, "single"

    if species == "CH4":
        cos_low = math.cos(math.radians(109.5))
        sin_low = math.sin(math.radians(109.5))
        positions = [[0.0, 0.0, 0.0]]
        positions.append([0.0, 0.0, d_ch])
        for k in range(3):
            phi = math.radians(k * 120.0)
            positions.append([
                d_ch * sin_low * math.cos(phi),
                d_ch * sin_low * math.sin(phi),
                d_ch * cos_low,
            ])
        frag = Atoms(
            symbols=["C", "H", "H", "H", "H"],
            positions=positions
        )
        return frag, "single"

    if species == "COCO":
        frag = Atoms(
            symbols=["C", "O", "C", "O"],
            positions=[
                [0.0, 0.0, 0.0],
                [0.0, 0.0, d_co],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, d_co],
            ],
        )
        return frag, "two_single_CO"

    if species == "OCCO":
        o_z = d_co * cos_tet
        o_r = d_co * sin_tet
        frag = Atoms(
            symbols=["O", "C", "C", "O"],
            positions=[
                [-0.5 * d_cc - o_r, 0.0, o_z],
                [-0.5 * d_cc,       0.0, 0.0],
                [ 0.5 * d_cc,       0.0, 0.0],
                [ 0.5 * d_cc + o_r, 0.0, o_z],
            ],
        )
        return frag, "pair_midpoint"

    raise ValueError(f"Unsupported species: {species}")


# =========================
# Site resolution
# =========================

def resolve_adsorbate_defaults(
    species: str, structure_kind: str, cfg_ads: Dict
) -> Dict[str, str]:
    placement = cfg_ads["placement_override"]
    site_mode = cfg_ads["site_mode_override"]

    if placement is None:
        placement = (
            cfg_ads["placement_default_pure"]
            if structure_kind == "pure"
            else cfg_ads["placement_default_interface"]
        )

    if site_mode is None or site_mode == "site_auto":
        if species in ("CO", "CH", "CH2"):
            site_mode = "hollow"
        elif species == "CHO":
            site_mode = "bridge"
        elif species in ("CHOH", "CH3", "CH4"):
            site_mode = "top"
        elif species in ("COCO", "OCCO"):
            if structure_kind == "pure":
                site_mode = "pair_cu_cu"
            else:
                site_mode = "pair_interface_cu_cu"
        else:
            site_mode = "top"

    return {
        "species": species,
        "placement": placement,
        "site_mode": site_mode,
    }


# =========================
# Placement functions
# =========================

def place_single_site_adsorbate(
    atoms: Atoms, species: str, site_pos: np.ndarray,
    site_mode: str, cfg_ads: Dict
) -> Atoms:
    new_atoms = atoms.copy()
    frag, anchor_mode = build_adsorbate_fragment(species, cfg_ads)
    assert anchor_mode == "single"

    if site_mode == "top":
        zoff = cfg_ads["z_anchor_top"]
    elif site_mode == "bridge":
        zoff = cfg_ads["z_anchor_bridge"]
    elif site_mode == "hollow":
        zoff = cfg_ads["z_anchor_hollow"]
    else:
        zoff = cfg_ads["z_anchor_top"]

    frag.positions += np.array([
        site_pos[0], site_pos[1], site_pos[2] + zoff
    ])
    new_atoms += frag
    return new_atoms


def place_pair_adsorbate(
    atoms: Atoms, species: str, pair: Tuple[int, int], cfg_ads: Dict
) -> Atoms:
    new_atoms = atoms.copy()
    frag, anchor_mode = build_adsorbate_fragment(species, cfg_ads)
    assert anchor_mode == "pair_midpoint"

    i, j = pair
    pi = new_atoms.positions[i]
    mv = mic_vector(new_atoms, i, j)
    midpoint = pi + 0.5 * mv

    pair_vec = mv.copy()
    pair_vec[2] = 0.0
    if np.linalg.norm(pair_vec[:2]) < 1e-12:
        pair_vec = np.array([1.0, 0.0, 0.0])

    R = rotation_matrix_from_x_to_vec(pair_vec)
    frag_pos = frag.positions.copy() @ R.T
    frag_pos[:, 0] += midpoint[0]
    frag_pos[:, 1] += midpoint[1]
    frag_pos[:, 2] += midpoint[2] + cfg_ads["z_anchor_bridge"]

    frag.set_positions(frag_pos)
    new_atoms += frag
    return new_atoms


def place_coco_on_two_hollow_sites(
    atoms: Atoms, candidates: List[int], cfg_ads: Dict,
    max_edge: float = 3.2
) -> Tuple[Atoms, Dict]:
    """
    Place two CO molecules on two adjacent hollow sites.
    """
    d_co = cfg_ads["bond_CO"]
    zoff = cfg_ads["z_anchor_hollow"]

    triplets = find_hollow_triplets_delaunay(
        atoms, candidates, max_edge=max_edge)
    if len(triplets) < 2:
        raise RuntimeError(
            "Need at least 2 hollow triplets for COCO placement.")

    a_vec = np.array(atoms.cell[0])
    b_vec = np.array(atoms.cell[1])
    center = 0.5 * (a_vec + b_vec)

    best_pair = None
    best_d = None
    for ia in range(len(triplets)):
        for ib in range(ia + 1, len(triplets)):
            sa = set(triplets[ia])
            sb = set(triplets[ib])
            if len(sa & sb) == 2:
                pos_a = get_hollow_site_position(atoms, triplets[ia])
                pos_b = get_hollow_site_position(atoms, triplets[ib])
                mid = 0.5 * (pos_a + pos_b)
                d = np.linalg.norm(mid[:2] - center[:2])
                if best_d is None or d < best_d:
                    best_d = d
                    best_pair = (triplets[ia], triplets[ib])

    if best_pair is None:
        scored = []
        for tri in triplets:
            pos = get_hollow_site_position(atoms, tri)
            d = np.linalg.norm(pos[:2] - center[:2])
            scored.append((d, tri))
        scored.sort(key=lambda x: x[0])
        best_pair = (scored[0][1], scored[1][1])

    pos_a = get_hollow_site_position(atoms, best_pair[0])
    pos_b = get_hollow_site_position(atoms, best_pair[1])

    new_atoms = atoms.copy()
    co1 = Atoms(
        symbols=["C", "O"],
        positions=[
            [pos_a[0], pos_a[1], pos_a[2] + zoff],
            [pos_a[0], pos_a[1], pos_a[2] + zoff + d_co],
        ],
    )
    co2 = Atoms(
        symbols=["C", "O"],
        positions=[
            [pos_b[0], pos_b[1], pos_b[2] + zoff],
            [pos_b[0], pos_b[1], pos_b[2] + zoff + d_co],
        ],
    )
    new_atoms += co1
    new_atoms += co2

    meta = {
        "triplet_a": [int(x) for x in best_pair[0]],
        "triplet_b": [int(x) for x in best_pair[1]],
        "hollow_pos_a": pos_a.tolist(),
        "hollow_pos_b": pos_b.tolist(),
    }
    return new_atoms, meta


# =========================
# Main adsorbate dispatcher
# =========================

def _get_hollow_candidates(
    atoms: Atoms, placement: str, nc: float
) -> List[int]:
    """
    Get candidate atom indices for hollow-site triangulation.
    For interface placement, use ALL top-layer atoms in the interface
    region (Cu + Ag/Au neighbors) so that triangles can form across
    the boundary.  For terrace, use terrace Cu.
    """
    if placement == "interface":
        cand = get_interface_region_indices(atoms, neighbor_cutoff=nc)
        if len(cand) >= 3:
            return cand
        # Fallback: all top-layer atoms
        return get_top_layer_indices(atoms)
    else:
        cand = get_terrace_cu_indices(atoms, neighbor_cutoff=nc)
        if len(cand) >= 3:
            return cand
        return get_top_cu_indices(atoms)


def add_adsorbate_with_defaults(
    atoms: Atoms, species: str, structure_kind: str, cfg: Dict
) -> Tuple[Atoms, Dict]:
    cfg_ads = cfg["adsorbates"]
    nc = cfg_ads["neighbor_cutoff"]

    resolved = resolve_adsorbate_defaults(species, structure_kind, cfg_ads)
    placement = resolved["placement"]
    site_mode = resolved["site_mode"]

    # Cu candidates for atop / bridge
    if placement == "terrace":
        cu_cand = get_terrace_cu_indices(atoms, neighbor_cutoff=nc)
    elif placement == "interface":
        cu_cand = get_interface_cu_indices(atoms, neighbor_cutoff=nc)
    else:
        raise ValueError(f"Unsupported placement: {placement}")

    # Fallback if no Cu candidates found
    if not cu_cand:
        print(f"  WARNING: No {placement} Cu found, falling back to "
              f"all top-layer Cu.")
        cu_cand = get_top_cu_indices(atoms)

    ac = adaptive_cutoff(atoms, cu_cand)
    pair_cand = get_neighbor_pairs(atoms, cu_cand, max_dist=ac)

    # --- top ---
    if site_mode == "top":
        chosen = choose_central_index(atoms, cu_cand)
        site_pos = atoms.positions[chosen]
        new_atoms = place_single_site_adsorbate(
            atoms, species, site_pos, "top", cfg_ads)
        meta = {
            "species": species, "placement": placement,
            "site_mode": site_mode,
            "chosen_index": int(chosen),
            "chosen_position": site_pos.tolist(),
        }
        return new_atoms, meta

    # --- bridge ---
    if site_mode == "bridge":
        if not pair_cand:
            raise RuntimeError(
                f"No bridge pairs found for {species} on {placement}.")
        chosen_pair = choose_central_pair(atoms, pair_cand)
        pi = atoms.positions[chosen_pair[0]]
        mv = mic_vector(atoms, chosen_pair[0], chosen_pair[1])
        site_pos = pi + 0.5 * mv
        new_atoms = place_single_site_adsorbate(
            atoms, species, site_pos, "bridge", cfg_ads)
        meta = {
            "species": species, "placement": placement,
            "site_mode": site_mode,
            "chosen_pair": [int(chosen_pair[0]), int(chosen_pair[1])],
            "chosen_position": site_pos.tolist(),
        }
        return new_atoms, meta

    # --- hollow ---
    if site_mode == "hollow":
        # Use expanded candidate set for triangulation
        hollow_cand = _get_hollow_candidates(atoms, placement, nc)
        triplets = find_hollow_triplets_delaunay(
            atoms, hollow_cand, max_edge=nc)
        if not triplets:
            raise RuntimeError(
                f"No hollow triplets found for {species} on {placement} "
                f"with {len(hollow_cand)} candidate atoms.")
        chosen_tri = choose_central_triplet_containing_cu(atoms, triplets)
        site_pos = get_hollow_site_position(atoms, chosen_tri)
        new_atoms = place_single_site_adsorbate(
            atoms, species, site_pos, "hollow", cfg_ads)
        meta = {
            "species": species, "placement": placement,
            "site_mode": site_mode,
            "chosen_triplet": [int(x) for x in chosen_tri],
            "chosen_position": site_pos.tolist(),
        }
        return new_atoms, meta

    # --- pair modes ---
    if site_mode == "pair_cu_cu":
        cu_for_coco = get_terrace_cu_indices(atoms, neighbor_cutoff=nc)
        ac2 = adaptive_cutoff(atoms, cu_for_coco)
        pairs = get_neighbor_pairs(atoms, cu_for_coco, max_dist=ac2)
    elif site_mode == "pair_interface_cu_cu":
        cu_for_coco = get_interface_cu_indices(atoms, neighbor_cutoff=nc)
        if not cu_for_coco:
            cu_for_coco = get_top_cu_indices(atoms)
        ac2 = adaptive_cutoff(atoms, cu_for_coco)
        pairs = get_neighbor_pairs(atoms, cu_for_coco, max_dist=ac2)
    elif site_mode == "pair_interface_cross":
        pairs = get_cross_boundary_pairs(atoms, neighbor_cutoff=nc)
        cu_for_coco = get_top_cu_indices(atoms)
    else:
        raise ValueError(f"Unsupported site_mode: {site_mode}")

    if not pairs:
        print(f"  WARNING: No pairs found for {site_mode}, "
              f"falling back to all top Cu pairs.")
        cu_for_coco = get_top_cu_indices(atoms)
        ac2 = adaptive_cutoff(atoms, cu_for_coco)
        pairs = get_neighbor_pairs(atoms, cu_for_coco, max_dist=ac2)

    if species == "COCO":
        # Use expanded candidates for hollow triangulation
        hollow_cand = _get_hollow_candidates(atoms, placement, nc)
        new_atoms, coco_meta = place_coco_on_two_hollow_sites(
            atoms, hollow_cand, cfg_ads, max_edge=nc)
        meta = {
            "species": species, "placement": placement,
            "site_mode": site_mode,
            **coco_meta,
        }
        return new_atoms, meta

    chosen = choose_central_pair(atoms, pairs)
    new_atoms = place_pair_adsorbate(atoms, species, chosen, cfg_ads)
    meta = {
        "species": species, "placement": placement,
        "site_mode": site_mode,
        "chosen_pair": [int(chosen[0]), int(chosen[1])],
    }
    return new_atoms, meta


# =========================
# VASP writers
# =========================

def write_incar(
    path: Path, system_name: str, cfg: Dict,
    mode: Optional[str] = None
):
    """Write INCAR file. mode: 'relax', 'static', or 'cp'."""
    if mode is None:
        mode = cfg["vasp"]["incar_mode"]

    params = dict(cfg["vasp"]["standard"])

    if mode == "static":
        params.update(cfg["vasp"]["static_overrides"])
        params.pop("EDIFFG", None)

    suffix = {"relax": "_relax", "static": "_static", "cp": "_cp"}
    full_name = f"{system_name}{suffix.get(mode, '')}"

    lines = [f"SYSTEM = {full_name}"]

    order = [
        "ISPIN", "PREC", "ENCUT", "EDIFF", "EDIFFG", "NELM", "ALGO",
        "GGA", "IVDW", "LASPH",
        "IBRION", "NSW", "ISIF",
        "ISMEAR", "SIGMA",
        "LREAL", "ISYM", "ICHARG", "LMAXMIX",
        "LWAVE", "LCHARG",
        "LDIPOL", "IDIPOL",
    ]

    for key in order:
        if key in params:
            lines.append(f"{key} = {params[key]}")

    if mode == "cp":
        cp = cfg["vasp"]["cp_extras"]
        lines.append("")
        lines.append(f"LSOL = {cp['LSOL']}")
        lines.append(f"EB_K = {cp['EB_K']}")
        lines.append("")
        lines.append(f"LCEP = {cp['LCEP']}")
        lines.append(f"NESCHEME = {cp['NESCHEME']}")
        lines.append(f"FERMICONVERGE = {cp['FERMICONVERGE']}")
        if cp["TARGETMU"] is not None:
            lines.append(f"TARGETMU = {cp['TARGETMU']}")
        else:
            lines.append("# TARGETMU = <set_this>")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_kpoints(path: Path, mesh=(1, 1, 1)):
    with open(path, "w") as f:
        f.write("Automatic mesh\n0\nMonkhorst-Pack\n")
        f.write(f"{mesh[0]} {mesh[1]} {mesh[2]}\n0 0 0\n")


def write_potcar_placeholder(path: Path):
    with open(path, "w") as f:
        f.write(
            "POTCAR not written by this script.\n"
            "Create POTCAR manually from your licensed VASP PAW datasets.\n"
            "Species order must match POSCAR.\n"
        )


def write_nersc_job_script(path: Path, job_name: str, cfg: Dict):
    n = cfg["nersc"]
    script = f"""#!/bin/bash
#SBATCH -A {n['account']}
#SBATCH -q regular
#SBATCH -J {job_name}
#SBATCH -t {n['walltime']}
#SBATCH -N {n['nodes']}
#SBATCH -C {n['constraint']}
#SBATCH --mail-type={n['mail_type']}
#SBATCH --mail-user={n['mail_user']}

module load {n['module']}

export OMP_NUM_THREADS={n['omp_num_threads']}
export OMP_PLACES={n['omp_places']}
export OMP_PROC_BIND={n['omp_proc_bind']}

{n['srun_cmd']}
"""
    with open(path, "w") as f:
        f.write(script)


def export_case_inputs(
    case_dir: Path, system_name: str,
    kmesh: Tuple[int, int, int], cfg: Dict
):
    write_incar(case_dir / "INCAR", system_name, cfg)
    write_kpoints(case_dir / "KPOINTS", kmesh)
    if cfg["output"]["write_potcar_placeholder"]:
        write_potcar_placeholder(case_dir / "POTCAR")
    write_nersc_job_script(case_dir / "submit.sh", system_name, cfg)


# =========================
# Visualization
# =========================

def visualize_structure(
    surface_name: str,
    adsorbate_name: Optional[str] = None,
    cfg: Optional[Dict] = None,
):
    """
    Build and visualize a slab (optionally with an adsorbate) using
    ASE's built-in GUI viewer.

    Parameters
    ----------
    surface_name : str
        One of 'Cu111', 'CuAg_interface', 'CuAu_interface'.
    adsorbate_name : str or None
        One of the species in the config species_list, e.g. 'CO', 'CHO',
        or None for the clean slab.
    cfg : dict or None
        Configuration dictionary.  Uses the global CONFIG if None.

    Examples
    --------
        python workflow.py view Cu111 CO
        python workflow.py view CuAu_interface CHOH
        python workflow.py view CuAg_interface
    """
    from ase.visualize import view

    if cfg is None:
        cfg = CONFIG
    validate_config(cfg)

    if surface_name == "Cu111":
        atoms = build_pure_cu111_slab(cfg)
        structure_kind = "pure"
    elif surface_name == "CuAg_interface":
        if cfg["interface"]["match_mode"] == "strained_cu":
            atoms, _ = build_strained_interface_111(
                "Cu", "Ag",
                cfg["bulk"]["a_cu"], cfg["bulk"]["a_ag"], cfg)
        else:
            atoms, _ = build_1d_commensurate_interface_111(
                "Cu", "Ag",
                cfg["bulk"]["a_cu"], cfg["bulk"]["a_ag"],
                cfg["interface"]["commensurate_pair_cu_ag"], cfg)
        structure_kind = "interface"
    elif surface_name == "CuAu_interface":
        if cfg["interface"]["match_mode"] == "strained_cu":
            atoms, _ = build_strained_interface_111(
                "Cu", "Au",
                cfg["bulk"]["a_cu"], cfg["bulk"]["a_au"], cfg)
        else:
            atoms, _ = build_1d_commensurate_interface_111(
                "Cu", "Au",
                cfg["bulk"]["a_cu"], cfg["bulk"]["a_au"],
                cfg["interface"]["commensurate_pair_cu_au"], cfg)
        structure_kind = "interface"
    else:
        raise ValueError(
            f"Unknown surface '{surface_name}'.  "
            f"Choose from: Cu111, CuAg_interface, CuAu_interface")

    title = surface_name
    if adsorbate_name is not None:
        valid = cfg["adsorbates"]["species_list"]
        if adsorbate_name not in valid:
            raise ValueError(
                f"Unknown adsorbate '{adsorbate_name}'.  "
                f"Choose from: {valid}")
        atoms, meta = add_adsorbate_with_defaults(
            atoms, adsorbate_name, structure_kind, cfg)
        title = f"{surface_name} + {adsorbate_name}"
        print(f"Adsorbate metadata: {json.dumps(meta, indent=2)}")

    print(f"Visualizing: {title}  ({len(atoms)} atoms)")
    view(atoms, title=title)


# =========================
# Main workflow
# =========================

def run_workflow(cfg: Dict):
    validate_config(cfg)

    outdir = Path(cfg["output"]["root_dir"])
    ensure_dir(outdir)

    report_basic_mismatch(cfg["bulk"]["a_cu"], cfg["bulk"]["a_ag"], "Cu-Ag")
    report_basic_mismatch(cfg["bulk"]["a_cu"], cfg["bulk"]["a_au"], "Cu-Au")

    cu_slab = build_pure_cu111_slab(cfg)
    write_poscar(outdir / "POSCAR_Cu111_clean", cu_slab)

    if cfg["interface"]["match_mode"] == "strained_cu":
        cu_ag, cu_ag_meta = build_strained_interface_111(
            "Cu", "Ag", cfg["bulk"]["a_cu"], cfg["bulk"]["a_ag"], cfg)
        cu_au, cu_au_meta = build_strained_interface_111(
            "Cu", "Au", cfg["bulk"]["a_cu"], cfg["bulk"]["a_au"], cfg)
    else:
        cu_ag, cu_ag_meta = build_1d_commensurate_interface_111(
            "Cu", "Ag", cfg["bulk"]["a_cu"], cfg["bulk"]["a_ag"],
            cfg["interface"]["commensurate_pair_cu_ag"], cfg)
        cu_au, cu_au_meta = build_1d_commensurate_interface_111(
            "Cu", "Au", cfg["bulk"]["a_cu"], cfg["bulk"]["a_au"],
            cfg["interface"]["commensurate_pair_cu_au"], cfg)

    write_poscar(outdir / "POSCAR_CuAg_interface_clean", cu_ag)
    write_poscar(outdir / "POSCAR_CuAu_interface_clean", cu_au)

    if cfg["output"]["write_metadata_json"]:
        for name, meta in [("CuAg", cu_ag_meta), ("CuAu", cu_au_meta)]:
            with open(outdir / f"{name}_interface_clean_metadata.json",
                      "w") as f:
                json.dump(meta, f, indent=2)

    generated_cases = []

    structures = [
        ("Cu111", cu_slab, "pure",
         cfg["vasp"]["kpoints"]["Cu111"]),
        ("CuAg_interface", cu_ag, "interface",
         cfg["vasp"]["kpoints"]["interface"]),
        ("CuAu_interface", cu_au, "interface",
         cfg["vasp"]["kpoints"]["interface"]),
    ]

    if cfg["adsorbates"]["enabled"]:
        for struct_name, atoms_obj, structure_kind, kmesh in structures:
            for species in cfg["adsorbates"]["species_list"]:
                try:
                    ads_atoms, ads_meta = add_adsorbate_with_defaults(
                        atoms_obj, species, structure_kind, cfg)

                    system_name = f"{struct_name}_{species}"
                    case_dir = outdir / system_name
                    ensure_dir(case_dir)

                    write_poscar(case_dir / "POSCAR", ads_atoms)

                    meta = {
                        "system_name": system_name,
                        "structure_name": struct_name,
                        "structure_kind": structure_kind,
                        "kmesh": list(kmesh),
                        **ads_meta,
                    }

                    if cfg["output"]["write_metadata_json"]:
                        with open(case_dir / "metadata.json", "w") as f:
                            json.dump(meta, f, indent=2)

                    export_case_inputs(
                        case_dir, system_name, kmesh, cfg)

                    generated_cases.append((system_name, case_dir))
                    print(f"WROTE: {system_name}")

                except Exception as e:
                    print(
                        f"FAILED: {struct_name} {species} -> {repr(e)}")

    print(f"\nGenerated {len(generated_cases)} adsorbate cases.")
    return generated_cases


if __name__ == "__main__":
    import sys

    # ---- Interactive visualization mode ----
    # Usage:  python workflow.py view <surface> [adsorbate]
    #   e.g.  python workflow.py view Cu111 CO
    #         python workflow.py view CuAu_interface CHOH
    #         python workflow.py view CuAg_interface
    if len(sys.argv) >= 3 and sys.argv[1] == "view":
        surface = sys.argv[2]
        adsorbate = sys.argv[3] if len(sys.argv) >= 4 else None
        visualize_structure(surface, adsorbate)
        sys.exit(0)

    # ---- Default: run full workflow ----
    run_workflow(CONFIG)