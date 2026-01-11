"""Optimization engine using Pareto pruning and divide-and-conquer strategy.

This module implements a two-phase optimization approach to find wall assemblies
that minimize environmental impact (LCA) while meeting thermal performance (U-value)
constraints.

Algorithm Overview:
1. **Pareto Pruning**: Eliminates dominated material options per layer
2. **Divide & Conquer**: Splits wall into inner/outer halves for efficient combination
3. **Constraint Filtering**: Retains only assemblies meeting U-value target

Performance: Processes ~2 million potential combinations in ~100ms by reducing
search space to ~5,000 efficient candidates through Pareto optimization.
"""

import time
import itertools
import logging
from typing import List, Tuple, Dict
from dataclasses import dataclass
from data_loader import load_data, Material
from physics import WallAssembly, R_SI, R_SE
from logging_config import get_logger

logger = get_logger(__name__)

# --- Configuration ---
TARGET_U = 0.14  # W/(m²K) - Target U-value
TOLERANCE = 0.10  # ±10% tolerance
U_MIN = TARGET_U * (1 - TOLERANCE)  # 0.126
U_MAX = TARGET_U * (1 + TOLERANCE)  # 0.154

# Target R-Value Range (Inverse of U)
# U = 1 / R_total  =>  R_total = 1 / U
R_TOTAL_MIN = 1.0 / U_MAX  # ~6.49 m²K/W
R_TOTAL_MAX = 1.0 / U_MIN  # ~7.93 m²K/W

# Required sum of layer resistances (excluding surface resistances)
R_LAYERS_MIN = R_TOTAL_MIN - R_SI - R_SE  # ~6.32 m²K/W
R_LAYERS_MAX = R_TOTAL_MAX - R_SI - R_SE  # ~7.76 m²K/W

logger.info(f"Optimizer configured: Target U={TARGET_U} ±{TOLERANCE*100}%")
logger.info(f"  U-value range: {U_MIN:.3f} - {U_MAX:.3f} W/(m²K)")
logger.info(f"  R-layers range: {R_LAYERS_MIN:.2f} - {R_LAYERS_MAX:.2f} m²K/W")


@dataclass
class Candidate:
    """Represents a single layer option with computed performance metrics.
    
    A Candidate combines a specific material with a chosen thickness,
    along with precomputed thermal (R-value) and environmental (LCA) metrics.
    
    Attributes:
        material: The Material object
        thickness: Selected thickness in meters
        r_val: Computed thermal resistance in m²K/W
        lca_val: Computed LCA impact in kg CO₂-eq/m²
    
    Example:
        >>> candidate = Candidate(
        ...     material=cellulose_material,
        ...     thickness=0.100,  # 100mm
        ...     r_val=3.462,
        ...     lca_val=-8.25
        ... )
    """
    material: Material
    thickness: float
    r_val: float
    lca_val: float

    def __repr__(self):
        return f"<{self.material.name[:10]}... t={self.thickness:.3f} R={self.r_val:.2f} LCA={self.lca_val:.2f}>"


def get_layer_candidates(materials: List[Material]) -> Dict[int, List[Candidate]]:
    """Generate Pareto-efficient candidates for each layer.
    
    Implements a two-step process:
    1. **Explode**: Create all (material, thickness) combinations
    2. **Prune**: Remove dominated options using Pareto optimization
    
    Pareto Dominance Rule:
    Candidate A dominates B if:
    - A has equal or higher R-value (better insulation) AND
    - A has lower LCA (less environmental impact)
    
    Dominated candidates are eliminated as they offer no advantage.
    
    Args:
        materials: List of all available materials across all layers
    
    Returns:
        Dictionary mapping layer_index (0-8) to list of Pareto-efficient
        Candidate objects for that layer.
        
    Performance:
        Typically reduces ~10-50 raw options per layer to ~5-15 efficient options,
        achieving ~70-90% reduction in search space per layer.
    """
    logger.info("Generating layer candidates...")
    candidates_by_layer = {i: [] for i in range(9)}
    
    # Step 1: Flatten all (material, thickness) combinations
    dummy_wall = WallAssembly(layers=[])  # Helper for calculations
    total_raw = 0
    
    for mat in materials:
        for t in mat.thickness_options:
            r = dummy_wall.calculate_r_value(mat, t)
            lca = dummy_wall.calculate_layer_lca(mat, t)
            candidates_by_layer[mat.layer_index].append(Candidate(mat, t, r, lca))
            total_raw += 1
    
    logger.info(f"Generated {total_raw} raw candidates across 9 layers")
    
    # Step 2: Pareto Pruning per layer
    pruned_by_layer = {}
    total_efficient = 0
    
    for layer_idx, candidates in candidates_by_layer.items():
        # Sort by R-value descending (best insulators first)
        candidates.sort(key=lambda x: x.r_val, reverse=True)
        
        efficient = []
        min_lca_seen = float('inf')
        
        # Scan from best to worst insulator
        # Keep only if LCA is better than all superior insulators
        for c in candidates:
            if c.lca_val < min_lca_seen:
                efficient.append(c)
                min_lca_seen = c.lca_val
        
        pruned_by_layer[layer_idx] = efficient
        total_efficient += len(efficient)
        
        reduction_pct = (1 - len(efficient)/len(candidates)) * 100 if candidates else 0
        logger.info(
            f"Layer {layer_idx}: {len(candidates)} raw → {len(efficient)} efficient "
            f"({reduction_pct:.1f}% reduction)"
        )
    
    overall_reduction = (1 - total_efficient/total_raw) * 100
    logger.info(
        f"Overall Pareto pruning: {total_raw} → {total_efficient} candidates "
        f"({overall_reduction:.1f}% reduction)"
    )
    
    return pruned_by_layer


def combine_layers(
    layer_indices: List[int],
    candidate_map: Dict[int, List[Candidate]]
) -> List[Tuple[float, float, Tuple[Candidate, ...]]]:
    """Generate Pareto-efficient combinations for a subset of layers.
    
    Creates all possible combinations of candidates across specified layers,
    then applies Pareto pruning to the partial sums.
    
    Args:
        layer_indices: List of layer indices to combine (e.g., [0,1,2,3,4])
        candidate_map: Dictionary of Pareto-efficient candidates per layer
    
    Returns:
        List of tuples, each containing:
        - Sum of R-values across layers
        - Sum of LCA values across layers
        - Tuple of Candidate objects forming this combination
        
    Note:
        Combinations are Pareto-pruned to keep only efficient partial sums.
    """
    layer_names = ','.join(str(i) for i in layer_indices)
    logger.debug(f"Combining layers {layer_names}...")
    
    lists_to_combine = [candidate_map[i] for i in layer_indices]
    results = []
    
    # Generate Cartesian product
    for combo in itertools.product(*lists_to_combine):
        sum_r = sum(c.r_val for c in combo)
        sum_lca = sum(c.lca_val for c in combo)
        results.append((sum_r, sum_lca, combo))
    
    logger.debug(f"Generated {len(results)} raw combinations for layers {layer_names}")
    
    # Pareto prune the partial combinations
    results.sort(key=lambda x: x[0], reverse=True)  # Sort by R descending
    
    efficient_results = []
    min_lca = float('inf')
    
    for r, lca, combo in results:
        if lca < min_lca:
            efficient_results.append((r, lca, combo))
            min_lca = lca
    
    reduction = (1 - len(efficient_results)/len(results)) * 100 if results else 0
    logger.debug(
        f"Pruned layers {layer_names}: {len(results)} → {len(efficient_results)} "
        f"({reduction:.1f}% reduction)"
    )
    
    return efficient_results


def run_optimization() -> List[Candidate]:
    """Execute the complete wall optimization algorithm.
    
    Implements a three-phase approach:
    1. **Data Loading & Pruning**: Load materials, apply per-layer Pareto pruning
    2. **Divide & Conquer**: Build inner (0-4) and outer (5-8) halves separately
    3. **Merge & Filter**: Combine halves, filter by U-value, select minimum LCA
    
    Returns:
        List of 9 Candidate objects representing the optimal wall assembly,
        or None if no valid assembly found.
        
    Performance:
        Typical execution time: 50-150ms for standard dataset
    """
    logger.info("=" * 60)
    logger.info("Starting Wall Assembly Optimization")
    logger.info(f"Target R-layers: {R_LAYERS_MIN:.2f} - {R_LAYERS_MAX:.2f} m²K/W")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Phase 1: Load Data & Get Efficient Candidates
    logger.info("\n[Phase 1] Loading data and applying Pareto pruning...")
    all_mats = load_data()  # Uses default layers/ directory
    candidates_map = get_layer_candidates(all_mats)
    
    # Phase 2: Divide & Conquer
    logger.info("\n[Phase 2] Building wall half combinations...")
    
    logger.info("Building Inner Wall (layers 0-4)...")
    inner_combos = combine_layers([0, 1, 2, 3, 4], candidates_map)
    logger.info(f"  → {len(inner_combos)} efficient inner combinations")

    logger.info("Building Outer Wall (layers 5-8)...")
    outer_combos = combine_layers([5, 6, 7, 8], candidates_map)
    logger.info(f"  → {len(outer_combos)} efficient outer combinations")
    
    # Phase 3: Merge & Filter
    logger.info("\n[Phase 3] Merging halves and filtering by U-value constraint...")
    
    best_wall = None
    min_total_lca = float('inf')
    valid_count = 0
    
    # Try all combinations of inner × outer
    for r_in, lca_in, c_in in inner_combos:
        for r_out, lca_out, c_out in outer_combos:
            total_r_layers = r_in + r_out
            
            # Check if total R is within target range
            if R_LAYERS_MIN <= total_r_layers <= R_LAYERS_MAX:
                total_lca = lca_in + lca_out
                valid_count += 1
                
                if total_lca < min_total_lca:
                    min_total_lca = total_lca
                    best_wall = list(c_in + c_out)  # Combine tuples into list
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    logger.info("=" * 60)
    logger.info(f"Optimization complete in {elapsed:.4f} seconds")
    logger.info(f"Found {valid_count} valid wall combinations")
    logger.info("=" * 60)
    
    if best_wall:
        # Verify and display results
        r_sum = sum(c.r_val for c in best_wall)
        u_val = 1.0 / (R_SI + r_sum + R_SE)
        
        logger.info("\n*** OPTIMAL WALL ASSEMBLY FOUND ***")
        logger.info(f"Total LCA Impact: {min_total_lca:.4f} kg CO₂-eq/m²")
        logger.info(f"U-Value: {u_val:.4f} W/(m²K) (Target: 0.14 ±10%)")
        logger.info(f"Total R-Value: {r_sum:.3f} m²K/W")
        
        logger.info("\nLayer-by-layer breakdown:")
        for idx, c in enumerate(best_wall):
            logger.info(
                f"  L{idx} [{c.material.name[:30]:30}] "
                f"t={c.thickness*1000:5.1f}mm | R={c.r_val:5.3f} | LCA={c.lca_val:6.3f}"
            )
        
        return best_wall
    else:
        logger.warning("\n*** NO VALID WALL FOUND ***")
        logger.warning("No combination meets the U-value constraint.")
        logger.warning("Consider relaxing tolerances or adding more materials.")
        return None


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging(logging.INFO)
    
    result = run_optimization()
    
    if result:
        logger.info("\nOptimization successful!")
    else:
        logger.error("\nOptimization failed - no valid solution found")