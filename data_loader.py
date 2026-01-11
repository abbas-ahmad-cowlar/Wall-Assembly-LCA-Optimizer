"""Material data loader with normalization and validation.

This module handles loading material data from JSON files, applying data cleaning
rules, and creating Material objects for use in the optimization engine.

Key responsibilities:
- Parse JSON files from layers/ directory
- Normalize units (Tonne → kg)
- Handle empty thickness_range arrays
- Detect and flag thin foils
- Apply data validation rules
"""

import json
import os
import pathlib
import pandas as pd
import logging
from dataclasses import dataclass
from typing import List, Optional

from logging_config import get_logger

logger = get_logger(__name__)

# --- Configuration ---
# Resolve path relative to this file's location
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
DATA_FOLDER = SCRIPT_DIR / "layers"

# Map filename prefixes to Layer IDs (0-8) to ensure correct order
LAYER_MAP = {
    "01": 0, "02": 1, "03": 2, "04": 3, "05": 4, 
    "06": 5, "07": 6, "08": 7, "09": 8
}

@dataclass
class Material:
    """Represents a building material with thermal and environmental properties.
    
    Attributes:
        id: Unique identifier for the material
        name: Material name from database
        layer_index: Wall layer position (0-8, inside to outside)
        thickness_options: Available thicknesses in meters
        lambda_val: Thermal conductivity in W/(m·K)
        u_val_ref: Reference U-value in W/(m²K) (backup if lambda missing)
        density: Material density in kg/m³
        lca_unit: Unit basis for GWP ('m3', 'm2', or 'kg')
        gwp_a1a3: Global Warming Potential A1-A3 in kg CO2-eq/<unit>
        factor: Multiplier for LCA calculation
        is_foil: Flag indicating thin foil material (<1mm, no lambda)
    """
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


def load_data(folder_path=None) -> List[Material]:
    """Load and normalize material data from JSON files.
    
    Applies comprehensive data cleaning rules:
    - Converts Tonne units to kg (multiplies GWP by 1000)
    - Handles empty thickness_range arrays (uses thickness_init as fallback)
    - Detects and flags thin foils (thickness < 1mm with no lambda)
    - Normalizes null factors to 1.0
    - Validates data completeness
    
    Args:
        folder_path: Path to directory containing JSON files.
                    Defaults to layers/ directory adjacent to this script.
    
    Returns:
        List of Material objects representing all available materials
        across 9 wall layers.
    
    Raises:
        FileNotFoundError: If folder_path doesn't exist.
        ValueError: If no JSON files found or critical data is missing.
    
    Example:
        >>> materials = load_data()
        >>> print(f"Loaded {len(materials)} materials")
        Loaded 81 materials
    """
    if folder_path is None:
        folder_path = DATA_FOLDER
    
    logger.info(f"Loading material data from: {folder_path}")
    
    all_materials = []
    
    # Validate folder exists
    folder_path = pathlib.Path(folder_path)
    if not folder_path.exists():
        logger.error(f"Data folder not found: {folder_path}")
        raise FileNotFoundError(f"Data folder not found: {folder_path}")
    
    # Get all JSON files sorted
    try:
        files = sorted([f for f in os.listdir(str(folder_path)) if f.endswith(".json")])
    except Exception as e:
        logger.error(f"Error listing directory {folder_path}: {e}")
        raise
    
    if not files:
        logger.error(f"No JSON files found in {folder_path}")
        raise ValueError(f"No JSON files found in {folder_path}")
    
    logger.info(f"Found {len(files)} JSON files. Processing...")
    
    for filename in files:
        prefix = filename[:2]
        if prefix not in LAYER_MAP:
            logger.warning(f"Skipping unknown file: {filename}")
            continue
            
        layer_idx = LAYER_MAP[prefix]
        
        # Handle both string and Path objects
        if isinstance(folder_path, pathlib.Path):
            filepath = folder_path / filename
        else:
            filepath = os.path.join(folder_path, filename)
        
        try:
            with open(str(filepath), 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Successfully read {filename}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filename}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}", exc_info=True)
            continue

        # Navigate the JSON structure
        root_content = data.get("Components", {})
        if not root_content:
            logger.warning(f"No 'Components' found in {filename}")
            continue
            
        # Process each material in the layer
        materials_in_layer = 0
        for category_key, materials_dict in root_content.items():
            for mat_name, props in materials_dict.items():
                
                try:
                    material = _parse_material(mat_name, props, layer_idx)
                    all_materials.append(material)
                    materials_in_layer += 1
                except Exception as e:
                    logger.error(f"Error parsing material '{mat_name}' in {filename}: {e}")
                    continue
        
        logger.debug(f"Layer {layer_idx} ({filename}): Loaded {materials_in_layer} materials")

    logger.info(f"Successfully loaded {len(all_materials)} materials across {len(files)} layers")
    return all_materials


def _parse_material(mat_name: str, props: dict, layer_idx: int) -> Material:
    """Parse a single material from JSON properties.
    
    Args:
        mat_name: Material name from JSON
        props: Material properties dictionary
        layer_idx: Layer index (0-8)
    
    Returns:
        Material object
        
    Raises:
        ValueError: If critical properties are missing
    """
    # Handle Factor (Default to 1.0 if missing)
    factor = props.get("factor")
    if factor is None:
        logger.debug(f"Material '{mat_name}' has null factor, defaulting to 1.0")
        factor = 1.0
    
    # Handle Unit Normalization (Tonne → Kg)
    raw_unit = props.get("unit", "m2")
    a1a3_raw = props.get("A1-A3")
    
    # Handle Null GWP (treat as 0.0)
    if a1a3_raw is None:
        logger.debug(f"Material '{mat_name}' has null GWP, defaulting to 0.0")
        a1a3_raw = 0.0
    
    final_unit = raw_unit
    final_gwp = float(a1a3_raw)

    if raw_unit == "tonne":
        logger.debug(f"Converting '{mat_name}' from tonne to kg")
        final_unit = "kg"
        final_gwp = final_gwp * 1000.0  # Convert impact per tonne to per kg
    
    # Handle Thickness (Convert mm → m)
    t_init_mm = props.get("thickness_init", 0)
    t_range_mm = props.get("thickness_range")
    
    # FALLBACK RULE: If range is empty/null, use init
    if not t_range_mm:
        logger.debug(f"Material '{mat_name}' has empty thickness_range, using thickness_init={t_init_mm}mm")
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
        logger.debug(f"Material '{mat_name}' detected as foil (thin + no lambda)")
        is_foil = True
    
    # Create Material object
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
    
    return mat_obj


def generate_summary(materials: List[Material]) -> None:
    """Print a summary table of loaded materials.
    
    Args:
        materials: List of Material objects to summarize
    """
    logger.info("Generating material summary...")
    
    data_for_df = []
    for m in materials:
        # Show first thickness option
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
    df = df.sort_values(by="Layer")
    
    print("\n--- Data Loading Summary ---")
    print(df.to_string())
    print("-" * 60)
    
    # Validation Check: Do we have materials for all 9 layers?
    layers_found = df['Layer'].unique()
    missing = [i for i in range(9) if i not in layers_found]
    if missing:
        logger.error(f"CRITICAL: Missing materials for layers: {missing}")
        print(f"CRITICAL WARNING: Missing Layers: {missing}")
    else:
        logger.info("SUCCESS: All 9 layers have candidate materials")
        print("SUCCESS: All 9 Layers have candidate materials.")


if __name__ == "__main__":
    # Set up logging for standalone execution
    from logging_config import setup_logging
    setup_logging(log_level=logging.INFO)
    
    # Run Loader
    materials = load_data(DATA_FOLDER)
    
    # Print Summary
    generate_summary(materials)