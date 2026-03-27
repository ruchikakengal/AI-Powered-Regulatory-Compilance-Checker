from risk_assessment.extract_pdf import extract_clauses
from risk_assessment.ingestion_processing import ingest_to_sheet

# Path to your contract PDF
pdf_path ="contracts/sample.pdf"

# Step 1: Extract clauses from the PDF
clauses = extract_clauses(pdf_path)

# Step 2: Analyze and ingest results into Google Sheets
ingest_to_sheet(clauses, batch_size=3)