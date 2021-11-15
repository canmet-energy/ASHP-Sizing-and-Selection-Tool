# Some code below was used from https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/iotools/epw.html under apache licence.

import requests

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


def download_all_canadian_epw_files(save_location = os.path.join(os.path.abspath(''), '..', '..', r'data\energy_plus_weather'),
                                    file_suffix='CWEC2016.zip'): #'CWEC2016.zip'
    # specify the URL of the archive here
    url = "http://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/CAN_Canada/"
    response = requests.get(url)
    soup= BeautifulSoup(response.text, "html.parser")
    for link in soup.select(f"a[href$='{file_suffix}']"):
        filename = os.path.join(save_location, link['href'].split('/')[-1])
        with open(filename, 'wb') as f:
            f.write(requests.get(urllib.parse.urljoin(url, link['href'])).content)
        print(f"Filename:{filename} downloaded to {save_location}")

"""
Import functions for EPW data files.
"""




def read_epw(filename, coerce_year=None):
    r'''
    Read an EPW file in to a pandas dataframe.
    Note that values contained in the metadata dictionary are unchanged
    from the EPW file.
    EPW files are commonly used by building simulation professionals
    and are widely available on the web. For example via:
    https://energyplus.net/weather , http://climate.onebuilding.org or
    http://www.ladybug.tools/epwmap/
    Parameters
    ----------
    filename : String
        Can be a relative file path, absolute file path, or url.
    coerce_year : None or int, default None
        If supplied, the year of the data will be set to this value. This can
        be a useful feature because EPW data is composed of data from
        different years.
        Warning: EPW files always have 365*24 = 8760 data rows;
        be careful with the use of leap years.
    Returns
    -------
    data : DataFrame
        A pandas dataframe with the columns described in the table
        below. For more detailed descriptions of each component, please
        consult the EnergyPlus Auxiliary Programs documentation [1]_
    metadata : dict
        The site metadata available in the file.
    See Also
    --------
    pvlib.iotools.parse_epw
    Notes
    -----
    The returned structures have the following fields.
    ===============   ======  =========================================
    key               format  description
    ===============   ======  =========================================
    loc               String  default identifier, not used
    city              String  site loccation
    state-prov        String  state, province or region (if available)
    country           String  site country code
    data_type         String  type of original data source
    WMO_code          String  WMO identifier
    latitude          Float   site latitude
    longitude         Float   site longitude
    TZ                Float   UTC offset
    altitude          Float   site elevation
    ===============   ======  =========================================
    +-------------------------------+-----------------------------------------+
    | EPWData field                 | description                             |
    +===============================+=========================================+
    | index                         | A pandas datetime index. NOTE, times are|
    |                               | set to local standard time (daylight    |
    |                               | savings is not included). Days run from |
    |                               | 0-23h to comply with PVLIB's convention.|
    +-------------------------------+-----------------------------------------+
    | year                          | Year, from original EPW file. Can be    |
    |                               | overwritten using coerce function.      |
    +-------------------------------+-----------------------------------------+
    | month                         | Month, from original EPW file.          |
    +-------------------------------+-----------------------------------------+
    | day                           | Day of the month, from original EPW     |
    |                               | file.                                   |
    +-------------------------------+-----------------------------------------+
    | hour                          | Hour of the day from original EPW file. |
    |                               | Note that EPW's convention of 1-24h is  |
    |                               | not taken over in the index dataframe   |
    |                               | used in PVLIB.                          |
    +-------------------------------+-----------------------------------------+
    | minute                        | Minute, from original EPW file. Not     |
    |                               | used.                                   |
    +-------------------------------+-----------------------------------------+
    | data_source_unct              | Data source and uncertainty flags. See  |
    |                               | [1]_, chapter 2.13                      |
    +-------------------------------+-----------------------------------------+
    | temp_air                      | Dry bulb temperature at the time        |
    |                               | indicated, deg C                        |
    +-------------------------------+-----------------------------------------+
    | temp_dew                      | Dew-point temperature at the time       |
    |                               | indicated, deg C                        |
    +-------------------------------+-----------------------------------------+
    | relative_humidity             | Relative humidity at the time indicated,|
    |                               | percent                                 |
    +-------------------------------+-----------------------------------------+
    | atmospheric_pressure          | Station pressure at the time indicated, |
    |                               | Pa                                      |
    +-------------------------------+-----------------------------------------+
    | etr                           | Extraterrestrial horizontal radiation   |
    |                               | recv'd during 60 minutes prior to       |
    |                               | timestamp, Wh/m^2                       |
    +-------------------------------+-----------------------------------------+
    | etrn                          | Extraterrestrial normal radiation recv'd|
    |                               | during 60 minutes prior to timestamp,   |
    |                               | Wh/m^2                                  |
    +-------------------------------+-----------------------------------------+
    | ghi_infrared                  | Horizontal infrared radiation recv'd    |
    |                               | during 60 minutes prior to timestamp,   |
    |                               | Wh/m^2                                  |
    +-------------------------------+-----------------------------------------+
    | ghi                           | Direct and diffuse horizontal radiation |
    |                               | recv'd during 60 minutes prior to       |
    |                               | timestamp, Wh/m^2                       |
    +-------------------------------+-----------------------------------------+
    | dni                           | Amount of direct normal radiation       |
    |                               | (modeled) recv'd during 60 minutes prior|
    |                               | to timestamp, Wh/m^2                    |
    +-------------------------------+-----------------------------------------+
    | dhi                           | Amount of diffuse horizontal radiation  |
    |                               | recv'd during 60 minutes prior to       |
    |                               | timestamp, Wh/m^2                       |
    +-------------------------------+-----------------------------------------+
    | global_hor_illum              | Avg. total horizontal illuminance recv'd|
    |                               | during the 60 minutes prior to          |
    |                               | timestamp, lx                           |
    +-------------------------------+-----------------------------------------+
    | direct_normal_illum           | Avg. direct normal illuminance recv'd   |
    |                               | during the 60 minutes prior to          |
    |                               | timestamp, lx                           |
    +-------------------------------+-----------------------------------------+
    | diffuse_horizontal_illum      | Avg. horizontal diffuse illuminance     |
    |                               | recv'd during the 60 minutes prior to   |
    |                               | timestamp, lx                           |
    +-------------------------------+-----------------------------------------+
    | zenith_luminance              | Avg. luminance at the sky's zenith      |
    |                               | during the 60 minutes prior to          |
    |                               | timestamp, cd/m^2                       |
    +-------------------------------+-----------------------------------------+
    | wind_direction                | Wind direction at time indicated,       |
    |                               | degrees from north (360 = north; 0 =    |
    |                               | undefined,calm)                         |
    +-------------------------------+-----------------------------------------+
    | wind_speed                    | Wind speed at the time indicated, m/s   |
    +-------------------------------+-----------------------------------------+
    | total_sky_cover               | Amount of sky dome covered by clouds or |
    |                               | obscuring phenomena at time stamp,      |
    |                               | tenths of sky                           |
    +-------------------------------+-----------------------------------------+
    | opaque_sky_cover              | Amount of sky dome covered by clouds or |
    |                               | obscuring phenomena that prevent        |
    |                               | observing the sky at time stamp, tenths |
    |                               | of sky                                  |
    +-------------------------------+-----------------------------------------+
    | visibility                    | Horizontal visibility at the time       |
    |                               | indicated, km                           |
    +-------------------------------+-----------------------------------------+
    | ceiling_height                | Height of cloud base above local terrain|
    |                               | (7777=unlimited), meter                 |
    +-------------------------------+-----------------------------------------+
    | present_weather_observation   | Indicator for remaining fields: If 0,   |
    |                               | then the observed weather codes are     |
    |                               | taken from the following field. If 9,   |
    |                               | then missing weather is assumed.        |
    +-------------------------------+-----------------------------------------+
    | present_weather_codes         | Present weather code, see [1], chapter  |
    |                               | 2.9.1.28                                |
    +-------------------------------+-----------------------------------------+
    | precipitable_water            | Total precipitable water contained in a |
    |                               | column of unit cross section from earth |
    |                               | to top of atmosphere, cm. Note that some|
    |                               | old \*_TMY3.epw files may have incorrect|
    |                               | unit if it was retrieved from           |
    |                               | www.energyplus.net.                     |
    +-------------------------------+-----------------------------------------+
    | aerosol_optical_depth         | The broadband aerosol optical depth per |
    |                               | unit of air mass due to extinction by   |
    |                               | aerosol component of atmosphere,        |
    |                               | unitless                                |
    +-------------------------------+-----------------------------------------+
    | snow_depth                    | Snow depth in centimeters on the day    |
    |                               | indicated, (999 = missing data)         |
    +-------------------------------+-----------------------------------------+
    | days_since_last_snowfall      | Number of days since last snowfall      |
    |                               | (maximum value of 88, where 88 = 88 or  |
    |                               | greater days; 99 = missing data)        |
    +-------------------------------+-----------------------------------------+
    | albedo                        | The ratio of reflected solar irradiance |
    |                               | to global horizontal irradiance,        |
    |                               | unitless                                |
    +-------------------------------+-----------------------------------------+
    | liquid_precipitation_depth    | The amount of liquid precipitation      |
    |                               | observed at indicated time for the      |
    |                               | period indicated in the liquid          |
    |                               | precipitation quantity field,           |
    |                               | millimeter                              |
    +-------------------------------+-----------------------------------------+
    | liquid_precipitation_quantity | The period of accumulation for the      |
    |                               | liquid precipitation depth field, hour  |
    +-------------------------------+-----------------------------------------+
    References
    ----------
    .. [1] `EnergyPlus documentation, Auxiliary Programs
       <https://energyplus.net/documentation>`_
    '''

    if str(filename).startswith('http'):
        # Attempts to download online EPW file
        # See comments above for possible online sources
        request = Request(filename, headers={'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 '
            'Safari/537.36')})
        response = urlopen(request)
        csvdata = io.StringIO(response.read().decode(errors='ignore'))
    elif filename.lower().endswith('.zip'):
        epw_file = Path(filename).stem + '.epw'
        zip = zipfile.ZipFile(filename)
        csvdata = io.TextIOWrapper(zip.open(epw_file), encoding="utf-8")
    else:
        # Assume it's accessible via the file system
        csvdata = open(str(filename), 'r')

    try:
        data, meta = parse_epw(csvdata, coerce_year)
    finally:
        csvdata.close()
    return data, meta


def parse_epw(csvdata, coerce_year=None):
    """
    Given a file-like buffer with data in Energy Plus Weather (EPW) format,
    parse the data into a dataframe.
    Parameters
    ----------
    csvdata : file-like buffer
        a file-like buffer containing data in the EPW format
    coerce_year : None or int, default None
        If supplied, the year of the data will be set to this value. This can
        be a useful feature because EPW data is composed of data from
        different years.
        Warning: EPW files always have 365*24 = 8760 data rows;
        be careful with the use of leap years.
    Returns
    -------
    data : DataFrame
        A pandas dataframe with the columns described in the table
        below. For more detailed descriptions of each component, please
        consult the EnergyPlus Auxiliary Programs documentation
        available at: https://energyplus.net/documentation.
    metadata : dict
        The site metadata available in the file.
    See Also
    --------
    pvlib.iotools.read_epw
    """
    # Read line with metadata
    firstline = csvdata.readline()

    head = ['loc', 'city', 'state-prov', 'country', 'data_type', 'WMO_code',
            'latitude', 'longitude', 'TZ', 'altitude']
    meta = dict(zip(head, firstline.rstrip('\n').split(",")))

    meta['altitude'] = float(meta['altitude'])
    meta['latitude'] = float(meta['latitude'])
    meta['longitude'] = float(meta['longitude'])
    meta['TZ'] = float(meta['TZ'])
    meta['city'] = str(meta['city'])
    meta['state-prov'] = str(meta['state-prov'])


    colnames = ['year', 'month', 'day', 'hour', 'minute', 'data_source_unct',
                'temp_air', 'temp_dew', 'relative_humidity',
                'atmospheric_pressure', 'etr', 'etrn', 'ghi_infrared', 'ghi',
                'dni', 'dhi', 'global_hor_illum', 'direct_normal_illum',
                'diffuse_horizontal_illum', 'zenith_luminance',
                'wind_direction', 'wind_speed', 'total_sky_cover',
                'opaque_sky_cover', 'visibility', 'ceiling_height',
                'present_weather_observation', 'present_weather_codes',
                'precipitable_water', 'aerosol_optical_depth', 'snow_depth',
                'days_since_last_snowfall', 'albedo',
                'liquid_precipitation_depth', 'liquid_precipitation_quantity']

    # We only have to skip 6 rows instead of 7 because we have already used
    # the realine call above.
    data = pd.read_csv(csvdata, skiprows=6, header=0, names=colnames)

    # Change to single year if requested
    if coerce_year is not None:
        data["year"] = coerce_year

    # create index that supplies correct date and time zone information
    dts = data[['month', 'day']].astype(str).apply(lambda x: x.str.zfill(2))
    hrs = (data['hour'] - 1).astype(str).str.zfill(2)
    dtscat = data['year'].astype(str) + dts['month'] + dts['day'] + hrs
    idx = pd.to_datetime(dtscat, format='%Y%m%d%H')
    idx = idx.dt.tz_localize(int(meta['TZ'] * 3600))
    data.index = idx
    return data, meta


# The below method is experimental.

def create_heating_cooling_degree_hour():
    # This is the folder where the epw zip files will be downloaded to your system. Rename this to a folder on your system.
    folder_location = os.path.join(os.path.abspath(''),'energy_plus_weather')

    #create the folder if it does not exist.
    os.makedirs(folder_location, exist_ok=True)
    # This method will download all the canadian weather files into your folder location with the file suffix.
    download_all_canadian_epw_files(save_location=folder_location,
                                    file_suffix='CWEC2016.zip')
    result_list = []
    # Glob basically finds all the weather files in the folder with a zip extention
    for file in glob.glob(os.path.join(folder_location,'*.zip')):
        try:
            # let user know which file we are processing.

            # read the epw file into a dataframe (df) variable to manipulate.
            # this function also colllects the meta data on top of the epw files See the funtion above for what is available.
            df,meta = read_epw(file)

            #Set options for grouping.
            degree_day_standard_temp_c = 18.3
            min_temp_range_c = -29.2
            max_temp_range_c = 12.8
            temperature_bin_interval_c = 2.8

            ## Get the heating degree binned hours.

            # Filter the rows of the weather table where the temp_air < 18.3C
            df_heating = df[df['temp_air'] < degree_day_standard_temp_c ].copy()
            # Create a new column with the heating degree hour. This is the difference of the temperature from the HDD standard (18.3c - Tair) * 1Day / 24 Hours
            df_heating['heating_degree_hour'] = (degree_day_standard_temp_c - df_heating['temp_air'])/24.0
            # Create a new bin column to flag which rows are in which bucket.  Jer asked for 1c intervals and range
            df_heating['bin'] = pd.cut(df['temp_air'], np.arange(min_temp_range_c, max_temp_range_c, temperature_bin_interval_c).tolist())
            # Group the heating degree hour by hour of day..so 24 values... aggregate by summing the heating_degree_hour calculated, and get the mean of the temp_air
            df_hdh = df_heating.groupby(['hour', 'bin']).agg( {'heating_degree_hour': 'sum', 'temp_air': 'mean'}).reset_index()
            # Fill zeros where there is no value.
            df_hdh['heating_degree_hour'].fillna(0.0, inplace =True)
            #Rename column from temp_air to temp_mean_heating...
            df_hdh.rename(columns={"temp_air": "temp_mean_heating"}, inplace =True)


            # Cooling same as heating but now > 18C...
            df_cooling = df[df['temp_air'] > degree_day_standard_temp_c].copy()
            if len(df_cooling) > 0:
                df_cooling ['cooling_degree_hour'] = (df_cooling['temp_air'] - degree_day_standard_temp_c )/24
                df_cooling['bin'] = pd.cut(df['temp_air'], np.arange(min_temp_range_c, max_temp_range_c, temperature_bin_interval_c).tolist())
                df_cdh = df_cooling.groupby(['hour','bin']).agg({'cooling_degree_hour':'sum','temp_air':'mean'}).reset_index()
                df_cdh['cooling_degree_hour'].fillna(0.0, inplace =True)
                df_cdh.rename(columns={"temp_air": "temp_mean_cooling"}, inplace =True)
                df_hdh['heating_degree_hour'].fillna(0.0, inplace=True)
                # add the cooling and temp mean cooling to a single dataframe.
                df_hdh_and_cdh = df_hdh.join(df_cdh['cooling_degree_hour'])
                df_hdh_and_cdh = df_hdh_and_cdh.join(df_cdh['temp_mean_cooling'])
            else:
                # There was no cooling degree days for this location. It is just too cold to require cooling. So no
                # df_cdh to calulate, but lets set them all to zero in the df_hdh and use that.

                # Set cooling degree column to zero everywhere in the df_hdh
                df_hdh['cooling_degree_hour'] = 0.0
                # Set the average to None.
                df_hdh['temp_mean_cooling'] = None
                # Assign
                df_hdh_and_cdh = df_hdh


            # Add city name
            df_hdh_and_cdh['city'] = meta['city']
            df_hdh_and_cdh['state-prov'] = meta['state-prov']


            # appending results to one big csv file.  Converting dataframe to list(array) of dicts(hashes) This is faster as
            # dataframe contatenation is expensive. Not really necessary, but good coding practice to be efficient
            result_list = result_list + df_hdh_and_cdh.to_dict('records')
        except Exception as error:
            print(f'File {file} failed by {error}')
    # Convert back to dataframe.
    df = pd.DataFrame(result_list)

    # Save to csv file.
    df.to_csv(os.path.join(folder_location, 'degree_hour.csv'))

create_heating_cooling_degree_hour()