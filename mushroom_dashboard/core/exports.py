"""Shared helpers for the admin "Export PDF" and "Convert to CSV" buttons.

PDF  - built with ReportLab: branded header, KPI tiles, zebra tables and a
       "Page x of y" footer. Core PDF fonts have no peso sign, so money is
       written as "PHP 1,234.50".
CSV  - written so Excel opens it cleanly: UTF-8 with BOM (accents/peso text
       survive), CRLF line endings, one header row, real numbers (no currency
       symbols or thousands separators), separate Date and Time columns so
       nothing shows as "#####", and text that looks like a formula or a
       number with leading zeros is protected from Excel "helpfulness".
"""
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone

BRAND_NAME = 'KABUTOMATE'
BRAND_GREEN = '#0c4b33'
LIGHT_GREEN = '#e9f5ee'
ZEBRA = '#f8fafc'
GRID = '#d9e2ec'
TEXT_MUTED = '#64748b'


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def money(value):
    """'PHP 1,234.50' (None -> 'PHP 0.00')."""
    amount = Decimal(value or 0)
    return f"-PHP {abs(amount):,.2f}" if amount < 0 else f"PHP {amount:,.2f}"


def num(value, places=2):
    """Plain, thousands-separated number for PDFs; '-' for empty values."""
    if value is None or value == '':
        return '-'
    return f"{Decimal(value):,.{places}f}"


def local_dt(value):
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def pretty_dt(value):
    value = local_dt(value)
    return value.strftime('%Y-%m-%d %H:%M') if value else '-'


def file_stamp():
    return timezone.localtime().strftime('%Y%m%d_%H%M')


# --------------------------------------------------------------------------
# CSV (Excel-friendly)
# --------------------------------------------------------------------------
_FORMULA_START = ('=', '+', '-', '@')


def _csv_cell(value):
    """Convert a Python value to something Excel renders cleanly."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, Decimal):
        # Plain number, no thousands separator or symbol -> stays numeric in Excel.
        return format(value, 'f')
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return local_dt(value).strftime('%Y-%m-%d %H:%M')
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    text = str(value).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').strip()
    if text.startswith(_FORMULA_START) and not re.fullmatch(r'[-+]?\d+(\.\d+)?', text):
        # Neutralise spreadsheet formula injection.
        return "'" + text
    return text


def text_cell(value):
    """Force Excel to keep a value as text (phone numbers, long IDs)."""
    value = '' if value is None else str(value).strip()
    if value and (re.fullmatch(r'\+?\d{6,}', value) or re.fullmatch(r'0\d+', value)):
        return f'="{value}"'
    return value


def split_datetime(value):
    """Return (date, time) strings for two clean Excel columns."""
    value = local_dt(value)
    if not value:
        return '', ''
    return value.strftime('%Y-%m-%d'), value.strftime('%H:%M')


def csv_response(filename, headers, rows, footer_rows=None):
    """Return a download response for an Excel-friendly CSV.

    rows / footer_rows: iterables of lists matching `headers`. Footer rows
    (e.g. totals) go after one blank line so the main table stays sortable.
    """
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\r\n', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([c if (isinstance(c, str) and c.startswith('="')) else _csv_cell(c) for c in row])
    if footer_rows:
        writer.writerow([])
        for row in footer_rows:
            writer.writerow([c if (isinstance(c, str) and c.startswith('="')) else _csv_cell(c) for c in row])

    # utf-8-sig writes the BOM that tells Excel the file is UTF-8.
    response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def _styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    green = colors.HexColor(BRAND_GREEN)
    return {
        'title': ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=green),
        'subtitle': ParagraphStyle('Subtitle', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor(TEXT_MUTED)),
        'h2': ParagraphStyle('H2', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=green, spaceBefore=10, spaceAfter=5),
        'cell': ParagraphStyle('Cell', fontName='Helvetica', fontSize=8, leading=10, alignment=TA_LEFT),
        'cell_right': ParagraphStyle('CellR', fontName='Helvetica', fontSize=8, leading=10, alignment=2),
        'head': ParagraphStyle('Head', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white),
        'head_right': ParagraphStyle('HeadR', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=2),
        'note': ParagraphStyle('Note', fontName='Helvetica-Oblique', fontSize=8, leading=10, textColor=colors.HexColor(TEXT_MUTED)),
        'kpi_label': ParagraphStyle('KpiL', fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor(TEXT_MUTED)),
        'kpi_value': ParagraphStyle('KpiV', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=green),
    }


def _esc(value):
    from xml.sax.saxutils import escape
    return escape('' if value is None else str(value))


def _numbered_canvas_class(report_title):
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total):
            width, _ = self._pagesize
            self.setStrokeColor(colors.HexColor(GRID))
            self.setLineWidth(0.5)
            self.line(40, 30, width - 40, 30)
            self.setFont('Helvetica', 7.5)
            self.setFillColor(colors.HexColor(TEXT_MUTED))
            self.drawString(40, 19, f'{BRAND_NAME}  |  {report_title}')
            self.drawRightString(width - 40, 19, f'Page {self._pageNumber} of {total}')

    return NumberedCanvas


def build_pdf(filename, title, subtitle_lines=None, kpis=None, sections=None, landscape_mode=False):
    """Build and return a branded PDF response.

    kpis     : list of (label, value) shown as tiles under the title.
    sections : list of dicts. Each is either
               {'heading': str, 'headers': [...], 'rows': [[...]],
                'widths': [relative widths], 'right': {col indexes},
                'empty': 'text when no rows', 'note': 'optional small text'}
               or {'heading': str, 'flowable': <reportlab flowable>, 'then': <table section kept with it>}.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
    )

    page = landscape(A4) if landscape_mode else A4
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=page,
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
        title=f'{BRAND_NAME} {title}', author=BRAND_NAME,
    )
    usable = page[0] - 28 * mm
    st = _styles()
    green = colors.HexColor(BRAND_GREEN)
    story = []

    # Brand band + title
    band = Table([[Paragraph(f'<font color="white"><b>{BRAND_NAME}</b></font>', st['cell'])]], colWidths=[usable], rowHeights=[8 * mm])
    band.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), green),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story += [band, Spacer(1, 8), Paragraph(_esc(title), st['title'])]
    generated = timezone.localtime().strftime('%B %d, %Y %I:%M %p')
    for line in (subtitle_lines or []):
        story.append(Paragraph(_esc(line), st['subtitle']))
    story.append(Paragraph(f'Generated {generated}', st['subtitle']))
    story.append(Spacer(1, 8))

    # KPI tiles
    if kpis:
        per_row = 4 if landscape_mode else 3
        tiles = []
        for label, value in kpis:
            tiles.append([Paragraph(_esc(label).upper(), st['kpi_label']), Paragraph(_esc(value), st['kpi_value'])])
        rows = []
        for i in range(0, len(tiles), per_row):
            chunk = tiles[i:i + per_row]
            while len(chunk) < per_row:
                chunk.append(['', ''])
            rows.append(chunk)
        gap = 3 * mm
        tile_w = (usable - gap * (per_row - 1)) / per_row
        for chunk in rows:
            cells = []
            for tile in chunk:
                inner = Table([[tile[0]], [tile[1]]], colWidths=[tile_w]) if tile[0] != '' else ''
                if inner != '':
                    inner.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(LIGHT_GREEN)),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 1), (-1, 1), 7),
                        ('TOPPADDING', (0, 1), (-1, 1), 1), ('BOTTOMPADDING', (0, 0), (-1, 0), 0),
                    ]))
                cells.append(inner)
            outer = Table([cells], colWidths=[tile_w] * per_row, hAlign='LEFT')
            outer.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), gap),
                ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(outer)
        story.append(Spacer(1, 4))

    # Sections
    def section_flowables(section):
        items = []
        heading = section.get('heading')
        if section.get('flowable') is not None:
            if heading:
                items.append(Paragraph(_esc(heading), st['h2']))
            items.append(section['flowable'])
            items.append(Spacer(1, 4))
            return items

        headers = section['headers']
        rows = section.get('rows') or []
        right = set(section.get('right', ()))
        weights = section.get('widths') or [1] * len(headers)
        total_w = float(sum(weights))
        col_widths = [usable * w / total_w for w in weights]

        if heading:
            items.append(Paragraph(_esc(heading), st['h2']))
        if section.get('note'):
            items.append(Paragraph(_esc(section['note']), st['note']))
            items.append(Spacer(1, 3))

        data = [[Paragraph(_esc(h), st['head_right'] if i in right else st['head']) for i, h in enumerate(headers)]]
        if rows:
            for row in rows:
                data.append([Paragraph(_esc(c), st['cell_right'] if i in right else st['cell']) for i, c in enumerate(row)])
        else:
            empty = [Paragraph(_esc(section.get('empty', 'No records found.')), st['note'])] + [''] * (len(headers) - 1)
            data.append(empty)

        table = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), green),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor(GRID)),
            ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor(GRID)),
            ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(ZEBRA)]),
        ]
        if not rows:
            style.append(('SPAN', (0, 1), (-1, 1)))
        table.setStyle(TableStyle(style))
        items.append(table)
        items.append(Spacer(1, 6))
        return items

    for section in (sections or []):
        items = section_flowables(section)
        # 'then' = a table that must stay on the same page as its chart/heading.
        if section.get('then'):
            story.append(KeepTogether(items + section_flowables(section['then'])))
        elif section.get('flowable') is not None:
            story.append(KeepTogether(items))
        else:
            story.extend(items)

    doc.build(story, canvasmaker=_numbered_canvas_class(title))
    return response


# --------------------------------------------------------------------------
# Charts for the Analytics PDF
# --------------------------------------------------------------------------
CHART_COLORS = ['#16a34a', '#3b82f6', '#8b5cf6', '#f97316', '#ec4899', '#14b8a6', '#eab308', '#ef4444']


def _short(value, limit=14):
    value = str(value)
    return value if len(value) <= limit else value[:limit - 1] + '.'


def bar_chart(labels, series, width, height=170):
    """series: list of (name, [values]). Grouped vertical bars."""
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors

    drawing = Drawing(width, height)
    if not labels or not series:
        drawing.add(String(width / 2, height / 2, 'No data for this chart', textAnchor='middle', fontSize=9, fillColor=colors.HexColor(TEXT_MUTED)))
        return drawing
    chart = VerticalBarChart()
    chart.x, chart.y = 38, 34
    chart.width, chart.height = width - 60, height - 56
    chart.data = [list(map(float, values)) for _, values in series]
    chart.categoryAxis.categoryNames = [_short(l, 10) for l in labels]
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fontName = 'Helvetica'
    chart.valueAxis.labels.fontName = 'Helvetica'
    chart.categoryAxis.labels.angle = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.gridStrokeColor = colors.HexColor(GRID)
    chart.valueAxis.visibleGrid = True
    chart.barSpacing = 1
    chart.groupSpacing = 8
    for i in range(len(series)):
        chart.bars[i].fillColor = colors.HexColor(CHART_COLORS[i % len(CHART_COLORS)])
        chart.bars[i].strokeColor = None
    drawing.add(chart)
    legend = Legend()
    legend.x, legend.y = 40, height - 4
    legend.alignment = 'right'
    legend.fontSize = 7
    legend.fontName = 'Helvetica'
    legend.columnMaximum = 1
    legend.deltax = 70
    legend.dxTextSpace = 4
    legend.boxAnchor = 'nw'
    legend.colorNamePairs = [(colors.HexColor(CHART_COLORS[i % len(CHART_COLORS)]), _short(name, 16)) for i, (name, _) in enumerate(series)]
    drawing.add(legend)
    return drawing


def line_chart(labels, series, width, height=170, colors_map=None):
    """series: list of (name, [values]). Simple multi-line chart."""
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.lib import colors

    drawing = Drawing(width, height)
    if not labels or not series:
        drawing.add(String(width / 2, height / 2, 'No data for this chart', textAnchor='middle', fontSize=9, fillColor=colors.HexColor(TEXT_MUTED)))
        return drawing
    chart = LinePlot()
    chart.x, chart.y = 44, 34
    chart.width, chart.height = width - 66, height - 56
    chart.data = [[(i, float(v)) for i, v in enumerate(values)] for _, values in series]
    chart.xValueAxis.valueMin = 0
    chart.xValueAxis.valueMax = max(len(labels) - 1, 1)
    chart.xValueAxis.valueSteps = list(range(len(labels)))
    chart.xValueAxis.labelTextFormat = lambda v: _short(labels[int(v)], 9) if 0 <= int(v) < len(labels) else ''
    chart.xValueAxis.labels.fontSize = 7
    chart.xValueAxis.labels.fontName = 'Helvetica'
    chart.yValueAxis.labels.fontName = 'Helvetica'
    chart.yValueAxis.labels.fontSize = 7
    chart.yValueAxis.gridStrokeColor = colors.HexColor(GRID)
    chart.yValueAxis.visibleGrid = True
    palette = colors_map or CHART_COLORS
    for i in range(len(series)):
        chart.lines[i].strokeColor = colors.HexColor(palette[i % len(palette)])
        chart.lines[i].strokeWidth = 1.6
        chart.lines[i].symbol = makeMarker('FilledCircle', size=4, fillColor=colors.HexColor(palette[i % len(palette)]))
    drawing.add(chart)
    legend = Legend()
    legend.x, legend.y = 48, height - 4
    legend.alignment = 'right'
    legend.fontSize = 7
    legend.fontName = 'Helvetica'
    legend.columnMaximum = 1
    legend.deltax = 70
    legend.dxTextSpace = 4
    legend.boxAnchor = 'nw'
    legend.colorNamePairs = [(colors.HexColor(palette[i % len(palette)]), _short(name, 16)) for i, (name, _) in enumerate(series)]
    drawing.add(legend)
    return drawing


def pie_chart(labels, values, width, height=170):
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors

    drawing = Drawing(width, height)
    values = [float(v) for v in values]
    if not labels or not any(values):
        drawing.add(String(width / 2, height / 2, 'No data for this chart', textAnchor='middle', fontSize=9, fillColor=colors.HexColor(TEXT_MUTED)))
        return drawing
    pie = Pie()
    size = min(height - 20, 140)
    pie.x, pie.y = 20, (height - size) / 2
    pie.width = pie.height = size
    pie.data = values
    pie.labels = None
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    for i in range(len(values)):
        pie.slices[i].fillColor = colors.HexColor(CHART_COLORS[i % len(CHART_COLORS)])
    drawing.add(pie)
    total = sum(values) or 1
    legend = Legend()
    legend.x, legend.y = size + 50, height - 24
    legend.alignment = 'right'
    legend.fontSize = 8
    legend.fontName = 'Helvetica'
    legend.deltay = 12
    legend.dxTextSpace = 5
    legend.boxAnchor = 'nw'
    legend.colorNamePairs = [
        (colors.HexColor(CHART_COLORS[i % len(CHART_COLORS)]), f'{_short(l, 22)} ({v / total * 100:.1f}%)')
        for i, (l, v) in enumerate(zip(labels, values))
    ]
    drawing.add(legend)
    return drawing
