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
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

from data_loader import load_data, Material
from physics import (
    calculate_layer_r_value,
    calculate_layer_lca_impact
)
from config import (
    R_SI, R_SE,
    TARGET_U, TOLERANCE,
    U_MIN, U_MAX,
    R_LAYERS_MIN, R_LAYERS_MAX
)
from logging_config import get_logger

logger = get_logger(__name__)

logger.info(f"Optimizer configured: Target U={TARGET_U} ±{TOLERANCE*100:.0f}%")
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
        lca_val: Computed LCA impact in kg CO2-eq/m²
    """
    material: Material
    thickness: float
    r_val: float
    lca_val: float

    def __repr__(self) -> str:
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
    
    Args:
        materials: List of all available materials across all layers
    
    Returns:
        Dictionary mapping layer_index (0-8) to list of Pareto-efficient
        Candidate objects for that layer.
    """
    logger.info("Generating layer candidates...")
    candidates_by_layer = {i: [] for i in range(9)}
    
    # Step 1: Flatten all (material, thickness) combinations
    # No dummy wall needed - using static calculation functions
    total_raw_count = 0
    
    for material in materials:
        for thickness in material.thickness_options:
            r_value = calculate_layer_r_value(material, thickness)
            lca_value = calculate_layer_lca_impact(material, thickness)
            
            candidate = Candidate(material, thickness, r_value, lca_value)
            candidates_by_layer[material.layer_index].append(candidate)
            total_raw_count += 1
    
    logger.info(f"Generated {total_raw_count} raw candidates across 9 layers")
    
    # Step 2: Pareto Pruning per layer
    pruned_by_layer = {}
    total_efficient_count = 0
    
    for layer_idx, candidates in candidates_by_layer.items():
        # Sort by R-value descending (best insulators first)
        candidates.sort(key=lambda x: x.r_val, reverse=True)
        
        efficient_candidates = []
        min_lca_seen = float('inf')
        
        # Scan from best to worst insulator
        # Keep only if LCA is better than all superior insulators
        for candidate in candidates:
            if candidate.lca_val < min_lca_seen:
                efficient_candidates.append(candidate)
                min_lca_seen = candidate.lca_val
        
        pruned_by_layer[layer_idx] = efficient_candidates
        total_efficient_count += len(efficient_candidates)
        
        # Calculate reduction percentage
        if candidates:
            reduction_pct = (1 - len(efficient_candidates) / len(candidates)) * 100
        else:
            reduction_pct = 0
            
        logger.info(
            f"Layer {layer_idx}: {len(candidates)} raw -> {len(efficient_candidates)} efficient "
            f"({reduction_pct:.1f}% reduction)"
        )
    
    overall_reduction = (1 - total_efficient_count / total_raw_count) * 100
    logger.info(
        f"Overall Pareto pruning: {total_raw_count} -> {total_efficient_count} candidates "
        f"({overall_reduction:.1f}% reduction)"
    )
    
    return pruned_by_layer


def combine_layers(
    layer_indices: List[int],
    candidate_map: Dict[int, List[Candidate]]
) -> List[Tuple[float, float, Tuple[Candidate, ...]]]:
    """Generate Pareto-efficient combinations for a subset of layers.
    
    Args:
        layer_indices: List of layer indices to combine (e.g., [0,1,2,3,4])
        candidate_map: Dictionary of Pareto-efficient candidates per layer
    
    Returns:
        List of tuples, each containing:
        - Sum of R-values across layers
        - Sum of LCA values across layers
        - Tuple of Candidate objects forming this combination
    """
    layer_names = ','.join(str(i) for i in layer_indices)
    logger.debug(f"Combining layers {layer_names}...")
    
    lists_to_combine = [candidate_map[i] for i in layer_indices]
    results = []
    
    # Generate Cartesian product
    for combination in itertools.product(*lists_to_combine):
        # Calculate sums for this combination
        sum_r = sum(candidate.r_val for candidate in combination)
        sum_lca = sum(candidate.lca_val for candidate in combination)
        results.append((sum_r, sum_lca, combination))
    
    logger.debug(f"Generated {len(results)} raw combinations for layers {layer_names}")
    
    # Pareto prune the partial combinations
    results.sort(key=lambda x: x[0], reverse=True)  # Sort by R descending
    
    efficient_results = []
    min_lca = float('inf')
    
    for r_sum, lca_sum, combination_tuple in results:
        if lca_sum < min_lca:
            efficient_results.append((r_sum, lca_sum, combination_tuple))
            min_lca = lca_sum
    
    if results:
        reduction_pct = (1 - len(efficient_results) / len(results)) * 100
    else:
        reduction_pct = 0
        
    logger.debug(
        f"Pruned layers {layer_names}: {len(results)} -> {len(efficient_results)} "
        f"({reduction_pct:.1f}% reduction)"
    )
    
    return efficient_results


def run_optimization() -> Optional[List[Candidate]]:
    """Execute the complete wall optimization algorithm.
    
    Returns:
        List of 9 Candidate objects representing the optimal wall assembly,
        or None if no valid assembly found.
    """
    logger.info("=" * 60)
    logger.info("Starting Wall Assembly Optimization")
    logger.info(f"Target R-layers: {R_LAYERS_MIN:.2f} - {R_LAYERS_MAX:.2f} m²K/W")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Phase 1: Load Data & Get Efficient Candidates
    logger.info("\n[Phase 1] Loading data and aplicating Pareto pruning...")
    all_materials = load_data()
    candidates_map = get_layer_candidates(all_materials)
    
    # Phase 2: Divide & Conquer
    logger.info("\n[Phase 2] Building wall half combinations...")
    
    logger.info("Building Inner Wall (layers 0-4)...")
    inner_combos = combine_layers([0, 1, 2, 3, 4], candidates_map)
    logger.info(f"  -> {len(inner_combos)} efficient inner combinations")

    logger.info("Building Outer Wall (layers 5-8)...")
    outer_combos = combine_layers([5, 6, 7, 8], candidates_map)
    logger.info(f"  -> {len(outer_combos)} efficient outer combinations")
    
    # Phase 3: Merge & Filter
    logger.info("\n[Phase 3] Merging halves and filtering by U-value constraint...")
    
    best_wall = None
    min_total_lca = float('inf')
    valid_count = 0
    
    # Try all combinations of inner × outer
    for r_in, lca_in, candidates_in in inner_combos:
        for r_out, lca_out, candidates_out in outer_combos:
            total_r_layers = r_in + r_out
            
            # Check if total R is within target range
            if R_LAYERS_MIN <= total_r_layers <= R_LAYERS_MAX:
                total_lca = lca_in + lca_out
                valid_count += 1
                
                if total_lca < min_total_lca:
                    min_total_lca = total_lca
                    # Combine the tuples of candidates
                    best_wall = list(candidates_in + candidates_out)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    logger.info("=" * 60)
    logger.info(f"Optimization complete in {elapsed_time:.4f} seconds")
    logger.info(f"Found {valid_count} valid wall combinations")
    logger.info("=" * 60)
    
    if best_wall:
        # Verify and display results
        r_sum = sum(candidate.r_val for candidate in best_wall)
        u_val = 1.0 / (R_SI + r_sum + R_SE)
        
        logger.info("\n*** OPTIMAL WALL ASSEMBLY FOUND ***")
        logger.info(f"Total LCA Impact: {min_total_lca:.4f} kg CO2-eq/m**2")
        logger.info(f"U-Value: {u_val:.4f} W/(m²K) (Target: {TARGET_U} ±{TOLERANCE*100:.0f}%)")
        logger.info(f"Total R-Value: {r_sum:.3f} m²K/W")
        
        logger.info("\nLayer-by-layer breakdown:")
        for idx, candidate in enumerate(best_wall):
            logger.info(
                f"  L{idx} [{candidate.material.name[:30]:30}] "
                f"t={candidate.thickness*1000:5.1f}mm | "
                f"R={candidate.r_val:5.3f} | LCA={candidate.lca_val:6.3f}"
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
    
    run_optimization()