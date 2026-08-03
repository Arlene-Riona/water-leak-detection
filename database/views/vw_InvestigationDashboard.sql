DROP VIEW IF EXISTS vw_InvestigationDashboard;

CREATE VIEW vw_InvestigationDashboard AS

SELECT

    c.KM_Number,
    c.Name,
    c.Zone,
    c.Category,

    d.DetectionStatus,
    d.LeakType,

    d.PriorityScore,
    d.PriorityLevel,

    d.HistoricalNightFloor,
    d.RecentNightFloor,
    d.NightTroughRatio,

    d.MK_PValue,
    d.MK_SenSlope,
    d.PeakZScore,

    d.Evidence,

    d.EstimatedWaterLoss,
    d.EstimatedRevenueLoss,

    d.Recommendation,

    d.FirstDetected,
    d.LastDetected

FROM Customers c

JOIN DetectionResults d
ON c.KM_Number = d.KM_Number;