# Implementation Plan: Advanced Cooling Degree Day Logic

## Task Understanding ✅
Replace the current CDH_SC3 weekly mean temperature logic (19.5°C threshold) with a sophisticated dual-gate cooling degree day system using:
- **Daily threshold**: 23.9°C (updated from 22.8°C) 
- **7-day rolling CDD**: CDD_week > 2.0 threshold
- **OR logic**: Either condition triggers data storage
- **New CDD formula**: `CDD_Daily = MAX((T_DA - 19.44), 0)` where base = 19.44°C (67°F)

## Implementation Steps

### 1. Analysis Phase
- Review current CDH_SC3 implementation in weather_v4.py
- Identify the apply_conditional_filters function logic for cooling scenarios
- Understand current temperature binning and data storage mechanisms

### 2. New CDD Calculation Functions
- Create `calculate_daily_cdd()` function using formula: `MAX((daily_avg - 19.44), 0)`
- Create `calculate_weekly_rolling_cdd()` function for 7-day rolling average
- Handle edge cases for first 6 days of dataset (adjust denominator)

### 3. Update CDH_SC3 Configuration
- Modify ScenarioConfig for cdh_sc3:
  - Update daily_threshold from 22.8°C to 23.9°C
  - Add new CDD-related parameters
  - Update conditional logic type

### 4. Implement Dual-Gate Logic
- Replace weekly mean temperature logic with new dual-gate system
- Implement OR logic: `(daily_mean > 23.9) OR (CDD_week > 2.0)`
- Ensure entire day (24 hours) is flagged when either condition is met

### 5. Update Processing Pipeline
- Integrate CDD calculations into main processing flow
- Update `apply_conditional_filters()` function for CDH_SC3 scenario
- Maintain compatibility with other scenarios (CDH_SC1, CDH_SC2, HDH_*)

### 6. Testing & Validation
- Create test functions to validate against Excel reference (row 194)
- Compare results with provided sample calculation
- Ensure mathematical accuracy and edge case handling
- Run scenario comparison tests to verify only CDH_SC3 is affected

### 7. Documentation Updates
- Update scenario descriptions in code comments
- Document new CDD calculation methodology
- Update CRITICAL_FIXES.md if needed
- Add validation notes referencing Excel sample

## Technical Considerations
- Maintain backward compatibility with existing scenarios
- Preserve existing folder structure (data/weather, results/)
- Ensure thread-safe implementation for parallel processing
- Handle missing data gracefully
- Validate that change only affects CDH_SC3, not other scenarios

## Expected Outcome
CDH_SC3 will use sophisticated cooling degree day logic instead of simple weekly temperature thresholds, providing more accurate cooling load calculations for HVAC equipment sizing in Canadian climate conditions.