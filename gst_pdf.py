"""
gst_pdf.py — GST-compliant invoice PDF generation using ReportLab.
Produces a proper Indian tax invoice with:
  - Business & buyer details
  - GSTIN numbers
  - HSN/SAC code
  - CGST + SGST breakdown (or IGST for inter-state)
  - Cryptographic proof section
  - QR code embedded in the invoice
"""
import io, base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfgen import canvas as pdfcanvas
from config import (
    BUSINESS_NAME, BUSINESS_GSTIN, BUSINESS_ADDRESS,
    BUSINESS_PAN, BUSINESS_EMAIL, BUSINESS_PHONE
)

# ── Colours ──────────────────────────────────────────────────────────────────
SAFFRON   = HexColor("#D97706")
INK       = HexColor("#0F172A")
INK_LIGHT = HexColor("#64748B")
CREAM     = HexColor("#FEF3C7")
SAGE      = HexColor("#059669")
LINE      = HexColor("#E2E8F0")

W, H = A4  # 595.27 × 841.89 pt

# ── Styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **{"fontName":"Helvetica","fontSize":9,"textColor":INK,"leading":13,**kw})

HEAD   = S("head",   fontName="Helvetica-Bold", fontSize=18, textColor=SAFFRON)
SUBHD  = S("subhd",  fontName="Helvetica-Bold", fontSize=11, textColor=INK)
SMALL  = S("small",  fontSize=8,  textColor=INK_LIGHT, leading=11)
BODY   = S("body",   fontSize=9,  textColor=INK)
RBODY  = S("rbody",  fontSize=9,  textColor=INK, alignment=TA_RIGHT)
MONO   = S("mono",   fontName="Courier", fontSize=7.5, textColor=INK_LIGHT, leading=10)

# ── Main function ─────────────────────────────────────────────────────────────

def generate_gst_invoice(receipt: dict, qr_b64: str = None) -> bytes:
    """
    Returns PDF bytes for a GST-compliant invoice.

    receipt dict must contain:
      id, amount, upi_id, vendor_id, vendor_name, timestamp,
      hash, signature  (and optionally: gst_number, hsn_code, payment_ref)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=15*mm,
        title="GST Tax Invoice — PayShield"
    )

    story = []

    # ── Header bar ───────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(BUSINESS_NAME, HEAD),
        Paragraph("TAX INVOICE", S("ti", fontName="Helvetica-Bold", fontSize=14,
                                   textColor=INK, alignment=TA_RIGHT))
    ]]
    header_tbl = Table(header_data, colWidths=[100*mm, 65*mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width="100%", thickness=1.5, color=SAFFRON, spaceAfter=6))

    # ── Business & invoice details row ───────────────────────────────────────
    ts = receipt.get("timestamp","")[:19].replace("T", " ")
    inv_no = "INV-" + receipt.get("id","")[:8].upper()

    biz_info = f"""
<b>{BUSINESS_NAME}</b><br/>
GSTIN: {BUSINESS_GSTIN}<br/>
PAN: {BUSINESS_PAN}<br/>
{BUSINESS_ADDRESS}<br/>
📧 {BUSINESS_EMAIL} &nbsp; 📞 {BUSINESS_PHONE}
"""
    inv_info = f"""
<b>Invoice No:</b> {inv_no}<br/>
<b>Date:</b> {ts} UTC<br/>
<b>Vendor:</b> {receipt.get('vendor_name','')}<br/>
<b>Vendor ID:</b> {receipt.get('vendor_id','')}
"""
    buyer_gstin = receipt.get("gst_number","") or "Unregistered / Consumer"
    buyer_info = f"""
<b>Buyer / Payer</b><br/>
UPI ID: {receipt.get('upi_id','')}<br/>
GSTIN: {buyer_gstin}<br/>
Payment Ref: {receipt.get('payment_ref','') or receipt.get('id','')[:16] + '…'}
"""

    biz_tbl = Table([
        [Paragraph(biz_info, SMALL), Paragraph(inv_info, SMALL), Paragraph(buyer_info, SMALL)]
    ], colWidths=[65*mm, 55*mm, 45*mm])
    biz_tbl.setStyle(TableStyle([
        ("VALIGN",  (0,0),(-1,-1),"TOP"),
        ("BACKGROUND",(0,0),(0,0), HexColor("#FDFAF5")),
        ("BOX",     (0,0),(0,0), 0.5, LINE),
        ("BOX",     (1,0),(1,0), 0.5, LINE),
        ("BOX",     (2,0),(2,0), 0.5, LINE),
        ("LEFTPADDING", (0,0),(-1,-1), 6),
        ("RIGHTPADDING",(0,0),(-1,-1), 6),
        ("TOPPADDING",  (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    story.append(biz_tbl)
    story.append(Spacer(1, 8))

    # ── Line items table ──────────────────────────────────────────────────────
    amount       = float(receipt.get("amount", 0))
    hsn          = receipt.get("hsn_code", "9971")    # 9971 = Financial services
    # GST 18% split into CGST 9% + SGST 9% (intra-state)
    taxable      = round(amount / 1.18, 2)
    cgst         = round(taxable * 0.09, 2)
    sgst         = round(taxable * 0.09, 2)
    total        = round(taxable + cgst + sgst, 2)

    items_header = ["#", "Description", "HSN/SAC", "Qty", "Rate (₹)", "Taxable (₹)"]
    items_row    = ["1",
                    Paragraph(f"Digital Payment Processing Service<br/><font size=7 color=grey>Vendor: {receipt.get('vendor_name','')}</font>", BODY),
                    hsn, "1",
                    f"{taxable:,.2f}", f"{taxable:,.2f}"]
    items_data   = [items_header, items_row]

    items_tbl = Table(items_data, colWidths=[8*mm,62*mm,20*mm,12*mm,25*mm,25*mm])
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0),  INK),
        ("TEXTCOLOR",    (0,0),(-1,0),  white),
        ("FONTNAME",     (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,-1), 8.5),
        ("ALIGN",        (3,0),(-1,-1), "RIGHT"),
        ("ALIGN",        (0,0),(0,-1),  "CENTER"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[HexColor("#FDFAF5"), white]),
        ("BOX",          (0,0),(-1,-1), 0.5, LINE),
        ("INNERGRID",    (0,0),(-1,-1), 0.3, LINE),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0),(-1,-1), 5),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 4))

    # ── Tax summary + QR ─────────────────────────────────────────────────────
    tax_rows = [
        ["",                  "Taxable Value",      f"₹{taxable:,.2f}"],
        ["",                  "CGST @ 9%",          f"₹{cgst:,.2f}"],
        ["",                  "SGST @ 9%",          f"₹{sgst:,.2f}"],
        ["",                  Paragraph("<b>Total Invoice Amount</b>", S("tb",fontName="Helvetica-Bold",fontSize=9,textColor=SAGE)), Paragraph(f"<b>₹{total:,.2f}</b>", S("tv",fontName="Helvetica-Bold",fontSize=11,textColor=SAGE,alignment=TA_RIGHT))],
    ]

    qr_cell = ""
    if qr_b64:
        try:
            qr_bytes  = base64.b64decode(qr_b64)
            qr_buf    = io.BytesIO(qr_bytes)
            qr_img    = RLImage(qr_buf, width=30*mm, height=30*mm)
            qr_cell   = qr_img
        except Exception:
            qr_cell = Paragraph("QR unavailable", SMALL)

    summary_data = [[qr_cell, Table(tax_rows, colWidths=[0, 47*mm, 30*mm])]]
    summary_tbl  = Table(summary_data, colWidths=[35*mm, 80*mm])
    summary_tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0)]))
    story.append(summary_tbl)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))

    # ── Cryptographic proof section ───────────────────────────────────────────
    story.append(Paragraph("🔐  Cryptographic Proof of Payment", SUBHD))
    story.append(Spacer(1, 4))
    proof_data = [
        ["Transaction ID",  receipt.get("id","")],
        ["SHA-256 Hash",    receipt.get("hash","")],
        ["RSA-PSS Sig",     (receipt.get("signature","") or "")[:72] + "…"],
        ["Issued At",       receipt.get("timestamp","")],
        ["Expires At",      receipt.get("expires_at","")],
        ["Key Version",     receipt.get("key_version","v1")],
    ]
    proof_tbl = Table(proof_data, colWidths=[28*mm, 137*mm])
    proof_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(0,-1), HexColor("#F1F5F9")),
        ("FONTNAME",     (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTNAME",     (1,0),(1,-1), "Courier"),
        ("FONTSIZE",     (0,0),(-1,-1),7.5),
        ("TEXTCOLOR",    (0,0),(0,-1), INK),
        ("TEXTCOLOR",    (1,0),(1,-1), INK_LIGHT),
        ("INNERGRID",    (0,0),(-1,-1), 0.3, LINE),
        ("BOX",          (0,0),(-1,-1), 0.5, LINE),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    story.append(proof_tbl)
    story.append(Spacer(1, 6))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=4))
    story.append(Paragraph(
        "This is a computer-generated GST Tax Invoice. "
        "The cryptographic signature above constitutes proof of payment. "
        "Verify at: http://localhost:5000/vendor",
        SMALL
    ))

    doc.build(story)
    return buf.getvalue()
