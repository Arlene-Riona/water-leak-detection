-- ============================================================================
-- Water Leakage Detection Decision Support System
-- Database Schema v1.0
--
-- Author : Arlene
-- Purpose: SQLite database schema for storing customer information,
--          hourly consumption data, leak detection results,
--          technician feedback, and algorithm execution history.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: Customers
-- ============================================================================

CREATE TABLE IF NOT EXISTS Customers (
    KM_Number               TEXT PRIMARY KEY,
    Name                    TEXT NOT NULL,
    Zone                    TEXT NOT NULL,
    Category                TEXT NOT NULL,

    EstimatedRevenueQAR     REAL,
    PeakDemandM3            REAL,
    TotalConsumptionM3      REAL,

    CreatedAt               DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: HourlyConsumption
-- ============================================================================

CREATE TABLE IF NOT EXISTS HourlyConsumption (

    ReadingID               INTEGER PRIMARY KEY AUTOINCREMENT,

    KM_Number               TEXT NOT NULL,

    Timestamp               DATETIME NOT NULL,

    ConsumptionM3           REAL NOT NULL,

    FOREIGN KEY (KM_Number)
        REFERENCES Customers(KM_Number)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: DetectionResults
--
-- Current state of every customer.
-- Exactly ONE row per customer.
-- Optimized for dashboards and reporting.
-- ============================================================================

CREATE TABLE IF NOT EXISTS DetectionResults (

    KM_Number               TEXT PRIMARY KEY,

    DetectionStatus         TEXT NOT NULL,

    LeakType                TEXT,

    PriorityScore           REAL,

    PriorityLevel           TEXT,

    HistoricalNightFloor    REAL,

    RecentNightFloor        REAL,

    NightTroughRatio        REAL,

    MK_PValue               REAL,

    MK_SenSlope             REAL,

    PeakZScore              REAL,

    Evidence                TEXT,

    DataCompleteness        REAL,

    EstimatedWaterLoss      REAL,

    EstimatedRevenueLoss    REAL,

    Recommendation          TEXT,

    AISummary               TEXT,

    FirstDetected           DATETIME,

    LastDetected            DATETIME,

    LastUpdated             DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (KM_Number)
        REFERENCES Customers(KM_Number)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: AlgorithmRuns
--
-- One record every time the detection engine executes.
-- ============================================================================

CREATE TABLE IF NOT EXISTS AlgorithmRuns (

    RunID                   INTEGER PRIMARY KEY AUTOINCREMENT,

    RunTimestamp            DATETIME DEFAULT CURRENT_TIMESTAMP,

    CustomersProcessed      INTEGER,

    LeaksDetected           INTEGER,

    RuntimeSeconds          REAL,

    Status                  TEXT,

    ErrorMessage            TEXT
);

-- ============================================================================
-- TABLE: DetectionHistory
--
-- Historical snapshot of every algorithm execution.
-- ============================================================================

CREATE TABLE IF NOT EXISTS DetectionHistory (

    DetectionID             INTEGER PRIMARY KEY AUTOINCREMENT,

    RunID                   INTEGER NOT NULL,

    KM_Number               TEXT NOT NULL,

    DetectionTime           DATETIME DEFAULT CURRENT_TIMESTAMP,

    DetectionStatus         TEXT,

    LeakType                TEXT,

    PriorityScore           REAL,

    HistoricalNightFloor    REAL,

    RecentNightFloor        REAL,

    NightTroughRatio        REAL,

    MK_PValue               REAL,

    MK_SenSlope             REAL,

    PeakZScore              REAL,

    Evidence                TEXT,

    EstimatedWaterLoss      REAL,

    EstimatedRevenueLoss    REAL,

    Recommendation          TEXT,

    FOREIGN KEY (KM_Number)
        REFERENCES Customers(KM_Number)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (RunID)
        REFERENCES AlgorithmRuns(RunID)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: TechnicianFeedback
--
-- Human validation of detections.
-- Used for future ML training.
-- ============================================================================

CREATE TABLE IF NOT EXISTS TechnicianFeedback (

    FeedbackID              INTEGER PRIMARY KEY AUTOINCREMENT,

    DetectionID             INTEGER NOT NULL,

    KM_Number               TEXT NOT NULL,

    Validation              TEXT,

    RootCause               TEXT,

    Notes                   TEXT,

    TechnicianName          TEXT,

    VisitDate               DATETIME,

    ResolutionDate          DATETIME,

    FOREIGN KEY (DetectionID)
        REFERENCES DetectionHistory(DetectionID)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (KM_Number)
        REFERENCES Customers(KM_Number)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_hourly_customer_time
ON HourlyConsumption(KM_Number, Timestamp);

CREATE INDEX IF NOT EXISTS idx_detectionhistory_customer
ON DetectionHistory(KM_Number);

CREATE INDEX IF NOT EXISTS idx_detectionhistory_run
ON DetectionHistory(RunID);

CREATE INDEX IF NOT EXISTS idx_detectionresults_status
ON DetectionResults(DetectionStatus);

CREATE INDEX IF NOT EXISTS idx_detectionresults_priority
ON DetectionResults(PriorityScore);

CREATE INDEX IF NOT EXISTS idx_feedback_detection
ON TechnicianFeedback(DetectionID);

CREATE INDEX IF NOT EXISTS idx_customer_category
ON Customers(Category);