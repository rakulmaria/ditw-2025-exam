from datetime import datetime
from fileinput import filename
import os
from IPython.core.display_functions import display
import pandas as pd
import re
from pyprojroot.here import here
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

datafolder = here()/'data'  # here() is the root of the project's folder, makes routing between folders easier (DIW-DR-PROJECT)
csv_files = os.listdir(datafolder)  # a list of all the names of the files in the /data folder

def get_all_dataframes(channel = "", year = ""):
    """ loads all CSV files in /data/enriched_final as pandas DataFrames.
    optional arguments are channel and year to filter filenames.

    channel (str, optional): -- Channel keyword to filter filenames (e.g., "p3").
    year (str, optional): -- Year keyword to filter filenames (e.g., "2024").

    returns all the dataframes as a tuple, which can be unpacked to individual variables.
    """
    final_datafolder = here()/'data/enriched_final' 
    csv_files = os.listdir(final_datafolder)  # a list of all the names of the files in the /data/enriched_final folder
    dfs = []

    csv_files.sort()
    if year:
        csv_files = [f for f in csv_files if year in f]
    if channel:
        csv_files = [f for f in csv_files if channel in f]

    for filename in csv_files:
        df = pd.read_csv(final_datafolder/filename, parse_dates=["localTime"])
        dfs.append(df)

    # returns them as a tuple of dataframes, which essentially can be unpacked when called
    return tuple(dfs)

def load_df_from_channel(channel):
    """ Get the data from a specific channel as a pandas dataframe
    valid DR channels are: p2, p3, p4, p5, p6 or p8 

    channel -- a valid DR channel, such as p2
    """
    df = merge_datasets(get_filenames_for_channel(channel))
    return df

def get_filenames_for_channel(channel):
    """ Returns a list of all the filenames of a specific channel using the global variable csv_files 
    valid DR channels are: p2, p3, p4, p5, p6 or p8 

    channel -- a valid DR channel, such as p2
    """
    filenames = [filename for filename in csv_files if filename.startswith(channel)]
    return filenames

def merge_datasets(filenames):
    """ Reads all the .csv files of the filenames and merges them into a single pandas dataframe
    
    filenames -- a list of all the filenames to be read
    """
    dfs = []
    for filename in filenames:
        logger.debug(f"Loading {filename}")
        df = pd.read_csv(datafolder/filename)
        dfs.append(df)

    df = pd.concat(dfs, axis=0, ignore_index=True)
    return df

def reform_datasets_to_minimal(df):
    """
    Reforms scraped dataset to minimal structure matching the DR dataset format.

    Scraped format columns:
        - track_played_time, channel, programme_title, programme_start_time,
          programme_description, track_title, artist_names

    Minimal format columns:
        - localTime, channel, episodeTitle, episodeStartTime,
          episodeDescription, trackTitle, artistString

    Args:
        df: DataFrame with scraped data columns

    Returns:
        DataFrame with minimal structure (without gender column)
    """
    df = df.copy()

    # Rename columns to match minimal format
    column_mapping = {
        'track_played_time': 'localTime',
        'programme_title': 'episodeTitle',
        'programme_start_time': 'episodeStartTime',
        'programme_description': 'episodeDescription',
        'track_title': 'trackTitle',
        'artist_names': 'artistString'
    }

    df = df.rename(columns=column_mapping)

    # Convert channel to uppercase (e.g., 'p3' -> 'P3')
    if 'channel' in df.columns:
        df['channel'] = df['channel'].str.upper()

    # Convert datetime columns
    if 'localTime' in df.columns:
        df['localTime'] = pd.to_datetime(df['localTime'], errors='coerce')
    if 'episodeStartTime' in df.columns:
        df['episodeStartTime'] = pd.to_datetime(df['episodeStartTime'], errors='coerce')

    # Select only the minimal columns (in the correct order)
    minimal_columns = [
        'localTime', 'channel', 'episodeTitle', 'episodeStartTime',
        'episodeDescription', 'trackTitle', 'artistString'
    ]

    # Only keep columns that exist in the dataframe
    existing_columns = [col for col in minimal_columns if col in df.columns]
    df = df[existing_columns]

    return df
