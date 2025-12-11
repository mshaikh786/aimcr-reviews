# app.py — place this file in the root of your cloned repo mshaikh786/aimcr-reviews
import streamlit as st
import json, os
from datetime import datetime
from pathlib import Path
import subprocess
import time

# ========================= CONFIG =========================
st.set_page_config(page_title="KAUST AIMCR Review", layout="wide")
st.title("KAUST AI Model Control Review (AIMCR)")

REPO_PATH = Path(__file__).parent.resolve()
DRAFTS_DIR = REPO_PATH / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True)

# ========================= GIT HELPERS =========================
def git_pull():
    subprocess.run(["git", "pull", "--rebase"], cwd=REPO_PATH, capture_output=True)

def git_add_commit_push(message: str):
    try:
        subprocess.run(["git", "add", "."], cwd=REPO_PATH, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_PATH,
                                capture_output=True, text=True)
        if status.stdout.strip():  # only commit if there are changes
            subprocess.run(["git", "commit", "-m", message], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "push"], cwd=REPO_PATH, check=True)
    except:
        pass

# Pull latest changes every time the app (re)loads
git_pull()

# ========================= DRAFT FUNCTIONS =========================
def list_drafts():
    return sorted(DRAFTS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)

def save_draft(data):
    pid = data.get("project_id", "UNKNOWN").strip() or "UNKNOWN"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{pid}_{ts}.json"
    path = DRAFTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    git_add_commit_push(f"draft: {pid} {ts}")
    return filename

def load_draft(filename):
    path = DRAFTS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ========================= SIDEBAR =========================
with st.sidebar:
    st.header("GitHub Sync – mshaikh786/aimcr-reviews")

    if st.button("Refresh from GitHub"):
        with st.spinner("Pulling latest changes…"):
            git_pull()
        st.success("Repository is now up-to-date!")
        st.rerun()

    drafts = list_drafts()
    if drafts:
        chosen = st.selectbox(
            "Resume existing draft",
            options=[""] + [d.name for d in drafts],
            format_func=lambda x: "— Select draft —" if not x else x[:-5].replace("_", " ")
        )
        if chosen and st.button("Load Draft"):
            st.session_state.data = load_draft(chosen)
            st.success(f"Loaded {chosen}")
            st.rerun()

    st.markdown("---")

    project_id = st.text_input("Project ID", value="PROJ001")
    today = datetime.now().strftime("%d-%m-%Y")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Draft", use_container_width=True):
            st.session_state.data["project_id"] = project_id
            st.session_state.data["crr_date"] = today
            name = save_draft(st.session_state.data)
            st.success(f"Draft saved → {name}")
    with c2:
        if st.button("FINAL SUBMIT", type="primary", use_container_width=True):
            if st.checkbox("I confirm this review is complete"):
                folder = REPO_PATH / f"AIMCR-{project_id}-{today}"
                folder.mkdir(exist_ok=True)
                with open(folder / "data.json", "w", encoding="utf-8") as f:
                    json.dump(st.session_state.data, f, indent=4, ensure_ascii=False)
                git_add_commit_push(f"FINAL AIMCR {project_id} {today}")
                st.balloons()
                st.success(f"Submitted to {folder.name}/")
                if "data" in st.session_state:
                    del st.session_state.data
                st.rerun()

    st.caption("Auto-save every 30 seconds")

# Auto-save every 30 seconds
if "data" in st.session_state:
    if time.time() - st.session_state.get("last_auto", 0) > 30:
        st.session_state.data["project_id"] = project_id
        st.session_state.data["crr_date"] = today
        save_draft(st.session_state.data)
        st.session_state.last_auto = time.time()
        st.rerun()

# ========================= INITIALISE DATA =========================
if "data" not in st.session_state:
    st.session_state.data = {
        "project_id": "PROJ001",
        "proposal_title": "",
        "principal_investigator": "",
        "proposal_date": "",
        "reviewer_name": "",
        "reviewer_id": "",
        "crr_date": datetime.now().strftime("%d-%m-%Y"),
        "third_party_software": [],
        "source_code": [],
        "datasets_user_files": [],
        "models": [],
    }

data = st.session_state.data

# ========================= HEADER – FROM ORIGINAL TEMPLATE =========================
st.markdown("## Proposal Information")
c1, c2 = st.columns(2)
with c1:
    data["project_id"] = st.text_input("Project ID", data.get("project_id", "PROJ001"))
    data["proposal_title"] = st.text_input("Proposal Title", data.get("proposal_title", ""))
    data["principal_investigator"] = st.text_input("Principal Investigator", data.get("principal_investigator", ""))
with c2:
    data["proposal_date"] = st.date_input("Proposal Date", value=datetime.today()).strftime("%d-%m-%Y")
    data["crr_date"] = st.date_input("CRR Date (Review Date)", value=datetime.today()).strftime("%d-%m-%Y")

st.markdown("## Reviewer Identification")
rc1, rc2 = st.columns(2)
with rc1:
    data["reviewer_name"] = st.text_input("Reviewer Name", data.get("reviewer_name", ""))
with rc2:
    data["reviewer_id"] = st.text_input("Reviewer ID", data.get("reviewer_id", ""))

st.markdown("**Conformance Score:** 1 = No Risk · 2 = Low · 3 = Medium · 4 = High · 5 = Critical")

# ========================= SECTIONS =========================
sections = [
    ("Third-Party Software (Packages, Libraries, Containers & Binaries)", "third_party_software", [
        "Open-source license compliance",
        "Known vulnerabilities (CVE)",
        "Supply chain risks (typosquatting, protestware)",
        "Binary/source origin verification",
        "Malicious code insertion risk",
        "Dependency pinning & reproducibility",
    ]),
    ("Source Code Screening Procedure", "source_code", [
        "Static code analysis (bandit, semgrep)",
        "Secrets scanning",
        "Malicious code patterns",
        "Code provenance & signing",
        "Backdoors/trojans",
        "Obfuscated code",
    ]),
    ("Datasets & User Files Screening Procedure", "datasets_user_files", [
        "Data poisoning risk",
        "PII / sensitive data leakage",
        "Copyright / licensing issues",
        "Adversarial examples",
        "Dataset provenance",
        "Jailbreak prompts in dataset",
    ]),
    ("Models Screening Procedure", "models", [
        "Model weights integrity (hash verification)",
        "Known unsafe/refusal-bypassed models",
        "Backdoor/trojan in weights",
        "Model card completeness",
        "Unsafe fine-tuning detected",
        "Export-controlled model",
    ]),
]

def calculate_section_risk(artifacts, checks):
    if not artifacts:
        return 0, False
    max_scores = [max(a["checks"].get(c, 1) for a in artifacts) for c in checks]
    return sum(max_scores), 5 in max_scores

overall_scores = []
has_critical = False

for title, key, checks in sections:
    st.markdown(f"### {title}")

    if st.button(f"+ Add Artifact – {title.split('(')[0].strip()}", key=f"add_{key}"):
        data[key].append({"name": f"Artifact {len(data[key])+1}", "checks": {c: 1 for c in checks}})

    st.metric("Artifacts", len(data[key]), delta=None)

    for idx, artifact in enumerate(data[key][:]):
        with st.expander(f"Artifact: {artifact['name']} ({idx+1})", expanded=True):
            artifact["name"] = st.text_input("Artifact name/ID", artifact["name"], key=f"name_{key}_{idx}")

            cols = st.columns(4)
            for i, check in enumerate(checks):
                with cols[i % 4]:
                    artifact["checks"][check] = st.selectbox(
                        check if len(check) <= 40 else check[:37] + "...",
                        options=[1, 2, 3, 4, 5],
                        format_func=lambda x: ["1-No", "2-Low", "3-Med", "4-High", "5-Critical"][x-1],
                        index=artifact["checks"].get(check, 1) - 1,
                        key=f"sel_{key}_{idx}_{i}"
                    )

            if st.button("Remove artifact", key=f"del_{key}_{idx}"):
                data[key].pop(idx)
                st.rerun()

    # Section risk
    if data[key]:
        score, critical = calculate_section_risk(data[key], checks)
        overall_scores.append(score)
        if critical:
            has_critical = True
        color = "red" if critical or score >= 21 else "orange" if score >= 15 else "green"
        level = "CRITICAL" if critical or score >= 21 else "HIGH" if score >= 15 else "MEDIUM" if score >= 10 else "LOW"
        st.markdown(f"**Section risk score: {score} → <span style='color:{color};font-size:1.2em;'>{level}</span>**",
                    unsafe_allow_html=True)
    st.markdown("---")

# ========================= FINAL SUMMARY =========================
total_risk = sum(overall_scores)
if total_risk >= 21 or has_critical:
    st.error(f"**CRITICAL RISK: {total_risk}** – Senior review and mitigation required before deployment.")
else:
    st.success(f"**Total risk score: {total_risk}** – Acceptable with standard controls.")

st.info(f"Final folder on submit: `AIMCR-{project_id}-{today}`")