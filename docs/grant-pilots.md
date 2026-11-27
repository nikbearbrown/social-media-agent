# Shared intake for three lexicon proposals

All three can reuse bounded intake, duplicate handling, versioned vocabulary and reviewer QA. They should not share person-level data or blend sources. These are design concepts, not sponsor-approved workflows.

| Proposal | What this repo contributes | What stays outside |
| --- | --- | --- |
| I3-03: Disease, Syndromes and Symptoms | Compare public-facing wording in approved organizational bulletins with the existing lexicon to generate candidate plain-language synonyms. Review candidates on fictional examples; measure whether reviewers accept or reject each candidate consistently. | The proposal's document extraction evaluation is separate. Social posts do not create case records or substantiate diagnoses or outbreaks. |
| I3-04: Clinical Treatments and Procedures, with the symptom/syndrome layer | Compare how established procedures and related vocabulary appear in approved public education material. Build synthetic examples to separate a symptom term from a procedure term and test ambiguous matches. | Emergency department notes and any review-queue evaluation stay inside a separate BPHC-approved workflow. Never link feeds to patient records. |
| I3-08: Drugs and Recreational Drug Use | If the sponsor confirms the brief, assess terminology ambiguity on invented examples and language in approved public organizational notices. Report false positives and language gaps at an aggregate level. | No individual watchlists, demographic inference, location tracking, small-group outputs, personal posts or automatic action. |

For each pilot, start with the same fixture, add a small human-reviewed vocabulary layer, and keep a versioned list of suggestions accepted, rejected or unresolved. Study usefulness separately from mention volume. An analyst should be able to explain why a term was added without exposing a source post.

Sponsor: [BPHC I³ Accelerator](https://www.boston.gov/departments/boston-public-health-commission/boston-sphere). Lexica: [Disease, Syndromes and Symptoms](https://github.com/nikbearbrown/disease-syndromes-and-symptoms-lexicon), [Clinical Treatments and Procedures](https://github.com/nikbearbrown/clinical-treatments-and-procedures-lexicon), and [Drugs and Recreational Drug Use](https://github.com/nikbearbrown/drugs-and-recreational-drug-use-lexicon).
