import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import DriftReport, ReferenceDistribution, get_db
from ..detector import run_full_drift_check
from ..main import DRIFT_ALERTS_TOTAL, DRIFT_SCORE_GAUGE
from ..schemas import DriftCheckRequest, DriftReportResponse

router = APIRouter()

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://scheduler:8005")


@router.post("/check", response_model=list[DriftReportResponse], status_code=201)
async def check_drift(body: DriftCheckRequest, db: AsyncSession = Depends(get_db)):
    """Run KS + PSI drift check for a feature against stored reference distribution."""
    ref_result = await db.execute(
        select(ReferenceDistribution).where(
            and_(
                ReferenceDistribution.model_name == body.model_name,
                ReferenceDistribution.version == body.version,
                ReferenceDistribution.feature_name == body.feature_name,
            )
        )
    )
    ref = ref_result.scalar_one_or_none()
    if not ref:
        raise HTTPException(
            404,
            f"No reference distribution for {body.model_name} v{body.version} "
            f"feature '{body.feature_name}'. Upload one first via POST /reference/",
        )

    result = run_full_drift_check(
        reference=ref.samples,
        current=body.current_samples,
        bin_edges=ref.bin_edges,
        ks_threshold=body.ks_threshold,
        psi_threshold=body.psi_threshold,
    )

    reports = []
    for test_type, res in [("ks", result["ks"]), ("psi", result["psi"])]:
        report = DriftReport(
            model_name=body.model_name,
            version=body.version,
            feature_name=body.feature_name,
            test_type=test_type,
            statistic=res.get("statistic", 0.0),
            p_value=res.get("p_value"),
            psi_score=res.get("psi_score"),
            drift_detected=res["drift_detected"],
            threshold=res["threshold"],
            sample_size=result["sample_size"],
        )
        db.add(report)
        reports.append(report)

        # Update Prometheus gauge
        score = (
            res.get("psi_score") if test_type == "psi" else res.get("statistic", 0.0)
        )
        DRIFT_SCORE_GAUGE.labels(
            model_name=body.model_name,
            feature_name=body.feature_name,
            test_type=test_type,
        ).set(score)

        if res["drift_detected"]:
            DRIFT_ALERTS_TOTAL.labels(
                model_name=body.model_name,
                feature_name=body.feature_name,
            ).inc()

    await db.commit()
    for r in reports:
        await db.refresh(r)

    # Notify scheduler to trigger retraining if drift detected
    if result["drift_detected"]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{SCHEDULER_URL}/jobs/trigger",
                    json={
                        "model_name": body.model_name,
                        "trigger_type": "drift",
                        "metadata": {
                            "feature_name": body.feature_name,
                            "ks_drift": result["ks"]["drift_detected"],
                            "psi_drift": result["psi"]["drift_detected"],
                        },
                    },
                )
        except Exception:
            pass  # Scheduler unavailable - report is still saved

    return reports


@router.get("/reports", response_model=list[DriftReportResponse])
async def list_drift_reports(
    model_name: str | None = None,
    feature_name: str | None = None,
    drift_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    q = select(DriftReport)
    if model_name:
        q = q.where(DriftReport.model_name == model_name)
    if feature_name:
        q = q.where(DriftReport.feature_name == feature_name)
    if drift_only:
        q = q.where(DriftReport.drift_detected == True)
    result = await db.execute(q.order_by(DriftReport.reported_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/reports/summary")
async def drift_summary(model_name: str, db: AsyncSession = Depends(get_db)):
    """Returns a per-feature drift summary for a model."""
    result = await db.execute(
        select(DriftReport)
        .where(DriftReport.model_name == model_name)
        .order_by(DriftReport.reported_at.desc())
        .limit(500)
    )
    rows = result.scalars().all()

    # Latest result per feature+test_type
    seen = {}
    for r in rows:
        key = (r.feature_name, r.test_type)
        if key not in seen:
            seen[key] = r

    return [
        {
            "feature_name": r.feature_name,
            "test_type": r.test_type,
            "statistic": r.statistic,
            "drift_detected": r.drift_detected,
            "reported_at": r.reported_at,
        }
        for r in seen.values()
    ]
