# Data in the Wild: Wrangling and Visualising Data

This project was a part of the final exam for [Data in the Wild: Wrangling and Visualising Data](https://learnit.itu.dk/local/coursebase/view.php?ciid=1767) taught at the [IT-University of Copenhagen](https://www.itu.dk) in Autumn 2025 by [Luca Maria Aiello](http://www.lajello.com).

## Repo Structure

```text
ditw-2025-exam/
├── README.md
├── pyproject.toml
├── uv.lock
├── data/
│   ├── helpers/
│   │   └── dataset_from_DR_minimal.zip
│   ├── p3_2024.csv
│   ├── p3_oct_2025.csv
│   ├── p4_2024.csv
│   ├── p4_oct_2025.csv
│   ├── p6_2024.csv
│   └── p6_oct_2025.csv
├── plots/
│   ├── gender_distribution_by_channel.svg
│   ├── p3_friday_shows_gender_distribution.svg
│   ├── p3_gender_distribution_weekly.svg
│   └── p3_hourly_gender_distribution.svg
├── scripts/
│   ├── annotation/
│   │   ├── AI_annotation.py
│   │   ├── extracting_host_from_description.ipynb
│   │   ├── inserting_hosts_into_dataset.ipynb
│   │   └── validator.py
│   ├── scraped_processing/
│   │   ├── data_preprocessing.py
│   │   └── gender_enrichment.ipynb
│   ├── web_scraper/
│   │   ├── dr_scraper.py
│   │   └── scrape_all_channels.py
│   └── experiments.ipynb
```

## Package management

[`uv`](https://docs.astral.sh/uv/) is used for package management. For setting up the project, please install uv by following the [installation guide](https://docs.astral.sh/uv/getting-started/installation/). After installing, packages can be synced using the following command:

```console
uv sync
```

# How to Run and Use

Our project consists of a few scripts and notebooks to collect, clean and process the data into the final CSV files shown in the data folder. **Note that some of the scripts might need slight changes in file names or paths to run without causing errors or destroying the final data sets in data.**

## Scrape Data
To begin scraping the data from DR, use the [scrape_all_channels.py](scripts/web_scraper/scrape_all_channels.py) script. It will scrape the data for all radio channels available on DR Radio for a specific day. 

To use the scraper, run the following command from the root of the project and modify the date as needed:

```bash
python -u scripts/web_scraper/scrape_all_channels.py --date 2025-10-30
```

It will output a CSV file for each channel with the date it was scraped from.

> **Note that as of 5/12/2025, DR Radio only has data publicly available one week from the current date.**

## Gender Enrichment

Using the notebook [gender_enrichment.ipynb](scripts/scraped_processing/gender_enrichment.ipynb), it will take the scraped data and compile it into a single CSV file for each channel and query the MusicBrainz API for the gender of the artist.
Note that you might need to modify the notebook or [data_preprocessing.py](scripts/scraped_processing/data_preprocessing.py).
This will output CSV files for each channel with all the dates into one. Additionally, a new gender column has been added to the data.

## Experiment

To regenerate all the plots, run the [experiments.ipynb](scripts/experiments.ipynb) notebook. Note that you will need all of the 2024 datasets to do so.

## Annotation of the Host Names

This stage has multiple steps.

### Regex Annotation

Before running this notebook, make sure you have the CSV files from the **Gender Enrichment** step.
Using the notebook [extracting_host_from_description.ipynb](scripts/annotation/extracting_host_from_description.ipynb) will use a regex and extract the host name from the program description.
This will change the data file by adding the host names, but it will also output a file with all the programs where no host was found.

### AI Annotation

Using the file generated from the previous step, the [AI_annotation.py](scripts/annotation/AI_annotation.py) script will use multiple AI models to find radio hosts and will output a file with the found radio hosts and their descriptions. In order for this script to work, you will need `API_KEYS` to each of the AI used. These `API_KEYS` need to be configured in your environment:

```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

To run the `AI_annotation.py` run the following command from the root of the project.

```bash
python scripts/annotation/AI_annotation.py 
```

### Inserting the Annotations

Finally, running the notebook [inserting_hosts_into_dataset.ipynb](scripts/annotation/inserting_hosts_into_dataset.ipynb) will take the file from the last step and update the host columns in the full channel data files.

## Final

Following the steps above, you should have CSV files similar to ours but with the time period of the data that you scraped.
