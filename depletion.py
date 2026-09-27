import os
import math
import openmc
import openmc.deplete
import PWRAssembly as pwr

# ==========================DEPLETION CALCULATION===============================
power = float(os.environ.get("DEPLETION_POWER_W", "3400e6"))
pwr.fuel16.volume = 3_514_017.1  # cm^3, total across all 18,216 rods
pwr.fuel24.volume = 3_870_511.6
pwr.fuel31.volume = 2_444_533.6

ba_rod_count = 12* (76 + 48)

    
pwr.pyrex.volume = ba_rod_count * math.pi * pwr.ba_or.r**2 * pwr.active_fuel_height

pwr.materials.export_to_xml()
pwr.geometry.export_to_xml()
pwr.settings.export_to_xml()

model = openmc.Model(geometry=pwr.geometry, materials=pwr.materials, settings=pwr.settings)
operator = openmc.deplete.CoupledOperator(model, chain_file=pwr.chain_file)


def run_depletion():
    depletion_steps = int(os.environ.get("DEPLETION_STEPS", "6"))
    timestep_days = float(os.environ.get("DEPLETION_TIMESTEP_DAYS", "30"))
    timesteps = [timestep_days] * depletion_steps
    integrator_name = os.environ.get("DEPLETION_INTEGRATOR", "predictor").lower()
    integrator_class = {
        "cecm": openmc.deplete.CECMIntegrator,
        "predictor": openmc.deplete.PredictorIntegrator,
    }.get(integrator_name)
    if integrator_class is None:
        raise ValueError("DEPLETION_INTEGRATOR must be 'cecm' or 'predictor'")
    integrator = integrator_class(
        operator, timesteps, power, timestep_units="d", solver="cram48"
    )
    integrator.integrate()
    plot_depletion_keff()


def plot_depletion_keff(
    results_path="depletion_results.h5", output_path="keff_vs_time.png"
):
    import matplotlib.pyplot as plt

    results = openmc.deplete.Results(results_path)
    times_days = results.get_times()
    if hasattr(results, "get_keff"):
        _, keff = results.get_keff()
    else:
        _, keff = results.get_eigenvalue()

    if keff.ndim > 1:
        keff_std = keff[:, 1]
        keff = keff[:, 0]
    else:
        keff_std = None

    fig, axis = plt.subplots(figsize=(8, 5))
    axis.errorbar(
        times_days,
        keff,
        yerr=keff_std,
        fmt="o-",
        capsize=3,
        linewidth=1.5,
        label=r"$k_{\mathrm{eff}}$",
    )
    axis.set_xlabel("Time (days)")
    axis.set_ylabel(r"$k_{\mathrm{eff}}$")
    axis.set_title("Effective multiplication factor during depletion")
    axis.grid(True, alpha=0.3)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"Saved depletion plot to {output_path}")

if __name__ == "__main__":
	run_depletion()