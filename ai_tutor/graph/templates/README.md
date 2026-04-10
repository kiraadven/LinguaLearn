# Template Matrix

This folder now includes `skill_matrix_templates.yaml`, a baseline 4x4 matrix:

- Skills: `grammar`, `vocabulary`, `pronunciation`, `pragmatics`
- Cognitive levels: `recognition`, `recall`, `controlled_production`, `free_production`

Coverage targets encoded in template `tags` and `exercise_type`:

- `grammar`: `multiple_choice`, `fill_blank`, `sentence_transformation`, `compose`
- `vocabulary`: `matching`, `define`, `use_in_sentence`, `describe`
- `pronunciation`: `discriminate`, `repeat_shadow`, `minimal_pairs`, `free_talk`
- `pragmatics`: `identify`, `choose_register`, `rewrite_formal`, `role_play`

Conventions:

- Include `matrix` and skill/cognitive tags, for example:
  - `tags: ["matrix", "vocabulary", "controlled_production"]`
- Keep `node_type` aligned with interaction style:
  - recognition -> mostly `check_understanding`
  - recall/controlled -> mostly `guided_practice` / `pronunciation_drill`
  - free production -> mostly `free_practice` / `dialogue_practice`

L1-aware error coverage (supported in every template):

```yaml
l1_aware_error_patterns:
  "zh->en": ["article_omission", "tense_confusion", "word_order_svo_to_sov"]
  "ja->en": ["article_confusion", "singular_plural", "relative_clause"]
  "ko->en": ["preposition_errors", "word_order", "passive_voice"]
  "es->en": ["false_friends", "adjective_placement", "ser_estar_confusion"]
```

Notes:
- `AssessmentEngine` accepts both `zh->en` and `zh→en` key formats.
- Pattern ids are interpreted per L1-L2 pair, so names can be reused with pair-specific rules.
