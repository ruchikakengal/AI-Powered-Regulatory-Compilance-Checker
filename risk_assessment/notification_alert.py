import os
import math
import base64
import smtplib
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
import matplotlib.pyplot as plt


# ----- Helper: generate a small bar chart and return base64 PNG -----
def generate_risk_chart_b64(high: int, medium: int, low: int) -> str:
    """Return base64 PNG (data URI-compatible) of risk distribution bar chart."""
    counts = [high, medium, low]
    labels = ['High', 'Medium', 'Low']

    # create a compact bar chart
    fig, ax = plt.subplots(figsize=(6, 3.2), dpi=100)
    bars = ax.bar(labels, counts, edgecolor='none')
    ax.grid(axis='y', linestyle='--', alpha=0.25)
    ax.set_ylabel('Clauses')
    ax.set_title('Risk Level Distribution', fontsize=12, pad=8)
    ax.set_ylim(0, max(1, max(counts) * 1.15))

    # add value labels above bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.02 * max(1, max(counts)),
                f'{int(height)}', ha='center', va='bottom', fontsize=10)

    # remove top/right spines for modern look
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png', transparent=False)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_b64

# ----- Helper: build the HTML email ----- 
def build_notification_email_html(
    contract_name: str,
    contract_description: str,
    total_clauses: int,
    high: int,
    medium: int,
    low: int,
    gsheet_url: str,
    chart_b64: str,
    ai_modified_files: list = None,
) -> str:
    """Return a polished HTML email as string. chart_b64 should be base64 PNG string."""
    ai_modified_files = ai_modified_files or []
    # percentages (safe)
    def pct(x):
        return f"{round((x / total_clauses * 100), 1)}%" if total_clauses > 0 else "0%"

    high_pct = pct(high)
    medium_pct = pct(medium)
    low_pct = pct(low)

    # colors / gradients (brand)
    primary = "#0033FF"
    accent = "#977DFF"
    neutral = "#333333"

    # build HTML
    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <style>
        body {{
          font-family: 'Helvetica Neue', Arial, sans-serif;
          background: #f7f8fb;
          margin: 0;
          padding: 20px;
          color: {neutral};
        }}
        .card {{
          max-width: 800px;
          margin: 0 auto;
          background: #ffffff;
          border-radius: 12px;
          box-shadow: 0 12px 30px rgba(20,20,50,0.08);
          overflow: hidden;
        }}
        .hero {{
          padding: 26px 28px;
          background: linear-gradient(90deg, {accent}, {primary});
          color: #fff;
        }}
        .hero h1 {{
          margin: 0;
          font-size: 22px;
          letter-spacing: -0.4px;
        }}
        .hero p {{
          margin: 8px 0 0 0;
          font-size: 13px;
          opacity: 0.95;
        }}
        .content {{
          padding: 22px 28px;
          color: {neutral};
        }}
        .section-title {{
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 10px;
        }}
        .summary-grid {{
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          margin-bottom: 16px;
        }}
        .metric {{
          flex: 1 1 140px;
          background: linear-gradient(180deg, rgba(0,0,0,0.03), #fff);
          padding: 12px;
          border-radius: 10px;
          text-align: center;
          box-shadow: 0 6px 18px rgba(0,0,0,0.04);
        }}
        .metric .value {{
          font-size: 18px;
          font-weight: 700;
          color: {primary};
        }}
        .metric .label {{
          font-size: 12px;
          color: #666;
        }}
        .chart {{
          text-align: center;
          margin: 18px 0;
        }}
        .cta {{
          text-align: center;
          margin-top: 18px;
        }}
        .btn {{
  display: inline-block;
  background: #21c66b;
  color: #fff;
  padding: 12px 20px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 700;
  box-shadow: 0 8px 22px rgba(33,198,107,0.14);
}}
        .next-steps {{
          margin-top: 18px;
          padding: 14px;
          border-radius: 10px;
          background: #fbfbff;
          font-size: 13px;
        }}
        .attachments {{
          margin-top: 14px;
          font-size: 13px;
        }}
        .footer {{
          font-size: 12px;
          color: #888;
          padding: 18px 28px;
          text-align: center;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="hero">
          <h1>Compliance Risk Report</h1>
          <p>Automated analysis for <strong>{contract_name}</strong></p>
        </div>

        <div class="content">
          <p style="margin:0 0 12px 0;"><strong>Greetings,</strong></p>
          <p style="margin:0 0 18px 0; color:#444;">
            Below is the summary of the compliance analysis for <strong>{contract_name}</strong>.
            <em style="display:block; margin-top:8px; color:#666;">{contract_description}</em>
          </p>

          <div class="section-title">Summary — Key Metrics</div>
          <div class="summary-grid">
            <div class="metric">
              <div class="value">{total_clauses}</div>
              <div class="label">Total Clauses</div>
            </div>
            <div class="metric">
              <div class="value">{high} ({high_pct})</div>
              <div class="label">High Risk</div>
            </div>
            <div class="metric">
              <div class="value">{medium} ({medium_pct})</div>
              <div class="label">Medium Risk</div>
            </div>
            <div class="metric">
              <div class="value">{low} ({low_pct})</div>
              <div class="label">Low Risk</div>
            </div>
          </div>

          <div class="section-title">Risk Distribution</div>
<div style="margin: 15px 0;">
  <div style="font-size:12px; margin-bottom:4px;">High Risk ({high})</div>
  <div style="width:100%; background:#eee; border-radius:6px; overflow:hidden;">
    <div style="width:{(high/total_clauses)*100 if total_clauses else 0}%; background:#ff4d4f; height:10px;"></div>
  </div>

  <div style="font-size:12px; margin:10px 0 4px;">Medium Risk ({medium})</div>
  <div style="width:100%; background:#eee; border-radius:6px; overflow:hidden;">
    <div style="width:{(medium/total_clauses)*100 if total_clauses else 0}%; background:#faad14; height:10px;"></div>
  </div>

  <div style="font-size:12px; margin:10px 0 4px;">Low Risk ({low})</div>
  <div style="width:100%; background:#eee; border-radius:6px; overflow:hidden;">
    <div style="width:{(low/total_clauses)*100 if total_clauses else 0}%; background:#52c41a; height:10px;"></div>
  </div>
</div>


          <div class="cta">
            <div style="font-size:13px; margin-bottom:8px; font-weight:600;">Full Report</div>
            <a class="btn" href="{gsheet_url}" target="_blank">Open Google Sheets Report</a>
          </div>

          <div class="next-steps">
            <div style="font-weight:700; margin-bottom:8px;">Recommended Next Steps</div>
            <ol style="margin:0 0 0 18px; padding:0;">
              <li>Review the detailed compliance report and analysis.</li>
              <li>Examine AI-rewritten clauses for safer alternatives.</li>
              <li>Evaluate AI-provided suggestions for risk mitigation.</li>
              <li>Implement corrective measures to reduce risks across all levels.</li>
            </ol>
          </div>

          <div class="attachments">
            <div style="font-weight:700; margin-bottom:8px;">Attachments</div>
            <ul style="margin:0; padding-left:18px;">
    """
    # list attachments in body
    if ai_modified_files:
        for f in ai_modified_files:
            fname = os.path.basename(f)
            html += f"<li>{fname} (attached)</li>"
    else:
        html += "<li>No AI-modified clause files attached.</li>"

    html += f"""
            </ul>
          </div>

          <p style="margin-top:18px; color:#666;">Closing,<br/>Compliance Automation Team</p>
        </div>

        <div class="footer">
          This report was generated automatically. If you prefer different recipients or need help, reply to this email.
        </div>
      </div>
    </body>
    </html>
    """
    return html


# ----- Example send function using SMTP (keeps your existing signature of returning (success, message)) -----
def send_compliance_alert(
    subject: str,
    high_risk_count: int,
    medium_risk_count: int,
    low_risk_count: int,
    gsheet_link: str,
    recipient: str = None,
    contract_name: str = "Contract",
    contract_description: str = "",
    total_clauses: int = 0,
    ai_modified_filepaths: list = None,
) -> tuple[bool, str]:


    """
    Sends a styled HTML compliance email with embedded chart and optional attachments.
    Returns (success: bool, message: str).
    """

    # config from env (set these in your deployment)
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")  # sender email
    SMTP_PASS = os.getenv("SMTP_PASS")  # app password or SMTP key
    EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER or "no-reply@example.com")
    EMAIL_TO = recipient or os.getenv("EMAIL_TO_DEFAULT", "compliance@example.com")

    ai_modified_filepaths = ai_modified_filepaths or []

    # Build chart
    try:
        chart_b64 = generate_risk_chart_b64(high_risk_count, medium_risk_count, low_risk_count)
    except Exception as e:
        return False, f"Chart generation failed: {e}"

    # Build HTML
    html_body = build_notification_email_html(
        contract_name=contract_name,
        contract_description=contract_description,
        total_clauses=total_clauses,
        high=high_risk_count,
        medium=medium_risk_count,
        low=low_risk_count,
        gsheet_url=gsheet_link,
        chart_b64=chart_b64,
        ai_modified_files=ai_modified_filepaths,
    )

    # Build MIME message
    msg = MIMEMultipart()
    msg['From'] = formataddr(("Compliance Bot", EMAIL_FROM))
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject

    # attach HTML
    msg.attach(MIMEText(html_body, 'html'))

    # attach files (AI modified reports, PDFs, etc.)
    for path in ai_modified_filepaths:
        try:
            with open(path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                msg.attach(part)
        except Exception as e:
            # continue attaching others but log
            print(f"Warning: failed to attach {path}: {e}")

    # send via SMTP
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()
        return True, "Email sent"
    except Exception as e:
        return False, f"SMTP send failed: {e}"
