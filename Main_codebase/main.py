import sys
import os
from typing import List, Tuple
from data_loader import load_data, Material
from physics import WallAssembly, R_SI, R_SE
from optimizer import run_optimization, Candidate

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("="*60)
    print("      WALL ASSEMBLY LCA OPTIMIZER & DESIGN TOOL")
    print("="*60)

def display_wall_status(assembly: List[Candidate]):
    """Prints the current state of the wall with precise alignment."""
    print("\n--- CURRENT WALL ASSEMBLY ---")
    print(f"{'ID':<4} {'Layer Name':<25} {'Material':<30} {'Thick(mm)':<10} {'R-Val':<8} {'LCA':<8}")
    print("-" * 90)
    
    total_r = 0.0
    total_lca = 0.0
    
    for i, c in enumerate(assembly):
        mat_name = c.material.name[:28]
        layer_name = f"Layer {i}"
        thick_mm = c.thickness * 1000
        
        print(f"{i:<4} {layer_name:<25} {mat_name:<30} {thick_mm:<10.1f} {c.r_val:<8.3f} {c.lca_val:<8.3f}")
        
        total_r += c.r_val
        total_lca += c.lca_val

    # Physics Summary
    u_val = 1.0 / (R_SI + total_r + R_SE)
    
    print("-" * 90)
    print(f"{'TOTALS':<61} {'R=' + str(round(total_r,2)):<10} {total_lca:.3f}")
    print("=" * 90)
    
    # Status Check
    print(f"\n>> PHYSICS CHECK:")
    print(f"   Total LCA Impact: {total_lca:.4f} kg CO2-eq/m2")
    print(f"   U-Value:          {u_val:.4f} W/m2K")
    
    # Validation
    if 0.126 <= u_val <= 0.154:
        print(f"   Status:           [PASS] (Target 0.14 ± 10%)")
    else:
        diff = u_val - 0.14
        direction = "HIGH" if diff > 0 else "LOW"
        print(f"   Status:           [FAIL] {direction} by {abs(diff):.4f}")

def get_user_selection(options: List[tuple], prompt: str):
    """Generic helper for menu selection."""
    while True:
        try:
            val = input(f"\n{prompt} ")
            idx = int(val)
            if 0 <= idx < len(options):
                return idx
            print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a number.")

def interactive_mode(current_wall: List[Candidate], all_materials: List[Material]):
    """The main loop for manual modification."""
    
    while True:
        clear_screen()
        print_header()
        display_wall_status(current_wall)
        
        print("\n[MENU]")
        print("1. Modify a Layer")
        print("2. Export/Save Results (Simulated)")
        print("3. Exit")
        
        choice = input("\nSelect Action (1-3): ")
        
        if choice == '3':
            print("Exiting...")
            break
            
        elif choice == '2':
            print("\nSaving results to 'final_wall.txt'...")
            with open("final_wall.txt", "w") as f:
                f.write(str(current_wall))
            print("Done. Press Enter.")
            input()
            
        elif choice == '1':
            # 1. Select Layer
            l_idx_str = input("\nEnter Layer ID (0-8) to modify: ")
            try:
                l_idx = int(l_idx_str)
                if not (0 <= l_idx <= 8): raise ValueError
            except:
                print("Invalid Layer ID.")
                input("Press Enter...")
                continue
                
            # 2. Find all materials available for this layer
            valid_mats = [m for m in all_materials if m.layer_index == l_idx]
            
            # Flatten to options (Material + Thickness)
            options = []
            for m in valid_mats:
                # Calculate R and LCA for single unit to help user choose
                # Just use the first thickness for preview
                preview_t = m.thickness_options[0]
                
                # Check fallbacks
                if len(m.thickness_options) == 0:
                     continue

                for t in m.thickness_options:
                    # Quick calc
                    dummy_wall = WallAssembly([])
                    r = dummy_wall.calculate_r_value(m, t)
                    lca = dummy_wall.calculate_layer_lca(m, t)
                    options.append(Candidate(m, t, r, lca))
            
            # 3. Display Options
            print(f"\n--- Options for Layer {l_idx} ---")
            print(f"{'ID':<4} {'Material':<30} {'Thick(mm)':<10} {'R-Val':<8} {'LCA':<8}")
            for i, opt in enumerate(options):
                print(f"{i:<4} {opt.material.name[:28]:<30} {opt.thickness*1000:<10.1f} {opt.r_val:<8.3f} {opt.lca_val:<8.3f}")
                
            # 4. Apply Change
            sel_idx = get_user_selection(options, "Select new option ID:")
            new_candidate = options[sel_idx]
            
            current_wall[l_idx] = new_candidate
            print("Layer updated!")

def main():
    clear_screen()
    print_header()
    print("Phase 1: Loading Data...")
    all_materials = load_data(".")
    
    print("\nPhase 2: Running Optimization Engine...")
    best_wall = run_optimization()
    
    if not best_wall:
        print("Critical Error: Optimizer found no valid initial wall.")
        sys.exit(1)
        
    print("\nOptimization Successful! Loading Interactive Mode...")
    input("Press Enter to start...")
    
    interactive_mode(best_wall, all_materials)

if __name__ == "__main__":
    main()