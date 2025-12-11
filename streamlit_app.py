# app.py — place this file in the root of mshaikh786/aimcr-reviews
import streamlit as st
import json
from datetime import datetime
from pathlib import Path
import subprocess
import time
import os

# ========================= CONFIG =========================
st.set_page_config(page_title="KAUST AIMCR Review", layout="wide")
st.title("KAUST AI Model Control Review (AIMCR)")

# The repository we are currently in
REPO_PATH = Path(__file__).parent.resolve()
DRAFTS_DIR = REPO_PATH / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True)

# ========================= GIT HELPERS =========================
def git_pull():
    subprocess.run(["git", "pull", "--rebase"], cwd=REPO_PATH, capture_output=True)

def git_add_commit_push(message: str):
    try:
        subprocess.run(["git", "add", "."], cwd=REPO_PATH, check=True)
        result = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_PATH,
                                capture_output=True, text=True)
        if result.stdout.strip():  # only commit if there are changes
            subprocess.run(["git", "commit", "-m", message], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "push"], cwd=REPO_PATH, check=True)
    except subprocess.CalledProcessError:
        pass

# Pull on every app (re)load so we always have latest drafts
git_pull()

# ========================= DRAFT FUNCTIONS =========================
def list_drafts():
    return sorted(DRAFTS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)

def save_draft(data):
    project_id = data.get("project_id", "UNKNOWN").strip() or "UNKNOWN"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{project_id}_{timestamp}.json"
    path = DRAFTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    git_add_commit_push(f"draft: {project_id} {timestamp}")
    return filename

def load_draft(filename):
    path = DRAFTS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ========================= SIDEBAR =========================
with st.sidebar:
    st.header("Live Sync – mshaikh786/aimcr-reviews")

    if st.button("Refresh / Pull latest from GitHub"):
        with st.spinner("Pulling…"):
            git_pull()
        st.success("Up to date!")
        st.rerun()

    # Load draft
    drafts = list_drafts()
    if drafts:
        selected = st.selectbox(
            "Resume existing draft",
            options=[""] + [d.name for d in drafts],
            format_func=lambda x: "— Select draft —" if not x else x[:-5].replace("_", " ")
        )
        if selected and st.button("Load selected draft"):
            st.session_state.data = load_draft(selected)
            st.success(f"Loaded {selected}")
            st.rerun()

    st.markdown("---")

    project_id = st.text_input("Project ID", value="PROJ001", help="e.g. PROJ123")
    today = datetime.now().strftime("%d-%m-%Y")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Draft", use_container_width=True):
            st.session_state.data["project_id"] = project_id
            st.session_state.data["date"] = today
            name = save_draft(st.session_state.data)
            st.success(f"Draft saved as {name}")

    with col2:
        if st.button("FINAL SUBMIT", type="primary", use_container_width=True):
            confirm = st.checkbox("I confirm this review is complete")
            if confirm:
                folder = REPO_PATH / f"AIMCR-{project_id}-{today}"
                folder.mkdir(exist_ok=True)
                final_file = folder / "data.json"
                with open(final_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.data, f, indent=4, ensure_ascii=False)
                git_add_commit_push(f"FINAL AIMCR {project_id} {today}")
                st.balloons()
                st.success(f"Submitted → {folder.name}/")
                # optional: clear session
                if "data" in st.session_state:
                    del st.session_state.data
                st.rerun()

    st.caption("Auto-save every 30 seconds")

# Auto-save every 30 s
if "data" in st.session_state:
    if time.time() - st.session_state.get("last_auto", 0) > 30:
        st.session_state.data["project_id"] = project_id
        st.session_state.data["date"] = today
        save_draft(st.session_state.data)
        st.session_state.last_auto = time.time()
        st.rerun()

# ========================= INITIALISE DATA =========================
if "data" not in st.session_state:
    st.session_state.data = {
        "project_id": project_id,
        "date": datetime.now().strftime("%d-%m-%Y"),
        "reviewer": "",
        "third_party_software": [],
        "source_code": [],
        "datasets_user_files": [],
        "models": [],
    }

data = st.session_state.data
data["project_id"] = project_id
data["date"] = today

# ========================= MAIN FORM =========================
st.subheader("Reviewer Identification")
data["reviewer"] = st.text_input("Reviewer Name", value=data.get("reviewer", ""))

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

# Risk calculation helper
def calculate_section_risk(artifacts, checks):
    if not artifacts:
        return 0, False
    maxes = []
    for check in checks:
        scores = [a["checks"].get(check, 1) for a in artifacts]
        if scores:
            maxes.append(max(scores))
        else:
            maxes.append(1)
    total = sum(maxes)
    critical = 5 in maxes
    return total, critical

overall_scores = []
has_critical = False

for title, key, checks in sections:
    st.markdown(f"### {title}")

    col_add, col_count = st.columns([3,1])
    with col_add:
        if st.button(f"+ Add Artifact – {title.split('(')[0].strip()}", key=f"add_{key}"):
            data[key].append({"name": f"Artifact {len(data[key])+1}", "checks": {c: 1 for c in checks}})
    with col_count:
        st.metric("Artifacts", len(data[key]))

    for idx, artifact in enumerate(data[key][:]):
        with st.expander(f"Artifact: {artifact['name']} ({idx+1})", expanded=True):
            artifact["name"] = st.text_input("Artifact name/ID", artifact["name"], key=f"name_{key}_{idx}")

            cols = st.columns(4)
            for i, check in enumerate(checks):
                with cols[i % 4]:
                    artifact["checks"][check] = st.selectbox(
                        check[:35] + ("…" if len(check)>35 else ""),
                        options=[1,2,3,4,5],
                        format_func=lambda x: ["1-No","2-Low","3-Med","4-High","5-Critical"][x-1],
                        index=artifact["checks"].get(check, 1)-1,
                        key=f"score_{key}_{idx}_{i}"
                    )

            if st.button("Remove artifact", key=f"del_{key}_{idx}"):
                data[key].pop(idx)
                st.rerun()

    # Section summary
    if data[key]:
        score, crit = calculate_section_risk(data[key], checks)
        overall_scores.append(score)
        if crit:
            has_critical = True
        color = "red" if crit or score >= 21 else "orange" if score >= 15 else "green"
        st.markdown(f"**Section risk score: {score} → <span style='color:{color};font-size:1.2em;'>{
            'CRITICAL' if crit or score >= 21 else 'HIGH' if score >= 15 else 'MEDIUM' if score >= 10 else 'LOW'}</span>**", 
            unsafe_allow_html=True)
    else:
        st.info("No artifacts yet")
    st.markdown("---")

# ========================= FINAL SUMMARY =========================
st.header("Overall Risk Summary")
total = sum(overall_scores) if overall_scores else 0

if total >= 21 or has_critical:
    st.error(f"**CRITICAL RISK: {total}** – Senior review and mitigation required before deployment.")
else:
    st.success(f"**Total risk score: {total}** – Acceptable with standard controls.")

st.info(f"Final folder on submit: `AIMCR-{project_id}-{today}`")