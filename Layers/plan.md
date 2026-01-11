# PHASE 0: VALIDATION & ARCHITECTURE PLAN (REVISED)

## Project Overview
**Objective:** Build a Python CLI tool to optimize a 9-layer wall assembly minimizing LCA impact while meeting U-value target (0.14 ± 10%).

**Constraints:**
- Target U-Value: 0.126 – 0.154 W/(m²K)
- Internal Surface Resistance: Rsi = 0.13 m²K/W
- External Surface Resistance: Rse = 0.04 m²K/W
- Discrete material/thickness selection (no continuous optimization)
- Minimize Total A1-A3 GWP (kg CO₂-eq / m²)

---

## Data Structure Analysis

### Input Data Validation

**9 Layers Analyzed (Inside → Outside):**
1. **01_InteriorFinish.json** – Gypsum, calcium silicate, wood fiber finishes (m2/m3 mix)
2. **02_vapour_control_layer.json** – Foils, membranes (<1mm) – **MESSY LAYER** (typo λ=null, U-values suspicious)
3. **03_Wood_based_board.json** – OSB, plywood, particleboard (m3/m2 mix, null λ values)
4. **04_CavityInsulation.json** – Main insulation (Cellulose, StoneWool, WoodFiber, PIR, Aerogel) – Well-formed
5. **05_Base_layer.json** – **CONTAINS TONNE UNIT** – will normalize to kg in Phase 1
6. **06_SecondInsulationLayer.json** – Secondary insulation (Rockwool, Cork, PIR, EPS, XPS) – Well-formed
7. **07_WaterControlLayer.json** – Membranes, breathable sheets – Good λ values
8. **08_battens_rainscreen.json** – Steel/wood profiles – EMPTY thickness_range[] BUT materials must be included
9. **09_Facade_cladding.json** – Fiber cement, wood, composites – Null values in some LCA columns

### Critical Data Issues Identified

| Layer | Issue | Action |
|-------|-------|--------|
| **02** | Thin foils (<1mm) with suspicious U-values (0.04–0.07). λ=null. | Treat as **R ≈ 0** (negligible thermal resistance). Use provided U-value only for reference, ignore lambda-based calc. |
| **02** | Empty `thickness_range[]` | **Fallback Rule:** Use `[thickness_init]` (single-element list). Material is eligible but locked to that thickness. |
| **03** | Mix of `unit="m3"` and `unit="m2"`. λ=null, U-value provided. | For `unit="m2"`, thickness affects only mass (if density available). For `unit="m3"`, standard R-calculation. Ignore U-value; compute from λ if present. |
| **04** | `Cellulose_Insulation_01`: empty `thickness_range[]`. Factor = 1 for most, but factor may vary. | **Fallback Rule:** Use `[thickness_init]`. Apply factor multiplier to LCA. |
| **05** | Contains `unit="tonne"` – will normalize to kg in Phase 1 (multiply A1A3 by 1000, set unit to "kg"). | Standardize during data loading. |
| **06** | All materials have `thickness_range` (2–6 discrete values each). | **Best layer**: clean discrete choices. |
| **08** | **All materials have `thickness_range=[]` (empty).** Factor field sometimes `1.0`, sometimes unusual. | **Fallback Rule:** Use `[thickness_init]` as single-element list. Optimize by **material swapping only** (e.g., Steel vs Wood at fixed 1.5 mm). |
| **09** | Some A5/C2/C3 values are null. | Treat null LCA values as 0 in summation. |

---

## Chosen Data Structure: Hybrid Class + Dict

### Class Definition (Python)

```python
class Material:
    """Encapsulates a single material with thermal & LCA properties."""
    name: str
    layer_index: int           # 0-8 for layers 01-09
    lambda_value: float | None # W/m.K (thermal conductivity)
    thickness_init: float      # mm (initial thickness from JSON)
    thickness_range: list[float] # mm (discrete thickness options; fallback = [thickness_init])
    density: float | None      # kg/m³
    unit: str                  # "m3", "m2", or "kg" (tonne normalized to kg in Phase 1)
    a1a3: float               # A1-A3 GWP impact (unit-dependent: per m³, per kg, or per m²)
    factor: float             # Multiplier (default 1.0); may be 0.0 to exclude impact
    a5: float | None          # A5 impact (optional, sum for total)
    c2: float | None          # C2 impact
    c3: float | None          # C3 impact
    d: float | None           # D recovery (negative = benefit)
    
    def get_r_value(self, thickness_mm: float) -> float:
        """Compute R-value in m²K/W. Handles unit conversion."""
        # λ is in W/m.K; thickness in mm → convert to m
        # R = thickness_m / λ
        # Handle None λ gracefully: set R = 0 for foils (thin materials)
        
    def get_lca_impact(self, thickness_mm: float) -> float:
        """Compute LCA impact (A1-A3) based on unit, thickness, and factor."""
        # CORRECTED: Include factor multiplier in all cases
        # Logic depends on unit:
        # - m3: Impact = A1A3 * (thickness_mm / 1000) * Factor
        # - m2: Impact = A1A3 * Factor (thickness independent)
        # - kg: Impact = A1A3 * density * (thickness_mm / 1000) * Factor
```

### Wall Assembly Structure

```python
class WallAssembly:
    """Represents the complete 9-layer wall with one material per layer."""
    layers: list[Material]  # Index 0-8 for layers 01-09
    
    def calculate_u_value(self) -> float:
        """Compute U-value from R-values of selected materials."""
        r_total = 0.13 + sum(layer.get_r_value() for layer in layers) + 0.04
        return 1.0 / r_total
    
    def calculate_total_lca(self) -> float:
        """Sum all A1-A3 impacts across layers."""
        return sum(layer.get_lca_impact() for layer in layers)
    
    def is_valid(self) -> bool:
        """Check U-value within target range."""
        u = self.calculate_u_value()
        return 0.126 <= u <= 0.154
```

---

## Mathematical Verification Strategy

### 1. **R-Value Calculation**

**Formula:** 
$$R = \frac{\text{thickness (m)}}{\lambda \text{ (W/m.K)}}$$

**Test Case 1 (Normal Material):**
- Material: StoneWool, λ = 0.037 W/m.K, thickness = 100 mm
- Expected: R = 0.1 / 0.037 = 2.703 m²K/W ✓

**Test Case 2 (Thin Foil, Layer 02):**
- Material: PE_Foil_0.2_mm, λ = null, thickness = 0.2 mm
- **Action:** Set R ≈ 0 (foil negligible). Log warning.

**Test Case 3 (Fixed Battens, Layer 08):**
- Material: carbonlow_steel_profiles_01, λ = 50 W/m.K, thickness = 1.5 mm
- Expected: R = 0.0015 / 50 = 0.00003 m²K/W ✓ (minimal contribution)

---

### 2. **U-Value Calculation**

**Formula:**
$$U = \frac{1}{R_{si} + \sum(R_{\text{layers}}) + R_{se}} = \frac{1}{0.13 + R_{\text{total}} + 0.04}$$

**Manual Verification Example:**
Suppose total R_layers = 5.0 m²K/W:
- R_total = 0.13 + 5.0 + 0.04 = 5.17
- U = 1 / 5.17 = 0.194 W/(m²K) ✗ (exceeds upper bound 0.154)
- Adjustment needed: increase λ (thinner insulation) or increase thickness of low-λ materials.

---

### 3. **LCA Calculation Logic (FINAL CORRECTED WITH FACTOR)**

**Key Principle:** Unit field indicates the basis of the A1-A3 value. Factor is a multiplier applied to ALL cases.

#### **Case A: unit = "m3"**
$$\text{Impact} = \text{A1A3} \times \frac{\text{thickness (mm)}}{1000} \times \text{Factor}$$

The A1-A3 value is **per cubic meter of material**. Scale by thickness and apply factor.

Example: WoodFibre_Insulation_03, A1A3 = -173.14 kg CO₂-eq/m³, thickness = 60 mm, factor = 1.0
- Impact = -173.14 × (60 / 1000) × 1.0 = **-10.39 kg CO₂-eq/m²** ✓

**Special Case (Factor = 0.0):**
Example: Cellulose_Insulation_01 (Layer 04), A1A3 = -8.25, factor = 1.0
- If factor were 0.0: Impact = -8.25 × (thickness / 1000) × 0.0 = **0** (material ignored in LCA)
- **Action:** Log warning "Material excluded from LCA (factor=0.0)" but still include in U-value calculation.

---

#### **Case B: unit = "m2"**
$$\text{Impact} = \text{A1A3} \times \text{Factor}$$

The A1-A3 value is **per square meter** (thickness-independent).

Example: EPDM_Membrane, A1A3 = 6.8 kg CO₂-eq/m², factor = 1.0
- Impact = 6.8 × 1.0 = **6.8 kg CO₂-eq/m²** ✓

---

#### **Case C: unit = "kg"**
$$\text{Impact} = \text{A1A3} \times \text{density} \times \frac{\text{thickness (mm)}}{1000} \times \text{Factor}$$

The A1-A3 value is **per kilogram of material**. Multiply by mass and apply factor.

Example: carbonlow_steel_profiles_01, A1A3 = 0.902 kg CO₂-eq/kg, density = 7850 kg/m³, thickness = 1.5 mm, factor = 1.0
- Impact = 0.902 × 7850 × (1.5 / 1000) × 1.0 = **10.56 kg CO₂-eq/m²** ✓

---

#### **Case D: unit = "tonne" (NORMALIZED IN PHASE 1)**
**Phase 1 Action:** If `unit="tonne"`, multiply `A1A3` by 1000 immediately and change `unit` to `"kg"`.
This eliminates the need for a special case in the physics engine.

Example (input): Material_X, A1A3 = 0.5 kg CO₂-eq/tonne, unit = "tonne"
- **After Phase 1 normalization:** A1A3 = 500 kg CO₂-eq/kg, unit = "kg"
- Physics engine treats it as Case C normally.

---

### 4. **Target U-Value Feasibility Check**

**Lower bound (0.126):** Requires high R_total ≈ 6.5 (very thick insulation)
**Upper bound (0.154):** Requires R_total ≈ 5.35

**Estimated optimal R range:** 5.35 – 6.5 m²K/W (good insulation achievable)

---

## Three Critical Logic Fixes

### **FIX #1: Layer 08 Fallback Rule (REVISED)**

**The Contradiction Resolved:**
- Your plan correctly identified that Layer 08 has empty `thickness_range[]` lists.
- However, marking Layer 08 as "ineligible" would prevent the optimizer from building a complete 9-layer wall.

**The Solution: Fallback Rule**
```
if thickness_range is empty or has length 0:
    thickness_range = [thickness_init]  # Single-element list
```

**Implication:**
- Layer 08 materials are **still optimized** (you can swap Steel vs Wood batten material).
- But thickness is **locked** to `thickness_init` (e.g., 1.5 mm).
- This satisfies both the constraint (9 complete layers) and the discrete optimization (material selection only).

---

### **FIX #2: Factor Multiplier in LCA Formulas (REVISED)**

**The Issue:**
Your plan.md identified the `factor` field in JSONs but omitted it from the math formulas in Section 3.

**The Solution: Include Factor in All Cases**

| Unit | Formula (Corrected) |
|------|---|
| m³ | `Impact = A1A3 × (thickness / 1000) × Factor` |
| m² | `Impact = A1A3 × Factor` |
| kg | `Impact = A1A3 × density × (thickness / 1000) × Factor` |

**Special Handling: factor = 0.0**
- Materials with `factor = 0.0` contribute **zero** to LCA impact.
- They still contribute to U-value (thermal resistance is included).
- **Action:** Log warning for transparency: "Material 'X' excluded from LCA (factor=0.0)".

Example: Layer 04 has some materials with factor = 0.0; they are thermally active but LCA-neutral.

---

### **FIX #3: Tonne Unit Normalization (PHASE 1)**

**The Issue:**
Layer 05 contains `unit="tonne"`. Handling this in the physics engine would require a 4th case.

**The Solution: Normalize During Data Loading**

In **Phase 1: Data Normalization**, apply this rule to every material:
```python
if material['unit'] == 'tonne':
    material['a1a3'] *= 1000  # Convert kg CO₂-eq/tonne → kg CO₂-eq/kg
    material['unit'] = 'kg'    # Relabel to standard unit
```

**Benefit:**
- Physics engine (Phase 2) only needs 3 cases (m³, m², kg).
- Cleaner code, fewer special cases.
- All LCA values internally normalized to the same basis.

**Verification:**
- Input: A1A3 = 0.5 kg CO₂-eq/tonne, unit = "tonne"
- After Phase 1: A1A3 = 500 kg CO₂-eq/kg, unit = "kg" ✓
- Physics engine applies Case C (kg) normally.

---

## Updated Do's and Don'ts (Data Handling)

### ✅ **DO:**

1. **Apply Fallback Rule for empty thickness_range** – If `thickness_range.length == 0`, set `thickness_range = [thickness_init]`.
2. **Check unit field** – Parse correctly (m3, m2, kg, tonne) before Phase 2.
3. **Handle null λ gracefully** – Set R = 0 for foils in Layer 02; warn user.
4. **Handle null density** – Only required for kg units (after normalization). For m2/m3, use A1-A3 as-is.
5. **Include factor multiplier in all LCA calculations** – Apply factor to every case.
6. **Treat factor = 0.0 gracefully** – Material is thermally active but LCA-neutral. Log warning.
7. **Normalize tonne → kg in Phase 1** – Multiply A1A3 by 1000, change unit to "kg".
8. **Iterate discrete thickness only** – Do NOT interpolate or guess values.
9. **Store valid combinations** – Cache passing U-value combos before sorting by LCA.

### ❌ **DON'T:**

1. ❌ Mark Layer 08 as "ineligible" – Use Fallback Rule instead.
2. ❌ Omit factor from LCA formulas – Factor is mandatory.
3. ❌ Use U-value fields from JSON directly – Recalculate from λ and thickness.
4. ❌ Interpolate missing λ values – Data is discrete; set R = 0 for foils.
5. ❌ Mix unit systems – Normalize all units to (m3, m2, kg) in Phase 1.
6. ❌ Apply density to m³ cases – A1A3 is already per m³; scale only by thickness × factor.
7. ❌ Forget surface resistances – Always include Rsi = 0.13, Rse = 0.04.
8. ❌ Handle tonne in physics engine – Normalize in Phase 1 instead.

---

## Execution Phases Roadmap

| Phase | Task | Input | Output | Est. Time |
|-------|------|-------|--------|-----------|
| **0** | ✓ Architecture & Validation (REVISED) | JSON files | `plan.md` (this doc) | *COMPLETE* |
| **1** | Data Normalization | 9 JSONs | `data_loader.py` + DataFrame | 30 min |
| **2** | Physics Engine | Normalized data | `math_engine.py` (U, LCA calcs) + unit tests | 30 min |
| **3** | Optimization Loop | Materials registry | `optimizer.py` (find winners) | 45 min |
| **4** | Interactive CLI | Optimizer output | `main.py` (full user loop) | 60 min |
| **5** | Documentation | Code + tests | `README.md` + tutorial | 30 min |

---

## Code Quality Assurance

- **Unit Tests:** Verify R-value, U-value, LCA for known materials (3+ per function, including factor=0.0 edge case).
- **Integration Test:** Full wall (9 layers) with one combo; print all intermediates.
- **Performance:** Optimization must complete <10 seconds (typical 10³–10⁴ valid combos).
- **Logging:** Warn on null values, skipped materials, empty thickness_range (with fallback), factor=0.0, tonne normalization.
- **CLI Robustness:** Input validation; fallback defaults for invalid selections.

---

## Validated Math Logic (Final)

Based on the provided diagrams, the physics engine will use:

1. **R-Value:** $R = d / \lambda$ (with R ≈ 0 for thin foils where λ = null)
2. **U-Value:** $U = 1 / (0.13 + \sum R + 0.04)$
3. **LCA (m³):** $\text{GWP} \times \text{thickness (m)} \times \text{Factor}$
4. **LCA (kg):** $\text{GWP} \times \text{density} \times \text{thickness (m)} \times \text{Factor}$
5. **LCA (m²):** $\text{GWP} \times \text{Factor}$

---

## ✅ REVISED & READY FOR PHASE 1

**Three critical fixes applied:**
1. **Layer 08 Fallback Rule:** Empty thickness_range → use [thickness_init]
2. **Factor Multiplier:** Included in all LCA formulas
3. **Tonne Normalization:** Convert to kg in Phase 1 (multiply A1A3 by 1000, set unit = "kg")

**Proceeding to Phase 1: Data Normalization** ✓
