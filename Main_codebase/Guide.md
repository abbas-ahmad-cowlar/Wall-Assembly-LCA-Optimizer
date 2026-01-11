# Wall Assembly LCA Optimizer

## 1. Introduction & Objective

### The Challenge

The goal of this project was to design a 9-layer architectural wall assembly that balances two competing constraints:

1. **Thermal Performance (U-Value):** The wall must insulate well, meeting a strict target of ****.
2. **Environmental Impact (LCA):** The wall must have the lowest possible Global Warming Potential (GWP), measured in .

### The Computational Problem

Manually calculating every possible combination of materials is impossible.

* The wall has 9 layers.
* Each layer has multiple material choices (e.g., Brick vs. Concrete Block).
* Each material has multiple thickness options.

If we estimate roughly 5 valid options per layer, the total number of combinations is:


A human cannot calculate 1.9 million spreadsheets. This tool automates that process to find the mathematical minimum impact in under 1 second.

---

## 2. Architecture: How the Tool Works

The software is divided into five distinct "Phases" or scripts. Think of each script as a specialist team member with one specific job.

### Phase 1: The Cleaner (`data_loader.py`)

**Job:** Prepare the messy raw data for calculation.

Real-world data is rarely perfect. This script handles three critical issues found in the provided JSON files:

1. **Unit Standardization:** Some materials were measured in `Tonnes`, others in `kg`, and others in `m³`. This script converts everything into standard units so they can be compared fairly.
2. **The "Foil" Logic:** Layer 2 contains thin foils (<1mm). These materials often lacked thermal conductivity data (). The script detects these and assigns them a thermal resistance of roughly zero (), preventing mathematical errors.
3. **Fallback Rules:** Some materials (like Battens in Layer 8) had no thickness options listed. The script automatically assigns a default thickness so the optimization doesn't break.

### Phase 2: The Physicist (`physics.py`)

**Job:** Apply the Laws of Physics (ISO 6946).

This script calculates two numbers for every single layer:

**A. Thermal Resistance (R-Value)**
Formula: $R = \frac{\text{thickness}}{\text{thermal conductivity}(\lambda)}$

* *Why?* Higher R-values mean better insulation. We sum the R-values of all 9 layers to get the total insulation.

**B. Environmental Impact (LCA)**
Formula: $\text{Impact} = \text{GWP (A1-A3)} \times \text{Quantity} \times \text{Factor}$

* *Why?* This measures the carbon footprint. The "Quantity" depends on the unit type (Mass vs. Volume vs. Area).

### Phase 3: The Strategist (`optimizer.py`)

**Job:** Find the best combination without checking every single one (Brute Force).

This script uses two advanced logic techniques:

**Technique 1: Pareto Pruning**
Imagine you have two insulation options for Layer 3:

* **Option A:** Thickness 100mm, Impact 10 kg CO2.
* **Option B:** Thickness 100mm, Impact 20 kg CO2.

Option B is mathematically "dominated." It provides no benefit (same insulation) but costs twice as much carbon. The script deletes Option B immediately. This reduces the search space from 1.9 million to just a few thousand "efficient" options.

**Technique 2: Divide and Conquer**
Instead of building the whole wall at once, the script builds the "Inner Half" (Layers 0-4) and the "Outer Half" (Layers 5-8) separately. It then mathematically matches the best inner halves with the best outer halves to hit the target U-value.

### Phase 4: The Interface (`main.py`)

**Job:** Allow you to interact with the results.

This script runs the optimization, presents the "Winning Wall," and then lets you enter "Interactive Mode." You can manually change the thickness of any layer, and the tool recalculates the physics instantly. This is useful for "What-If" scenarios.

---

## 3. Understanding the Results

When you run the tool, you will see a final result that might look surprising:
**Total LCA: -50.63 kg CO2-eq/m²**

### Why is the value negative?

A negative LCA value indicates a **Climate Positive** wall. This happens because of two specific layers:

1. **Layer 3 (Cellulose Insulation):** Made from recycled paper/plant fiber.
2. **Layer 7 (Wood Battens):** Made from timber.

**The Science:** Trees absorb  from the atmosphere as they grow. When we use wood in construction, we are effectively storing that carbon in the building. In LCA methodology (A1-A3), this stored carbon is counted as a negative emission.
In this optimized wall, the carbon stored in the wood layers is greater than the carbon emitted by manufacturing the concrete and steel layers.

### Verification (Trust but Verify)

To ensure these results aren't a glitch, a separate script `validation.py` was created. It essentially performs a manual "napkin math" check on the final output.

* It verified the U-value matches the ISO formula to 4 decimal places.
* It confirmed the negative LCA matches the input data provided in the JSON files.

---

## 4. Key Design Decisions

During development, several engineering decisions were made:

1. **Discrete vs. Continuous:** We treat thickness as a "Discrete" choice (selecting from a list of 50mm, 100mm, etc.) rather than "Continuous" (allowing any number like 50.123mm). This matches how materials are actually sold in the real world.
2. **Handling "Ghost" Materials:** Layer 4 contained materials with `Factor: 0.0`. We decided to keep these in the calculation but honor the factor. This means they contribute thermal insulation (R-value) but have zero environmental impact in the LCA calculation.
3. **The "Tonne" Fix:** Layer 5 data used "Tonnes" as a unit. We normalized this to "kg" immediately to prevent a "Order of Magnitude" error (where a result is 1000x too small).

## 5. Summary

This tool is not just a calculator; it is a decision-support system. It filters out inefficient choices and presents the architect with the mathematically optimal solution for a sustainable, high-performance wall assembly.