#!/usr/bin/env python3
"""
KSL AI Model Control Review → PDF Generator (v2)
- Addendum artifacts appear inline within their original section, blue-bordered with date badge
- Risk Score Summary shows Original vs Updated (incl. addenda) side-by-side when addenda exist
- Maximum Risk Score label (not cumulative)
- Dedicated addendum pages at the end retain per-addendum observations/recommendations
"""

import json
import sys
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)

MAX_NOTES_IN_TABLE = 800


def load_json(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='DocTitle',
        parent=styles['Title'],
        fontSize=22,
        spaceAfter=30,
        textColor=HexColor('#1a365d'),
        alignment=1,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading1'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=12,
        textColor=HexColor('#2c5282'),
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='ItemHeader',
        parent=styles['Heading2'],
        fontSize=13,
        spaceBefore=18,
        spaceAfter=8,
        textColor=HexColor('#3182ce'),
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='AddendumItemHeader',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
        textColor=HexColor('#1d4ed8'),
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name='AddendumBadge',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        textColor=HexColor('#1d4ed8'),
        spaceBefore=4,
        spaceAfter=4,
        leftIndent=4,
    ))
    styles.add(ParagraphStyle(
        name='TableText',
        parent=styles['Normal'],
        fontSize=10,
        leading=12
    ))
    styles.add(ParagraphStyle(
        name='NotesExpanded',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        leftIndent=20,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=8,
        backColor=HexColor('#f8fafc'),
        borderPadding=5
    ))
    styles.add(ParagraphStyle(
        name='NotesLabel',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-BoldOblique',
        textColor=HexColor('#4a5568'),
        leftIndent=10,
        spaceBefore=6,
        spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name='TotalRisk',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        textColor=HexColor('#b91c1c'),
        spaceBefore=10,
        spaceAfter=15,
        leftIndent=5
    ))
    styles.add(ParagraphStyle(
        name='AddendumTitle',
        parent=styles['Normal'],
        fontSize=18,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        name='AddendumMeta',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.white,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        name='AddendumObsHeader',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=18,
        spaceAfter=6,
        textColor=HexColor('#744210'),
        keepWithNext=True,
    ))

    return styles


def format_text_with_breaks(text: str) -> str:
    if not text:
        return ""
    return text.strip().replace('\n', '<br/>')


def calculate_total_risk(checks) -> int:
    total = 0
    if isinstance(checks, dict):
        for check_data in checks.values():
            score = check_data.get("score")
            if isinstance(score, (int, float)):
                total += int(score)
    elif isinstance(checks, list):
        for check in checks:
            score = check.get("score")
            if isinstance(score, (int, float)):
                total += int(score)
    return total


def get_highest_score_in_items(items: list) -> int:
    max_score = 0
    for item in items:
        checks = item.get("checks", [])
        if isinstance(checks, dict):
            for check_data in checks.values():
                score = check_data.get("score")
                if isinstance(score, (int, float)):
                    max_score = max(max_score, int(score))
        elif isinstance(checks, list):
            for check in checks:
                score = check.get("score")
                if isinstance(score, (int, float)):
                    max_score = max(max_score, int(score))
    return max_score


def get_risk_category(score: int) -> str:
    return {1: "No Risk", 2: "Low Risk", 3: "Medium Risk",
            4: "High Risk", 5: "Critical Risk"}.get(score, "Unknown")


def get_risk_color(score: int) -> HexColor:
    return {
        1: HexColor('#10b981'),
        2: HexColor('#fbbf24'),
        3: HexColor('#f97316'),
        4: HexColor('#ef4444'),
        5: HexColor('#dc2626'),
    }.get(score, HexColor('#6b7280'))


def calculate_section_total_score(items: list) -> int:
    """Max-per-check-position then sum — matches the app rubric."""
    if not items:
        return 0
    check_max = {}
    for item in items:
        checks = item.get("checks", [])
        if isinstance(checks, dict):
            for name, cd in checks.items():
                s = cd.get("score")
                if isinstance(s, (int, float)):
                    check_max[name] = max(check_max.get(name, 0), int(s))
        elif isinstance(checks, list):
            for c in checks:
                name = c.get("name", "")
                s = c.get("score")
                if isinstance(s, (int, float)):
                    check_max[name] = max(check_max.get(name, 0), int(s))
    return sum(check_max.values())


def _build_section_info_entry(display_name: str, items: list) -> dict:
    if not items:
        return {'total': 0, 'highest': 0, 'category': 'No Data',
                'count': 0, 'pass_fail': 'N/A', 'artifacts': []}
    total = calculate_section_total_score(items)
    highest = get_highest_score_in_items(items)
    high_arts = [
        item.get("name", "Unnamed").strip() or "Unnamed"
        for item in items
        if get_highest_score_in_items([item]) == highest
    ]
    return {
        'total': total,
        'highest': highest,
        'category': get_risk_category(highest),
        'count': len(items),
        'pass_fail': 'FAIL' if total >= 21 else 'PASS',
        'artifacts': high_arts,
    }


SECTION_KEYS = {
    'Third-Party Software': 'third_party_software',
    'Source Code':          'source_code',
    'Datasets / User Files': 'datasets_user_files',
    'AI Models':            'models',
}

ADDENDUM_CATEGORY_LABELS = {v: k for k, v in SECTION_KEYS.items()}


def calculate_section_totals(data: dict) -> dict:
    """Original artifacts only."""
    return {
        display: _build_section_info_entry(display, data.get(key, []))
        for display, key in SECTION_KEYS.items()
    }


def calculate_merged_section_totals(data: dict) -> dict:
    """Original + all addendum artifacts merged per section."""
    result = {}
    for display, key in SECTION_KEYS.items():
        merged = list(data.get(key, []))
        for add in data.get('addenda', []):
            if add.get('category') == key:
                merged.extend(add.get('artifacts', []))
        result[display] = _build_section_info_entry(display, merged)
    return result


def get_addendum_artifacts_for_section(data: dict, section_key: str) -> list:
    """Return list of (add_n, date, art_idx, artifact) 4-tuples for a section.
    art_idx is the 0-based position within that addendum's artifact list."""
    result = []
    for idx, add in enumerate(data.get('addenda', [])):
        if add.get('category') == section_key:
            for art_idx, artifact in enumerate(add.get('artifacts', [])):
                result.append((idx + 1, add.get('date', '—'), art_idx, artifact))
    return result


def _build_section_info_entry_anchored(items_with_anchors: list) -> dict:
    """Like _build_section_info_entry but accepts (anchor_id, item) pairs and
    returns artifact_links: [{'name': str, 'anchor': str}] instead of plain names."""
    if not items_with_anchors:
        return {'total': 0, 'highest': 0, 'category': 'No Data',
                'count': 0, 'pass_fail': 'N/A', 'artifact_links': []}
    items = [item for _, item in items_with_anchors]
    total   = calculate_section_total_score(items)
    highest = get_highest_score_in_items(items)
    links = []
    for anchor_id, item in items_with_anchors:
        if get_highest_score_in_items([item]) == highest:
            name = item.get("name", "Unnamed").strip() or "Unnamed"
            links.append({'name': name, 'anchor': anchor_id})
    return {
        'total': total,
        'highest': highest,
        'category': get_risk_category(highest),
        'count': len(items),
        'pass_fail': 'FAIL' if total >= 21 else 'PASS',
        'artifact_links': links,
    }


def calculate_section_totals_anchored(data: dict) -> dict:
    """Original artifacts only, with anchor IDs for the summary table."""
    result = {}
    for display, key in SECTION_KEYS.items():
        pairs = [(f"orig_{key}_{i}", item)
                 for i, item in enumerate(data.get(key, []))]
        result[display] = _build_section_info_entry_anchored(pairs)
    return result


def calculate_merged_section_totals_anchored(data: dict) -> dict:
    """Original + addendum artifacts merged per section, with anchor IDs."""
    result = {}
    for display, key in SECTION_KEYS.items():
        pairs = [(f"orig_{key}_{i}", item)
                 for i, item in enumerate(data.get(key, []))]
        for add_idx, add in enumerate(data.get('addenda', [])):
            if add.get('category') == key:
                add_n = add_idx + 1
                for art_idx, artifact in enumerate(add.get('artifacts', [])):
                    pairs.append((f"add_{add_n}_{key}_{art_idx}", artifact))
        result[display] = _build_section_info_entry_anchored(pairs)
    return result


def create_check_elements(checks, styles, header_color=None) -> list:
    elements = []
    table_data = [["Check", "Risk Score", "Notes"]]
    expanded_notes = []

    check_list = []
    if isinstance(checks, dict):
        for name, cd in checks.items():
            check_list.append({"name": name, "score": cd.get("score"), "notes": cd.get("notes", "")})
    elif isinstance(checks, list):
        check_list = checks

    for check in check_list:
        name = check.get("name", "—")
        score = check.get("score", "—")
        notes_raw = (check.get("notes") or "").strip()
        notes_html = format_text_with_breaks(notes_raw)
        score_display = f"<b>{score}</b>" if score != "—" else "—"

        if len(notes_raw) > MAX_NOTES_IN_TABLE:
            table_data.append([
                Paragraph(name, styles['TableText']),
                Paragraph(score_display, styles['TableText']),
                Paragraph("<i>See details below ↓</i>", styles['TableText'])
            ])
            expanded_notes.append((name, notes_html))
        else:
            table_data.append([
                Paragraph(name, styles['TableText']),
                Paragraph(score_display, styles['TableText']),
                Paragraph(notes_html or "—", styles['TableText'])
            ])

    hdr = header_color or HexColor('#2c5282')
    table = Table(table_data, colWidths=[2.3*inch, 0.8*inch, 3.9*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), hdr),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('ALIGN',        (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN',        (1, 1), (1, -1), 'CENTER'),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 10),
        ('GRID',         (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)

    if expanded_notes:
        elements.append(Spacer(1, 10))
        for check_name, notes_html in expanded_notes:
            elements.append(Paragraph(f"► {check_name}:", styles['NotesLabel']))
            elements.append(Paragraph(notes_html, styles['NotesExpanded']))

    return elements


def create_metadata_table(metadata: dict, styles) -> Table:
    fields = {
        'proposal_title':         'Proposal Title',
        'principal_investigator': 'Principal Investigator',
        'proposal_date':          'Proposal Date',
        'reviewer_name':          'Reviewer Name',
        'reviewer_id':            'Reviewer ID',
        'aimcr_date':             'AIMCR Date',
        'project_id':             'Project ID',
    }
    data = [
        [Paragraph(f"<b>{label}:</b>", styles['TableText']),
         Paragraph(str(metadata.get(key, 'N/A')), styles['TableText'])]
        for key, label in fields.items()
    ]
    table = Table(data, colWidths=[2.4*inch, 4.3*inch])
    table.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('GRID',         (0, 0), (-1, -1), 0.5, HexColor('#cbd5e0')),
        ('BACKGROUND',   (0, 0), (-1, -1), HexColor('#edf2f7')),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    return table


def add_component_section(story, title: str, items: list, styles,
                           is_models_section: bool = False,
                           addendum_artifacts: list = None,
                           section_key: str = ""):
    """
    Render a section.  Original artifacts first (white rows, with named anchors),
    then addendum artifacts (blue-bordered with date badge, also anchored).
    Anchor IDs: orig_{section_key}_{0-based idx}  /  add_{add_n}_{section_key}_{art_idx}
    """
    story.append(Paragraph(title, styles['SectionHeader']))

    if not items and not addendum_artifacts:
        story.append(Paragraph("No items in this category.", styles['TableText']))
        story.append(Spacer(1, 20))
        return

    # ── Original artifacts ────────────────────────────────────────────────────
    for idx, item in enumerate(items):
        name    = item.get("name", "").strip() or "(Unnamed component)"
        anchor  = f'<a name="orig_{section_key}_{idx}"/>'
        display = idx + 1
        if is_models_section and item.get('is_proprietary', False):
            story.append(Paragraph(
                f'{anchor}{display}. {name} \U0001F512 <i>(Marked as Proprietary)</i>',
                styles['ItemHeader']
            ))
        else:
            story.append(Paragraph(f'{anchor}{display}. {name}', styles['ItemHeader']))

        if is_models_section:
            prop = "Yes" if item.get('is_proprietary', False) else "No"
            story.append(Paragraph(f"<b>Marked as Proprietary in Proposal:</b> {prop}", styles['TableText']))
            story.append(Spacer(1, 8))

        checks = item.get("checks", [])
        if checks:
            story.extend(create_check_elements(checks, styles))
            story.append(Paragraph(f"Total Risk Score: {calculate_total_risk(checks)}", styles['TotalRisk']))
        else:
            story.append(Paragraph("No checks recorded.", styles['TableText']))
        story.append(Spacer(1, 25))

    # ── Addendum artifacts (inline, blue-bordered) ────────────────────────────
    if addendum_artifacts:
        story.append(Paragraph("📎 Addendum Artifacts", styles['SectionHeader']))

        for add_n, add_date, art_idx, item in addendum_artifacts:
            name   = item.get("name", "").strip() or "(Unnamed component)"
            anchor = f'<a name="add_{add_n}_{section_key}_{art_idx}"/>'

            badge_data = [[
                Paragraph(
                    f"{anchor}<b>Addendum {add_n} — Added: {add_date}</b> &nbsp;&nbsp; {name}",
                    styles['AddendumBadge']
                )
            ]]
            badge_table = Table(badge_data, colWidths=[7*inch])
            badge_table.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, -1), HexColor('#eff6ff')),
                ('LINEBEFORE',    (0, 0), (0, -1), 5, HexColor('#3b82f6')),
                ('LEFTPADDING',   (0, 0), (-1, -1), 10),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
                ('TOPPADDING',    (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(badge_table)
            story.append(Spacer(1, 4))

            if is_models_section:
                prop = "Yes" if item.get('is_proprietary', False) else "No"
                story.append(Paragraph(f"<b>Marked as Proprietary in Proposal:</b> {prop}", styles['TableText']))
                story.append(Spacer(1, 4))

            checks = item.get("checks", [])
            if checks:
                story.extend(create_check_elements(checks, styles, header_color=HexColor('#1d4ed8')))
                story.append(Paragraph(f"Total Risk Score: {calculate_total_risk(checks)}", styles['TotalRisk']))
            else:
                story.append(Paragraph("No checks recorded.", styles['TableText']))
            story.append(Spacer(1, 18))


def create_risk_summary_table(section_info: dict, styles, header_label: str = "Risk Score Summary") -> list:
    """Single risk table (used for both original-only and per-addendum tables)."""
    elements = []
    table_data = [["Section", "Max Score", "Risk Category", "Status", "Items", "Artifacts"]]

    for section_name, info in section_info.items():
        if info['count'] > 0:
            rc = get_risk_color(info['highest'])
            cat_text = f"<font color='{rc.hexval()}'><b>{info['category']}</b></font>"
            score_text = f"<font color='{rc.hexval()}'><b>{info['highest']}</b></font>"
            pf_color = '#10b981' if info['pass_fail'] == 'PASS' else '#dc2626'
            pf_text = f"<font color='{pf_color}'><b>{info['pass_fail']}</b></font>"
            links = info.get('artifact_links', [])
            arts = info.get('artifacts', [])
            if links:
                arts_text = "<br/>".join(
                    f'<a href="#{l["anchor"]}" color="#1d4ed8">• {l["name"]}</a>' for l in links
                )
            elif arts:
                arts_text = arts[0] if len(arts) == 1 else "<br/>".join(f"• {a}" for a in arts)
            else:
                arts_text = "—"
            table_data.append([
                Paragraph(section_name, styles['TableText']),
                Paragraph(score_text, styles['TableText']),
                Paragraph(cat_text, styles['TableText']),
                Paragraph(pf_text, styles['TableText']),
                Paragraph(str(info['count']), styles['TableText']),
                Paragraph(arts_text, styles['TableText']),
            ])
        else:
            table_data.append([
                Paragraph(section_name, styles['TableText']),
                Paragraph("—", styles['TableText']),
                Paragraph("<i>No Data</i>", styles['TableText']),
                Paragraph("—", styles['TableText']),
                Paragraph("0", styles['TableText']),
                Paragraph("—", styles['TableText']),
            ])

    table = Table(table_data, colWidths=[1.5*inch, 0.9*inch, 1.2*inch, 0.7*inch, 0.5*inch, 2.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), HexColor('#2c5282')),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('ALIGN',        (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN',        (1, 0), (1, -1), 'CENTER'),
        ('ALIGN',        (3, 0), (3, -1), 'CENTER'),
        ('ALIGN',        (4, 0), (4, -1), 'CENTER'),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 10),
        ('GRID',         (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING',   (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    return elements


def create_maximum_risk_box(section_info: dict, styles,
                             label: str = "MAXIMUM RISK LEVEL",
                             subtitle: str = "Highest risk across all sections",
                             box_bg: str = '#f8fafc',
                             box_border_override: HexColor = None) -> list:
    """Render a centred risk-level box (previously called cumulative risk box)."""
    elements = []
    scores = [info['highest'] for info in section_info.values() if info.get('highest', 0) > 0]
    max_score = max(scores, default=0)
    if max_score == 0:
        elements.append(Paragraph("<i>No risk data available</i>", styles['TableText']))
        return elements

    category = get_risk_category(max_score)
    risk_color = box_border_override or get_risk_color(max_score)
    any_failed = any(i.get('pass_fail') == 'FAIL' for i in section_info.values() if i.get('pass_fail') != 'N/A')
    pass_fail = "FAIL" if any_failed else "PASS"
    pf_color = '#dc2626' if any_failed else '#10b981'

    box_data = [[Paragraph(
        f"<para align=center>"
        f"<b><font size=13>{label}</font></b><br/><br/>"
        f"<font size=34 color='{get_risk_color(max_score).hexval()}'><b>{max_score}</b></font><br/>"
        f"<font size=15 color='{get_risk_color(max_score).hexval()}'><b>{category}</b></font><br/>"
        f"<font size=16 color='{pf_color}'><b>{pass_fail}</b></font><br/><br/>"
        f"<font size=9 color='#718096'><i>{subtitle}</i></font>"
        f"</para>",
        styles['TableText']
    )]]
    box_table = Table(box_data, colWidths=[3.0*inch])
    box_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), HexColor(box_bg)),
        ('BOX',           (0, 0), (-1, -1), 3, risk_color),
        ('LEFTPADDING',   (0, 0), (-1, -1), 16),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 16),
        ('TOPPADDING',    (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(box_table)
    return elements


def create_dual_maximum_risk_boxes(orig_info: dict, updated_info: dict, styles) -> list:
    """Two risk boxes side by side: Original | Updated (incl. Addenda)."""
    orig_elements   = create_maximum_risk_box(
        orig_info, styles,
        label="ORIGINAL MAXIMUM RISK",
        subtitle="Original submission artifacts"
    )
    updated_elements = create_maximum_risk_box(
        updated_info, styles,
        label="UPDATED MAXIMUM RISK",
        subtitle="Incl. all addenda",
        box_bg='#eff6ff',
        box_border_override=HexColor('#3b82f6')
    )

    # Place the two boxes in a two-cell table for side-by-side layout
    row = [[orig_elements[0], updated_elements[0]]]
    dual_table = Table(row, colWidths=[3.25*inch, 3.25*inch], hAlign='CENTER')
    dual_table.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 12),   # gap between boxes
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return [dual_table]


# ── Addendum pages (at end of document) ──────────────────────────────────────

def create_addendum_header_table(addendum_num: int, addendum: dict, styles) -> Table:
    date_str  = addendum.get('date', '—')
    cat_key   = addendum.get('category', '')
    cat_label = ADDENDUM_CATEGORY_LABELS.get(cat_key, cat_key.replace('_', ' ').title())
    n_arts    = len(addendum.get('artifacts', []))
    art_word  = 'artifact' if n_arts == 1 else 'artifacts'

    banner_data = [[
        Paragraph(f"<b>ADDENDUM {addendum_num}</b>", styles['AddendumTitle']),
        Paragraph(
            f"<b>Date:</b> {date_str}<br/><b>Category:</b> {cat_label}<br/>{n_arts} {art_word}",
            styles['AddendumMeta']
        ),
    ]]
    banner = Table(banner_data, colWidths=[2.5*inch, 4.5*inch])
    banner.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), HexColor('#92400e')),
        ('LEFTPADDING',   (0, 0), (-1, -1), 16),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 16),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW',     (0, 0), (-1, -1), 3, HexColor('#f59e0b')),
    ]))
    return banner


def add_addendum_pages(story: list, addenda: list, styles) -> None:
    """Dedicated page(s) per addendum — retains per-addendum obs/rec."""
    if not addenda:
        return

    for idx, addendum in enumerate(addenda, start=1):
        story.append(PageBreak())
        story.append(create_addendum_header_table(idx, addendum, styles))
        story.append(Spacer(1, 20))

        artifacts = addendum.get('artifacts', [])
        cat_key   = addendum.get('category', '')
        cat_label = ADDENDUM_CATEGORY_LABELS.get(cat_key, cat_key.replace('_', ' ').title())

        add_component_section(
            story, title=cat_label, items=artifacts, styles=styles,
            is_models_section=(cat_key == 'models'),
        )

        if artifacts:
            section_info = {cat_label: _build_section_info_entry(cat_label, artifacts)}
            story.append(Spacer(1, 10))
            story.extend(create_risk_summary_table(section_info, styles))
            story.append(Spacer(1, 20))

        story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#fcd34d'), spaceAfter=10))
        story.append(Paragraph("General Observations", styles['AddendumObsHeader']))
        obs = format_text_with_breaks(addendum.get('observations', '')) or "<i>None recorded.</i>"
        story.append(Paragraph(obs, styles['TableText']))
        story.append(Spacer(1, 14))

        story.append(Paragraph("Final Recommendation", styles['AddendumObsHeader']))
        rec = format_text_with_breaks(addendum.get('recommendation', '')) or "<i>Not provided.</i>"
        story.append(Paragraph(rec, styles['TableText']))
        story.append(Spacer(1, 30))


# ── Main PDF builder ──────────────────────────────────────────────────────────

def json_to_pdf(json_filepath: str, output_filepath: str = None) -> str:
    data = load_json(json_filepath)
    output_filepath = output_filepath or json_filepath.rsplit('.', 1)[0] + ".pdf"

    doc = SimpleDocTemplate(
        output_filepath,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.8*inch,
        bottomMargin=0.8*inch
    )

    styles = create_styles()
    story  = []
    addenda = data.get('addenda', [])
    has_addenda = bool(addenda)

    # ── Title & metadata ──────────────────────────────────────────────────────
    story.append(Paragraph("KSL AI Model Control Review", styles['DocTitle']))
    story.append(HRFlowable(width="100%", thickness=4, color=HexColor('#2c5282'), spaceAfter=30))
    story.append(Paragraph("Review Information", styles['SectionHeader']))
    story.append(create_metadata_table(data.get("metadata", {}), styles))
    story.append(Spacer(1, 30))
    story.append(PageBreak())

    # ── Artifact sections (original + inline addenda) ─────────────────────────
    for section_title, section_key in SECTION_KEYS.items():
        add_arts = get_addendum_artifacts_for_section(data, section_key) if has_addenda else []
        add_component_section(
            story,
            title=section_title,
            items=data.get(section_key, []),
            styles=styles,
            is_models_section=(section_key == 'models'),
            addendum_artifacts=add_arts if add_arts else None,
            section_key=section_key,
        )
        story.append(PageBreak())

    # ── Risk Score Summary ────────────────────────────────────────────────────
    story.append(Paragraph("Risk Score Summary", styles['SectionHeader']))

    orig_info = calculate_section_totals_anchored(data)

    if has_addenda:
        # Original table
        story.append(Paragraph(
            "<b>Original Assessment</b>",
            ParagraphStyle('SubLabel', parent=styles['TableText'],
                           fontSize=11, spaceBefore=6, spaceAfter=4,
                           textColor=HexColor('#2c5282'))
        ))
        story.extend(create_risk_summary_table(orig_info, styles))
        story.append(Spacer(1, 14))

        # Updated table (merged)
        updated_info = calculate_merged_section_totals_anchored(data)
        story.append(Paragraph(
            "<b>Updated Assessment (incl. Addenda)</b>",
            ParagraphStyle('SubLabel2', parent=styles['TableText'],
                           fontSize=11, spaceBefore=6, spaceAfter=4,
                           textColor=HexColor('#1d4ed8'))
        ))
        story.extend(create_risk_summary_table(updated_info, styles))
        story.append(Spacer(1, 20))

        # Dual maximum risk boxes
        story.extend(create_dual_maximum_risk_boxes(orig_info, updated_info, styles))
    else:
        story.extend(create_risk_summary_table(orig_info, styles))
        story.append(Spacer(1, 20))
        story.extend(create_maximum_risk_box(orig_info, styles))


    story.append(Spacer(1, 30))

    # ── Observations & Recommendation ─────────────────────────────────────────
    story.append(Paragraph("General Observations", styles['SectionHeader']))
    obs = format_text_with_breaks(data.get("observations", "")) or "None recorded."
    story.append(Paragraph(obs, styles['TableText']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("Final Recommendation", styles['SectionHeader']))
    rec = format_text_with_breaks(data.get("recommendation", "")) or "Not provided."
    story.append(Paragraph(rec, styles['TableText']))
    story.append(Spacer(1, 40))

    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cbd5e0')))
    story.append(Paragraph(
        f"Report generated on {datetime.now():%Y-%m-%d %H:%M:%S}",
        ParagraphStyle(name='Footer', alignment=1, fontSize=9, textColor=HexColor('#718096'))
    ))

    # ── Dedicated addendum pages at end ───────────────────────────────────────
    add_addendum_pages(story, addenda, styles)

    doc.build(story)
    return output_filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python json_to_pdf_v2.py <input.json> [output.pdf]")
        sys.exit(1)
    input_file  = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        result = json_to_pdf(input_file, output_file)
        print(f"PDF created: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
