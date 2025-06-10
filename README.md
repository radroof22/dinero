# Portfolio Dashboard

A Streamlit-based dashboard for visualizing your investment portfolio across multiple brokerages. Currently supports Fidelity and Charles Schwab CSV exports.

## Features

- Combined view of positions across multiple brokerages
- Interactive visualizations using Plotly:
  - Profit/Loss by symbol with gradient coloring
  - Portfolio weight distribution by current value
  - Portfolio weight distribution by cost basis
  - Invested vs Cash allocation
- Formatted position table with current values and P&L
- Data source tracking with file metadata

## Setup

### Prerequisites

- [Mamba](https://mamba.readthedocs.io/en/latest/installation.html) or [Conda](https://docs.conda.io/en/latest/miniconda.html)
- CSV exports from your brokerage accounts (Fidelity and/or Charles Schwab)

### Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd mint
   ```

2. Create and activate the conda environment:
   ```bash
   mamba env create -f environment.yml
   mamba activate dinero
   ```

### Data Preparation

1. Create a `portfolio_data` directory in the project root:
   ```bash
   mkdir portfolio_data
   ```

2. Export your portfolio data from your brokerages:
   - For Fidelity: Save as `fidelity.csv`
   - For Charles Schwab: Save as `charles_schwab.csv`
   - Place both files in the `portfolio_data` directory

## Usage

1. Ensure your conda environment is activated:
   ```bash
   mamba activate dinero
   ```

2. Run the Streamlit app:
   ```bash
   streamlit run main.py
   ```

3. The dashboard will open in your default web browser, showing:
   - Raw positions table with formatted values
   - P&L visualization by symbol
   - Portfolio distribution charts
   - Cash vs Invested breakdown
   - Data source information

## Environment Details

The app requires the following key dependencies (managed by conda):
- Python ≥ 3.8
- pandas ≥ 2.0.0
- numpy ≥ 1.24.0
- streamlit ≥ 1.24.0
- plotly ≥ 5.15.0

For a complete list of dependencies, see `environment.yml`.

## Data Sources

The app expects portfolio data in CSV format:
- Fidelity: Standard account positions export
- Charles Schwab: Standard positions/holdings export (app will handle the header rows automatically)

Place your CSV files in the `portfolio_data` directory and ensure they are named appropriately:
- `fidelity.csv` for Fidelity exports
- `charles_schwab.csv` for Charles Schwab exports
