import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from collections import Counter
import time
import json
import re
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- PATHS ---
INPUT_CSV = "data/episode_descriptions_for_annotation.csv"
OUTPUT_CSV = "data/radio_programs_annotated-ai.csv"

DESCRIPTION_COLUMN = "episodeDescription"
BATCH_SIZE = 10

# --- MODEL SETUP ---
genai.configure(api_key=GEMINI_API_KEY)

# Model 1
gemini_flash = genai.GenerativeModel(
    'gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})

# Model 2
gemini_pro = genai.GenerativeModel(
    'gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

# Model 3
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- PROMPT ---
SYSTEM_PROMPT = """
You are an expert data extraction assistant.
I will provide a JSON object containing multiple radio program descriptions, indexed by their ID.
The descriptions are in **Danish**.
Your task is to extract the host name(s) for EACH description.

Rules:
1. Return a JSON object where the keys are the IDs provided in the input.
2. The values should be the extracted host name(s).
3. If multiple hosts, comma separate them (e.g. "Mo, Laila" not "Mo og Laila").
4. If no host is found, use the string "None". Do NOT guess. If you are unsure, return "None".
5. Do not include titles like "DJ", "Dr.", "Vært" or "Host". Just the names.
6. CRITICAL: Distinguish between HOSTS (Værter) and GUESTS (Gæster) or CALLERS (Lyttere). 
   - Look for Danish keywords indicating a host: "Vært", "Værter", "Med", "Præsenteret af", "Styret af".
   - Do NOT extract names of people being interviewed, discussed, or calling in (e.g. "Morten nominerer...", "Lise kommer ind..."). Only extract the presenter/host.
7. **Context matters**: Even if names appear in the text (e.g. "Nicolas har lokket..."), do NOT extract them unless the text explicitly frames them as the host. If the text just describes their actions without a host title, return "None".
8. **Groups/Teams**: If a specific group name (like "Drømmeholdet") is acting as the host and NO specific **HOST** names are mentioned, extract the group name. (Ignore guests/callers). However, if a specific **HOST** name IS mentioned (e.g. "Vært: Nicolas"), prefer the host name and ignore the group name.

**Few-Shot Examples (Use these as ground truth for logic):**

Input:
{
  "ex1": "Mo og Laila udforsker small talk og de udfordringer der kan opstå undervejs. Mo er usikker på emojiernes betydning...",
  "ex2": "Forelsk dig i den nyeste musik, og vær med i klubben, når Marie Hobitz tager nye navne og udgivelser under kærlig behandling...",
  "ex3": "Det er en smuk fredag i Drømmeholdet. Nicolas har lokket sin søde mormor, Inge, med på et nyt element: Sexdrømme med Mormor. Mikkel har en gammel pladespiller, som godt kunne bruge en kærlig hånd."
}

Output:
{
  "ex1": "Mo, Laila",
  "ex2": "Marie Hobitz",
  "ex3": "None"
}
"""

# --- HELPER FUNCTIONS ---


def clean_json_string(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"```$", "", text)
    return text


def ask_with_retry(func_name, func, *args, max_retries=3, initial_wait=20):
    """
    Tries to execute an API function. If it fails, waits and tries again.
    Useful for handling 429 Rate Limit errors.
    """
    for attempt in range(max_retries):
        try:
            return func(*args)
        except Exception as e:
            error_msg = str(e)
            print(
                f"  Warning: {func_name} failed (Attempt {attempt + 1}/{max_retries}). Error: {error_msg}")

            # If it's the last attempt, return empty dict
            if attempt == max_retries - 1:
                print(
                    f"  Error: {func_name} gave up after {max_retries} attempts.")
                return {}

            # Wait before retrying (exponential backoff: 20s, 40s...)
            wait_time = initial_wait * (attempt + 1)
            print(f"  Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)

    return {}


def _call_gemini_flash(batch_dict):
    prompt = f"{SYSTEM_PROMPT}\n\nInput Data:\n{json.dumps(batch_dict)}"
    response = gemini_flash.generate_content(prompt)
    return json.loads(clean_json_string(response.text))


def ask_gemini_flash_batch(batch_dict):
    return ask_with_retry("Gemini Flash", _call_gemini_flash, batch_dict, initial_wait=5)


def _call_gemini_pro(batch_dict):
    prompt = f"{SYSTEM_PROMPT}\n\nInput Data:\n{json.dumps(batch_dict)}"
    response = gemini_pro.generate_content(prompt)
    return json.loads(clean_json_string(response.text))


def ask_gemini_pro_batch(batch_dict):
    return ask_with_retry("Gemini Pro", _call_gemini_pro, batch_dict, initial_wait=10)


def _call_openai(batch_dict):
    prompt = f"Input Data:\n{json.dumps(batch_dict)}"
    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )
    return json.loads(response.choices[0].message.content)


def ask_openai_batch(batch_dict):
    # GPT-4o-mini free tier is strict, so we start with a higher wait time
    return ask_with_retry("OpenAI", _call_openai, batch_dict, initial_wait=20)


def get_majority_vote(preds):
    clean_preds = [str(p).strip()
                   for p in preds if p is not None and str(p).strip() != ""]
    if not clean_preds:
        return "Error"
    counts = Counter(clean_preds)
    return counts.most_common(1)[0][0]

# --- MAIN EXECUTION ---


def main():
    print(f"Reading CSV from {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Could not find file at {INPUT_CSV}")
        return

    # Check if 'id' column exists, if not create a temporary one for tracking
    if 'id' not in df.columns:
        df['temp_id'] = df.index.astype(str)
    else:
        df['temp_id'] = df['id'].astype(str)

    # Initialize result columns
    df['model1pred'] = ""
    df['model2pred'] = ""
    df['model3pred'] = ""
    df['selectedpred'] = ""  # Majority Vote

    rows = df.to_dict('records')
    total_rows = len(rows)

    print(f"Processing {total_rows} rows in batches of {BATCH_SIZE}...")

    for i in range(0, total_rows, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        print(f"Processing batch {i} to {min(i + BATCH_SIZE, total_rows)}...")

        # Create input payload: {ID: episodeDescription}
        input_payload = {
            row['temp_id']: row[DESCRIPTION_COLUMN]
            for row in batch
            if pd.notna(row.get(DESCRIPTION_COLUMN))
        }

        if not input_payload:
            continue

        # Call APIs
        # Note: The retry logic inside these functions handles the waiting if errors occur
        flash_results = ask_gemini_flash_batch(input_payload)
        pro_results = ask_gemini_pro_batch(input_payload)
        openai_results = ask_openai_batch(input_payload)

        for row in batch:
            row_id = row['temp_id']
            row_idx = df.index[df['temp_id'] == row_id].tolist()[0]

            f_val = flash_results.get(row_id, "Error")
            p_val = pro_results.get(row_id, "Error")
            o_val = openai_results.get(row_id, "Error")

            # Store in the new column names
            df.at[row_idx, 'model1pred'] = f_val
            df.at[row_idx, 'model2pred'] = p_val
            df.at[row_idx, 'model3pred'] = o_val

            # Vote
            df.at[row_idx, 'selectedpred'] = get_majority_vote(
                [f_val, p_val, o_val])

        # --- PROGRESS SAVE ---
        # We save after EVERY batch so we never lose data again.
        try:
            temp_df = df.copy()
            if 'temp_id' in temp_df.columns and 'id' not in temp_df.columns:
                temp_df.drop(columns=['temp_id'], inplace=True)
            elif 'temp_id' in temp_df.columns:
                temp_df.drop(columns=['temp_id'], inplace=True)

            temp_df.to_csv(OUTPUT_CSV, index=False, escapechar='\\')
            print("  Progress saved.")
        except Exception as e:
            print(f"  Warning: Could not save progress: {e}")

        print("Sleeping 21s to respect strict API rate limits...")
        time.sleep(21)

    print("Final save...")
    # Clean up tracking ID before final save
    if 'temp_id' in df.columns and 'id' not in df.columns:
        df.drop(columns=['temp_id'], inplace=True)
    elif 'temp_id' in df.columns:
        df.drop(columns=['temp_id'], inplace=True)

    df.to_csv(OUTPUT_CSV, index=False, escapechar='\\')
    print(f"Done! Results saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
