import os
import tempfile
import base64
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import altair as alt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from risk_assessment.extract_pdf import extract_clauses
from risk_assessment.analyze_clauses import analyze_all_batches
from risk_assessment.notification_alert import send_compliance_alert

from config import ModelManager

# Load environment variables
load_dotenv()

# Styling
def add_custom_style():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
    
    .stApp {
        font-family: 'Poppins', sans-serif;
        transition: background 0.5s ease-in-out;
        font-size: 18px;
    }
    
    h1 {
        font-size: 2.5em !important;
        font-weight: 700 !important;
        transition: transform 0.3s ease, text-shadow 0.3s ease;
    }
    h1:hover {
        transform: scale(1.05);
        text-shadow: 0 0 10px rgba(0, 128, 255, 0.8);
    }

    h2, h3 {
        font-size: 1.6em !important;
    }

    .stContainer {
        background-color: rgba(255,255,255,0.9);
        border-radius: 14px;
        padding: 25px;
        box-shadow: 0 6px 35px rgba(0,0,0,0.1);
    }

    .stButton>button {
        font-size: 1.1em !important;
        padding: 12px 22px !important;
        border-radius: 8px !important;
    }
    .stButton>button:hover {
        background-color: #4CAF50;
        color: white;
        transform: scale(1.07);
    }

    .stFileUploader>div {
        font-size: 1.1em !important;
        padding: 18px !important;
    }
    .stFileUploader>div:hover {
        border: 2px dashed #4CAF50;
    }

    .stDataFrame, .dataframe {
        font-size: 1.05em !important;
    }

    .metric-container {
        font-size: 1.2em !important;
    }

    .glow { 
        box-shadow: 0 0 18px rgba(0, 128, 255, 0.5);
    }

    .bottom-right {
        text-align: right;
        margin-top: 30px;
    }
    .stButton>button:hover {
    transform: scale(1.05);
    background-color: #1e3c72;
    color: white;
    }

    </style>
    """, unsafe_allow_html=True)

# Background image
def add_background_image():
    image_path = "images/bgimg.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{encoded}"), 
                              linear-gradient(-45deg, #1e3c72, #2a5298);
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
        }}
        </style>
        """, unsafe_allow_html=True)

add_custom_style()
add_background_image()
st.set_page_config(page_title="AI Compliance Checker", layout="wide", page_icon="📑")

# Google Sheets 
GOOGLE_AUTH_FILE = "services.json"
GSHEET_ID = os.getenv("GSHEET_ID")
SHEET_NAME = "Sheet1"

creds = Credentials.from_service_account_file(
    GOOGLE_AUTH_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gs_client = gspread.authorize(creds)

spreadsheet = gs_client.open_by_key(GSHEET_ID)

# Only clear contract-specific sheets once per session
if "sheet_cleared" not in st.session_state:
    for ws in spreadsheet.worksheets():
        if ws.title != "Sheet1":
            ws.clear()
    st.session_state.sheet_cleared = True


# Session State
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "clauses" not in st.session_state:
    st.session_state.clauses = None
if "results" not in st.session_state:
    st.session_state.results = None
if "df" not in st.session_state:
    st.session_state.df = None
if "contracts" not in st.session_state:
    st.session_state.contracts = {}
if "current_contract" not in st.session_state:
    st.session_state.current_contract = None

# Header (Upload Page Only)
def show_header():
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: rgba(255,255,255,0.9); 
                border-radius: 12px; margin-bottom: 25px; box-shadow: 0px 6px 18px rgba(0,0,0,0.15);">
        <h1 style="color:#1e3c72;">📑 AI Powered Regulatory Compliance Checker</h1>
        <p style="font-size:1.25em; color:#333;">
            Upload a contract in PDF format to automatically extract clauses, 
            assess regulatory risks, and receive AI-powered compliance recommendations for improvement.
        </p>
    </div>
    """, unsafe_allow_html=True)

    image_path = "images/headimg.png"
    if os.path.exists(image_path):
        st.markdown(
            f"""
            <div style="text-align:center; margin-top:20px;">
                <img src="data:image/png;base64,{base64.b64encode(open(image_path, "rb").read()).decode()}" 
                     style="width:650px; max-width:95%; border-radius:12px;" />
            </div>
            """,
            unsafe_allow_html=True
        )
# Session State
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "clauses" not in st.session_state:
    st.session_state.clauses = None
if "results" not in st.session_state:
    st.session_state.results = None
if "df" not in st.session_state:
    st.session_state.df = None
if "contracts" not in st.session_state:  # <-- store all previous contracts
    st.session_state.contracts = {}
if "current_contract" not in st.session_state:
    st.session_state.current_contract = None

# Sidebar (Contract History with icons) 
def show_sidebar():
    st.sidebar.header("📂 Previous Contracts")

if st.session_state.contracts:
    contract_names = list(st.session_state.contracts.keys())
    options_with_icons = [f"📄 {name}" for name in contract_names]

    selected_with_icon = st.sidebar.radio(
        "Select a contract:",
        options=options_with_icons,
        index=contract_names.index(st.session_state.current_contract)
        if st.session_state.current_contract in contract_names else 0
    )

    selected = selected_with_icon[2:] 

    # Only load if a new contract is selected
    if selected != st.session_state.current_contract:
        contract = st.session_state.contracts[selected]
        st.session_state.current_contract = selected
        st.session_state.df = contract["df"]
        st.session_state.clauses = contract["clauses"]
        st.session_state.results = contract["results"]
        st.session_state.page = "results"
        st.rerun()
else:
    st.sidebar.info("🛈 No previous contracts yet.")

# Upload page
def upload_page():
    show_sidebar()
    show_header()
    uploaded_file = st.file_uploader("📝 Upload your contract (PDF)", type=["pdf"])
    batch_size = 5

    if uploaded_file:
        # 🔑 Reset results for every new upload
        st.session_state.clauses = None
        st.session_state.results = None
        st.session_state.df = None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        st.info("📂 Extracting clauses...")
        st.session_state.clauses = extract_clauses(tmp_path)

        with st.spinner("Analyzing clauses..."):
            progress = st.progress(0)
            results = []
            for i in range(0, len(st.session_state.clauses), batch_size):
                batch = st.session_state.clauses[i:i + batch_size]
                batch_results = analyze_all_batches(batch, start_id=i+1, batch_size=batch_size)
                results.extend(batch_results)
                progress.progress(min((i + batch_size) / len(st.session_state.clauses), 1.0))
            progress.empty()
            st.success("✅ Analysis completed!")
            st.session_state.results = results

        df = pd.DataFrame(st.session_state.results)
        df["Risk Score"] = df.get("Risk Score", "0%").fillna("0%")
        st.session_state.df = df

        try:
            rows = [st.session_state.df.columns.tolist()] + st.session_state.df.astype(str).values.tolist()

            # Contract-specific sheet name
            new_name = f"Contract {len(st.session_state.contracts)+1}"

            # Try to open existing sheet, else create
            try:
                ws = gs_client.open_by_key(GSHEET_ID).worksheet(new_name)
                ws.clear()
            except gspread.exceptions.WorksheetNotFound:
                ws = gs_client.open_by_key(GSHEET_ID).add_worksheet(title=new_name, rows="1000", cols="20")

            ws.update("A1", rows)

            # Save into contracts history
            st.session_state.contracts[new_name] = {
                "df": st.session_state.df.copy(),
                "clauses": st.session_state.clauses.copy(),
                "results": st.session_state.results.copy()
            }
            st.session_state.current_contract = new_name

            # Loader
            st.markdown(""" 
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                        background-color: white; display: flex; justify-content: center; 
                        align-items: center; z-index: 9999; font-size: 2.2em; color: #1e3c72;">
                ⏳ Loading Results...
            </div>
            """, unsafe_allow_html=True)

            st.session_state.page = "results"
            st.rerun()

        except Exception as e:
            st.error(f"⚠ Upload failed: {e}")

    # Go to Results Button 
    if st.session_state.df is not None and not st.session_state.df.empty:
        col1, col2, col3 = st.columns([6, 2, 1])  
        with col3:
            if st.button("➡ Go to Results", key="go_to_results"):
                st.session_state.page = "results"
                st.rerun()



# PDF Export Helper 
def generate_rewritten_pdf(df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>AI-Rewritten Contract Clauses Report</b>", styles["Title"]))
    story.append(Spacer(1, 20))

    for _, row in df.iterrows():
        clause_id = row["Clause ID"]
        original = row["Contract Clause"]
        risk_level = row.get("Risk Level", "Unknown")
        modified = row.get("AI-Modified Clause", "⚠️ Not available")
        modified_risk = row.get("AI-Modified Risk Level", "Unknown")

        story.append(Paragraph(f"<b>Clause ID:</b> {clause_id}", styles["Heading2"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>Original Risk Level:</b> {risk_level}", styles["Normal"]))
        story.append(Paragraph(f"<b>Original Clause:</b> {original}", styles["Normal"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>AI-Modified Clause:</b> {modified}", styles["Normal"]))
        story.append(Paragraph(f"<b>AI-Modified Risk Level:</b> {modified_risk}", styles["Normal"]))
        story.append(Spacer(1, 15))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# Mail alert modal
def email_modal(high, medium, low, gsheet_url):
    if "recipient_email" not in st.session_state:
        st.session_state.recipient_email = ""
    if "reset_email_field" not in st.session_state:
        st.session_state.reset_email_field = False

    # If reset flag is True, clear before rendering widget
    if st.session_state.reset_email_field:
        st.session_state.recipient_email = ""
        st.session_state.reset_email_field = False

    with st.form("email_form", clear_on_submit=True):
        st.markdown("### ✉️ Send Compliance Alert")
        st.caption("Enter recipient email or leave blank to use default compliance analyst.")

        recipient_email = st.text_input(
            "Recipient Email (optional)",
            key="recipient_email",
            placeholder="example@company.com"
        )

        col1, col2 = st.columns([1, 1])
        send_btn = col1.form_submit_button("📧 Send")
        cancel_btn = col2.form_submit_button("❌ Cancel")

        if send_btn:
            pdf_path = "ai_modified_clauses.pdf"
            pdf_data = generate_rewritten_pdf(st.session_state.df)
            with open(pdf_path, "wb") as f:
                f.write(pdf_data)

            success, msg = send_compliance_alert(
                subject="Compliance Risk Report",
                high_risk_count=high,
                medium_risk_count=medium,
                low_risk_count=low,
                gsheet_link=gsheet_url,
                recipient=recipient_email if recipient_email else None,
                contract_name=st.session_state.current_contract,
                contract_description=generate_contract_summary(st.session_state.df, st.session_state.current_contract),
                total_clauses=len(st.session_state.df),
                ai_modified_filepaths=[pdf_path] if os.path.exists(pdf_path) else []
            )

            if success:
                st.success(f"✅ Email sent to {recipient_email if recipient_email else 'default compliance analyst'}.")
                st.session_state.show_email_modal = False
                st.session_state.reset_email_field = True  
                st.rerun()
            else:
                st.error(f"⚠️ Failed to send: {msg}")

        elif cancel_btn:
            st.session_state.show_email_modal = False
            st.session_state.reset_email_field = True  
            st.info("❌ Email sending cancelled.")
            st.rerun()



# Results Page
def results_page():
    show_sidebar()   
    df = st.session_state.df
    if df is None or df.empty:
        st.error("No data available.")
        return

    # Page Header
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: rgba(255,255,255,0.9); 
                border-radius: 12px; margin-bottom: 25px; box-shadow: 0px 6px 18px rgba(0,0,0,0.15);">
        <h1 style="color:#1e3c72;">📊 Compliance Risk Analysis Results</h1>
        <p style="font-size:1.2em; color:#333;">
            Your contract has been analyzed clause-by-clause. The sections below summarize compliance risks, 
            provide a distribution overview, and highlight AI-generated recommendations for improvements.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📊 Results Summary")
    # Metrics
    st.markdown("###      Key Metrics:")
    st.info("These metrics summarize the overall compliance profile of your contract, "
            "helping you quickly assess areas that require the most attention.")

    high = df[df["Risk Level"] == "High"].shape[0]
    medium = df[df["Risk Level"] == "Medium"].shape[0]
    low = df[df["Risk Level"] == "Low"].shape[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Total Clauses", len(df))
    col2.metric("🔴 High Risk", high, "Clauses with high compliance risk")
    col3.metric("🟡 Medium Risk", medium, "Clauses with moderate compliance risk")
    col4.metric("🟢 Low Risk", low, "Clauses with low compliance risk")



    # Charts Section
    st.markdown("### 📊 Risk Level Distribution:")
    st.caption("Overview of how clauses are distributed across High, Medium, and Low risk levels.")

    risk_counts = df["Risk Level"].value_counts().reindex(["High", "Medium", "Low"], fill_value=0).reset_index()
    risk_counts.columns = ["Risk Level", "Count"]

    color_scale = alt.Scale(domain=["High", "Medium", "Low"], range=["red", "yellow", "green"])

    # Bar Chart
    bar_chart = (
        alt.Chart(risk_counts)
        .mark_bar()
        .encode(
            x=alt.X("Risk Level:N", sort=["High", "Medium", "Low"]),
            y="Count:Q",
            color=alt.Color("Risk Level:N", scale=color_scale),
            tooltip=["Risk Level", "Count"]
        )
        .properties(width=350, height=350)
    )

    # Pie Chart
    pie_chart = (
        alt.Chart(risk_counts)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta(field="Count", type="quantitative"),
            color=alt.Color("Risk Level:N", scale=color_scale),
            tooltip=["Risk Level", "Count"]
        )
        .properties(width=350, height=350)
    )

    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(bar_chart, use_container_width=True)
    with col2:
        st.altair_chart(pie_chart, use_container_width=True)

    # Clause Analysis
    st.markdown("### 📋 Clause Analysis:")

    desc_col, filter_col = st.columns([7, 2])
    with desc_col:
        st.caption(
            "This table provides a breakdown of each extracted clause with its assessed risk level. "
            "Use the filter on the right to focus on a specific risk category."
        )
    with filter_col:
        filter_option = st.selectbox(
            "Filter Risk Level",
            options=["All", "High", "Medium", "Low"],
            index=0,
            label_visibility="collapsed"
        )

    if filter_option != "All":
        filtered_df = df[df["Risk Level"] == filter_option]
    else:
        filtered_df = df

    # Drop AI-modified columns for this view
    analysis_df = filtered_df.drop(columns=["AI-Modified Clause", "AI-Modified Risk Level"], errors="ignore")
    st.dataframe(analysis_df, use_container_width=True, height=500)

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        " Download Filtered Clause Analysis CSV ",
        data=csv,
        file_name="clause_analysis.csv",
        mime="text/csv"
    )

    # AI-Rewritten Clauses Button with Description 
    st.markdown("### ⚡ AI-Modified Clauses")
    st.caption("High-risk clauses can be minimized by reviewing AI suggestions below.")

    if "show_rewrites" not in st.session_state:
        st.session_state.show_rewrites = False

    if not st.session_state.show_rewrites:
        st.markdown(
            "<div style='margin-bottom:10px;'>Do you want AI suggestions to minimize high-risk clauses? Click the button below.</div>",
            unsafe_allow_html=True
        )
        if st.button("⚡ Give AI-Modified Clauses"):
            st.session_state.show_rewrites = True
            st.rerun()

    # Show AI-modified clauses only if button clicked
    if st.session_state.show_rewrites:
        # Filter High-risk clauses
        high_risk_df = df[df["Risk Level"] == "High"].copy()
        
        if not high_risk_df.empty:
            if "AI-Modified Clause" not in high_risk_df.columns:
                high_risk_df["AI-Modified Clause"] = "⚠️ No rewritten version available"
            if "Clause Feedback & Fix" not in high_risk_df.columns:
                high_risk_df["Clause Feedback & Fix"] = "No feedback available"
            if "AI-Modified Risk Level" not in high_risk_df.columns:
                high_risk_df["AI-Modified Risk Level"] = "Unknown"

            keep_cols = [
                "Clause ID",
                "Contract Clause",
                "Risk Level",
                "AI-Modified Clause",
                "AI-Modified Risk Level"
            ]
            sugg_df = high_risk_df[[c for c in keep_cols if c in high_risk_df.columns]]

            # <-- make collapsible -->
            with st.expander("⚡ AI-Modified Clauses (click to expand)"):
                st.dataframe(sugg_df, use_container_width=True, height=400)

                sugg_csv = sugg_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    " Download AI-Modified Clauses CSV ",
                    data=sugg_csv,
                    file_name="ai_modified_clauses.csv",
                    mime="text/csv"
                )

                # PDF Download
                pdf_data = generate_rewritten_pdf(sugg_df)
                st.download_button(
                    "📄 Download AI-Modified Clauses PDF",
                    data=pdf_data,
                    file_name="ai_Modified_clauses.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("✅ No high-risk clauses to rewrite.")



    # Google Sheets Button
    current_name = st.session_state.current_contract

    # Try to get worksheet link safely
    try:
        ws = gs_client.open_by_key(GSHEET_ID).worksheet(current_name)
        gsheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit#gid={ws.id}"
    except gspread.exceptions.WorksheetNotFound:
        # fallback if the sheet is not found
        gsheet_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit"

    st.markdown(f"""
    <div style="text-align: left; margin-top: 15px;">
        <a href="{gsheet_url}" target="_blank">
            <button style="font-size:1.1em; background-color:#4285F4; color:white; padding:12px 22px; 
                        border-radius:6px; cursor:pointer;">
                📊 View Full Report in Google Sheets
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True)

    # Email Notification
    st.markdown("---")
    st.subheader("📧 Compliance Alert")

    # Generate PDF
    pdf_path = "ai_modified_clauses.pdf"
    pdf_data = generate_rewritten_pdf(df)
    with open(pdf_path, "wb") as f:
        f.write(pdf_data)

    # Use the same gsheet_url (safe version)
    if st.button("📨 Send to Compliance Officer"):
        success, msg = send_compliance_alert(
            subject="Compliance Risk Report",
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            gsheet_link=gsheet_url,
            recipient=None,
            contract_name=current_name,
            contract_description=generate_contract_summary(df, current_name),
            total_clauses=len(df),
            ai_modified_filepaths=[pdf_path] if os.path.exists(pdf_path) else []
        )
        if success:
            st.success("✅ Email sent.")
        else:
            st.error(f"⚠️ Failed to send: {msg}")

    # Custom Recipient
    with st.expander("✉️ Send to Another Recipient", expanded=False):
        email_modal(high, medium, low, gsheet_url)


# Back Button 
    col1, col2, col3 = st.columns([6, 2, 1])  # Adjust ratios for spacing
    with col3:
        if st.button("⬅ Go Back to Upload", key="back_to_upload"):
            st.session_state.page = "upload"
            st.rerun()

# Contract Summary 
def generate_contract_summary(df, contract_name: str) -> str:
    high = df[df["Risk Level"] == "High"].shape[0]
    medium = df[df["Risk Level"] == "Medium"].shape[0]
    low = df[df["Risk Level"] == "Low"].shape[0]
    total = len(df)

    # Build structured summary
    summary = f"Contract '{contract_name}' contains {total} clauses: "
    summary += f"{high} high risk, {medium} medium risk, {low} low risk. "
    return summary.strip()


# Router
if st.session_state.page == "upload":
    upload_page()
elif st.session_state.page == "results":
    results_page()
