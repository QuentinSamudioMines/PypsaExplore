"""
Network builder module for PyPSA energy system optimization.

Constructs PyPSA Network objects from scenario configuration,
including buses, lines, generators, and storage units.
"""

import pypsa
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path


def build_network(
    scenario_config: Dict[str, Any],
    data: pd.DataFrame,
    scenario_name: Optional[str] = None
) -> pypsa.Network:
    """
    Build a PyPSA Network from scenario configuration and time series data.
    
    Parameters
    ----------
    scenario_config : dict
        Scenario configuration containing network topology, generators, storage
    data : pd.DataFrame
        Time series data with demand profiles and renewable capacity factors
    scenario_name : str, optional
        Name of the scenario (for logging and metadata)
        
    Returns
    -------
    pypsa.Network
        Configured PyPSA network ready for optimization
    """
    print(f"Building network for scenario: {scenario_name or 'unnamed'}")
    
    # Initialize network
    n = pypsa.Network()
    
    # Set time index from data
    n.set_snapshots(data.index)
    
    # Get network topology from config
    network_topo = scenario_config.get('network', {})
    
    # === ADD BUSES ===
    buses = network_topo.get('buses', [])
    for bus in buses:
        n.add(
            "Bus",
            name=bus['name'],
            carrier=bus.get('carrier', 'AC'),
            x=bus.get('x', 0),
            y=bus.get('y', 0),
            country=bus.get('country', '')
        )
        print(f"  Added bus: {bus['name']}")
    
    # === ADD LINES ===
    lines = network_topo.get('lines', [])
    for line in lines:
        n.add(
            "Line",
            name=line['name'],
            bus0=line['bus0'],
            bus1=line['bus1'],
            carrier=line.get('carrier', 'AC'),
            s_nom=line.get('s_nom', 1000),  # MVA
            x=line.get('x', 0.1),  # pu
            r=line.get('r', 0.01),  # pu
            length=line.get('length', 100)  # km
        )
        print(f"  Added line: {line['name']} ({line['bus0']} <-> {line['bus1']})")
    
    # === ADD CARRIERS ===
    carriers = network_topo.get('carriers', ['AC'])
    for carrier in carriers:
        # Add with default CO2 and color attributes
        co2_attrs = {
            'AC': 0, 'wind': 0, 'solar': 0, 'gas': 0.35,
            'battery': 0, 'hydro': 0, 'nuclear': 0
        }
        color_attrs = {
            'AC': 'gray', 'wind': 'skyblue', 'solar': 'gold',
            'gas': 'brown', 'battery': 'green', 'hydro': 'blue',
            'nuclear': 'purple'
        }
        
        n.add(
            "Carrier",
            name=carrier,
            co2_emissions=co2_attrs.get(carrier, 0),
            color=color_attrs.get(carrier, 'black')
        )
    
    # === ADD LOADS (DEMAND) ===
    demand_config = scenario_config.get('demand', {})
    for bus_name, bus_demand in demand_config.items():
        profile_column = bus_demand.get('profile_column', f'demand_{bus_name.lower()}')
        
        if profile_column in data.columns:
            p_set = data[profile_column]
        else:
            # Use base load if no profile
            p_set = pd.Series(bus_demand.get('base_load_mw', 1000), index=n.snapshots)
            print(f"  Warning: No demand profile found for {bus_name}, using constant load")
        
        n.add(
            "Load",
            name=f"{bus_name}_Load",
            bus=bus_name,
            p_set=p_set
        )
        print(f"  Added load: {bus_name}_Load (avg: {p_set.mean():.1f} MW)")
    
    # === ADD GENERATORS ===
    generators = scenario_config.get('generators', [])
    for gen in generators:
        gen_name = gen['name']
        bus = gen['bus']
        carrier = gen['carrier']
        
        # Capacity limit (fixed or extendable)
        p_nom = gen.get('p_nom', 100)
        p_nom_extendable = gen.get('p_nom_extendable', False)
        p_nom_max = gen.get('p_nom_max', p_nom * 10) if p_nom_extendable else p_nom
        
        # Cost parameters
        marginal_cost = gen.get('marginal_cost', 0)
        capital_cost = gen.get('capital_cost', 0)
        
        # Renewable profiles (p_max_pu)
        p_max_pu = 1.0
        if 'p_max_pu_column' in gen:
            profile_col = gen['p_max_pu_column']
            if profile_col in data.columns:
                p_max_pu = data[profile_col]
            else:
                print(f"  Warning: Profile {profile_col} not found, using p_max_pu=1.0")
        
        # CO2 emissions
        co2_emissions = gen.get('co2_emissions', 0)
        
        # Efficiency (for dispatchable generators)
        efficiency = gen.get('efficiency', 1.0)
        
        # Minimum stable generation
        p_min_pu = gen.get('p_min_pu', 0) if carrier in ['gas', 'coal', 'nuclear'] else 0
        
        # Build generator
        n.add(
            "Generator",
            name=gen_name,
            bus=bus,
            carrier=carrier,
            p_nom=p_nom,
            p_nom_extendable=p_nom_extendable,
            p_nom_max=p_nom_max,
            p_min_pu=p_min_pu,
            p_max_pu=p_max_pu,
            marginal_cost=marginal_cost,
            capital_cost=capital_cost,
            efficiency=efficiency,
            co2_emissions=co2_emissions
        )
        
        extend_info = " (extendable)" if p_nom_extendable else ""
        print(f"  Added generator: {gen_name} ({carrier}, {p_nom} MW){extend_info}")
    
    # === ADD STORAGE UNITS ===
    storage_units = scenario_config.get('storage_units', [])
    for storage in storage_units:
        storage_name = storage['name']
        bus = storage['bus']
        carrier = storage['carrier']
        
        # Power and energy capacity
        p_nom = storage.get('p_nom', 100)
        p_nom_extendable = storage.get('p_nom_extendable', False)
        p_nom_max = storage.get('p_nom_max', p_nom * 5) if p_nom_extendable else p_nom
        
        max_hours = storage.get('max_hours', 4)  # Duration in hours
        
        # Efficiency
        efficiency_store = storage.get('efficiency_store', 0.9)
        efficiency_dispatch = storage.get('efficiency_dispatch', 0.9)
        standing_loss = storage.get('standing_loss', 0)  # per hour
        
        # Costs
        capital_cost = storage.get('capital_cost', 0)
        marginal_cost = storage.get('marginal_cost', 0)
        
        # Cycling constraint
        cyclic = storage.get('cyclic_state_of_charge', False)
        
        n.add(
            "StorageUnit",
            name=storage_name,
            bus=bus,
            carrier=carrier,
            p_nom=p_nom,
            p_nom_extendable=p_nom_extendable,
            p_nom_max=p_nom_max,
            max_hours=max_hours,
            efficiency_store=efficiency_store,
            efficiency_dispatch=efficiency_dispatch,
            standing_loss=standing_loss,
            capital_cost=capital_cost,
            marginal_cost=marginal_cost,
            cyclic_state_of_charge=cyclic
        )
        
        e_nom = p_nom * max_hours
        extend_info = " (extendable)" if p_nom_extendable else ""
        print(f"  Added storage: {storage_name} ({p_nom} MW, {e_nom} MWh{extend_info})")
    
    # === ADD GLOBAL CONSTRAINTS (if any) ===
    global_constraints = scenario_config.get('global_constraints', [])
    for constraint in global_constraints:
        n.add(
            "GlobalConstraint",
            name=constraint.get('name', 'constraint'),
            type=constraint.get('type', 'primary_energy'),
            carrier_attribute=constraint.get('carrier_attribute', 'co2_emissions'),
            sense=constraint.get('sense', '<='),
            constant=constraint.get('constant', 0)
        )
        print(f"  Added global constraint: {constraint.get('name')}")
    
    print(f"\nNetwork summary:")
    print(f"  Buses: {len(n.buses)}")
    print(f"  Lines: {len(n.lines)}")
    print(f"  Generators: {len(n.generators)}")
    print(f"  Storage Units: {len(n.storage_units)}")
    print(f"  Time steps: {len(n.snapshots)}")
    
    return n


def export_network_to_csv(network: pypsa.Network, output_dir: str) -> None:
    """
    Export network components to CSV files for inspection.
    
    Parameters
    ----------
    network : pypsa.Network
        Network to export
    output_dir : str
        Directory to save CSV files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Export main components
    network.buses.to_csv(output_path / "buses.csv")
    network.lines.to_csv(output_path / "lines.csv")
    network.generators.to_csv(output_path / "generators.csv")
    network.storage_units.to_csv(output_path / "storage_units.csv")
    network.loads.to_csv(output_path / "loads.csv")
    
    print(f"Network exported to: {output_path}")
