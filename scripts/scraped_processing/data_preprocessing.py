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


def merge_related():
    """Merges all the dataframes for all channels into a single dataframe"""
    channel_splitted_dfs = {} # eg {"p3": {"artist": df}}
    for channel in get_channels():
        channel_splitted_dfs[channel] = split_df_to_dfs(channel)
    keys = {"artist": None, 
          "track": None,
          "program": None,
          "played_in": None,
          "composed": None,
          #"host": None, # not used for now
          }

    final_dict = {k: pd.DataFrame() for k in keys}

    for channel, channel_dfs in channel_splitted_dfs.items(): # loop over each channel
        for entity in final_dict.keys(): # loop through artist, track 
            old_df = final_dict[entity] # data so far
            new_df =  channel_dfs[entity] # new data
            final_dict[entity] = pd.concat([old_df,new_df], axis=0, ignore_index=True) #    df = pd.concat(dfs, axis=0, ignore_index=True)

    return final_dict# {"artist": df_artist_for_all_channels, "track": df_track_for_all_channels}
        

def split_df_to_dfs(channel="p3"):
    """Creates a dictionary of dataframes for one channel"""
    dfs = {"artist": None, 
          "track": None,
          "program": None,
          "played_in": None,
          "composed": None,
          #"host": None, # not used for now
          }
    for entity in dfs.keys():
        logger.info(f"Loading df {channel}")
        df = load_df_from_channel(channel)
        logger.info(f"Creating df for {channel}-{entity}")
        create_subset_df_factory = globals()[f"create_{entity}"]
        dfs[entity] = create_subset_df_factory(df)
    return dfs

def load_df_from_channel(channel):
    """ Get the data from a specific channel as a pandas dataframe
    valid DR channels are: p2, p3, p4, p5, p6 or p8 

    channel -- a valid DR channel, such as p2
    """
    df = merge_datasets(get_filenames_for_channel(channel))
    return df
    
def create_artist(df):
    check_artist_commas(df)
    df = explode_artists(df)
    df = df.rename(columns={"artist_names": "name",
    "artist_urns": "urn"})
    artist_df = df[["urn", "name"]].drop_duplicates().set_index("urn")
    return artist_df

def create_track(df):
    df = explode_artists(df)
    df = df.rename(columns={"track_urn": "urn",
                            "track_title": "title",
                            "track_duration_ms": "duration_ms",                       
                            })
    df = df[["urn", "title"]].drop_duplicates(subset=["urn", "title"])
    df = df.set_index("urn")
    return df

def create_program(df):
    cols = ["programme_title", "channel", "programme_start_time", "programme_description"]
    df = df[cols]
    df = df.drop_duplicates(cols)
    return df

def create_composed(df):
    """Arists composed one or more tracks, this is a many-to-many relationship
    ella augusta, dronning af månen
    ida lauberg, dronning af månen
    """
    df = explode_artists(df)
    df = df[[ "artist_urns", "track_urn"]]
    return df

def create_played_in(df):
    cols = ["track_urn", "programme_title", "track_played_time"]
    df = df[cols]
    df = df.drop_duplicates(cols)
    df["track_played_time"] = pd.to_datetime(df["track_played_time"], errors="coerce")
    return df

def get_channels():
    channels = set()
    for filename in csv_files:
        pattern = r"dr_(.*?)_"
        match = re.match(pattern, filename)
        channels.add(match.group(1))
    return channels


def get_filenames_for_channel(channel):
    """ Returns a list of all the filenames of a specific channel using the global variable csv_files 
    valid DR channels are: p2, p3, p4, p5, p6 or p8 

    channel -- a valid DR channel, such as p2
    """
    filenames = [filename for filename in csv_files if filename.startswith('dr_' + channel)]
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

def check_artist_commas(df):
    logger.info("Checking if any artists have commas in their name")
    try:
        df = find_comma_artist_names(df)
        if not df.empty:
            logger.warning(f"Found {len(df)} artists with commas in their name")
            pd.set_option('display.max_colwidth', None)  # None means no limit
            if logging.getLogger().level == logging.DEBUG:
                pd.set_option('display.max_colwidth', 100)  # Limit to 100 characters
                display(df[["artist_names", "artist_urns"]])
                pd.reset_option('display.max_colwidth')  # Reset to default
            raise ValueError(f"Found {len(df)} artists with commas in their name")
    except Exception as e:
        logger.warning(f"Failed to check {e}")

def find_comma_artist_names(df):
    """Finds artists with commas in their name causing downstream problems"""
    df = df.copy() # Added since incplace ops are causing errors
    df = stringcol_to_listcol(df, "artist_names")
    df = stringcol_to_listcol(df, "artist_urns")
    df['urn_eq_name_len'] = df[['artist_urns', 'artist_names']].apply( lambda row: len(row[0]) == len(row[1]) , axis=1) 
    df = df[df['urn_eq_name_len'] == False]
    return df # finds Tyler, The Creator among other artists with commas in name

def stringcol_to_listcol(df, colname):
    df[colname] = df[colname].apply(lambda x: x.split(",") if pd.notna(x) else [])
    return df

def fix_artist_names_by_urn_length(row):
    """Fixes artist_names by using artist_urns length as ground truth.
    When artist_names has more elements than artist_urns after splitting by comma,
    merges consecutive names from the beginning until lengths match.
    
    Args:
        row: pandas Series with 'artist_names' and 'artist_urns' columns
        
    Returns:
        Fixed artist_names string
    """
    if pd.isna(row['artist_names']) or pd.isna(row['artist_urns']):
        return row['artist_names']
    
    # Split both columns by comma
    names_list = [name.strip() for name in str(row['artist_names']).split(",")]
    urns_list = [urn.strip() for urn in str(row['artist_urns']).split(",")]
    
    # If lengths match, no fix needed
    if len(names_list) == len(urns_list):
        return row['artist_names']
    
    # If names count > urns count, we need to merge some names
    if len(names_list) > len(urns_list):
        # Calculate how many names need to be merged
        excess = len(names_list) - len(urns_list)
        
        # Merge the first (excess + 1) names together
        # This removes the problematic comma by joining with space instead
        # Strip each name to avoid double spaces
        names_to_merge = [name.strip() for name in names_list[:excess + 1]]
        merged_name = " ".join(names_to_merge)
        # Keep the rest of the names as is (also strip them)
        fixed_names_list = [merged_name] + [name.strip() for name in names_list[excess + 1:]]
        
        # Join back with comma
        return ", ".join(fixed_names_list)
    
    # If names count < urns count, return as is (shouldn't happen normally)
    return row['artist_names']

def fix_artist_commas_universal(df):
    """Universally fixes artist names with commas by using URN length as ground truth.
    This function identifies and fixes cases where splitting by comma produces
    more artist names than artist URNs, indicating commas within artist names.
    
    Args:
        df: DataFrame with 'artist_names' and 'artist_urns' columns
        
    Returns:
        DataFrame with fixed artist_names
    """
    df = df.copy()
    
    # Apply the fix row by row
    df['artist_names'] = df.apply(fix_artist_names_by_urn_length, axis=1)
    
    return df

def explode_artists(df):
    # First fix any problematic commas using URN length as ground truth
    df = fix_artist_commas_universal(df)
    # Then proceed with normal splitting and exploding
    df = stringcol_to_listcol(df, "artist_names")
    df = stringcol_to_listcol(df, "artist_urns")
    df = df.explode(["artist_names", "artist_urns"])
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


#%%
if __name__ == "__main__":
    # p3_dfs = split_df_to_dfs("p3")
    merge_related()
    # df = load_df_from_channel('p3')
    # display(df)

# %%
