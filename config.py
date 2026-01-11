"""Configuration settings for Wall Assembly LCA Optimizer.

Centralizes all physics constants, target constraints, and tolerance settings.
"""

from typing import Tuple

# --- ISO 6946 Surface Resistances (m²K/W) ---
R_SI: float = 0.13  # Interior surface resistance
R_SE: float = 0.04  # Exterior surface resistance

# --- Optimization Constraints ---
TARGET_U: float = 0.14  # Target U-value in W/(m²K)
TOLERANCE: float = 0.10  # ±10% tolerance

# Calculated Constraints
U_MIN: float = TARGET_U * (1 - TOLERANCE)
U_MAX: float = TARGET_U * (1 + TOLERANCE)

# Target R-Value Range (Inverse of U)
# U = 1 / R_total  =>  R_total = 1 / U
R_TOTAL_MIN: float = 1.0 / U_MAX
R_TOTAL_MAX: float = 1.0 / U_MIN

# Required sum of layer resistances (excluding surfaces)
# R_layers = R_total - R_si - R_se
R_LAYERS_MIN: float = R_TOTAL_MIN - R_SI - R_SE
R_LAYERS_MAX: float = R_TOTAL_MAX - R_SI - R_SE

def get_target_description() -> str:
    """Return specific target description string."""
    return f"Target U={TARGET_U} ±{TOLERANCE*100:.0f}% ({U_MIN:.3f}-{U_MAX:.3f})"
