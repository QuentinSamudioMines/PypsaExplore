"""
Optimization runner and results analysis module for PyPSA energy system.

Handles model execution, constraint application, and post-processing.
"""

import pypsa
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


def run_optimization(
    network: pypsa.Network,
    solver_name: str = "cbc",
    solver_options: Optional[Dict[str, Any]] = None,
    verbose: bool = True
) -> bool:
    """
    Run linear optimal power flow (LOPF) optimization on the network.
    
    Parameters
    ----------
    network : pypsa.Network
        Configured PyPSA network
    solver_name : str
        Solver to use (cbc, glpk, gurobi, cplex)
    solver_options : dict, optional
        Additional solver-specific options
    verbose : bool
        Print optimization progress
        
    Returns
    -------
    bool
        True if optimization successful, False otherwise
    """
    if verbose:
        print(f"\n{'='*60}")
        print("Starting Optimization")
        print(f"{'='*60}")
        print(f"Solver: {solver_name}")
        print(f"Time steps: {len(network.snapshots)}")
        print(f"Variables: ~{len(network.snapshots) * (len(network.generators) + len(network.storage_units))}")
    
    # Default solver options
    default_options = {
        'threads': 4,
        'time_limit': 3600,
        'log_file': 'results/solver.log'
    }
    
    if solver_options:
        default_options.update(solver_options)
    
    try:
        # Run linear optimal power flow (LOPF) - PyPSA 0.25+ uses optimize()
        # include_objective_constant=False improves LP numerical conditioning
        network.optimize(
            solver_name=solver_name,
            solver_options=default_options,
            include_objective_constant=False
        )
        
        if verbose:
            print(f"\n{'='*60}")
            print("Optimization Complete - SUCCESS")
            print(f"{'='*60}")
            print(f"Objective value: {network.objective/1e6:.2f} M€")
            print(f"Termination condition: {network.status if hasattr(network, 'status') else 'OK'}")
        
        return True
        
    except Exception as e:
        if verbose:
            print(f"\n{'='*60}")
            print("Optimization FAILED")
            print(f"{'='*60}")
            print(f"Error: {str(e)}")
        return False


def analyze_results(network: pypsa.Network) -> Dict[str, Any]:
    """
    Extract and analyze optimization results from solved network.
    
    Parameters
    ----------
    network : pypsa.Network
        Solved PyPSA network
        
    Returns
    -------
    dict
        Dictionary containing key performance indicators and time series
    """
    results = {
        'objective_value_eur': network.objective,
        'total_demand_mwh': 0,
        'total_generation_mwh': {},
        'renewable_share': 0,
        'co2_emissions_ton': 0,
        'storage_utilization': {},
        'curtailment_mwh': 0,
        'transmission_flows': {},
        'generator_capacities': {},
        'time_series': {}
    }
    
    # === TOTAL DEMAND ===
    total_demand = network.loads_t.p_set.sum().sum()
    results['total_demand_mwh'] = total_demand
    
    # === GENERATION BY CARRIER ===
    for carrier in network.generators.carrier.unique():
        gen_carrier = network.generators[network.generators.carrier == carrier]
        if len(gen_carrier) > 0:
            gen_names = gen_carrier.index.tolist()
            if hasattr(network, 'generators_t') and 'p' in network.generators_t:
                gen_output = network.generators_t.p[gen_names].sum().sum()
                results['total_generation_mwh'][carrier] = gen_output
    
    # === RENEWABLE SHARE ===
    renewable_carriers = ['wind', 'solar', 'hydro']
    renewable_gen = sum(
        results['total_generation_mwh'].get(carrier, 0)
        for carrier in renewable_carriers
    )
    total_gen = sum(results['total_generation_mwh'].values())
    results['renewable_share'] = renewable_gen / total_gen if total_gen > 0 else 0
    
    # === CO2 EMISSIONS ===
    for carrier in network.generators.carrier.unique():
        gen_carrier = network.generators[network.generators.carrier == carrier]
        co2_factor = gen_carrier['co2_emissions'].iloc[0] if len(gen_carrier) > 0 else 0
        gen_names = gen_carrier.index.tolist()
        
        if hasattr(network, 'generators_t') and 'p' in network.generators_t:
            gen_output = network.generators_t.p[gen_names].sum().sum()
            results['co2_emissions_ton'] += gen_output * co2_factor
    
    # === STORAGE UTILIZATION ===
    for storage in network.storage_units.index:
        if hasattr(network, 'storage_units_t') and 'p' in network.storage_units_t:
            storage_dispatch = network.storage_units_t.p[storage].abs().sum()
            storage_capacity = network.storage_units.at[storage, 'p_nom'] * len(network.snapshots)
            if storage_capacity > 0:
                utilization = storage_dispatch / storage_capacity
                results['storage_utilization'][storage] = utilization
    
    # === CURTAILMENT ===
    # Calculate as available renewable energy minus actual generation
    for carrier in ['wind', 'solar']:
        gen_carrier = network.generators[network.generators.carrier == carrier]
        for gen_name in gen_carrier.index:
            p_nom = network.generators.at[gen_name, 'p_nom']
            p_max_pu = network.generators_t.p_max_pu[gen_name] if hasattr(network, 'generators_t') else pd.Series(1, index=network.snapshots)
            available = (p_max_pu * p_nom).sum()
            
            actual = 0
            if hasattr(network, 'generators_t') and 'p' in network.generators_t:
                actual = network.generators_t.p[gen_name].sum()
            
            results['curtailment_mwh'] += max(0, available - actual)
    
    # === TRANSMISSION FLOWS ===
    if hasattr(network, 'lines_t') and 'p0' in network.lines_t:
        for line in network.lines.index:
            flow = network.lines_t.p0[line].abs().mean()
            capacity = network.lines.at[line, 's_nom']
            results['transmission_flows'][line] = {
                'average_mw': flow,
                'capacity_mw': capacity,
                'utilization': flow / capacity if capacity > 0 else 0
            }
    
    # === GENERATOR CAPACITIES (for extendable) ===
    for gen in network.generators.index:
        p_nom_opt = network.generators.at[gen, 'p_nom_opt']
        p_nom = network.generators.at[gen, 'p_nom']
        carrier = network.generators.at[gen, 'carrier']
        
        results['generator_capacities'][gen] = {
            'initial_mw': p_nom,
            'optimal_mw': p_nom_opt,
            'expansion_mw': p_nom_opt - p_nom if p_nom_opt > p_nom else 0,
            'carrier': carrier
        }
    
    # === TIME SERIES DATA ===
    if hasattr(network, 'generators_t') and 'p' in network.generators_t:
        results['time_series']['generation'] = network.generators_t.p.copy()
    
    if hasattr(network, 'storage_units_t') and 'p' in network.storage_units_t:
        results['time_series']['storage_dispatch'] = network.storage_units_t.p.copy()
        if 'state_of_charge' in network.storage_units_t:
            results['time_series']['storage_soc'] = network.storage_units_t.state_of_charge.copy()
    
    if hasattr(network, 'loads_t') and 'p' in network.loads_t:
        results['time_series']['demand'] = network.loads_t.p.copy()
    
    return results


def compare_scenarios(
    results_dict: Dict[str, Dict[str, Any]]
) -> pd.DataFrame:
    """
    Create comparison table of multiple scenario results.
    
    Parameters
    ----------
    results_dict : dict
        Dictionary mapping scenario names to their results dictionaries
        
    Returns
    -------
    pd.DataFrame
        Comparison table with scenarios as rows and metrics as columns
    """
    comparison_data = []
    
    for scenario_name, results in results_dict.items():
        row = {
            'Scenario': scenario_name,
            'Total Cost (M€)': results['objective_value_eur'] / 1e6,
            'Total Demand (TWh)': results['total_demand_mwh'] / 1e6,
            'Renewable Share (%)': results['renewable_share'] * 100,
            'CO2 Emissions (kt)': results['co2_emissions_ton'] / 1000,
            'Curtailment (GWh)': results['curtailment_mwh'] / 1000
        }
        
        # Add generation by carrier
        for carrier, gen in results['total_generation_mwh'].items():
            row[f'{carrier.capitalize()} (GWh)'] = gen / 1000
        
        # Add storage utilization average
        if results['storage_utilization']:
            avg_util = np.mean(list(results['storage_utilization'].values())) * 100
            row['Storage Utilization (%)'] = avg_util
        
        comparison_data.append(row)
    
    df = pd.DataFrame(comparison_data)
    df.set_index('Scenario', inplace=True)
    
    return df


def save_results(
    results: Dict[str, Any],
    network: pypsa.Network,
    output_dir: str,
    scenario_name: str
) -> None:
    """
    Save optimization results to files.
    
    Parameters
    ----------
    results : dict
        Results dictionary from analyze_results
    network : pypsa.Network
        Solved network (for detailed outputs)
    output_dir : str
        Directory to save results
    scenario_name : str
        Name of the scenario (used in filenames)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save summary metrics
    summary = {
        'Metric': [],
        'Value': [],
        'Unit': []
    }
    
    metrics = [
        ('Total System Cost', results['objective_value_eur'] / 1e6, 'M€'),
        ('Total Electricity Demand', results['total_demand_mwh'] / 1e6, 'TWh'),
        ('Renewable Share', results['renewable_share'] * 100, '%'),
        ('CO2 Emissions', results['co2_emissions_ton'] / 1000, 'kt'),
        ('Curtailment', results['curtailment_mwh'] / 1000, 'GWh'),
    ]
    
    for metric, value, unit in metrics:
        summary['Metric'].append(metric)
        summary['Value'].append(value)
        summary['Unit'].append(unit)
    
    summary_df = pd.DataFrame(summary)
    summary_file = output_path / f"{scenario_name}_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"Saved summary: {summary_file}")
    
    # Save generation by carrier
    gen_df = pd.DataFrame([
        {'Carrier': carrier, 'Generation_GWh': gen / 1000}
        for carrier, gen in results['total_generation_mwh'].items()
    ])
    gen_file = output_path / f"{scenario_name}_generation.csv"
    gen_df.to_csv(gen_file, index=False)
    print(f"Saved generation: {gen_file}")
    
    # Save time series if available
    if 'time_series' in results and 'generation' in results['time_series']:
        ts_file = output_path / f"{scenario_name}_generation_timeseries.csv"
        results['time_series']['generation'].to_csv(ts_file)
        print(f"Saved generation time series: {ts_file}")
    
    if 'time_series' in results and 'storage_dispatch' in results['time_series']:
        ts_file = output_path / f"{scenario_name}_storage_timeseries.csv"
        results['time_series']['storage_dispatch'].to_csv(ts_file)
        print(f"Saved storage time series: {ts_file}")
    
    # Save network for further analysis
    network_file = output_path / f"{scenario_name}_network.nc"
    network.export_to_netcdf(network_file)
    print(f"Saved network: {network_file}")
