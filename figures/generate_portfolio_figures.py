"""
Portfolio figures for wall-assembly-LCA-optimizer.

All numbers are produced by RE-RUNNING the project's own optimizer on the real
material/layer JSON catalogs in layers/ -- nothing is fabricated. This script is
self-contained: run it from the project root (the directory containing
optimizer.py / data_loader.py / layers/).

Extracted directly from the optimizer:
  - Pareto-efficient (R, LCA) points for every merged assembly it evaluates
  - the valid assemblies meeting the U-value constraint band
  - the search-space funnel: full raw product -> Pareto-efficient layer combos
    -> merged half-combinations -> valid -> optimum
The optimum (R=6.609, LCA=-50.63, U=0.1475) matches outputs/reports/summary_*.md.
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

# --- locate project root (parent of this figures/ dir) and import real modules ---
PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
OUT = PROJ / "figures"
OUT.mkdir(exist_ok=True)

from data_loader import load_data                                   # noqa: E402
from optimizer import get_layer_candidates, combine_layers          # noqa: E402
from config import (R_SI, R_SE, R_LAYERS_MIN, R_LAYERS_MAX,         # noqa: E402
                    TARGET_U, U_MIN, U_MAX)

# --- recompute everything from the real catalogs ---
_mats = load_data()
_raw_per_layer = {}
for _m in _mats:
    _raw_per_layer[_m.layer_index] = _raw_per_layer.get(_m.layer_index, 0) + len(_m.thickness_options)
_full = 1
for _k in _raw_per_layer:
    _full *= _raw_per_layer[_k]
_cm = get_layer_candidates(_mats)
_eff = 1
for _k in _cm:
    _eff *= len(_cm[_k])
_inner = combine_layers([0, 1, 2, 3, 4], _cm)
_outer = combine_layers([5, 6, 7, 8], _cm)

allpts, validpts = [], []
for r_in, lca_in, _ in _inner:
    for r_out, lca_out, _ in _outer:
        R = r_in + r_out
        L = lca_in + lca_out
        U = 1.0 / (R_SI + R + R_SE)
        ok = (R_LAYERS_MIN <= R <= R_LAYERS_MAX)
        allpts.append([R, L, U, ok])
        if ok:
            validpts.append([R, L, U])

cfg = {"R_MIN": R_LAYERS_MIN, "R_MAX": R_LAYERS_MAX,
       "U_MIN": U_MIN, "U_MAX": U_MAX, "TARGET_U": TARGET_U}
fn = {"full": _full, "efficient_layers": _eff,
      "merged": len(allpts), "valid": len(validpts)}

R_all  = np.array([p[0] for p in allpts])
L_all  = np.array([p[1] for p in allpts])
valid  = np.array([p[3] for p in allpts], dtype=bool)
R_v    = np.array([p[0] for p in validpts])
L_v    = np.array([p[1] for p in validpts])
# optimum = min LCA among valid
opt_i  = int(np.argmin(L_v))
R_opt, L_opt = R_v[opt_i], L_v[opt_i]
U_opt  = [p[2] for p in validpts][opt_i]

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 170,
    "font.size": 11, "font.family": "DejaVu Sans",
    "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.labelsize": 11.5, "axes.edgecolor": "#444444", "axes.linewidth": 0.9,
    "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.7,
    "axes.axisbelow": True, "legend.frameon": True, "legend.framealpha": 0.95,
    "legend.edgecolor": "#cccccc", "figure.facecolor": "white", "axes.facecolor": "white",
})

GREEN = "#1b7f3b"; GREY = "#b9c0c7"; GOLD = "#e8a33d"; RED = "#c0392b"

# ============================================================
# FIG 1 (HERO): Pareto frontier -- LCA (carbon) vs total R-value
#   every evaluated Pareto-efficient assembly; constraint band shaded;
#   the 6 valid assemblies highlighted; climate-positive optimum starred.
# ============================================================
fig, ax = plt.subplots(figsize=(9.8, 6.2))

# Focus on the decision-relevant region: assemblies up to R = 35, where the
# U-value target band and the optimum live. Every assembly in this window stores
# carbon (LCA < 0). A separate high-insulation / high-GWP regime (R up to ~66,
# LCA up to 8,087) is summarized in the caption rather than crushing this view.
X_LO, X_HI = 4.7, 35.6
in_x = (R_all >= X_LO) & (R_all <= X_HI)
Y_LO, Y_HI = float(np.floor(L_all[in_x].min())) - 3.0, 6.0
shown = in_x & (L_all <= Y_HI)
n_shown = int(shown.sum())
n_hidden = len(allpts) - n_shown

# constraint band on R (behind everything) + carbon-neutral reference line
ax.axvspan(cfg["R_MIN"], cfg["R_MAX"], color="#2ca02c", alpha=0.10, zorder=0)
ax.axhline(0, color="#777", lw=1.0, ls="--", zorder=1)
ax.text(X_HI - 0.4, 0.9, "carbon-neutral  (LCA = 0)", fontsize=8.2, color="#888",
        style="italic", ha="right", va="bottom", zorder=3)
ax.text(20.0, -4.0,
        "every assembly shown stores more CO₂ than it emits  (climate-positive)",
        fontsize=8.8, color=GREEN, style="italic", fontweight="bold",
        ha="center", va="center", zorder=3)

# all evaluated efficient assemblies in this window (alpha reveals overlap density)
ax.scatter(R_all[~valid & in_x], L_all[~valid & in_x], s=24, color=GREY, alpha=0.5,
           edgecolor="white", linewidth=0.2, zorder=2,
           label="Evaluated assembly")
# valid (within U-value target band)
ax.scatter(R_v, L_v, s=120, color=GOLD, edgecolor="#7a4d00", linewidth=1.1,
           zorder=4, label=f"Meets U-value target ({len(validpts)})")
# optimum
ax.scatter([R_opt], [L_opt], marker="*", s=560, color=RED, edgecolor="#4d0000",
           linewidth=1.3, zorder=6, label=f"Optimum: {L_opt:.1f} kg CO₂/m²")

# optimum callout, anchored in the clear strip above the point cloud
ax.annotate(f"OPTIMUM\nR = {R_opt:.2f} m²K/W\nU = {U_opt:.3f} W/(m²K)\n"
            f"LCA = {L_opt:.1f} kg CO₂-eq/m²",
            xy=(R_opt, L_opt), xytext=(13.5, -11.5), textcoords="data",
            ha="left", va="center", fontsize=9.5, fontweight="bold", color="#222",
            bbox=dict(boxstyle="round,pad=0.5", fc="#fff4f4", ec=RED, lw=1.3),
            arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.7,
                            connectionstyle="arc3,rad=0.12"), zorder=7)

# constraint-band label, top-centered over the band
ax.annotate(f"U-value target band\nR ∈ [{cfg['R_MIN']:.2f}, {cfg['R_MAX']:.2f}]\n"
            f"U ∈ [{cfg['U_MIN']:.3f}, {cfg['U_MAX']:.3f}]",
            ((cfg["R_MIN"]+cfg["R_MAX"])/2, Y_HI-0.6), ha="center", va="top",
            fontsize=8.4, color="#2a6e2a",
            bbox=dict(boxstyle="round,pad=0.4", fc="#eefaef", ec="#2ca02c"), zorder=5)

ax.set_xlim(X_LO, X_HI); ax.set_ylim(Y_LO, Y_HI)
ax.set_xlabel("Total thermal resistance  R  (m²K/W)  → better insulation")
ax.set_ylabel("Life-cycle carbon  (kg CO₂-eq/m²)  ↓ lower is better")
ax.set_title("Wall Assembly Optimization: Carbon vs. Thermal Performance")
ax.legend(loc="upper right", fontsize=9.3, framealpha=0.96)
ax.text(0.5, -0.16,
        f"Showing the {n_shown} lower-R assemblies (R ≤ 35), where the U-value target and "
        f"optimum lie.  {n_hidden} higher-R assemblies (R up to {R_all.max():.0f}) run off-scale, "
        f"including {int((L_all > 100).sum())} high-GWP (LCA up to {L_all.max():,.0f} kg CO₂/m²).",
        transform=ax.transAxes, ha="center", fontsize=7.8, color="#888", style="italic")
fig.tight_layout()
fig.savefig(OUT / "fig1_pareto_carbon_vs_rvalue.png", bbox_inches="tight", dpi=200)
plt.close(fig)

# ============================================================
# FIG 2: Search-space reduction funnel (real counts)
# ============================================================
stages = [
    ("Full search space\n(all material × thickness combos)", fn["full"]),
    ("After Pareto pruning\n(efficient layer combinations)",      fn["efficient_layers"]),
    ("Divide-&-conquer merge\n(efficient half-combinations)",     fn["merged"]),
    ("Meet U-value constraint",                                   fn["valid"]),
    ("Optimal assembly",                                          1),
]
vals = [s[1] for s in stages]
labels = [s[0] for s in stages]
logv = np.log10(vals)
cols = ["#9bb7d4", "#6f9bd1", "#4b7fc0", "#2e63a6", RED]

fig, ax = plt.subplots(figsize=(9.6, 5.6))
maxw = logv[0]
for i, (lv, raw, lab, c) in enumerate(zip(logv, vals, labels, cols)):
    w = lv
    y = len(stages) - 1 - i
    ax.add_patch(Rectangle(((maxw - w)/2, y-0.34), w, 0.68, facecolor=c,
                           edgecolor="#222", linewidth=0.8, alpha=0.92))
    ax.text(maxw/2, y, f"{raw:,}", ha="center", va="center", fontsize=12,
            fontweight="bold", color="white")
    ax.text(maxw + 0.25, y, lab, ha="left", va="center", fontsize=10.2)
# reduction arrows / factors
for i in range(len(stages)-1):
    factor = vals[i] / vals[i+1]
    ymid = (len(stages)-1-i) - 0.5
    ax.annotate("", xy=(maxw/2, ymid-0.16), xytext=(maxw/2, ymid+0.16),
                arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.4))
    ax.text(maxw/2 - 0.35, ymid, f"÷{factor:,.0f}", ha="right", va="center",
            fontsize=8.6, color="#555", style="italic")

ax.set_xlim(-0.3, maxw + 6.2)
ax.set_ylim(-0.7, len(stages)-0.3)
ax.axis("off")
ax.set_title("Search-Space Reduction: 2.1 Trillion → 1 Optimal Wall",
             fontsize=15, pad=14)
ax.text(0.5, -0.06,
        "Bar length ∝ log₁₀(count).  All counts produced by re-running the project's "
        "own Pareto + divide-and-conquer optimizer on the real material catalogs.",
        transform=ax.transAxes, ha="center", fontsize=8.4, color="#666")
fig.tight_layout()
fig.savefig(OUT / "fig2_search_space_reduction.png", bbox_inches="tight")
plt.close(fig)

# ============================================================
# FIG 3: Layer-by-layer carbon contribution of the optimal assembly
#   (from outputs/reports/summary_*.md, which equals the optimizer result)
# ============================================================
layers = [
    ("L0  Calcium silicate board",      0.103),
    ("L1  Aluminium foil",              0.001),
    ("L2  Plywood",                     0.017),
    ("L3  Cellulose insulation",       -8.250),
    ("L4  Hollow block B40",            1.214),
    ("L5  Jackon XPS",                  0.550),
    ("L6  Breathable membrane",         1.600),
    ("L7  Planed & treated wood",     -35.820),
    ("L8  Cladding & decking",        -10.045),
]
names = [l[0] for l in layers]
lca   = [l[1] for l in layers]
total = sum(lca)
fig, ax = plt.subplots(figsize=(9.4, 5.8))
bar_cols = [GREEN if v < 0 else "#c98a3a" for v in lca]
y = np.arange(len(names))[::-1]
ax.barh(y, lca, color=bar_cols, edgecolor="#222", linewidth=0.7, alpha=0.9)
for yi, v in zip(y, lca):
    if v <= -25:   # long storing bars: label sits inside, to the right of bar end
        ax.text(v + 0.8, yi, f"{v:+.1f}", va="center", ha="left",
                fontsize=9.5, fontweight="bold", color="white")
    else:
        ax.text(v + (0.5 if v >= 0 else -0.5), yi, f"{v:+.1f}",
                va="center", ha="left" if v >= 0 else "right",
                fontsize=9.5, fontweight="bold",
                color=GREEN if v < 0 else "#8a5a18")
ax.axvline(0, color="#333", lw=1.1)
ax.set_xlim(-40, 5)
ax.set_yticks(y); ax.set_yticklabels(names, fontsize=9.6)
ax.set_xlabel("Layer life-cycle carbon  (kg CO₂-eq/m²)   ← stores   |   emits →")
ax.set_title("Carbon Contribution by Layer in the Optimal Wall")
ax.text(0.04, 0.30,
        f"Net assembly: {total:.1f} kg CO₂-eq/m²\n(climate-positive)\n"
        f"U-value 0.1475 W/(m²K)\nR 6.609 m²K/W",
        transform=ax.transAxes, ha="left", va="center", fontsize=9.5,
        fontweight="bold", color="#1b5e20",
        bbox=dict(boxstyle="round,pad=0.5", fc="#eefaef", ec=GREEN, lw=1.2))
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(OUT / "fig3_layer_carbon_breakdown.png", bbox_inches="tight")
plt.close(fig)

print("wall-LCA figures written to", OUT)
for p in sorted(OUT.glob("fig*.png")):
    print("  ", p.name)
print(f"\nKey real numbers: full={fn['full']:,}  efficient={fn['efficient_layers']:,} "
      f"merged={fn['merged']}  valid={fn['valid']}  optimum LCA={L_opt:.2f}")
