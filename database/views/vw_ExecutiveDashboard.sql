DROP VIEW IF EXISTS vw_ExecutiveDashboard;

CREATE VIEW vw_ExecutiveDashboard AS

SELECT

    c.KM_Number,
    c.Name,
    c.Zone,
    c.Category,

    d.DetectionStatus,
    d.LeakType,
    d.PriorityScore,
    d.PriorityLevel,

    d.EstimatedWaterLoss,
    d.EstimatedRevenueLoss,

    d.DataCompleteness,

    d.FirstDetected,
    d.LastDetected,
    d.LastUpdated

FROM Customers c

LEFT JOIN DetectionResults d
ON c.KM_Number = d.KM_Number;