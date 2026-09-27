import math
import os

import openmc
import openmc.deplete


# Use the local OpenMC nuclear-data library unless the environment overrides it.
cross_sections = os.environ.get(
    "OPENMC_CROSS_SECTIONS",
    "/home/asus/nuclear_data/endfb-vii.1-hdf5/cross_sections.xml",
)
if not os.path.isfile(cross_sections):
    raise FileNotFoundError(
        f"OpenMC cross-section library not found: {cross_sections}"
    )
os.environ["OPENMC_CROSS_SECTIONS"] = cross_sections

# Depletion chain file - download one matching your cross-section library,
# e.g. chain_endfb71_pwr.xml, and point this at it (or set the
# OPENMC_CHAIN_FILE environment variable instead of hardcoding a path).
chain_file = os.environ.get(
    "OPENMC_CHAIN_FILE",
    "/home/asus/nuclear_data/chain_casl_pwr.xml",
)
if not os.path.isfile(chain_file):
    raise FileNotFoundError(
        f"Depletion chain file not found: {chain_file}\n"
        "Download one matching your cross-section library, e.g. from "
        "https://openmc.org/depletion-chains/ (chain_endfb71_pwr.xml is a "
        "common choice for ENDF/B-VII.1/VIII.0 libraries)."
    )

# =====================================================================
# 1. MATERIALS
# =====================================================================

def make_fuel(enrichment):
    fuel = openmc.Material(name=f"UO2 fuel {enrichment:.1f}% U235")
    fuel.add_element("U", 1.0, enrichment=enrichment)
    fuel.add_nuclide("O16", 2.0)
    fuel.set_density("g/cm3", 10.4)
    fuel.depletable = True  # mark as depletable up front
    return fuel


fuel16 = make_fuel(1.6)
fuel24 = make_fuel(2.4)
fuel31 = make_fuel(3.1)

pyrex = openmc.Material(name="Pyrex burnable absorber")
pyrex.add_element("B", 0.13, "wo")
pyrex.add_element("Si", 0.37, "wo")
pyrex.add_nuclide("O16", 0.50, "wo")
pyrex.set_density("g/cm3", 2.23)
pyrex.depletable = True  # Pyrex burns out (B-10 depletes) too - worth tracking

helium = openmc.Material(name="Helium gap")
helium.add_element("He", 1.0)
helium.set_density("g/cm3", 0.0015)

zircaloy = openmc.Material(name="Zircaloy-4")
zircaloy.add_element("Zr", 0.98, "wo")
zircaloy.add_element("Sn", 0.015, "wo")
zircaloy.add_element("Fe", 0.002, "wo")
zircaloy.add_element("Cr", 0.001, "wo")
zircaloy.add_nuclide("O16", 0.00125, "wo")
zircaloy.set_density("g/cm3", 6.55)

water = openmc.Material(name="Borated water")
water.add_element("H", 0.111894, "wo")
water.add_nuclide("O16", 0.888106, "wo")
water.add_element("B", 900e-6, "wo")
water.set_density("g/cm3", 0.72)
water.add_s_alpha_beta("c_H_in_H2O")

stainless_steel = openmc.Material(name='Stainless Steel 316')
stainless_steel.add_element('Si', 0.0075)
stainless_steel.add_element('Mn', 0.02)
stainless_steel.add_element('P',  0.00045)
stainless_steel.add_element('S',  0.0003)
stainless_steel.add_element('Cr', 0.17)
stainless_steel.add_element('Ni', 0.12)
stainless_steel.add_element('Mo', 0.025)
stainless_steel.add_element('Fe', 0.65675)

# --- Spacer grid materials -------------------------------------------------
inconel718 = openmc.Material(name="Inconel-718 spacer grid")
inconel718.add_element("Ni", 0.525, "wo")
inconel718.add_element("Cr", 0.19, "wo")
inconel718.add_element("Fe", 0.185, "wo")
inconel718.add_element("Nb", 0.051, "wo")
inconel718.add_element("Mo", 0.03, "wo")
inconel718.add_element("Ti", 0.009, "wo")
inconel718.add_element("Al", 0.005, "wo")
inconel718.set_density("g/cm3", 8.19)

GRID_METAL_VOL_FRAC = 0.06

water_for_mixing = openmc.Material(name="Borated water (no S(a,b), mixing helper)")
water_for_mixing.add_element("H", 0.111894, "wo")
water_for_mixing.add_nuclide("O16", 0.888106, "wo")
water_for_mixing.add_element("B", 900e-6, "wo")
water_for_mixing.set_density("g/cm3", 0.72)

grid_mix_zirc = openmc.Material.mix_materials(
    [water_for_mixing, zircaloy],
    [1 - GRID_METAL_VOL_FRAC, GRID_METAL_VOL_FRAC],
    "vo",
    name="Mid-span grid smeared coolant",
)
grid_mix_zirc.add_s_alpha_beta("c_H_in_H2O")

grid_mix_inconel = openmc.Material.mix_materials(
    [water_for_mixing, inconel718],
    [1 - GRID_METAL_VOL_FRAC, GRID_METAL_VOL_FRAC],
    "vo",
    name="End grid smeared coolant",
)
grid_mix_inconel.add_s_alpha_beta("c_H_in_H2O")

materials = openmc.Materials(
    [
        fuel16, fuel24, fuel31, pyrex, helium, zircaloy, water, stainless_steel,
        inconel718, grid_mix_zirc, grid_mix_inconel,
    ]
)
materials.cross_sections = cross_sections

# =====================================================================
# 2. GEOMETRY - pin cell dimensions (17x17, ~0.950 cm pitch)
# =====================================================================

pin_pitch = 1.26
assembly_size = 17 * pin_pitch
stainless_thickness = 5.0
perimeter_thickness = 2.5
assembly_pitch = assembly_size

r_fuel = 0.4096
r_gap = 0.4180
r_clad_out = 0.4750
r_gt_in = 0.5610
r_gt_out = 0.6020
r_steel_out = 190
r_steel_in = r_steel_out - stainless_thickness

fuel_or = openmc.ZCylinder(r=r_fuel)
clad_ir = openmc.ZCylinder(r=r_gap)
clad_or = openmc.ZCylinder(r=r_clad_out)
ba_or = openmc.ZCylinder(r=0.45)
gt_ir = openmc.ZCylinder(r=r_gt_in)
gt_or = openmc.ZCylinder(r=r_gt_out)
steel_or = openmc.ZCylinder(r=r_steel_out)
steel_ir = openmc.ZCylinder(r=r_steel_in)


def make_fuel_pin(fuel, moderator):
    fuel_cell = openmc.Cell(name=f"fuel_{fuel.name}", fill=fuel, region=-fuel_or)
    gap_cell = openmc.Cell(name="gap", fill=helium, region=+fuel_or & -clad_ir)
    clad_cell = openmc.Cell(name="clad", fill=zircaloy, region=+clad_ir & -clad_or)
    mod_cell = openmc.Cell(name="pin_water", fill=moderator, region=+clad_or)
    return openmc.Universe(
        name=f"fuel_pin_{fuel.name}_{moderator.name}",
        cells=[fuel_cell, gap_cell, clad_cell, mod_cell],
    )


def make_guide_tube(moderator):
    # Only the coolant-facing outer region is affected by a spacer grid -
    # the stagnant water inside the guide tube is is untouched.
    gt_water_in = openmc.Cell(name="gt_water_in", fill=water, region=-gt_ir)
    gt_wall = openmc.Cell(name="gt_wall", fill=zircaloy, region=+gt_ir & -gt_or)
    gt_water_out = openmc.Cell(name="gt_water_out", fill=moderator, region=+gt_or)
    return openmc.Universe(
        name=f"guide_tube_{moderator.name}",
        cells=[gt_water_in, gt_wall, gt_water_out],
    )


def make_ba_rod(moderator):
    ba_glass = openmc.Cell(name="ba_glass", fill=pyrex, region=-ba_or)
    ba_water_out = openmc.Cell(name="ba_water_out", fill=water, region=+ba_or & -gt_ir)
    ba_wall = openmc.Cell(name="ba_wall", fill=zircaloy, region=+gt_ir & -gt_or)
    ba_water_outside = openmc.Cell(name="ba_water_outside", fill=moderator, region=+gt_or)
    return openmc.Universe(
        name=f"pyrex_ba_rod_{moderator.name}",
        cells=[ba_glass, ba_water_out, ba_wall, ba_water_outside],
    )


MODERATORS = {
    "normal": water,
    "grid_zirc": grid_mix_zirc,
    "grid_inconel": grid_mix_inconel,
}

fuel_pins = {}
guide_tubes = {}
ba_rods = {}
for mod_key, moderator in MODERATORS.items():
    fuel_pins[mod_key] = {
        "1.6": make_fuel_pin(fuel16, moderator),
        "2.4": make_fuel_pin(fuel24, moderator),
        "3.1": make_fuel_pin(fuel31, moderator),
    }
    guide_tubes[mod_key] = make_guide_tube(moderator)
    ba_rods[mod_key] = make_ba_rod(moderator)


instr_tubes = guide_tubes

steel_cell = openmc.Cell(name="steel", fill=stainless_steel, region=+steel_ir & -steel_or)
steel_Universe = openmc.Universe(name="steel", cells=[steel_cell])

# =====================================================================
# 3. 17x17 LATTICE
# =====================================================================

fuel16_gt_positions = [
    (2, 5), (2, 8), (2, 11),
    (3, 3), (3, 13),
    (5, 2), (5, 5), (5, 8), (5, 11), (5, 14),
    (8, 2), (8, 5), (8, 8), (8, 11), (8, 14),
    (11, 2), (11, 5), (11, 8), (11, 11), (11, 14),
    (13, 3), (13, 13),
    (14, 5), (14, 8), (14, 11),
]

other_gt_positions = [
    (2, 8),
    (5, 5), (5, 8), (5, 11),
    (8, 2), (8, 5), (8, 8), (8, 11), (8, 14),
    (11, 5), (11, 8), (11, 11),
    (14, 8),
]

ba_positions = set(fuel16_gt_positions) - set(other_gt_positions)


def make_assembly_universe(assembly_type, mod_key):
    if assembly_type not in ("1.6", "2.4", "3.1"):
        raise ValueError(f"Unknown assembly type: {assembly_type}")

    fuel_pin = fuel_pins[mod_key][assembly_type]
    guide_tube_universe = guide_tubes[mod_key]
    ba_rod_universe = ba_rods[mod_key]
    instr_tube_universe = instr_tubes[mod_key]

    guide_tube_positions = (
        fuel16_gt_positions if assembly_type == "1.6" else other_gt_positions
    )
    assembly_lattice = openmc.RectLattice(
        name=f"17x17 {assembly_type}% assembly ({mod_key})"
    )
    assembly_lattice.lower_left = (-assembly_size / 2, -assembly_size / 2)
    assembly_lattice.pitch = (pin_pitch, pin_pitch)
    assembly_lattice.outer = fuel_pin
    assembly_universes = [[fuel_pin for _ in range(17)] for _ in range(17)]

    positions = guide_tube_positions
    if assembly_type != "1.6":
        positions = positions + list(ba_positions)
    for position in positions:
        assembly_universes[position[0]][position[1]] = (
            ba_rod_universe
            if assembly_type != "1.6" and position in ba_positions
            else guide_tube_universe
        )
    assembly_universes[8][8] = instr_tube_universe
    assembly_lattice.universes = assembly_universes
    assembly_cell = openmc.Cell(
        name=f"{assembly_type}% fuel assembly ({mod_key})", fill=assembly_lattice
    )
    return openmc.Universe(
        name=f"assembly_{assembly_type}_{mod_key}", cells=[assembly_cell]
    )



assemblies = {}
for mod_key in MODERATORS:
    assemblies[mod_key] = {
        "1.6": make_assembly_universe("1.6", mod_key),
        "2.4": make_assembly_universe("2.4", mod_key),
        "3.1": make_assembly_universe("3.1", mod_key),
    }

# =====================================================================
# 3b. 193-ASSEMBLY CORE LATTICE
# =====================================================================

core_water = openmc.Universe(
    name="core interstitial water",
    cells=[openmc.Cell(name="core interstitial water", fill=water)],
)


def core_assembly_type(row, col):
    if not 0 <= row < 17 or not 0 <= col < 17:
        return None
    distance2 = (row - 8) ** 2 + (col - 8) ** 2
    if distance2 > 61:
        return None
    if distance2 <= 21:
        return "1.6"
    if distance2 <= 45:
        return "2.4"
    return "3.1"


def build_core_lattice(assemblies_for_mod, name_suffix):
    """Build a full 193-assembly core lattice using one assembly variant set
    (normal in-span coolant, or one of the grid-band coolant mixtures)."""
    lattice = openmc.RectLattice(name=f"193 assembly core ({name_suffix})")
    lattice.lower_left = (-core_size / 2, -core_size / 2)
    lattice.pitch = (assembly_pitch, assembly_pitch)
    lattice.outer = core_water

    def core_assembly(row, col):
        assembly_type = core_assembly_type(row, col)
        if assembly_type is None:
            return core_water
        return assemblies_for_mod[assembly_type]

    lattice.universes = [
        [core_assembly(row, col) for col in range(17)] for row in range(17)
    ]
    return lattice


core_size = 17 * assembly_pitch

# One core lattice per axial band type: plain coolant between grids, and the
# two grid-band coolant mixtures at grid elevations.
core_lattice = build_core_lattice(assemblies["normal"], "normal")
core_lattice_grid_zirc = build_core_lattice(assemblies["grid_zirc"], "grid_zirc")
core_lattice_grid_inconel = build_core_lattice(assemblies["grid_inconel"], "grid_inconel")

half = core_size / 2
outer_half = half + perimeter_thickness
outer_radius = 210.0
outer_boundary = openmc.ZCylinder(
    r=outer_radius,
    boundary_type="vacuum",
)

active_fuel_height = 366.0
z_min = openmc.ZPlane(z0=-active_fuel_height / 2, boundary_type="vacuum")
z_max = openmc.ZPlane(z0=active_fuel_height / 2, boundary_type="vacuum")

core_region = -outer_boundary & -steel_ir
outer_x_min = openmc.XPlane(x0=-outer_half)
outer_x_max = openmc.XPlane(x0=outer_half)
outer_y_min = openmc.YPlane(y0=-outer_half)
outer_y_max = openmc.YPlane(y0=outer_half)

fuel_coordinates = {
    (row, col)
    for row in range(17)
    for col in range(17)
    if core_assembly_type(row, col) is not None
}
outer_31_coordinates = {
    (row, col)
    for row in range(17)
    for col in range(17)
    if core_assembly_type(row, col) == "3.1"
}

perimeter_regions = []
for row, col in outer_31_coordinates:
    x_min = -half + col * assembly_pitch
    x_max = x_min + assembly_pitch
    y_max = half - row * assembly_pitch
    y_min = y_max - assembly_pitch
    neighbors = {
        "left": (row, col - 1),
        "right": (row, col + 1),
        "bottom": (row + 1, col),
        "top": (row - 1, col),
    }
    for side, neighbor in neighbors.items():
        if neighbor in fuel_coordinates:
            continue
        if side == "left":
            perimeter_regions.append(
                +openmc.XPlane(x0=x_min - perimeter_thickness)
                & -openmc.XPlane(x0=x_min)
                & +openmc.YPlane(y0=y_min)
                & -openmc.YPlane(y0=y_max)
            )
        elif side == "right":
            perimeter_regions.append(
                +openmc.XPlane(x0=x_max)
                & -openmc.XPlane(x0=x_max + perimeter_thickness)
                & +openmc.YPlane(y0=y_min)
                & -openmc.YPlane(y0=y_max)
            )
        elif side == "bottom":
            perimeter_regions.append(
                +openmc.XPlane(x0=x_min)
                & -openmc.XPlane(x0=x_max)
                & +openmc.YPlane(y0=y_min - perimeter_thickness)
                & -openmc.YPlane(y0=y_min)
            )
        else:
            perimeter_regions.append(
                +openmc.XPlane(x0=x_min)
                & -openmc.XPlane(x0=x_max)
                & +openmc.YPlane(y0=y_max)
                & -openmc.YPlane(y0=y_max + perimeter_thickness)
            )

rectangular_perimeter_region = perimeter_regions[0]
for perimeter_region in perimeter_regions[1:]:
    rectangular_perimeter_region |= perimeter_region
circular_perimeter_region = +steel_ir & -steel_or
core_region = core_region & ~rectangular_perimeter_region
steel_region = -outer_boundary & (
    rectangular_perimeter_region | circular_perimeter_region
)
outer_water_region = -outer_boundary & +steel_or

# --- Axial stack of spacer grids ---------------
GRID_THICKNESS = 3.8       #cm
N_MID_GRIDS = 8

z0 = -active_fuel_height / 2
mid_spacing = active_fuel_height / (N_MID_GRIDS + 1)

grid_specs = [(z0 + GRID_THICKNESS / 2, core_lattice_grid_inconel)]  # bottom end grid
grid_specs += [
    (z0 + i * mid_spacing, core_lattice_grid_zirc) for i in range(1, N_MID_GRIDS + 1)
]
grid_specs.append(
    (z0 + active_fuel_height - GRID_THICKNESS / 2, core_lattice_grid_inconel)
)  # top end grid
grid_specs.sort(key=lambda spec: spec[0])

axial_segments = []
prev_z = z0
for z_center, lattice in grid_specs:
    grid_lo = z_center - GRID_THICKNESS / 2
    grid_hi = z_center + GRID_THICKNESS / 2
    if grid_lo > prev_z:
        axial_segments.append((prev_z, grid_lo, core_lattice))  # plain water band
    axial_segments.append((grid_lo, grid_hi, lattice))  # grid band
    prev_z = grid_hi
axial_segments.append((prev_z, z0 + active_fuel_height, core_lattice))  # final plain band

# Reuse a single surface for every z-value that appears as a boundary,
# instead of creating a fresh ZPlane per cell. This matters most at the
# very top and bottom of the stack: those boundaries must be the actual
# z_min/z_max surfaces (which carry boundary_type="vacuum"), not new plain
# transmission surfaces that happen to sit at the same coordinate - a
# transmission surface with no cell beyond it is exactly what produces
# "particle not located in any cell" lost-particle errors.
_zplane_cache = {
    round(z0, 9): z_min,
    round(z0 + active_fuel_height, 9): z_max,
}


def get_zplane(z):
    key = round(z, 9)
    if key not in _zplane_cache:
        _zplane_cache[key] = openmc.ZPlane(z0=z)
    return _zplane_cache[key]


main_cells = []
for z_lo, z_hi, lattice in axial_segments:
    plane_lo = get_zplane(z_lo)
    plane_hi = get_zplane(z_hi)
    main_cells.append(
        openmc.Cell(
            name=f"core [{z_lo:.2f}, {z_hi:.2f}] cm ({lattice.name})",
            fill=lattice,
            region=core_region & +plane_lo & -plane_hi,
        )
    )

steel_ring_cell = openmc.Cell(
    name="stainless steel perimeter and circular ring",
    fill=stainless_steel,
    region=steel_region & +z_min & -z_max,
)
outer_water_cell = openmc.Cell(
    name="water outside stainless steel ring",
    fill=water,
    region=outer_water_region & +z_min & -z_max,
)

root_universe = openmc.Universe(cells=main_cells + [steel_ring_cell, outer_water_cell])
geometry = openmc.Geometry(root_universe)

# =====================================================================
# 4. SETTINGS
# =====================================================================

settings = openmc.Settings()
settings.batches = int(os.environ.get("OPENMC_BATCHES", "40"))
settings.inactive = int(os.environ.get("OPENMC_INACTIVE", "10"))
settings.particles = int(os.environ.get("OPENMC_PARTICLES", "500"))
settings.threads = int(os.environ.get("OPENMC_THREADS", "1"))
settings.run_mode = "eigenvalue"

bounds = [
    -outer_radius,
    -outer_radius,
    -active_fuel_height / 2,
    outer_radius,
    outer_radius,
    active_fuel_height / 2,
]
uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True)
settings.source = openmc.Source(space=uniform_dist)

# =====================================================================
# 6. RUN
# =====================================================================

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists("plot_settings.pkl"):
        os.remove("plot_settings.pkl")
    materials.export_to_xml()
    geometry.export_to_xml()
    settings.export_to_xml()
    print(f"Exported geometry.xml: outer radius={r_steel_out:g}, inner radius={r_steel_in:g}")
    print(f"Axial segments (spacer grid stack): {len(axial_segments)} bands "
          f"({N_MID_GRIDS} mid-span + 2 end grids)")
    openmc.run()