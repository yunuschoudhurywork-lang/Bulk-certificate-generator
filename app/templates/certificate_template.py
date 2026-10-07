"""
Certificate template design constants and drawing functions.
Defines the layout, colors, fonts, and helper functions for generating
professional-looking certificates using ReportLab.
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Page dimensions - A4 landscape (297mm x 210mm)
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # 842pt x 595pt

# Layout constants
MARGIN = 50  # 50pt margin from edges
TITLE_FONT_SIZE = 36
SUBTITLE_FONT_SIZE = 18
BODY_FONT_SIZE = 14

# Color scheme
PRIMARY_COLOR = colors.HexColor("#1a237e")  # Navy blue
ACCENT_COLOR = colors.HexColor("#ffd700")  # Gold
TEXT_COLOR = colors.black
BORDER_COLOR = ACCENT_COLOR


def draw_certificate_border(c: canvas.Canvas) -> None:
    """
    Draw decorative border around the certificate.
    
    Args:
        c: ReportLab Canvas object
    """
    # Outer gold border
    c.setStrokeColor(ACCENT_COLOR)
    c.setLineWidth(3)
    c.rect(MARGIN, MARGIN, PAGE_WIDTH - 2 * MARGIN, PAGE_HEIGHT - 2 * MARGIN)
    
    # Inner line
    c.setStrokeColor(PRIMARY_COLOR)
    c.setLineWidth(1)
    c.rect(MARGIN + 10, MARGIN + 10, 
           PAGE_WIDTH - 2 * MARGIN - 20, 
           PAGE_HEIGHT - 2 * MARGIN - 20)


def draw_certificate_header(c: canvas.Canvas) -> None:
    """
    Draw the certificate title/header section.
    
    Args:
        c: ReportLab Canvas object
    """
    # Main title
    c.setFont("Helvetica-Bold", TITLE_FONT_SIZE)
    c.setFillColor(PRIMARY_COLOR)
    title_text = "Certificate of Completion"
    title_width = c.stringWidth(title_text, "Helvetica-Bold", TITLE_FONT_SIZE)
    c.drawString((PAGE_WIDTH - title_width) / 2, PAGE_HEIGHT - 120, title_text)
    
    # Decorative line under title
    c.setStrokeColor(ACCENT_COLOR)
    c.setLineWidth(2)
    line_start_x = (PAGE_WIDTH - 300) / 2
    c.line(line_start_x, PAGE_HEIGHT - 130, line_start_x + 300, PAGE_HEIGHT - 130)


def draw_recipient_info(
    c: canvas.Canvas,
    recipient_name: str,
    course: str,
    completion_date: str
) -> None:
    """
    Draw the recipient information section with name, course, and date.
    
    Args:
        c: ReportLab Canvas object
        recipient_name: Name of the certificate recipient
        course: Name of the completed course
        completion_date: Date of completion (formatted string)
    """
    center_x = PAGE_WIDTH / 2
    current_y = PAGE_HEIGHT - 200
    
    # "This is to certify that"
    c.setFont("Helvetica", BODY_FONT_SIZE)
    c.setFillColor(TEXT_COLOR)
    certify_text = "This is to certify that"
    certify_width = c.stringWidth(certify_text, "Helvetica", BODY_FONT_SIZE)
    c.drawString((PAGE_WIDTH - certify_width) / 2, current_y, certify_text)
    current_y -= 50
    
    # Recipient name - large and prominent
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(PRIMARY_COLOR)
    name_width = c.stringWidth(recipient_name, "Helvetica-Bold", 28)
    c.drawString((PAGE_WIDTH - name_width) / 2, current_y, recipient_name)
    
    # Decorative line under name
    c.setStrokeColor(ACCENT_COLOR)
    c.setLineWidth(1)
    line_length = min(name_width + 40, 400)
    c.line((PAGE_WIDTH - line_length) / 2, current_y - 5, 
           (PAGE_WIDTH + line_length) / 2, current_y - 5)
    current_y -= 50
    
    # "has successfully completed"
    c.setFont("Helvetica", BODY_FONT_SIZE)
    c.setFillColor(TEXT_COLOR)
    completed_text = "has successfully completed"
    completed_width = c.stringWidth(completed_text, "Helvetica", BODY_FONT_SIZE)
    c.drawString((PAGE_WIDTH - completed_width) / 2, current_y, completed_text)
    current_y -= 40
    
    # Course name
    c.setFont("Helvetica-Bold", SUBTITLE_FONT_SIZE)
    c.setFillColor(PRIMARY_COLOR)
    course_width = c.stringWidth(course, "Helvetica-Bold", SUBTITLE_FONT_SIZE)
    c.drawString((PAGE_WIDTH - course_width) / 2, current_y, course)
    current_y -= 40
    
    # "on" date
    c.setFont("Helvetica", BODY_FONT_SIZE)
    c.setFillColor(TEXT_COLOR)
    date_text = f"on {completion_date}"
    date_width = c.stringWidth(date_text, "Helvetica", BODY_FONT_SIZE)
    c.drawString((PAGE_WIDTH - date_width) / 2, current_y, date_text)


def draw_certificate_footer(c: canvas.Canvas) -> None:
    """
    Draw footer section with optional signature placeholder and decorative elements.
    
    Args:
        c: ReportLab Canvas object
    """
    footer_y = 120
    
    # Signature line placeholder (optional - can be enhanced later)
    c.setStrokeColor(TEXT_COLOR)
    c.setLineWidth(1)
    signature_line_length = 150
    signature_x = (PAGE_WIDTH - signature_line_length) / 2
    c.line(signature_x, footer_y, signature_x + signature_line_length, footer_y)
    
    # "Authorized Signature" label
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.grey)
    label_text = "Authorized Signature"
    label_width = c.stringWidth(label_text, "Helvetica", 10)
    c.drawString((PAGE_WIDTH - label_width) / 2, footer_y - 15, label_text)
    
    # Decorative corner elements
    c.setFillColor(ACCENT_COLOR)
    corner_size = 20
    # Bottom left corner
    c.circle(MARGIN + 20, MARGIN + 20, corner_size, fill=0, stroke=1)
    # Bottom right corner
    c.circle(PAGE_WIDTH - MARGIN - 20, MARGIN + 20, corner_size, fill=0, stroke=1)
