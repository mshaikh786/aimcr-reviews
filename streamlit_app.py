import streamlit as st
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import shutil
from helper_functions import (calculate_section_risk,
                              compute_merged_section_risk,
                              create_folder_structure,
                              get_risk_color,
                              load_draft, delete_draft,
                              get_draft_files, save_draft,
                              save_final_submission,
                              save_to_json,
                              setup_local_workspace,
                              push_to_github,
                              get_submission_files,
                              load_submission,
                              archive_draft_as_checkpoint,
                              get_checkpoints,
                              load_checkpoint)

# Page configuration
st.set_page_config(
    page_title="AI Model Control Review (AIMCR)",
    page_icon="🔍",
    layout="wide"
)

# GitHub Configuration
GITHUB_REPO = "mshaikh786/aimcr-reviews"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO}.git"
LOCAL_REPO_PATH = Path.cwd() / ".aimcr_workspace"

# Initialize workspace on startup
if 'workspace_initialized' not in st.session_state:
    with st.spinner("Initializing workspace and syncing with GitHub..."):
        success, message = setup_local_workspace(LOCAL_REPO_PATH, GITHUB_REPO_URL)
        if success:
            st.session_state.workspace_initialized = True
        else:
            st.error(f"⚠️ Could not sync with GitHub: {message}")
            st.info("You can still use the application locally. Drafts will be saved locally only.")
            LOCAL_REPO_PATH.mkdir(parents=True, exist_ok=True)
            st.session_state.workspace_initialized = True

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = {
        'metadata': {
            'proposal_title': '',
            'principal_investigator': '',
            'proposal_date': '',
            'reviewer_name': '',
            'reviewer_id': '',
            'aimcr_date': '',
            'project_id': ''
        },
        'third_party_software': [],
        'source_code': [],
        'datasets_user_files': [],
        'models': [],
        'observations': '',
        'recommendation': '',
        'addenda': []
    }

if 'current_section' not in st.session_state:
    st.session_state.current_section = 'metadata'

if 'edit_index' not in st.session_state:
    st.session_state.edit_index = {}

if 'addendum_edit_index' not in st.session_state:
    st.session_state.addendum_edit_index = {}  # key: (addendum_idx, section_key) -> artifact_idx

if 'active_addendum' not in st.session_state:
    st.session_state.active_addendum = None  # index of addendum being expanded/edited

# Track if we're editing an existing submission
if 'editing_submission' not in st.session_state:
    st.session_state.editing_submission = False

if 'original_submission_folder' not in st.session_state:
    st.session_state.original_submission_folder = None

# Risk scoring configuration
RISK_LEVELS = {
    1: "No Risk",
    2: "Low Risk",
    3: "Medium Risk",
    4: "High Risk",
    5: "Critical Risk"
}

# Help text for each check type - organized by section with exact text from AIMCR template
# Format: {section_key: {check_name: "Description / Guidance\n\nExample(s) / Reference"}}
SECTION_CHECK_HELP = {
    'third_party_software': {
        'Project & Usage Alignment': "Description / Guidance: Confirm the software is associated with an approved project and matches the project's scientific domain and objectives.\n\nExample(s) / Reference: Reference table of approved uses in 'Research Topics Descriptions' workbook.",
        
        'Prohibited Use Screening (LC 2.7)': "Description / Guidance: Review for any indication of prohibited uses/functionality (e.g., military, weapons, surveillance). Explicitly reference LC 2.7.\n\nExample(s) / Reference: Package description includes 'surveillance' or 'military' functionality.",
        
        'D5+M affiliation Screening (LC 2.5)': "Description / Guidance: Scan/review software origin, contributors, and metadata for restricted countries/entities. Explicitly reference LC 2.5.\n\nExample(s) / Reference: Maintainer from D:5 country, Entity List, SDN List.",
        
        'Source / Provenance': "Description / Guidance: Verify source repository authenticity and integrity; review dependencies for provenance and approval status.\n\nExample(s) / Reference: Software from official GitHub repo; dependencies from trusted sources.",
        
        'License / Permissions': "Description / Guidance: Confirm the license allows the intended use (research, redistribution, modification). Identify any obligations or restrictions.\n\nExample(s) / Reference: Package licensed under MIT; no non-commercial clause.",
        
        'Bundled Tools / Dependencies': "Description / Guidance: Check bundled tools, utilities, dependencies, and sub-dependencies for prohibited functionality or untrusted sources.\n\nExample(s) / Reference: Dependency list includes only approved packages; no suspicious binaries."
    },
    
    'source_code': {
        'Project & Usage Alignment': "Description / Guidance: Confirm the code is associated with an approved project and matches the project's scientific domain and objectives.\n\nExample(s) / Reference: Reference table of approved uses in 'Research Topics Descriptions' workbook.",
        
        'Prohibited Use Screening (LC 2.7)': "Description / Guidance: Review the project proposal, code and documentation for any indication of prohibited uses/functionality (e.g., military, weapons, surveillance). Explicitly reference LC 2.7.\n\nExample(s) / Reference: Code contains functions or comments related to 'military' or 'surveillance' applications.",
        
        'Source / Provenance & D5+M Affiliation Screening (LC 2.5)': "Description / Guidance: Verify source repository authenticity and integrity; review dependencies for provenance and approval status; scan/review code origin, contributors, and metadata for restricted countries/entities. Explicitly reference LC 2.5.\n\nExample(s) / Reference: Code from official GitHub repo; contributors from trusted countries; no links to D:5 country, Entity List, SDN List.",
        
        'License / Permissions': "Description / Guidance: Confirm the license allows the intended use (research, redistribution, modification). Identify any obligations or restrictions.\n\nExample(s) / Reference: Code licensed under MIT; no non-commercial clause.",
        
        'Dependencies / Bundled Components': "Description / Guidance: Check dependencies and sub-dependencies for prohibited functionality or untrusted sources.\n\nExample(s) / Reference: Dependency list includes only approved packages; no suspicious binaries.",
        
        'Sample Inspection': "Description / Guidance: Open a subset of the code and check for indications of prohibited use, ambiguous content, or technical parameters associated with prohibited applications.\n\nExample(s) / Reference: Review 10% of scripts for prohibited keywords or functions."
    },
    
    'datasets_user_files': {
        'Project & Usage Alignment': "Description / Guidance: Confirm the dataset & files are associated with an approved project and match the project's scientific domain and objectives.\n\nExample(s) / Reference: Reference table of approved uses in 'Research Topics Descriptions' workbook.",
        
        'Prohibited Use Screening (LC 2.7)': "Description / Guidance: Review for any indication of prohibited uses (e.g., military, weapons, surveillance). Explicitly reference LC 2.7.\n\nExample(s) / Reference: Dataset contains 'military' or 'surveillance' keywords.",
        
        'D5+M affiliation Screening (LC 2.5)': "Description / Guidance: Scan/review dataset fields, variables, and metadata for restricted countries/entities. Explicitly reference LC 2.5.\n\nExample(s) / Reference: Data from/about D:5 countries, Entity List, SDN List.",
        
        'Prompts / Fine-tuning Scripts': "Description / Guidance: Scan/review prompts and fine-tuning scripts for keywords or instructions that could enable or encourage non-compliant outputs or domains.\n\nExample(s) / Reference: Prompt includes 'target military installation'.",
        
        'Sample Inspection': "Description / Guidance: Open a subset† of the data and check for indications of prohibited use (e.g., geospatial coordinates, military terminology, data from/about restricted countries/entities, technical parameters).\n\nExample(s) / Reference: 1% sample for ≤10,000 records, 0.1% for ≤100,000, etc.",
        
        'Provenance': "Description / Guidance: Review the dataset's provenance: source, country of origin, previous owners/custodians, modifications or transformations.\n\nExample(s) / Reference: Dataset originally collected by Org X, modified by Y.",
        
        'License / Permissions': "Description / Guidance: Confirm the license allows the intended use (research, redistribution, modification). Identify any obligations or restrictions.\n\nExample(s) / Reference: Dataset licensed under MIT, no non-commercial clause."
    },
    
    'models': {
        'Project & Usage Alignment': "Description / Guidance: Confirm the model is associated with an approved project and matches the project's scientific domain and objectives.\n\nExample(s) / Reference: Reference table of approved uses in 'Research Topics Descriptions' workbook.",
        
        'Prohibited Use Screening (LC 2.7)': "Description / Guidance: Review the model and documentation for any indication of prohibited uses/functionality (e.g., military, weapons, surveillance). Explicitly reference LC 2.7.\n\nExample(s) / Reference: Model documentation includes references to 'military' or 'surveillance' applications.",
        
        'Source / Provenance & D5+M Affiliation Screening (LC 2.5)': "Description / Guidance: Confirm model (architecture and weights) was obtained from a trusted internal registry, approved vendor or trusted official repositories; assess training data and model provenance; flag involvement from prohibited entities. Explicitly reference LC 2.5.\n\nExample(s) / Reference: Model downloaded from official registry; training data from trusted sources; no links to D:5 country, Entity List, SDN List.",
        
        'License / Permissions': "Description / Guidance: Assess permissions: Confirm the license of the model and its training data allows the intended use (research, redistribution, modification). Identify any obligations or restrictions.\n\nExample(s) / Reference: Model licensed under MIT; training data with open license.",
        
        'Training Data Documentation': "Description / Guidance: Review training data documentation for provenance, compliance, and absence of restricted entities or prohibited content.\n\nExample(s) / Reference: Training data sourced from approved datasets; documentation complete.",
        
        'Customisation / Fine-tuning': "Description / Guidance: Check for evidence that the model has been customised or fine-tuned for exclusively generating outputs that support prohibited domains.\n\nExample(s) / Reference: Model fine-tuned for prohibited applications (e.g., weapon design, surveillance strategies).",
        
        'FLOPS Calculation': "Description / Guidance: For proprietary models, estimate training FLOPS and further usage FLOPS on Shaheen III; escalate if total exceeds 10^27.\n\nExample(s) / Reference: Model trained with 10^25 FLOPS; planned usage within allowed limits.",
        
        'Sample Inspection': "Description / Guidance: Open a subset of the model outputs or scripts and check for indications of prohibited use, ambiguous content, or technical parameters associated with prohibited applications.\n\nExample(s) / Reference: Review 10% of outputs for prohibited keywords or functions."
    }
}

# Section configurations
SECTION_CHECKS = {
    'third_party_software': [
        'Project & Usage Alignment',
        'Prohibited Use Screening (LC 2.7)',
        'D5+M affiliation Screening (LC 2.5)',
        'Source / Provenance',
        'License / Permissions',
        'Bundled Tools / Dependencies'
    ],
    'source_code': [
        'Project & Usage Alignment',
        'Prohibited Use Screening (LC 2.7)',
        'Source / Provenance & D5+M Affiliation Screening (LC 2.5)',
        'License / Permissions',
        'Dependencies / Bundled Components',
        'Sample Inspection'
    ],
    'datasets_user_files': [
        'Project & Usage Alignment',
        'Prohibited Use Screening (LC 2.7)',
        'D5+M affiliation Screening (LC 2.5)',
        'Prompts / Fine-tuning Scripts',
        'Sample Inspection',
        'Provenance',
        'License / Permissions'
    ],
    'models': [
        'Project & Usage Alignment',
        'Prohibited Use Screening (LC 2.7)',
        'Source / Provenance & D5+M Affiliation Screening (LC 2.5)',
        'License / Permissions',
        'Training Data Documentation',
        'Customisation / Fine-tuning',
        'FLOPS Calculation',
        'Sample Inspection'
    ]
}

# Header
st.title("🔍 AI Model Control Review (AIMCR)")
st.markdown("**KAUST Supercomputing Lab (KSL) - Project Proposal**")
st.divider()

# Sidebar navigation
with st.sidebar:
    st.header("Navigation")
    section = st.radio(
        "Select Section",
        ["Metadata", "Third-Party Software", "Source Code", "Datasets & User Files", "Models", "Final Review", "Addendum"],
        key="navigation"
    )
    st.session_state.current_section = section.lower().replace(" & ", "_").replace(" ", "_").replace("-", "_")
    
    st.divider()
    
    # Draft Management Section
    st.subheader("📂 Draft Management")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Draft", use_container_width=True):
            project_id = st.session_state.data['metadata'].get('project_id', '')
            try:
                draft_path = save_draft(LOCAL_REPO_PATH, st.session_state.data, project_id)
                
                # Push to GitHub
                commit_msg = f"Save draft: {project_id or 'unnamed'} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                success, message = push_to_github(LOCAL_REPO_PATH, commit_msg)
                
                if success:
                    st.success("✅ Draft saved and synced!")
                else:
                    st.warning(f"⚠️ Draft saved locally but not synced: {message}")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving draft: {str(e)}")
    
    with col2:
        if st.button("🔄 Sync", use_container_width=True):
            with st.spinner("Syncing..."):
                success, message = setup_local_workspace(LOCAL_REPO_PATH, GITHUB_REPO_URL)
                if success:
                    st.success("✅ Synced!")
                else:
                    st.error(f"❌ {message}")
                st.rerun()
    
    # Load Draft Section
    drafts = get_draft_files(LOCAL_REPO_PATH)
    if drafts:
        st.write(f"**Available Drafts ({len(drafts)})**")
        
        # Pagination for drafts
        DRAFTS_PER_PAGE = 6
        if 'drafts_page' not in st.session_state:
            st.session_state.drafts_page = 0
        
        total_draft_pages = (len(drafts) + DRAFTS_PER_PAGE - 1) // DRAFTS_PER_PAGE
        start_idx = st.session_state.drafts_page * DRAFTS_PER_PAGE
        end_idx = min(start_idx + DRAFTS_PER_PAGE, len(drafts))
        
        for draft in drafts[start_idx:end_idx]:
            with st.expander(f"📄 {draft['project_id']}", expanded=False):
                st.write(f"**Title:** {draft['proposal_title'][:30]}...")
                st.write(f"**Modified:** {draft['modified'].strftime('%Y-%m-%d %H:%M')}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Load", key=f"load_{draft['filename']}", use_container_width=True):
                        loaded_data = load_draft(draft['path'])
                        if loaded_data:
                            st.session_state.data = loaded_data
                            st.success("Draft loaded!")
                            st.rerun()
                        else:
                            st.error("Failed to load draft")
                
                with col2:
                    if st.button("Delete", key=f"del_{draft['filename']}", use_container_width=True):
                        success, msg = delete_draft(draft['path'])
                        if success:
                            # Push deletion to GitHub
                            commit_msg = f"Delete draft: {draft['filename']}"
                            push_to_github(LOCAL_REPO_PATH, commit_msg)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        
        # Pagination controls for drafts
        if total_draft_pages > 1:
            draft_nav_col1, draft_nav_col2, draft_nav_col3 = st.columns([1, 2, 1])
            with draft_nav_col1:
                if st.button("◀ Prev", key="drafts_prev", disabled=st.session_state.drafts_page == 0, use_container_width=True):
                    st.session_state.drafts_page -= 1
                    st.rerun()
            with draft_nav_col2:
                st.caption(f"Page {st.session_state.drafts_page + 1} of {total_draft_pages}")
            with draft_nav_col3:
                if st.button("Next ▶", key="drafts_next", disabled=st.session_state.drafts_page >= total_draft_pages - 1, use_container_width=True):
                    st.session_state.drafts_page += 1
                    st.rerun()
    else:
        st.info("No drafts available")
    
    st.divider()
    
    # Submission Management Section
    st.subheader("📋 Submitted Forms")
    
    submissions = get_submission_files(LOCAL_REPO_PATH)
    if submissions:
        st.write(f"**Available Submissions ({len(submissions)})**")
        
        # Pagination for submissions
        SUBMISSIONS_PER_PAGE = 6
        if 'submissions_page' not in st.session_state:
            st.session_state.submissions_page = 0
        
        total_submission_pages = (len(submissions) + SUBMISSIONS_PER_PAGE - 1) // SUBMISSIONS_PER_PAGE
        start_idx = st.session_state.submissions_page * SUBMISSIONS_PER_PAGE
        end_idx = min(start_idx + SUBMISSIONS_PER_PAGE, len(submissions))
        
        for submission in submissions[start_idx:end_idx]:
            with st.expander(f"📄 {submission['project_id']}", expanded=False):
                st.write(f"**Title:** {submission['proposal_title'][:30]}...")
                st.write(f"**Folder:** {submission['folder_name']}")
                st.write(f"**Modified:** {submission['modified'].strftime('%Y-%m-%d %H:%M')}")
                if submission['revision_count'] > 0:
                    st.write(f"**Revisions:** {submission['revision_count']}")
                
                if st.button("📝 Edit Submission", key=f"edit_sub_{submission['folder_name']}", use_container_width=True):
                    loaded_data = load_submission(submission['path'])
                    if loaded_data:
                        # Store the original folder name for resubmission
                        st.session_state.original_submission_folder = loaded_data.get('_original_submission_folder')
                        st.session_state.editing_submission = True
                        
                        # Remove internal tracking fields before loading into session
                        clean_data = {k: v for k, v in loaded_data.items() if not k.startswith('_')}
                        st.session_state.data = clean_data
                        
                        st.success(f"Submission loaded for editing!")
                        st.rerun()
                    else:
                        st.error("Failed to load submission")
        
        # Pagination controls for submissions
        if total_submission_pages > 1:
            sub_nav_col1, sub_nav_col2, sub_nav_col3 = st.columns([1, 2, 1])
            with sub_nav_col1:
                if st.button("◀ Prev", key="subs_prev", disabled=st.session_state.submissions_page == 0, use_container_width=True):
                    st.session_state.submissions_page -= 1
                    st.rerun()
            with sub_nav_col2:
                st.caption(f"Page {st.session_state.submissions_page + 1} of {total_submission_pages}")
            with sub_nav_col3:
                if st.button("Next ▶", key="subs_next", disabled=st.session_state.submissions_page >= total_submission_pages - 1, use_container_width=True):
                    st.session_state.submissions_page += 1
                    st.rerun()
    else:
        st.info("No submissions available")
    
    # Show editing status
    if st.session_state.editing_submission:
        st.divider()
        st.warning(f"✏️ Editing: {st.session_state.original_submission_folder}")
        if st.button("🆕 Start New Form", use_container_width=True):
            # Reset to a new form
            st.session_state.data = {
                'metadata': {
                    'proposal_title': '',
                    'principal_investigator': '',
                    'proposal_date': '',
                    'reviewer_name': '',
                    'reviewer_id': '',
                    'aimcr_date': '',
                    'project_id': ''
                },
                'third_party_software': [],
                'source_code': [],
                'datasets_user_files': [],
                'models': [],
                'observations': '',
                'recommendation': '',
                'addenda': []
            }
            st.session_state.editing_submission = False
            st.session_state.original_submission_folder = None
            st.rerun()
    
    st.divider()
    st.subheader("Risk Score Legend")
    for score, level in RISK_LEVELS.items():
        st.write(f"**{score}**: {level}")

# Metadata Section
if st.session_state.current_section == 'metadata':
    st.header("📋 Project Metadata")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.data['metadata']['proposal_title'] = st.text_input(
            "Proposal Title",
            value=st.session_state.data['metadata']['proposal_title']
        )
        
        st.session_state.data['metadata']['principal_investigator'] = st.text_input(
            "Principal Investigator",
            value=st.session_state.data['metadata']['principal_investigator']
        )
        
        st.session_state.data['metadata']['proposal_date'] = st.date_input(
            "Proposal Date",
            value=datetime.strptime(st.session_state.data['metadata']['proposal_date'], "%Y-%m-%d") if st.session_state.data['metadata']['proposal_date'] else datetime.now()
        ).strftime("%Y-%m-%d")
    
    with col2:
        st.session_state.data['metadata']['project_id'] = st.text_input(
            "Project ID",
            value=st.session_state.data['metadata']['project_id']
        )
        
        st.session_state.data['metadata']['reviewer_name'] = st.text_input(
            "Reviewer Name",
            value=st.session_state.data['metadata']['reviewer_name']
        )
        
        st.session_state.data['metadata']['reviewer_id'] = st.text_input(
            "Reviewer ID",
            value=st.session_state.data['metadata']['reviewer_id']
        )
        
        st.session_state.data['metadata']['aimcr_date'] = st.date_input(
            "AIMCR Date",
            value=datetime.strptime(st.session_state.data['metadata']['aimcr_date'], "%Y-%m-%d") if st.session_state.data['metadata']['aimcr_date'] else datetime.now()
        ).strftime("%Y-%m-%d")

# Function to render artifact form
def _render_addendum_artifacts_readonly(addendum_artifacts):
    """Render addendum artifacts inline, color-coded and read-only."""
    if not addendum_artifacts:
        return
    st.markdown("#### 📎 Addendum Artifacts")
    for entry in addendum_artifacts:
        add_n = entry['addendum_idx'] + 1
        date  = entry['date']
        artifact = entry['artifact']
        name = artifact.get('name', 'Unnamed')
        st.markdown(
            f"<div style='border-left:5px solid #3b82f6; background-color:#eff6ff; "
            f"padding:8px 14px; margin:6px 0; border-radius:4px;'>"
            f"<b>📎 Addendum {add_n} &mdash; Added: {date}</b> &nbsp;|&nbsp; {name}"
            f"</div>",
            unsafe_allow_html=True
        )
        with st.expander(f"View details — {name} (Addendum {add_n})", expanded=False):
            if section_key == 'models' and artifact.get('is_proprietary', False):
                st.write("**Marked as Proprietary:** Yes ✓")
            total = sum(c['score'] for c in artifact.get('checks', []))
            has_crit = any(c['score'] == 5 for c in artifact.get('checks', []))
            if has_crit or total >= 21:
                st.markdown(
                    f"**Total Score:** <span style='color:red;font-weight:bold;'>{total}</span>",
                    unsafe_allow_html=True
                )
            else:
                st.write(f"**Total Score:** {total}")
            for check in artifact.get('checks', []):
                st.write(f"- {check['name']}: Score **{check['score']}** | {check['notes']}")


def render_artifact_form(section_key, section_title, checks, artifacts_ref=None,
                         key_prefix='', show_header=True, addendum_artifacts=None):
    """
    Renders the artifact add/edit/list UI for a given section.

    artifacts_ref      – if provided, reads/writes to this list instead of
                         st.session_state.data[section_key] (used by addenda).
    key_prefix         – string prepended to all widget keys to avoid collisions
                         when the same section_key appears in both main form and addenda.
    show_header        – whether to render the section header (False when embedded in addendum).
    addendum_artifacts – list of {addendum_idx, date, artifact} dicts to show read-only
                         after the main artifact list (only used by top-level section calls).
    """
    if show_header:
        st.header(f"📦 {section_title}")
    
    # Resolve the artifact list we are operating on
    if artifacts_ref is None:
        artifacts = st.session_state.data[section_key]
        def _get_artifacts():
            return st.session_state.data[section_key]
        def _set_artifacts(lst):
            st.session_state.data[section_key] = lst
    else:
        artifacts = artifacts_ref
        def _get_artifacts():
            return artifacts_ref
        def _set_artifacts(lst):
            artifacts_ref.clear()
            artifacts_ref.extend(lst)
    
    # Edit-index namespace (scoped by key_prefix so addenda don't clash with main form)
    edit_ns = f"{key_prefix}{section_key}"
    
    # Display existing artifacts
    artifacts = _get_artifacts()
    
    if artifacts:
        st.subheader("Existing Artifacts")
        
        for idx, artifact in enumerate(artifacts):
            artifact_container = st.container()
            
            with artifact_container:
                col1, col2, col3 = st.columns([6, 1, 1])
                
                with col1:
                    artifact_name = artifact.get('name', 'Unnamed')
                    if section_key == 'models' and artifact.get('is_proprietary', False):
                        st.markdown(f"### Artifact {idx + 1}: {artifact_name} 🔒 *Proprietary*")
                    else:
                        st.markdown(f"### Artifact {idx + 1}: {artifact_name}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_{edit_ns}_{idx}", use_container_width=True):
                        st.session_state.edit_index[edit_ns] = idx
                        st.rerun()
                
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_{edit_ns}_{idx}", use_container_width=True):
                        _get_artifacts().pop(idx)
                        st.rerun()
                
                with st.expander("View Details", expanded=False):
                    if section_key == 'models':
                        proprietary_status = "Yes ✓" if artifact.get('is_proprietary', False) else "No"
                        st.write(f"**Marked as Proprietary in Proposal:** {proprietary_status}")
                        st.write("")
                    
                    artifact_score = sum(check['score'] for check in artifact['checks'])
                    has_critical = any(check['score'] == 5 for check in artifact['checks'])
                    
                    if has_critical or artifact_score >= 21:
                        st.markdown(f"**Total Score:** <span style='color:red; font-weight:bold;'>{artifact_score}</span>", unsafe_allow_html=True)
                    else:
                        st.write(f"**Total Score:** {artifact_score}")
                    
                    for check in artifact['checks']:
                        st.write(f"- {check['name']}: Score {check['score']} | Notes: {check['notes']}")
                
                st.divider()
        
        total_risk, max_scores = calculate_section_risk(artifacts)
        has_critical = any(score == 5 for score in max_scores)
        
        st.divider()
        st.subheader("Section Maximum Risk Score")
        
        if has_critical or total_risk >= 21:
            st.markdown(f"### <span style='color:red; font-weight:bold;'>Total: {total_risk}</span>", unsafe_allow_html=True)
            st.error("⚠️ CRITICAL: This section has critical risk (score ≥21 or individual check = 5)")
        else:
            st.markdown(f"### Total: {total_risk}")
        
        st.write("**Maximum scores per check:**")
        for i, (check_name, max_score) in enumerate(zip(checks, max_scores)):
            if max_score == 5:
                st.markdown(f"- {check_name}: <span style='color:red; font-weight:bold;'>{max_score}</span>", unsafe_allow_html=True)
            else:
                st.write(f"- {check_name}: {max_score}")
    
    # Show addendum artifacts for this section (read-only, color-coded)
    if addendum_artifacts and artifacts_ref is None:
        _render_addendum_artifacts_readonly(addendum_artifacts)

    st.divider()

    # Add/Edit artifact form
    edit_mode = edit_ns in st.session_state.edit_index
    if edit_mode:
        artifact_edit_idx = st.session_state.edit_index[edit_ns]
        st.info(f"✏️ **Editing Artifact {artifact_edit_idx + 1}** - Make your changes below and click 'Save Artifact' when done.")
        artifact = _get_artifacts()[artifact_edit_idx]
        form_key = f"{edit_ns}_form_edit_{artifact_edit_idx}"
    else:
        st.subheader("Add New Artifact")
        artifact = None
        form_key = f"{edit_ns}_form_add"
    
    with st.form(form_key):
        artifact_name = st.text_input(
            "Artifact Name",
            value=artifact['name'] if artifact else ""
        )
        
        st.write("### Risk Assessment Checks")
        
        checks_data = []
        for i, check_name in enumerate(checks):
            col1, col2 = st.columns([1, 2])
            
            widget_suffix = f"edit_{st.session_state.edit_index[edit_ns]}" if edit_mode else "add"
            
            help_text = SECTION_CHECK_HELP.get(section_key, {}).get(check_name, "No description available for this check.")
            
            with col1:
                score = st.selectbox(
                    f"{check_name}",
                    options=[1, 2, 3, 4, 5],
                    format_func=lambda x: f"{x} - {RISK_LEVELS[x]}",
                    index=artifact['checks'][i]['score'] - 1 if artifact else 0,
                    key=f"{edit_ns}_check_{i}_{widget_suffix}",
                    help=help_text
                )
            
            with col2:
                notes = st.text_area(
                    f"Notes for {check_name}",
                    value=artifact['checks'][i]['notes'] if artifact else "",
                    key=f"{edit_ns}_notes_{i}_{widget_suffix}",
                    height=100
                )
            
            checks_data.append({
                'name': check_name,
                'score': score,
                'notes': notes
            })
        
        is_proprietary = False
        if section_key == 'models':
            st.write("---")
            st.write("### Additional Information (Not part of risk scoring)")
            widget_suffix = f"edit_{st.session_state.edit_index[edit_ns]}" if edit_mode else "add"
            is_proprietary = st.checkbox(
                "Has the model been marked proprietary in the proposal?",
                value=artifact.get('is_proprietary', False) if artifact else False,
                key=f"{edit_ns}_proprietary_{widget_suffix}"
            )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            submit = st.form_submit_button("Save Artifact", type="primary")
        
        with col2:
            if edit_mode:
                cancel = st.form_submit_button("Cancel Edit")
                if cancel:
                    del st.session_state.edit_index[edit_ns]
                    st.rerun()
        
        if submit:
            new_artifact = {
                'name': artifact_name,
                'checks': checks_data
            }
            
            if section_key == 'models':
                new_artifact['is_proprietary'] = is_proprietary
            
            if edit_mode:
                _get_artifacts()[st.session_state.edit_index[edit_ns]] = new_artifact
                del st.session_state.edit_index[edit_ns]
            else:
                _get_artifacts().append(new_artifact)
            
            st.success("Artifact saved successfully!")
            st.rerun()

def get_addendum_artifacts_for_section(section_key):
    """Return list of {addendum_idx, date, artifact} for all addenda matching section_key."""
    result = []
    for idx, add in enumerate(st.session_state.data.get('addenda', [])):
        if add.get('category') == section_key:
            for artifact in add.get('artifacts', []):
                result.append({'addendum_idx': idx, 'date': add['date'], 'artifact': artifact})
    return result


# Render sections
if st.session_state.current_section == 'third_party_software':
    render_artifact_form(
        'third_party_software',
        'Third-Party Software (Packages, Libraries, Containers & Binaries)',
        SECTION_CHECKS['third_party_software'],
        addendum_artifacts=get_addendum_artifacts_for_section('third_party_software')
    )

elif st.session_state.current_section == 'source_code':
    render_artifact_form(
        'source_code', 'Source Code', SECTION_CHECKS['source_code'],
        addendum_artifacts=get_addendum_artifacts_for_section('source_code')
    )

elif st.session_state.current_section == 'datasets_user_files':
    render_artifact_form(
        'datasets_user_files', 'Datasets & User Files', SECTION_CHECKS['datasets_user_files'],
        addendum_artifacts=get_addendum_artifacts_for_section('datasets_user_files')
    )

elif st.session_state.current_section == 'models':
    render_artifact_form(
        'models', 'Models', SECTION_CHECKS['models'],
        addendum_artifacts=get_addendum_artifacts_for_section('models')
    )

# ── Addendum Section ──────────────────────────────────────────────────────────
elif st.session_state.current_section == 'addendum':
    st.header("📎 Addendum")
    st.markdown("Append supplementary artifact reviews to an existing AIMCR submission. Each addendum carries its own date, category, artifact assessments, observations, and recommendation.")

    # Ensure addenda list exists in data (backwards-compat with older loaded drafts)
    if 'addenda' not in st.session_state.data:
        st.session_state.data['addenda'] = []

    ADDENDUM_CATEGORY_OPTIONS = {
        'Third-Party Software': 'third_party_software',
        'Source Code': 'source_code',
        'Datasets & User Files': 'datasets_user_files',
        'Models': 'models'
    }
    ADDENDUM_CATEGORY_LABELS = {v: k for k, v in ADDENDUM_CATEGORY_OPTIONS.items()}

    # ── Existing addenda ──────────────────────────────────────────────────────
    addenda = st.session_state.data['addenda']

    if addenda:
        st.subheader(f"Existing Addenda ({len(addenda)})")
        for add_idx, addendum in enumerate(addenda):
            cat_key   = addendum.get('category', 'third_party_software')
            cat_label = ADDENDUM_CATEGORY_LABELS.get(cat_key, cat_key)
            add_date  = addendum.get('date', '—')
            n_arts    = len(addendum.get('artifacts', []))

            with st.expander(f"📎 Addendum {add_idx + 1}  |  {add_date}  |  {cat_label}  |  {n_arts} artifact(s)", expanded=(st.session_state.active_addendum == add_idx)):

                # Header controls
                col_del, col_expand = st.columns([1, 5])
                with col_del:
                    if st.button("🗑️ Delete", key=f"del_addendum_{add_idx}", use_container_width=True):
                        st.session_state.data['addenda'].pop(add_idx)
                        if st.session_state.active_addendum == add_idx:
                            st.session_state.active_addendum = None
                        st.rerun()

                st.divider()

                # Observations & Recommendation (saved inline with each addendum)
                obs_col, rec_col = st.columns(2)
                with obs_col:
                    new_obs = st.text_area(
                        "General Observations",
                        value=addendum.get('observations', ''),
                        height=120,
                        key=f"addendum_obs_{add_idx}"
                    )
                    addendum['observations'] = new_obs
                with rec_col:
                    new_rec = st.text_area(
                        "Recommendations",
                        value=addendum.get('recommendation', ''),
                        height=120,
                        key=f"addendum_rec_{add_idx}"
                    )
                    addendum['recommendation'] = new_rec

                st.divider()

                # Artifact form for this addendum (reuses the same checks & rubric)
                checks = SECTION_CHECKS[cat_key]
                render_artifact_form(
                    section_key   = cat_key,
                    section_title = cat_label,
                    checks        = checks,
                    artifacts_ref = addendum['artifacts'],
                    key_prefix    = f"add{add_idx}_",
                    show_header   = False
                )

    else:
        st.info("No addenda yet. Use the form below to add the first one.")

    st.divider()

    # ── Add a new addendum ────────────────────────────────────────────────────
    st.subheader("➕ New Addendum")
    with st.form("new_addendum_form"):
        col_date, col_cat = st.columns(2)
        with col_date:
            new_add_date = st.date_input("Addendum Date", value=datetime.now()).strftime("%Y-%m-%d")
        with col_cat:
            new_add_cat_label = st.selectbox("Artifact Category", list(ADDENDUM_CATEGORY_OPTIONS.keys()))

        if st.form_submit_button("Create Addendum", type="primary"):
            new_addendum = {
                'date': new_add_date,
                'category': ADDENDUM_CATEGORY_OPTIONS[new_add_cat_label],
                'artifacts': [],
                'observations': '',
                'recommendation': ''
            }
            st.session_state.data['addenda'].append(new_addendum)
            # Expand the newly created addendum automatically
            add_n = len(st.session_state.data['addenda'])
            st.session_state.active_addendum = add_n - 1
            # Insert date demarcation into observations and recommendation
            marker = f"\n\n--- Addendum {add_n} added: {new_add_date} ({new_add_cat_label}) ---\n"
            st.session_state.data['observations'] = (
                st.session_state.data.get('observations', '') + marker)
            st.session_state.data['recommendation'] = (
                st.session_state.data.get('recommendation', '') + marker)
            st.success(f"Addendum {add_n} created — scroll up to fill in artifacts.")
            st.rerun()

# Final Review Section
elif st.session_state.current_section == 'final_review':
    st.header("📊 Final Review and Summary")
    
    # Display metadata
    st.subheader("Project Information")
    meta = st.session_state.data['metadata']
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Proposal Title:** {meta['proposal_title']}")
        st.write(f"**Principal Investigator:** {meta['principal_investigator']}")
        st.write(f"**Proposal Date:** {meta['proposal_date']}")
    with col2:
        st.write(f"**Project ID:** {meta['project_id']}")
        st.write(f"**Reviewer Name:** {meta['reviewer_name']}")
        st.write(f"**Reviewer ID:** {meta['reviewer_id']}")
        st.write(f"**AIMCR Date:** {meta['aimcr_date']}")
    
    st.divider()
    
    # Backwards-compat: addenda may be absent in older drafts/submissions
    if 'addenda' not in st.session_state.data:
        st.session_state.data['addenda'] = []

    # Display all section scores
    st.subheader("Risk Score Summary")

    sections_summary = {
        'Third-Party Software': ('third_party_software', SECTION_CHECKS['third_party_software']),
        'Source Code': ('source_code', SECTION_CHECKS['source_code']),
        'Datasets & User Files': ('datasets_user_files', SECTION_CHECKS['datasets_user_files']),
        'Models': ('models', SECTION_CHECKS['models'])
    }

    has_addenda = bool(st.session_state.data.get('addenda'))

    overall_critical = False
    section_scores_list = []        # original scores
    section_scores_updated = []     # merged (original + addenda) scores

    for section_name, (section_key, checks) in sections_summary.items():
        orig_artifacts = st.session_state.data[section_key]

        # ── Original scores ──────────────────────────────────────────────────
        if orig_artifacts:
            total_risk, max_scores = calculate_section_risk(orig_artifacts)
            highest_score = max(max_scores) if max_scores else 1
            risk_category = RISK_LEVELS.get(highest_score, "Unknown")
            risk_color = get_risk_color(highest_score)
            if highest_score == 5:
                overall_critical = True
            pass_fail = "FAIL" if total_risk >= 21 else "PASS"
            section_scores_list.append({
                'name': section_name, 'key': section_key,
                'total_score': total_risk, 'highest_score': highest_score,
                'risk_category': risk_category, 'risk_color': risk_color,
                'n_artifacts': len(orig_artifacts), 'max_scores': max_scores,
                'checks': checks, 'pass_fail': pass_fail
            })
        else:
            section_scores_list.append({
                'name': section_name, 'key': section_key,
                'total_score': 0, 'highest_score': 0,
                'risk_category': 'No Data', 'risk_color': 'gray',
                'n_artifacts': 0, 'max_scores': [], 'checks': checks, 'pass_fail': 'N/A'
            })

        # ── Updated scores (original + addenda merged) ────────────────────────
        if has_addenda:
            upd_total, upd_max = compute_merged_section_risk(st.session_state.data, section_key)
            upd_highest = max(upd_max) if upd_max else 0
            upd_category = RISK_LEVELS.get(upd_highest, "No Data")
            upd_color = get_risk_color(upd_highest) if upd_highest else "gray"
            upd_pass_fail = "FAIL" if upd_total >= 21 else ("PASS" if upd_total > 0 else "N/A")
            if upd_highest == 5:
                overall_critical = True
            section_scores_updated.append({
                'name': section_name, 'key': section_key,
                'total_score': upd_total, 'highest_score': upd_highest,
                'risk_category': upd_category, 'risk_color': upd_color,
                'pass_fail': upd_pass_fail
            })

    # ── Section-by-section display ───────────────────────────────────────────
    for i, s in enumerate(section_scores_list):
        if s['n_artifacts'] > 0 or (has_addenda and section_scores_updated[i]['total_score'] > 0):
            rc = s['risk_color']
            pf_color = "red" if s['pass_fail'] == "FAIL" else "green"

            if has_addenda:
                upd = section_scores_updated[i]
                upd_pf_color = "red" if upd['pass_fail'] == "FAIL" else ("green" if upd['pass_fail'] == "PASS" else "gray")
                orig_part = (
                    f"<span style='font-size:14px;'>Original — Score: <strong>{s['total_score']}</strong> &nbsp;"
                    f"<strong style='color:{rc};'>{s['risk_category']}</strong> &nbsp;"
                    f"<strong style='color:{pf_color};'>{s['pass_fail']}</strong></span>"
                ) if s['n_artifacts'] > 0 else "<span style='font-size:14px; color:gray;'>Original — No artifacts</span>"
                upd_part = (
                    f"<span style='font-size:14px; color:#3b82f6;'>📎 After Addenda — Score: <strong>{upd['total_score']}</strong> &nbsp;"
                    f"<strong style='color:{upd['risk_color']};'>{upd['risk_category']}</strong> &nbsp;"
                    f"<strong style='color:{upd_pf_color};'>{upd['pass_fail']}</strong></span>"
                )
                border_color = upd['risk_color'] if upd['total_score'] > 0 else rc
                st.markdown(f"""
                <div style='padding:12px 15px; border-left:5px solid {border_color}; margin:10px 0; background-color:rgba(128,128,128,0.05);'>
                    <div style='font-size:18px; font-weight:bold; margin-bottom:6px;'>{s['name']}</div>
                    <div>{orig_part}</div>
                    <div style='margin-top:4px;'>{upd_part}</div>
                </div>""", unsafe_allow_html=True)
            else:
                pf_color = "red" if s['pass_fail'] == "FAIL" else "green"
                st.markdown(f"""
                <div style='padding:15px; border-left:5px solid {rc}; margin:10px 0; background-color:rgba(128,128,128,0.05);'>
                    <div style='font-size:18px; font-weight:bold;'>{s['name']}</div>
                    <div style='margin-top:8px;'>
                        <span style='font-size:16px;'>Total Score: <strong>{s['total_score']}</strong></span>
                        <span style='margin-left:20px; font-size:16px;'>Risk Category: <strong style='color:{rc};'>{s['risk_category']}</strong></span>
                        <span style='margin-left:20px; font-size:16px;'>Status: <strong style='color:{pf_color};'>{s['pass_fail']}</strong></span>
                    </div>
                </div>""", unsafe_allow_html=True)

            with st.expander(f"View {s['name']} Details"):
                st.write(f"**Original artifacts:** {s['n_artifacts']}")
                if s['max_scores']:
                    st.write(f"**Highest original score:** {s['highest_score']} ({s['risk_category']})")
                    st.write("**Original max scores per check:**")
                    for check_name, max_score in zip(s['checks'], s['max_scores']):
                        check_color = get_risk_color(max_score)
                        check_risk = RISK_LEVELS.get(max_score, "Unknown")
                        st.markdown(f"- {check_name}: <span style='color:{check_color}; font-weight:bold;'>{max_score}</span> ({check_risk})", unsafe_allow_html=True)
                if has_addenda:
                    upd = section_scores_updated[i]
                    add_arts = get_addendum_artifacts_for_section(s['key'])
                    st.write(f"**Addendum artifacts in this section:** {len(add_arts)}")
                    if upd['total_score'] > 0:
                        st.write(f"**Updated highest score:** {upd['highest_score']} ({upd['risk_category']})")
        else:
            st.markdown(f"""
            <div style='padding:15px; border-left:5px solid gray; margin:10px 0; background-color:rgba(128,128,128,0.05);'>
                <div style='font-size:18px; font-weight:bold;'>{s['name']}</div>
                <div style='margin-top:8px; color:gray;'>No artifacts added</div>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # Overall status
    if overall_critical:
        st.error("⚠️ CRITICAL RISK DETECTED: One or more sections have critical risk scores!")
    else:
        st.success("✅ All sections are within acceptable risk levels")

    st.divider()

    # ── Cumulative risk (original) ────────────────────────────────────────────
    orig_scores_with_data = [s for s in section_scores_list if s['highest_score'] > 0]
    cumulative_risk_score = max(s['highest_score'] for s in orig_scores_with_data) if orig_scores_with_data else 1
    cumulative_risk_category = RISK_LEVELS.get(cumulative_risk_score, "No Risk")
    cumulative_risk_color = get_risk_color(cumulative_risk_score)
    any_section_failed = any(s['pass_fail'] == 'FAIL' for s in section_scores_list)
    cumulative_pass_fail = "FAIL" if any_section_failed else "PASS"
    cumulative_pass_fail_color = "red" if any_section_failed else "green"

    # ── Cumulative risk (updated with addenda) ────────────────────────────────
    if has_addenda:
        upd_scores_with_data = [s for s in section_scores_updated if s['highest_score'] > 0]
        upd_cumulative_score = max(s['highest_score'] for s in upd_scores_with_data) if upd_scores_with_data else cumulative_risk_score
        upd_cumulative_category = RISK_LEVELS.get(upd_cumulative_score, "No Risk")
        upd_cumulative_color = get_risk_color(upd_cumulative_score)
        any_upd_failed = any(s['pass_fail'] == 'FAIL' for s in section_scores_updated)
        upd_cumulative_pass_fail = "FAIL" if any_upd_failed else "PASS"
        upd_pass_fail_color = "red" if any_upd_failed else "green"

        col_orig, col_updated = st.columns(2)
        with col_orig:
            st.markdown(f"""
            <div style='padding:20px; border:4px solid {cumulative_risk_color}; border-radius:10px;
                        text-align:center; background-color:rgba(128,128,128,0.05);'>
                <div style='font-size:14px; font-weight:bold; margin-bottom:10px;'>ORIGINAL MAXIMUM RISK</div>
                <div style='font-size:42px; font-weight:bold; color:{cumulative_risk_color};'>{cumulative_risk_score}</div>
                <div style='font-size:18px; font-weight:bold; color:{cumulative_risk_color};'>{cumulative_risk_category}</div>
                <div style='font-size:16px; font-weight:bold; color:{cumulative_pass_fail_color}; margin-top:10px;'>{cumulative_pass_fail}</div>
                <div style='font-size:11px; margin-top:8px; color:gray;'>Based on original submission artifacts</div>
            </div>""", unsafe_allow_html=True)
        with col_updated:
            st.markdown(f"""
            <div style='padding:20px; border:4px solid {upd_cumulative_color}; border-radius:10px;
                        text-align:center; background-color:#eff6ff;'>
                <div style='font-size:14px; font-weight:bold; margin-bottom:10px; color:#1d4ed8;'>📎 UPDATED MAXIMUM RISK</div>
                <div style='font-size:42px; font-weight:bold; color:{upd_cumulative_color};'>{upd_cumulative_score}</div>
                <div style='font-size:18px; font-weight:bold; color:{upd_cumulative_color};'>{upd_cumulative_category}</div>
                <div style='font-size:16px; font-weight:bold; color:{upd_pass_fail_color}; margin-top:10px;'>{upd_cumulative_pass_fail}</div>
                <div style='font-size:11px; margin-top:8px; color:gray;'>Includes all addenda</div>
            </div>""", unsafe_allow_html=True)
    else:
        # No addenda — single cumulative risk box centred
        col_l, col_mid, col_r = st.columns([1, 2, 1])
        with col_mid:
            st.markdown(f"""
            <div style='padding:20px; border:4px solid {cumulative_risk_color}; border-radius:10px;
                        text-align:center; background-color:rgba(128,128,128,0.05);'>
                <div style='font-size:16px; font-weight:bold; margin-bottom:15px;'>MAXIMUM RISK LEVEL</div>
                <div style='font-size:48px; font-weight:bold; color:{cumulative_risk_color};'>{cumulative_risk_score}</div>
                <div style='font-size:20px; font-weight:bold; color:{cumulative_risk_color};'>{cumulative_risk_category}</div>
                <div style='font-size:18px; font-weight:bold; color:{cumulative_pass_fail_color}; margin-top:15px;'>{cumulative_pass_fail}</div>
                <div style='font-size:12px; margin-top:10px; color:gray;'>Highest risk across all sections</div>
            </div>""", unsafe_allow_html=True)

    # Observations and Recommendations
    st.subheader("Observations and Recommendations")

    st.session_state.data['observations'] = st.text_area(
        "Observations",
        value=st.session_state.data['observations'],
        height=150
    )

    st.session_state.data['recommendation'] = st.text_area(
        "Recommendation",
        value=st.session_state.data['recommendation'],
        height=150
    )
    
    st.divider()
    
    # ── Addenda Summary ───────────────────────────────────────────────────────
    addenda = st.session_state.data.get('addenda', [])
    if addenda:
        st.subheader(f"📎 Addenda ({len(addenda)})")
        ADDENDUM_CATEGORY_LABELS_FR = {
            'third_party_software': 'Third-Party Software',
            'source_code': 'Source Code',
            'datasets_user_files': 'Datasets & User Files',
            'models': 'Models'
        }
        for add_idx, addendum in enumerate(addenda):
            cat_key   = addendum.get('category', '')
            cat_label = ADDENDUM_CATEGORY_LABELS_FR.get(cat_key, cat_key)
            add_date  = addendum.get('date', '—')
            artifacts = addendum.get('artifacts', [])

            with st.expander(f"📎 Addendum {add_idx + 1}  |  {add_date}  |  {cat_label}  |  {len(artifacts)} artifact(s)"):
                if artifacts:
                    total_risk, max_scores = calculate_section_risk(artifacts)
                    has_crit = any(s == 5 for s in max_scores)
                    risk_color = get_risk_color(max(max_scores) if max_scores else 1)
                    risk_label = RISK_LEVELS.get(max(max_scores) if max_scores else 1, 'No Risk')
                    st.markdown(
                        f"**Risk Score:** <span style='color:{risk_color}; font-weight:bold;'>{total_risk} — {risk_label}</span>",
                        unsafe_allow_html=True
                    )
                    if has_crit:
                        st.error("⚠️ CRITICAL risk in this addendum")
                    for art in artifacts:
                        art_score = sum(c['score'] for c in art['checks'])
                        st.write(f"- **{art['name']}**: total score {art_score}")
                else:
                    st.write("_No artifacts recorded._")

                obs = addendum.get('observations', '')
                rec = addendum.get('recommendation', '')
                if obs:
                    st.write(f"**Observations:** {obs}")
                if rec:
                    st.write(f"**Recommendations:** {rec}")
    else:
        st.info("No addenda attached to this review.")

    st.divider()
    
    # Save and Export
    st.subheader("💾 Save and Export")
    
    # Show editing status banner if editing
    if st.session_state.editing_submission:
        st.info(f"✏️ **Editing existing submission:** {st.session_state.original_submission_folder}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Draft", type="secondary", use_container_width=True):
            project_id = meta['project_id']
            if not project_id:
                st.error("Please enter a Project ID in the Metadata section")
            else:
                try:
                    draft_path = save_draft(LOCAL_REPO_PATH, st.session_state.data, project_id)
                    
                    # Push to GitHub
                    commit_msg = f"Save draft: {project_id} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    success, message = push_to_github(LOCAL_REPO_PATH, commit_msg)
                    
                    if success:
                        st.success(f"✅ Draft saved and synced to GitHub!")
                    else:
                        st.warning(f"⚠️ Draft saved locally: {draft_path}")
                        st.info(f"Sync issue: {message}")
                except Exception as e:
                    st.error(f"Error saving draft: {str(e)}")
    
    with col2:
        # Change button text based on whether editing or new submission
        button_text = "📤 Resubmit" if st.session_state.editing_submission else "📤 Submit Final"
        
        if st.button(button_text, type="primary", use_container_width=True):
            if not meta['project_id']:
                st.error("Please enter a Project ID in the Metadata section")
            else:
                try:
                    # Create a checkpoint before submission
                    checkpoint_type = "pre_resubmission" if st.session_state.editing_submission else "pre_submission"
                    checkpoint_path = archive_draft_as_checkpoint(
                        LOCAL_REPO_PATH, 
                        st.session_state.data, 
                        meta['project_id'],
                        checkpoint_type
                    )
                    
                    # Determine if this is a resubmission or new submission
                    original_folder = st.session_state.original_submission_folder if st.session_state.editing_submission else None
                    
                    # Save to submissions folder (same folder if resubmitting)
                    submission_path = save_final_submission(
                        LOCAL_REPO_PATH, 
                        st.session_state.data, 
                        meta['project_id'],
                        original_folder_name=original_folder
                    )
                    
                    # Push to GitHub
                    action_type = "Resubmission" if st.session_state.editing_submission else "Final submission"
                    commit_msg = f"{action_type}: {meta['project_id']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    success, message = push_to_github(LOCAL_REPO_PATH, commit_msg)
                    
                    if success:
                        if st.session_state.editing_submission:
                            st.success(f"✅ Resubmission saved to original folder and pushed to GitHub!")
                        else:
                            st.success(f"✅ Final submission saved and pushed to GitHub!")
                        st.info(f"📁 Submission saved in: {submission_path}")
                        st.info(f"📋 Checkpoint saved: {checkpoint_path.name}")
                        
                        # Clean up draft if exists
                        drafts_dir = LOCAL_REPO_PATH / "drafts"
                        for draft_file in drafts_dir.glob(f"draft_{meta['project_id']}_*.json"):
                            draft_file.unlink()
                        
                        # Commit draft cleanup
                        push_to_github(LOCAL_REPO_PATH, f"Clean up drafts for {meta['project_id']}")
                        
                        # Reset editing state after successful submission
                        st.session_state.editing_submission = False
                        st.session_state.original_submission_folder = None
                        
                    else:
                        st.warning(f"⚠️ Submission saved locally but not synced: {message}")
                        st.info(f"📁 Files saved in: {submission_path}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    with col3:
        if st.button("📥 Save Local Copy", use_container_width=True):
            if not meta['project_id']:
                st.error("Please enter a Project ID in the Metadata section")
            else:
                try:
                    folder_path = create_folder_structure(meta['project_id'])
                    json_path = save_to_json(st.session_state.data, folder_path)
                    st.success(f"✅ Data saved to {json_path}")
                except Exception as e:
                    st.error(f"Error saving file: {str(e)}")
    
    # Download JSON
    if meta['project_id']:
        st.download_button(
            label="📥 Download JSON",
            data=json.dumps(st.session_state.data, indent=2),
            file_name=f"aimcr_{meta['project_id']}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    st.divider()
    
    # Workspace Information
    st.subheader("📊 Workspace Information")
    st.write(f"**Local Workspace:** `{LOCAL_REPO_PATH}`")
    st.write(f"**GitHub Repository:** `{GITHUB_REPO}`")
    
    # Show recent activity
    drafts = get_draft_files(LOCAL_REPO_PATH)
    st.write(f"**Drafts:** {len(drafts)}")
    
    submissions_dir = LOCAL_REPO_PATH / "submissions"
    if submissions_dir.exists():
        submissions = list(submissions_dir.glob("AIMCR-*"))
        st.write(f"**Submissions:** {len(submissions)}")
    else:
        st.write(f"**Submissions:** 0")
    
    # Show checkpoints if project ID exists
    if meta['project_id']:
        st.divider()
        st.subheader("📋 Checkpoints")
        checkpoints = get_checkpoints(LOCAL_REPO_PATH, meta['project_id'])
        
        if checkpoints:
            st.write(f"**Available checkpoints for {meta['project_id']}:** {len(checkpoints)}")
            
            for checkpoint in checkpoints[:5]:  # Show last 5 checkpoints
                with st.expander(f"📋 {checkpoint['type']} - {checkpoint['modified'].strftime('%Y-%m-%d %H:%M')}", expanded=False):
                    st.write(f"**Type:** {checkpoint['type']}")
                    st.write(f"**Timestamp:** {checkpoint['timestamp']}")
                    
                    if st.button("🔄 Restore this checkpoint", key=f"restore_{checkpoint['filename']}", use_container_width=True):
                        restored_data = load_checkpoint(checkpoint['path'])
                        if restored_data:
                            st.session_state.data = restored_data
                            st.success("Checkpoint restored! Review your data and save/submit when ready.")
                            st.rerun()
                        else:
                            st.error("Failed to restore checkpoint")
        else:
            st.info("No checkpoints available for this project")

# Footer
st.divider()
st.caption("AI Model Control Review (AIMCR) - KAUST Supercomputing Lab")
