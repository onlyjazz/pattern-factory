# Threat scenarios — Aegis medical federated learning

Source: supplied text of *Aegis: Generative Gradient Masking for Privacy-Preserving Medical Federated Learning*, arXiv:2609.38339v1, 29 September 2026. Analysis is grounded in the supplied paper, not independent replication.

## Modeling conventions

- Probability is an illustrative annual likelihood (0–1) for a hypothetical multi-institutional medical-FL deployment. These are analyst assumptions, not measured event frequencies or paper results. Recalibrate for the actual system, actors, and exposure.
- Damage is an illustrative 0–100 conditional severity score for the scenario, not a dollar loss or a percentage to apply uniformly to each asset. Asset-specific loss estimates are needed for SLE.
- Mitigation level is an illustrative 0–100 estimate of reduction in the specific scenario's likelihood, conditional on implementation and validation. It is not a measured efficacy claim. Do not add or multiply these levels without a dependency model.
- Costs are indicative USD for one vendor deployment: fixed implementation and annual recurring implementation. They exclude incident costs and require scoping; shared controls should be budgeted once rather than once per threat.
- C1000–C1006 are proposed additions because the supplied catalog lacks these FL-specific controls. All other tags retain supplied names.
- These scenarios overlap. R1 is the general loss event; R2–R4, R6–R7 describe alternative mechanisms or residual exposure. Do not sum their loss estimates as independent losses.
- Aegis addresses server-side reconstruction; it does not establish protection from client poisoning, backdoors, membership inference, or every future attack. Secure aggregation remains useful within its assumptions. Properly configured DP can provide a formal bound; noisy training alone does not.

## Assets

- **A1 — Product / Clinical IP:** Algorithms, models, device design, proprietary know-how, technical differentiation, and clinically valuable intellectual property.
- **A2 — Regulatory / Market Authorization:** FDA clearance or approval, other market authorizations, validated claims, quality evidence, and regulatory position supporting market access.
- **A3 — Revenue / Customer Franchise:** Existing revenue, customers, contracts, installed base, procurement relationships, renewals, and commercial franchise.
- **A4 — Clinical / Patient Data:** Clinical datasets, patient data under stewardship, training and evaluation datasets, measurements, images, and other valuable health data.
- **A5 — Brand / Trust:** Trust and reputation with clinicians, patients, hospitals, regulators, partners, investors, and the market.
- **A6 — Operations / Service Delivery:** Ability to manufacture, deploy, operate, support, maintain, and continuously deliver the product or clinical service.
- **A7 — Safety:** Sustain safety of patients and medical staff.
- **A8 — Strategic / Enterprise Value:** Strategic partnerships, future pipeline, competitive position, platform value, growth options, and broader enterprise value not captured elsewhere.

# Threat R1

Tag: R1

Name: Patient images reconstructed from shared federated updates

Domain: PRIVACY

Probability: 0.15

Affects Assets: A4, A3, A5, A8

Damage: 80

Scenario:

An honest-but-curious coordinator inspects legitimate updates, or an active coordinator broadcasts leakage-enabling models and reconstructs patient images. Exposure can undermine institutional agreements and customer trust.

Vulnerability:

Tag: V1000

Keeping raw records local does not prevent gradients or parameter deltas from carrying recoverable patient information. Encryption in transit does not protect against the authorized recipient.

Evidence / inference:

Directly supported: §§2–3. Active linear-leakage attacks and passive optimization attacks have different prerequisites; do not assume equal effectiveness.

Countermeasures:

**C1000    Client-Side Generative Gradient Masking**

Compute a masking gradient from local, task-relevant synthetic samples and combine it with the real update before transmission; validate leakage reduction for the deployed model and attack setting.

mitigation level 65

recurring_implementation_cost 18000

fixed_implementation_cost 60000

**C1001    Client-Enforced Model Architecture and Parameter Policy**

Independently approve broadcast architectures and enforce bounds on leakage-sensitive layers and parameter changes; reject unauthorized models even when server-signed.

mitigation level 70

recurring_implementation_cost 15000

fixed_implementation_cost 45000

**C863    Differential Privacy or Noise Injection during Training**

Limit the influence of any single training example; specify clipping, privacy unit, noise mechanism, composition, and privacy budget rather than relying on arbitrary noise.

mitigation level 60

recurring_implementation_cost 25000

fixed_implementation_cost 50000

# Threat R2

Tag: R2

Name: Target institution's patient data isolated despite secure aggregation

Domain: PRIVACY

Probability: 0.1

Affects Assets: A4, A3, A5, A8

Damage: 85

Scenario:

An active server manipulates models or participation to isolate a target client's contribution from otherwise aggregated updates, then reconstructs sensitive images.

Vulnerability:

Tag: V1001

Secure aggregation protects individual messages under its protocol assumptions but does not independently prevent malicious model construction, suppression, or inference from released aggregates.

Evidence / inference:

Directly supported: §2.2 and §3; effectiveness depends on the attack and aggregation configuration.

Countermeasures:

**C1001    Client-Enforced Model Architecture and Parameter Policy**

Independently approve broadcast architectures and enforce bounds on leakage-sensitive layers and parameter changes; reject unauthorized models even when server-signed.

mitigation level 70

recurring_implementation_cost 15000

fixed_implementation_cost 45000

**C1004    Federated Cohort and Aggregate Release Controls**

Enforce independently governed minimum cohorts, participation rules, and restrictions on repeated or overlapping aggregate releases; test isolation and disaggregation attacks.

mitigation level 60

recurring_implementation_cost 20000

fixed_implementation_cost 50000

**C1000    Client-Side Generative Gradient Masking**

Compute a masking gradient from local, task-relevant synthetic samples and combine it with the real update before transmission; validate leakage reduction for the deployed model and attack setting.

mitigation level 65

recurring_implementation_cost 18000

fixed_implementation_cost 60000

# Threat R3

Tag: R3

Name: Adaptive server exceeds the deployed masking capacity

Domain: PRIVACY

Probability: 0.1

Affects Assets: A4, A3, A5

Damage: 80

Scenario:

The coordinator increases leakage-layer capacity after a fixed masking configuration is deployed. Previously validated protection becomes inadequate and patient images become recoverable.

Vulnerability:

Tag: V1002

A fixed defense batch is sized against an assumed leakage capacity. Merely making total batch size larger than layer width does not establish that every real sample collides or that leakage is zero.

Evidence / inference:

Explicit deployment limitation: §5.3 and Appendix I. The paper uses M=2048 and k=1024 by default; these are experimental settings, not universal safety thresholds.

Countermeasures:

**C1001    Client-Enforced Model Architecture and Parameter Policy**

Independently approve broadcast architectures and enforce bounds on leakage-sensitive layers and parameter changes; reject unauthorized models even when server-signed.

mitigation level 70

recurring_implementation_cost 15000

fixed_implementation_cost 45000

**C1002    Adaptive Reconstruction Testing and Mask Sizing**

Test reconstruction against the actual broadcast model, generator, batch size, and adaptive attacks; resize masking or suspend uploads when leakage exceeds acceptance criteria.

mitigation level 65

recurring_implementation_cost 25000

fixed_implementation_cost 50000

**C1003    Fail-Closed Masked Update Transmission**

Permit transmission only after verifying completion and integrity of the masking computation; prevent raw updates from escaping through retries, debugging, fallback paths, or monitoring.

mitigation level 85

recurring_implementation_cost 10000

fixed_implementation_cost 30000

# Threat R4

Tag: R4

Name: Residual reconstructions expose patients under an approved Aegis configuration

Domain: PRIVACY

Probability: 0.15

Affects Assets: A4, A3, A5

Damage: 75

Scenario:

A coordinator recovers a subset of images even though average reconstruction quality has fallen. Repeated releases could increase the number of exposed records.

Vulnerability:

Tag: V1003

Aggregate privacy metrics obscure surviving high-fidelity reconstructions. The tested defense does not supply a formal differential-privacy guarantee or establish non-identifiability of every sample.

Evidence / inference:

Direct evidence: Table 2 reports Aegis RR 9.50% (ChestMNIST), 11.63% (OrganAMNIST), and 9.38% (PathMNIST), using PSNR>18. These image-level experimental rates are not annual breach probabilities.

Countermeasures:

**C1002    Adaptive Reconstruction Testing and Mask Sizing**

Test reconstruction against the actual broadcast model, generator, batch size, and adaptive attacks; resize masking or suspend uploads when leakage exceeds acceptance criteria.

mitigation level 65

recurring_implementation_cost 25000

fixed_implementation_cost 50000

**C863    Differential Privacy or Noise Injection during Training**

Limit the influence of any single training example; specify clipping, privacy unit, noise mechanism, composition, and privacy budget rather than relying on arbitrary noise.

mitigation level 60

recurring_implementation_cost 25000

fixed_implementation_cost 50000

**C911    Model Cards & Clear Documentation**

Maintain concise, accessible documentation of intended use, performance, limitations, and failure modes.

mitigation level 50

recurring_implementation_cost 8000

fixed_implementation_cost 15000

# Threat R5

Tag: R5

Name: Poorly matched synthetic masking weakens privacy and clinical performance

Domain: CLINICAL

Probability: 0.15

Affects Assets: A1, A2, A4, A5, A7

Damage: 85

Scenario:

Synthetic defense samples fail to overlap the real samples' leakage behavior while also shifting model learning. Images remain recoverable and subgroup diagnostic performance deteriorates, potentially causing missed or incorrect diagnoses.

Vulnerability:

Tag: V1004

Generated images may be poorly matched to local modality, pathology, or population. Global accuracy can hide subgroup errors; convergence under convex assumptions does not guarantee clinical deep-network performance.

Evidence / inference:

Generator mismatch is explicitly discussed in §4.2 and Appendix A/I. Patient harm and authorization impacts are deployment inferences; the paper does not demonstrate clinical adverse events.

Countermeasures:

**C1005    Synthetic Defense Dataset Qualification**

Verify local synthetic samples cover clinically relevant classes, sites, and leakage-bin distributions; measure privacy and utility together before approving their use.

mitigation level 65

recurring_implementation_cost 20000

fixed_implementation_cost 45000

**C872    Robustness Testing Across Sites & Populations**

Validate performance on data from multiple institutions and demographic groups before release.

mitigation level 70

recurring_implementation_cost 30000

fixed_implementation_cost 60000

**C874    Stratified Performance Evaluation**

Measure and report metrics across relevant demographic and clinical subgroups.

mitigation level 60

recurring_implementation_cost 20000

fixed_implementation_cost 35000

**C869    Continuous Performance Monitoring**

Track key metrics (accuracy, sensitivity, specificity, calibration) on live or shadow data.

mitigation level 55

recurring_implementation_cost 24000

fixed_implementation_cost 35000

**C873    Fallback to Conservative Clinical Pathways**

When drift or low confidence is detected, default to standard non-AI workflows.

mitigation level 65

recurring_implementation_cost 12000

fixed_implementation_cost 25000

# Threat R6

Tag: R6

Name: Unmasked updates escape through implementation or resource failure

Domain: PRIVACY

Probability: 0.1

Affects Assets: A4, A5, A6

Damage: 80

Scenario:

An out-of-memory error, retry path, debug export, or fallback skips masking and transmits the real update. A recipient with reconstruction capability obtains patient information.

Vulnerability:

Tag: V1005

The client lacks a mandatory transmission gate tied to successful masking, or emits intermediate real gradients through secondary paths.

Evidence / inference:

Engineering inference from Algorithm 1 and resource limitations in §5.2/Appendix I; not an observed failure in the paper.

Countermeasures:

**C1003    Fail-Closed Masked Update Transmission**

Permit transmission only after verifying completion and integrity of the masking computation; prevent raw updates from escaping through retries, debugging, fallback paths, or monitoring.

mitigation level 85

recurring_implementation_cost 10000

fixed_implementation_cost 30000

**C893    Capacity Planning & Load Testing**

Regularly test under expected and peak clinical loads.

mitigation level 65

recurring_implementation_cost 10000

fixed_implementation_cost 20000

**C1002    Adaptive Reconstruction Testing and Mask Sizing**

Test reconstruction against the actual broadcast model, generator, batch size, and adaptive attacks; resize masking or suspend uploads when leakage exceeds acceptance criteria.

mitigation level 65

recurring_implementation_cost 25000

fixed_implementation_cost 50000

# Threat R7

Tag: R7

Name: Repeated-round analysis separates reusable synthetic contributions

Domain: PRIVACY

Probability: 0.05

Affects Assets: A4, A5, A8

Damage: 75

Scenario:

An adaptive coordinator uses repeated updates and generator knowledge to estimate synthetic contributions, potentially recovering information masked in a single-round test.

Vulnerability:

Tag: V1006

Defense samples are reused and the privacy case does not establish resistance to all repeated-round or demixing strategies. Synthetic gradients still depend on changing model parameters, so reuse alone does not prove simple subtraction will work.

Evidence / inference:

Prospective threat, not a demonstrated bypass: Algorithm 1 reuses defense data; §5.3 and Appendix I discuss attempted demixing as underdetermined without sample identities.

Countermeasures:

**C1006    Repeated-Round and Demixing Resistance Validation**

Evaluate repeated-round reconstruction and estimation of synthetic contributions; control defense-data reuse and refresh samples when empirical testing shows a benefit.

mitigation level 40

recurring_implementation_cost 25000

fixed_implementation_cost 45000

**C1002    Adaptive Reconstruction Testing and Mask Sizing**

Test reconstruction against the actual broadcast model, generator, batch size, and adaptive attacks; resize masking or suspend uploads when leakage exceeds acceptance criteria.

mitigation level 65

recurring_implementation_cost 25000

fixed_implementation_cost 50000

**C863    Differential Privacy or Noise Injection during Training**

Limit the influence of any single training example; specify clipping, privacy unit, noise mechanism, composition, and privacy budget rather than relying on arbitrary noise.

mitigation level 60

recurring_implementation_cost 25000

fixed_implementation_cost 50000

# Threat R8

Tag: R8

Name: Benchmark privacy claims used to justify unsupported clinical deployment

Domain: REGULATORY

Probability: 0.2

Affects Assets: A2, A3, A5, A8

Damage: 70

Scenario:

A vendor represents benchmark results as proof of complete patient privacy or unchanged clinical safety for full-resolution imaging. A customer review or incident reveals that production conditions were never validated, threatening contracts and market access.

Vulnerability:

Tag: V1007

Evidence from benchmark-resolution MedMNIST and selected attacks is extrapolated to different modalities, architectures, data distributions, resolutions, or clinical endpoints. Published claims exceed demonstrated scope.

Evidence / inference:

Explicit evidence limitations: §5.3 and Appendix I; commercial and authorization consequences are conditional deployment inferences.

Countermeasures:

**C911    Model Cards & Clear Documentation**

Maintain concise, accessible documentation of intended use, performance, limitations, and failure modes.

mitigation level 50

recurring_implementation_cost 8000

fixed_implementation_cost 15000

**C940    Controlled Documentation & Records**

Maintain approved, version-controlled procedures, specifications, risk records, test evidence, and required operational records.

mitigation level 55

recurring_implementation_cost 15000

fixed_implementation_cost 20000

**C943    Regulatory Change Assessment**

Assess whether product, model, infrastructure, intended-use, or supplier changes trigger new validation, documentation, or regulatory obligations.

mitigation level 60

recurring_implementation_cost 12000

fixed_implementation_cost 20000

**C872    Robustness Testing Across Sites & Populations**

Validate performance on data from multiple institutions and demographic groups before release.

mitigation level 70

recurring_implementation_cost 30000

fixed_implementation_cost 60000

**C1002    Adaptive Reconstruction Testing and Mask Sizing**

Test reconstruction against the actual broadcast model, generator, batch size, and adaptive attacks; resize masking or suspend uploads when leakage exceeds acceptance criteria.

mitigation level 65

recurring_implementation_cost 25000

fixed_implementation_cost 50000

## Validation before operational use

Identify the real server trust boundary, client update format, aggregation protocol, approved architectures, and data modalities. Test the configured system against both privacy reconstruction and clinically meaningful performance criteria, including surviving reconstructions and subgroup results. Confirm fail-closed behavior during masking faults and model changes. Replace the illustrative financial and likelihood inputs with documented assumptions before using these scenarios to price exposure.

