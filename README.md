# Wall Assembly LCA Optimizer

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Complete-success)

## 📌 Overview

The **Wall Assembly LCA Optimizer** is a specialized Command-Line Interface (CLI) tool designed for architectural technologists and engineers. It automates the material selection process for a complex 9-layer wall assembly, finding the mathematically optimal combination that minimizes **Life Cycle Assessment (LCA) Impact** (Global Warming Potential) while strictly adhering to **Thermal Transmittance (U-Value)** targets.

By leveraging **Pareto Optimization** and a **Divide & Conquer** algorithm, this tool processes millions of potential material combinations in under **10 milliseconds**, delivering a climate-positive solution without relying on brute-force guesswork.

---

## 🚀 Key Features

- **Multi-Constraint Optimization:** Minimizes GWP (A1-A3) while maintaining a U-Value of $0.14\ W/(m^2K) \pm 10\%$.
- **High-Performance Algorithm:** Uses Pareto Pruning to reduce the search space from ~2 million combinations to a few thousand efficient candidates.
- **Automatic Fallback Handling:** Some materials have empty `thickness_range` arrays in the data files. The tool automatically uses `thickness_init` as a single option in these cases, ensuring all layers remain optimizable.
- **ISO Standard Compliance:** Physics engine is built on **ISO 6946** standards for thermal resistance and transmittance calculations.
- **Data Sanitization:** Robust data loader handles inconsistent input units (`m3`, `m2`, `kg`, `Tonne`), detects missing thermal properties (foils), and normalizes data automatically.
- **Interactive Design Studio:** After optimization, users can enter an interactive mode to manually tweak layer thicknesses and see real-time physics updates.

---

## 📂 Project Structure

| File             | Description                                                                                                                                                                      |
| :--------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`        | **The Entry Point.** Orchestrates the data loading, optimization, and interactive CLI loop.                                                                                      |
| `optimizer.py`   | **The Engine.** Implements the Pareto Pruning and Divide & Conquer algorithms to find the global minimum.                                                                        |
| `physics.py`     | **The Law.** Contains the pure functions for calculating R-values, U-values, and LCA impacts based on unit types.                                                                |
| `data_loader.py` | **The Cleaner.** Parses raw JSON files, standardizes units (Tonne $\to$ kg), handles data anomalies (e.g., thin foils, empty thickness ranges), and applies automatic fallbacks. |
| `validation.py`  | **The Auditor.** A standalone test suite that performs manual "napkin math" verification to prove accuracy.                                                                      |
| `layers/`        | **The Data.** Directory containing the 9 JSON files representing the material database for each wall layer.                                                                      |

---

## 🛠️ Installation

### Prerequisites

- Python 3.8 or higher.

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/abbas-ahmad-cowlar/Wall-Assembly-LCA-Optimizer.git
    cd Wall-Assembly-LCA-Optimizer
    ```
2.  **Install dependencies:**

    ```bash
    pip install pandas
    ```

3.  **Verify Data:**
    The 9 JSON material files are located in the `layers/` directory and are automatically loaded by the tool.

---

## 💻 Usage

### 1. Run the Optimizer

Execute the main script to load data, run the optimization, and view the "Winning Wall."

```bash
python main.py

```

### 2. Interactive Mode

Once the optimal wall is found, the tool enters **Interactive Mode**.

- **View Status:** See the current U-Value and Total LCA in real-time.
- **Modify Layers:** Select any layer (0-8) to swap materials or change thickness.
- **Validate:** The tool automatically flags if your manual changes push the U-Value out of the target range ().

### 3. Verification (Optional)

To verify the mathematical accuracy of the tool against manual calculations:

```bash
python validation.py

```

_Expected Output:_ `PASS` on all ISO summation and edge-case stress tests.

---

## 🧠 Technical Logic

### The Combinatorial Problem

With 9 layers and roughly 5-15 options per layer, the brute-force search space is:

Calculating physics for 2 million walls linearly is inefficient.

### The Solution: Pareto Pruning

The optimizer filters candidates **per layer** before combination. A material option is discarded if another option exists in the same layer that is **both** a better insulator (Higher R) **and** has a lower environmental impact (Lower LCA).

> _Result:_ The search space is often reduced by 95% before the combination phase begins.

### The Physics: Negative LCA?

You may observe a **negative** Total LCA result (e.g., ).
This is mathematically valid and indicates a **Climate Positive** assembly.

- **Cause:** The optimization engine prioritizes bio-based materials (Cellulose Insulation, Wood Battens) which have negative GWP values due to biogenic carbon storage.
- **Result:** The carbon stored in the wood layers exceeds the carbon emitted during the production of the concrete/steel layers.

---
