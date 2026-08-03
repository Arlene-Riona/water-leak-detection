# Backend Architecture

## Overview

The backend of the Water Leakage Detection Decision Support System is responsible for managing the complete data processing pipeline, from importing customer information and hourly consumption datasets to executing the leak detection algorithm and storing the results for visualization and future analysis.

The backend follows a modular architecture where each component has a single responsibility. This design improves maintainability, makes testing easier, and allows future enhancements without modifying existing components.

The overall workflow is:

```
Customer Master
        │
        ▼
Customers Table

Hourly Consumption Files
        │
        ▼
HourlyConsumption Table

        │
        ▼
run_detection.py
        │
        ▼
Leak Detection Engine
        │
        ▼
DetectionResults
        │
        ├────────► DetectionHistory
        │
        └────────► AlgorithmRuns
```

---

# Backend Components

## Customer Import

The customer import module loads the customer master spreadsheet into the SQLite database.

Responsibilities include:

* Reading the customer master Excel file.
* Validating customer information.
* Removing non-data rows such as filter summaries.
* Ensuring customer identifiers are unique.
* Replacing the Customers table with the latest customer information.

The customer master is considered the source of truth for all registered customers.

The imported information includes:

* KM Number
* Customer Name
* Zone
* Customer Category
* Estimated Revenue
* Peak Demand
* Total Consumption

---

## Consumption Import

The consumption import module imports hourly water consumption data into the database.

Responsibilities include:

* Scanning the consumption dataset folder.
* Detecting the correct header row automatically.
* Reading Excel or CSV files.
* Extracting the customer KM Number from the filename.
* Validating timestamps and consumption values.
* Importing all hourly readings into SQLite.

Each imported record contains:

* Customer KM Number
* Timestamp
* Hourly Consumption (m³)

All hourly measurements are stored in the HourlyConsumption table.

---

# Database Design

The backend uses SQLite as its storage engine.

The database consists of six primary tables.

## Customers

Stores the customer master information.

This table acts as the reference table for every other component in the system.

Primary Key:

* KM_Number

---

## HourlyConsumption

Stores every imported hourly consumption measurement.

Each row represents a single hourly reading.

Foreign Key:

* KM_Number → Customers

---

## DetectionResults

Stores the latest leak detection result for every customer.

Only one row exists per customer.

Whenever the pipeline executes, the previous record is replaced with the newest analysis.

This table is optimized for dashboards and operational reporting.

Typical information includes:

* Detection Status
* Leak Type
* Priority Score
* Estimated Water Loss
* Estimated Revenue Loss
* Recommendation
* AI Summary

---

## DetectionHistory

Stores a permanent historical record of every detection performed.

Unlike DetectionResults, this table never replaces existing records.

Each execution of the detection pipeline inserts a new snapshot.

This allows historical analysis such as:

* Leak progression
* Detection trends
* Customer history
* Algorithm performance over time

DetectionHistory references the corresponding pipeline execution through the RunID foreign key.

---

## AlgorithmRuns

Stores metadata for every execution of the detection pipeline.

Each pipeline execution creates one record containing:

* Execution timestamp
* Number of processed customers
* Number of detected leaks
* Runtime
* Execution status
* Error messages (if any)

This table acts as an audit log for the entire system.

---

## TechnicianFeedback

Stores field validation after technicians investigate suspected leaks.

This table is not currently used by the detection engine but has been designed for future improvements.

Potential future uses include:

* Model validation
* Supervised machine learning
* Detection accuracy evaluation
* Continuous algorithm improvement

---

# Leak Detection Engine

The backend intentionally separates the leak detection algorithm from the surrounding infrastructure.

The production detection algorithm remains completely independent from:

* SQLite
* Database queries
* File management
* Pipeline orchestration

Instead, the backend communicates with the algorithm through a lightweight wrapper.

This design preserves the original detection engine while allowing different data sources to be connected without modifying the validated algorithm.

---

# Detection Pipeline

The central orchestration script is:

```
run_detection.py
```

This script coordinates the complete backend workflow.

For every customer stored in the database, the pipeline performs the following steps:

1. Retrieve the customer information.
2. Load hourly consumption data from SQLite.
3. Execute the leak detection wrapper.
4. Update the latest customer result.
5. Append the historical detection record.
6. Continue to the next customer.
7. Update the AlgorithmRuns table once processing is complete.

This design allows the entire customer portfolio to be processed using a single command.

---

# Separation of Responsibilities

The backend follows a layered architecture.

```
Excel Files
      │
      ▼
Import Scripts
      │
      ▼
SQLite Database
      │
      ▼
Pipeline Wrapper
      │
      ▼
Leak Detection Engine
      │
      ▼
Detection Results
```

Each layer has a clearly defined responsibility.

### Import Scripts

Responsible only for reading external files and importing data.

### Database Layer

Responsible only for storing and retrieving information.

### Pipeline

Responsible only for orchestrating execution.

### Detection Wrapper

Responsible only for translating database data into the format expected by the detection engine.

### Leak Detection Engine

Responsible only for leak analysis.

Because each layer is independent, future modifications can be made with minimal impact on the remaining system.

---

# Design Principles

Several software engineering principles were followed during development.

## Separation of Concerns

Each module performs one clearly defined task.

## Modular Design

Components can be modified independently.

## Reusability

Database importers, detection wrappers, and pipeline components can be reused in future projects.

## Maintainability

Changes to one module have minimal impact on other modules.

## Extensibility

Future functionality such as machine learning, APIs, web dashboards, notifications, or cloud deployment can be integrated without redesigning the existing backend.

---

# Current Backend Status

The backend currently supports:

* Customer master management
* Automated consumption import
* SQLite database storage
* End-to-end leak detection execution
* Current detection storage
* Historical detection tracking
* Algorithm execution logging
* Technician feedback storage
* Production-ready modular architecture

The backend now serves as the data processing foundation for future visualization dashboards, reporting systems, web applications, and intelligent decision-support features.
