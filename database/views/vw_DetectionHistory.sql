DROP VIEW IF EXISTS vw_DetectionHistory;

CREATE VIEW vw_DetectionHistory AS

SELECT

    h.DetectionID,
    h.RunID,

    h.KM_Number,

    c.Name,
    c.Zone,
    c.Category,

    h.DetectionTime,

    h.DetectionStatus,
    h.LeakType,

    h.PriorityScore,

    h.HistoricalNightFloor,
    h.RecentNightFloor,
    h.NightTroughRatio,

    h.MK_PValue,
    h.MK_SenSlope,
    h.PeakZScore,

    h.Evidence,

    h.EstimatedWaterLoss,
    h.EstimatedRevenueLoss,

    h.Recommendation

FROM DetectionHistory h

JOIN Customers c
ON h.KM_Number = c.KM_Number;