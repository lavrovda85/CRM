#!/usr/bin/env python3
"""Build SPEC CRM PDF presentation from text + images in this directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

HERE = Path(__file__).resolve().parent
OUT_PDF = HERE / "SPEC_CRM_presentation.pdf"

# Windows Cyrillic-capable font
_FONT_CANDIDATES = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "calibri.ttf",
]


def _register_font() -> str:
    for p in _FONT_CANDIDATES:
        if p.is_file():
            name = "SpecCRMFont"
            pdfmetrics.registerFont(TTFont(name, str(p)))
            return name
    print("ERROR: No Arial/Calibri found — install Windows fonts or set FONT_PATH", file=sys.stderr)
    sys.exit(1)


def _styles(font: str):
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleRU",
        parent=base["Heading1"],
        fontName=font,
        fontSize=26,
        textColor=colors.HexColor("#1e1b4b"),
        alignment=TA_CENTER,
        spaceAfter=18,
    )
    h2 = ParagraphStyle(
        "H2RU",
        parent=base["Heading2"],
        fontName=font,
        fontSize=16,
        textColor=colors.HexColor("#312e81"),
        spaceBefore=14,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "BodyRU",
        parent=base["Normal"],
        fontName=font,
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    bullet = ParagraphStyle(
        "BulletRU",
        parent=body,
        leftIndent=18,
        bulletIndent=8,
    )
    cap = ParagraphStyle(
        "CaptionRU",
        parent=base["Normal"],
        fontName=font,
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    return title, h2, body, bullet, cap


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _img_flow(path: Path, max_w_cm: float = 16.5, max_h_cm: float = 11.0) -> Image:
    """Scale image to fit page width."""
    pil = PILImage.open(path)
    w, h = pil.size
    max_w = max_w_cm * cm
    max_h = max_h_cm * cm
    ratio = min(max_w / w, max_h / h)
    nw, nh = w * ratio, h * ratio
    return Image(str(path), width=nw, height=nh)


def main() -> None:
    font = _register_font()
    title_s, h2_s, body_s, bullet_s, cap_s = _styles(font)

    images = sorted(HERE.glob("photo_*.jpg")) + sorted(HERE.glob("photo_*.png"))
    if not images:
        print("No photo_*.jpg/png in", HERE, file=sys.stderr)
        sys.exit(1)

    # Caption order aligned with sorted filenames (chronological by date in name)
    captions = [
        "Главная панель: активные задачи и тендеры",
        "Задачи: канбан-доска",
        "Задачи: календарь по исполнителям",
        "Карточка задачи",
        "Планировщик правил (автозадачи)",
        "Задачи: месячный календарь",
        "Мобильный вид задач",
        "ИИ-ассистент: текст, голос, вложения",
        "ИИ: ведомость из Excel — массовое создание задач",
        "ИИ: поиск тендера на zakupki и импорт в CRM",
        "Тендер: риски и рентабельность (анализ документов)",
        "Тендер: индикативный сметный расчёт по ведомости",
    ]
    while len(captions) < len(images):
        captions.append("Интерфейс SPEC CRM")
    captions = captions[: len(images)]

    story: list = []

    story.append(Paragraph(_esc("SPEC CRM"), title_s))
    story.append(Paragraph(_esc("Короткая презентация продукта"), ParagraphStyle("sub", parent=title_s, fontSize=14)))
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph(_esc("Что это"), h2_s))
    story.append(
        Paragraph(
            _esc(
                "SPEC CRM — единая платформа для тендерных команд и операционного управления: "
                "от поиска и разбора закупок до задач, документов, сметной оценки и ИИ-помощника."
            ),
            body_s,
        )
    )

    story.append(Paragraph(_esc("Зачем"), h2_s))
    story.append(
        Paragraph(
            _esc(
                "Тендеры размазаны по Excel, почте, ЕИС и мессенджерам; сроки и риски теряются, "
                "ведомость и смета не связаны с задачами. SPEC CRM собирает цепочку в одном месте "
                "и не даёт забыть критические шаги до торгов."
            ),
            body_s,
        )
    )

    story.append(Paragraph(_esc("Как помогает"), h2_s))
    bullets = [
        "Тендеры — карточка закупки, статусы по пайплайну, чеклисты с привязкой к датам торгов, ссылка на zakupki, импорт документов с площадки.",
        "Анализ документов — фоновый разбор PDF/DOCX/XLSX и архивов (ZIP/7Z/RAR): риски, рентабельность, ведомость работ; прозрачно видно, что ушло в модель.",
        "Ведомость — правка в интерфейсе, сохранение в карточке, задачи по строкам, задача сметчику с выгрузкой CSV, индикативный «сметный» расчёт и ориентир по нижней границе цены (в связке с опциональным контекстом цен и ИИ).",
        "Задачи и процессы — привычные задачи, шаблоны, чек-листы, уведомления, интеграция с тендером.",
        "ИИ-ассистент — те же сценарии, что и через MCP: поиск тендеров, импорт по ссылке, задачи из таблиц и переписки, без ручного копирования UUID.",
    ]
    for b in bullets:
        story.append(Paragraph(_esc(f"• {b}"), bullet_s))

    story.append(Paragraph(_esc("Для кого"), h2_s))
    story.append(
        Paragraph(
            _esc(
                "Компании в сфере поставок и монтажа (в т.ч. инженерные системы), где важны сроки подачи, "
                "документация и согласование сметчика с реальностью тендера."
            ),
            body_s,
        )
    )

    story.append(Paragraph(_esc("Итог"), h2_s))
    story.append(
        Paragraph(
            _esc(
                "SPEC CRM — не «ещё одна воронка», а операционная оболочка вокруг тендера: "
                "документы → анализ → ведомость → оценка → задачи — с ИИ там, где это ускоряет работу, "
                "и с понятными ограничениями там, где нужна ответственность человека (смета, торги, договор)."
            ),
            body_s,
        )
    )

    story.append(PageBreak())
    story.append(Paragraph(_esc("Скриншоты интерфейса"), h2_s))
    story.append(Spacer(1, 0.3 * cm))

    for img_path, cap in zip(images, captions):
        try:
            story.append(_img_flow(img_path))
        except Exception as exc:
            story.append(Paragraph(_esc(f"(не удалось вставить {img_path.name}: {exc})"), cap_s))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(_esc(cap), cap_s))
        story.append(Spacer(1, 0.4 * cm))

    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="SPEC CRM — презентация",
        author="SPEC CRM",
    )
    doc.build(story)
    print("Written:", OUT_PDF)


if __name__ == "__main__":
    main()
