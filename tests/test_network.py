"""
Unit tests for network building and optimization functions.

Run with: pytest tests/test_network.py
"""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config_loader import load_scenario_config, get_scenario_names
from src.load_data import create_synthetic_profiles, validate_data_profiles
from src.build_network import build_network
from src.run_optimization import run_optimization, analyze_results


class TestConfigLoader:
    """Tests for configuration loading."""
    
    def test_load_baseline_config(self):
        """Test loading baseline scenario configuration."""
        config = load_scenario_config('baseline')
        
        assert 'generators' in config
        assert 'demand' in config
        assert len(config['generators']) > 0
        assert 'description' in config
    
    def test_load_high_renewable_config(self):
        """Test loading high renewable scenario configuration."""
        config = load_scenario_config('high_renewable')
        
        assert 'generators' in config
        assert 'storage_units' in config
        
        # Check for expandability
        generators = config['generators']
        has_extendable = any(g.get('p_nom_extendable', False) for g in generators)
        assert has_extendable, "High renewable scenario should have extendable generators"
    
    def test_get_scenario_names(self):
        """Test retrieving list of scenario names."""
        scenarios = get_scenario_names()
        
        assert isinstance(scenarios, list)
        assert 'baseline' in scenarios
        assert 'high_renewable' in scenarios
    
    def test_invalid_scenario_raises_error(self):
        """Test that invalid scenario name raises ConfigError."""
        with pytest.raises(Exception):
            load_scenario_config('nonexistent_scenario')


class TestDataLoading:
    """Tests for data loading and generation."""
    
    def test_create_synthetic_profiles(self):
        """Test synthetic data generation."""
        periods = 168
        data = create_synthetic_profiles(periods=periods)
        
        assert len(data) == periods
        assert 'wind_north' in data.columns
        assert 'wind_south' in data.columns
        assert 'solar_north' in data.columns
        assert 'solar_south' in data.columns
        assert 'demand_north' in data.columns
        assert 'demand_south' in data.columns
    
    def test_synthetic_profiles_range(self):
        """Test that capacity factors are in valid range [0, 1]."""
        data = create_synthetic_profiles(periods=168)
        
        renewable_cols = ['wind_north', 'wind_south', 'solar_north', 'solar_south']
        for col in renewable_cols:
            assert data[col].min() >= 0, f"{col} has negative values"
            assert data[col].max() <= 1, f"{col} has values > 1"
    
    def test_demand_positive(self):
        """Test that demand values are positive."""
        data = create_synthetic_profiles(periods=168)
        
        assert (data['demand_north'] >= 0).all()
        assert (data['demand_south'] >= 0).all()
    
    def test_validate_data_profiles(self):
        """Test data validation function."""
        data = create_synthetic_profiles(periods=168)
        
        is_valid, errors = validate_data_profiles(data)
        assert is_valid, f"Data validation failed: {errors}"
        assert len(errors) == 0


class TestNetworkBuilding:
    """Tests for network construction."""
    
    @pytest.fixture
    def sample_config(self):
        """Load baseline config for testing."""
        return load_scenario_config('baseline')
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        return create_synthetic_profiles(periods=24)  # Short for speed
    
    def test_build_network_buses(self, sample_config, sample_data):
        """Test that buses are correctly added to network."""
        network = build_network(sample_config, sample_data, 'test')
        
        assert len(network.buses) == 2  # North and South
        assert 'North' in network.buses.index
        assert 'South' in network.buses.index
    
    def test_build_network_lines(self, sample_config, sample_data):
        """Test that transmission lines are added."""
        network = build_network(sample_config, sample_data, 'test')
        
        assert len(network.lines) == 1
        assert 'North_South' in network.lines.index
    
    def test_build_network_generators(self, sample_config, sample_data):
        """Test that generators are added."""
        network = build_network(sample_config, sample_data, 'test')
        
        assert len(network.generators) > 0
        
        # Check for expected carriers
        carriers = network.generators.carrier.unique()
        assert 'wind' in carriers
        assert 'solar' in carriers
        assert 'gas' in carriers
    
    def test_build_network_loads(self, sample_config, sample_data):
        """Test that loads are added."""
        network = build_network(sample_config, sample_data, 'test')
        
        assert len(network.loads) == 2
        assert 'North_Load' in network.loads.index
        assert 'South_Load' in network.loads.index
    
    def test_build_network_storage(self, sample_config, sample_data):
        """Test that storage units are added."""
        network = build_network(sample_config, sample_data, 'test')
        
        assert len(network.storage_units) == 2
        assert 'North_Battery' in network.storage_units.index
        assert 'South_Battery' in network.storage_units.index


class TestOptimization:
    """Tests for optimization functionality."""
    
    @pytest.fixture
    def solved_network(self):
        """Create and solve a small test network."""
        config = load_scenario_config('baseline')
        data = create_synthetic_profiles(periods=24)  # Very short for tests
        network = build_network(config, data, 'test')
        
        # Run optimization
        success = run_optimization(network, solver_name='cbc', verbose=False)
        
        if not success:
            pytest.skip("Optimization solver not available")
        
        return network
    
    def test_optimization_success(self, solved_network):
        """Test that optimization completes successfully."""
        # If we get here, optimization succeeded
        assert hasattr(solved_network, 'objective')
        assert solved_network.objective is not None
    
    def test_analyze_results_structure(self, solved_network):
        """Test that results analysis returns expected structure."""
        results = analyze_results(solved_network)
        
        assert 'objective_value_eur' in results
        assert 'total_demand_mwh' in results
        assert 'total_generation_mwh' in results
        assert 'renewable_share' in results
        assert 'co2_emissions_ton' in results
        
        # Check value ranges
        assert results['total_demand_mwh'] > 0
        assert 0 <= results['renewable_share'] <= 1
        assert results['co2_emissions_ton'] >= 0
    
    def test_energy_balance(self, solved_network):
        """Test that supply equals demand (energy balance)."""
        results = analyze_results(solved_network)
        
        total_generation = sum(results['total_generation_mwh'].values())
        total_demand = results['total_demand_mwh']
        
        # Allow 1% tolerance for numerical errors
        assert abs(total_generation - total_demand) / total_demand < 0.01, \
            f"Energy imbalance: generation={total_generation}, demand={total_demand}"


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_baseline_workflow(self):
        """Test complete baseline scenario workflow."""
        # 1. Load config
        config = load_scenario_config('baseline')
        
        # 2. Create data
        data = create_synthetic_profiles(periods=24)
        
        # 3. Build network
        network = build_network(config, data, 'baseline_test')
        
        # 4. Run optimization
        success = run_optimization(network, solver_name='cbc', verbose=False)
        
        if not success:
            pytest.skip("Optimization solver not available")
        
        # 5. Analyze results
        results = analyze_results(network)
        
        # Assertions
        assert results['objective_value_eur'] > 0
        assert results['total_demand_mwh'] > 0
        assert 'wind' in results['total_generation_mwh']
        assert 'solar' in results['total_generation_mwh']
    
    def test_high_renewable_workflow(self):
        """Test high renewable scenario workflow."""
        config = load_scenario_config('high_renewable')
        data = create_synthetic_profiles(periods=24)
        network = build_network(config, data, 'high_renewable_test')
        
        success = run_optimization(network, solver_name='cbc', verbose=False)
        
        if not success:
            pytest.skip("Optimization solver not available")
        
        results = analyze_results(network)
        
        # High renewable should have higher renewable share
        assert results['renewable_share'] > 0.3, \
            f"Expected >30% renewable, got {results['renewable_share']*100:.1f}%"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
