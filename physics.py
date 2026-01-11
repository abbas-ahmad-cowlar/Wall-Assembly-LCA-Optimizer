"""Building physics calculations following ISO 6946 standards.

This module implements thermal and environmental performance calculations
for wall assemblies, including:
- Thermal resistance (R-value) calculations
- U-value (thermal transmittance) calculations  
- Life Cycle Assessment (LCA) impact calculations

All thermal calculations comply with ISO 6946 standard for building components.
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple
from data_loader import Material
from logging_config import get_logger

logger = get_logger(__name__)

# --- ISO 6946 Surface Resistance Constants ---
R_SI = 0.13  # Interior surface resistance (m²K/W)
R_SE = 0.04  # Exterior surface resistance (m²K/W)


@dataclass
class WallAssembly:
    """Represents a complete wall assembly with 9 material layers.
    
    This class encapsulates thermal and environmental calculations for
    a specific combination of materials and thicknesses.
    
    Attributes:
        layers: List of (Material, thickness) tuples representing each layer.
               Thickness is in meters. Should contain exactly 9 layers for
               a complete wall assembly (inside to outside).
    
    Example:
        >>> wall = WallAssembly(layers=[
        ...     (gypsum_material, 0.0125),  # Layer 0: 12.5mm gypsum
        ...     (foil_material, 0.0002),    # Layer 1: 0.2mm foil
        ...     # ... 7 more layers
        ... ])
        >>> u_value = wall.calculate_u_value()
        >>> lca = wall.calculate_total_lca()
    """
    layers: List[Tuple[Material, float]]  # List of (Material, thickness_in_meters)

    def calculate_r_value(self, material: Material, thickness_m: float) -> float:
        """Calculate thermal resistance for a single layer.
        
        Implements ISO 6946 formula: R = d/λ where:
        - d = thickness in meters
        - λ = thermal conductivity in W/(m·K)
        
        Special cases:
        1. Foils (thin materials <1mm with no lambda): R ≈ 0
        2. Missing lambda with U-ref available: R = 1/U
        3. No thermal data: R = 0 (shouldn't occur with validated data)
        
        Args:
            material: Material object with thermal properties
            thickness_m: Layer thickness in meters
        
        Returns:
            Thermal resistance in m²K/W
            
        Note:
            For foils, returns 0.0001 instead of 0 to avoid division by zero
            in downstream calculations.
        """
        if material.is_foil:
            logger.debug(f"Foil material '{material.name}': R ≈ 0")
            return 0.0001  # Negligible resistance
        
        if material.lambda_val:
            r_value = thickness_m / material.lambda_val
            logger.debug(f"Material '{material.name}': R = {thickness_m}/{material.lambda_val} = {r_value:.4f}")
            return r_value
            
        if material.u_val_ref:
            r_value = 1.0 / material.u_val_ref
            logger.debug(f"Material '{material.name}': Using U-ref, R = 1/{material.u_val_ref} = {r_value:.4f}")
            return r_value
        
        logger.warning(f"Material '{material.name}' has no thermal data, assuming R = 0")
        return 0.0

    def calculate_u_value(self) -> float:
        """Calculate total U-value (thermal transmittance) of the assembly.
        
        Implements ISO 6946 formula:
        U = 1 / (R_si + ΣR_layers + R_se)
        
        Where:
        - R_si = 0.13 m²K/W (interior surface resistance)
        - R_se = 0.04 m²K/W (exterior surface resistance)
        - ΣR_layers = sum of all material layer resistances
        
        Returns:
            U-value in W/(m²K). Lower values indicate better insulation.
        
        Example:
            >>> wall.calculate_u_value()
            0.1475  # W/(m²K) - good insulation
        """
        r_sum = sum(self.calculate_r_value(m, t) for m, t in self.layers)
        r_total = R_SI + r_sum + R_SE
        u_value = 1.0 / r_total
        
        logger.debug(f"U-value calculation: R_total = {R_SI} + {r_sum:.3f} + {R_SE} = {r_total:.3f}")
        logger.debug(f"U-value = 1/{r_total:.3f} = {u_value:.4f} W/(m²K)")
        
        return u_value

    def calculate_layer_lca(self, material: Material, thickness_m: float) -> float:
        """Calculate Life Cycle Assessment (A1-A3 GWP) for a single layer.
        
        Calculates environmental impact based on material unit basis.
        All formulas multiply by material.factor.
        
        Formulas:
        1. Volume basis (m³): Impact = GWP × thickness × factor
        2. Area basis (m²):   Impact = GWP × factor
        3. Mass basis (kg):   Impact = GWP × density × thickness × factor
        
        Where:
        - GWP = Global Warming Potential in kg CO₂-eq/<unit>
        - thickness is in meters
        - density is in kg/m³
        - factor is a material-specific multiplier
        
        Args:
            material: Material object with LCA properties
            thickness_m: Layer thickness in meters
        
        Returns:
            LCA impact in kg CO₂-eq/m² (per square meter of wall)
            
        Note:
            Negative values indicate biogenic carbon storage (e.g., wood products).
            Zero impact occurs when factor = 0.0 (material excluded from LCA).
        """
        base_impact = 0.0
        
        if material.lca_unit == 'm3':
            # Impact per cubic meter
            base_impact = material.gwp_a1a3 * thickness_m
            logger.debug(
                f"LCA (m³): {material.name} = {material.gwp_a1a3} × {thickness_m} = {base_impact:.3f}"
            )
            
        elif material.lca_unit == 'm2':
            # Impact per square meter (thickness independent)
            base_impact = material.gwp_a1a3 * 1.0
            logger.debug(f"LCA (m²): {material.name} = {material.gwp_a1a3:.3f}")
            
        elif material.lca_unit == 'kg':
            # Impact per kilogram
            if material.density:
                mass_kg = material.density * thickness_m
                base_impact = material.gwp_a1a3 * mass_kg
                logger.debug(
                    f"LCA (kg): {material.name} = {material.gwp_a1a3} × {material.density} × {thickness_m} = {base_impact:.3f}"
                )
            else:
                logger.warning(f"Missing density for kg-based material '{material.name}', impact = 0")
                base_impact = 0.0
        
        final_impact = base_impact * material.factor
        
        if material.factor != 1.0:
            logger.debug(f"Applying factor {material.factor}: {base_impact:.3f} × {material.factor} = {final_impact:.3f}")
                
        return final_impact

    def calculate_total_lca(self) -> float:
        """Calculate total LCA impact for the complete wall assembly.
        
        Sums A1-A3 GWP impacts across all 9 layers.
        
        Returns:
            Total LCA impact in kg CO₂-eq/m²
            
        Note:
            Negative total indicates a climate-positive wall assembly where
            biogenic carbon storage (wood, cellulose) exceeds manufacturing
            emissions.
        """
        total = sum(self.calculate_layer_lca(m, t) for m, t in self.layers)
        logger.debug(f"Total LCA: {total:.4f} kg CO₂-eq/m²")
        return total


# --- Unit Testing Suite ---
if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging(logging.INFO)
    
    logger.info("=== Running Physics Verification Tests ===")

    # TEST CASE 1: Standard Material (StoneWool)
    # Lambda=0.038, d=0.1m, R should be 2.63
    mat_standard = Material(
        id="test1", name="StoneWool", layer_index=1, thickness_options=[0.1],
        lambda_val=0.038, u_val_ref=None, density=50, lca_unit="m3",
        gwp_a1a3=10.0, factor=1.0, is_foil=False
    )
    
    wall_1 = WallAssembly(layers=[(mat_standard, 0.1)])
    r_val = wall_1.calculate_r_value(mat_standard, 0.1)
    result_1 = 'PASS' if abs(r_val - 2.6315) < 0.01 else 'FAIL'
    logger.info(f"Test 1 (Standard R): Expected ~2.631 | Got {r_val:.4f} → {result_1}")

    # TEST CASE 2: LCA with kg unit (Tonne conversion check)
    # Density=1000 kg/m3, d=0.1m, Mass=100kg, GWP=0.1, Impact should be 10.0
    mat_tonne = Material(
        id="test2", name="ConcreteBlock", layer_index=1, thickness_options=[0.1],
        lambda_val=0.5, u_val_ref=None, density=1000, lca_unit="kg",
        gwp_a1a3=0.1, factor=1.0, is_foil=False 
    )
    
    wall_2 = WallAssembly(layers=[(mat_tonne, 0.1)])
    lca_val = wall_2.calculate_layer_lca(mat_tonne, 0.1)
    result_2 = 'PASS' if abs(lca_val - 10.0) < 0.01 else 'FAIL'
    logger.info(f"Test 2 (Kg/Tonne LCA): Expected 10.0 | Got {lca_val:.4f} → {result_2}")

    # TEST CASE 3: Foil Handling
    # Thickness small, is_foil=True, R should be ~0
    mat_foil = Material(
        id="test3", name="Foil", layer_index=1, thickness_options=[0.0002],
        lambda_val=None, u_val_ref=None, density=None, lca_unit="m2",
        gwp_a1a3=5.0, factor=1.0, is_foil=True
    )
    r_foil = wall_1.calculate_r_value(mat_foil, 0.0002)
    result_3 = 'PASS' if r_foil < 0.001 else 'FAIL'
    logger.info(f"Test 3 (Foil R): Expected ~0.0 | Got {r_foil:.4f} → {result_3}")

    # TEST CASE 4: Factor Multiplier
    # Factor = 0.5, Base Impact = 1.0, Total should be 0.5
    mat_factor = Material(
        id="test4", name="FactorTest", layer_index=1, thickness_options=[0.1],
        lambda_val=0.038, u_val_ref=None, density=50, lca_unit="m3",
        gwp_a1a3=10.0, factor=0.5, is_foil=False
    )
    wall_4 = WallAssembly(layers=[(mat_factor, 0.1)])
    lca_factor = wall_4.calculate_layer_lca(mat_factor, 0.1)
    result_4 = 'PASS' if abs(lca_factor - 0.5) < 0.01 else 'FAIL'
    logger.info(f"Test 4 (Factor): Expected 0.50 | Got {lca_factor:.4f} → {result_4}")
    
    all_passed = all([result_1 == 'PASS', result_2 == 'PASS', result_3 == 'PASS', result_4 == 'PASS'])
    
    if all_passed:
        logger.info("=== ALL TESTS PASSED ===")
    else:
        logger.error("=== SOME TESTS FAILED ===")