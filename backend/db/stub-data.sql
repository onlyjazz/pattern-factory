DELETE FROM categories;
insert into categories (description) values ('TechBio');
insert into categories (description) values ('Biotech');
insert into categories (description) values ('AI');

--
DELETE FROM posts;
INSERT INTO posts (name, description, keywords, substack_url) 
VALUES (
    'Founder–Market Misfit',
    'Counter-Positioning through founder-market misfit creates defensible moats. Delve Health disrupts CROs by automating home-based trials, combining Process Power with AI-driven Scale Economies.',
    '{"Counter-Positioning", "founder-market misfit", "Delve Health", "clinical trials", "Process Power", "Scale Economies", "CRO disruption", "AI automation"}',
    'https://newsletter.dannylieberman.com/p/foundermarket-misfit'
);

INSERT INTO posts (name, description, keywords, substack_url) 
VALUES (
    'The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma',
    'Early-stage TechBio companies build moats through Cornered Resources or Counter-Positioning. Itay and Beyond uses human-derived brain organoids to replace failing animal models.',
    '{"Cornered Resources", "Counter-Positioning", "brain organoids", "TechBio strategy", "Itay and Beyond", "competitive moats", "drug discovery", "founder teams"}',
    'https://newsletter.dannylieberman.com/p/the-great-brain-bet-how-human-derived'
);

INSERT INTO posts (name, description, keywords, substack_url) 
VALUES (
    'Switching Costs',
    'Switching Costs create customer lock-in through integration complexity and workflow dependencies. SAP and Flatiron Health demonstrate how captive customers become defensible moats.',
    '{"Switching Costs", "customer lock-in", "SAP", "Flatiron Health", "enterprise integration", "competitive moats", "network effects", "EMR systems"}',
    'https://newsletter.dannylieberman.com/p/switching-costs'
);

INSERT INTO posts (name, description, keywords, substack_url) 
VALUES (
    'Why do we buy Brands: For good feeling or good value?',
    'Brand Power commands premium pricing through emotional connection and trust. Analysis of Tiffany, Carolina Lemke Berlin, and Selmer reveals leverage metrics from heritage cultivation.',
    '{"Brand Power", "pricing premium", "brand leverage", "Tiffany", "Carolina Lemke Berlin", "Selmer Mark VI", "emotional branding", "competitive moats"}',
    'https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling'
);

INSERT INTO posts (name, description, keywords, substack_url) 
VALUES (
    'AI and Robotics Rewrite Drug Discovery',
    'Process Power builds competitive moats through years of pattern accumulation. Iktos integrates AI with robotics for drug discovery orchestration competitors can''t easily replicate.',
    '{"Process Power", "drug discovery", "AI orchestration", "robotics integration", "competitive moats", "pattern accumulation", "Iktos", "TPS (Toyota Production System)"}',
    'https://newsletter.dannylieberman.com/p/ai-and-robotics-rewrite-drug-discovery'
);

-- episodes
DELETE FROM episodes;
INSERT INTO episodes (name, description, keywords, episode_url) 
VALUES (
    'From Math to Medicine: Yann Gaston-Mathé''s Mission to Transform Drug Discovery with AI and Robotics',
    'Yann Gaston-Mathé combines generative AI with robotic synthesis for faster drug discovery. Iktos automates design-make-test cycles, running 100 parallel reactions versus traditional methods.',
    '{"Iktos", "AI drug discovery", "robotic synthesis", "generative AI", "automated chemistry", "drug development", "Yann Gaston-Mathé", "parallel reactions"}',
    'https://www.healthcareittoday.com/2025/11/14/from-math-to-medicine-yann-gaston-mathes-mission-to-transform-drug-discovery-with-ai-and-robotics-life-sciences-today-podcast-episode-35/'
);
--
INSERT INTO episodes (name, description, keywords, episode_url) 
VALUES (
    'Precision Oncology Alliance with Caris Life Sciences',
    'Dr. James Hamrick leads Caris Precision Oncology Alliance with 600,000+ matched molecular and clinical patient records, combining genomic data for precision cancer treatment insights.',
    '{"Caris Life Sciences", "precision oncology", "molecular diagnostics", "genomic data", "clinical outcomes", "James Hamrick", "multimodal database", "cancer treatment"}',
    'https://www.healthcareittoday.com/2025/11/07/precision-oncology-alliance-with-caris-life-sciences-life-sciences-today-podcast-episode-34/'
);

INSERT INTO episodes (name, description, keywords, episode_url) 
VALUES (
    'Hybrid Intelligence with Carta Healthcare',
    'Aaron Brouser''s Carta Healthcare uses Hybrid Intelligence combining AI and clinical expertise for real-time EHR analysis, instantly matching patients to clinical trials.',
    '{"Carta Healthcare", "Hybrid Intelligence", "clinical data abstraction", "EHR analysis", "clinical trials", "AI-LLM", "Aaron Brouser", "patient matching"}',
    'https://www.healthcareittoday.com/2025/10/31/hybrid-intelligence-with-carta-healthcare-life-sciences-today-podcast-episode-33/'
);

INSERT INTO episodes (name, description, keywords, episode_url) 
VALUES (
    'Clean and Structured Text with emtelligent',
    'Tim O''Connell founded emtelligent to transform unstructured healthcare text into clean, structured formats using purpose-built AI for medical data analysis and research.',
    '{"emtelligent", "unstructured text", "data structuring", "healthcare NLP", "Tim O''Connell", "medical data", "clinical documentation", "AI extraction"}',
    'https://www.healthcareittoday.com/2025/10/24/clean-and-structured-text-with-emtelligent-life-sciences-today-podcast-episode-32/'
);

INSERT INTO episodes (name, description, keywords, episode_url) 
VALUES (
    'From Personal Struggle to Global Solution: Wessam Sonbol''s Mission to Bring Trials Home',
    'Wessam Sonbol founded Delve Health after his mother''s trial access struggle, bringing clinical trials home with wearables, AI agents, and multilingual support.',
    '{"Delve Health", "home-based trials", "clinical trial access", "wearables", "AI agents", "Wessam Sonbol", "patient compliance", "decentralized trials"}',
    'https://www.healthcareittoday.com/2025/10/17/from-personal-struggle-to-global-solution-wessam-sonbols-mission-to-bring-trials-home-life-sciences-today-podcast-episode-31/'
);

--
-- Guests table inserts
DELETE from guests;
INSERT INTO guests (name, job_description) 
VALUES (
    'Yann Gaston-Mathé',
    'Co-Founder and CEO at Iktos'
);

INSERT INTO guests (name, job_description) 
VALUES (
    'James Hamrick',
    'Chairman of the Caris Precision Oncology Alliance at Caris Life Sciences'
);

INSERT INTO guests (name, job_description) 
VALUES (
    'Aaron Brouser',
    'General Manager Life Sciences at Carta Healthcare'
);

INSERT INTO guests (name, job_description) 
VALUES (
    'Tim O''Connell',
    'Founder and CEO at emtelligent'
);

INSERT INTO guests (name, job_description) 
VALUES (
    'Wessam Sonbol',
    'Founder and CEO at Delve Health'
);

-- Orgs
DELETE from orgs;
INSERT INTO orgs (name) VALUES 
    ('Iktos'),
    ('Caris Life Sciences'),
    ('Carta Healthcare'),
    ('emtelligent'),
    ('Delve Health');

DELETE from patterns;
INSERT INTO patterns (name, description) VALUES 
    ('Scale Economies', 'Unit costs decline as production volume increases due to fixed cost spreading and operational efficiencies. Barriers rise when competitors can''t match your volume economics.'),
    ('Network Economies', 'Product value increases as more users join the network. Each additional user makes the product more valuable for everyone. See The Network Effects Bible for a detailed treatment of the different kinds of network effects.'),
    ('Counter-Positioning', 'A newcomer adopts a superior business model that incumbents can''t copy without damaging their existing business. The incumbent faces a "damned if you do, damned if you don''t" dilemma.'),
    ('Switching Costs', 'Customers face high financial, time, or risk costs when changing suppliers, keeping them loyal even when alternatives exist.'),
    ('Branding', 'Customers attribute higher value based on reputation and trust, not just product features.'),
    ('Cornered Resource', 'Exclusive access to a critical asset (data, talent, IP, relationships, raw materials) that others can''t easily obtain.'),
    ('Process Power', 'Organizational capabilities and methods that enable superior operations and are difficult for competitors to replicate — often built through years of learning and refinement.');

-- Link patterns to episodes based on content analysis
-- Episode 1: Delve Health - Counter-Positioning, Process Power, Scale Economies
delete from pattern_episode_link;
INSERT INTO pattern_episode_link (pattern_id, episode_id) VALUES
    (3, 1),  -- Counter-Positioning
    (7, 1),  -- Process Power
    (1, 1);  -- Scale Economies

-- Episode 2: emtelligent - Process Power, Cornered Resource
INSERT INTO pattern_episode_link (pattern_id, episode_id) VALUES
    (7, 2),  -- Process Power
    (6, 2);  -- Cornered Resource

-- Episode 3: Carta Healthcare - Switching Costs
INSERT INTO pattern_episode_link (pattern_id, episode_id) VALUES
    (4, 3);  -- Switching Costs

-- Episode 4: Caris Life Sciences - Branding, Cornered Resource
INSERT INTO pattern_episode_link (pattern_id, episode_id) VALUES
    (5, 4),  -- Branding
    (6, 4);  -- Cornered Resource

-- Episode 5: Iktos - Process Power, Scale Economies
INSERT INTO pattern_episode_link (pattern_id, episode_id) VALUES
    (7, 5),  -- Process Power
    (1, 5);  -- Scale Economies
--
-- Link patterns to guests based on episode content
DELETE from pattern_guest_link;
-- Guest 1: Yann Gaston-Mathé (Iktos) - Process Power, Scale Economies
INSERT INTO pattern_guest_link (pattern_id, guest_id) VALUES
    (7, 1);  -- Process Power


-- Guest 2: James Hamrick (Caris) - Branding, Cornered Resource
INSERT INTO pattern_guest_link (pattern_id, guest_id) VALUES
    (2, 2),  -- Network Economies
    (5, 2),  -- Branding
    (6, 2);  -- Cornered Resource

-- Guest 3: Aaron Brouser (Carta Healthcare) - Switching Costs
INSERT INTO pattern_guest_link (pattern_id, guest_id) VALUES
    (4, 3);  -- Switching Costs

-- Guest 4: Tim O'Connell (emtelligent) - Process Power, Cornered Resource
INSERT INTO pattern_guest_link (pattern_id, guest_id) VALUES
    (7, 4),  -- Process Power
    (6, 4);  -- Cornered Resource

-- Guest 5: Wessam Sonbol (Delve Health) - Counter-Positioning, Process Power, Scale Economies
INSERT INTO pattern_guest_link (pattern_id, guest_id) VALUES
    (3, 5),  -- Counter-Positioning
    (7, 5),  -- Process Power
    (1, 5);  -- Scale Economies

-- Link patterns to organizations based on their business models
DELETE from pattern_org_link;
-- Org 1: Iktos - Process Power
INSERT INTO pattern_org_link (pattern_id, org_id) VALUES
    (7, 1);  -- Process Power

-- Org 2: Caris Life Sciences - Branding, Cornered Resource, Network Economies
INSERT INTO pattern_org_link (pattern_id, org_id) VALUES
    (5, 2),  -- Branding
    (6, 2),  -- Cornered Resource
    (2, 2);  -- Network Economies

-- Org 3: Carta Healthcare - Switching Costs
INSERT INTO pattern_org_link (pattern_id, org_id) VALUES
    (4, 3);  -- Switching Costs

-- Org 4: emtelligent - Process Power
INSERT INTO pattern_org_link (pattern_id, org_id) VALUES
    (7, 4);  -- Process Power
    
-- Org 5: Delve Health - Counter-Positioning, Process Power, Scale Economies
INSERT INTO pattern_org_link (pattern_id, org_id) VALUES
    (3, 5),  -- Counter-Positioning
    (7, 5),  -- Process Power
    (1, 5);  -- Scale Economies

-- 
-- Link patterns to posts

-- Post 1: AI and Robotics Rewrite Drug Discovery (Iktos) - Process Power, Scale Economies
INSERT INTO pattern_post_link (pattern_id, post_id) VALUES
    (7, 1);  -- Process Power

-- Post 2: Why do we buy Brands (Tiffany, Carolina Lemke, Selmer) - Branding
INSERT INTO pattern_post_link (pattern_id, post_id) VALUES
    (5, 2);  -- Branding

-- Post 3: Switching Costs (SAP, Flatiron Health) - Switching Costs, Network Economies
INSERT INTO pattern_post_link (pattern_id, post_id) VALUES
    (4, 3),  -- Switching Costs
    (2, 3);  -- Network Economies (Flatiron's data flywheel)

-- Post 4: The Great Brain Bet (Itay and Beyond) - Cornered Resource, Counter-Positioning
INSERT INTO pattern_post_link (pattern_id, post_id) VALUES
    (6, 4),  -- Cornered Resource
    (3, 4);  -- Counter-Positioning

-- Post 5: Founder-Market Misfit (Delve Health) - Counter-Positioning, Process Power, Scale Economies
INSERT INTO pattern_post_link (pattern_id, post_id) VALUES
    (3, 5),  -- Counter-Positioning
    (7, 5),  -- Process Power
    (1, 5);  -- Scale Economies



INSERT INTO orgs (name, description, stage, funding, date_funded, date_founded)
VALUES
('Iktos', 'AI for new drug discovery and design', 'Series A', 21000000.00, '2025-02-20', '2016-01-01'),
('Caris Life Sciences', 'AI TechBio company specializing in molecular profiling for oncology', 'Public (previously Series D)', 1230000000.00, '2025-06-18', '2008-01-01'),
('Carta Healthcare', 'AI-powered clinical data abstraction and analytics solutions', 'Series B', 80500000.00, '2025-05-08', '2017-01-01'),
('Emtelligent', 'NLP engine and apps primarily for healthcare', 'Unfunded (Revenue Generating)', 0.00, NULL, '2016-01-01'),
('Delve Health', 'Digital clinical trial management tool for researchers', 'Seed/Early Stage', 1250000.00, '2022-07-07', '2016-01-01');
--
--