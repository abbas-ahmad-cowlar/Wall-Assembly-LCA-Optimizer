import time
import itertools
from typing import List, Tuple, Dict
from dataclasses import dataclass
from data_loader import load_data, Material
from physics import WallAssembly, R_SI, R_SE

# --- Configuration ---
TARGET_U = 0.14
TOLERANCE = 0.10
U_MIN = TARGET_U * (1 - TOLERANCE)  # 0.126
U_MAX = TARGET_U * (1 + TOLERANCE)  # 0.154

# Target R-Value Range (Inverse of U)
# U = 1 / R_total  =>  R_total = 1 / U
# We need R_total to be between 1/0.154 and 1/0.126
R_TOTAL_MIN = 1.0 / U_MAX  # ~6.49
R_TOTAL_MAX = 1.0 / U_MIN  # ~7.93

# We need the sum of layers to be: Total - R_si - R_se
R_LAYERS_MIN = R_TOTAL_MIN - R_SI - R_SE  # ~6.32
R_LAYERS_MAX = R_TOTAL_MAX - R_SI - R_SE  # ~7.76

@dataclass
class Candidate:
    """Represents a single layer option (Material + Thickness)"""
    material: Material
    thickness: float
    r_val: float
    lca_val: float

    def __repr__(self):
        return f"<{self.material.name[:10]}... t={self.thickness:.3f} R={self.r_val:.2f} LCA={self.lca_val:.2f}>"

def get_layer_candidates(materials: List[Material]) -> Dict[int, List[Candidate]]:
    """
    Explodes materials into discrete (Material, Thickness) candidates.
    Applies PARETO PRUNING: Removes candidates that are strictly worse 
    (Higher LCA *and* Lower R) than another candidate in the same layer.
    """
    candidates_by_layer = {i: [] for i in range(9)}
    
    # 1. Flatten all options
    for mat in materials:
        dummy_wall = WallAssembly(layers=[]) # Helper for calc methods
        for t in mat.thickness_options:
            r = dummy_wall.calculate_r_value(mat, t)
            lca = dummy_wall.calculate_layer_lca(mat, t)
            candidates_by_layer[mat.layer_index].append(Candidate(mat, t, r, lca))

    # 2. Pareto Pruning per layer
    pruned_by_layer = {}
    for layer_idx, candidates in candidates_by_layer.items():
        # Sort by R (descending) -> Higher R first
        candidates.sort(key=lambda x: x.r_val, reverse=True)
        
        efficient = []
        min_lca_seen = float('inf')
        
        # Scan from best insulator to worst.
        # We only keep an option if it's cheaper (LCA) than all better insulators seen so far.
        for c in candidates:
            if c.lca_val < min_lca_seen:
                efficient.append(c)
                min_lca_seen = c.lca_val
        
        pruned_by_layer[layer_idx] = efficient
        print(f"Layer {layer_idx}: Pruned {len(candidates)} -> {len(efficient)} efficient options.")
        
    return pruned_by_layer

def combine_layers(layer_indices: List[int], candidate_map: Dict[int, List[Candidate]]):
    """
    Generates all combinations for a subset of layers.
    Returns list of tuples: (Sum_R, Sum_LCA, [List of Candidates])
    Also applies Pareto Pruning to the partial sums!
    """
    lists_to_combine = [candidate_map[i] for i in layer_indices]
    results = []
    
    # Cartesian Product
    for combo in itertools.product(*lists_to_combine):
        sum_r = sum(c.r_val for c in combo)
        sum_lca = sum(c.lca_val for c in combo)
        results.append((sum_r, sum_lca, combo))
        
    # Prune the Partial Combinations to keep memory low
    # Sort by R descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    efficient_results = []
    min_lca = float('inf')
    
    for r, lca, combo in results:
        if lca < min_lca:
            efficient_results.append((r, lca, combo))
            min_lca = lca
            
    return efficient_results

def run_optimization():
    print(f"--- Starting Optimization (Target R-Layers: {R_LAYERS_MIN:.2f} - {R_LAYERS_MAX:.2f}) ---")
    start_time = time.time()
    
    # 1. Load Data
    all_mats = load_data(".")
    candidates_map = get_layer_candidates(all_mats)
    
    # 2. Divide & Conquer
    # Split: Inner (0,1,2,3,4) | Outer (5,6,7,8)
    print("Building Inner Wall combinations...")
    inner_combos = combine_layers([0, 1, 2, 3, 4], candidates_map)
    print(f"  > Generated {len(inner_combos)} efficient Inner Wall halves.")

    print("Building Outer Wall combinations...")
    outer_combos = combine_layers([5, 6, 7, 8], candidates_map)
    print(f"  > Generated {len(outer_combos)} efficient Outer Wall halves.")
    
    # 3. Merge & Filter
    # Sort outer by R for binary search (or efficient scanning)
    # Since both lists are Pareto-sorted (Desc R), we can scan efficiently.
    
    best_wall = None
    min_total_lca = float('inf')
    valid_count = 0
    
    # Brute force the merged efficient lists (Should be small now, <5k * <5k)
    for r_in, lca_in, c_in in inner_combos:
        for r_out, lca_out, c_out in outer_combos:
            
            total_r_layers = r_in + r_out
            
            # Optimization: If total R is already too low, and outer list is sorted desc R,
            # subsequent outer items will also be too low. Break inner loop?
            # Actually, just check range.
            
            if R_LAYERS_MIN <= total_r_layers <= R_LAYERS_MAX:
                total_lca = lca_in + lca_out
                valid_count += 1
                
                if total_lca < min_total_lca:
                    min_total_lca = total_lca
                    best_wall = c_in + c_out # Combine tuples
                    
    end_time = time.time()
    print(f"--- Optimization Complete in {end_time - start_time:.4f} seconds ---")
    print(f"Found {valid_count} valid combinations.")
    
    if best_wall:
        print("\n*** WINNING WALL ASSEMBLY ***")
        print(f"Total LCA: {min_total_lca:.4f} kg CO2-eq/m2")
        
        # Verify U-Value
        r_sum = sum(c.r_val for c in best_wall)
        u_val = 1.0 / (R_SI + r_sum + R_SE)
        print(f"U-Value:   {u_val:.4f} W/m2K (Target 0.14)")
        
        print("\nLayer Details:")
        for idx, c in enumerate(best_wall):
            print(f"L{idx} [{c.material.name[:25]:<25}] Thick: {c.thickness*1000:5.1f}mm | R: {c.r_val:5.3f} | LCA: {c.lca_val:5.3f}")
            
        # Save result for Phase 4
        return best_wall
    else:
        print("NO VALID WALL FOUND. Relax constraints?")
        return None

if __name__ == "__main__":
    # from dataclasses import dataclass # Re-import hack removed
    run_optimization()