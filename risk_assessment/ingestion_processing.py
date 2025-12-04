import os
import time
from dotenv import load_dotenv
import gspread
from tqdm import tqdm
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()

# Import the batch analysis function from analyze_clauses
from risk_assessment.analyze_clauses import analyze_all_batches

# Google Sheets setup
google_auth_file = "services.json"
google_sheet_scope = ["https://www.googleapis.com/auth/spreadsheets"]
gsheet_id = os.getenv("GSHEET_ID")
sheet_name = "Sheet1"

creds = Credentials.from_service_account_file(google_auth_file, scopes=google_sheet_scope)
gs_client = gspread.authorize(creds)

# Retry logic for transient API errors
max_retries = 5
retry_delay = 5  # seconds

for attempt in range(max_retries):
    try:
        worksheet = gs_client.open_by_key(gsheet_id).worksheet(sheet_name)
        break  # Success
    except gspread.exceptions.WorksheetNotFound:
        worksheet = gs_client.open_by_key(gsheet_id).add_worksheet(title=sheet_name, rows="100", cols="20")
        break
    except gspread.exceptions.APIError as e:
        print(f"Attempt {attempt + 1} failed with APIError: {e}")
        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            raise e  # Give up after max retries

# Clause ingestion and analysis
def ingest_to_sheet(clauses, batch_size=6, max_workers=3):
    """
    Analyze clauses in batches and upload results to Google Sheets.
    """
    rows = [
        ["Clause ID", "Contract Clause", "Regulation", "Risk Level", "Risk Score",
         "Clause Identification", "Clause Feedback & Fix", "AI-Modified Clause", "AI-Modified Risk Level"]
    ]

    # Process clauses in batches
    for i in tqdm(range(0, len(clauses), batch_size), desc="Processing Batches"):
        batch = clauses[i:i + batch_size]

        # Analyze the batch using multiple workers
        results = analyze_all_batches(batch, start_id=i + 1, max_workers=max_workers)

        # Append results to rows
        for res in results:
            rows.append([
                res.get("Clause ID"),
                res.get("Contract Clause"),
                res.get("Regulation"),
                res.get("Risk Level"),
                res.get("Risk Score", "0%"),
                res.get("Clause Identification"),
                res.get("Clause Feedback & Fix", "No feedback or recommendation available."),
                res.get("AI-Modified Clause", "No AI-modified clause available."),
                res.get("AI-Modified Risk Level", "Unknown")
            ])

    # Clear existing content and update sheet
    worksheet.clear()
    worksheet.update(values=rows, range_name="A1")

