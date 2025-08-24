"""
ASHP Weather Data Processing Tool - Optimized Version 4
========================================================

This tool processes weather data to calculate heating and cooling degree hours 
for Air Source Heat Pump (ASHP) sizing and selection.

WHAT THIS TOOL DOES (for Mechanical Engineers):
1. Downloads Canadian weather files (like getting weather station data)
2. Calculates "degree hours" - similar to degree days but more precise (hourly vs daily)
3. Sorts temperature data into bins (like organizing data into temperature ranges)
4. Counts how many hours occur in each temperature bin for each season
5. Generates CSV files with this analysis for ASHP system sizing

DEGREE HOURS EXPLAINED:
- Heating Degree Hour = (18.3°C - outdoor_temp) / 24, when outdoor temp < 18.3°C
- Cooling Degree Hour = (outdoor_temp - 18.3°C) / 24, when outdoor temp > 18.3°C
- These help size heating/cooling equipment by showing temperature distribution

Based on pvlib-python EPW parsing functions (Apache License)
Original source: https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/iotools/epw.html
"""

import os
from bs4 import BeautifulSoup
import urllib.parse
import io
from urllib.request import urlopen, Request
import pandas as pd
import glob
import zipfile
from pathlib import Path
import numpy as np
import asyncio
import aiohttp
import time
from multiprocessing import Pool, cpu_count
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONSTANTS - Fixed values used throughout the program
# Think of these like engineering constants (like gravity = 9.81 m/s²)
class Constants:
    # Weather file format constants
    EPW_HEADER_LINES = 8        # EPW files have 8 header lines before data starts
    EPW_DATA_ROWS = 8760        # 365 days × 24 hours = 8760 hourly data points per year
    EPW_SKIP_ROWS = 6           # Skip 6 rows after reading the first header line
    STANDARDIZED_YEAR = 2020    # Use this year for seasonal calculations (any non-leap year works)
    
    # Time-based constants
    HOURS_PER_DAY = 24          # Obviously 24 hours in a day
    HOURS_PER_WEEK = 168        # 7 days × 24 hours = 168 hours per week
    
    # Temperature bin limits (for organizing data)
    TEMP_OVERFLOW_MIN = -100    # Catch any extremely cold temperatures below our range
    TEMP_OVERFLOW_MAX = 100     # Catch any extremely hot temperatures above our range
    
    # Website settings for downloading weather files
    BASE_URL = "http://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/CAN_Canada/"
    HTML_PARSER = "html.parser"  # How to read the website's HTML code
    
    # Download settings (like timeout limits)
    AIOHTTP_TIMEOUT_SECONDS = 300   # 5 minutes - stop trying to download if it takes too long
    AIOHTTP_CONNECTOR_LIMIT = 20    # Maximum simultaneous connections to the server
    
    # User agent - tells the website what kind of browser we are (prevents blocking)
    USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 '
                  'Safari/537.36')

# ENUMS - These are like categories or options to choose from
# Think of them like multiple choice options: A, B, C, or D

class DegreeHourType(Enum):
    """What type of degree hour calculation are we doing?"""
    HEATING = "heating"  # Calculate heating degree hours (when it's cold outside)
    COOLING = "cooling"  # Calculate cooling degree hours (when it's hot outside)

class Season(Enum):
    """The four seasons of the year"""
    WINTER = "winter"    # Dec 21 - Mar 20
    SPRING = "spring"    # Mar 21 - Jun 20  
    SUMMER = "summer"    # Jun 21 - Sep 20
    FALL = "fall"        # Sep 21 - Dec 20

# CONFIGURATION CLASSES
# These are like templates or forms that hold all the settings for different scenarios

@dataclass  # This makes it easy to create objects that hold data
class ScenarioConfig:
    """
    Configuration for a degree hour calculation scenario
    
    Think of this like a recipe card that tells us:
    - What type of calculation (heating or cooling)
    - What temperature thresholds to use
    - How to organize the temperature data into bins
    """
    name: str                    # Name of the scenario (like "hdh_sc1")
    degree_type: DegreeHourType  # Heating or cooling calculation
    daily_threshold: float       # Temperature threshold for daily averages (°C)
    weekly_threshold: float      # Temperature threshold for weekly averages (°C)
    temp_range: Tuple[float, float]  # Min and max temperatures for bins (°C)
    bin_size: float             # Size of each temperature bin (°C) - like 2.8°C intervals
    daily_condition: bool       # Should we check daily average temperature?
    weekly_condition: bool      # Should we check weekly average temperature?
    
    def __post_init__(self):
        """Check that the settings make sense (like quality control)"""
        if self.temp_range[0] >= self.temp_range[1]:
            raise ValueError(f"Invalid temperature range: {self.temp_range}")
        if self.bin_size <= 0:
            raise ValueError(f"Invalid bin size: {self.bin_size}")

@dataclass
class ProcessingResults:
    """
    Container for results from processing a single weather file
    Like a folder that holds all the outputs from one weather station
    """
    aggregated_data: pd.DataFrame  # The calculated degree hour data (like a spreadsheet)
    metadata: Dict                 # Information about the weather station (location, etc.)
    file_path: str                # Which file this came from
    processing_time: float        # How long it took to process (for performance monitoring)

# EPW COLUMN NAMES - All the different measurements in weather files
# EPW = EnergyPlus Weather files (a standard format used by building engineers)
# Think of this like column headers in a spreadsheet with 35 different measurements

EPW_COLNAMES = [
    # Time information
    'year', 'month', 'day', 'hour', 'minute', 'data_source_unct',
    
    # Temperature measurements (the main ones we care about)
    'temp_air',              # Dry bulb temperature (normal air temperature) in °C
    'temp_dew',              # Dew point temperature in °C
    'relative_humidity',     # Humidity as a percentage
    'atmospheric_pressure',  # Air pressure in Pa
    
    # Solar radiation measurements (for solar panel calculations)
    'etr', 'etrn', 'ghi_infrared', 'ghi', 'dni', 'dhi',
    'global_hor_illum', 'direct_normal_illum', 'diffuse_horizontal_illum',
    'zenith_luminance',
    
    # Wind measurements
    'wind_direction',        # Wind direction in degrees (0-360)
    'wind_speed',           # Wind speed in m/s
    
    # Sky and visibility conditions
    'total_sky_cover', 'opaque_sky_cover', 'visibility', 'ceiling_height',
    'present_weather_observation', 'present_weather_codes',
    
    # Atmospheric conditions
    'precipitable_water', 'aerosol_optical_depth',
    
    # Precipitation and ground conditions
    'snow_depth', 'days_since_last_snowfall', 'albedo',
    'liquid_precipitation_depth', 'liquid_precipitation_quantity'
]

# SCENARIO CONFIGURATIONS
# These are the 6 pre-defined analysis scenarios that building engineers commonly use
# Think of these like standard test conditions or design cases

PREDEFINED_SCENARIOS = {
    # HEATING DEGREE HOUR SCENARIOS (for sizing heating equipment)
    'hdh_sc1': ScenarioConfig(
        name='hdh_sc1', 
        degree_type=DegreeHourType.HEATING,
        daily_threshold=18.3,        # Start heating when daily avg drops below 18.3°C
        weekly_threshold=18.3,       # Not used in this scenario
        temp_range=(-29.2, 12.8),   # Analyze temperatures from -29.2°C to 12.8°C
        bin_size=2.8,               # Group temperatures in 2.8°C increments
        daily_condition=True,       # Only heat when daily average is cold
        weekly_condition=False      # Don't check weekly averages
    ),
    
    'hdh_sc2': ScenarioConfig(
        name='hdh_sc2', 
        degree_type=DegreeHourType.HEATING,
        daily_threshold=14.9,        # Lower threshold - more conservative heating
        weekly_threshold=18.3,       # Not used
        temp_range=(-29.2, 12.8), 
        bin_size=2.8,
        daily_condition=True, 
        weekly_condition=False
    ),
    
    'hdh_sc3': ScenarioConfig(
        name='hdh_sc3', 
        degree_type=DegreeHourType.HEATING,
        daily_threshold=14.9,        # Heat if daily avg < 14.9°C
        weekly_threshold=17.1,       # OR if weekly avg < 17.1°C
        temp_range=(-29.2, 12.8), 
        bin_size=2.8,
        daily_condition=True, 
        weekly_condition=True       # Check BOTH daily AND weekly conditions
    ),
    
    # COOLING DEGREE HOUR SCENARIOS (for sizing cooling equipment)
    'cdh_sc1': ScenarioConfig(
        name='cdh_sc1', 
        degree_type=DegreeHourType.COOLING,
        daily_threshold=18.3,        # Start cooling when daily avg exceeds 18.3°C
        weekly_threshold=18.3,       # Not used
        temp_range=(-29.2, 12.8),   # Same temp range as heating scenarios
        bin_size=2.8,
        daily_condition=True, 
        weekly_condition=False
    ),
    
    'cdh_sc2': ScenarioConfig(
        name='cdh_sc2', 
        degree_type=DegreeHourType.COOLING,
        daily_threshold=22.8,        # Higher threshold - less aggressive cooling
        weekly_threshold=18.3,       # Not used
        temp_range=(-29.2, 12.8), 
        bin_size=2.8,
        daily_condition=True, 
        weekly_condition=False
    ),
    
    'cdh_sc3': ScenarioConfig(
        name='cdh_sc3', 
        degree_type=DegreeHourType.COOLING,
        daily_threshold=22.8,        # Cool if daily avg > 22.8°C
        weekly_threshold=19.5,       # OR if weekly avg > 19.5°C
        temp_range=(23.6, 43.2),    # Different temp range for hot weather analysis
        bin_size=2.8,
        daily_condition=True, 
        weekly_condition=True       # Check BOTH daily AND weekly conditions
    )
}

# DOWNLOAD FUNCTIONS (Keep async functionality from v3)
async def download_file_async(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, 
                             url: str, filename: str, max_retries: int = 3) -> bool:
    """Download a single file asynchronously with retry logic"""
    async with semaphore:
        for attempt in range(max_retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(filename, 'wb') as f:
                            f.write(content)
                        logger.info(f"✓ Downloaded: {os.path.basename(filename)}")
                        return True
                    else:
                        logger.warning(f"⚠ HTTP {response.status} for {os.path.basename(filename)}")
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠ Retry {attempt + 1}/{max_retries} for {os.path.basename(filename)}: {e}")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"✗ Failed to download {os.path.basename(filename)}: {e}")
        return False

async def download_all_canadian_epw_files(save_location: str = 'energy_plus_weather',
                                          file_suffix: str = 'CWEC2016.zip',
                                          max_concurrent: int = 10) -> None:
    """Asynchronously download all Canadian EPW files"""
    logger.info(f"Starting async download to: {save_location}")
    os.makedirs(save_location, exist_ok=True)
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=Constants.AIOHTTP_TIMEOUT_SECONDS),
        connector=aiohttp.TCPConnector(limit=Constants.AIOHTTP_CONNECTOR_LIMIT)
    ) as session:
        try:
            async with session.get(Constants.BASE_URL) as response:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, Constants.HTML_PARSER)
                
            download_tasks = []
            semaphore = asyncio.Semaphore(max_concurrent)
            
            for link in soup.select(f"a[href$='{file_suffix}']"):
                file_url = urllib.parse.urljoin(Constants.BASE_URL, link['href'])
                filename = os.path.join(save_location, link['href'].split('/')[-1])
                
                if os.path.exists(filename):
                    logger.info(f"⏭ Skipping existing file: {os.path.basename(filename)}")
                    continue
                    
                task = download_file_async(session, semaphore, file_url, filename)
                download_tasks.append(task)
            
            if not download_tasks:
                logger.info("All files already exist. No downloads needed.")
                return
            
            logger.info(f"Starting {len(download_tasks)} concurrent downloads...")
            start_time = time.time()
            
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if r is True)
            failed = len(results) - successful
            elapsed = time.time() - start_time
            
            logger.info(f"📊 Download Summary: ✓ {successful}, ✗ {failed}, ⏱ {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"Error during download process: {e}")

def download_weather_files(save_location: str = 'energy_plus_weather') -> None:
    """Synchronous wrapper for async download"""
    asyncio.run(download_all_canadian_epw_files(save_location))

# EPW PROCESSING FUNCTIONS (Optimized)
def read_epw(filename: str, coerce_year: Optional[int] = None) -> Tuple[pd.DataFrame, Dict]:
    """Read an EPW file into a pandas dataframe with metadata extraction"""
    if str(filename).startswith('http'):
        request = Request(filename, headers={'User-Agent': Constants.USER_AGENT})
        response = urlopen(request)
        csvdata = io.StringIO(response.read().decode(errors='ignore'))
    elif filename.lower().endswith('.zip'):
        epw_file = Path(filename).stem + '.epw'
        zip_obj = zipfile.ZipFile(filename)
        csvdata = io.TextIOWrapper(zip_obj.open(epw_file), encoding="utf-8")
    else:
        csvdata = open(str(filename), 'r')

    try:
        data, meta = parse_epw(csvdata, coerce_year)
    finally:
        csvdata.close()
    return data, meta

def parse_epw(csvdata, coerce_year: Optional[int] = None) -> Tuple[pd.DataFrame, Dict]:
    """Parse EPW format data from file buffer"""
    # Read metadata line
    firstline = csvdata.readline()
    head = ['loc', 'city', 'state-prov', 'country', 'data_type', 'WMO_code',
            'latitude', 'longitude', 'TZ', 'altitude']
    meta = dict(zip(head, firstline.rstrip('\n').split(",")))
    
    # Convert numeric metadata
    for key in ['altitude', 'latitude', 'longitude', 'TZ']:
        meta[key] = float(meta[key])
    
    # Read weather data
    data = pd.read_csv(csvdata, skiprows=Constants.EPW_SKIP_ROWS, header=0, names=EPW_COLNAMES)
    
    if coerce_year is not None:
        data["year"] = coerce_year
    
    # Create timezone-aware datetime index
    dts = data[['month', 'day']].astype(str).apply(lambda x: x.str.zfill(2))
    hrs = (data['hour'] - 1).astype(str).str.zfill(2)
    dtscat = data['year'].astype(str) + dts['month'] + dts['day'] + hrs
    idx = pd.to_datetime(dtscat, format='%Y%m%d%H')
    idx = idx.dt.tz_localize(int(meta['TZ'] * 3600))
    data.index = idx
    
    return data, meta

# OPTIMIZED PROCESSING FUNCTIONS
def calculate_degree_hours(df: pd.DataFrame, config: ScenarioConfig) -> pd.DataFrame:
    """
    Calculate heating or cooling degree hours - the main engineering calculation
    
    WHAT THIS DOES (for Mechanical Engineers):
    This is like calculating how much heating/cooling energy you need each hour.
    
    HEATING: When it's 15°C outside and your threshold is 18.3°C:
    - Degree hour = (18.3 - 15) / 24 = 3.3 / 24 = 0.1375 degree-hours
    - This represents the heating load for that hour
    
    COOLING: When it's 25°C outside and your threshold is 18.3°C:
    - Degree hour = (25 - 18.3) / 24 = 6.7 / 24 = 0.279 degree-hours
    - This represents the cooling load for that hour
    
    The division by 24 converts from degree-days to degree-hours (more precise)
    """
    if config.degree_type == DegreeHourType.HEATING:
        # For heating: calculate how much colder it is than the threshold
        # Only positive values matter (can't have negative heating load)
        df['degree_hour'] = np.maximum((config.daily_threshold - df['temp_air']) / Constants.HOURS_PER_DAY, 0.0).astype(float)
    else:  # COOLING
        # For cooling: calculate how much warmer it is than the threshold  
        # Only positive values matter (can't have negative cooling load)
        df['degree_hour'] = np.maximum((df['temp_air'] - config.daily_threshold) / Constants.HOURS_PER_DAY, 0.0).astype(float)
    return df

def calculate_mean_temperatures_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate mean temperatures to match weather_v2.py exactly
    
    IMPORTANT: This uses the EXACT same logic as weather_v2.py:
    - Daily means: 24-hour blocks (0-23, 24-47, 48-71, etc.)
    - Weekly means: 168-hour blocks (0-167, 168-335, 336-503, etc.)
    
    This ensures identical results between v2 and v4.
    """
    # Initialize columns
    df['daily_mean_temp_c'] = 0.0
    df['weekly_mean_temp_c'] = 0.0
    
    # Daily mean calculation - match v2 exactly
    # Process in 24-hour blocks: 0-23, 24-47, 48-71, etc.
    for i in range(0, 8791, 24):
        end_idx = min(i + 24, len(df))
        if end_idx > i:
            daily_mean = df['temp_air'].iloc[i:end_idx].mean()
            df['daily_mean_temp_c'].iloc[i:end_idx] = daily_mean
    
    # Weekly mean calculation - match v2 exactly  
    # Process in 168-hour blocks: 0-167, 168-335, 336-503, etc.
    for i in range(0, 8791, 168):
        end_idx = min(i + 168, len(df))
        if end_idx > i:
            weekly_mean = df['temp_air'].iloc[i:end_idx].mean()
            df['weekly_mean_temp_c'].iloc[i:end_idx] = weekly_mean
    
    return df

def apply_conditional_filters(df: pd.DataFrame, config: ScenarioConfig) -> pd.DataFrame:
    """
    Apply temperature condition filters - this controls WHEN heating/cooling is needed
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function decides when to "turn on" heating or cooling based on daily/weekly averages.
    It's like having a smart thermostat that looks at recent weather patterns, not just current temperature.
    
    HEATING LOGIC:
    - If the daily average is warm enough (above threshold), don't heat that day
    - If the weekly average is warm enough, don't heat that week
    - Example: Even if it's cold right now, if the daily average is 20°C, don't count heating hours
    
    COOLING LOGIC:
    - If the daily average is cool enough (below threshold), don't cool that day
    - If the weekly average is cool enough, don't cool that week
    - Example: Even if it's hot right now, if the daily average is 15°C, don't count cooling hours
    
    This prevents oversizing equipment by ignoring brief temperature spikes.
    """
    if config.degree_type == DegreeHourType.HEATING:
        # HEATING: Turn off heating when average temperatures are warm enough
        if config.daily_condition and not config.weekly_condition:
            # Only check daily averages (most common case)
            mask = (df['daily_mean_temp_c'] < config.daily_threshold) == False
        elif config.daily_condition or config.weekly_condition:
            # Check both daily AND weekly averages (more sophisticated control)
            daily_mask = df['daily_mean_temp_c'] < config.daily_threshold
            weekly_mask = df['weekly_mean_temp_c'] < config.weekly_threshold
            # Turn off heating if NEITHER daily NOR weekly conditions are met
            mask = (daily_mask | weekly_mask) == False
        else:
            # No conditions - heat anytime (unusual case)
            mask = pd.Series([True] * len(df), index=df.index)
    else:  # COOLING
        # COOLING: Turn off cooling when average temperatures are cool enough
        if config.daily_condition and not config.weekly_condition:
            # Only check daily averages - turn off cooling when daily avg is NOT above threshold
            mask = (df['daily_mean_temp_c'] > config.daily_threshold) == False
        elif config.daily_condition or config.weekly_condition:
            # Check both daily AND weekly averages - turn off cooling when NEITHER condition is met
            daily_mask = df['daily_mean_temp_c'] > config.daily_threshold
            weekly_mask = df['weekly_mean_temp_c'] > config.weekly_threshold
            # Turn off cooling if NEITHER daily NOR weekly average is above threshold
            mask = (daily_mask | weekly_mask) == False
        else:
            # No conditions - cool anytime (unusual case)
            mask = pd.Series([False] * len(df), index=df.index)
    
    # Set degree hours to zero when conditions aren't met (no heating/cooling needed)
    # Use direct assignment to match weather_v2.py exactly
    df.loc[mask, 'degree_hour'] = 0.0
    return df

def classify_seasons(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify seasons using EXACT same logic as weather_v2.py
    
    IMPORTANT: This matches weather_v2.py exactly using datetime comparison
    rather than string comparison to ensure identical results.
    """
    # Match weather_v2.py exactly - create datetime objects for comparison
    df['py_year'] = 2020
    df['py_dateInt'] = df['py_year'].astype(str) + df['month'].astype(str).str.zfill(2) + df['day'].astype(str).str.zfill(2)
    df['py_datetime'] = pd.to_datetime(df['py_dateInt'], format='%Y%m%d')
    
    # Use exact same nested np.where logic as weather_v2.py
    df['season'] = np.where((df['py_datetime'] >= pd.to_datetime('20200101', format='%Y%m%d')) & (df['py_datetime'] <= pd.to_datetime('20200320', format='%Y%m%d')), 'winter',
                            np.where((df['py_datetime'] >= pd.to_datetime('20200321', format='%Y%m%d')) & (df['py_datetime'] <= pd.to_datetime('20200620', format='%Y%m%d')), 'spring',
                            np.where((df['py_datetime'] >= pd.to_datetime('20200621', format='%Y%m%d')) & (df['py_datetime'] <= pd.to_datetime('20200920', format='%Y%m%d')), 'summer',
                            np.where((df['py_datetime'] >= pd.to_datetime('20200921', format='%Y%m%d')) & (df['py_datetime'] <= pd.to_datetime('20201220', format='%Y%m%d')), 'fall', 'winter'))))
    
    return df

def create_temperature_bins(df: pd.DataFrame, config: ScenarioConfig) -> pd.DataFrame:
    """
    Create temperature bins for aggregation - organize temperatures into ranges
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function sorts all temperatures into "bins" or ranges, like organizing data into buckets.
    Instead of analyzing every individual temperature, we group similar temperatures together.
    
    EXAMPLE:
    If bin_size = 2.8°C and temp_range = (-29.2, 12.8):
    - Bin 1: -29.2°C to -26.4°C (very cold heating)
    - Bin 2: -26.4°C to -23.6°C (cold heating)
    - Bin 3: -23.6°C to -20.8°C (moderate heating)
    - ... and so on ...
    - Bin 15: 9.9°C to 12.8°C (mild heating)
    
    WHY WE USE BINS:
    - Makes data analysis manageable (15 bins instead of thousands of individual temperatures)
    - Equipment manufacturers provide performance data in temperature ranges
    - HVAC design standards use binned temperature analysis
    - Easier to identify the most common operating conditions
    
    The result helps size equipment by showing how many hours occur in each temperature range.
    """
    min_temp, max_temp = config.temp_range
    
    # Create a list of temperature bin boundaries
    # Example: [-29.2, -26.4, -23.6, ..., 9.9, 12.8]
    bins_list = np.arange(min_temp, max_temp, config.bin_size).tolist()
    
    # Add overflow bins to catch extreme temperatures outside our normal range  
    # Match weather_v2.py exactly: insert -100 at beginning, append 100 at end
    bins_list.insert(0, -100)  # Catch extremely cold temps 
    bins_list.insert(len(bins_list), 100)  # Catch extremely hot temps
    
    # Use pandas.cut to assign each temperature to a bin
    # This is like sorting temperatures into labeled boxes
    # Result: each hour gets a label like "(-26.4, -23.6]" showing which bin it belongs to
    df['bin'] = pd.cut(df['temp_air'], bins_list)
    
    # Keep as categorical to match weather_v2.py behavior exactly
    # (Don't convert to string - this was causing differences)
    
    return df

def create_seasonal_masks(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Pre-calculate seasonal masks for efficient aggregation - filter data by season
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function creates "filters" that let us quickly separate data by season.
    Think of it like having 5 different colored filters that show only certain parts of the data.
    
    MASKS CREATED:
    - Spring mask: Shows only spring hours that need heating/cooling (degree_hour > 0)
    - Summer mask: Shows only summer hours that need heating/cooling
    - Fall mask: Shows only fall hours that need heating/cooling  
    - Winter mask: Shows only winter hours that need heating/cooling
    - Total mask: Shows ALL hours that need heating/cooling (any season)
    
    WHY WE USE MASKS:
    - Much faster than filtering data multiple times
    - Lets us count hours by season efficiently
    - Essential for seasonal equipment sizing analysis
    - Prevents double-counting hours in different seasons
    
    The base_mask filters out hours where degree_hour = 0 (no heating/cooling needed).
    """
    # Base mask: only include hours where heating/cooling is actually needed
    # This excludes hours where conditions weren't met (set to 0 by apply_conditional_filters)
    base_mask = df['degree_hour'] > 0.0
    
    # Create individual season masks by combining season check with base mask
    # The & operator means "AND" - must be both the right season AND need heating/cooling
    return {
        'spring': (df['season'] == Season.SPRING.value) & base_mask,
        'summer': (df['season'] == Season.SUMMER.value) & base_mask,
        'fall': (df['season'] == Season.FALL.value) & base_mask,
        'winter': (df['season'] == Season.WINTER.value) & base_mask,
        'total': base_mask  # All seasons combined
    }

def aggregate_results_optimized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate results using EXACT same logic as weather_v2.py with lambda functions
    
    This uses the identical groupby aggregation with lambda functions to ensure
    exactly matching results with weather_v2.py
    """
    # Use exact same aggregation as weather_v2.py with lambda functions
    df_dh = df.groupby(['hour', 'bin']).agg({
        'degree_hour': 'sum', 
        'temp_air': 'mean', 
        'count_hours_in_bin': lambda g: df['degree_hour'].loc[g.index][(df['degree_hour'] > 0.0)].count(),
        'count_hour_spring': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'spring') & (df['degree_hour'] > 0.0)].count(),
        'count_hour_summer': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'summer') & (df['degree_hour'] > 0.0)].count(),
        'count_hour_fall': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'fall') & (df['degree_hour'] > 0.0)].count(),
        'count_hour_winter': lambda g: df['degree_hour'].loc[g.index][(df['season'] == 'winter') & (df['degree_hour'] > 0.0)].count()
    }).reset_index()
    
    # Rename column from temp_air to temp_mean (match weather_v2.py)
    df_dh.rename(columns={"temp_air": "temp_mean"}, inplace=True)
    
    # Fill NaN values with 0.0 (match weather_v2.py exactly)
    df_dh['temp_mean'].fillna(0.0, inplace=True)
    df_dh['count_hours_in_bin'].fillna(0.0, inplace=True)
    df_dh['count_hour_spring'].fillna(0.0, inplace=True)
    df_dh['count_hour_summer'].fillna(0.0, inplace=True)
    df_dh['count_hour_fall'].fillna(0.0, inplace=True)
    df_dh['count_hour_winter'].fillna(0.0, inplace=True)
    
    return df_dh

def process_single_file(args: Tuple[str, ScenarioConfig]) -> Optional[ProcessingResults]:
    """
    Process a single weather file - the main processing pipeline for each city
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function is like a factory assembly line that processes one weather file at a time.
    Each weather file represents one city/weather station with 8,760 hours of data.
    
    THE PROCESSING STEPS (in order):
    1. Read EPW file: Load weather data from the ZIP file
    2. Calculate degree hours: Compute heating/cooling loads for each hour
    3. Calculate averages: Compute daily and weekly temperature averages  
    4. Apply filters: Decide when heating/cooling is actually needed
    5. Classify seasons: Determine what season each hour belongs to
    6. Create bins: Sort temperatures into ranges for analysis
    7. Aggregate results: Create final summary tables for HVAC sizing
    
    INPUTS:
    - file_path: Path to the weather file (e.g., "Toronto_CWEC2016.zip")
    - config: Scenario settings (heating vs cooling, thresholds, bin sizes)
    
    OUTPUTS:
    - Aggregated data table ready for HVAC equipment sizing
    - Metadata about the weather station (location, coordinates)
    - Processing performance statistics
    
    This function is designed for parallel execution (multiple cities processed simultaneously).
    """
    file_path, config = args
    start_time = time.time()
    
    try:
        # STEP 1: READ WEATHER DATA FILE
        # Load EPW file and extract weather station metadata
        df, meta = read_epw(file_path)
        df['hour'] = df['hour'] - 1  # Convert from 1-24 to 0-23 format (programming standard)
        
        # STEP 2-7: APPLY PROCESSING PIPELINE
        # Each function performs one step of the analysis
        # Order matters - each step builds on the previous one
        df = calculate_degree_hours(df, config)           # Calculate heating/cooling loads
        df = calculate_mean_temperatures_vectorized(df)   # Daily/weekly temperature averages
        df = apply_conditional_filters(df, config)        # Apply start/stop logic
        df = classify_seasons(df)                         # Assign seasons to each hour
        df = create_temperature_bins(df, config)          # Group temperatures into bins
        
        # Initialize count columns to match weather_v2.py exactly
        df['count_hours_in_bin'] = 0
        df['count_hour_spring'] = 0
        df['count_hour_summer'] = 0
        df['count_hour_fall'] = 0
        df['count_hour_winter'] = 0
        
        # Add city/state info to df before aggregation (match v2 order)
        df['city'] = meta['city']
        df['state-prov'] = meta['state-prov']
        
        # STEP 8: CREATE FINAL SUMMARY TABLE
        # Transform 8,760 individual hours into aggregated results for HVAC sizing
        result_df = aggregate_results_optimized(df)
        
        # STEP 9: ADD LOCATION INFORMATION (after aggregation like v2)
        # Include city and province/state for identification in final results
        result_df['city'] = meta['city']
        result_df['state-prov'] = meta['state-prov']
        
        # STEP 10: PERFORMANCE MONITORING
        processing_time = time.time() - start_time
        logger.info(f"Processed {os.path.basename(file_path)} in {processing_time:.2f}s")
        
        # Return packaged results
        return ProcessingResults(result_df, meta, file_path, processing_time)
        
    except Exception as e:
        # Log errors but don't crash the entire program
        logger.error(f"Failed to process {file_path}: {e}")
        return None

def create_degree_hour_parallel(folder_location: str, config: ScenarioConfig, 
                               num_processes: Optional[int] = None) -> pd.DataFrame:
    """
    Process weather files in parallel for maximum performance - the main orchestrator
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function manages the processing of ALL weather files simultaneously for maximum speed.
    Instead of processing cities one-by-one (slow), it processes multiple cities at the same time.
    
    ANALOGY:
    Think of this like having multiple engineers working on different cities simultaneously,
    rather than one engineer working on all cities sequentially.
    
    PARALLEL PROCESSING BENEFITS:
    - 4-8x faster than sequential processing
    - Uses all CPU cores available on the computer
    - Processes multiple weather files simultaneously
    - Scales automatically based on number of CPU cores and files
    
    THE PROCESS:
    1. Find all weather ZIP files in the folder
    2. Determine optimal number of parallel workers (CPU cores)
    3. Split work among multiple processes
    4. Each process handles different cities simultaneously  
    5. Combine all results into one big table
    
    PERFORMANCE EXAMPLE:
    - Sequential: 100 cities × 2 seconds each = 200 seconds total
    - Parallel (4 cores): 100 cities ÷ 4 cores × 2 seconds = 50 seconds total
    
    The output is a single table containing results for ALL Canadian cities.
    """
    # STEP 1: FIND ALL WEATHER FILES
    # Look for ZIP files (Canadian weather data format)
    files = glob.glob(os.path.join(folder_location, '*.zip'))
    
    if not files:
        logger.warning(f"No ZIP files found in {folder_location}")
        return pd.DataFrame()
    
    # STEP 2: OPTIMIZE PARALLEL PROCESSING
    # Use all CPU cores, but not more workers than files to process
    if num_processes is None:
        num_processes = min(cpu_count(), len(files))
    
    logger.info(f"Processing {len(files)} files using {num_processes} processes...")
    start_time = time.time()
    
    # STEP 3: PREPARE WORK PACKAGES
    # Each worker gets a (file_path, config) pair to process
    args = [(file_path, config) for file_path in files]
    
    # STEP 4: PROCESS FILES IN PARALLEL
    # Pool creates multiple worker processes that run simultaneously
    # Each worker processes different weather files at the same time
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_single_file, args)
    
    # STEP 5: QUALITY CONTROL
    # Filter out any failed processing attempts
    valid_results = [r for r in results if r is not None]
    
    if not valid_results:
        logger.error("No files processed successfully")
        return pd.DataFrame()
    
    # STEP 6: COMBINE ALL CITY RESULTS
    # Merge all individual city tables into one master table
    # This creates the final dataset with ALL Canadian cities
    combined_df = pd.concat([r.aggregated_data for r in valid_results], ignore_index=True)
    
    # STEP 7: PERFORMANCE REPORTING
    total_time = time.time() - start_time
    logger.info(f"Processed {len(valid_results)}/{len(files)} files in {total_time:.2f}s")
    
    return combined_df

def save_results(df: pd.DataFrame, folder_location: str, filename: str) -> None:
    """
    Save results to CSV with error handling - export the final analysis tables
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function saves the processed degree hour data to a CSV file that can be opened in Excel.
    The CSV file contains the final tables that HVAC engineers use for equipment sizing.
    
    OUTPUT FILE FORMAT:
    The CSV files (like hdh_sc1.csv, cdh_sc2.csv) contain columns like:
    - hour: Hour of day (0-23)
    - bin: Temperature range (e.g., "(-23.6, -20.8]")
    - degree_hour: Total heating/cooling load for that combination
    - temp_mean: Average temperature in that bin
    - count_hour_winter/spring/summer/fall: Hours per season
    - city: Weather station city name
    - state-prov: Province or state
    
    These files are ready for import into HVAC design software or manual calculations.
    """
    try:
        # Create full file path with .csv extension
        output_path = os.path.join(folder_location, f"{filename}.csv")
        
        # Save to CSV format (readable by Excel and other tools)
        # index=False prevents saving row numbers as a column
        df.to_csv(output_path, index=False)
        
        logger.info(f"Results saved to {output_path}")
    except Exception as e:
        # Log any file saving errors (permissions, disk space, etc.)
        logger.error(f"Failed to save results: {e}")

def run_scenario(scenario_name: str, folder_location: str = 'energy_plus_weather', 
                num_processes: Optional[int] = None) -> None:
    """
    Run a single scenario with performance monitoring - process one analysis type
    
    WHAT THIS DOES (for Mechanical Engineers):
    This function runs one complete analysis scenario (like "hdh_sc1" for heating scenario 1).
    It processes ALL Canadian weather stations for that specific scenario and saves the results.
    
    SCENARIOS AVAILABLE:
    - hdh_sc1, hdh_sc2, hdh_sc3: Three heating degree hour scenarios
    - cdh_sc1, cdh_sc2, cdh_sc3: Three cooling degree hour scenarios
    
    Each scenario uses different temperature thresholds and conditions,
    representing different HVAC design approaches and building types.
    
    THE PROCESS:
    1. Validate the scenario name exists
    2. Get the scenario configuration (thresholds, bin sizes, etc.)
    3. Process all weather files in parallel
    4. Save results to a CSV file named after the scenario
    5. Report performance statistics
    
    OUTPUT: One CSV file (e.g., hdh_sc1.csv) with results for ALL Canadian cities.
    """
    # Validate that the requested scenario exists
    if scenario_name not in PREDEFINED_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    
    # Get the configuration settings for this scenario
    config = PREDEFINED_SCENARIOS[scenario_name]
    logger.info(f"Running scenario: {scenario_name}")
    
    # Process all weather files for this scenario
    start_time = time.time()
    results_df = create_degree_hour_parallel(folder_location, config, num_processes)
    
    # Save results and report performance
    if not results_df.empty:
        save_results(results_df, folder_location, config.name)
        elapsed = time.time() - start_time
        logger.info(f"Scenario {scenario_name} completed in {elapsed:.2f}s")
    else:
        logger.error(f"Scenario {scenario_name} failed - no results generated")

def run_all_scenarios(weather_folder: str = 'data/weather', 
                     results_folder: str = 'results', num_processes: Optional[int] = None) -> None:
    """
    Run all predefined scenarios with optimized performance - complete ASHP analysis
    
    WHAT THIS DOES (for Mechanical Engineers):
    This is the main function that performs the complete ASHP sizing analysis.
    It downloads weather data and runs all 6 scenarios to provide comprehensive results.
    
    THE COMPLETE PROCESS:
    1. Download all Canadian weather files to weather_folder (if not already present)
    2. Run all 6 degree hour scenarios and save CSV results to results_folder:
       - results/hdh_sc1.csv: Heating scenario 1 (standard)
       - results/hdh_sc2.csv: Heating scenario 2 (conservative)  
       - results/hdh_sc3.csv: Heating scenario 3 (advanced)
       - results/cdh_sc1.csv: Cooling scenario 1 (standard)
       - results/cdh_sc2.csv: Cooling scenario 2 (conservative)
       - results/cdh_sc3.csv: Cooling scenario 3 (advanced)
    
    FOLDER STRUCTURE:
    weather_folder/     # Downloaded weather ZIP files (input data)
    results_folder/     # Generated CSV files (analysis results)
    
    FINAL OUTPUT:
    6 CSV files with degree hour data for all Canadian cities.
    Each file represents a different HVAC design approach.
    Engineers can choose the most appropriate scenario for their project.
    
    USAGE FOR HVAC ENGINEERS:
    - Use heating scenarios for furnace, boiler, and heat pump sizing
    - Use cooling scenarios for air conditioner and heat pump sizing  
    - Compare scenarios to understand sensitivity to different assumptions
    - Import CSV files into design software or use for manual calculations
    """
    # Create output directories if they don't exist
    os.makedirs(weather_folder, exist_ok=True)
    os.makedirs(results_folder, exist_ok=True)
    
    # STEP 1: DOWNLOAD WEATHER DATA
    logger.info(f"Step 1: Downloading Canadian weather files to {weather_folder}...")
    download_weather_files(weather_folder)
    
    # STEP 2: PROCESS ALL SCENARIOS
    logger.info(f"Step 2: Running all scenarios with parallel processing, saving to {results_folder}...")
    
    total_start = time.time()
    # Run each of the 6 predefined scenarios
    for scenario_name in PREDEFINED_SCENARIOS.keys():
        run_scenario(scenario_name, weather_folder, results_folder, num_processes)
    
    # Report total completion time
    total_elapsed = time.time() - total_start
    logger.info(f"🎉 All scenarios completed in {total_elapsed:.2f}s!")

if __name__ == "__main__":
    """
    Command line interface for the ASHP weather processing tool
    
    USAGE EXAMPLES (for Mechanical Engineers):
    python weather.py                           # Use default folders (data/weather, results)
    python weather.py --weather-folder weather  # Custom weather folder 
    python weather.py --results-folder outputs  # Custom results folder
    python weather.py --benchmark               # Run in benchmark mode
    """
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description='ASHP Weather Data Processing Tool - Calculate degree hours for equipment sizing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python weather.py                              # Default folders (data/weather, results)
  python weather.py --weather-folder weather     # Custom weather folder
  python weather.py --results-folder outputs     # Custom results folder 
  python weather.py --benchmark                  # Performance testing mode
        '''
    )
    
    parser.add_argument(
        '--weather-folder', 
        default='data/weather',
        help='Folder for downloaded weather files (default: data/weather)'
    )
    
    parser.add_argument(
        '--results-folder', 
        default='results',
        help='Folder for generated CSV results (default: results)'
    )
    
    parser.add_argument(
        '--benchmark', 
        action='store_true',
        help='Run in benchmark mode with maximum CPU cores for performance testing'
    )
    
    # Parse command line arguments
    args = parser.parse_args()
    
    # Configure performance settings
    if args.benchmark:
        logger.info(f"Running in benchmark mode - Weather: {args.weather_folder}, Results: {args.results_folder}")
        start_time = time.time()
        run_all_scenarios(weather_folder=args.weather_folder, results_folder=args.results_folder, num_processes=cpu_count())
        total_time = time.time() - start_time
        logger.info(f"🚀 Total execution time: {total_time:.2f}s")
    else:
        logger.info(f"Running with folders - Weather: {args.weather_folder}, Results: {args.results_folder}")
        run_all_scenarios(weather_folder=args.weather_folder, results_folder=args.results_folder)