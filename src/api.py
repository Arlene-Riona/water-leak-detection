"""
FastAPI backend for the Water Leakage Detection Decision Support System.

Provides web endpoints for technician feedback and other future
dashboard interactions.

Author: Arlene
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.database import get_connection

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title="Water Leakage Detection API",
    description="Backend API for the Water Leakage Detection Decision Support System.",
    version="1.0.0",
)

app.mount(
    "/web",
    StaticFiles(directory=WEB_DIR),
    name="web"
)

# ============================================================================
# REQUEST MODEL
# ============================================================================

class TechnicianFeedback(BaseModel):
    DetectionID: int
    KM_Number: str
    Validation: str
    RootCause: str
    Notes: str | None = None


# ============================================================================
# BASIC ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    return {
        "status": "running",
        "message": "Water Leakage Detection API is running."
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.get("/technician-feedback")
def technician_feedback_page():
    return FileResponse(
        WEB_DIR / "technician_feedback.html"
    )


# ============================================================================
# TECHNICIAN FEEDBACK
# ============================================================================

@app.post("/technician-feedback")
def submit_technician_feedback(feedback: TechnicianFeedback):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO TechnicianFeedback (
                DetectionID,
                KM_Number,
                Validation,
                RootCause,
                Notes,
                VisitDate
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                feedback.DetectionID,
                feedback.KM_Number,
                feedback.Validation,
                feedback.RootCause,
                feedback.Notes,
            )
        )

        connection.commit()

        feedback_id = cursor.lastrowid

        return {
            "status": "success",
            "message": "Technician feedback recorded successfully.",
            "FeedbackID": feedback_id
        }

    except Exception as e:

        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save technician feedback: {str(e)}"
        )

    finally:
        connection.close()