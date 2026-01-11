import json
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional

# --- Configuration ---
DATA_FOLDER = "."  # Assumes JSON files are in the current directory
# Map filename prefixes to Layer IDs (0-8) to ensure correct order
LAYER_MAP = {
    "01": 0, "02": 1, "03": 2, "04": 3, "05": 4, 
    "06": 5, "07": 6, "08": 7, "09": 8
}

@dataclass
class Material:
    id: str
    name: str
    layer_index: int
    thickness_options: List[float]  # In METERS
    lambda_val: Optional[float]     # W/m.K
    u_val_ref: Optional[float]      # W/m2.K (Backup if lambda is missing)
    density: Optional[float]        # kg/m3
    lca_unit: str                   # 'm3', 'm2', 'kg'
    gwp_a1a3: float                 # Base Impact
    factor: float                   # Multiplier
    is_foil: bool = False           # Flag for thin layers

    def __repr__(self):
        return f"Mat(L{self.layer_index}, {self.name}, Unit={self.lca_unit})"

def load_data(folder_path: str) -> List[Material]:
    all_materials = []
    
    # Get all JSON files sorted
    files = sorted([f for f in os.listdir(folder_path) if f.endswith(".json")])
    
    print(f"Found {len(files)} JSON files. Processing...")
    
    for filename in files:
        prefix = filename[:2]
        if prefix not in LAYER_MAP:
            print(f"Skipping unknown file: {filename}")
            continue
            
        layer_idx = LAYER_MAP[prefix]
        filepath = os.path.join(folder_path, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"ERROR reading {filename}: {e}")
            continue

        # Navigate the messy JSON structure
        # Usually: Root -> "Components" -> LayerName -> Materials
        root_content = data.get("Components", {})
        if not root_content:
            print(f"WARNING: No 'Components' found in {filename}")
            continue
            
        # The next key is dynamic (e.g., "IfcWall", "Layer_06...", etc.)
        for category_key, materials_dict in root_content.items():
            for mat_name, props in materials_dict.items():
                
                # --- 1. Data Cleaning & Extraction ---
                
                # Handle Factor (Default to 1.0 if missing)
                factor = props.get("factor")
                if factor is None: factor = 1.0
                
                # Handle Unit Normalization (Tonne -> Kg)
                raw_unit = props.get("unit", "m2")
                a1a3_raw = props.get("A1-A3")
                
                # Handle Null GWP (treat as 0.0 but warn)
                if a1a3_raw is None:
                    # print(f"  [Warn] Null GWP for {mat_name} in {filename}")
                    a1a3_raw = 0.0
                
                final_unit = raw_unit
                final_gwp = float(a1a3_raw)

                if raw_unit == "tonne":
                    final_unit = "kg"
                    final_gwp = final_gwp * 1000.0 # Convert impact per tonne to per kg
                
                # Handle Thickness (Convert mm -> m)
                t_init_mm = props.get("thickness_init", 0)
                t_range_mm = props.get("thickness_range")
                
                # FALLBACK RULE: If range is empty/null, use init
                if not t_range_mm: 
                    t_range_mm = [t_init_mm]
                
                # Convert list to meters
                t_options_m = [float(t) / 1000.0 for t in t_range_mm]
                
                # Handle Thermal Properties
                lambda_val = props.get("lambda")
                u_val = props.get("u-value")
                
                # FOIL DETECTION RULE
                # If thickness < 1mm (0.001m) and Lambda is missing, flag as foil
                is_foil = False
                if t_options_m[0] < 0.001 and lambda_val is None:
                    is_foil = True
                
                # Create Object
                mat_obj = Material(
                    id=f"{layer_idx}_{mat_name[:10]}",
                    name=mat_name,
                    layer_index=layer_idx,
                    thickness_options=t_options_m,
                    lambda_val=lambda_val,
                    u_val_ref=u_val,
                    density=props.get("density"),
                    lca_unit=final_unit,
                    gwp_a1a3=final_gwp,
                    factor=float(factor),
                    is_foil=is_foil
                )
                all_materials.append(mat_obj)

    print(f"Successfully loaded {len(all_materials)} materials.")
    return all_materials

def generate_summary(materials: List[Material]):
    """Prints a clear summary table of what we loaded."""
    data_for_df = []
    for m in materials:
        # Just showing the first thickness option for brevity
        t_display = f"{m.thickness_options[0]:.3f}"
        if len(m.thickness_options) > 1:
            t_display += f" (+{len(m.thickness_options)-1} opts)"
            
        data_for_df.append({
            "Layer": m.layer_index,
            "Name": m.name,
            "Unit": m.lca_unit,
            "GWP(A1A3)": m.gwp_a1a3,
            "Factor": m.factor,
            "Lambda": m.lambda_val,
            "Thickness(m)": t_display,
            "Foil?": m.is_foil
        })
    
    df = pd.DataFrame(data_for_df)
    # Sort by Layer
    df = df.sort_values(by="Layer")
    
    print("\n--- Data Loading Summary (Phase 1) ---")
    print(df.to_string())
    print("-" * 60)
    
    # Validation Check: Do we have materials for all 9 layers?
    layers_found = df['Layer'].unique()
    missing = [i for i in range(9) if i not in layers_found]
    if missing:
        print(f"CRITICAL WARNING: Missing Layers: {missing}")
    else:
        print("SUCCESS: All 9 Layers have candidate materials.")

if __name__ == "__main__":
    # 1. Run Loader
    materials = load_data(DATA_FOLDER)
    
    # 2. Print Summary
    generate_summary(materials)
    
    # 3. Save for Phase 2 (Optional, but good for debugging)
    # pd.DataFrame([vars(m) for m in materials]).to_csv("debug_materials.csv", index=False)