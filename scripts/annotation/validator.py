import pandas as pd
import os
import re

# File paths
AI_RESULTS_FILE = "data/enriched_with_hosts/radio_programs_annotated-ai.csv"
MANUAL_FILE = "data/enriched_with_hosts/Host_manual_annotation-validation.csv"

MANUAL_HOST_COLUMN = "host"
AI_HOST_COLUMN = "selectedpred"


def normalize_names(text):
    """
    Advanced normalization to handle:
    1. "Mo og Laila" == "Laila, Mo" (Sorting)
    2. "Mathias," == "Mathias" (Punctuation cleanup)
    3. Empty columns == "none"
    """
    # Handle NaN/Empty
    if pd.isna(text) or str(text).strip() == "":
        return {"none"}

    text = str(text).lower().strip()

    # Standardize separators (Danish 'og', English 'and', '&')
    text = re.sub(r'\s+og\s+', ',', text)
    text = re.sub(r'\s+and\s+', ',', text)
    text = text.replace('&', ',')

    # Remove non-name characters (keep letters, hyphens, spaces)
    # This removes the trailing comma in "Jensen,"
    # We keep standard letters and Danish chars (æøå)
    text = re.sub(r'[^\w\s\-,æøåÆØÅ]', '', text)

    # Split, strip, and put into a set (ignoring order)
    # "Laila, Mo" -> {"laila", "mo"}
    names = {name.strip() for name in text.split(',') if name.strip()}

    if not names:
        return {"none"}

    return names


def main():
    print("Loading data...")
    if not os.path.exists(AI_RESULTS_FILE):
        print(f"Error: Could not find AI results file at {AI_RESULTS_FILE}")
        return

    # Check if manual file exists
    if not os.path.exists(MANUAL_FILE):
        print(f"Error: Could not find Manual file at {MANUAL_FILE}")
        return

    df_ai = pd.read_csv(AI_RESULTS_FILE)
    df_manual = pd.read_csv(MANUAL_FILE)

    # Filter out completely empty rows in manual file
    df_manual = df_manual.dropna(how='all')

    print(f"Comparing {len(df_manual)} rows...")

    correct_count = 0
    errors = []

    # Iterate through the manual file
    for i, manual_row in df_manual.iterrows():
        # Get the corresponding row from AI (assuming index alignment)
        if i not in df_ai.index:
            continue

        ai_row = df_ai.iloc[i]

        # Get Raw Values
        manual_raw = manual_row[MANUAL_HOST_COLUMN]
        ai_raw = ai_row[AI_HOST_COLUMN]
        description = str(manual_row.get('episodeDescription', ''))

        # Normalize both sides to sets of names
        manual_set = normalize_names(manual_raw)
        ai_set = normalize_names(ai_raw)

        # Compare sets (Order doesn't matter)
        if manual_set == ai_set:
            correct_count += 1
        else:
            errors.append({
                "id": i,
                "desc": description[:50] + "...",
                "AI": ai_raw,
                "Manual": manual_raw,
                "AI_clean": ai_set,
                "Manual_clean": manual_set
            })

    # --- REPORT ---
    limit = len(df_manual)
    accuracy = (correct_count / limit) * 100 if limit > 0 else 0

    print("\n" + "=" * 60)
    print(f"VALIDATION REPORT")
    print("=" * 60)
    print(f"Rows checked: {limit}")
    print(f"Correct:      {correct_count}")
    print(f"Errors:       {len(errors)}")
    print("-" * 60)
    print(f"ACCURACY SCORE: {accuracy:.2f}%")
    print("=" * 60)

    if errors:
        print("\n--- MISMATCHES (AI vs Manual) ---")
        for err in errors:
            print(f"\n[Row {err['id']}] {err['desc']}")
            print(f"🔴 Mismatch:")
            print(f"   AI Says:     '{err['AI']}'")
            print(f"   Manual Says: '{err['Manual']}'")


if __name__ == "__main__":
    main()
