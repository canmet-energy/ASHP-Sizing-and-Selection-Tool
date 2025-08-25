# Implementation Guide

## Overview

This document provides detailed technical specifications for implementing the ASHP weather processing tool. 

**⚠️ IMPORTANT**: Read [CRITICAL_FIXES.md](./CRITICAL_FIXES.md) before implementing to avoid calculation errors.

---

## Architecture

### Core Components

1. **Download Module** - Async weather file downloading
2. **EPW Parser** - Weather file reading and parsing
3. **Calculator Module** - Degree hour calculations
4. **Aggregator Module** - Data binning and summarization
5. **Scenario Runner** - Configuration and execution management

### Data Flow
```
Weather Files → EPW Parser → Calculator → Aggregator → CSV Output
     ↑              ↓            ↓          ↓           ↓
Download Module   DataFrame   Degree    Binned      Results
                              Hours     Data
```

---

## Function Specifications

### 1. Download Functions

#### `download_all_canadian_epw_files()`
**Purpose**: Async download of Canadian weather files  
**Parameters**:
- `save_location`: Directory path (default: 'output')
- `file_suffix`: File filter (default: 'CWEC2020.zip')  
- `max_concurrent`: Concurrent limit (default: 10)

**Key Implementation Details**:
```python
# Required User-Agent
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36'}

# Session configuration
session = aiohttp.ClientSession(
    timeout=aiohttp.ClientTimeout(total=300),  # 5 minutes
    connector=aiohttp.TCPConnector(limit=20)
)

# Required status messages
print(f"✓ Downloaded: {filename}")      # Success
print(f"⚠ Retry {attempt}/{max_retries}") # Retry  
print(f"✗ Failed to download {filename}") # Failure
```

### 2. EPW Processing Functions

#### `read_epw(filename, coerce_year=None)`
**Purpose**: Read EPW file into pandas DataFrame with metadata  
**Returns**: `Tuple[pd.DataFrame, Dict]`

**Critical Implementation**:
```python
# EPW column structure (35 columns)
colnames = ['year', 'month', 'day', 'hour', 'minute', 'data_source_unct',
           'temp_air', 'temp_dew', 'relative_humidity', 'atmospheric_pressure',
           # ... (see full list in original requirements)
           ]

# Header processing
firstline = csvdata.readline()  # Read metadata line
data = pd.read_csv(csvdata, skiprows=6, header=0, names=colnames)  # Skip 6 more lines

# Hour normalization (CRITICAL)
df['hour'] = df['hour'] - 1  # Convert 1-24 to 0-23
```

### 3. Degree Hour Calculations

#### `calculate_degree_hours(df, config)`
**Purpose**: Core heating/cooling calculations  
**Formula Implementation**:
```python
if config.degree_type == DegreeHourType.HEATING:
    df['degree_hour'] = np.maximum((config.daily_threshold - df['temp_air']) / 24.0, 0.0)
else:  # COOLING  
    df['degree_hour'] = np.maximum((df['temp_air'] - config.daily_threshold) / 24.0, 0.0)
```

#### `calculate_mean_temperatures(df)` ⚠️ CRITICAL
**Purpose**: Daily and weekly temperature averages  
**MUST use non-overlapping blocks (not rolling windows)**:
```python
# Daily means (24-hour blocks)
df['daily_mean_temp_c'] = 0.0
for i in range(0, 8791, 24):
    end_idx = min(i + 24, len(df))
    if end_idx > i:
        daily_mean = df['temp_air'].iloc[i:end_idx].mean()
        df['daily_mean_temp_c'].iloc[i:end_idx] = daily_mean

# Weekly means (168-hour blocks) - NON-OVERLAPPING
df['weekly_mean_temp_c'] = 0.0  
for i in range(0, 8791, 168):
    end_idx = min(i + 168, len(df))
    if end_idx > i:
        weekly_mean = df['temp_air'].iloc[i:end_idx].mean()
        df['weekly_mean_temp_c'].iloc[i:end_idx] = weekly_mean
```

#### `apply_conditional_filters(df, config)` ⚠️ CRITICAL
**Purpose**: Apply heating/cooling start/stop logic  
**CRITICAL**: Cooling logic is easily inverted - see CRITICAL_FIXES.md

```python
if config.degree_type == DegreeHourType.COOLING:
    if config.daily_condition and not config.weekly_condition:
        mask = (df['daily_mean_temp_c'] > config.daily_threshold) == False
    elif config.daily_condition or config.weekly_condition:
        daily_mask = df['daily_mean_temp_c'] > config.daily_threshold
        weekly_mask = df['weekly_mean_temp_c'] > config.weekly_threshold
        mask = (daily_mask | weekly_mask) == False
    
    df.loc[mask, 'degree_hour'] = 0.0
```

### 4. Seasonal Classification ⚠️ CRITICAL

#### `classify_seasons(df)` 
**Purpose**: Assign seasons to each hour  
**MUST use datetime comparison (not string comparison)**:
```python
# Create datetime objects (CRITICAL)
df['py_year'] = 2020
df['py_dateInt'] = df['py_year'].astype(str) + df['month'].astype(str).str.zfill(2) + df['day'].astype(str).str.zfill(2)
df['py_datetime'] = pd.to_datetime(df['py_dateInt'], format='%Y%m%d')

# Nested np.where logic (EXACT match to v2)
df['season'] = np.where(
    (df['py_datetime'] >= pd.to_datetime('20200101', format='%Y%m%d')) & 
    (df['py_datetime'] <= pd.to_datetime('20200320', format='%Y%m%d')), 'winter',
    np.where(
        (df['py_datetime'] >= pd.to_datetime('20200321', format='%Y%m%d')) &
        (df['py_datetime'] <= pd.to_datetime('20200620', format='%Y%m%d')), 'spring',
        # ... continue nested pattern
    )
)
```

### 5. Temperature Binning ⚠️ CRITICAL

#### `create_temperature_bins(df, config)`
**Purpose**: Organize temperatures into bins for analysis  
**CRITICAL**: Overflow bin insertion method matters:
```python
# Create bin boundaries
bins_list = np.arange(min_temp, max_temp, config.bin_size).tolist()

# Add overflow bins (EXACT method from v2)
bins_list.insert(0, -100)  # Use exact value -100
bins_list.insert(len(bins_list), 100)  # Use insert(), NOT append()

# Create bins  
df['bin'] = pd.cut(df['temp_air'], bins_list)
```

### 6. Data Aggregation ⚠️ CRITICAL

#### `aggregate_results(df)` 
**Purpose**: Create final summary tables  
**MUST use lambda functions exactly like v2**:
```python
# Initialize count columns (REQUIRED)
df['count_hours_in_bin'] = 0
df['count_hour_spring'] = 0
df['count_hour_summer'] = 0  
df['count_hour_fall'] = 0
df['count_hour_winter'] = 0

# Aggregation with lambda functions (EXACT match)
df_dh = df.groupby(['hour', 'bin']).agg({
    'degree_hour': 'sum',
    'temp_air': 'mean',
    'count_hours_in_bin': lambda g: df['degree_hour'].loc[g.index][(df['degree_hour'] > 0.0)].count(),
    'count_hour_spring': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'spring') & (df['degree_hour'] > 0.0)].count(),
    'count_hour_summer': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'summer') & (df['degree_hour'] > 0.0)].count(),
    'count_hour_fall': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'fall') & (df['degree_hour'] > 0.0)].count(),
    'count_hour_winter': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'winter') & (df['degree_hour'] > 0.0)].count()
}).reset_index()

# Post-processing (REQUIRED)
df_dh.rename(columns={"temp_air": "temp_mean"}, inplace=True)
df_dh['temp_mean'].fillna(0.0, inplace=True)
df_dh['count_hours_in_bin'].fillna(0.0, inplace=True)
# ... fill all count columns
```

---

## Configuration Classes

### ScenarioConfig
```python
@dataclass
class ScenarioConfig:
    name: str
    degree_type: DegreeHourType  # HEATING or COOLING
    daily_threshold: float
    weekly_threshold: float
    temp_range: Tuple[float, float]
    bin_size: float
    daily_condition: bool
    weekly_condition: bool
```

### Predefined Scenarios
```python
SCENARIOS = {
    'hdh_sc1': ScenarioConfig('hdh_sc1', HEATING, 18.3, 18.3, (-29.2, 12.8), 2.8, True, False),
    'hdh_sc2': ScenarioConfig('hdh_sc2', HEATING, 14.9, 18.3, (-29.2, 12.8), 2.8, True, False),  
    'hdh_sc3': ScenarioConfig('hdh_sc3', HEATING, 14.9, 17.1, (-29.2, 12.8), 2.8, True, True),
    'cdh_sc1': ScenarioConfig('cdh_sc1', COOLING, 18.3, 18.3, (-29.2, 12.8), 2.8, True, False),
    'cdh_sc2': ScenarioConfig('cdh_sc2', COOLING, 22.8, 18.3, (-29.2, 12.8), 2.8, True, False),
    'cdh_sc3': ScenarioConfig('cdh_sc3', COOLING, 22.8, 19.5, (23.6, 43.2), 2.8, True, True),  # Different temp range
}
```

---

## Processing Pipeline

### Single File Processing
```python
def process_single_file(file_path: str, config: ScenarioConfig) -> pd.DataFrame:
    # 1. Read EPW file
    df, meta = read_epw(file_path)
    df['hour'] = df['hour'] - 1
    
    # 2. Apply processing pipeline (EXACT ORDER)
    df = calculate_degree_hours(df, config)
    df = calculate_mean_temperatures(df)  # Loops, not vectorized
    df = apply_conditional_filters(df, config) 
    df = classify_seasons(df)  # Datetime logic
    df = create_temperature_bins(df, config)
    
    # 3. Initialize count columns
    df['count_hours_in_bin'] = 0
    # ... initialize all count columns
    
    # 4. Add metadata  
    df['city'] = meta['city']
    df['state-prov'] = meta['state-prov']
    
    # 5. Aggregate
    result_df = aggregate_results(df)  # Lambda functions
    
    # 6. Add metadata to results
    result_df['city'] = meta['city']
    result_df['state-prov'] = meta['state-prov']
    
    return result_df
```

### Parallel Processing (Safe Optimization)
```python
def process_all_files_parallel(folder_location: str, config: ScenarioConfig, num_processes: int = None):
    files = glob.glob(os.path.join(folder_location, '*.zip'))
    
    if num_processes is None:
        num_processes = min(cpu_count(), len(files))
    
    # Prepare arguments
    args = [(file_path, config) for file_path in files]
    
    # Process in parallel
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_single_file, args)
    
    # Combine results
    valid_results = [r for r in results if r is not None]
    combined_df = pd.concat([r for r in valid_results], ignore_index=True)
    
    return combined_df
```

---

## Error Handling

### Download Errors
```python
async def download_with_retry(session, url, filename, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    # Success logic
                    return True
                else:
                    print(f"⚠ HTTP {response.status} for {filename}")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠ Retry {attempt + 1}/{max_retries} for {filename}: {e}")
                await asyncio.sleep(1)
            else:
                print(f"✗ Failed to download {filename}: {e}")
    return False
```

### Processing Errors
```python
def process_file_safe(file_path: str, config: ScenarioConfig):
    try:
        return process_single_file(file_path, config)
    except Exception as e:
        print(f'File {file_path} failed by {e}')
        return None  # Continue processing other files
```

---

## Performance Optimizations

### Safe Optimizations ✅
1. **Parallel file processing** - Process different files simultaneously
2. **Async downloads** - Download files concurrently  
3. **Memory management** - Delete intermediate DataFrames
4. **Connection pooling** - Reuse HTTP connections

### Dangerous Optimizations ❌ 
1. **Vectorized mean calculations** - Changes weekly mean logic
2. **Rolling windows** - Different from non-overlapping blocks
3. **String date comparisons** - Different from datetime logic
4. **Pre-calculated aggregation** - Different from lambda functions

---

## Testing and Validation

### Unit Tests
```python
def test_degree_hour_calculation():
    # Test heating calculation
    config = ScenarioConfig('test', HEATING, 18.3, 18.3, (-29.2, 12.8), 2.8, True, False)
    df = pd.DataFrame({'temp_air': [15.0, 20.0]})
    result = calculate_degree_hours(df, config)
    
    expected = [(18.3 - 15.0) / 24, 0.0]  # [0.1375, 0.0]
    assert np.allclose(result['degree_hour'], expected)

def test_weekly_mean_calculation():
    # Test non-overlapping blocks
    df = pd.DataFrame({'temp_air': list(range(168))})  # 0-167
    result = calculate_mean_temperatures(df)
    
    # First 168 hours should all have same weekly mean
    expected_mean = np.mean(range(168))
    assert result['weekly_mean_temp_c'].iloc[0] == expected_mean
    assert result['weekly_mean_temp_c'].iloc[167] == expected_mean
```

### Integration Tests  
```python
def test_scenario_matches_original():
    # Process same file with both versions
    original_result = process_with_weather_v2('test_file.zip', 'cdh_sc3')
    optimized_result = process_with_weather_v4('test_file.zip', 'cdh_sc3')
    
    # Results must be identical
    pd.testing.assert_frame_equal(original_result, optimized_result)
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Read CRITICAL_FIXES.md thoroughly
- [ ] Implement all mandatory fixes  
- [ ] Test with single weather file
- [ ] Compare outputs with `diff` - must be identical
- [ ] Run all 6 scenarios and verify results
- [ ] Benchmark performance improvements

### Post-Deployment
- [ ] Monitor for any calculation discrepancies
- [ ] Validate performance gains are realized
- [ ] Ensure error handling works correctly
- [ ] Document any new issues discovered

---

## Support and Maintenance

### Troubleshooting
1. **Different results**: Check CRITICAL_FIXES.md implementation
2. **Performance issues**: Verify parallel processing setup
3. **Download failures**: Check network and user-agent settings
4. **Memory problems**: Ensure proper DataFrame cleanup

### Code Maintenance
- Keep critical calculation logic unchanged
- Update only performance and usability features  
- Always validate against original implementation
- Document any discovered edge cases

**Remember: Correctness is more important than speed.**