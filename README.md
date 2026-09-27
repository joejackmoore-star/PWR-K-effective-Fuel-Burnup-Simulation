# PWR K-effective Fuel Burnup Simulation

Monte Carlo neutron transport and fuel depletion model of a
Pressurized Water Reactor (PWR) core, built with [OpenMC](https://openmc.org/).
The model tracks the effective multiplication factor, **k-effective**, as the
fuel burns up over time and plots its degradation.

## Overview

The core is a 193-assembly, 17×17 pin-cell PWR layout with three fuel
enrichment zones, burnable-absorber (Pyrex) rods, guide/instrument tubes, an
axial stack of Zircaloy and Inconel spacer grids, and a stainless-steel core
barrel. `openmc.deplete` is used to burn the fuel over a user-defined number
of timesteps at a given reactor power, and the resulting k-effective values
are plotted against time.

**Core layout**

- 17×17 fuel assemblies, `pin_pitch = 1.26 cm`
- 193 fuel assemblies arranged radially by enrichment zone:
  - 1.6% U-235 (innermost zone, includes burnable-absorber rods)
  - 2.4% U-235 (mid zone)
  - 3.1% U-235 (outer zone)
- Central instrument tube and 24/25-position guide-tube patterns per assembly
- Helium gap and Zircaloy-4 cladding for every fuel pin
- Borated water moderator/coolant (900 ppm boron)
- Axial spacer-grid stack: 2 Inconel-718 end grids + 8 mid-span Zircaloy-4
  grids, each smeared into the coolant as a volume-weighted mixture
- Stainless-steel core barrel with a vacuum outer boundary

## Repository contents

| File | Description |
|---|---|
| `PWRAssembly.py` | Builds materials, geometry (pin cells → assemblies → 193-assembly core), and eigenvalue `Settings`. Exporting this module writes `materials.xml`, `geometry.xml`, and `settings.xml`, and (when run directly) launches a criticality (`k-eigenvalue`) calculation. |
| `depletion.py` | Imports `PWRAssembly`, assigns depletable material volumes, builds an `openmc.Model`, and runs a coupled depletion calculation over a series of timesteps. Produces `depletion_results.h5` and a `keff_vs_time.png` plot of k-effective vs. time. |
| `materials.xml`, `geometry.xml`, `settings.xml`, `tallies.xml`, `plots.xml` | OpenMC input files exported by/for the model (also regenerated automatically by the Python scripts). |

## Requirements

- Python 3.8+
- [OpenMC](https://docs.openmc.org/en/stable/quickinstall.html) (with the
  `openmc.deplete` module)
- `matplotlib` (for plotting k-effective vs. time)
- A nuclear cross-section data library, e.g.
  [ENDF/B-VII.1 or VIII.0 HDF5 data](https://openmc.org/data-libraries/)
- A matching depletion chain file, e.g. `chain_endfb71_pwr.xml` from
  [OpenMC's depletion chains](https://openmc.org/depletion-chains/)

Install the Python dependencies:

```bash
pip install openmc matplotlib
```

OpenMC itself is typically installed via conda/mamba — see the
[OpenMC installation guide](https://docs.openmc.org/en/stable/quickinstall.html)
for platform-specific instructions.

## Configuration

Cross-section and chain file paths, along with key simulation parameters, are
read from environment variables (with sensible defaults hardcoded for the
original author's machine). Set the ones relevant to your setup before
running either script:

| Variable | Default | Purpose |
|---|---|---|
| `OPENMC_BATCHES` | `40` | Total number of criticality batches |
| `OPENMC_INACTIVE` | `10` | Number of inactive (source convergence) batches |
| `OPENMC_PARTICLES` | `500` | Particles per batch |
| `OPENMC_THREADS` | `1` | OpenMP threads for OpenMC |
| `DEPLETION_POWER_W` | `3400e6` | Reactor thermal power, in watts |
| `DEPLETION_STEPS` | `6` | Number of depletion timesteps |
| `DEPLETION_TIMESTEP_DAYS` | `30` | Length of each depletion timestep, in days |
| `DEPLETION_INTEGRATOR` | `predictor` | Depletion integrator: `predictor` or `cecm` |

> **Note:** `OPENMC_BATCHES`, `OPENMC_INACTIVE`, and `OPENMC_PARTICLES`
> default to low values suitable for a quick smoke test. Increase them for
> production-quality tallies and depletion results.

## Usage

### 1. Set up your nuclear data

Point the environment variables at your local cross-section and chain data,
for example:

```bash
export OPENMC_CROSS_SECTIONS=/path/to/endfb-vii.1-hdf5/cross_sections.xml
export OPENMC_CHAIN_FILE=/path/to/chain_endfb71_pwr.xml
```

### 2. Run a single criticality calculation

```bash
python PWRAssembly.py
```

This exports `materials.xml`, `geometry.xml`, and `settings.xml`, then runs a
`k-eigenvalue` calculation for the fresh (unburned) core.

### 3. Run the fuel burnup / depletion simulation

```bash
python depletion.py
```

This builds the OpenMC model, runs `openmc.deplete` over the configured
timesteps at the configured power, and produces:

- `depletion_results.h5` — depletion results (k-effective and nuclide
  inventories vs. time)
- `keff_vs_time.png` — plot of k-effective vs. time with uncertainty bars

Example (shorter run, 4 steps of 15 days at 3000 MWt):

```bash
export DEPLETION_STEPS=4
export DEPLETION_TIMESTEP_DAYS=15
export DEPLETION_POWER_W=3000e6
python depletion.py
```

## Output

`plot_depletion_keff()` in `depletion.py` reads the depletion results and
plots k-effective (with error bars, where available) against time in days,
saving the figure to `keff_vs_time.png`. This shows the expected downward
trend in k-effective as fissile material is consumed and fission products
build up over a fuel cycle.

## Notes

- The core geometry can be visualised interactively with openmc-plotter — after running PWRAssembly.py once to export materials.xml/geometry.xml (and using plots.xml if you want saved plot definitions), install it with pip install openmc-plotter and launch it from the repo directory with openmc-plotter.
- Geometry uses a single shared `ZPlane` per unique axial elevation to avoid
  "particle not located in any cell" lost-particle errors at segment
  boundaries.
- Spacer grids are modeled by volumetrically mixing grid metal (Zircaloy-4 for
  mid-span grids, Inconel-718 for end grids) into the coolant at the
  corresponding axial elevations, rather than modeling individual grid straps.
- Burnable-absorber (Pyrex) rod positions are derived as the set difference
  between the 1.6% assembly's guide-tube pattern and the standard guide-tube
  pattern used in the 2.4%/3.1% assemblies.