1.0 Temperature-Based Data Storage Requirements
1.1 Overview
This section defines the updated requirements for temperature-based conditional data storage, replacing the existing weekly mean temperature methodology with a more sophisticated cooling degree day approach.
1.2 Temperature Thresholds
1.2.1 Daily Mean Temperature Threshold

Current Implementation: 22.8°C
Required Implementation: 23.9°C
Definition: The daily mean temperature shall be calculated as the arithmetic average of all hourly temperature readings for a given calendar day.

1.3 Gate Condition Logic
1.3.1 Current Logic (To Be Replaced)
The existing implementation uses a weekly mean temperature threshold of 19.5°C to determine when hours should be stored. The exact scope of hour storage in the current implementation is unclear.
1.3.2 Required Logic
The system shall store data based on two independent trigger conditions:
Condition 1: Daily Mean Temperature Exceedance

When the daily mean temperature exceeds 23.9°C, all hours from that day shall be stored

Condition 2: Previous 7-Day Cooling Degree Day Exceedance

When the "previous 7-day cooling degree day" (CDD_week) exceeds 2.0, all hours from that day shall be stored

Logic Operator: The conditions shall be evaluated using OR logic - if either condition is met, data storage is triggered.
1.4 Cooling Degree Day Calculations
1.4.1 Daily Cooling Degree Days (CDD_Daily)
The daily cooling degree days shall be calculated using the following equation:
CDD_Daily = MAX((T_DA - 19.44), 0)
Where:

T_DA = the daily average of the hourly temperatures for that day (°C)
19.44°C = base temperature (equivalent to 67°F as specified in source standard)

1.4.2 Previous 7-Day Cooling Degree Days (CDD_week)
The 7-day rolling average cooling degree days shall be calculated using the following equation:
CDD_week = (Σ(i=0 to 6) CDD_Daily[current_day - i]) / 7
Where:

The sum includes the current day plus the previous 6 days
For days where insufficient historical data exists (first 6 days of dataset), use available data and adjust denominator accordingly

1.5 Data Storage Scope
1.5.1 Storage Requirement
When either gate condition is satisfied, the system shall store all 24 hours of data from the qualifying day.
1.5.2 Data Completeness

Storage shall include all hourly temperature readings and associated metadata for the entire calendar day
No selective hour filtering shall be applied once a day qualifies for storage
Missing hourly data within a qualifying day shall be flagged but shall not prevent storage of available hours

1.6 Implementation Notes
1.6.1 Calculation Sequence
The daily processing shall follow this sequence:

Calculate daily mean temperature for the current day
Calculate CDD_Daily for the current day
Calculate CDD_week using current and previous 6 days
Evaluate both gate conditions
If either condition is met, flag all hours from current day for storage

1.6.2 Reference Implementation
A sample calculation demonstrating the CDD_week methodology is provided in the accompanying Excel spreadsheet, with the final CDD_week calculation shown in row 194.
1.6.3 Validation Requirements
The implementation shall be validated against the provided sample calculation to ensure mathematical accuracy and proper handling of edge cases.