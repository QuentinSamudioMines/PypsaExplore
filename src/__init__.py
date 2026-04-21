"""
PyPSA Energy System Optimization Package

This package provides tools for building, optimizing, and analyzing
power systems with high renewable penetration using PyPSA.

Author: Research Energy Modeling Group
License: MIT
"""

__version__ = "0.1.0"
__author__ = "Research Energy Modeling Group"

from .build_network import build_network
from .run_optimization import run_optimization, analyze_results
from .load_data import load_time_series, create_synthetic_profiles
from .config_loader import load_scenario_config, get_scenario_names
from .plotting import (
    plot_generation_mix,
    plot_storage_operation,
    plot_network_diagram,
    plot_daily_profile,
    plot_scenario_comparison
)

__all__ = [
    "build_network",
    "run_optimization",
    "analyze_results",
    "load_time_series",
    "create_synthetic_profiles",
    "load_scenario_config",
    "get_scenario_names",
    "plot_generation_mix",
    "plot_storage_operation",
    "plot_network_diagram",
    "plot_daily_profile",
    "plot_scenario_comparison",
]
