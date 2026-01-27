#!/usr/bin/env python3
"""
KSL AI Model Control Review → PDF Generator
- Fixed title: "KSL AI Model Control Review"
- Shows original risk scores (1/2/3/4)
- Shows Total Risk Score per artifact
- Handles very long notes by rendering them separately
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


# If notes exceed this character count, render them outside the table
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

    return styles


def format_text_with_breaks(text: str) -> str:
    """Convert newline characters to HTML breaks for proper PDF rendering."""
    if not text:
        return ""
    return text.strip().replace('\n', '<br/>')


def calculate_total_risk(checks) -> int:
    """Calculate total risk score from checks (handles both dict and list format)."""
    total = 0
    
    # Handle checks as dictionary (Streamlit format)
    if isinstance(checks, dict):
        for check_data in checks.values():
            score = check_data.get("score")
            if isinstance(score, (int, float)):
                total += int(score)
    # Handle checks as list (original format)
    elif isinstance(checks, list):
        for check in checks:
            score = check.get("score")
            if isinstance(score, (int, float)):
                total += int(score)
    
    return total


def get_highest_score_in_section(items: list) -> int:
    """Get the highest individual score across all checks in a section."""
    if not items:
        return 0
    
    max_score = 0
    for item in items:
        checks = item.get("checks", [])
        
        # Handle checks as dictionary (Streamlit format)
        if isinstance(checks, dict):
            for check_data in checks.values():
                score = check_data.get("score")
                if isinstance(score, (int, float)):
                    max_score = max(max_score, int(score))
        # Handle checks as list (original format)
        elif isinstance(checks, list):
            for check in checks:
                score = check.get("score")
                if isinstance(score, (int, float)):
                    max_score = max(max_score, int(score))
    
    return max_score


def get_risk_category(score: int) -> str:
    """Map risk score to category."""
    risk_map = {
        1: "No Risk",
        2: "Low Risk",
        3: "Medium Risk",
        4: "High Risk",
        5: "Critical Risk"
    }
    return risk_map.get(score, "Unknown")


def get_risk_color(score: int) -> HexColor:
    """Get color for risk score."""
    color_map = {
        1: HexColor('#10b981'),  # green
        2: HexColor('#fbbf24'),  # yellow
        3: HexColor('#f97316'),  # orange
        4: HexColor('#ef4444'),  # red
        5: HexColor('#dc2626')   # dark red
    }
    return color_map.get(score, HexColor('#6b7280'))  # gray default


def calculate_section_total_score(items: list) -> int:
    """
    Calculate section total using two-step algorithm:
    1. Find max score for each question across all artifacts
    2. Sum all the max values
    """
    if not items:
        return 0
    
    # Dictionary to track max score for each check/question
    check_max_scores = {}
    
    for item in items:
        checks = item.get("checks", [])
        
        # Handle checks as dictionary (Streamlit format)
        if isinstance(checks, dict):
            for check_name, check_data in checks.items():
                score = check_data.get("score")
                if isinstance(score, (int, float)):
                    score = int(score)
                    if check_name not in check_max_scores:
                        check_max_scores[check_name] = score
                    else:
                        check_max_scores[check_name] = max(check_max_scores[check_name], score)
        # Handle checks as list (original format)
        elif isinstance(checks, list):
            for check in checks:
                check_name = check.get("name", "")
                score = check.get("score")
                if isinstance(score, (int, float)):
                    score = int(score)
                    if check_name not in check_max_scores:
                        check_max_scores[check_name] = score
                    else:
                        check_max_scores[check_name] = max(check_max_scores[check_name], score)
    
    # Sum all max values
    return sum(check_max_scores.values())


def calculate_section_totals(data: dict) -> dict:
    """Calculate total scores and risk categories for each section."""
    sections = {
        'Third-Party Software': 'third_party_software',
        'Source Code': 'source_code',
        'Datasets / User Files': 'datasets_user_files',
        'AI Models': 'models'
    }
    
    section_info = {}
    for display_name, key in sections.items():
        items = data.get(key, [])
        if items:
            # Use two-step algorithm: max per question, then sum
            total_score = calculate_section_total_score(items)
            highest_score = get_highest_score_in_section(items)
            pass_fail = "FAIL" if total_score >= 21 else "PASS"
            
            # Get artifacts that contributed to the highest score
            high_score_artifacts = []
            for item in items:
                checks = item.get("checks", [])
                item_has_high_score = False
                
                # Handle checks as dictionary (Streamlit format)
                if isinstance(checks, dict):
                    for check_data in checks.values():
                        score = check_data.get("score")
                        if isinstance(score, (int, float)) and int(score) == highest_score:
                            item_has_high_score = True
                            break
                # Handle checks as list (original format)
                elif isinstance(checks, list):
                    for check in checks:
                        score = check.get("score")
                        if isinstance(score, (int, float)) and int(score) == highest_score:
                            item_has_high_score = True
                            break
                
                if item_has_high_score:
                    artifact_name = item.get("name", "Unnamed").strip() or "Unnamed"
                    high_score_artifacts.append(artifact_name)
            
            section_info[display_name] = {
                'total': total_score,
                'highest': highest_score,
                'category': get_risk_category(highest_score),
                'count': len(items),
                'pass_fail': pass_fail,
                'artifacts': high_score_artifacts
            }
        else:
            section_info[display_name] = {
                'total': 0,
                'highest': 0,
                'category': 'No Data',
                'count': 0,
                'pass_fail': 'N/A',
                'artifacts': []
            }
    
    return section_info


def create_risk_summary_table(section_info: dict, styles) -> list:
    """Create the risk score summary table showing section scores and categories."""
    elements = []
    
    # Section scores table with artifacts column
    table_data = [["Section", "Section Score", "Risk Category", "Status", "Items", "Artifacts"]]
    
    for section_name, info in section_info.items():
        if info['count'] > 0:
            risk_color = get_risk_color(info['highest'])
            category_text = f"<font color='{risk_color.hexval()}'><b>{info['category']}</b></font>"
            score_text = f"<font color='{risk_color.hexval()}'><b>{info['highest']}</b></font>"
            
            # Color code Pass/Fail
            pass_fail = info['pass_fail']
            pass_fail_color = '#10b981' if pass_fail == 'PASS' else '#dc2626'  # green or red
            pass_fail_text = f"<font color='{pass_fail_color}'><b>{pass_fail}</b></font>"
            
            # Format artifacts list
            artifacts = info.get('artifacts', [])
            if artifacts:
                # Use bullet points for multiple artifacts
                if len(artifacts) == 1:
                    artifacts_text = artifacts[0]
                else:
                    artifacts_text = "<br/>".join([f"• {name}" for name in artifacts])
            else:
                artifacts_text = "—"
            
            table_data.append([
                Paragraph(section_name, styles['TableText']),
                Paragraph(score_text, styles['TableText']),
                Paragraph(category_text, styles['TableText']),
                Paragraph(pass_fail_text, styles['TableText']),
                Paragraph(str(info['count']), styles['TableText']),
                Paragraph(artifacts_text, styles['TableText'])
            ])
        else:
            table_data.append([
                Paragraph(section_name, styles['TableText']),
                Paragraph("—", styles['TableText']),
                Paragraph("<i>No Data</i>", styles['TableText']),
                Paragraph("—", styles['TableText']),
                Paragraph("0", styles['TableText']),
                Paragraph("—", styles['TableText'])
            ])
    
    table = Table(table_data, colWidths=[1.5*inch, 0.9*inch, 1.2*inch, 0.7*inch, 0.5*inch, 2.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    
    return elements


def create_cumulative_risk_box(section_info: dict, styles) -> list:
    """Create the cumulative risk level display."""
    elements = []
    
    # Find the highest risk score across all sections
    cumulative_score = max((info['highest'] for info in section_info.values()), default=0)
    cumulative_category = get_risk_category(cumulative_score)
    risk_color = get_risk_color(cumulative_score)
    
    # Determine cumulative Pass/Fail - fails if ANY section fails
    any_section_failed = any(info.get('pass_fail') == 'FAIL' for info in section_info.values() if info.get('pass_fail') != 'N/A')
    cumulative_pass_fail = "FAIL" if any_section_failed else "PASS"
    cumulative_pass_fail_color = '#dc2626' if any_section_failed else '#10b981'  # red or green
    
    if cumulative_score > 0:
        # Create a styled box for cumulative risk
        cumulative_data = [[
            Paragraph(
                f"<para align=center>"
                f"<b><font size=14>CUMULATIVE RISK LEVEL</font></b><br/><br/>"
                f"<font size=36 color='{risk_color.hexval()}'><b>{cumulative_score}</b></font><br/>"
                f"<font size=16 color='{risk_color.hexval()}'><b>{cumulative_category}</b></font><br/>"
                f"<font size=18 color='{cumulative_pass_fail_color}'><b>{cumulative_pass_fail}</b></font><br/><br/>"
                f"<font size=9 color='#718096'><i>Highest risk across all sections</i></font>"
                f"</para>",
                styles['TableText']
            )
        ]]
        
        cumulative_table = Table(cumulative_data, colWidths=[6.5*inch])
        cumulative_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 3, risk_color),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(cumulative_table)
    else:
        elements.append(Paragraph(
            "<i>No risk data available</i>",
            styles['TableText']
        ))
    
    return elements


def create_check_elements(checks, styles) -> list:
    """
    Create table and any expanded notes elements for checks.
    Returns a list of flowables.
    Handles checks as both dict (Streamlit format) and list (original format).
    """
    elements = []
    
    # Build table data - for long notes, just put "See below" in the cell
    table_data = [["Check", "Risk Score", "Notes"]]
    expanded_notes = []  # List of (check_name, notes) for long notes
    
    # Convert checks to list format if it's a dict
    check_list = []
    if isinstance(checks, dict):
        for check_name, check_data in checks.items():
            check_list.append({
                "name": check_name,
                "score": check_data.get("score"),
                "notes": check_data.get("notes", "")
            })
    elif isinstance(checks, list):
        check_list = checks
    
    for check in check_list:
        name = check.get("name", "—")
        score = check.get("score", "—")
        notes_raw = (check.get("notes") or "").strip()
        notes_html = format_text_with_breaks(notes_raw)
        score_display = f"<b>{score}</b>" if score != "—" else "—"
        
        if len(notes_raw) > MAX_NOTES_IN_TABLE:
            # Long notes - show reference in table, expand below
            table_data.append([
                Paragraph(name, styles['TableText']),
                Paragraph(score_display, styles['TableText']),
                Paragraph("<i>See details below ↓</i>", styles['TableText'])
            ])
            expanded_notes.append((name, notes_html))
        else:
            # Short notes - show in table
            table_data.append([
                Paragraph(name, styles['TableText']),
                Paragraph(score_display, styles['TableText']),
                Paragraph(notes_html if notes_html else "—", styles['TableText'])
            ])
    
    # Create the table
    table = Table(table_data, colWidths=[2.3*inch, 0.8*inch, 3.9*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    
    # Add expanded notes sections below the table
    if expanded_notes:
        elements.append(Spacer(1, 10))
        for check_name, notes_html in expanded_notes:
            elements.append(Paragraph(f"► {check_name}:", styles['NotesLabel']))
            elements.append(Paragraph(notes_html, styles['NotesExpanded']))
    
    return elements


def create_metadata_table(metadata: dict, styles) -> Table:
    fields = {
        'proposal_title': 'Proposal Title',
        'principal_investigator': 'Principal Investigator',
        'proposal_date': 'Proposal Date',
        'reviewer_name': 'Reviewer Name',
        'reviewer_id': 'Reviewer ID',
        'aimcr_date': 'AIMCR Date',
        'project_id': 'Project ID'
    }

    data = []
    for key, label in fields.items():
        value = metadata.get(key, 'N/A')
        data.append([
            Paragraph(f"<b>{label}:</b>", styles['TableText']),
            Paragraph(str(value), styles['TableText'])
        ])

    table = Table(data, colWidths=[2.4*inch, 4.3*inch])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e0')),
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#edf2f7')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table


def add_component_section(story, title: str, items: list, styles, is_models_section: bool = False):
    story.append(Paragraph(title, styles['SectionHeader']))

    if not items:
        story.append(Paragraph("No items in this category.", styles['TableText']))
        story.append(Spacer(1, 20))
        return

    for idx, item in enumerate(items, 1):
        name = item.get("name", "").strip() or "(Unnamed component)"
        
        # Add proprietary indicator for models
        if is_models_section and item.get('is_proprietary', False):
            story.append(Paragraph(f"{idx}. {name} 🔒 <i>(Marked as Proprietary)</i>", styles['ItemHeader']))
        else:
            story.append(Paragraph(f"{idx}. {name}", styles['ItemHeader']))
        
        # Show proprietary status as separate line for models
        if is_models_section:
            proprietary_text = "Yes" if item.get('is_proprietary', False) else "No"
            story.append(Paragraph(
                f"<b>Marked as Proprietary in Proposal:</b> {proprietary_text}",
                styles['TableText']
            ))
            story.append(Spacer(1, 8))

        checks = item.get("checks", [])
        if checks:
            # Get table and any expanded notes
            check_elements = create_check_elements(checks, styles)
            story.extend(check_elements)
            
            total = calculate_total_risk(checks)
            story.append(Paragraph(f"Total Risk Score: {total}", styles['TotalRisk']))
        else:
            story.append(Paragraph("No checks recorded.", styles['TableText']))

        story.append(Spacer(1, 25))


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
    story = []

    story.append(Paragraph("KSL AI Model Control Review", styles['DocTitle']))
    story.append(HRFlowable(width="100%", thickness=4, color=HexColor('#2c5282'), spaceAfter=30))

    story.append(Paragraph("Review Information", styles['SectionHeader']))
    story.append(create_metadata_table(data.get("metadata", {}), styles))
    story.append(Spacer(1, 30))
    story.append(PageBreak())

    add_component_section(story, "Third-Party Software", data.get("third_party_software", []), styles)
    story.append(PageBreak())

    add_component_section(story, "Source Code", data.get("source_code", []), styles)
    story.append(PageBreak())

    add_component_section(story, "Datasets / User Files", data.get("datasets_user_files", []), styles)
    story.append(PageBreak())

    add_component_section(story, "AI Models", data.get("models", []), styles, is_models_section=True)
    story.append(PageBreak())

    # Add Risk Score Summary before Observations
    story.append(Paragraph("Risk Score Summary", styles['SectionHeader']))
    section_info = calculate_section_totals(data)
    story.extend(create_risk_summary_table(section_info, styles))
    story.append(Spacer(1, 20))
    
    # Add Cumulative Risk Level
    story.extend(create_cumulative_risk_box(section_info, styles))
    story.append(Spacer(1, 30))

    story.append(Paragraph("General Observations", styles['SectionHeader']))
    observations_text = format_text_with_breaks(data.get("observations", "")) or "None recorded."
    story.append(Paragraph(observations_text, styles['TableText']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("Final Recommendation", styles['SectionHeader']))
    recommendation_text = format_text_with_breaks(data.get("recommendation", "")) or "Not provided."
    story.append(Paragraph(recommendation_text, styles['TableText']))

    story.append(Spacer(1, 40))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cbd5e0')))
    story.append(Paragraph(
        f"Report generated on {datetime.now():%Y-%m-%d %H:%M:%S}",
        ParagraphStyle(name='Footer', alignment=1, fontSize=9, textColor=HexColor('#718096'))
    ))

    doc.build(story)
    return output_filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python json_to_pdf.py <input.json> [output.pdf]")
        sys.exit(1)

    input_file = sys.argv[1]
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
