# ASHP Sizing and Selection Tool - Requirements

## Project Overview

A Python tool for processing Canadian weather data to calculate heating and cooling degree hours for Air Source Heat Pump (ASHP) sizing and selection.

### Purpose
- Download and process Canadian EPW (EnergyPlus Weather) files
- Calculate heating and cooling degree hours using multiple scenarios  
- Generate binned temperature analysis for HVAC system sizing
- Provide seasonal analysis for equipment selection

---

## ⚠️ CRITICAL: Read This First

**Before implementing any changes, read [CRITICAL_FIXES.md](./CRITICAL_FIXES.md)**

This document contains mandatory fixes that ensure calculation accuracy. Failure to implement these fixes will result in incorrect results.

---

## Core Functionality

### 1. Download Canadian Weather Files
- Source: http://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/CAN_Canada/
- Format: ZIP files containing EPW data (CWEC2020.zip)
- Method: Async downloads with retry logic
- Target: ~200+ Canadian weather stations

### 2. Process Weather Data
- Read EPW files (8,760 hourly data points per year)
- Calculate heating/cooling degree hours
- Apply conditional filtering based on daily/weekly averages
- Classify data by seasons
- Bin temperatures into ranges
- Generate seasonal hour counts

### 3. Generate Analysis Results
- 6 predefined scenarios (3 heating + 3 cooling)
- CSV outputs with aggregated data
- Ready for HVAC equipment sizing

---

## Scenarios

### Heating Degree Hour (HDH) Scenarios

| Scenario | Daily Threshold | Weekly Threshold | Temp Range | Bin Size | Conditions |
|----------|-----------------|------------------|------------|----------|------------|
| hdh_sc1  | 18.3°C         | N/A              | -29.2 to 12.8°C | 2.8°C | Daily only |
| hdh_sc2  | 14.9°C         | N/A              | -29.2 to 12.8°C | 2.8°C | Daily only |
| hdh_sc3  | 14.9°C         | 17.1°C           | -29.2 to 12.8°C | 2.8°C | Daily OR Weekly |

### Cooling Degree Hour (CDH) Scenarios  

| Scenario | Daily Threshold | Weekly Threshold | Temp Range | Bin Size | Conditions |
|----------|-----------------|------------------|------------|----------|------------|
| cdh_sc1  | 18.3°C         | N/A              | -29.2 to 12.8°C | 2.8°C | Daily only |
| cdh_sc2  | 22.8°C         | N/A              | -29.2 to 12.8°C | 2.8°C | Daily only |
| cdh_sc3  | 22.8°C         | 19.5°C           | **23.6 to 43.2°C** | 2.8°C | Daily OR Weekly |

---

## Degree Hour Calculation

### Formulas
- **Heating**: `max((threshold_temp - air_temp) / 24, 0)`  
- **Cooling**: `max((air_temp - threshold_temp) / 24, 0)`

### Conditional Logic
- **Daily condition**: Use daily average temperature vs threshold
- **Weekly condition**: Use weekly average temperature vs threshold  
- **Combined**: Apply heating/cooling only when conditions are met

---

## Output Format

### CSV Structure
```
hour,bin,degree_hour,temp_mean,count_hours_in_bin,count_hour_spring,count_hour_summer,count_hour_fall,count_hour_winter,city,state-prov
```

### Columns Explained
- `hour`: Hour of day (0-23)
- `bin`: Temperature bin range (e.g., "(-23.6, -20.8]")  
- `degree_hour`: Sum of degree hours for this hour-bin combination
- `temp_mean`: Average temperature in this bin
- `count_hours_in_bin`: Total hours with degree_hour > 0
- `count_hour_*`: Hours by season with degree_hour > 0
- `city`, `state-prov`: Weather station location

---

## Performance Requirements

### Download Performance
- **Target**: < 60 seconds for all Canadian files
- **Method**: 10 concurrent async downloads
- **Features**: Auto-retry, skip existing files, progress tracking

### Processing Performance  
- **Current**: 5-10 minutes for all scenarios
- **Optimized**: 1-2 minutes (with parallel processing)
- **Memory**: Process files individually to avoid buildup

---

## Dependencies

### Required Packages
```python
numpy>=1.21.0           # Numerical computations
pandas>=1.3.0           # Data manipulation  
requests>=2.26.0        # HTTP requests
beautifulsoup4>=4.10.0  # HTML parsing
aiohttp>=3.8.0          # Async HTTP client
```

### Installation
```bash
pip install -r requirements.txt
```

---

## Usage

### Basic Usage
```bash
python src/weather.py
```

### Custom Folders
```bash
python src/weather.py --weather-folder weather --results-folder outputs
```

### Performance Testing
```bash  
python src/weather.py --benchmark
```

---

## File Structure

```
project/
├── src/
│   ├── weather.py             # Main implementation  
│   ├── test_weather_v2.py     # Test single file (v2)
│   └── test_weather.py        # Test single file
├── data/
│   └── weather/               # Downloaded weather files (input data)
│       ├── CAN_AB_*.zip      # Alberta weather stations
│       ├── CAN_BC_*.zip      # British Columbia weather stations
│       └── ...               # All Canadian weather stations
├── results/                   # Generated CSV files (output results)
│   ├── hdh_sc1.csv           # Heating scenario 1 results
│   ├── hdh_sc2.csv           # Heating scenario 2 results  
│   ├── hdh_sc3.csv           # Heating scenario 3 results
│   ├── cdh_sc1.csv           # Cooling scenario 1 results
│   ├── cdh_sc2.csv           # Cooling scenario 2 results
│   └── cdh_sc3.csv           # Cooling scenario 3 results
├── resources/                 # Small reference data files
│   ├── hdh_sc1.csv           # Reference heating data
│   └── cdh_sc*.csv           # Reference cooling data
├── CRITICAL_FIXES.md          # **READ FIRST** - Critical implementation fixes
├── REQUIREMENTS.md            # This file - Project requirements
├── IMPLEMENTATION.md          # Detailed implementation guide
├── requirements.txt           # Python dependencies
└── README.md                 # User documentation
```

---

## Quality Assurance

### Validation Process
1. **Download test**: Verify file downloads work correctly
2. **Single file test**: Process one weather file with both versions
3. **Output comparison**: Use `diff` to ensure identical results
4. **Full scenario test**: Run all 6 scenarios and verify outputs
5. **Performance test**: Measure and validate speed improvements

### Success Criteria
- ✅ All scenarios produce identical results to original
- ✅ Processing time improved (target: 2-5x faster)  
- ✅ Memory usage stable or improved
- ✅ Error handling robust and informative
- ✅ Code maintainable and well-documented

---

## Next Steps

1. **Read [CRITICAL_FIXES.md](./CRITICAL_FIXES.md)** - Essential for correct implementation
2. **Review [IMPLEMENTATION.md](./IMPLEMENTATION.md)** - Detailed technical specifications  
3. **Test with single weather file** - Validate implementation before full deployment
4. **Run performance benchmarks** - Measure improvements
5. **Deploy with confidence** - Knowing results are mathematically identical

---

## Support

For implementation questions:
- Check existing test files for validation examples
- Reference CRITICAL_FIXES.md for known issues  
- Validate outputs match original before deployment

**Remember: Accuracy first, performance second.**