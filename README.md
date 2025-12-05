# Data in the Wild: Wrangling and Visualising Data

This project was a part of the final exam for [Data in the Wild: Wrangling and Visualising Data](https://learnit.itu.dk/local/coursebase/view.php?ciid=1767) taught at the [IT-University of Copenhagen](https://www.itu.dk) in Autumn 2025 by [Luca Maria Aiello](http://www.lajello.com).

## Repo Structure

```text
ditw-2025-exam/
├── README.md
├── pyproject.toml
├── uv.lock
├── data/
│   ├── p3_2024.csv
│   ├── p3_oct_2025.csv
│   ├── p4_2024.csv
│   ├── p4_oct_2025.csv
│   ├── p6_2024.csv
│   └── p6_oct_2025.csv
├── scripts/
│   ├── annotation/
│   │   ├── AI_annotation.py
│   │   ├── extracting_host_from_description.ipynb
│   │   ├── inserting_hosts_into_dataset.ipynb
│   │   └── validator.py
│   └── scraped_processing/
│       ├── data_preprocessing.py
│       └── gender_enrichment.ipynb
└── web_scraper/
    ├── dr_scraper.py
    └── scrape_all_channels.py
```


## Package management

[`uv`](https://docs.astral.sh/uv/) is used for package management. For setting up the project, please install uv by following the [installation guide](https://docs.astral.sh/uv/getting-started/installation/). After installing, packages can be synced using the following command:

```console
uv sync
```

# How to Run and use

our project consists of a few scripts and notebooks to collect, clean and process the data into the final csv files shown in the data folder. **Note that some of the scripts might need slightly change in file names or paths to run without casuing errors or destorying the final data sets in data.**

## Scrape data
to begin scraping the data from dr using the [scrape_all_channelse](web_scraper/scrape_all_channelse.py). it will scrappe the data for all radio channels avalible on dr radio for a specific day. To use the scrapper run it use the following command and modify the data as needed. 
```bash
python -u run scrape_all_channelse.py --date 2025-10-30
```
It will output a csv file for each channel with the date it was scraped from.
**Note that at 5/12/2025 dr radio only have data publicly avalible one week from the current date**

## Gender enrichment
Using the note book [gender_enrichment]{scripts/scraped_processing/gender_enrichment.ipynb} it will take the scrapeded data compile it into a single csv file for each chancele and query MusicBrainz api for the gender of the artist.
Note that you might need to modify the notebook or [data_preprocessing]{scripts/scraped_processing/data_preprocessing.py}
this will output csv files for each channel with all the dates into one, addtionaly a new gender coloum have been added to the data.

## Experiment
To regenerate all the plots, run the experiments.ipynb file. Note that you will need all of the 2024 datasets to do so.

## Annotation of the host names
This stage have multiple steps.

### Regex annotation
before running this notebook 
[extracting_host_from_description]{scripts/annotation/extracting_host_from_description.ipynb}


run scrapper 
    outputs raw scraped data from all channels from dr

run gender enrich
    input the raw scraped data via data_preprocessing.py
    outputs a structured version of the scraped data now with addtional information from MusicBrainz

run extracting_host_from_description.ipynb
    input the structured version of the data
    outputs a files where host are added by a regex
    outputs a episode_descriptions_for_annotation with all description where no hosts where found

run AI_annotation.py
    input episode_descriptions_for_annotation.csv wich all episode where we dindt find hosts.
    outputs a file where ai annotated host from descriptions radio_programs_annotated-ai.csv

run validator


run inserting_hosts_into_dataset.ipynb
    input radio_programs_annotated-ai.csv 
    input the big datafiles
    output the final data files with all the hosts annotated by ai

