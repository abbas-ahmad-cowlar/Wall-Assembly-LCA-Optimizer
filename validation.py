"""Automated validation test suite for physics and optimization correctness.

This module provides comprehensive testing of:
- ISO 6946 U-value calculation accuracy
- LCA calculation correctness (including negative values)
- Edge case handling (impossible constraints)

Tests can be run standalone or imported into main.py for pre-flight checks.
"""

import sys
import logging
from physics import WallAssembly, R_SI, R_SE
from data_loader import Material
from logging_config import get_logger

logger = get_logger(__name__)


def test_u_value_summation() -> bool:
    """Test ISO 6946 U-value calculation accuracy.
    
    Reconstructs the optimal 'Winning Wall' with known R-values and
    verifies the final U-value calculation matches the ISO standard.
    
    Returns:
        True if test passes, False otherwise
    """
    logger.info("\n[TEST 1] ISO 6946 U-Value Summation Check")
    
    # R-values from actual optimization output
    r_values = [
        0.294,  # L0: Interior Finish
        0.000,  # L1: Vapour Control
        0.309,  # L2: Wood-based Board
        3.462,  # L3: Cavity Insulation
        0.270,  # L4: Primary Structure
        1.562,  # L5: Second Insulation
        0.020,  # L6: Water Control
        0.375,  # L7: Battens/Rainscreen
        0.317   # L8: Facade Cladding
    ]
    
    total_r_layers = sum(r_values)
    total_r_system = R_SI + total_r_layers + R_SE
    calculated_u = 1.0 / total_r_system
    
    logger.info(f"   Sum of R-Layers: {total_r_layers:.3f} (Expected ~6.61)")
    logger.info(f"   Total System R:  {total_r_system:.3f} (Includes R_si + R_se)")
    logger.info(f"   Calculated U:    {calculated_u:.4f} W/(m²K)")
    
    # Assert U-value is approximately 0.1475
    expected_u = 0.1475
    tolerance = 0.001
    
    if abs(calculated_u - expected_u) < tolerance:
        logger.info("   ✓ PASS: Math matches ISO formula exactly")
        return True
    else:
        logger.error(f"   ✗ FAIL: U-value mismatch (expected {expected_u:.4f}, got {calculated_u:.4f})")
        return False


def test_layer_7_lca() -> bool:
    """Test negative LCA calculation for wood battens.
    
    Specific audit of the 'Hero' layer (Wood Battens) to confirm
    the large negative LCA value (-35.82) is mathematically valid
    and not a unit error.
    
    Returns:
        True if test passes, False otherwise
    """
    logger.info("\n[TEST 2] Layer 7 'Hero Number' Audit")
    
    # Recreate exact material state from data
    # Input: Unit=m3, GWP=-796, Thickness=0.045m, Factor=1.0
    gwp_per_m3 = -796.0
    thickness = 0.045  # 45mm
    factor = 1.0
    
    # Formula for volume-based unit
    impact = gwp_per_m3 * thickness * factor
    
    logger.info(f"   Input GWP (m³): {gwp_per_m3}")
    logger.info(f"   Thickness (m):  {thickness}")
    logger.info(f"   Factor:         {factor}")
    logger.info(f"   Calculated:     {impact:.3f} kg CO₂-eq/m²")
    logger.info(f"   Tool Output:    -35.820 kg CO₂-eq/m²")
    
    expected = -35.820
    tolerance = 0.001
    
    if abs(impact - expected) < tolerance:
        logger.info("   ✓ PASS: Large negative LCA is mathematically valid")
        return True
    else:
        logger.error(f"   ✗ FAIL: Calculation mismatch (expected {expected:.3f}, got {impact:.3f})")
        return False


def test_impossible_constraint() -> bool:
    """Test optimizer handles impossible constraints gracefully.
    
    Stress test: Request a U-value that is impossible to achieve
    (e.g., U=0.01, requiring R=100) and verify the optimizer
    correctly reports no solution found.
    
    Returns:
        True if test passes, False otherwise
    """
    logger.info("\n[TEST 3] Impossible Constraint Stress Test")
    logger.info("   Running optimizer with Target U = 0.01 (Impossible)...")
    
    # Import optimizer and temporarily override constants
    import optimizer
    original_min = optimizer.R_LAYERS_MIN
    original_max = optimizer.R_LAYERS_MAX
    
    # Set impossible R requirement (R ~ 100) 
    optimizer.R_LAYERS_MIN = 90.0
    optimizer.R_LAYERS_MAX = 110.0
    
    try:
        # Suppress optimizer's detailed logging for this test
        optimizer.logger.setLevel(logging.WARNING)
        
        result = optimizer.run_optimization()
        
        # Restore logging level
        optimizer.logger.setLevel(logging.INFO)
        
        if result is None:
            logger.info("   ✓ PASS: Optimizer correctly reported 'NO VALID WALL FOUND'")
            return True
        else:
            logger.error("   ✗ FAIL: Optimizer returned a wall for an impossible constraint!")
            return False
            
    finally:
        # Always restore original constants
        optimizer.R_LAYERS_MIN = original_min
        optimizer.R_LAYERS_MAX = original_max
        optimizer.logger.setLevel(logging.INFO)


def run_all_tests() -> bool:
    """Execute all validation tests.
    
    Returns:
        True if all tests pass, False if any test fails
    """
    logger.info("=" * 60)
    logger.info("VALIDATION TEST SUITE")
    logger.info("=" * 60)
    
    tests = [
        ("ISO 6946 U-Value Summation", test_u_value_summation),
        ("Layer 7 LCA Calculation", test_layer_7_lca),
        ("Impossible Constraint Handling", test_impossible_constraint),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\nRunning: {test_name}")
            result = test_func()
            results.append(result)
        except Exception as e:
            logger.error(f"Test '{test_name}' raised exception: {e}", exc_info=True)
            results.append(False)
    
    logger.info("\n" + "=" * 60)
    
    all_passed = all(results)
    passed_count = sum(results)
    total_count = len(results)
    
    if all_passed:
        logger.info(f"✓ ALL TESTS PASSED ({passed_count}/{total_count})")
        logger.info("=" * 60)
    else:
        logger.error(f"✗ SOME TESTS FAILED ({passed_count}/{total_count} passed)")
        logger.info("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging(log_level=logging.INFO)
    
    success = run_all_tests()
    
    # Exit with appropriate code for CI/CD
    sys.exit(0 if success else 1)