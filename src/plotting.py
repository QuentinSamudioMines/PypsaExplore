"""
Visualization module for PyPSA energy system analysis.

Provides professional-quality plots for generation mix, storage operation,
network diagrams, and scenario comparisons.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd
import numpy as np
import pypsa
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# Set professional style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")


def plot_generation_mix(
    network: pypsa.Network,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 6),
    title: Optional[str] = None
) -> plt.Figure:
    """
    Create stacked area plot of generation by carrier over time.
    
    Parameters
    ----------
    network : pypsa.Network
        Solved PyPSA network
    output_path : str, optional
        Path to save figure. If None, figure is not saved.
    figsize : tuple
        Figure dimensions (width, height)
    title : str, optional
        Custom plot title
        
    Returns
    -------
    matplotlib.figure.Figure
        Generated figure object
    """
    if not hasattr(network, 'generators_t') or 'p' not in network.generators_t:
        raise ValueError("Network must be solved before plotting")
    
    # Aggregate generation by carrier
    carriers = network.generators.carrier.unique()
    generation_by_carrier = pd.DataFrame(index=network.snapshots)
    
    colors = {
        'wind': '#4A90D9',
        'solar': '#F5A623',
        'gas': '#8B4513',
        'coal': '#2C2C2C',
        'nuclear': '#9013FE',
        'hydro': '#50E3C2',
        'battery': '#7ED321'
    }
    
    for carrier in carriers:
        gen_carrier = network.generators[network.generators.carrier == carrier]
        if len(gen_carrier) > 0:
            gen_names = gen_carrier.index.tolist()
            generation_by_carrier[carrier] = network.generators_t.p[gen_names].sum(axis=1)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Stacked area plot
    ax.stackplot(
        generation_by_carrier.index,
        *[generation_by_carrier[col] for col in generation_by_carrier.columns],
        labels=[c.capitalize() for c in generation_by_carrier.columns],
        colors=[colors.get(c, '#999999') for c in generation_by_carrier.columns],
        alpha=0.8
    )
    
    # Styling
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Power (MW)', fontsize=12, fontweight='bold')
    ax.set_title(title or 'Generation Mix Over Time', fontsize=14, fontweight='bold', pad=20)
    
    # Legend
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Format x-axis
    if len(network.snapshots) > 168:  # More than a week
        ax.xaxis.set_major_locator(plt.MaxNLocator(12))
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved generation mix plot: {output_path}")
    
    return fig


def plot_storage_operation(
    network: pypsa.Network,
    storage_name: Optional[str] = None,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 8),
    title: Optional[str] = None
) -> plt.Figure:
    """
    Plot storage dispatch and state of charge over time.
    
    Creates a dual-axis plot showing:
    - Charge/discharge power (MW)
    - State of charge (MWh)
    
    Parameters
    ----------
    network : pypsa.Network
        Solved PyPSA network
    storage_name : str, optional
        Name of specific storage unit to plot. If None, plots all.
    output_path : str, optional
        Path to save figure
    figsize : tuple
        Figure dimensions
    title : str, optional
        Custom plot title
        
    Returns
    -------
    matplotlib.figure.Figure
        Generated figure
    """
    if not hasattr(network, 'storage_units_t') or 'p' not in network.storage_units_t:
        raise ValueError("Network has no storage or is not solved")
    
    # Select storage units to plot
    if storage_name:
        storage_units = [storage_name]
    else:
        storage_units = network.storage_units.index.tolist()
    
    # Create figure with subplots
    n_storages = len(storage_units)
    fig, axes = plt.subplots(n_storages, 1, figsize=figsize, sharex=True)
    
    if n_storages == 1:
        axes = [axes]
    
    for idx, storage in enumerate(storage_units):
        ax = axes[idx]
        ax2 = ax.twinx()
        
        # Power dispatch
        power = network.storage_units_t.p[storage]
        ax.fill_between(power.index, 0, power, where=(power >= 0),
                        color='#7ED321', alpha=0.6, label='Charging')
        ax.fill_between(power.index, 0, power, where=(power < 0),
                        color='#D0021B', alpha=0.6, label='Discharging')
        
        # State of charge
        if 'state_of_charge' in network.storage_units_t:
            soc = network.storage_units_t.state_of_charge[storage]
            ax2.plot(soc.index, soc, color='#4A90D9', linewidth=2, label='State of Charge')
            ax2.fill_between(soc.index, 0, soc, color='#4A90D9', alpha=0.1)
        
        # Labels
        ax.set_ylabel('Power (MW)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('State of Charge (MWh)', fontsize=11, fontweight='bold', color='#4A90D9')
        ax.set_title(f'{storage}', fontsize=12, fontweight='bold')
        
        # Zero line
        ax.axhline(y=0, color='black', linewidth=0.5)
        
        # Legends
        ax.legend(loc='upper left', fontsize=9)
        ax2.legend(loc='upper right', fontsize=9)
    
    axes[-1].set_xlabel('Time', fontsize=12, fontweight='bold')
    
    # Overall title
    fig.suptitle(title or 'Storage Operation', fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved storage operation plot: {output_path}")
    
    return fig


def plot_network_diagram(
    network: pypsa.Network,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    title: Optional[str] = None
) -> plt.Figure:
    """
    Create schematic diagram of the network topology.
    
    Shows buses, lines, generators, and storage with capacity annotations.
    
    Parameters
    ----------
    network : pypsa.Network
        PyPSA network (solved or unsolved)
    output_path : str, optional
        Path to save figure
    figsize : tuple
        Figure dimensions
    title : str, optional
        Custom plot title
        
    Returns
    -------
    matplotlib.figure.Figure
        Generated figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Get bus positions - convert to numpy arrays for integer indexing
    x_pos = network.buses['x'].values if 'x' in network.buses.columns else np.arange(len(network.buses))
    y_pos = network.buses['y'].values if 'y' in network.buses.columns else np.zeros(len(network.buses))
    
    # Plot buses
    for i, bus in enumerate(network.buses.index):
        ax.scatter(x_pos[i], y_pos[i], s=2000, c='white', edgecolors='black', linewidth=2, zorder=3)
        ax.annotate(bus, (x_pos[i], y_pos[i]), ha='center', va='center',
                   fontsize=12, fontweight='bold', zorder=4)
        
        # Add generators at this bus
        bus_gens = network.generators[network.generators.bus == bus]
        gen_texts = []
        for carrier in bus_gens.carrier.unique():
            carrier_gens = bus_gens[bus_gens.carrier == carrier]
            total_cap = carrier_gens.p_nom.sum()
            expandable = any(carrier_gens.p_nom_extendable)
            
            icon = {'wind': 'Wind', 'solar': 'PV', 'gas': 'Gas', 'coal': 'Coal',
                   'nuclear': 'Nuc', 'hydro': 'Hydro'}.get(carrier, carrier)
            ext_marker = ' (+)' if expandable else ''
            gen_texts.append(f"{icon}: {total_cap:.0f} MW{ext_marker}")
        
        # Add storage at this bus
        bus_storage = network.storage_units[network.storage_units.bus == bus]
        for storage in bus_storage.index:
            cap = bus_storage.at[storage, 'p_nom']
            duration = bus_storage.at[storage, 'max_hours']
            expandable = bus_storage.at[storage, 'p_nom_extendable']
            ext_marker = ' (+)' if expandable else ''
            gen_texts.append(f"Battery: {cap:.0f} MW / {cap*duration:.0f} MWh{ext_marker}")
        
        if gen_texts:
            ax.annotate('\n'.join(gen_texts),
                       xy=(x_pos[i], y_pos[i]),
                       xytext=(0, -40),
                       textcoords='offset points',
                       ha='center', va='top',
                       fontsize=9,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))
    
    # Plot lines
    for line in network.lines.index:
        bus0 = network.lines.at[line, 'bus0']
        bus1 = network.lines.at[line, 'bus1']
        
        idx0 = network.buses.index.get_loc(bus0)
        idx1 = network.buses.index.get_loc(bus1)
        
        capacity = network.lines.at[line, 's_nom']
        
        ax.plot([x_pos[idx0], x_pos[idx1]], [y_pos[idx0], y_pos[idx1]],
               'k-', linewidth=3, alpha=0.6, zorder=1)
        
        # Line capacity label
        mid_x = (x_pos[idx0] + x_pos[idx1]) / 2
        mid_y = (y_pos[idx0] + y_pos[idx1]) / 2
        ax.annotate(f'{capacity:.0f} MW',
                   xy=(mid_x, mid_y),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    # Styling
    ax.set_xlim(min(x_pos) - 1, max(x_pos) + 1)
    ax.set_ylim(min(y_pos) - 1.5, max(y_pos) + 1)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Title
    fig.suptitle(title or 'Network Topology', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved network diagram: {output_path}")
    
    return fig


def plot_daily_profile(
    network: pypsa.Network,
    day: Optional[int] = None,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 8),
    title: Optional[str] = None
) -> plt.Figure:
    """
    Plot detailed 24-hour profile for a specific day.
    
    Shows generation stack, demand, storage operation, and net load.
    
    Parameters
    ----------
    network : pypsa.Network
        Solved PyPSA network
    day : int, optional
        Day number to plot (1-based). If None, uses first day.
    output_path : str, optional
        Path to save figure
    figsize : tuple
        Figure dimensions
    title : str, optional
        Custom plot title
        
    Returns
    -------
    matplotlib.figure.Figure
        Generated figure
    """
    if not hasattr(network, 'generators_t') or 'p' not in network.generators_t:
        raise ValueError("Network must be solved before plotting")
    
    # Select day
    if day is None:
        day = 1
    
    start_idx = (day - 1) * 24
    end_idx = day * 24
    
    if end_idx > len(network.snapshots):
        raise ValueError(f"Day {day} exceeds available data ({len(network.snapshots)//24} days)")
    
    snapshots = network.snapshots[start_idx:end_idx]
    
    # Create figure
    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True,
                          gridspec_kw={'height_ratios': [2, 1, 1]})
    
    colors = {
        'wind': '#4A90D9', 'solar': '#F5A623', 'gas': '#8B4513',
        'coal': '#2C2C2C', 'nuclear': '#9013FE', 'hydro': '#50E3C2'
    }
    
    # === GENERATION STACK ===
    ax1 = axes[0]
    carriers = network.generators.carrier.unique()
    
    generation_by_carrier = pd.DataFrame(index=snapshots)
    for carrier in carriers:
        gen_carrier = network.generators[network.generators.carrier == carrier]
        if len(gen_carrier) > 0:
            gen_names = gen_carrier.index.tolist()
            gen_data = network.generators_t.p[gen_names].loc[snapshots].sum(axis=1)
            generation_by_carrier[carrier] = gen_data
    
    ax1.stackplot(
        range(24),
        *[generation_by_carrier.loc[snapshots, col].values for col in generation_by_carrier.columns],
        labels=[c.capitalize() for c in generation_by_carrier.columns],
        colors=[colors.get(c, '#999999') for c in generation_by_carrier.columns],
        alpha=0.8
    )
    
    # Add demand line
    total_demand = network.loads_t.p.loc[snapshots].sum(axis=1).values
    ax1.plot(range(24), total_demand, 'k-', linewidth=2, label='Demand', linestyle='--')
    
    ax1.set_ylabel('Power (MW)', fontsize=11, fontweight='bold')
    ax1.set_title('Generation & Demand', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # === STORAGE OPERATION ===
    ax2 = axes[1]
    if hasattr(network, 'storage_units_t') and 'p' in network.storage_units_t:
        total_storage_power = network.storage_units_t.p.loc[snapshots].sum(axis=1)
        ax2.fill_between(range(24), 0, total_storage_power,
                        where=(total_storage_power >= 0),
                        color='#7ED321', alpha=0.6, label='Charging')
        ax2.fill_between(range(24), 0, total_storage_power,
                        where=(total_storage_power < 0),
                        color='#D0021B', alpha=0.6, label='Discharging')
        ax2.axhline(y=0, color='black', linewidth=0.5)
        ax2.set_ylabel('Storage Power (MW)', fontsize=11, fontweight='bold')
        ax2.legend(loc='upper left', fontsize=9)
        ax2.grid(True, alpha=0.3)
    
    # === RESIDUAL LOAD ===
    ax3 = axes[2]
    renewable_gen = generation_by_carrier[['wind', 'solar']].sum(axis=1).values
    residual_load = total_demand - renewable_gen
    ax3.plot(range(24), residual_load, color='#D0021B', linewidth=2, label='Residual Load')
    ax3.fill_between(range(24), 0, residual_load, color='#D0021B', alpha=0.2)
    ax3.axhline(y=0, color='black', linewidth=0.5)
    ax3.set_ylabel('Residual Load (MW)', fontsize=11, fontweight='bold')
    ax3.set_xlabel('Hour of Day', fontsize=11, fontweight='bold')
    ax3.set_xticks(range(0, 24, 3))
    ax3.legend(loc='upper left', fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Overall title
    date_str = snapshots[0].strftime('%Y-%m-%d')
    fig.suptitle(title or f'Daily Profile - {date_str} (Day {day})',
                fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved daily profile plot: {output_path}")
    
    return fig


def plot_scenario_comparison(
    comparison_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10),
    title: Optional[str] = None
) -> plt.Figure:
    """
    Create comprehensive comparison plots for multiple scenarios.
    
    Parameters
    ----------
    comparison_df : pd.DataFrame
        DataFrame with scenarios as index and metrics as columns
    output_path : str, optional
        Path to save figure
    figsize : tuple
        Figure dimensions
    title : str, optional
        Custom plot title
        
    Returns
    -------
    matplotlib.figure.Figure
        Generated figure
    """
    # Determine which metrics to plot
    metrics_to_plot = []
    for col in comparison_df.columns:
        if any(keyword in col.lower() for keyword in ['cost', 'demand', 'renewable', 'co2', 'curtailment']):
            metrics_to_plot.append(col)
    
    n_metrics = len(metrics_to_plot)
    n_cols = 2
    n_rows = (n_metrics + 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_metrics > 1 else [axes]
    
    scenarios = comparison_df.index.tolist()
    colors = plt.cm.Set2(np.linspace(0, 1, len(scenarios)))
    
    for idx, metric in enumerate(metrics_to_plot):
        ax = axes[idx]
        
        values = comparison_df[metric].values
        bars = ax.bar(scenarios, values, color=colors, edgecolor='black', linewidth=1.5)
        
        # Add value labels on bars
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=10, fontweight='bold')
        
        ax.set_ylabel(metric, fontsize=11, fontweight='bold')
        ax.set_title(metric.replace('_', ' '), fontsize=12, fontweight='bold')
        ax.grid(True, axis='y', alpha=0.3)
        
        # Rotate x labels if many scenarios
        if len(scenarios) > 3:
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
    
    # Hide unused subplots
    for idx in range(n_metrics, len(axes)):
        axes[idx].axis('off')
    
    fig.suptitle(title or 'Scenario Comparison', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved scenario comparison plot: {output_path}")
    
    return fig


def create_all_plots(
    network: pypsa.Network,
    results: Dict[str, Any],
    output_dir: str,
    scenario_name: str
) -> List[str]:
    """
    Generate all standard plots for a scenario.
    
    Parameters
    ----------
    network : pypsa.Network
        Solved PyPSA network
    results : dict
        Results dictionary from analyze_results
    output_dir : str
        Directory to save plots
    scenario_name : str
        Name of the scenario (used in filenames)
        
    Returns
    -------
    list
        List of paths to saved plot files
    """
    output_path = Path(output_dir) / "plots"
    output_path.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    
    # 1. Network diagram (before solving is fine)
    try:
        filepath = output_path / f"{scenario_name}_network.png"
        plot_network_diagram(network, str(filepath),
                           title=f'{scenario_name.replace("_", " ").title()} - Network Topology')
        saved_files.append(str(filepath))
    except Exception as e:
        print(f"Warning: Could not create network diagram: {e}")
    
    # 2. Generation mix (requires solved network)
    try:
        filepath = output_path / f"{scenario_name}_generation_mix.png"
        plot_generation_mix(network, str(filepath),
                         title=f'{scenario_name.replace("_", " ").title()} - Generation Mix')
        saved_files.append(str(filepath))
    except Exception as e:
        print(f"Warning: Could not create generation mix plot: {e}")
    
    # 3. Storage operation
    if len(network.storage_units) > 0:
        try:
            filepath = output_path / f"{scenario_name}_storage.png"
            plot_storage_operation(network, output_path=str(filepath),
                                 title=f'{scenario_name.replace("_", " ").title()} - Storage Operation')
            saved_files.append(str(filepath))
        except Exception as e:
            print(f"Warning: Could not create storage plot: {e}")
    
    # 4. Daily profile (first day)
    try:
        filepath = output_path / f"{scenario_name}_daily_profile.png"
        plot_daily_profile(network, day=1, output_path=str(filepath),
                         title=f'{scenario_name.replace("_", " ").title()} - Daily Profile')
        saved_files.append(str(filepath))
    except Exception as e:
        print(f"Warning: Could not create daily profile plot: {e}")
    
    print(f"\nGenerated {len(saved_files)} plots for scenario '{scenario_name}'")
    return saved_files
