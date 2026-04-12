"""
Build a teaching curriculum from LinguaLearnContent + learner profile.

The curriculum decides, per sentence:
  - Focus areas (vocab / grammar / culture / pronunciation / pragmatics / shadow)
  - How deep to go based on learner level and target language
  - Whether shadow-reading should be triggered
  - L1-specific transfer risks for the teacher to watch for
  - Content-type–specific teaching tips

All language logic is delegated to content.language_profiles so this file
stays clean and extensible.

SLA principles integrated:
  - Krashen i+1: difficulty calibrated to learner level
  - Swain Output: shadow + production tasks scheduled based on difficulty
  - Interaction Hypothesis: pragmatics focus for dialogic content types
  - Spaced Retrieval: revisit notes flagged for high-difficulty vocab
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from content.language_profiles import (
    LanguageProfile,
    TransferProfile,
    GrammarPattern,
    CultureTrigger,
    get_language_profile,
    get_content_type_profile,
    get_transfer_profile,
    get_grammar_patterns_for_lang,
    get_culture_triggers_for_lang,
    detect_content_type,
)

if TYPE_CHECKING:
    from content.loader import LinguaLearnContent, SentenceData
    from session.learner_profile import LearnerProfile

logger = logging.getLogger(__name__)

_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _level_idx(level: str) -> int:
    try:
        return _LEVEL_ORDER.index(level.upper())
    except ValueError:
        return 2  # default B1


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SentencePlan:
    sentence_index: int
    focus_areas: list[str]       # vocab | grammar | culture | pronunciation | pragmatics
    key_vocab: list[str]         # prioritised vocab words to emphasise
    grammar_point: str           # detected grammar pattern label
    grammar_hint: str            # brief hint for how to explain this grammar point
    culture_note: str            # cultural background for this sentence
    pronunciation_note: str      # phonology tip for this specific sentence
    pragmatics_note: str         # speech-act / register note (for dialogic content)
    l1_transfer_warning: str     # L1-interference risk teacher should watch for
    content_type_tip: str        # content-type–specific teaching move
    should_shadow: bool          # ask learner to shadow-read this sentence
    difficulty_note: str         # teacher-facing difficulty assessment


@dataclass
class Curriculum:
    job_id: str
    learner_id: str
    target_language: str
    content_type: str            # news | movie | tv_show | interview | documentary | daily_life | short_video | unknown
    intro_note: str              # Opening instruction for the teacher
    sentences_plan: list[SentencePlan]
    review_note: str             # Closing review instruction
    total_sentences: int
    teaching_approach_note: str  # Overall approach for this content type

    def get_plan(self, sentence_index: int) -> SentencePlan | None:
        for sp in self.sentences_plan:
            if sp.sentence_index == sentence_index:
                return sp
        return None

    def to_summary(self) -> str:
        lang_profile = get_language_profile(self.target_language)
        lang_name = lang_profile["display_name"]
        ct_profile = get_content_type_profile(self.content_type)
        ct_label = ct_profile["label"]

        lines = [
            f"课程大纲 [{lang_name} · {ct_label} · 共{self.total_sentences}句]",
            f"教学方向：{self.teaching_approach_note[:80]}",
        ]
        for sp in self.sentences_plan:
            focus = "、".join(sp.focus_areas) or "通读"
            entry = f"  句{sp.sentence_index + 1}：重点={focus}"
            if sp.grammar_point:
                entry += f"，语法={sp.grammar_point}"
            if sp.should_shadow:
                entry += "，需跟读"
            if sp.l1_transfer_warning:
                entry += f"，⚠️{sp.l1_transfer_warning[:30]}"
            lines.append(entry)
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Curriculum Builder
# ──────────────────────────────────────────────────────────────────────────────

class CurriculumBuilder:
    """
    Build a Curriculum without an LLM call — purely rule-based, language-aware.

    Corner cases handled:
      - Empty vocab list on a sentence
      - Very short sentences (< 2 seconds)
      - Very long sentences (> 10 seconds)
      - No grammar pattern detected
      - Unknown content type
      - Missing L1 transfer profile
      - Learner at advanced level (C1/C2) — shift focus from vocab to discourse/pragmatics
      - Learner at beginner level (A1) — minimal overload, one focus at a time
      - Multiple grammar patterns in one sentence — pick the most pedagogically relevant
    """

    @classmethod
    def build(
        cls,
        content: "LinguaLearnContent",
        learner_profile: "LearnerProfile",
    ) -> Curriculum:
        level_idx = _level_idx(learner_profile.level)
        target_lang = content.target_lang  # e.g. "en", "ja"
        l1 = learner_profile.l1            # e.g. "zh"

        # Resolve profiles from knowledge base
        lang_profile = get_language_profile(target_lang)
        transfer_profile = get_transfer_profile(l1, target_lang)
        grammar_patterns = get_grammar_patterns_for_lang(target_lang)
        culture_triggers = get_culture_triggers_for_lang(target_lang)

        # Content type: prefer explicit field if loader set it, else detect
        content_type = getattr(content, "content_type", None) or detect_content_type(
            content.title, content.brief
        )
        ct_profile = get_content_type_profile(content_type)

        sentences_plan: list[SentencePlan] = []

        for sentence in content.sentences:
            plan = cls._build_sentence_plan(
                sentence=sentence,
                level_idx=level_idx,
                lang_profile=lang_profile,
                transfer_profile=transfer_profile,
                grammar_patterns=grammar_patterns,
                culture_triggers=culture_triggers,
                ct_profile=ct_profile,
                content_type=content_type,
            )
            sentences_plan.append(plan)

        # Intro note
        lang_name = lang_profile["display_name_en"]
        ct_label = ct_profile["label_en"]
        level_name = learner_profile.level
        intro_note = cls._build_intro_note(
            lang_name=lang_name,
            ct_label=ct_label,
            ct_profile=ct_profile,
            level_name=level_name,
            sentence_count=content.sentence_count,
            lang_profile=lang_profile,
        )

        review_note = cls._build_review_note(
            ct_profile=ct_profile,
            level_idx=level_idx,
            lang_profile=lang_profile,
            transfer_profile=transfer_profile,
        )

        return Curriculum(
            job_id=content.job_id,
            learner_id=learner_profile.learner_id,
            target_language=target_lang,
            content_type=content_type,
            intro_note=intro_note,
            sentences_plan=sentences_plan,
            review_note=review_note,
            total_sentences=content.sentence_count,
            teaching_approach_note=ct_profile["teaching_approach"][:120],
        )

    # ── Sentence-level plan ────────────────────────────────────────────────────

    @classmethod
    def _build_sentence_plan(
        cls,
        sentence: "SentenceData",
        level_idx: int,
        lang_profile: LanguageProfile,
        transfer_profile: TransferProfile | None,
        grammar_patterns: list[GrammarPattern],
        culture_triggers: list[CultureTrigger],
        ct_profile: dict,
        content_type: str,
    ) -> SentencePlan:
        focus_areas: list[str] = []
        grammar_point = ""
        grammar_hint = ""
        culture_note = ""
        pronunciation_note = ""
        pragmatics_note = ""
        l1_transfer_warning = ""
        content_type_tip = ""

        # ── 1. Vocabulary focus ──────────────────────────────────────────────
        # Always for A1-B2; advanced learners focus on difficult/unusual vocab
        if level_idx <= 3 or any(v.difficulty >= 4 for v in sentence.vocab):
            if sentence.vocab:
                focus_areas.append("vocab")

        # ── 2. Grammar detection ─────────────────────────────────────────────
        # Try all patterns for this language, pick most pedagogically relevant
        # (first match wins; patterns are ordered by teaching priority in profiles)
        best_grammar = None
        for gp in grammar_patterns:
            if gp["pattern"].search(sentence.text):
                best_grammar = gp
                break
        if best_grammar:
            grammar_point = best_grammar["label"]
            grammar_hint = best_grammar["explanation_hint"]
            if "grammar" not in focus_areas:
                focus_areas.append("grammar")

        # ── 3. Culture triggers ──────────────────────────────────────────────
        for ct in culture_triggers:
            if ct["pattern"].search(sentence.text):
                culture_note = ct["note"]
                if "culture" not in focus_areas:
                    focus_areas.append("culture")
                break  # one culture note per sentence

        # ── 4. Pronunciation focus ───────────────────────────────────────────
        long_sentence = sentence.duration > 5.0
        very_long_sentence = sentence.duration > 10.0
        has_hard_vocab = any(v.difficulty >= 4 for v in sentence.vocab)
        beginner = level_idx <= 2  # A1/A2/B1

        if long_sentence and (beginner or has_hard_vocab):
            focus_areas.append("pronunciation")
            pronunciation_note = lang_profile.get("shadow_notes", "")[:120]

        # ── 5. Pragmatics focus (for dialogic content types) ─────────────────
        if ct_profile.get("pragmatics_focus") and level_idx >= 2:  # B1+
            pragmatics_note = cls._detect_pragmatics(sentence.text, content_type)
            if pragmatics_note and "pragmatics" not in focus_areas:
                focus_areas.append("pragmatics")

        # ── 6. L1 transfer warning ────────────────────────────────────────────
        if transfer_profile:
            # Pick the most relevant transfer risk based on detected grammar point
            risks = transfer_profile.get("interference_risks", [])
            if grammar_point and risks:
                # Heuristic: find a risk that mentions a keyword from the grammar label
                gp_keywords = set(grammar_point.lower().split("(")[0].split())
                matched = next(
                    (r for r in risks if any(kw in r.lower() for kw in gp_keywords)),
                    None,
                )
                l1_transfer_warning = matched or (risks[0] if risks else "")
            elif risks:
                l1_transfer_warning = risks[0]

        # ── 7. Content-type–specific teaching tip ────────────────────────────
        ct_foci = ct_profile.get("key_pedagogical_foci", [])
        if ct_foci:
            # Select a tip relevant to what's in this sentence
            content_type_tip = ct_foci[min(sentence.index % len(ct_foci), len(ct_foci) - 1)]

        # ── 8. Shadow reading ─────────────────────────────────────────────────
        should_shadow = (
            ct_profile.get("shadow_suitable", True)
            and long_sentence
            and (beginner or level_idx == 3)  # A1–B2 benefit most from shadowing
        )
        # Very long sentences: shadow even at B2
        if very_long_sentence and level_idx <= 4:
            should_shadow = True

        # ── 9. Corner case: no focus areas at all ────────────────────────────
        if not focus_areas:
            if level_idx >= 4:  # C1/C2
                focus_areas = ["discourse", "style"]
            else:
                focus_areas = ["comprehension"]

        # ── 10. Corner case: beginner overload guard ──────────────────────────
        # A1 learners: max 2 focus areas to avoid cognitive overload
        if level_idx == 0 and len(focus_areas) > 2:
            focus_areas = focus_areas[:2]

        # ── 11. Key vocab selection ───────────────────────────────────────────
        key_vocab = _select_key_vocab(sentence, level_idx)

        # ── 12. Difficulty note for teacher ──────────────────────────────────
        difficulty_note = _compute_difficulty_note(sentence, level_idx, lang_profile)

        return SentencePlan(
            sentence_index=sentence.index,
            focus_areas=focus_areas,
            key_vocab=key_vocab,
            grammar_point=grammar_point,
            grammar_hint=grammar_hint,
            culture_note=culture_note,
            pronunciation_note=pronunciation_note,
            pragmatics_note=pragmatics_note,
            l1_transfer_warning=l1_transfer_warning,
            content_type_tip=content_type_tip,
            should_shadow=should_shadow,
            difficulty_note=difficulty_note,
        )

    # ── Pragmatics detection ───────────────────────────────────────────────────

    @staticmethod
    def _detect_pragmatics(text: str, content_type: str) -> str:
        """Detect speech act or pragmatic function in a sentence."""
        import re
        lower = text.lower()

        # Apology
        if re.search(r"\b(sorry|apologize|excuse me|pardon|entschuldigung|désolé|lo siento|извини)\b", lower):
            return "道歉语用行为(apology speech act)：注意语境和诚意程度对语言形式的影响。"

        # Request / instruction
        if re.search(r"\b(please|could you|would you|can you|bitte|s'il vous plaît|por favor|пожалуйста)\b", lower):
            return "请求语用行为：注意礼貌程度和间接请求的语用策略。"

        # Refusal
        if re.search(r"\b(can't|won't|impossible|refuse|afraid not|no way|unfortunately)\b", lower):
            return "拒绝策略：注意如何礼貌地拒绝——直接vs.间接，以及文化差异。"

        # Disagreement / challenge
        if re.search(r"\b(actually|however|on the contrary|in fact|but|although|despite)\b", lower):
            return "异议/转折表达：注意说话人如何用语言标记立场转换或提出不同观点。"

        # Expressing emotion / emphasis
        if re.search(r"[!]{1,}|(!.*){2,}|\b(absolutely|definitely|incredible|amazing|terrible)\b", lower):
            return "情感强化表达：注意说话人用哪些语言手段来强化或表达情绪。"

        # Hedging
        if re.search(r"\b(maybe|perhaps|might|probably|seems|I think|I guess|sort of|kind of)\b", lower):
            return "模糊语言/推测表达(hedging)：说话人不确定时如何软化陈述——在正式场合非常重要。"

        # Content type specific
        if content_type in ("interview", "tv_show", "movie"):
            return "注意这句台词的语用功能：它在对话中起什么作用(推进情节/建立关系/传达态度)?"

        return ""

    # ── Intro / review notes ───────────────────────────────────────────────────

    @classmethod
    def _build_intro_note(
        cls,
        lang_name: str,
        ct_label: str,
        ct_profile: dict,
        level_name: str,
        sentence_count: int,
        lang_profile: LanguageProfile,
    ) -> str:
        key_challenges = lang_profile.get("key_challenges", [])
        top_challenges = "、".join(key_challenges[:3]) if key_challenges else "语言表达"

        return (
            f"【课程简介】本课内容：{lang_name} {ct_label}，共{sentence_count}句。"
            f"学习者水平：{level_name}。\n"
            f"【教学策略】{ct_profile['teaching_approach']}\n"
            f"【{lang_name}核心挑战】{top_challenges}。\n"
            f"【文化提示】{ct_profile['culture_tips']}\n"
            f"教学流程：先完整播放视频建立整体理解，再逐句精读拆解。"
        )

    @classmethod
    def _build_review_note(
        cls,
        ct_profile: dict,
        level_idx: int,
        lang_profile: LanguageProfile,
        transfer_profile: TransferProfile | None,
    ) -> str:
        review_tasks: list[str] = []

        # Universal: summary in target language
        review_tasks.append("请学习者用目标语言（不是母语）总结视频主要内容（2–3句话）")

        # Level-dependent review tasks
        if level_idx <= 1:  # A1/A2
            review_tasks.append("复习本节重点词汇，让学习者造一个新句子")
        elif level_idx <= 3:  # B1/B2
            review_tasks.append("选出本节最难的1–2个语法点，用新例子帮学习者巩固")
            if ct_profile.get("pragmatics_focus"):
                review_tasks.append("引导学习者在角色扮演中使用本节的关键表达")
        else:  # C1/C2
            review_tasks.append("讨论内容的语体风格和文化背景，引导批判性分析")
            review_tasks.append("探讨语言选择背后的意图（为什么说话人用这个词/结构而非其他）")

        # L1 transfer: remind teacher to check common errors
        if transfer_profile and transfer_profile.get("interference_risks"):
            top_risk = transfer_profile["interference_risks"][0]
            review_tasks.append(f"特别检查：{top_risk}（该学习者L1迁移高风险点）")

        tasks_str = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(review_tasks))
        return f"【复习阶段任务】\n{tasks_str}\n教师最后给予鼓励并预告下节课内容。"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _select_key_vocab(sentence: "SentenceData", level_idx: int) -> list[str]:
    """
    Select the most pedagogically relevant vocab words for this sentence.

    Rules:
    - Beginner (A1/A2): prefer lower difficulty (2–3), max 3 words
    - Intermediate (B1/B2): prefer medium-high difficulty (3–4), max 4 words
    - Advanced (C1/C2): prefer highest difficulty (4–5) or unusual collocations, max 3 words
    """
    if not sentence.vocab:
        return []

    if level_idx <= 1:  # A1/A2
        candidates = [v for v in sentence.vocab if 2 <= v.difficulty <= 3]
        if not candidates:
            candidates = sentence.vocab
        return [v.word for v in sorted(candidates, key=lambda v: v.difficulty)][:3]

    elif level_idx <= 3:  # B1/B2
        candidates = [v for v in sentence.vocab if v.difficulty >= 3]
        if not candidates:
            candidates = sentence.vocab
        return [v.word for v in sorted(candidates, key=lambda v: -v.difficulty)][:4]

    else:  # C1/C2
        candidates = [v for v in sentence.vocab if v.difficulty >= 4]
        if not candidates:
            candidates = [v for v in sentence.vocab if v.difficulty >= 3]
        if not candidates:
            candidates = sentence.vocab
        return [v.word for v in sorted(candidates, key=lambda v: -v.difficulty)][:3]


def _compute_difficulty_note(
    sentence: "SentenceData",
    level_idx: int,
    lang_profile: LanguageProfile,
) -> str:
    """Generate a teacher-facing difficulty note for the sentence."""
    if not sentence.vocab:
        avg_diff = 0.0
    else:
        avg_diff = sum(v.difficulty for v in sentence.vocab) / len(sentence.vocab)

    # Sentence duration as complexity proxy
    duration = sentence.duration
    is_long = duration > 6.0
    is_very_long = duration > 10.0

    # Base difficulty assessment
    parts: list[str] = []

    if avg_diff >= 4.2:
        parts.append("词汇难度高——建议分散讲解，不要一次性全部列出")
    elif avg_diff >= 2.8:
        parts.append("词汇难度适中")
    elif avg_diff > 0:
        parts.append("词汇较简单——可将重心放在语法、语用或文化上")

    if is_very_long:
        parts.append("句子很长(>10s)——考虑分段讲解，先抓主干再讲细节")
    elif is_long:
        parts.append("句子较长(>6s)——适合跟读练习")

    # Level calibration note
    level_names = ["A1", "A2", "B1", "B2", "C1", "C2"]
    level_name = level_names[level_idx] if level_idx < len(level_names) else "B1"
    if avg_diff > 3.5 and level_idx <= 1:
        parts.append(f"⚠️ 该句对{level_name}学习者偏难——选择1–2个核心词讲解，其余点到为止")
    elif avg_diff < 2.0 and level_idx >= 4:
        parts.append(f"该句对{level_name}学习者语言层面较简单——可深入讨论话语风格/文化含义")

    return "；".join(parts) if parts else "难度适中，正常讲解。"
