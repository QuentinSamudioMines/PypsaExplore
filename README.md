# Pypsa Energy System Optimization – Renewable Transition Case Study

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![PyPSA](https://img.shields.io/badge/PyPSA-0.25%2B-green)](https://pypsa.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

> **A pedagogical and professional demonstration of power system modeling with PyPSA, focusing on renewable energy integration and energy transition scenarios.**

---

## Objectives

This project simulates and optimizes a simplified electrical system based on a **fictional European region** (inspired by Iberian Peninsula characteristics). It demonstrates:

- **Network modeling** with PyPSA (buses, lines, generators, storage)
- **Economic dispatch optimization** minimizing total system costs
- **Renewable integration analysis** comparing baseline vs. high-renewable scenarios
- **Energy storage dispatch** for grid balancing
- **Research-grade visualization** of results

---

## System Architecture

### Geographic Layout

```
                    ┌─────────────────┐
                    │   NORTH ZONE    │  ← Wind-rich region (coastal/mountains)
                    │  (Load: 800 MW) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │  Transmission Line (400 kV) │
              │      Capacity: 1000 MW      │
              │      Reactance: 0.01 p.u.   │
              └──────────────┼──────────────┘
                             │
                    ┌────────┴────────┐
                    │   SOUTH ZONE    │  ← Solar-rich region
                    │  (Load: 1200 MW) │
                    └─────────────────┘
                           Central Hub
```

### Generation Mix

| Technology | North Zone | South Zone | Cost (€/MWh) | CO₂ (t/MWh) |
|------------|------------|------------|--------------|-------------|
| **Onshore Wind** | High potential | Low | 0 (fuel-free) | 0 |
| **Solar PV** | Medium | High | 0 (fuel-free) | 0 |
| **Gas CCGT** | Backup (300 MW) | Backup (500 MW) | 50 | 0.35 |
| **Battery Storage** | 200 MW / 800 MWh | 400 MW / 1600 MWh | - | 0 |

---

## Project Structure

```
pypsa-energy-project/
│
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── main.py                      # Entry point for running simulations
│
├── config/
│   └── scenario.yaml           # Scenario parameters (baseline, high_renewable)
│
├── data/
│   ├── demand_hourly.csv       # Hourly load profiles (8760h)
│   ├── renewables_profiles.csv # Wind/solar capacity factors
│   └── generators_costs.csv    # Marginal costs & investment costs
│
├── src/
│   ├── __init__.py
│   ├── config_loader.py        # YAML configuration parser
│   ├── load_data.py            # Data ingestion & validation
│   ├── build_network.py        # PyPSA network construction
│   ├── run_optimization.py     # Optimization engine
│   └── plotting.py             # Visualization utilities
│
├── results/
│   ├── plots/                  # Generated figures
│   └── outputs.csv             # Numerical results summary
│
├── notebooks/
│   └── exploratory_analysis.ipynb  # Interactive exploration
│
└── tests/
    └── test_network.py         # Unit tests for core functions
```

---

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager
- (Optional) Anaconda/Miniconda for environment management
- conda install -c conda-forge pypsa

### Setup

Use Python 3.11

```bash
# Créer le nouvel environnement
conda env create -f environment.yml

# Activer l'environnement
conda activate pypsa_env

# Installer le kernel Jupyter pour cet environnement
python -m ipykernel install --user --name=pypsa_env --display-name="Python (pypsa_env)"

# Install CBC solver (required for optimization)
# Windows (base method): 
conda install -c conda-forge coincbc
```

---

## Usage

### Quick Start

Run the complete analysis with default scenarios:

```bash
python main.py --scenario all --output results/
```

### Run Individual Scenarios

```bash
# Base scenario (standard version)
python main.py --scenario baseline --output results/baseline/

# High renewable scenario
python main.py --scenario high_renewable --output results/renewable/
```

### Compare Scenarios

```bash
python main.py --scenario all --compare --output results/
```

### Jupyter Notebook

For interactive exploration:

```bash
jupyter notebook notebooks/exploratory_analysis.ipynb
```

---

## Technical Details

### Optimization Formulation

The model solves a linear programming problem:

```
minimize    Σ_t Σ_g (marginal_cost_g × p_g,t) + Σ_s (storage_cost_s × |p_s,t|)
subject to  Σ_g p_g,t + Σ_s p_s,t = demand_t    ∀t  (energy balance)
            0 ≤ p_g,t ≤ P_max_g                    ∀g,t  (generation limits)
            SOC_s,t+1 = SOC_s,t + η×p_charge - p_discharge/η  (storage dynamics)
            -F_max ≤ f_l,t ≤ F_max                   ∀l,t  (line flows)
```

Where:
- `p_g,t`: Power output of generator g at time t
- `SOC_s,t`: State of charge of storage s at time t
- `f_l,t`: Power flow on line l at time t

### Solver Configuration

- **Default**: CBC (open-source, sufficient for this scale)
- **Recommended for larger models**: Gurobi or CPLEX
- **Typical solve time**: 45-120 seconds for 8760 time steps

---

## References

1. **PyPSA Documentation**: https://pypsa.readthedocs.io/
2. **Hörsch et al. (2018)**: "PyPSA: Python for Power System Analysis", Journal of Open Research Software
3. **Brown et al. (2018)**: "Synergies of sector coupling and transmission reinforcement", Renewable and Sustainable Energy Reviews
4. **Bussar et al. (2016)**: "Optimal allocation and dimensioning of hybrid energy storage systems", Applied Energy

---

## Contributing

Contributions are welcome! Areas for expansion:

- [ ] Add demand response modeling
- [ ] Implement multi-node European network
- [ ] Include hydrogen storage & Power-to-X
- [ ] Add weather year ensemble analysis
- [ ] Develop web dashboard for results

Please open an issue or pull request with your improvements.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Author

**Research Energy Modeling Group**  
*Institution: Mines ParisTech*  
*Contact: [quentin.samudio@minesparis.psl.eu]*

---

## Acknowledgments

- PyPSA development team (TUB, KIT)
- Open energy modeling community
- European power system datasets (ENTSO-E, Open Power System Data)
