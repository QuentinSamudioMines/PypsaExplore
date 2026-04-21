"""
Configuration loader module for PyPSA energy system scenarios.

Handles parsing of YAML configuration files and validation of scenario parameters.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional


class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass


def load_scenario_config(scenario_name: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration for a specific scenario from YAML file.
    
    Parameters
    ----------
    scenario_name : str
        Name of the scenario (e.g., 'baseline', 'high_renewable')
    config_path : str, optional
        Path to scenario.yaml. If None, uses default location.
        
    Returns
    -------
    dict
        Scenario configuration dictionary containing network topology,
        generator parameters, storage settings, etc.
        
    Raises
    ------
    ConfigError
        If scenario is not found or configuration is invalid.
    """
    if config_path is None:
        # Default path relative to project root
        config_path = Path(__file__).parent.parent / "config" / "scenario.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        full_config = yaml.safe_load(f)
    
    # Check if scenario exists
    if scenario_name not in full_config:
        available = get_scenario_names(config_path)
        raise ConfigError(
            f"Scenario '{scenario_name}' not found in configuration. "
            f"Available scenarios: {', '.join(available)}"
        )
    
    scenario_config = full_config[scenario_name]
    
    # Merge with global settings
    if 'settings' in full_config:
        scenario_config['settings'] = full_config['settings']
    if 'network' in full_config:
        scenario_config['network'] = full_config['network']
    
    # Validate required fields
    _validate_scenario_config(scenario_config, scenario_name)
    
    return scenario_config


def get_scenario_names(config_path: Optional[str] = None) -> List[str]:
    """
    Get list of available scenario names from configuration file.
    
    Parameters
    ----------
    config_path : str, optional
        Path to scenario.yaml. If None, uses default location.
        
    Returns
    -------
    list
        List of scenario names (excluding 'settings' and 'network' sections).
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "scenario.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        return []
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Filter out non-scenario keys
    exclude_keys = {'settings', 'network'}
    return [k for k in config.keys() if k not in exclude_keys]


def _validate_scenario_config(config: Dict[str, Any], scenario_name: str) -> None:
    """
    Validate scenario configuration structure.
    
    Parameters
    ----------
    config : dict
        Scenario configuration dictionary
    scenario_name : str
        Name of the scenario (for error messages)
        
    Raises
    ------
    ConfigError
        If required fields are missing or invalid.
    """
    required_fields = ['generators', 'demand']
    
    for field in required_fields:
        if field not in config:
            raise ConfigError(
                f"Scenario '{scenario_name}' missing required field: '{field}'"
            )
    
    # Validate generators structure
    if not isinstance(config['generators'], list) or len(config['generators']) == 0:
        raise ConfigError(
            f"Scenario '{scenario_name}': 'generators' must be a non-empty list"
        )
    
    # Validate each generator has required fields
    for i, gen in enumerate(config['generators']):
        gen_required = ['name', 'bus', 'carrier']
        for field in gen_required:
            if field not in gen:
                raise ConfigError(
                    f"Scenario '{scenario_name}': Generator {i} missing '{field}'"
                )
    
    # Validate demand structure
    if not isinstance(config['demand'], dict):
        raise ConfigError(
            f"Scenario '{scenario_name}': 'demand' must be a dictionary with bus names as keys"
        )


def get_global_settings(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load global settings from configuration file.
    
    Parameters
    ----------
    config_path : str, optional
        Path to scenario.yaml. If None, uses default location.
        
    Returns
    -------
    dict
        Global settings dictionary.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "scenario.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        return {}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config.get('settings', {})


def get_network_topology(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load network topology (buses, lines, carriers) from configuration.
    
    Parameters
    ----------
    config_path : str, optional
        Path to scenario.yaml. If None, uses default location.
        
    Returns
    -------
    dict
        Network topology dictionary with 'buses', 'lines', 'carriers'.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "scenario.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        return {'buses': [], 'lines': [], 'carriers': []}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config.get('network', {'buses': [], 'lines': [], 'carriers': []})


# Convenience function for quick access
def load_config(scenario: str) -> Dict[str, Any]:
    """Alias for load_scenario_config."""
    return load_scenario_config(scenario)
