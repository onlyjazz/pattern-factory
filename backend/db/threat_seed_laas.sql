BEGIN;

-- =========================================================
-- 1. Global pattern (public schema)
-- =========================================================

WITH pattern_ins AS (
    INSERT INTO public.patterns (name, description, kind, content_source)
    VALUES (
        'FDA Cyber compliance',
        'Cybersecurity controls and risk management expectations for FDA-regulated laboratory and medical systems.',
        'pattern',
        'seed'
    )
    RETURNING id
),

-- =========================================================
-- 2. Project
-- =========================================================

project_ins AS (
    INSERT INTO threat.projects (
        name,
        description
    )
    VALUES (
        'Lab as a Service',
        'Remote-controlled incubator platform enabling pharma users to run automated cell culture experiments.'
    )
    RETURNING id
),

-- =========================================================
-- 3. Assets
-- =========================================================

asset_ins AS (
    INSERT INTO threat.assets (
        project_id,
        name,
        description,
        fixed_value,
        fixed_value_period,
        recurring_value,
        include_fixed_value,
        include_recurring_value,
        disabled
    )
    SELECT
        p.id,
        a.name,
        a.description,
        500000,        -- placeholder valuation
        12,
        0,
        TRUE,
        FALSE,
        FALSE
    FROM project_ins p
    CROSS JOIN (
        VALUES
        ('Cell Culture Integrity',
         'Viability, sterility, and correctness of incubated cell cultures.'),
        ('Remote Control & Automation System',
         'Software and control logic enabling remote execution and monitoring.'),
        ('Experimental & Operational Data',
         'Sensor data, experiment metadata, logs, and predictive insights.')
    ) AS a(name, description)
    RETURNING id
),

-- =========================================================
-- 4. Threats
-- =========================================================

threat_ins AS (
    INSERT INTO threat.threats (
        project_id,
        name,
        description,
        probability,
        damage_description,
        spoofing,
        tampering,
        repudiation,
        information_disclosure,
        denial_of_service,
        elevation_of_privilege,
        mitigation_level,
        disabled
    )
    SELECT
        p.id,
        t.name,
        t.description,
        3,
        t.damage,
        t.spoofing,
        t.tampering,
        t.repudiation,
        t.info_disc,
        t.dos,
        t.eop,
        0,
        FALSE
    FROM project_ins p
    CROSS JOIN (
        VALUES
        (
            'Unauthorized Remote Control',
            'An attacker gains unauthorized access to the incubator control interface.',
            'Silent experiment corruption and large-scale experiment loss.',
            TRUE, TRUE, FALSE, FALSE, FALSE, TRUE
        ),
        (
            'Data Manipulation or Integrity Loss',
            'Sensor readings or experiment data are altered or falsified.',
            'Invalid scientific conclusions and regulatory exposure.',
            FALSE, TRUE, TRUE, TRUE, FALSE, FALSE
        ),
        (
            'Service Disruption During Active Experiments',
            'Loss of availability during active incubation runs.',
            'Experiment failure and loss of biological material.',
            FALSE, FALSE, FALSE, FALSE, TRUE, FALSE
        )
    ) AS t(
        name,
        description,
        damage,
        spoofing,
        tampering,
        repudiation,
        info_disc,
        dos,
        eop
    )
    RETURNING id
),

-- =========================================================
-- 5. Vulnerabilities
-- =========================================================

vuln_ins AS (
    INSERT INTO threat.vulnerabilities (
        project_id,
        name,
        description,
        disabled
    )
    SELECT
        p.id,
        v.name,
        v.description,
        FALSE
    FROM project_ins p
    CROSS JOIN (
        VALUES
        ('Weak Authentication',
         'Single-factor or poorly enforced authentication for remote access.'),
        ('No Control/Data Plane Segmentation',
         'Control logic and data systems share the same trust boundary.'),
        ('Unvalidated Control Commands',
         'Control commands are accepted without bounds or sanity checks.'),
        ('Insufficient Audit Logging',
         'Actions are not fully logged with actor and timestamp.'),
        ('Network Dependency',
         'System behavior degrades or fails on network loss.')
    ) AS v(name, description)
    RETURNING id
),

-- =========================================================
-- 6. Countermeasures
-- =========================================================

cm_ins AS (
    INSERT INTO threat.countermeasures (
        project_id,
        name,
        description,
        fixed_implementation_cost,
        fixed_cost_period,
        recurring_implementation_cost,
        detailed_design,
        implemented,
        include_fixed_cost,
        include_recurring_cost,
        disabled
    )
    SELECT
        p.id,
        c.name,
        c.description,
        25000,
        12,
        5000,
        NULL,
        FALSE,
        TRUE,
        TRUE,
        FALSE
    FROM project_ins p
    CROSS JOIN (
        VALUES
        ('Strong Authentication & RBAC',
         'Multi-factor authentication and role-based access control.'),
        ('Command Validation Guardrails',
         'Hard safety limits and validation of control commands.'),
        ('Immutable Audit Logging',
         'Append-only logs for control actions and configuration changes.'),
        ('Control/Data Plane Separation',
         'Isolation of control APIs from data ingestion and analytics.'),
        ('Local Fail-Safe Mode',
         'Autonomous safe operation during network outages.'),
        ('Sensor Data Integrity Checks',
         'Consistency and anomaly detection for sensor data.'),
        ('Continuous Monitoring & Alerting',
         'Detection of abnormal access patterns and system behavior.')
    ) AS c(name, description)
    RETURNING id
)

-- =========================================================
-- 7. Link threats to global pattern
-- =========================================================

INSERT INTO threat.pattern_threat (
    project_id,
    pattern_id,
    threat_id
)
SELECT
    p.id,
    pat.id,
    t.id
FROM project_ins p
CROSS JOIN pattern_ins pat
CROSS JOIN threat_ins t;

COMMIT;
