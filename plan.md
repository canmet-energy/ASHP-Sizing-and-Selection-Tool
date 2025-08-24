# Implementation Plan: Advanced Cooling Degree Day Logic

## Task Understanding ✅
Replace the current CDH_SC3 weekly mean temperature logic (19.5°C threshold) with a sophisticated dual-gate cooling degree day system using:
- **Daily threshold**: 23.9°C (updated from 22.8°C) 
- **7-day rolling CDD**: CDD_week > 2.0 threshold
- **OR logic**: Either condition triggers data storage
- **New CDD formula**: `CDD_Daily = MAX((T_DA - 19.44), 0)` where base = 19.44°C (67°F)

### What is CDD_Week?
**CDD_Week** is a **7-day rolling average of daily cooling degree days** that serves as a **sustained cooling demand indicator**:

**Conceptual Purpose:**
- Captures cumulative cooling demand over the past week
- Provides smoothed indicator of sustained warm weather periods that justify running cooling equipment
- Prevents cooling systems from cycling on/off due to single hot days

**Detailed Calculation:**
```
CDD_week = (Σ(i=0 to 6) CDD_Daily[current_day - i]) / 7
```
- Sum includes current day + previous 6 days (total 7 days)
- Each CDD_Daily = `MAX((daily_avg_temp - 19.44°C), 0)`
- For early days (first 6 days of dataset): use available data and adjust denominator

**Engineering Logic:**
- **High CDD_week (>2.0)**: Indicates sustained warm weather requiring consistent cooling
- **Low CDD_week (≤2.0)**: Brief hot days don't justify continuous cooling operation
- **Smoothing effect**: Eliminates equipment cycling from temporary temperature spikes

## Current vs. New Logic Comparison

### **Before (Current CDH_SC3)**
```python
# Current implementation in apply_conditional_filters()
if config.daily_condition or config.weekly_condition:
    daily_mask = df['daily_mean_temp_c'] > 22.8  # Current daily threshold
    weekly_mask = df['weekly_mean_temp_c'] > 19.5  # Simple weekly average
    mask = (daily_mask | weekly_mask) == False
```

### **After (New CDH_SC3)**
```python
# New implementation with CDD logic
if config.daily_condition or config.weekly_condition:
    daily_mask = df['daily_mean_temp_c'] > 23.9  # Updated daily threshold
    cdd_week_mask = df['CDD_week'] > 2.0  # New 7-day rolling CDD
    mask = (daily_mask | cdd_week_mask) == False
```

**Key Changes:**
- Daily threshold: 22.8°C → 23.9°C
- Weekly logic: Simple temperature average → Sophisticated CDD rolling average
- Trigger: Weekly temp > 19.5°C → CDD_week > 2.0

## Implementation Steps

### 1. Analysis Phase
- Review current CDH_SC3 implementation in weather_v4.py
- Identify the apply_conditional_filters function logic for cooling scenarios
- Understand current temperature binning and data storage mechanisms

### 2. New CDD Calculation Functions

#### `calculate_daily_cdd(df: pd.DataFrame) -> pd.DataFrame`
```python
def calculate_daily_cdd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily cooling degree days using base temperature 19.44°C"""
    df['CDD_Daily'] = np.maximum(df['daily_mean_temp_c'] - 19.44, 0.0)
    return df
```

#### `calculate_weekly_rolling_cdd(df: pd.DataFrame) -> pd.DataFrame` 
```python
def calculate_weekly_rolling_cdd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate 7-day rolling average of CDD_Daily"""
    # Handle edge cases for first 6 days
    df['CDD_week'] = 0.0
    for i in range(len(df)):
        # Determine how many days of data we have (max 7)
        days_available = min(i + 1, 7)
        start_idx = max(0, i - 6)
        
        # Calculate rolling average with proper denominator
        df['CDD_week'].iloc[i] = df['CDD_Daily'].iloc[start_idx:i+1].sum() / days_available
    return df
```

**Edge Case Handling:**
- Days 1-6: Use available data and adjust denominator (1-6 days instead of 7)
- Missing data: Fill with 0.0 for CDD calculations, flag in logs
- Data gaps: Handle gracefully, continue processing with available data

### 3. Update CDH_SC3 Configuration

**Current CDH_SC3 Configuration:**
```python
'cdh_sc3': ScenarioConfig(
    name='cdh_sc3',
    degree_type=DegreeHourType.COOLING,
    daily_threshold=22.8,      # Old threshold
    weekly_threshold=19.5,     # Simple weekly temp threshold
    temp_range=(23.6, 43.2),
    bin_size=2.8,
    daily_condition=True,
    weekly_condition=True      # Uses simple weekly logic
),
```

**New CDH_SC3 Configuration:**
```python
'cdh_sc3': ScenarioConfig(
    name='cdh_sc3',
    degree_type=DegreeHourType.COOLING,
    daily_threshold=23.9,      # Updated threshold
    weekly_threshold=2.0,      # Now represents CDD_week threshold
    temp_range=(23.6, 43.2),  # Unchanged
    bin_size=2.8,              # Unchanged
    daily_condition=True,
    weekly_condition=True,     # Now uses CDD logic
    cdd_base_temp=19.44       # New parameter for CDD calculations
),
```

**Configuration Changes:**
- Add `cdd_base_temp` parameter to ScenarioConfig dataclass
- Update daily_threshold: 22.8 → 23.9
- Repurpose weekly_threshold: temp threshold → CDD_week threshold
- No changes to temp_range or bin_size

### 4. Implement Dual-Gate Logic
- Replace weekly mean temperature logic with new dual-gate system
- Implement OR logic: `(daily_mean > 23.9) OR (CDD_week > 2.0)`
- Ensure entire day (24 hours) is flagged when either condition is met

### 5. Update Processing Pipeline

**Current Processing Flow:**
```
1. Read EPW file → df
2. Calculate degree hours → df['degree_hour']  
3. Calculate daily/weekly means → df['daily_mean_temp_c'], df['weekly_mean_temp_c']
4. Apply conditional filters → filter df['degree_hour'] based on conditions
5. Classify seasons → df['season']
6. Create temperature bins → df['bin']
7. Aggregate results → final CSV
```

**New Processing Flow (CDH_SC3 only):**
```
1. Read EPW file → df
2. Calculate degree hours → df['degree_hour']
3. Calculate daily/weekly means → df['daily_mean_temp_c'], df['weekly_mean_temp_c'] 
4. **NEW**: Calculate daily CDD → df['CDD_Daily']
5. **NEW**: Calculate 7-day rolling CDD → df['CDD_week'] 
6. Apply conditional filters → filter using CDD_week instead of weekly_mean_temp_c
7. Classify seasons → df['season']
8. Create temperature bins → df['bin'] 
9. Aggregate results → final CSV
```

**Integration Points:**
- Insert CDD calculations after step 3 (daily/weekly means)
- Modify `apply_conditional_filters()` to detect CDH_SC3 and use CDD logic
- All other scenarios (CDH_SC1, CDH_SC2, HDH_*) unchanged

**Data Structure Changes:**
- Add temporary columns: `df['CDD_Daily']`, `df['CDD_week']`
- These columns dropped before final aggregation (not in CSV output)
- No changes to final CSV structure

### 6. Testing & Validation

#### **Excel Reference Validation**
- **Target**: Row 194 of provided Excel spreadsheet contains reference CDD_week calculation
- **Test approach**: Process same weather data and compare CDD_week values
- **Tolerance**: ±0.001 for floating-point differences
- **Key validation points**:
  - CDD_Daily calculations for individual days
  - CDD_week rolling average for days 1-6 (edge cases)
  - CDD_week rolling average for day 7+ (full 7-day window)

#### **Unit Tests**
```python
def test_daily_cdd_calculation():
    """Test CDD_Daily = MAX((daily_avg - 19.44), 0)"""
    # Test cases: above/below/equal to base temp
    
def test_weekly_rolling_cdd():
    """Test 7-day rolling average with edge cases"""
    # Test first 6 days (partial data)
    # Test day 7+ (full rolling window)
    
def test_cdh_sc3_dual_gate():
    """Test OR logic: (daily > 23.9) OR (CDD_week > 2.0)"""
    # Test each condition independently
    # Test both conditions together
```

#### **Integration Tests**
- **Scenario isolation**: Verify CDH_SC1, CDH_SC2, HDH_* scenarios unchanged
- **Before/after comparison**: Compare CDH_SC3 results with current implementation
- **End-to-end test**: Full pipeline with real weather data

#### **Performance Impact Assessment**
- Measure additional processing time for CDD calculations
- Memory usage for temporary CDD columns
- Parallel processing compatibility

### 7. Documentation Updates
- Update scenario descriptions in code comments
- Document new CDD calculation methodology
- Update CRITICAL_FIXES.md if needed
- Add validation notes referencing Excel sample

## Technical Considerations

### **Compatibility & Safety**
- Maintain backward compatibility with existing scenarios
- Preserve existing folder structure (data/weather, results/)
- Ensure thread-safe implementation for parallel processing
- Handle missing data gracefully
- Validate that change only affects CDH_SC3, not other scenarios

### **Implementation Challenges**

#### **Daily Data Processing**
- **Challenge**: Weather data is hourly, but CDD calculations need daily grouping
- **Solution**: Use existing daily_mean_temp_c calculation, extend with CDD_Daily

#### **Rolling Window Memory**
- **Challenge**: Need 7 days of data for rolling calculation
- **Solution**: Process sequentially, maintain sliding window in memory

#### **DataFrame Operations**
- **Challenge**: Avoid pandas SettingWithCopyWarning for temporary columns
- **Solution**: Use proper .loc indexing for CDD column assignments

#### **Scenario Detection**
- **Challenge**: Distinguish CDH_SC3 from other cooling scenarios in apply_conditional_filters()
- **Solution**: Check scenario name or add scenario type flag

### **Performance Optimizations**
- **Rolling calculation**: Use pandas .rolling() if possible for better performance
- **Memory management**: Drop temporary CDD columns after filtering
- **Parallel processing**: Ensure CDD calculations work with multiprocessing

### **Validation Strategy**
- **Mathematical verification**: Cross-check CDD formulas against engineering standards
- **Excel reference**: Exact match for provided sample calculation  
- **Regression testing**: Ensure other scenarios produce identical results
- **Edge case testing**: First 6 days, missing data, temperature extremes

## Expected Outcome
CDH_SC3 will use sophisticated cooling degree day logic instead of simple weekly temperature thresholds, providing more accurate cooling load calculations for HVAC equipment sizing in Canadian climate conditions.