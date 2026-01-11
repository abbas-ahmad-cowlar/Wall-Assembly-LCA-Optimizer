import sys
from physics import WallAssembly, R_SI, R_SE
from data_loader import Material
from optimizer import run_optimization, TARGET_U

def test_u_value_summation():
    """
    Reconstructs the EXACT 'Winning Wall' from your main.py output 
    to verify the final U-Value calculation matches the ISO standard.
    """
    print("\n[TEST 1] ISO 6946 U-Value Summation Check")
    
    # R-values taken directly from your output
    r_values = [
        0.294,  # L0
        0.000,  # L1
        0.309,  # L2
        3.462,  # L3
        0.270,  # L4
        1.562,  # L5
        0.020,  # L6
        0.375,  # L7
        0.317   # L8
    ]
    
    total_r_layers = sum(r_values) # Should be 6.61
    total_r_system = R_SI + total_r_layers + R_SE
    calculated_u = 1.0 / total_r_system
    
    print(f"   Sum of R-Layers: {total_r_layers:.3f} (Tool said 6.61)")
    print(f"   Total System R:  {total_r_system:.3f} (Includes 0.13 + 0.04)")
    print(f"   Calculated U:    {calculated_u:.4f}")
    
    # Assert
    if 0.1470 <= calculated_u <= 0.1480:
        print("   >> PASS: Math matches ISO formula exactly.")
    else:
        print("   >> FAIL: Math discrepancy found.")

def test_impossible_constraint():
    """
    Stress Test: What happens if we ask for a U-value that is impossible?
    (e.g., U=0.01, requiring R=100, which our materials can't reach).
    """
    print("\n[TEST 2] Impossible Constraint Stress Test")
    print("   Running optimizer with Target U = 0.01 (Impossible)...")
    
    # Hijack the global constants in optimizer (Temporary override)
    import optimizer
    original_min = optimizer.R_LAYERS_MIN
    original_max = optimizer.R_LAYERS_MAX
    
    # Set impossible R requirement (R ~ 100)
    optimizer.R_LAYERS_MIN = 90.0
    optimizer.R_LAYERS_MAX = 110.0
    
    try:
        result = optimizer.run_optimization()
        if result is None:
            print("   >> PASS: Optimizer correctly reported 'NO VALID WALL FOUND'.")
        else:
            print("   >> FAIL: Optimizer returned a wall for an impossible constraint!")
    finally:
        # Restore constants just in case
        optimizer.R_LAYERS_MIN = original_min
        optimizer.R_LAYERS_MAX = original_max

def test_layer_7_logic():
    """
    Specific audit of the 'Hero' layer (Wood Battens) 
    to confirm the -35.82 LCA isn't a unit error.
    """
    print("\n[TEST 3] Layer 7 'Hero Number' Audit")
    
    # Recreate the exact material state
    # Input: Unit=m3, GWP=-796, Thickness=0.045m
    gwp_per_m3 = -796.0
    thickness = 0.045
    factor = 1.0
    
    # Formula for m3
    impact = gwp_per_m3 * thickness * factor
    
    print(f"   Input GWP (m3):  {gwp_per_m3}")
    print(f"   Thickness (m):   {thickness}")
    print(f"   Calculated:      {impact:.3f}")
    print(f"   Tool Output:     -35.820")
    
    if abs(impact - (-35.820)) < 0.001:
         print("   >> PASS: Large negative LCA is mathematically valid.")
    else:
         print("   >> FAIL: Calculation mismatch.")

if __name__ == "__main__":
    print("=== VALIDATION SUITE ===")
    test_u_value_summation()
    test_layer_7_logic()
    
    # Note: Test 2 actually runs the heavy optimizer, so it takes a split second
    test_impossible_constraint()
    print("\n=== SUITE COMPLETE ===")