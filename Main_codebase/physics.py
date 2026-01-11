from dataclasses import dataclass
from typing import List
from data_loader import Material

# --- Constants ---
R_SI = 0.13  # Interior Surface Resistance
R_SE = 0.04  # Exterior Surface Resistance

@dataclass
class WallAssembly:
    """
    Represents a specific combination of 9 materials and their chosen thicknesses.
    """
    layers: List[tuple[Material, float]]  # List of (Material, thickness_in_meters)

    def calculate_r_value(self, material: Material, thickness_m: float) -> float:
        """
        Calculates R-value for a single layer.
        Rule 1: If it's a foil (thin, no lambda), R is negligible (~0).
        Rule 2: If lambda is present, R = d / lambda.
        Rule 3: If lambda is missing but U-ref exists (unlikely in this dataset but safe), R = 1/U.
        """
        if material.is_foil:
            return 0.0001  # Negligible resistance, but not zero to avoid div/0 errors elsewhere
        
        if material.lambda_val:
            return thickness_m / material.lambda_val
            
        if material.u_val_ref:
            return 1.0 / material.u_val_ref
            
        return 0.0 # Should not happen with clean data

    def calculate_u_value(self) -> float:
        """
        Calculates total U-value of the assembly.
        U = 1 / (Rsi + Sum(R_layers) + Rse)
        """
        r_sum = sum(self.calculate_r_value(m, t) for m, t in self.layers)
        r_total = R_SI + r_sum + R_SE
        return 1.0 / r_total

    def calculate_layer_lca(self, material: Material, thickness_m: float) -> float:
        """
        Calculates LCA (A1-A3 GWP) for a single layer.
        Formulas (After Phase 1 Normalization):
        1. Unit=m3: GWP * thickness * factor
        2. Unit=m2: GWP * 1 * factor
        3. Unit=kg: GWP * density * thickness * factor
        """
        base_impact = 0.0
        
        if material.lca_unit == 'm3':
            # Impact is per cubic meter
            base_impact = material.gwp_a1a3 * thickness_m
            
        elif material.lca_unit == 'm2':
            # Impact is per square meter (thickness independent)
            base_impact = material.gwp_a1a3 * 1.0
            
        elif material.lca_unit == 'kg':
            # Impact is per kg. Need mass = density * thickness * 1m2
            if material.density:
                mass_kg = material.density * thickness_m
                base_impact = material.gwp_a1a3 * mass_kg
            else:
                # Should not happen if data is valid
                print(f"WARNING: Missing density for kg-based material {material.name}")
                base_impact = 0.0
                
        return base_impact * material.factor

    def calculate_total_lca(self) -> float:
        """Sum of LCA impacts for all 9 layers."""
        return sum(self.calculate_layer_lca(m, t) for m, t in self.layers)


# --- Unit Testing Suite ---
if __name__ == "__main__":
    print("--- Running Physics Verification Tests ---")

    # TEST CASE 1: Standard Material (StoneWool)
    # Lambda=0.038, d=0.1m, R should be 2.63
    mat_standard = Material(
        id="test1", name="StoneWool", layer_index=1, thickness_options=[0.1],
        lambda_val=0.038, u_val_ref=None, density=50, lca_unit="m3",
        gwp_a1a3=10.0, factor=1.0, is_foil=False
    )
    
    wall_1 = WallAssembly(layers=[(mat_standard, 0.1)])
    r_val = wall_1.calculate_r_value(mat_standard, 0.1)
    print(f"Test 1 (Standard R): Expected ~2.631 | Got {r_val:.4f} -> {'PASS' if abs(r_val - 2.6315) < 0.01 else 'FAIL'}")

    # TEST CASE 2: The "Tonne" Conversion Check
    # Input was 100 kgCO2/tonne -> Phase 1 converted to 0.1 kgCO2/kg
    # Let's say density=1000 kg/m3, d=0.1m. Mass=100kg. Impact should be 0.1 * 100 = 10.
    mat_tonne = Material(
        id="test2", name="ConcreteBlock", layer_index=1, thickness_options=[0.1],
        lambda_val=0.5, u_val_ref=None, density=1000, lca_unit="kg",
        gwp_a1a3=0.1, factor=1.0, is_foil=False 
    )
    
    wall_2 = WallAssembly(layers=[(mat_tonne, 0.1)])
    lca_val = wall_2.calculate_layer_lca(mat_tonne, 0.1)
    print(f"Test 2 (Kg/Tonne LCA): Expected 10.0 | Got {lca_val:.4f} -> {'PASS' if abs(lca_val - 10.0) < 0.01 else 'FAIL'}")

    # TEST CASE 3: Foil Handling
    # Thickness small, is_foil=True. R should be ~0.
    mat_foil = Material(
        id="test3", name="Foil", layer_index=1, thickness_options=[0.0002],
        lambda_val=None, u_val_ref=None, density=None, lca_unit="m2",
        gwp_a1a3=5.0, factor=1.0, is_foil=True
    )
    r_foil = wall_1.calculate_r_value(mat_foil, 0.0002)
    print(f"Test 3 (Foil R): Expected ~0.0 | Got {r_foil:.4f} -> {'PASS' if r_foil < 0.001 else 'FAIL'}")

    # TEST CASE 4: Factor Multiplier
    # Factor = 0.5. Base Impact = 10. Total should be 5.
    mat_factor = Material(
        id="test4", name="FactorTest", layer_index=1, thickness_options=[0.1],
        lambda_val=0.038, u_val_ref=None, density=50, lca_unit="m3",
        gwp_a1a3=10.0, factor=0.5, is_foil=False
    )
    wall_4 = WallAssembly(layers=[(mat_factor, 0.1)])
    lca_factor = wall_4.calculate_layer_lca(mat_factor, 0.1)
    print(f"Test 4 (Factor): Expected 0.50 | Got {lca_factor:.4f} -> {'PASS' if abs(lca_factor - 0.5) < 0.01 else 'FAIL'}")

    print("------------------------------------------")