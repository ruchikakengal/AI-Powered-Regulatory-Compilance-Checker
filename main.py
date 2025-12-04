from risk_assessment.extract_pdf import extract_clauses
from risk_assessment.ingestion_processing import ingest_to_sheet

# Path to your contract PDF
pdf_path = r"C:\Users\satya\OneDrive\AI_Powered_Compilance_regulatory_checker\contracts\Law_Insider_americas-diamond-corp_exhibit-101-stock-purchase-agreement-stock-purchase-agreement-dated-as-of-february-11-2013-and-wi_Filed_01-03-2013_Contract.pdf"

# Step 1: Extract clauses from the PDF
clauses = extract_clauses(pdf_path)

# Step 2: Analyze and ingest results into Google Sheets
ingest_to_sheet(clauses, batch_size=3)