"""PDF rendering for Bud test reports.

Everything visual lives here: the Bud logo, the pass/fail/skip pie chart, the
tables, and the "Powered by EmbedLabs" footer that is stamped on every page.
The API layer builds the numbers; this module only draws them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Optional, Sequence

from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets"
BUD_LOGO = ASSETS / "bud-logo.png"
# Optional: drop an EmbedLabs logo here and the footer picks it up automatically.
# Until then the footer shows the EmbedLabs wordmark, still linked.
EMBEDLABS_LOGO = ASSETS / "embedlabs-logo.png"

EMBEDLABS_URL = "https://www.embedlabs.net"

PASSED = colors.HexColor("#16a34a")
FAILED = colors.HexColor("#dc2626")
SKIPPED = colors.HexColor("#f59e0b")
INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d1d5db")

PAGE_MARGIN = 18 * mm
FOOTER_HEIGHT = 16 * mm


@dataclass
class Outcome:
    """Passed/failed/skipped counts for one row of a report."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total * 100, 1) if self.total else 0.0


@dataclass
class Breakdown:
    """A titled table of outcomes - per suite, per station, or per time bucket."""

    title: str
    label_heading: str
    rows: list[tuple[str, Outcome]] = field(default_factory=list)


@dataclass
class RunDetail:
    """The identity of a single run, for the per-run report."""

    run_id: int
    name: str
    status: str
    station: Optional[str] = None
    product: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    test_software_url: Optional[str] = None
    test_software_ref: Optional[str] = None
    software_under_test_url: Optional[str] = None
    software_under_test_ref: Optional[str] = None
    run_url: Optional[str] = None


@dataclass
class AssertionDetail:
    """One assertion recorded by one method in one test case."""

    test_class: str
    test_method: str
    index: int
    passed: Optional[bool]
    assertion_type: str = "Assertion"
    message: str = ""
    expected: object = None
    actual: object = None
    source: str = ""
    metadata: object = None
    traceback: str = ""


@dataclass
class ReportRequest:
    """Everything the renderer needs for one document."""

    title: str
    subtitle: str
    filters: list[tuple[str, str]]
    overall: Outcome
    breakdowns: list[Breakdown] = field(default_factory=list)
    run: Optional[RunDetail] = None
    assertions: list[AssertionDetail] = field(default_factory=list)
    generated_at: Optional[datetime] = None
    app_version: str = ""


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "BudTitle", parent=base["Title"], fontSize=20, leading=24, textColor=INK, alignment=0
        ),
        "subtitle": ParagraphStyle(
            "BudSubtitle", parent=base["Normal"], fontSize=10, leading=14, textColor=MUTED
        ),
        "h2": ParagraphStyle(
            "BudH2",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
            textColor=INK,
        ),
        "body": ParagraphStyle("BudBody", parent=base["Normal"], fontSize=9, leading=12),
        "link": ParagraphStyle(
            "BudLink",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2563eb"),
        ),
        "right": ParagraphStyle(
            "BudRight", parent=base["Normal"], fontSize=9, leading=12, alignment=TA_RIGHT
        ),
    }


def link(url: str, label: Optional[str] = None) -> str:
    """Markup for a clickable link inside a Paragraph."""
    text = label or url
    return f'<link href="{url}" color="#2563eb">{text}</link>'


class OutcomePie(Flowable):
    """Pass/fail/skip pie with a legend, or a note when there is nothing to plot."""

    def __init__(self, outcome: Outcome, width: float = 150 * mm, height: float = 55 * mm):
        super().__init__()
        self.outcome = outcome
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):  # noqa: N802 - reportlab API
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        drawing = Drawing(self.width, self.height)
        slices = [
            ("Passed", self.outcome.passed, PASSED),
            ("Failed", self.outcome.failed, FAILED),
            ("Skipped", self.outcome.skipped, SKIPPED),
        ]
        present = [(name, value, colour) for name, value, colour in slices if value > 0]

        if not present:
            drawing.add(
                String(
                    4,
                    self.height / 2,
                    "No test outcomes recorded for this selection.",
                    fontName="Helvetica-Oblique",
                    fontSize=10,
                    fillColor=MUTED,
                )
            )
            drawing.drawOn(self.canv, 0, 0)
            return

        pie = Pie()
        pie.x = 0
        pie.y = 2
        pie.width = self.height - 8
        pie.height = self.height - 8
        pie.data = [value for _, value, _ in present]
        pie.labels = None
        pie.sideLabels = False
        pie.slices.strokeWidth = 0.75
        pie.slices.strokeColor = colors.white
        for index, (_, _, colour) in enumerate(present):
            pie.slices[index].fillColor = colour
        drawing.add(pie)

        legend = Legend()
        legend.x = pie.width + 12
        legend.y = self.height - 10
        legend.alignment = "right"
        legend.fontName = "Helvetica"
        legend.fontSize = 9
        legend.dxTextSpace = 6
        legend.deltay = 13
        legend.columnMaximum = 3
        total = self.outcome.total
        legend.colorNamePairs = [
            (colour, f"{name}  {value}  ({round(value / total * 100, 1)}%)")
            for name, value, colour in present
        ]
        drawing.add(legend)
        drawing.drawOn(self.canv, 0, 0)


def _outcome_table(breakdown: Breakdown, styles: dict[str, ParagraphStyle]) -> Table:
    header = [breakdown.label_heading, "Total", "Passed", "Failed", "Skipped", "Pass rate"]
    data: list[Sequence[object]] = [header]
    for label, outcome in breakdown.rows:
        data.append(
            [
                Paragraph(label or "-", styles["body"]),
                str(outcome.total),
                str(outcome.passed),
                str(outcome.failed),
                str(outcome.skipped),
                f"{outcome.pass_rate}%",
            ]
        )
    if not breakdown.rows:
        data.append([Paragraph("Nothing recorded.", styles["body"]), "", "", "", "", ""])

    table = Table(data, colWidths=[None, 46, 46, 46, 46, 56], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _display(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _assertions_table(
    assertions: list[AssertionDetail], styles: dict[str, ParagraphStyle]
) -> Table:
    data: list[Sequence[object]] = [
        ["Test / method", "Assertion", "Outcome", "Expected", "Actual", "Evidence"]
    ]
    for assertion in assertions:
        if assertion.passed is True:
            outcome, colour = "Passed", "#16a34a"
        elif assertion.passed is False:
            outcome, colour = "Failed", "#dc2626"
        else:
            outcome, colour = "Skipped", "#f59e0b"

        evidence = []
        if assertion.message:
            evidence.append(escape(assertion.message))
        if assertion.source:
            evidence.append(f"<b>Source:</b> {escape(assertion.source)}")
        if assertion.metadata not in (None, {}, []):
            evidence.append(f"<b>Metadata:</b> {escape(_display(assertion.metadata))}")
        if assertion.traceback:
            evidence.append(f"<b>Trace:</b> {escape(assertion.traceback)}")

        data.append(
            [
                Paragraph(
                    f"<b>{escape(assertion.test_class)}</b><br/>{escape(assertion.test_method)}",
                    styles["body"],
                ),
                Paragraph(
                    f"#{assertion.index} {escape(assertion.assertion_type or 'Assertion')}",
                    styles["body"],
                ),
                Paragraph(f'<font color="{colour}">{outcome}</font>', styles["body"]),
                Paragraph(escape(_display(assertion.expected)), styles["body"]),
                Paragraph(escape(_display(assertion.actual)), styles["body"]),
                Paragraph("<br/>".join(evidence) or "-", styles["body"]),
            ]
        )
    if not assertions:
        data.append([Paragraph("No assertions recorded.", styles["body"]), "", "", "", "", ""])

    table = Table(
        data,
        colWidths=[34 * mm, 27 * mm, 17 * mm, 24 * mm, 24 * mm, None],
        repeatRows=1,
        hAlign="LEFT",
        # Evidence cells carry whole tracebacks, so a single row can be taller
        # than the frame. Without this reportlab refuses to place it at all.
        splitInRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _draw_footer(canvas, doc) -> None:
    """ "Powered by EmbedLabs" on every page, with the page number.

    The wordmark is a real PDF link annotation, so it is clickable in any
    viewer. The logo is drawn beside it when the asset is present.
    """
    canvas.saveState()
    width, _ = A4
    baseline = FOOTER_HEIGHT - 4 * mm

    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(PAGE_MARGIN, FOOTER_HEIGHT + 2 * mm, width - PAGE_MARGIN, FOOTER_HEIGHT + 2 * mm)

    text = "Powered by EmbedLabs"
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#2563eb"))

    x = PAGE_MARGIN
    if EMBEDLABS_LOGO.exists():
        logo_height = 6.5 * mm
        logo = ImageReader(str(EMBEDLABS_LOGO))
        iw, ih = logo.getSize()
        logo_width = logo_height * (iw / ih)
        # Sit the mark on the text's optical centre rather than its baseline.
        canvas.drawImage(
            logo,
            x,
            baseline - (logo_height - 8 * 0.72) / 2,
            width=logo_width,
            height=logo_height,
            mask="auto",
        )
        x += logo_width + 2.5 * mm

    canvas.drawString(x, baseline, text)
    text_width = canvas.stringWidth(text, "Helvetica", 8)
    canvas.linkURL(
        EMBEDLABS_URL,
        (PAGE_MARGIN, baseline - 2 * mm, x + text_width, baseline + 4 * mm),
        relative=0,
        thickness=0,
    )

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - PAGE_MARGIN, baseline, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _header(request: ReportRequest, styles: dict[str, ParagraphStyle]) -> list:
    generated = request.generated_at or datetime.utcnow()
    meta = [
        Paragraph(f"<b>{request.title}</b>", styles["title"]),
        Paragraph(request.subtitle, styles["subtitle"]),
        Paragraph(
            f"Generated {generated.strftime('%Y-%m-%d %H:%M')} UTC"
            + (f" &middot; Bud {request.app_version}" if request.app_version else ""),
            styles["subtitle"],
        ),
    ]

    if BUD_LOGO.exists():
        logo = ImageReader(str(BUD_LOGO))
        iw, ih = logo.getSize()
        logo_height = 14 * mm
        logo_width = logo_height * (iw / ih)
        from reportlab.platypus import Image as PlatypusImage

        # mask="auto" honours the logo's alpha channel; without it the artwork
        # is composited onto an opaque box.
        banner = Table(
            [
                [
                    meta,
                    PlatypusImage(str(BUD_LOGO), width=logo_width, height=logo_height, mask="auto"),
                ]
            ],
            colWidths=[None, logo_width + 4],
            hAlign="LEFT",
        )
        banner.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [banner]
    return meta


def _run_facts(run: RunDetail, styles: dict[str, ParagraphStyle]) -> Table:
    def value(text: Optional[str]) -> Paragraph:
        return Paragraph(text or "-", styles["body"])

    def repo(url: Optional[str], ref: Optional[str]) -> Paragraph:
        if not url:
            return Paragraph("-", styles["body"])
        label = f"{url} @ {ref}" if ref else url
        return Paragraph(link(url, label), styles["body"])

    rows = [
        ["Run ID", value(f"BUD-RUN-{run.run_id}")],
        ["Suite", value(run.name)],
        ["Status", value(run.status)],
        ["Test Station", value(run.station)],
        ["Product", value(run.product)],
        [
            "Started",
            value(run.started_at.strftime("%Y-%m-%d %H:%M UTC") if run.started_at else None),
        ],
        [
            "Completed",
            value(run.completed_at.strftime("%Y-%m-%d %H:%M UTC") if run.completed_at else None),
        ],
        [
            "Duration",
            value(f"{run.duration_seconds:.1f}s" if run.duration_seconds is not None else None),
        ],
        ["Test software", repo(run.test_software_url, run.test_software_ref)],
        ["Software under test", repo(run.software_under_test_url, run.software_under_test_ref)],
    ]
    if run.run_url:
        rows.append(["Open in Bud", Paragraph(link(run.run_url), styles["body"])])

    table = Table(rows, colWidths=[38 * mm, None], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
            ]
        )
    )
    return table


def render_report(request: ReportRequest) -> bytes:
    """Render a report to PDF bytes."""
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=FOOTER_HEIGHT + 6 * mm,
        title=request.title,
        author="Bud TMP by EmbedLabs",
        subject=request.subtitle,
    )

    story: list = []
    story.extend(_header(request, styles))
    story.append(Spacer(1, 6 * mm))

    if request.filters:
        applied = "  &middot;  ".join(f"<b>{name}:</b> {value}" for name, value in request.filters)
        story.append(Paragraph(applied, styles["body"]))
        story.append(Spacer(1, 4 * mm))

    if request.run:
        story.append(Paragraph("Run", styles["h2"]))
        story.append(_run_facts(request.run, styles))
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Outcomes", styles["h2"]))
    story.append(
        Paragraph(
            f"{request.overall.total} assertions &middot; "
            f"{request.overall.passed} passed &middot; "
            f"{request.overall.failed} failed &middot; "
            f"{request.overall.skipped} skipped &middot; "
            f"pass rate {request.overall.pass_rate}%",
            styles["body"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(OutcomePie(request.overall))

    for breakdown in request.breakdowns:
        story.append(
            KeepTogether(
                [
                    Paragraph(breakdown.title, styles["h2"]),
                    _outcome_table(breakdown, styles),
                ]
            )
        )

    if request.run is not None:
        story.append(PageBreak())
        story.append(Paragraph("Assertion evidence", styles["h2"]))
        story.append(_assertions_table(request.assertions, styles))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()
