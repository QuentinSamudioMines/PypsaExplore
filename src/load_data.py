"""
Data loading and generation module for PyPSA energy system analysis.

Handles time series data ingestion and synthetic profile generation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_time_series(filepath: str, columns: Optional[list] = None) -> pd.DataFrame:
    """
    Load time series data from CSV file.
    
    Parameters
    ----------
    filepath : str
        Path to CSV file containing time series data
    columns : list, optional
        Specific columns to load. If None, loads all columns.
        
    Returns
    -------
    pd.DataFrame
        Time series data with DatetimeIndex
        
    Raises
    ------
    FileNotFoundError
        If the specified file does not exist
    ValueError
        If data format is invalid
    """
    path = Path(filepath)
    
    if not path.exists():
        raise FileNotFoundError(f"Time series file not found: {filepath}")
    
    # Load data
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    
    if columns:
        missing = set(columns) - set(df.columns)
        if missing:
            raise ValueError(f"Columns not found in data: {missing}")
        df = df[columns]
    
    # Validate datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Data index must be datetime")
    
    return df


def create_synthetic_profiles(
    periods: int = 168,
    freq: str = 'h',
    start_date: str = '2024-01-01',
    random_seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic renewable profiles and demand data.
    
    Creates realistic time series for:
    - Wind capacity factors (North/South zones)
    - Solar capacity factors (North/South zones)
    - Electricity demand profiles (North/South zones)
    
    Parameters
    ----------
    periods : int
        Number of time periods to generate (default: 168 hours = 1 week)
    freq : str
        Frequency string for time index (default: 'h' for hourly)
    start_date : str
        Start date for time series (YYYY-MM-DD format)
    random_seed : int
        Random seed for reproducibility
        
    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - wind_north, wind_south: Wind capacity factors [0-1]
        - solar_north, solar_south: Solar capacity factors [0-1]
        - demand_north, demand_south: Demand in MW
    """
    np.random.seed(random_seed)
    
    # Create time index
    time_index = pd.date_range(start=start_date, periods=periods, freq=freq)
    hours = time_index.hour
    day_of_year = time_index.dayofyear
    
    # Initialize DataFrame
    data = pd.DataFrame(index=time_index)
    
    # === WIND PROFILES ===
    # North zone: Higher wind, more variable
    wind_base_north = 0.35
    wind_seasonal_north = 0.1 * np.sin(2 * np.pi * day_of_year / 365 + np.pi/4)
    wind_noise_north = np.random.normal(0, 0.15, periods)
    data['wind_north'] = np.clip(wind_base_north + wind_seasonal_north + wind_noise_north, 0, 1)
    
    # South zone: Lower wind, more stable
    wind_base_south = 0.25
    wind_seasonal_south = 0.05 * np.sin(2 * np.pi * day_of_year / 365)
    wind_noise_south = np.random.normal(0, 0.10, periods)
    data['wind_south'] = np.clip(wind_base_south + wind_seasonal_south + wind_noise_south, 0, 1)
    
    # === SOLAR PROFILES ===
    # Solar depends on hour of day (daylight hours ~ 6-20h)
    def solar_profile(hours, peak_factor=1.0, noise_std=0.05):
        """Generate solar capacity factor based on hour."""
        profile = np.zeros(len(hours))
        daytime = (hours >= 6) & (hours <= 20)
        # Parabolic shape during daytime
        profile[daytime] = peak_factor * np.sin(np.pi * (hours[daytime] - 6) / 14)
        profile[daytime] += np.random.normal(0, noise_std, np.sum(daytime))
        return np.clip(profile, 0, 1)
    
    # North zone: Moderate solar
    data['solar_north'] = solar_profile(hours.values, peak_factor=0.8)
    
    # South zone: High solar (southern latitude)
    data['solar_south'] = solar_profile(hours.values, peak_factor=1.0)
    
    # === DEMAND PROFILES ===
    def demand_profile(hours, base_load, peak_load, pattern='industrial'):
        """Generate demand profile with daily patterns."""
        profile = np.ones(len(hours)) * base_load
        
        if pattern == 'industrial':
            # Higher during working hours (8-18h), lower at night
            working = (hours >= 8) & (hours <= 18)
            profile[working] *= 1.3
            night = (hours < 6) | (hours > 22)
            profile[night] *= 0.7
        else:  # residential
            # Morning and evening peaks
            morning = (hours >= 7) & (hours <= 9)
            evening = (hours >= 18) & (hours <= 22)
            profile[morning] *= 1.4
            profile[evening] *= 1.5
            night = (hours >= 23) | (hours <= 6)
            profile[night] *= 0.5
        
        # Scale to match peak load
        profile = profile / profile.max() * peak_load
        # Add small noise
        profile += np.random.normal(0, peak_load * 0.02, len(hours))
        
        return np.maximum(profile, base_load * 0.5)  # Minimum load floor
    
    # North zone: More industrial pattern
    data['demand_north'] = demand_profile(hours.values, base_load=800, peak_load=1200, pattern='industrial')
    
    # South zone: More residential pattern
    data['demand_south'] = demand_profile(hours.values, base_load=1200, peak_load=1800, pattern='residential')
    
    return data


def save_synthetic_data(
    data: pd.DataFrame,
    output_dir: str = "data",
    filename: str = "synthetic_profiles.csv"
) -> str:
    """
    Save generated synthetic data to CSV file.
    
    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with synthetic profiles
    output_dir : str
        Directory to save the file
    filename : str
        Name of the output file
        
    Returns
    -------
    str
        Path to saved file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filepath = output_path / filename
    data.to_csv(filepath)
    
    return str(filepath)


def generate_and_save_all_data(output_dir: str = "data") -> Dict[str, str]:
    """
    Generate and save all synthetic data files for the project.
    
    Creates:
    - demand_hourly.csv: Electricity demand profiles
    - renewables_profiles.csv: Wind and solar capacity factors
    
    Parameters
    ----------
    output_dir : str
        Directory to save data files
        
    Returns
    -------
    dict
        Dictionary mapping file descriptions to file paths
    """
    # Generate full year of data (8760 hours)
    print("Generating synthetic data for 8760 hours (full year)...")
    data = create_synthetic_profiles(periods=8760, start_date='2024-01-01')
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Split into separate files as expected by config
    demand_cols = ['demand_north', 'demand_south']
    renewable_cols = ['wind_north', 'wind_south', 'solar_north', 'solar_south']
    
    # Save demand
    demand_file = output_path / "demand_hourly.csv"
    data[demand_cols].to_csv(demand_file)
    print(f"  Saved: {demand_file}")
    
    # Save renewables
    renewable_file = output_path / "renewables_profiles.csv"
    data[renewable_cols].to_csv(renewable_file)
    print(f"  Saved: {renewable_file}")
    
    # Save combined (for reference)
    combined_file = output_path / "synthetic_profiles.csv"
    data.to_csv(combined_file)
    print(f"  Saved: {combined_file}")
    
    return {
        'demand': str(demand_file),
        'renewables': str(renewable_file),
        'combined': str(combined_file)
    }


def validate_data_profiles(df: pd.DataFrame) -> Tuple[bool, list]:
    """
    Validate that data profiles meet expected constraints.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with profiles to validate
        
    Returns
    -------
    tuple
        (is_valid, list of error messages)
    """
    errors = []
    
    # Check for required columns
    required_renewables = ['wind_north', 'wind_south', 'solar_north', 'solar_south']
    for col in required_renewables:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    
    if errors:
        return False, errors
    
    # Validate capacity factors are in [0, 1]
    for col in required_renewables:
        if df[col].min() < 0 or df[col].max() > 1:
            errors.append(f"{col}: Capacity factors must be in [0, 1]")
    
    # Check for NaN values
    if df.isnull().any().any():
        nan_cols = df.columns[df.isnull().any()].tolist()
        errors.append(f"NaN values found in columns: {nan_cols}")
    
    # Check for negative demand (if present)
    demand_cols = [c for c in df.columns if 'demand' in c]
    for col in demand_cols:
        if (df[col] < 0).any():
            errors.append(f"{col}: Demand cannot be negative")
    
    return len(errors) == 0, errors


# Module-level convenience function
def get_data_for_scenario(scenario_config: dict, data_dir: str = "data") -> pd.DataFrame:
    """
    Load or generate data based on scenario configuration.
    
    Parameters
    ----------
    scenario_config : dict
        Scenario configuration dictionary
    data_dir : str
        Directory containing data files
        
    Returns
    -------
    pd.DataFrame
        DataFrame with all required time series
    """
    data_path = Path(data_dir)
    
    # Try to load existing files
    try:
        demand_file = data_path / "demand_hourly.csv"
        renewable_file = data_path / "renewables_profiles.csv"
        
        demand = pd.read_csv(demand_file, index_col=0, parse_dates=True)
        renewables = pd.read_csv(renewable_file, index_col=0, parse_dates=True)
        
        # Combine
        data = pd.concat([demand, renewables], axis=1)
        
        # Validate
        valid, errors = validate_data_profiles(data)
        if not valid:
            raise ValueError(f"Data validation failed: {errors}")
        
        return data
        
    except FileNotFoundError:
        print("Data files not found. Generating synthetic data...")
        generate_and_save_all_data(data_dir)
        
        # Load again
        demand = pd.read_csv(data_path / "demand_hourly.csv", index_col=0, parse_dates=True)
        renewables = pd.read_csv(data_path / "renewables_profiles.csv", index_col=0, parse_dates=True)
        
        return pd.concat([demand, renewables], axis=1)
