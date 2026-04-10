"""
AssessmentEngine - Evaluates student input on the hot path.

Rule-based, low-latency assessment. No LLM calls.
Produces: error_type, focus_skill, confidence, fatigue, engagement,
is_correct, is_silence, is_off_topic, error_severity, plus diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Optional

from ..graph.schema import LiveNode
from .memory import HotMemory


@dataclass
class ErrorHit:
    error_type: str
    severity: float


class AssessmentEngine:
    """Deterministic multi-signal assessor for runtime graph logic."""

    _STRICT_NODE_TYPES = {
        "vocabulary_focus",
        "guided_practice",
        "pronunciation_drill",
        "listening_comprehension",
        "reading_comprehension",
        "dialogue_practice",
        "dictation",
        "error_analysis",
        "free_practice",
        "check_understanding",
        "review",
        "repair",
    }

    # Lightweight multilingual grammar patterns (expandable).
    _GRAMMAR_PATTERNS: dict[str, list[tuple[str, str, float]]] = {
        "en": [
            (r"\b(yesterday|last|ago)\b.+\b(go|eat|do|have|make|come|see)\b", "major_tense_error", 0.8),
            (r"\b(he|she|it)\s+(go|do|have|make|eat|want|need)\b", "minor_subject_verb_agreement", 0.5),
            (r"\bi am agree\b|\bi am interesting\b", "minor_copula_adjective_error", 0.45),
            (r"\b(a|an)\s+[aeiou]\w*", "minor_article_error", 0.4),
            (r"\b(an)\s+[bcdfghjklmnpqrstvwxyz]\w*", "minor_article_error", 0.4),
        ],
        "es": [
            (r"\byo es\b|\btu es\b|\byo tiene\b", "major_spanish_conjugation_error", 0.75),
            (r"\bel casa\b|\bla problema\b", "minor_spanish_gender_article_error", 0.45),
        ],
        "fr": [
            (r"\bje suis faim\b", "major_french_avoir_etre_error", 0.75),
            (r"\bje ne\b(?!.*\bpas\b)", "minor_french_negation_error", 0.45),
        ],
        "de": [
            (r"\bich bin hunger\b", "major_german_copula_error", 0.75),
            (r"\bich gehen\b", "minor_german_conjugation_error", 0.5),
        ],
        "ja": [
            (r"ですです|ますます", "minor_japanese_politeness_reduplication", 0.4),
        ],
        "zh": [
            (r"了了|的是的", "minor_chinese_particle_error", 0.35),
        ],
    }

    # L1 interference patterns for English learning (expandable).
    _L1_TRANSFER_PATTERNS: dict[tuple[str, str], list[tuple[str, str, float]]] = {
        ("zh", "en"): [
            (r"\b(open|close)\s+the\s+light\b", "minor_l1_transfer_zh_en_collocation", 0.5),
            (r"\bvery\s+like\b", "minor_l1_transfer_zh_en_calque", 0.45),
            (r"\btoday\s+morning\b", "minor_l1_transfer_zh_en_time_expression", 0.45),
        ],
        ("ja", "en"): [
            (r"\bi am agree\b", "minor_l1_transfer_ja_en_predicate", 0.5),
            (r"\bi am interesting\b", "minor_l1_transfer_ja_en_interested_interesting", 0.5),
            (r"\bplease teach me english\b", "minor_l1_transfer_ja_en_literal_request", 0.4),
        ],
    }
    _L1_AWARE_PATTERN_LIBRARY: dict[tuple[str, str], dict[str, list[str]]] = {
        ("zh", "en"): {
            "article_omission": [
                r"\b(i|we|they)\s+(bought|need|want|saw)\s+\w+\b",
                r"\bgo to (store|school|hospital)\b",
            ],
            "tense_confusion": [
                r"\b(yesterday|last|ago)\b.+\b(go|eat|do|have|make|come|see)\b",
                r"\b(last week|last year)\b.+\b(is|are)\b",
            ],
            "word_order_svo_to_sov": [
                r"\b(i|we|they|he|she)\s+(to|at|in)\s+\w+\s+(go|went|do|did|eat|ate)\b",
                r"\b(i|we|they|he|she)\s+\w+\s+(to|at|in)\s+\w+\s+(go|went|do|did|eat|ate)\b",
            ],
        },
        ("ja", "en"): {
            "article_confusion": [
                r"\b(a|an)\s+[aeiou]\w+\b",
                r"\b(an)\s+[bcdfghjklmnpqrstvwxyz]\w+\b",
            ],
            "singular_plural": [
                r"\b(two|three|many|several)\s+\w+\b(?!s\b)",
            ],
            "relative_clause": [
                r"\bthe\s+\w+\s+which\s+\w+\s+is\s+\w+\b",
            ],
        },
        ("ko", "en"): {
            "preposition_errors": [
                r"\bdiscuss about\b",
                r"\bmarried with\b",
                r"\bdepend of\b",
            ],
            "word_order": [
                r"\b(i|we|they|he|she)\s+(to|at|in)\s+\w+\s+(go|went|do|did)\b",
                r"\b(i|we|they)\s+\w+\s+\w+\s+(go|went|do|did)\b",
            ],
            "passive_voice": [
                r"\b(is|was|were)\s+happened\b",
                r"\b(is|was|were)\s+occurred\b",
            ],
        },
        ("es", "en"): {
            "false_friends": [
                r"\bactually\b.+\b(currently|now)\b",
                r"\bassist to\b",
            ],
            "adjective_placement": [
                r"\b(the|a|an)\s+\w+\s+(red|blue|big|small|important|interesting)\b",
            ],
            "ser_estar_confusion": [
                r"\bi am boring\b",
                r"\bi am agree\b",
            ],
        },
    }

    _HEDGE_TERMS = ("maybe", "i think", "not sure", "i guess", "probably")

    _ANSWER_KEYS = {
        "answer", "correct", "correct_answer", "example_answer", "translation",
        "source", "target", "word", "expression", "sentence", "text",
    }

    _LANG_HINT_KEYS = {
        "target_lang", "learning_lang", "study_lang", "source_lang", "lesson_lang",
    }
    _L1_HINT_KEYS = {
        "student_l1", "l1_lang", "native_lang", "native_language", "user_lang",
    }

    _EN_STOPWORDS = {
        "a", "an", "the", "i", "you", "he", "she", "it", "we", "they", "is",
        "are", "was", "were", "be", "to", "of", "in", "on", "for", "and", "or",
    }

    _OFF_TOPIC_CUES = {
        "weather", "bitcoin", "politics", "football", "nba", "movie", "game", "music",
    }

    def evaluate(
        self,
        student_text: str,
        audio_features: dict,
        current_node: LiveNode,
        hot_memory: HotMemory,
    ) -> dict:
        """Evaluate student input against current node expectations."""
        text = student_text.strip()
        text_lower = text.lower()

        detected_lang = self._detect_text_lang(text)
        target_lang = self._resolve_target_lang(audio_features, current_node, detected_lang)
        l1_lang = self._resolve_l1_lang(audio_features, current_node)
        focus_skill = current_node.learning_targets[0] if current_node.learning_targets else ""

        expected_answers = self._extract_expected_answers(current_node)
        requires_semantic_match = self._requires_semantic_match(current_node, expected_answers)
        semantic_similarity = self._semantic_similarity(text, expected_answers, target_lang)
        pronunciation_hit, pronunciation_score = self._assess_pronunciation(audio_features)

        if not text or len(text) < 2:
            return {
                "is_silence": True,
                "is_correct": False,
                "is_off_topic": False,
                "error_type": "",
                "focus_skill": "",
                "confidence": 0.0,
                "fatigue": self._estimate_fatigue(audio_features, hot_memory),
                "engagement": 0.2,
                "error_severity": 0.0,
                "semantic_similarity": 0.0,
                "pronunciation_score": pronunciation_score,
                "detected_lang": detected_lang,
                "target_lang": target_lang,
                "l1_lang": l1_lang,
                "duration_ms": audio_features.get("duration_ms", 0),
                "silence_before_ms": audio_features.get("silence_before_ms", 0),
            }

        grammar_hit = self._classify_grammar_error(text_lower, target_lang)
        l1_hit = self._classify_l1_transfer_error(
            text_lower=text_lower, l1_lang=l1_lang, target_lang=target_lang, node=current_node,
        )
        semantic_hit = self._classify_semantic_error(
            semantic_similarity=semantic_similarity,
            requires_semantic_match=requires_semantic_match,
        )
        completeness_hit = self._classify_completeness_error(text, current_node)
        is_off_topic = self._detect_off_topic(
            text=text_lower,
            node=current_node,
            expected_answers=expected_answers,
            semantic_similarity=semantic_similarity,
        )
        off_topic_hit = ErrorHit("major_off_topic_response", 0.85) if is_off_topic else None

        hits = [
            hit for hit in (
                grammar_hit, l1_hit, pronunciation_hit, semantic_hit, completeness_hit, off_topic_hit
            ) if hit is not None
        ]
        selected = max(hits, key=lambda h: h.severity) if hits else None

        error_type = selected.error_type if selected else ""
        error_severity = selected.severity if selected else 0.0
        is_correct = selected is None and not is_off_topic

        confidence = self._estimate_confidence(
            text=text,
            audio_features=audio_features,
            semantic_similarity=semantic_similarity,
            error_severity=error_severity,
            pronunciation_score=pronunciation_score,
        )
        fatigue = self._estimate_fatigue(audio_features, hot_memory)
        engagement = self._estimate_engagement(text, audio_features, hot_memory)

        return {
            "is_silence": False,
            "is_correct": is_correct,
            "is_off_topic": is_off_topic,
            "error_type": error_type,
            "focus_skill": focus_skill,
            "confidence": confidence,
            "fatigue": fatigue,
            "engagement": engagement,
            "error_severity": error_severity,
            "semantic_similarity": semantic_similarity,
            "pronunciation_score": pronunciation_score,
            "detected_lang": detected_lang,
            "target_lang": target_lang,
            "l1_lang": l1_lang,
            "duration_ms": audio_features.get("duration_ms", 0),
            "silence_before_ms": audio_features.get("silence_before_ms", 0),
        }

    # ------------------------------------------------------------------
    # Core classifiers
    # ------------------------------------------------------------------

    def _classify_grammar_error(self, text_lower: str, target_lang: str) -> Optional[ErrorHit]:
        lang = self._canonical_lang(target_lang)
        for pattern, err, sev in self._GRAMMAR_PATTERNS.get(lang, []):
            if re.search(pattern, text_lower):
                return ErrorHit(err, sev)
        return None

    def _classify_l1_transfer_error(
        self,
        text_lower: str,
        l1_lang: str,
        target_lang: str,
        node: LiveNode,
    ) -> Optional[ErrorHit]:
        l1 = self._canonical_lang(l1_lang)
        tgt = self._canonical_lang(target_lang)
        for pattern, err, sev in self._L1_TRANSFER_PATTERNS.get((l1, tgt), []):
            if re.search(pattern, text_lower):
                return ErrorHit(err, sev)
        template_hit = self._classify_template_l1_transfer_error(text_lower, l1, tgt, node)
        if template_hit is not None:
            return template_hit

        common = (node.content_pack or {}).get("common_mistakes", {})
        examples = common.get("error_examples", []) if isinstance(common, dict) else []
        for item in examples:
            if not isinstance(item, dict):
                continue
            wrong = str(item.get("wrong", "")).strip().lower()
            correct = str(item.get("correct", "")).strip().lower()
            if not wrong:
                continue

            if wrong in text_lower:
                return ErrorHit("minor_l1_transfer_from_content_pack", 0.55)

            sim_wrong = self._text_similarity(text_lower, wrong)
            sim_correct = self._text_similarity(text_lower, correct) if correct else 0.0
            # Only trigger if the student response is materially closer to the
            # wrong pattern than the correct pattern.
            if sim_wrong >= 0.9 and sim_wrong > sim_correct + 0.05:
                return ErrorHit("minor_l1_transfer_from_content_pack", 0.55)
        return None

    def _classify_template_l1_transfer_error(
        self,
        text_lower: str,
        l1_lang: str,
        target_lang: str,
        node: LiveNode,
    ) -> Optional[ErrorHit]:
        pair_patterns = self._L1_AWARE_PATTERN_LIBRARY.get((l1_lang, target_lang), {})
        if not pair_patterns:
            return None
        for pattern_id in self._resolve_node_l1_pattern_ids(node, l1_lang, target_lang):
            regex_list = pair_patterns.get(pattern_id, [])
            for pattern in regex_list:
                if re.search(pattern, text_lower):
                    return ErrorHit(f"minor_l1_transfer_{pattern_id}", 0.58)
        return None

    def _resolve_node_l1_pattern_ids(
        self,
        node: LiveNode,
        l1_lang: str,
        target_lang: str,
    ) -> list[str]:
        raw = getattr(node, "l1_aware_error_patterns", {})
        if not isinstance(raw, dict):
            return []
        target_pair = f"{l1_lang}->{target_lang}"
        out: list[str] = []
        for pair_key, value in raw.items():
            if self._normalize_l1_pair_key(pair_key) != target_pair:
                continue
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
        # Preserve order while deduplicating.
        dedup: list[str] = []
        seen = set()
        for item in out:
            if item in seen:
                continue
            seen.add(item)
            dedup.append(item)
        return dedup

    def _normalize_l1_pair_key(self, pair_key: object) -> str:
        if not isinstance(pair_key, str):
            return ""
        normalized = pair_key.strip().lower()
        normalized = normalized.replace("→", "->").replace("=>", "->").replace("/", "->")
        normalized = normalized.replace(" ", "")
        if "->" not in normalized:
            return ""
        src_raw, tgt_raw = normalized.split("->", 1)
        src = self._canonical_lang(src_raw)
        tgt = self._canonical_lang(tgt_raw)
        if not src or not tgt:
            return ""
        return f"{src}->{tgt}"

    @staticmethod
    def _classify_semantic_error(
        semantic_similarity: float,
        requires_semantic_match: bool,
    ) -> Optional[ErrorHit]:
        if not requires_semantic_match:
            return None
        if semantic_similarity < 0.18:
            return ErrorHit("major_semantic_mismatch", 0.85)
        if semantic_similarity < 0.35:
            return ErrorHit("minor_semantic_mismatch", 0.5)
        return None

    @staticmethod
    def _classify_completeness_error(text: str, node: LiveNode) -> Optional[ErrorHit]:
        if node.expected_student_evidence and len(text.split()) < 3:
            return ErrorHit("minor_incomplete_response", 0.4)
        return None

    def _assess_pronunciation(self, audio_features: dict) -> tuple[Optional[ErrorHit], float]:
        score = self._extract_pronunciation_score(audio_features)
        if score is None:
            return None, 0.5

        per = self._extract_fraction(audio_features, ("phoneme_error_rate", "per"))
        mispronounced = float(audio_features.get("mispronounced_count", 0) or 0)
        derived = score
        if per is not None:
            derived = min(derived, max(0.0, 1.0 - per))
        if mispronounced > 0:
            derived = max(0.0, derived - min(0.3, mispronounced * 0.03))

        if derived < 0.45 or (per is not None and per > 0.35):
            return ErrorHit("major_pronunciation_error", 0.8), derived
        if derived < 0.65:
            return ErrorHit("minor_pronunciation_error", 0.45), derived
        return None, derived

    def _detect_off_topic(
        self,
        text: str,
        node: LiveNode,
        expected_answers: list[str],
        semantic_similarity: float,
    ) -> bool:
        if any(cue in text for cue in self._OFF_TOPIC_CUES):
            return True

        text_tokens = self._tokenize(text)
        if len(text_tokens) < 4:
            return False

        topical_tokens = set()
        for t in node.learning_targets:
            topical_tokens.update(self._tokenize(t))
        for c in expected_answers[:20]:
            topical_tokens.update(self._tokenize(c))
        topical_tokens = {t for t in topical_tokens if len(t) >= 2 and t not in self._EN_STOPWORDS}
        if not topical_tokens:
            return False

        overlap = len(set(text_tokens) & topical_tokens) / max(1, len(set(text_tokens)))
        return overlap < 0.08 and semantic_similarity < 0.15 and len(text_tokens) > 8

    # ------------------------------------------------------------------
    # Expected answer + semantic matching
    # ------------------------------------------------------------------

    def _requires_semantic_match(self, node: LiveNode, expected_answers: list[str]) -> bool:
        if node.node_type in self._STRICT_NODE_TYPES and expected_answers:
            return True
        evidence = " ".join(node.expected_student_evidence).lower()
        return bool(expected_answers) and any(
            key in evidence for key in ("answer", "translation", "sentence", "correct")
        )

    def _extract_expected_answers(self, node: LiveNode) -> list[str]:
        out: list[str] = []

        def add(value) -> None:
            if value is None:
                return
            if isinstance(value, str):
                v = value.strip()
                if len(v) >= 2:
                    out.append(v)
                return
            if isinstance(value, list):
                for i in value:
                    add(i)
                return
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in self._ANSWER_KEYS or k in ("acceptable_variations", "error_examples", "target_item"):
                        add(v)
                return

        add(node.learning_targets)
        cp = node.content_pack or {}
        add(cp.get("target_item"))
        add(cp.get("examples"))
        add(cp.get("minimal_examples"))
        add(cp.get("exercises"))
        add(cp.get("quiz_items"))
        add(cp.get("micro_exercise"))

        # MCQ correct option.
        quiz_items = cp.get("quiz_items", [])
        if isinstance(quiz_items, list):
            for item in quiz_items:
                if not isinstance(item, dict):
                    continue
                options = item.get("options", [])
                idx = item.get("correct_index")
                if isinstance(options, list) and isinstance(idx, int) and 0 <= idx < len(options):
                    add(options[idx])

        # Common mistakes: correct side is a valid expected answer.
        common = cp.get("common_mistakes", {})
        if isinstance(common, dict):
            errs = common.get("error_examples", [])
            if isinstance(errs, list):
                for item in errs:
                    if isinstance(item, dict):
                        add(item.get("correct"))

        dedup: list[str] = []
        seen = set()
        for item in out:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
        return dedup[:50]

    def _semantic_similarity(self, student_text: str, candidates: list[str], target_lang: str) -> float:
        if not candidates:
            return 0.0

        student_norm = self._normalize_text(student_text)
        if not student_norm:
            return 0.0

        lang = self._canonical_lang(target_lang)
        use_char_mode = lang in {"zh", "ja", "ko"}

        best = 0.0
        for c in candidates:
            cand_norm = self._normalize_text(c)
            if not cand_norm:
                continue
            seq = self._text_similarity(student_norm, cand_norm)
            if use_char_mode:
                jac = self._char_ngram_jaccard(student_norm, cand_norm, n=2)
                score = 0.3 * seq + 0.7 * jac
            else:
                jac = self._token_jaccard(student_norm, cand_norm)
                score = 0.55 * seq + 0.45 * jac
            if score > best:
                best = score
        return best

    # ------------------------------------------------------------------
    # Confidence / fatigue / engagement
    # ------------------------------------------------------------------

    def _estimate_confidence(
        self,
        text: str,
        audio_features: dict,
        semantic_similarity: float = 0.0,
        error_severity: float = 0.0,
        pronunciation_score: float = 0.5,
    ) -> float:
        confidence = 0.5

        word_count = len(text.split())
        if word_count > 10:
            confidence += 0.2
        elif word_count < 3:
            confidence -= 0.2

        if any(h in text.lower() for h in self._HEDGE_TERMS):
            confidence -= 0.15

        latency = audio_features.get("latency_ms", 0)
        if latency > 3000:
            confidence -= 0.1
        if audio_features.get("self_correction_count", 0) > 0:
            confidence -= 0.1

        asr_conf = self._extract_fraction(audio_features, ("asr_confidence", "speech_confidence"))
        if asr_conf is not None:
            confidence += (asr_conf - 0.5) * 0.2

        confidence += (semantic_similarity - 0.5) * 0.25
        confidence += (pronunciation_score - 0.5) * 0.15
        confidence -= error_severity * 0.25

        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _estimate_fatigue(audio_features: dict, hot: HotMemory) -> float:
        fatigue = 0.0
        fatigue += hot.turn_number * 0.015
        silence = audio_features.get("silence_before_ms", 0)
        if silence > 5000:
            fatigue += 0.15
        return min(1.0, fatigue)

    @staticmethod
    def _estimate_engagement(text: str, audio_features: dict, hot: HotMemory) -> float:
        engagement = 0.5

        word_count = len(text.split())
        if word_count > 15:
            engagement += 0.2
        elif word_count < 3:
            engagement -= 0.2

        if "?" in text:
            engagement += 0.15

        speaking_rate = audio_features.get("speech_rate_wpm", 0) or 0
        if speaking_rate >= 120:
            engagement += 0.05
        elif 0 < speaking_rate < 70:
            engagement -= 0.08

        latency = audio_features.get("latency_ms", 0) or 0
        if latency > 4500:
            engagement -= 0.1

        return max(0.0, min(1.0, engagement))

    # ------------------------------------------------------------------
    # Language + text utilities
    # ------------------------------------------------------------------

    def _resolve_target_lang(self, audio_features: dict, node: LiveNode, fallback_lang: str) -> str:
        lang = self._extract_lang_hint(audio_features, self._LANG_HINT_KEYS)
        if lang:
            return lang
        if node.target_language:
            return node.target_language
        content = node.content_pack or {}
        if isinstance(content, dict):
            lang = self._extract_lang_hint(content, self._LANG_HINT_KEYS)
            if lang:
                return lang
        return fallback_lang

    def _resolve_l1_lang(self, audio_features: dict, node: LiveNode) -> str:
        lang = self._extract_lang_hint(audio_features, self._L1_HINT_KEYS)
        if lang:
            return lang
        if node.source_language:
            return node.source_language
        content = node.content_pack or {}
        if isinstance(content, dict):
            lang = self._extract_lang_hint(content, self._L1_HINT_KEYS)
            if lang:
                return lang
        return ""

    @staticmethod
    def _extract_lang_hint(data: dict, keys: set[str]) -> str:
        if not isinstance(data, dict):
            return ""
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _detect_text_lang(text: str) -> str:
        if re.search(r"[\u3040-\u30ff]", text):
            return "ja"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[а-яА-Я]", text):
            return "ru"
        if re.search(r"[äöüß]", text.lower()):
            return "de"
        if re.search(r"[àâçéèêëîïôûùüÿœ]", text.lower()):
            return "fr"
        if re.search(r"[áéíóúñ¿¡]", text.lower()):
            return "es"
        return "en"

    @staticmethod
    def _canonical_lang(lang: str) -> str:
        l = (lang or "").strip().lower()
        if l.startswith("zh"):
            return "zh"
        if l.startswith("ja"):
            return "ja"
        if l.startswith("ko"):
            return "ko"
        if l.startswith("en"):
            return "en"
        if l.startswith("es"):
            return "es"
        if l.startswith("fr"):
            return "fr"
        if l.startswith("de"):
            return "de"
        if l.startswith("ru"):
            return "ru"
        return l or "en"

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"[^\w\s\u4e00-\u9fff\u3040-\u30ff]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        t = AssessmentEngine._normalize_text(text)
        if not t:
            return []
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", t):
            return list(t.replace(" ", ""))
        return t.split()

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _token_jaccard(self, a: str, b: str) -> float:
        ta = set(self._tokenize(a))
        tb = set(self._tokenize(b))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    @staticmethod
    def _char_ngram_jaccard(a: str, b: str, n: int = 2) -> float:
        def grams(s: str) -> set[str]:
            s = s.replace(" ", "")
            if not s:
                return set()
            if len(s) < n:
                return {s}
            return {s[i:i + n] for i in range(len(s) - n + 1)}

        ga = grams(a)
        gb = grams(b)
        if not ga or not gb:
            return 0.0
        return len(ga & gb) / len(ga | gb)

    @staticmethod
    def _extract_fraction(audio_features: dict, keys: tuple[str, ...]) -> Optional[float]:
        for key in keys:
            if key not in audio_features:
                continue
            raw = audio_features.get(key)
            if raw is None:
                continue
            value = float(raw)
            if value > 1.0:
                value = value / 100.0
            return max(0.0, min(1.0, value))
        return None

    def _extract_pronunciation_score(self, audio_features: dict) -> Optional[float]:
        return self._extract_fraction(
            audio_features,
            ("pronunciation_score", "pronunciation_accuracy", "gop_score", "pron_score"),
        )
