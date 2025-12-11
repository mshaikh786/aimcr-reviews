# app.py — Final version, faithful to KAUST AIMCR template
import streamlit as st
from datetime import datetime
from pathlib import Path
import subprocess
import json
import time

st.set_page_config(page_title="KAUST AIMCR", layout="wide")
st.title("KAUST AI Model Control Review (AIMCR)")

# === REPO & PATHS ===
REPO_PATH = Path(__file__).parent.resolve()
DRAFTS_DIR = REPO_PATH / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True)

# === GIT HELPERS ===
def git_pull():
    subprocess.run(["git", "pull", "--rebase"], cwd=REPO_PATH, capture_output=True, check=True)

def git_add_commit_push(msg):
    try:
        subprocess.run(["git", "add", "."], cwd=REPO_PATH, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO_PATH, check=True)
        subprocess.run(["git", "push"], cwd=REPO_PATH, check=True)
    except:
        pass

git_pull()

# === DRAFTS ===
def list_drafts():
    return sorted(DRAFTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

def save_draft(data):
    pid = data.get("project_id", "UNKNOWN") or "UNKNOWN"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file = DRAFTS_DIR / f"{pid}_{ts}.json"
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    git_add_commit_push(f"draft: {pid} {ts}")
    return file.name

def load_draft(name):
    with open(DRAFTS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)

# === SIDEBAR ===
with st.sidebar:
    st.header("mshaikh786/aimcr-reviews")
    if st.button("Pull latest from GitHub"):
        with st.spinner("Syncing…"):
            git_pull()
        st.success("Synced")
        st.rerun()

    drafts = list_drafts()
    if drafts:
        sel = st.selectbox("Resume draft", [""] + [d.name for d in drafts],
                           format_func=lambda x: x[:-5].replace("_", " ") if x else "— Select —")
        if sel and st.button("Load"):
            st.session_state.data = load_draft(sel)
            st.rerun()

    project_id = st.text_input("Project ID", "PROJ001")
    today = datetime.now().strftime("%d-%m-%Y")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Draft"):
            st.session_state.data["project_id"] = project_id
            st.session_state.data["crr_date"] = today
            save_draft(st.session_state.data)
            st.success("Draft saved")
    with c2:
        if st.button("FINAL SUBMIT", type="primary"):
            if st.checkbox("Confirm complete"):
                folder = REPO_PATH / f"AIMCR-{project_id}-{today}"
                folder.mkdir(exist_ok=True)
                with open(folder / "data.json", "w") as f:
                    json.dump(st.session_state.data, f, indent=4, ensure_ascii=False)
                git_add_commit_push(f"FINAL: {project_id}")
                st.balloons()
                st.success("Submitted!")
                del st.session_state.data
                st.rerun()

# Auto-save
if "data" in st.session_state:
    if time.time() - st.session_state.get("last", 0) > 30:
        st.session_state.data["project_id"] = project_id
        st.session_state.data["crr_date"] = today
        save_draft(st.session_state.data)
        st.session_state.last = time.time()
        st.rerun()

# === INIT DATA ===
if "data" not in st.session_state:
    st.session_state.data = {
        "project_id": "PROJ001",
        "proposal_title": "",
        "principal_investigator": "",
        "proposal_date": "",
        "reviewer_name": "",
        "reviewer_id": "",
        "crr_date": today,
        "third_party_software": [],
        "source_code": [],
        "datasets_user_files": [],
        "models": [],
    }

data = st.session_state.data

# === HEADER ===
st.markdown("## Proposal Information")
c1, c2 = st.columns(2)
with c1:
    data["project_id"] = st.text_input("Project ID", data.get("project_id",""))
    data["proposal_title"] = st.text_input("Proposal Title", data.get("proposal_title",""))
    data["principal_investigator"] = st.text_input("Principal Investigator", data.get("principal_investigator",""))
with c2:
    data["proposal_date"] = st.date_input("Proposal Date", datetime.today()).strftime("%d-%m-%Y")
    data["crr_date"] = st.date_input("CRR Date", datetime.today()).strftime("%d-%m-%Y")

st.markdown("## Reviewer Identification")
r1, r2 = st.columns(2)
with r1:
    data["reviewer_name"] = st.text_input("Reviewer Name", data.get("reviewer_name",""))
with r2:
    data["reviewer_id"] = st.text_input("Reviewer ID", data.get("reviewer_id",""))

st.markdown("**Risk Score:** 1=No Risk · 2=Low · 3=Medium · 4=High · 5=Critical")

# === CHECK DEFINITIONS (exactly as in template) ===
checks = {
    "third_party_software": [
        "Open-source license compliance",
        "Known vulnerabilities (CVE)",
        "Supply chain risks (typosquatting, protestware)",
        "Binary/source origin verification",
        "Malicious code insertion risk",
        "Dependency pinning & reproducibility",
    ],
    "source_code": [
        "Static code analysis (bandit, semgrep)",
        "Secrets scanning",
        "Malicious code patterns",
        "Code provenance & signing",
        "Backdoors/trojans",
        "Obfuscated code",
    ],
    "datasets_user_files": [
        "Data poisoning risk",
        "PII / sensitive data leakage",
        "Copyright / licensing issues",
        "Adversarial examples",
        "Dataset provenance",
        "Jailbreak prompts in dataset",
    ],
    "models": [
        "Model weights integrity (hash verification)",
        "Known unsafe/refusal-bypassed models",
        "Backdoor/trojan in weights",
        "Model card completeness",
        "Unsafe fine-tuning detected",
        "Export-controlled model",
    ]
}

# === RENDER SECTION WITH REAL TABLES ===
def render_section(title, key):
    st.markdown(f"### {title}")
    if st.button(f"+ Add Artifact — {title.split('(')[0].strip()}", key=f"add_{key}"):
        data[key].append({"name": f"Artifact {len(data[key])+1}", "checks": {c: {"score":1,"notes":""} for c in checks[key]}})

    for idx, artifact in enumerate(data[key]):
        with st.expander(f"Artifact: {artifact['name']} ({idx+1})", expanded=True):
            artifact["name"] = st.text_input("Artifact Name/ID", artifact["name"], key=f"name_{key}_{idx}")

            # Table header
            cols = st.columns([5, 1.5, 4])
            cols[0].markdown("**Check Description**")
            cols[1].markdown("**Risk Score**")
            cols[2].markdown("**Notes / Evidence**")

            for check_name in checks[key]:
                row_cols = st.columns([5, 1.5, 4])
                row_cols[0].write(check_name)
                current = artifact["checks"][check_name]
                score = row_cols[1].selectbox(
                    "score", [1,2,3,4,5],
                    format_func=lambda x: ["1-No","2-Low","3-Med","4-High","5-Critical"][x-1],
                    index=current["score"]-1,
                    key=f"score_{key}_{idx}_{check_name}"
                )
                notes = row_cols[2].text_area("", current["notes"], height=60, key=f"notes_{key}_{idx}_{check_name}")
                artifact["checks"][check_name] = {"score": score, "notes": notes}

            if st.button("Remove artifact", key=f"del_{key}_{idx}"):
                data[key].pop(idx)
                st.rerun()

    # Section risk
    if data[key]:
        maxes = [max(a["checks"][c]["score"] for a in data[key]) for c in checks[key]]
        total = sum(maxes)
        critical = 5 in maxes
        color = "red" if critical or total>=21 else "orange" if total>=15 else "green"
        level = "CRITICAL" if critical or total>=21 else "HIGH" if total>=15 else "MEDIUM" if total>=10 else "LOW"
        st.markdown(f"**Section Risk Score: {total} → <span style='color:{color};font-size:1.3em;'>{level}</span>**", unsafe_allow_html=True)

# === RENDER ALL SECTIONS ===
render_section("Third-Party Software (Packages, Libraries, Containers & Binaries)", "third_party_software")
render_section("Source Code Screening Procedure", "source_code")
render_section("Datasets & User Files Screening Procedure", "datasets_user_files")
render_section("Models Screening Procedure", "models")

# === FINAL SUMMARY ===
section_totals = []
has_crit = False
for k, clist in checks.items():
    if data[k]:
        secs = [a["checks"][c]["score"] for a in data[k] for c in clist]
        maxes = [max(a["checks"][c]["score"] for a in data[k]) for c in clist]
        section_totals.append(sum(maxes))
        if 5 in maxes: has_crit = True

total_risk = sum(section_totals)
if total_risk >= 21 or has_crit:
    st.error(f"**FINAL RISK: {total_risk} — CRITICAL**")
else:
    st.success(f"**FINAL RISK: {total_risk} — Acceptable**")

st.info(f"Final folder on submit: `AIMCR-{project_id}-{today}`")