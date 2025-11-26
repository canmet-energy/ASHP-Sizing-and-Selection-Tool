# ASHP Sizing and Selection Tool

## 📖 What This Tool Does (For Mechanical Engineers)

This Python tool helps **mechanical engineers** size and select **Air Source Heat Pumps (ASHP)** by processing Canadian weather data. It downloads real weather files from across Canada and calculates **heating and cooling degree hours** - the key metrics you need for proper HVAC equipment sizing.

### Why Do You Need This?
- ✅ **Accurate Equipment Sizing**: Get precise heating/cooling loads for any Canadian location
- ✅ **Multiple Design Scenarios**: Compare different operating strategies (6 scenarios included)
- ✅ **Ready-to-Use Data**: Outputs CSV files you can directly use in Excel or other engineering software
- ✅ **Seasonal Analysis**: Understand equipment performance across different seasons
- ✅ **Binned Temperature Data**: See exactly how many hours your equipment will operate at each temperature

---

## 🏗️ Engineering Background

### What Are Degree Hours?
**Degree hours** measure the cumulative heating or cooling demand over time:
- **Heating Degree Hours (HDH)**: How much heating energy is needed below a threshold temperature
- **Cooling Degree Hours (CDH)**: How much cooling energy is needed above a threshold temperature

### The 6 Analysis Scenarios
This tool processes weather data using 6 predefined scenarios optimized for Canadian climates:

| Scenario | Type | Daily Threshold | Weekly Threshold | Purpose |
|----------|------|----------------|------------------|---------|
| **hdh_sc1** | Heating | 18.3°C | None | Conservative heating design |
| **hdh_sc2** | Heating | 14.9°C | None | Standard heating design |
| **hdh_sc3** | Heating | 14.9°C | 17.1°C | Optimized heating with weekly logic |
| **cdh_sc1** | Cooling | 18.3°C | None | Conservative cooling design |
| **cdh_sc2** | Cooling | 22.8°C | None | Standard cooling design |
| **cdh_sc3** | Cooling | 22.8°C | 19.5°C | Optimized cooling with weekly logic |

### Temperature Binning
Weather data is organized into **2.8°C temperature bins** (e.g., -23.6°C to -20.8°C) so you can see:
- How many hours your equipment operates at each temperature range
- Peak demand periods and typical operating conditions
- Seasonal variations in heating/cooling loads

---

## 💻 Getting Started (Step-by-Step)

### Step 1: Install dependancies

**Install Git** (if not already installed):
   - Windows: Download from [git-scm.com](https://git-scm.com/download/win)
     
**Install Python 3.10** (if not already installed) using Powershell:
   ```bash
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex; uv --native-tls python install 3.10" 
   ```

### Step 2: Clone the workspace to a folder on your computer, and change directory into that folder.  
   ```bash
   git clone https://github.com/canmet-energy/ASHP-Sizing-and-Selection-Tool.git;cd ASHP-Sizing-and-Selection-Tool
   ```

### Step 3: Set Up Python Environment
   ```bash
    uv venv .venv; uv pip install -r requirements.txt
   ```
### Step 4: Run the weather.py file. 
   ```bash
   uv run src/weather.py
   ```



## Tips

**Custom folders** (if you want to organize files differently):
```bash
python src/weather.py --weather-folder weather --results-folder outputs
```

---

## 📁 What Folders Are Created

After running the tool, you'll see this folder structure:

```
ASHP-Sizing-and-Selection-Tool-1/
├── 📁 data/
│   └── 📁 weather/              # Downloaded weather files (INPUT)
│       ├── CAN_AB_Calgary.zip  # Calgary, Alberta weather data
│       ├── CAN_BC_Vancouver.zip # Vancouver, BC weather data
│       └── ... (~200 more Canadian cities)
├── 📁 results/                  # Analysis results (OUTPUT)
│   ├── 📄 hdh_sc1.csv          # Heating scenario 1 results
│   ├── 📄 hdh_sc2.csv          # Heating scenario 2 results  
│   ├── 📄 hdh_sc3.csv          # Heating scenario 3 results
│   ├── 📄 cdh_sc1.csv          # Cooling scenario 1 results
│   ├── 📄 cdh_sc2.csv          # Cooling scenario 2 results
│   └── 📄 cdh_sc3.csv          # Cooling scenario 3 results
├── 📁 src/                      # Source code
│   └── 📄 weather.py           # Main program
└── 📄 README.md                # This file
```

### 📁 data/weather/ (Input Files)
- **Size**: ~500MB total
- **Format**: ZIP files containing EPW (EnergyPlus Weather) data
- **Content**: 8,760 hours of weather data per location (1 full year)
- **Source**: Downloaded automatically from Canadian government weather databases

### 📁 results/ (Output Files) 
- **Size**: ~50MB total
- **Format**: CSV files you can open in Excel
- **Content**: Processed degree hour calculations for all Canadian locations

---

## 📊 Understanding the Output Files

Each CSV file contains the following columns:

| Column | Example | Description |
|--------|---------|-------------|
| **hour** | 14 | Hour of day (0-23, where 14 = 2 PM) |
| **bin** | "(-23.6, -20.8]" | Temperature range in °C |
| **degree_hour** | 2.5 | Sum of degree hours for this temperature/time |
| **temp_mean** | -22.2 | Average temperature in this bin (°C) |
| **count_hours_in_bin** | 45 | Total hours with heating/cooling needed |
| **count_hour_spring** | 12 | Hours in spring (Mar-May) |
| **count_hour_summer** | 0 | Hours in summer (Jun-Aug) |
| **count_hour_fall** | 18 | Hours in fall (Sep-Nov) |
| **count_hour_winter** | 15 | Hours in winter (Dec-Feb) |
| **city** | Calgary | Weather station location |
| **state-prov** | AB | Province/territory code |

### 🧮 How to Use the Results

**Example: Sizing a Heat Pump for Calgary**

1. **Open** `results/hdh_sc2.csv` in Excel
2. **Filter** for Calgary: `city = Calgary`
3. **Find peak demand**: Look for highest `degree_hour` values
4. **Check operating hours**: Use `count_hour_winter` to see winter operation
5. **Size equipment**: Total degree hours ÷ design temperature difference = heating capacity needed

**Practical Engineering Application**:
```
If Calgary shows 2,500 degree hours at -20°C bin:
- Design indoor temperature: 20°C
- Temperature difference: 20°C - (-20°C) = 40°C
- Required capacity: 2,500 ÷ 40 = 62.5 kW-hours of heating needed
```

---

## ⚡ How Long Does It Take?

**First Run** (downloads all weather data):
- Download time: ~2-5 minutes (depends on internet speed)
- Processing time: ~2-3 minutes
- **Total: ~5-8 minutes**

**Subsequent Runs** (weather data already downloaded):
- Processing time: ~2-3 minutes
- **Total: ~2-3 minutes**

**What's Happening During Processing:**
1. 📥 Downloading weather files from Canadian government servers
2. 🔄 Processing 200+ weather stations (8,760 hours each)
3. 🧮 Calculating degree hours for 6 scenarios
4. 📊 Binning temperatures and counting seasonal hours
5. 💾 Writing CSV results

---

## 🔧 Troubleshooting

### Common Issues

**Problem**: `python: command not found`
```bash
# Try python3 instead
python3 src/weather.py
```

**Problem**: `ModuleNotFoundError: No module named 'pandas'`
```bash
# Make sure virtual environment is activated and packages installed
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

**Problem**: Download errors or timeouts
```bash
# Run again - the tool will skip already downloaded files
python src/weather.py
```

**Problem**: Permission errors on Windows
```bash
# Run Command Prompt as Administrator
```

### Getting Help

1. **Check the log output** - the tool shows progress and any errors
2. **Verify internet connection** - downloads require stable internet
3. **Check disk space** - need ~1GB free space for weather data
4. **Try a single location first** - modify the code to test with one city

---

## 🎯 For Advanced Users

### Custom Scenarios
You can modify the scenarios in `src/weather.py` by changing these parameters:
- `daily_threshold`: Temperature threshold for daily conditions
- `weekly_threshold`: Temperature threshold for weekly conditions  
- `temp_range`: Min/max temperatures for analysis
- `bin_size`: Temperature bin width (default: 2.8°C)

### Performance Optimization
The tool automatically:
- Downloads files in parallel (10 concurrent downloads)
- Processes cities in parallel
- Skips already-downloaded files
- Shows progress bars and timing information

### Integration with Other Tools
The CSV outputs work directly with:
- **Excel**: Open CSV files for analysis and graphing
- **MATLAB**: Use `readtable()` to import data
- **R**: Use `read.csv()` for statistical analysis
- **Power BI**: Import CSV files for visualization
- **AutoCAD/Revit**: Export degree hour data for building energy models

---

## 📚 Further Reading

### Canadian Weather Data Sources
- **Environment and Climate Change Canada**: Official weather data source
- **CWEC2016**: Canadian Weather for Energy Calculations (2016 format)
- **EPW Files**: EnergyPlus Weather data format standard

### HVAC Design Standards
- **ASHRAE Handbook**: Fundamentals chapter on heating/cooling loads
- **CSA C448**: Canadian standard for heat pump performance
- **NBC**: National Building Code energy efficiency requirements

### Heat Pump Sizing Guidelines
- Size equipment for 90-95% of peak load (not 100%)
- Consider backup heating for extreme cold periods
- Account for defrost cycles in cooling degree hour calculations
- Use seasonal performance factors (HSPF/SEER) for final sizing

---

## 🤝 Contributing

Found a bug? Have a suggestion? Want to add more scenarios?
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---



**Remember**: Always validate results with local building codes and engineering judgment. This tool provides data for informed decision-making, but final equipment sizing should be reviewed by a licensed professional engineer.
