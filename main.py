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
from typing import List, Tuple, Optional

from data_loader import load_data, Material
from physics import (
    WallAssembly, 
    calculate_layer_r_value, 
    calculate_layer_lca_impact
)
from config import R_SI, R_SE, TARGET_U, TOLERANCE
from optimizer import run_optimization, Candidate
from logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def clear_screen() -> None:
    """Clear the terminal screen (cross-platform)."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header() -> None:
    """Print the application header."""
    print("="*60)
    print("      WALL ASSEMBLY LCA OPTIMIZER & DESIGN TOOL")
    print("="*60)


def display_wall_status(assembly: List[Candidate]) -> None:
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
    
    total_r_value = 0.0
    total_lca_impact = 0.0
    
    for i, candidate in enumerate(assembly):
        material_name = candidate.material.name[:28]
        layer_name = f"Layer {i}"
        thickness_mm = candidate.thickness * 1000
        
        print(
            f"{i:<4} {layer_name:<25} {material_name:<30} "
            f"{thickness_mm:<10.1f} {candidate.r_val:<8.3f} {candidate.lca_val:<8.3f}"
        )
        
        total_r_value += candidate.r_val
        total_lca_impact += candidate.lca_val

    # Physics Summary
    u_value = 1.0 / (R_SI + total_r_value + R_SE)
    
    print("-" * 90)
    print(f"{'TOTALS':<61} {'R=' + str(round(total_r_value, 2)):<10} {total_lca_impact:.3f}")
    print("=" * 90)
    
    # Status Check
    print(f"\n>> PHYSICS CHECK:")
    print(f"   Total LCA Impact: {total_lca_impact:.4f} kg CO2-eq/m²")
    print(f"   U-Value:          {u_value:.4f} W/(m²K)")
    
    # Validation against config constants
    u_min = TARGET_U * (1 - TOLERANCE)
    u_max = TARGET_U * (1 + TOLERANCE)
    
    if u_min <= u_value <= u_max:
        print(f"   Status:           [PASS] (Target {TARGET_U} ± {TOLERANCE*100:.0f}%)")
        logger.info(f"Wall validates: U={u_value:.4f}, LCA={total_lca_impact:.4f}")
    else:
        diff = u_value - TARGET_U
        direction = "HIGH" if diff > 0 else "LOW"
        print(f"   Status:           [FAIL] {direction} by {abs(diff):.4f}")
        logger.warning(f"Wall fails validation: U={u_value:.4f} (target {TARGET_U} ±{TOLERANCE*100:.0f}%)")


def save_results(current_wall: List[Candidate], output_dir: str = "outputs") -> Tuple[Path, Path]:
    """Save wall assembly results with timestamp.
    
    Creates two files:
    1. Raw data in outputs/runs/
    2. Formatted report in outputs/reports/
    
    Args:
        current_wall: List of Candidate objects representing the wall
        output_dir: Base directory for outputs (default: outputs/)
    
    Returns:
        Tuple of (raw_file_path, report_file_path)
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


def _generate_report(current_wall: List[Candidate], output_file: Path) -> None:
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
- **Total LCA Impact:** {total_lca:.3f} kg CO2-eq/m²

## Layer Breakdown

| Layer | Material | Thickness (mm) | R-Value | LCA Impact |
|-------|----------|----------------|---------|------------|
"""
    
    for i, c in enumerate(current_wall):
        report += f"| {i} | {c.material.name[:40]} | {c.thickness*1000:.1f} | {c.r_val:.3f} | {c.lca_val:.3f} |\n"
    
    # Config-based validation
    u_min = TARGET_U * (1 - TOLERANCE)
    u_max = TARGET_U * (1 + TOLERANCE)
    
    report += f"\n## Validation\n"
    if u_min <= u_val <= u_max:
        report += f"✅ **PASS** - U-value within target range ({TARGET_U} ± {TOLERANCE*100:.0f}%)\n"
    else:
        report += f"❌ **FAIL** - U-value outside target range\n"
    
    report += f"\n## Surface Resistances (ISO 6946)\n"
    report += f"- Interior (R_si): {R_SI} m²K/W\n"
    report += f"- Exterior (R_se): {R_SE} m²K/W\n"
    
    with open(output_file, "w") as f:
        f.write(report)
    
    logger.debug(f"Report generated: {output_file}")


def get_user_selection(options: List[tuple], prompt: str, min_val: int = 0, max_val: Optional[int] = None) -> int:
    """Get validated user selection from a list of options.
    
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
            val_str = input(f"\n{prompt} ").strip()
            
            if not val_str:
                print(f"❌ Error: Please enter a number between {min_val} and {max_val}.")
                continue
            
            val_int = int(val_str)
            
            if min_val <= val_int <= max_val:
                logger.debug(f"User selected: {val_int}")
                return val_int
            else:
                print(f"❌ Error: Selection must be between {min_val} and {max_val}. You entered: {val_int}")
        except ValueError:
            print(f"❌ Error: '{val_str}' is not a valid number. Please enter an integer.")
        except KeyboardInterrupt:
            logger.info("User interrupted with Ctrl+C")
            print("\n\nExiting...")
            sys.exit(0)


def handle_modify_layer(current_wall: List[Candidate], all_materials: List[Material]) -> None:
    """Handle user request to modify a specific layer.
    
    Args:
        current_wall: List of Candidate objects (modified in-place)
        all_materials: List of all available materials
    """
    try:
        layer_idx_str = input("\nEnter Layer ID (0-8) to modify: ").strip()
        
        if not layer_idx_str:
            print("❌ Error: Please enter a layer number.")
            input("Press Enter to continue...")
            return
        
        layer_idx = int(layer_idx_str)
        
        if not (0 <= layer_idx <= 8):
            print(f"❌ Error: Layer ID must be between 0 and 8. You entered: {layer_idx}")
            input("Press Enter to continue...")
            return
        
        logger.info(f"User modifying layer {layer_idx}")
            
    except ValueError:
        print(f"❌ Error: '{layer_idx_str}' is not a valid number.")
        input("Press Enter to continue...")
        return
        
    # Find materials for this layer
    valid_materials = [m for m in all_materials if m.layer_index == layer_idx]
    
    # Generate options
    options = []
    for material in valid_materials:
        if len(material.thickness_options) == 0:
             continue

        for thickness in material.thickness_options:
            # Use standalone calculation functions (No Dummy Wall!)
            r_val = calculate_layer_r_value(material, thickness)
            lca_val = calculate_layer_lca_impact(material, thickness)
            
            options.append(Candidate(material, thickness, r_val, lca_val))
    
    if not options:
        print("No options found for this layer.")
        return

    # Display options
    print(f"\n--- Options for Layer {layer_idx} ---")
    print(f"{'ID':<4} {'Material':<30} {'Thick(mm)':<10} {'R-Val':<8} {'LCA':<8}")
    for i, opt in enumerate(options):
        print(
            f"{i:<4} {opt.material.name[:28]:<30} "
            f"{opt.thickness*1000:<10.1f} {opt.r_val:<8.3f} {opt.lca_val:<8.3f}"
        )
        
    # Apply change
    selected_index = get_user_selection(options, "Select new option ID:")
    new_candidate = options[selected_index]
    
    current_wall[layer_idx] = new_candidate
    logger.info(f"Layer {layer_idx} updated to: {new_candidate.material.name} ({new_candidate.thickness*1000:.1f}mm)")
    print("✓ Layer updated!")
    input("Press Enter to continue...")


def handle_save_report(current_wall: List[Candidate]) -> None:
    """Handle user request to save results."""
    logger.info("User saving results...")
    try:
        raw_file, report_file = save_results(current_wall)
        print(f"\n✓ Results saved successfully!")
        print(f"  Raw data: {raw_file.name}")
        print(f"  Report:   {report_file.name}")
    except Exception as e:
        logger.error(f"Error saving results: {e}", exc_info=True)
        print(f"❌ Error: {e}")
    input("Press Enter to continue...")


def interactive_mode(current_wall: List[Candidate], all_materials: List[Material]) -> None:
    """Run interactive mode for manual wall modification.
    
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
                
            if choice == '3':
                logger.info("User chose to exit")
                print("Exiting...")
                break
                
            elif choice == '2':
                handle_save_report(current_wall)
                
            elif choice == '1':
                handle_modify_layer(current_wall, all_materials)
                
            else:
                print(f"❌ Error: '{choice}' is not valid. Please enter 1, 2, or 3.")
                input("Press Enter to continue...")
                
        except KeyboardInterrupt:
            logger.info("User interrupted")
            print("\n\nExiting...")
            break


def main() -> None:
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
        print(f"   - U-value constraints too strict (Target {TARGET_U})")
        print("   - Data quality issues")
        sys.exit(1)
    
    logger.info("Optimization successful")
    print("\n✓ Optimization Successful! Loading Interactive Mode...")
    input("Press Enter to start...")
    
    interactive_mode(best_wall, all_materials)
    
    logger.info("Application exited normally")


if __name__ == "__main__":
    main()