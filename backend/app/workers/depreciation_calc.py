"""Equipment depreciation calculation background tasks.

Ежемесячный расчёт амортизации оборудования
на основе срока службы и метода начисления.
"""

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.workers.depreciation_calc.calculate_monthly_depreciation")
def calculate_monthly_depreciation() -> dict:
    """Calculate monthly depreciation for all active equipment.

    Возвращает:
        Количество обработанных единиц оборудования.
    """
    logger.info("Calculating monthly depreciation")
    # TODO: fetch all active equipment, compute straight-line depreciation
    return {"processed_count": 0}
