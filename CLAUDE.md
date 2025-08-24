# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the ASHP (Air Source Heat Pump) Sizing and Selection Tool, a Python-based tool for processing and analyzing weather data to calculate heating and cooling degree hours for various scenarios. The tool downloads Canadian weather files in EPW (EnergyPlus Weather) format and processes them to generate degree-hour calculations for different temperature conditions.

## Environment Setup

The project supports both pip (recommended) and conda for environment management with Python 3.8+ and Jupyter notebooks.

### Setup Commands (pip - recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch Jupyter notebook
jupyter notebook

# Run weather processing tool
python src/weather_v2.py
```

### Setup Commands (conda - legacy)
```bash
# Create conda environment
conda env create --prefix ./env --file environment.yml

# Activate environment  
conda activate <path_to_your_environment>

# Launch Jupyter notebook
jupyter notebook

# Update environment (if needed)
conda env update --prefix ./env --file environment.yml --prune
```

## Project Structure

- **src/weather.py**: Legacy Python module with EPW file processing functions and degree-hour calculations
- **src/weather_v2.ipynb**: Main Jupyter notebook with updated degree-hour calculation functions and scenario processing
- **resources/**: Contains pre-generated CSV files with degree-hour data for different scenarios:
  - `hdh_sc1.csv`, `hdh_sc2.csv`, `hdh_sc3.csv`: Heating degree hour scenarios
  - `cdh_sc1.csv`, `cdh_sc2.csv`, `cdh_sc3.csv`: Cooling degree hour scenarios
- **environment.yml**: Conda environment specification with all dependencies

## Core Architecture

### Weather Data Processing
The tool processes EPW (EnergyPlus Weather) files containing hourly weather data with the following workflow:
1. **Data Download**: Downloads Canadian EPW files from climate.onebuilding.org
2. **Data Parsing**: Parses EPW format into pandas DataFrames with metadata extraction
3. **Degree Hour Calculation**: Calculates heating/cooling degree hours based on temperature thresholds
4. **Binning**: Groups temperatures into configurable bins for analysis
5. **Seasonal Analysis**: Categorizes data by season and counts hours in each bin/season

### Key Functions

#### From weather.py (legacy)
- `download_all_canadian_epw_files()`: Downloads EPW files from web
- `read_epw()`: Reads EPW files into pandas DataFrames
- `parse_epw()`: Parses EPW format with metadata extraction
- `create_heating_cooling_degree_hour()`: Legacy degree-hour calculation

#### From weather_v2.ipynb (current)
- `create_degree_hour()`: Main function for degree-hour calculations with multiple scenarios
  - Supports both heating and cooling degree hour calculations
  - Configurable temperature thresholds and binning
  - Daily and weekly mean temperature conditions
  - Seasonal hour counting

### Scenario Parameters
The tool supports multiple calculation scenarios with different:
- **Temperature thresholds**: Daily and weekly degree-day standards
- **Temperature ranges**: Min/max temperature ranges for binning
- **Bin intervals**: Temperature bin sizes (typically 2.8°C)
- **Conditions**: Daily mean vs weekly mean temperature requirements

## Data Processing Notes

- Weather data uses hourly temperature readings from EPW files
- Hours are converted from EPW convention (1-24) to standard (0-23)
- Degree hours are calculated as temperature difference divided by 24
- Seasonal categorization uses fixed date ranges for spring, summer, fall, winter
- Temperature bins include overflow bins for values outside specified ranges

## Dependencies

Key packages from environment.yml:
- pandas, numpy: Data processing
- requests, beautifulsoup4: Web scraping for EPW files
- jupyter notebook: Interactive development
- glob2, pathlib: File system operations
- zipfile: EPW file extraction

## Development Workflow

1. Use Jupyter notebook (weather_v2.ipynb) for interactive development
2. Core functions can be extracted to weather.py for reusable modules
3. Generated CSV files are saved to resources/ directory
4. Weather data is typically stored in energy_plus_weather/ directory