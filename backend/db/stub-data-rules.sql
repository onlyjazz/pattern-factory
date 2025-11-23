INSERT INTO rules (name, description, rule_code, sql) VALUES
(
  'Patterns in Episodes',
  'Show patterns that appear in podcast episodes with their type and episode links.',
  'PATTERN_IN_EPISODE',
  $$SELECT 
      p.id AS pattern_id,
      p.name AS pattern_name,
      p.kind,
      e.id AS episode_id,
      e.title AS episode_title,
      e.youtube_url
    FROM patterns p
    JOIN episodes_patterns ep ON ep.pattern_id = p.id
    JOIN episodes e ON e.id = ep.episode_id
    ORDER BY e.id, p.name;$$
),

(
  'Patterns by Guest',
  'List all patterns associated with each guest and where those patterns appear.',
  'PATTERNS_BY_GUEST',
  $$SELECT 
      g.id AS guest_id,
      g.name AS guest_name,
      g.job_description,
      p.id AS pattern_id,
      p.name AS pattern_name,
      p.kind,
      e.id AS episode_id,
      e.title AS episode_title,
      pst.id AS post_id
    FROM guests g
    JOIN guests_patterns gp ON gp.guest_id = g.id
    JOIN patterns p ON p.id = gp.pattern_id
    LEFT JOIN episodes e ON e.id = g.episode_id
    LEFT JOIN posts pst ON pst.id = g.post_id
    ORDER BY g.name, p.name;$$
),

(
  'Patterns by Organization',
  'List patterns associated with organizations and their funding stages.',
  'PATTERNS_BY_ORGANIZATION',

  $$SELECT 
      o.id AS org_id,
      o.name AS org_name,
      o.stage AS funding_stage,
      p.id AS pattern_id,
      p.name AS pattern_name,
      p.kind
    FROM orgs o
    JOIN orgs_patterns op ON op.org_id = o.id
    JOIN patterns p ON p.id = op.pattern_id
    ORDER BY o.stage, o.name;$$
),

(
  'Top 10 Patterns by Frequency',
  'Rank patterns by how many times they appear across guests, episodes, posts, or orgs.',
  'TOP_PATTERNS_BY_FREQUENCY',
  $$WITH freq AS (
      SELECT pattern_id, COUNT(*) AS count FROM episodes_patterns GROUP BY pattern_id
      UNION ALL
      SELECT pattern_id, COUNT(*) FROM guests_patterns GROUP BY pattern_id
      UNION ALL
      SELECT pattern_id, COUNT(*) FROM orgs_patterns GROUP BY pattern_id
      UNION ALL
      SELECT pattern_id, COUNT(*) FROM posts_patterns GROUP BY pattern_id
  )
  SELECT 
      p.id AS pattern_id,
      p.name AS pattern_name,
      p.kind,
      SUM(freq.count) AS total_mentions
  FROM patterns p
  JOIN freq ON freq.pattern_id = p.id
  GROUP BY p.id, p.name, p.kind
  ORDER BY total_mentions DESC
  LIMIT 10;$$
),

(
  'Episodes with the Most Patterns',
  'Rank episodes by the number of patterns linked to them.',
  'EPISODES_WITH_MOST_PATTERNS',
  $$SELECT 
      e.id AS episode_id,
      e.title AS episode_title,
      e.youtube_url,
      COUNT(ep.pattern_id) AS pattern_count
    FROM episodes e
    LEFT JOIN episodes_patterns ep ON ep.episode_id = e.id
    GROUP BY e.id, e.title, e.youtube_url
    ORDER BY pattern_count DESC;$$
),

(
  'Guests Discussing the Same Pattern',
  'Find groups of guests who discuss the same pattern.',
  'GUESTS_DISCUSSING_SAME_PATTERN',
  $$SELECT 
      p.id AS pattern_id,
      p.name AS pattern_name,
      STRING_AGG(g.name, ', ') AS guest_list
    FROM patterns p
    JOIN guests_patterns gp ON gp.pattern_id = p.id
    JOIN guests g ON g.id = gp.guest_id
    GROUP BY p.id, p.name
    HAVING COUNT(g.id) > 1
    ORDER BY p.name;$$
),

(
  'Patterns Related to Funding Stage',
  'Explore relationships between pattern types and the funding stage of organizations.',
  'PATTERNS_BY_ORG_FUNDING_STAGE',
  $$SELECT 
      o.stage AS funding_stage,
      p.kind AS pattern_kind,
      COUNT(*) AS pattern_count
    FROM orgs o
    JOIN orgs_patterns op ON op.org_id = o.id
    JOIN patterns p ON p.id = op.pattern_id
    GROUP BY o.stage, p.kind
    ORDER BY o.stage, pattern_count DESC;$$
),

(
  'Time to Funding After Founding',
  'Compute time from founding date to funding date for organizations.',
  'TIME_TO_FUNDING',
  $$SELECT 
      o.id AS org_id,
      o.name AS org_name,
      o.stage,
      EXTRACT(YEAR FROM (o.date_funded - o.date_founded)) AS years_to_funding
    FROM orgs o
    WHERE o.date_funded IS NOT NULL
      AND o.date_founded IS NOT NULL
    ORDER BY years_to_funding;$$
);
--
--
insert into views_registry (rule_id, table_name, summary) values
(1, 'pattern_episodes', 'Patterns in Episodes'),
(2, 'pattern_guests', 'Patterns by Guest'),
(3, 'pattern_orgs', 'Patterns by Organization'),
(4, 'pattern_posts', 'Patterns by Post');
