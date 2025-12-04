import json
import re
import time
from groq import Groq
from config import GROQ_API_KEY, ModelManager

groq_client = Groq(api_key=GROQ_API_KEY)
model_manager = ModelManager()

# ---------------- Allowed Fields Schema ----------------
ALLOWED_FIELDS = {
    "Clause ID",
    "Contract Clause",
    "Regulation",
    "Risk Level",
    "Risk Score",
    "Clause Identification",
    "Clause Feedback & Fix",
    "AI-Modified Clause",
    "AI-Modified Risk Level"   # <-- added
}

# ---------------- Cleaner ----------------
def clean_clause_text(text: str) -> str:
    """Normalize clause text by stripping whitespace and collapsing spaces/newlines."""
    return re.sub(r"\s+", " ", (text or "")).strip()

# ---------------- Risk Score Normalizer ----------------
def normalize_risk_score(score) -> str:
    """Ensure Risk Score is always formatted as a percentage string (0%–100%)."""
    if score is None:
        return "0%"
    s = str(score).strip()
    # find first numeric portion (e.g. "65" or "65%" or "about 65 percent")
    match = re.search(r"\d{1,3}", s)
    if not match:
        return "0%"
    try:
        val = int(match.group(0))
    except Exception:
        return "0%"
    val = max(0, min(100, val))
    return f"{val}%"

# ---------------- Risk Level Normalizer ----------------
def normalize_risk_level(level) -> str:
    """Normalize risk-level-like strings to 'High' / 'Medium' / 'Low' / 'Unknown'."""
    if level is None:
        return "Unknown"
    s = str(level).strip().lower()
    if not s:
        return "Unknown"
    if "high" in s:
        return "High"
    if "med" in s:
        return "Medium"
    if "low" in s:
        return "Low"
    # numeric heuristics (if user provided score-like text)
    m = re.search(r"\d{1,3}", s)
    if m:
        v = int(m.group(0))
        if v >= 70:
            return "High"
        if v >= 40:
            return "Medium"
        return "Low"
    return "Unknown"

# ---------------- Clause Validity Checker ----------------
def is_valid_clause(clause: str) -> bool:
    """Rejects text that doesn't look like a real contract clause."""
    if not clause or len(clause.split()) < 5:  # too short
        return False
    # Skip common junk
    junk_patterns = ["Table of Contents", "Exhibit", "Signature", "Page", "Schedule", "Index"]
    if any(j.lower() in clause.lower() for j in junk_patterns):
        return False
    return True

# ---------------- Normalizer ----------------
def normalize_result(parsed, clauses, start_id):
    """
    Cleans AI output: ensures schema, strips unknown fields,
    fills defaults if missing, cleans whitespace.
    """
    normalized = []
    for i, cl in enumerate(clauses):
        if not is_valid_clause(cl):
            # Skip non-clauses (these will not be ingested)
            continue

        base = {
            "Clause ID": i + start_id,
            "Contract Clause": clean_clause_text(cl),
            "Regulation": "Unknown",
            "Risk Level": "Unknown",
            "Risk Score": "0%",
            "Clause Identification": "Unknown",
            "Clause Feedback & Fix": "No feedback or recommendation available.",
            "AI-Modified Clause": "No AI-modified clause available.",
            "AI-Modified Risk Level": "Unknown"  # default
        }

        try:
            ai_dict = parsed[i] if isinstance(parsed, list) and i < len(parsed) else {}
            if isinstance(ai_dict, dict):
                for k, v in ai_dict.items():
                    if k in ALLOWED_FIELDS:
                        if k == "Risk Score":
                            base[k] = normalize_risk_score(v)
                        elif k == "Risk Level":
                            base[k] = normalize_risk_level(v)
                        elif k == "AI-Modified Risk Level":
                            # normalize and force to Medium/Low if needed per rules
                            norm = normalize_risk_level(v)
                            # if the model returned High for AI-Modified, we lower it to Medium
                            if norm == "High":
                                norm = "Medium"
                            base[k] = norm
                        else:
                            base[k] = clean_clause_text(v) if isinstance(v, str) else v
        except Exception:
            pass

        # --- Fallback inference for AI-Modified Risk Level ---
        # If model didn't provide AI-Modified Risk Level but did provide a rewritten clause,
        # infer a safer level based on original Risk Level. This avoids Unknown states.
        if base.get("AI-Modified Risk Level", "Unknown") == "Unknown":
            modified_clause_present = base.get("AI-Modified Clause") and base.get("AI-Modified Clause") != "No AI-modified clause available."
            orig_rl = base.get("Risk Level", "Unknown")
            if modified_clause_present:
                if orig_rl == "High":
                    base["AI-Modified Risk Level"] = "Medium"
                elif orig_rl == "Medium":
                    base["AI-Modified Risk Level"] = "Low"
                elif orig_rl == "Low":
                    base["AI-Modified Risk Level"] = "Low"
                else:
                    # If original is Unknown but model rewrote, assume Medium (safer default)
                    base["AI-Modified Risk Level"] = "Medium"

        normalized.append(base)
    return normalized

# ---------------- Safe JSON Parser ----------------
def safe_json_parse(content, clauses, start_id):
    try:
        parsed = json.loads(content)
        return normalize_result(parsed, clauses, start_id)
    except:
        try:
            match = re.search(r"\[\s*{.*?}\s*\]", content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                return normalize_result(parsed, clauses, start_id)
        except:
            pass

    # fallback if parsing fails
    return normalize_result([], clauses, start_id)

# ---------------- Batch Analysis ----------------
def analyze_batch(clauses, start_id=1, retries=3, timeout=30):
    # Keep only valid clauses (this makes results consistent)
    clauses = [clean_clause_text(cl) for cl in clauses if is_valid_clause(cl)]

    regulation_list = (
        "GDPR, UK GDPR, HIPAA, SOX, ITAR, SEC, FCPA, PCI-DSS, RBI, SEBI, IT Act, "
        "CCPA, CPRA, GLBA, FERPA, COPPA, NIST, ISO 27001, SOC 2, SOC 1, SOC 3, "
        "FINRA, MiFID II, EMIR, DORA, eIDAS, PIPEDA, LGPD, PDPA, APPI, POPIA, "
        "BDSG, Swiss FADP, CIS Controls, NYDFS, MAS TRM, Basel III, AML/KYC, "
        "OFAC, EAR, Export Control Act, Bank Secrecy Act, FedRAMP, FISMA, "
        "HITECH, CMMC, CSA STAR, IRAP, ENS, NIS2, PSD2, ePrivacy Directive, "
        "DPA 2018 (UK), PECR, PRA/FCA (UK), OSFI (Canada), HKMA, SAMA, "
        "DFSA, DIFC, QFCRA, APRA CPS 234, OAIC (Australia), Privacy Act 1988, "
        "Brazil LGPD, Mexico Federal Data Law, Chile Data Protection Bill, "
        "South Africa POPIA, Kenya Data Protection Act, Nigeria NDPR, "
        "Singapore PDPA, Malaysia PDPA, India DPDP Act 2023, China PIPL, "
        "China CSL, China DSL, Russia Federal Data Law 152-FZ, UAE PDPL, "
        "Qatar PDP Law, Bahrain PDPL, Turkey KVKK"
    )

    prompt = f"""
You are a legal compliance analyst. Analyze the following contract clauses. 

For each contract clause, analyze risks and rewrite it into an "AI-Modified Clause" that strictly reduces risk.  

⚖️ Rules:
- The rewritten "AI-Modified Clause" must always reduce High risk into Medium/Low.
- Preserve the intent of the original clause but make it safer and compliant.
For each clause, return ONLY valid JSON in this format:

[
  {{
    "Clause ID": 1,
    "Contract Clause": "...",
    "Regulation": "Best matching regulation(s) from: {regulation_list}",
    "Risk Level": "High/Medium/Low (determine strictly based on regulation compliance risk. Never use Unknown.)",
    "Risk Score": "0%-100% (strictly must always include % sign)",
    "Clause Identification": "short explanation (max 100 words)",
    "Clause Feedback & Fix": "feedback with fix (max 100 words)",
    "AI-Modified Clause": "rewritten safer clause which always reduce High risk into Medium/Low",
    "AI-Modified Risk Level": "Reassess the rewritten clause's risk. Must be either Medium or Low, never High or Unknown."
  }}
]

Clauses:
{json.dumps([{"Clause ID": i + start_id, "Contract Clause": cl} for i, cl in enumerate(clauses)])}
"""

    for attempt in range(retries):
        model = model_manager.get_next_model()
        try:
            response = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a legal compliance analyst. Respond ONLY with valid JSON. Risk Score must include %."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0,
                timeout=timeout
            )
            content = response.choices[0].message.content
            return safe_json_parse(content, clauses, start_id)
        except Exception as e:
            print(f"Attempt {attempt + 1} with model '{model}' failed: {type(e).__name__} → {e}")
            time.sleep(2)

    print("All retries failed. Using fallback.")
    return safe_json_parse("[]", clauses, start_id)


# ---------------- Auto-Retry ----------------
def retry_failed_clauses(results, retries=1):
    final_results = []
    failed = []

    for res in results:
        if res["Risk Level"] == "Unknown" or res["Regulation"] == "Unknown":
            failed.append(res)
        else:
            final_results.append(res)

    if failed and retries > 0:
        print(f"Retrying {len(failed)} failed clauses...")
        retry_clauses = [f["Contract Clause"] for f in failed if is_valid_clause(f["Contract Clause"])]
        retried = analyze_batch(retry_clauses, start_id=failed[0]["Clause ID"])
        final_results.extend(retried)
    else:
        final_results.extend(failed)

    final_results.sort(key=lambda x: x["Clause ID"])
    return final_results

# ---------------- Batch Wrapper ----------------
def analyze_all_batches(clauses, start_id=1, batch_size=6, max_workers=3):
    results = []
    for i in range(0, len(clauses), batch_size):
        batch = clauses[i:i + batch_size]
        batch_results = analyze_batch(batch, start_id=start_id + i)
        batch_results = retry_failed_clauses(batch_results, retries=1)
        results.extend(batch_results)
    return results
