"""Interactive CLI for wall assembly optimization and manual modification.

This module provides the user interface for:
- Running the optimization algorithm
- Displaying results in formatted tables
- Interactive modification of wall assemblies
- Saving results with timestamps

The tool guides users through optimization and allows "what-if" scenario exploration.
"""

import sys
import os
import logging
import datetime
from pathlib import Path
from typing import List, Tuple
from data_loader import load_data, Material
from physics import WallAssembly, R_SI, R_SE
from optimizer import run_optimization, Candidate
from logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def clear_screen():
    """Clear the terminal screen (cross-platform)."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print the application header."""
    print("="*60)
    print("      WALL ASSEMBLY LCA OPTIMIZER & DESIGN TOOL")
    print("="*60)


def display_wall_status(assembly: List[Candidate]):
    """Display current wall assembly with thermal and environmental metrics.
    
    Shows a formatted table with:
    - Layer-by-layer material details
    - Individual R-values and LCA impacts
    - Total U-value and LCA
    - Pass/fail validation against target
    
    Args:
        assembly: List of 9 Candidate objects representing the wall
    """
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
    print(f"   Total LCA Impact: {total_lca:.4f} kg CO2-eq/m²")
    print(f"   U-Value:          {u_val:.4f} W/(m²K)")
    
    # Validation
    if 0.126 <= u_val <= 0.154:
        print(f"   Status:           [PASS] (Target 0.14 ± 10%)")
        logger.info(f"Wall validates: U={u_val:.4f}, LCA={total_lca:.4f}")
    else:
        diff = u_val - 0.14
        direction = "HIGH" if diff > 0 else "LOW"
        print(f"   Status:           [FAIL] {direction} by {abs(diff):.4f}")
        logger.warning(f"Wall fails validation: U={u_val:.4f} (target 0.14 ±10%)")


def save_results(current_wall: List[Candidate], output_dir="outputs") -> Tuple[Path, Path]:
    """Save wall assembly results with timestamp.
    
    Creates two files:
    1. Raw data in outputs/runs/
    2. Formatted report in outputs/reports/
    
    Args:
        current_wall: List of Candidate objects representing the wall
        output_dir: Base directory for outputs (default: outputs/)
    
    Returns:
        Tuple of (raw_file_path, report_file_path)
        
    Raises:
        IOError: If unable to create directories or write files
    """
    logger.info("Saving optimization results...")
    
    # Create directories
    output_path = Path(output_dir)
    runs_path = output_path / "runs"
    reports_path = output_path / "reports"
    
    runs_path.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Save raw data
    raw_file = runs_path / f"wall_{timestamp}.txt"
    with open(raw_file, "w") as f:
        f.write(str(current_wall))
    
    logger.debug(f"Raw data saved to: {raw_file}")
    
    # Generate formatted report
    report_file = reports_path / f"summary_{timestamp}.md"
    _generate_report(current_wall, report_file)
    
    logger.info(f"Results saved: {raw_file.name}, {report_file.name}")
    
    return raw_file, report_file


def _generate_report(current_wall: List[Candidate], output_file: Path):
    """Generate formatted markdown report of wall assembly.
    
    Args:
        current_wall: List of Candidate objects
        output_file: Path to output markdown file
    """
    total_r = sum(c.r_val for c in current_wall)
    total_lca = sum(c.lca_val for c in current_wall)
    u_val = 1.0 / (R_SI + total_r + R_SE)
    
    report = f"""# Wall Assembly Optimization Report
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
- **U-Value:** {u_val:.4f} W/(m²K)
- **Total R-Value:** {total_r:.3f} m²K/W
- **Total LCA Impact:** {total_lca:.3f} kg CO₂-eq/m²

## Layer Breakdown

| Layer | Material | Thickness (mm) | R-Value | LCA Impact |
|-------|----------|----------------|---------|------------|
"""
    
    for i, c in enumerate(current_wall):
        report += f"| {i} | {c.material.name[:40]} | {c.thickness*1000:.1f} | {c.r_val:.3f} | {c.lca_val:.3f} |\n"
    
    report += f"\n## Validation\n"
    if 0.126 <= u_val <= 0.154:
        report += "✅ **PASS** - U-value within target range (0.14 ± 10%)\n"
    else:
        report += f"❌ **FAIL** - U-value outside target range\n"
    
    report += f"\n## Surface Resistances (ISO 6946)\n"
    report += f"- Interior (R_si): {R_SI} m²K/W\n"
    report += f"- Exterior (R_se): {R_SE} m²K/W\n"
    
    with open(output_file, "w") as f:
        f.write(report)
    
    logger.debug(f"Report generated: {output_file}")


def get_user_selection(options: List[tuple], prompt: str, min_val: int = 0, max_val: int = None) -> int:
    """Get validated user selection from a list of options.
    
    Handles input validation with helpful error messages for:
    - Empty input
    - Non-numeric input
    - Out-of-range values
    - Keyboard interrupt (Ctrl+C)
    
    Args:
        options: List of available options
        prompt: Prompt message to display
        min_val: Minimum valid value (default 0)
        max_val: Maximum valid value (default len(options)-1)
    
    Returns:
        Valid integer selection
    """
    if max_val is None:
        max_val = len(options) - 1
    
    while True:
        try:
            val = input(f"\n{prompt} ").strip()
            
            if not val:
                print(f"❌ Error: Please enter a number between {min_val} and {max_val}.")
                continue
            
            idx = int(val)
            
            if min_val <= idx <= max_val:
                logger.debug(f"User selected: {idx}")
                return idx
            else:
                print(f"❌ Error: Selection must be between {min_val} and {max_val}. You entered: {idx}")
        except ValueError:
            print(f"❌ Error: '{val}' is not a valid number. Please enter an integer.")
        except KeyboardInterrupt:
            logger.info("User interrupted with Ctrl+C")
            print("\n\nExiting...")
            exit(0)


def interactive_mode(current_wall: List[Candidate], all_materials: List[Material]):
    """Run interactive mode for manual wall modification.
    
    Allows users to:
    - View current wall status
    - Modify individual layers
    - Save results with timestamps
    - Exit when finished
    
    Args:
        current_wall: List of 9 Candidate objects (initial optimal wall)
        all_materials: List of all available materials for modification
    """
    logger.info("Entering interactive mode")
    
    while True:
        clear_screen()
        print_header()
        display_wall_status(current_wall)
        
        print("\n[MENU]")
        print("1. Modify a Layer")
        print("2. Save Results")
        print("3. Exit")
        
        try:
            choice = input("\nSelect Action (1-3): ").strip()
            
            if not choice:
                print("❌ Error: Please enter a number (1, 2, or 3).")
                input("Press Enter to continue...")
                continue
                
            if choice not in ['1', '2', '3']:
                print(f"❌ Error: '{choice}' is not valid. Please enter 1, 2, or 3.")
                input("Press Enter to continue...")
                continue
        except KeyboardInterrupt:
            logger.info("User interrupted")
            print("\n\nExiting...")
            break
        
        if choice == '3':
            logger.info("User chose to exit")
            print("Exiting...")
            break
            
        elif choice == '2':
            logger.info("User saving results...")
            try:
                raw_file, report_file = save_results(current_wall)
                print(f"\n✓ Results saved successfully!")
                print(f"  Raw data: {raw_file.name}")
                print(f"  Report: {report_file.name}")
            except Exception as e:
                logger.error(f"Error saving results: {e}", exc_info=True)
                print(f"❌ Error: {e}")
            input("Press Enter to continue...")
            
        elif choice == '1':
            # Layer selection
            try:
                l_idx_str = input("\nEnter Layer ID (0-8) to modify: ").strip()
                
                if not l_idx_str:
                    print("❌ Error: Please enter a layer number.")
                    input("Press Enter to continue...")
                    continue
                
                l_idx = int(l_idx_str)
                
                if not (0 <= l_idx <= 8):
                    print(f"❌ Error: Layer ID must be between 0 and 8. You entered: {l_idx}")
                    input("Press Enter to continue...")
                    continue
                
                logger.info(f"User modifying layer {l_idx}")
                    
            except ValueError:
                print(f"❌ Error: '{l_idx_str}' is not a valid number.")
                input("Press Enter to continue...")
                continue
            except KeyboardInterrupt:
                logger.info("User interrupted")
                print("\n\nExiting...")
                break
                
            # Find materials for this layer
            valid_mats = [m for m in all_materials if m.layer_index == l_idx]
            
            # Generate options
            options = []
            for m in valid_mats:
                if len(m.thickness_options) == 0:
                     continue

                for t in m.thickness_options:
                    dummy_wall = WallAssembly([])
                    r = dummy_wall.calculate_r_value(m, t)
                    lca = dummy_wall.calculate_layer_lca(m, t)
                    options.append(Candidate(m, t, r, lca))
            
            # Display options
            print(f"\n--- Options for Layer {l_idx} ---")
            print(f"{'ID':<4} {'Material':<30} {'Thick(mm)':<10} {'R-Val':<8} {'LCA':<8}")
            for i, opt in enumerate(options):
                print(f"{i:<4} {opt.material.name[:28]:<30} {opt.thickness*1000:<10.1f} {opt.r_val:<8.3f} {opt.lca_val:<8.3f}")
                
            # Apply change
            sel_idx = get_user_selection(options, "Select new option ID:")
            new_candidate = options[sel_idx]
            
            current_wall[l_idx] = new_candidate
            logger.info(f"Layer {l_idx} updated to: {new_candidate.material.name} ({new_candidate.thickness*1000:.1f}mm)")
            print("✓ Layer updated!")
            input("Press Enter to continue...")


def main():
    """Main entry point for the wall assembly optimizer."""
    # Setup logging with file output
    log_file = Path("outputs/logs") / f"optimizer_{datetime.datetime.now().strftime('%Y-%m-%d')}.log"
    setup_logging(log_level=logging.INFO, log_file=log_file)
    
    logger.info("=" * 60)
    logger.info("Wall Assembly LCA Optimizer Started")
    logger.info("=" * 60)
    
    clear_screen()
    print_header()
    
    print("Phase 1: Loading Data...")
    all_materials = load_data()
    
    print("\nPhase 2: Running Optimization Engine...")
    best_wall = run_optimization()
    
    if not best_wall:
        logger.error("Optimization failed - no valid wall found")
        print("\n❌ Critical Error: Optimizer found no valid wall assembly.")
        print("   This may indicate:")
        print("   - Insufficient materials in database")
        print("   - U-value constraints too strict")
        print("   - Data quality issues")
        sys.exit(1)
    
    logger.info("Optimization successful")
    print("\n✓ Optimization Successful! Loading Interactive Mode...")
    input("Press Enter to start...")
    
    interactive_mode(best_wall, all_materials)
    
    logger.info("Application exited normally")


if __name__ == "__main__":
    main()