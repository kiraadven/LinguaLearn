"""
Comprehensive language-specific teaching profiles for the AI Tutor.

Grounded in Second Language Acquisition (SLA) research:
- Krashen: i+1 Input Hypothesis, Affective Filter, Natural Order
- Swain: Output Hypothesis (pushed output, noticing the gap)
- Long: Interaction Hypothesis (negotiation of meaning, recasts)
- Schmidt: Noticing Hypothesis (conscious attention accelerates acquisition)
- Spaced Retrieval Practice (Morgan-Short, Carpenter)
- Authentic Materials Pedagogy / TBLT (Task-Based Language Teaching)
- Shadowing (Murphey, Field) for prosody and pronunciation

Supported target languages: en, zh, ja, ko, de, fr, es, ru
Supported L1 backgrounds:  en, zh, ja, ko, de, fr, es, ru (and generic fallback)
Content types: news, movie, tv_show, interview, documentary, daily_life,
               short_video, unknown
"""
from __future__ import annotations

import re
from typing import TypedDict


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONTENT TYPE PROFILES
#    Each type defines how to frame the learning experience, what to emphasize,
#    and pedagogical tips for the AI teacher.
# ═══════════════════════════════════════════════════════════════════════════════

CONTENT_TYPE_PROFILES: dict[str, dict] = {
    "news": {
        "label": "新闻报道",
        "label_en": "News Report",
        "register": "formal",
        "speech_style": "scripted / anchor-read",
        "key_pedagogical_foci": [
            "formal register and journalism-specific vocabulary",
            "passive voice and impersonal constructions common in news",
            "reported speech (said that / according to)",
            "dense noun phrases and nominalization",
            "hedging language (allegedly, reportedly, officials said)",
            "abbreviations, acronyms, and proper nouns (agencies, places, titles)",
            "sentence structure: topic–comment, inverted pyramid",
        ],
        "teaching_approach": (
            "Use the news context to anchor vocabulary in real-world significance. "
            "Activate prior knowledge about the topic before playing the clip. "
            "Treat the headline/title as a prediction prompt. "
            "After listening: comprehension-check → vocab deep-dive → grammar analysis → "
            "critical discussion (what is the source? what is missing?)."
        ),
        "culture_tips": (
            "Discuss the media landscape of the target-language country. "
            "Draw attention to reporting conventions that differ across cultures "
            "(e.g., directness in US news vs. indirectness in Japanese broadcasting). "
            "Highlight politically sensitive vocabulary or culture-specific references "
            "(government bodies, legal terms, units of measurement)."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": False,
        "typical_difficulty_offset": 0,  # relative to learner level
        "intro_frame": (
            "今天我们要学一段{lang_label}新闻，这类内容用词比较正式，"
            "有很多新闻特有的表达。先整体看一遍感受内容，然后我们逐句精读。"
        ),
    },
    "movie": {
        "label": "电影片段",
        "label_en": "Movie Clip",
        "register": "varied (dramatic / colloquial / elevated)",
        "speech_style": "scripted but naturalistic, emotionally charged",
        "key_pedagogical_foci": [
            "character-specific speech style (idiolect)",
            "emotional and attitudinal language",
            "colloquial contractions and reductions",
            "pragmatic acts: requests, refusals, apologies, threats",
            "subtext and implication (what is NOT said)",
            "cultural stereotypes or references embedded in dialogue",
            "genre conventions (thriller vocabulary vs. romance vocabulary)",
        ],
        "teaching_approach": (
            "Set scene context before playing: who are these characters? "
            "what is their relationship? what just happened? "
            "Focus on WHY characters speak the way they do (power, emotion, genre). "
            "Use role-play to let learners practice the speech acts in the clip. "
            "Highlight lines that are frequently quoted or culturally iconic."
        ),
        "culture_tips": (
            "Discuss the cultural context of the film (era, country, social class). "
            "Point out humor, irony, or sarcasm that may not translate. "
            "Explain cultural references, historical events, or social norms depicted. "
            "Note regional accents or dialects if present."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": True,
        "typical_difficulty_offset": -1,  # often slightly easier than pure news
        "intro_frame": (
            "今天的材料来自一部{lang_label}电影，对话会更口语、更有情感。"
            "我们先看一遍感受一下场景氛围，然后深入分析台词和表达。"
        ),
    },
    "tv_show": {
        "label": "电视剧/剧集",
        "label_en": "TV Series / Drama",
        "register": "informal to semi-formal",
        "speech_style": "naturalistic dialogue, overlapping, interrupted speech",
        "key_pedagogical_foci": [
            "everyday conversational patterns",
            "filler words and discourse markers (well, you know, like, I mean)",
            "episode-internal references (character backstory, running jokes)",
            "genre-specific language (medical, legal, procedural shows)",
            "humor, irony, and sarcasm",
            "informal grammar (ellipsis, reduction, non-standard forms)",
            "relationship dynamics expressed through language choices",
        ],
        "teaching_approach": (
            "Briefly explain the show's premise and character relationships. "
            "Focus on natural speech phenomena: reductions, contractions, overlaps. "
            "Use the episode context to practice pragmatics and social language. "
            "Contrast formal vs. informal register within the same episode."
        ),
        "culture_tips": (
            "TV shows are windows into everyday cultural life. "
            "Point out how social relationships are encoded in language choices. "
            "Discuss current slang or trending expressions from the show. "
            "Compare how the same social situation would play out in the learner's culture."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": True,
        "typical_difficulty_offset": -1,
        "intro_frame": (
            "今天我们看一段{lang_label}电视剧的片段，对话非常贴近日常生活。"
            "注意里面的口语表达和人物之间的互动方式。"
        ),
    },
    "interview": {
        "label": "采访/访谈",
        "label_en": "Interview / Talk",
        "register": "semi-formal",
        "speech_style": "spontaneous speech, turn-taking, hedging",
        "key_pedagogical_foci": [
            "interview question formation (open vs. closed questions)",
            "hedging and epistemic language (I think, perhaps, as far as I know)",
            "turn-taking signals (well, so, right, anyway)",
            "self-repair and reformulation (what I mean is...)",
            "professional register with personal voice",
            "discourse structure: topic introduction, elaboration, conclusion",
            "authentic non-fluencies (pauses, hesitations, fillers) in spontaneous speech",
        ],
        "teaching_approach": (
            "Preview: who is the interviewer and interviewee? what is the purpose? "
            "Focus on HOW ideas are expressed, not just WHAT is said. "
            "Analyze the question techniques used by the interviewer. "
            "Practice: learner reformulates one answer in their own words."
        ),
        "culture_tips": (
            "Interview norms differ across cultures: "
            "some cultures expect direct confrontational questions, others prefer deference. "
            "Discuss the power dynamics: is the interviewer aggressive or deferential? "
            "Highlight culture-specific politeness strategies."
        ),
        "shadow_suitable": False,  # spontaneous speech harder to shadow
        "pragmatics_focus": True,
        "typical_difficulty_offset": 0,
        "intro_frame": (
            "今天我们看一段{lang_label}采访视频，是真实的对话录像，"
            "注意采访中使用的问题方式和受访者的回应策略。"
        ),
    },
    "documentary": {
        "label": "纪录片",
        "label_en": "Documentary",
        "register": "formal to semi-formal",
        "speech_style": "narrated voiceover + interview segments",
        "key_pedagogical_foci": [
            "academic and domain-specific vocabulary",
            "narrative structure and cohesive devices",
            "cause-and-effect language (as a result, consequently, which led to)",
            "contrast and concession (however, although, despite)",
            "factual language and hedging in scientific claims",
            "rhetorical questions and audience engagement devices",
            "time markers and historical sequencing",
        ],
        "teaching_approach": (
            "Pre-teach 3–5 key domain terms before watching. "
            "After watching: comprehension → analysis of argument structure → "
            "critical thinking (what evidence is given? is it persuasive?). "
            "Encourage learners to summarize the main argument in their own words."
        ),
        "culture_tips": (
            "Documentaries reflect cultural priorities and narratives. "
            "Discuss the perspective or bias of the documentary. "
            "Point out culture-specific values embedded in the narrator's framing. "
            "Compare how the same topic would be covered in the learner's culture."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": False,
        "typical_difficulty_offset": 1,  # typically harder vocabulary
        "intro_frame": (
            "今天我们看一段{lang_label}纪录片，内容比较专业，用词正式。"
            "先整体感知主题，然后我们重点学习关键词汇和表达方式。"
        ),
    },
    "daily_life": {
        "label": "生活片段/Vlog",
        "label_en": "Daily Life / Vlog",
        "register": "informal / colloquial",
        "speech_style": "casual, spontaneous, personally expressive",
        "key_pedagogical_foci": [
            "casual colloquialisms and slang",
            "regional or demographic dialect features",
            "personal narrative structures (telling stories)",
            "emotional expression and rapport-building language",
            "cultural daily routines and lifestyle vocabulary",
            "humor and self-expression",
            "authentic non-fluencies as normal features of speech",
        ],
        "teaching_approach": (
            "This content is highly motivating and culturally immersive. "
            "Embrace authentic messiness: non-standard forms are valid in this register. "
            "Focus on how to talk about everyday topics naturally. "
            "Use the content as a springboard: 'Do you do this in your country?'"
        ),
        "culture_tips": (
            "Daily life content reveals what people actually value and how they live. "
            "Discuss cultural differences in daily routines, food, relationships, humor. "
            "Point out informal taboos or sensitive topics the speaker avoids. "
            "Highlight culturally-specific objects, places, or customs shown."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": True,
        "typical_difficulty_offset": -1,
        "intro_frame": (
            "今天的内容很生活化，是真实的{lang_label}日常场景，"
            "会有很多地道的口语表达，放松来学。"
        ),
    },
    "short_video": {
        "label": "短视频/社交媒体",
        "label_en": "Short Video / Social Media",
        "register": "ultra-casual / internet language",
        "speech_style": "compressed, high-energy, trend-driven",
        "key_pedagogical_foci": [
            "internet slang and meme language",
            "abbreviations and neologisms",
            "fast speech and reductions",
            "visual-language integration (language that depends on visual context)",
            "humor styles: irony, self-deprecation, cultural jokes",
            "trending expressions and generational language",
            "code-switching and multilingual mixing",
        ],
        "teaching_approach": (
            "Acknowledge that this register differs from textbook norms — and that's OK. "
            "Discuss which expressions are appropriate in which contexts. "
            "Use the content as a cultural barometer: what do young speakers value/mock? "
            "Be cautious: fast speech may require multiple replays; don't shame learner."
        ),
        "culture_tips": (
            "Short video culture varies hugely by platform and country. "
            "Discuss what makes this content platform-specific. "
            "Point out humor, controversy, or trends specific to the culture. "
            "Note that some language here may be inappropriate in formal settings."
        ),
        "shadow_suitable": False,  # too fast / visual-dependent
        "pragmatics_focus": True,
        "typical_difficulty_offset": -2,  # vocab easy but register is tricky
        "intro_frame": (
            "今天这段是{lang_label}的社交媒体/短视频内容，语言非常口语化，"
            "可能有很多网络用语。我们一起来感受一下真实的年轻人是怎么说话的。"
        ),
    },
    "unknown": {
        "label": "视频内容",
        "label_en": "Video Content",
        "register": "varied",
        "speech_style": "varied",
        "key_pedagogical_foci": [
            "context-appropriate vocabulary",
            "natural speech patterns of the target language",
            "grammar structures present in the content",
            "cultural references relevant to the material",
        ],
        "teaching_approach": (
            "Adapt dynamically to the register and style of the content. "
            "Lead with comprehension before drilling into language details. "
            "Match your teaching depth and style to what you observe in the material."
        ),
        "culture_tips": (
            "Use whatever cultural context is available in the content. "
            "Draw the learner's attention to authentic cultural cues."
        ),
        "shadow_suitable": True,
        "pragmatics_focus": False,
        "typical_difficulty_offset": 0,
        "intro_frame": (
            "我们来看这段{lang_label}视频，先整体感受一遍，"
            "然后逐句深入学习。"
        ),
    },
}

# Keywords for content type auto-detection (from title / brief)
CONTENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "news": [
        "cnn", "bbc", "nbc", "abc", "fox news", "reuters", "ap news",
        "breaking", "report", "official", "spokesman", "minister", "president",
        "government", "election", "congress", "parliament", "crisis",
        "新闻", "报道", "播报", "记者", "NHK", "朝日", "央视",
        "NHK", "뉴스", "ARD", "ZDF", "TF1", "RFI", "RT",
    ],
    "movie": [
        "movie", "film", "cinema", "电影", "映画", "영화",
        "scene", "trailer", "hollywood", "bollywood",
    ],
    "tv_show": [
        "episode", "series", "season", "drama", "sitcom", "soap opera",
        "电视剧", "剧集", "连续剧", "ドラマ", "드라마",
        "Staffel", "Folge", "épisode", "série", "temporada",
    ],
    "interview": [
        "interview", "podcast", "talk show", "q&a", "discussion",
        "采访", "访谈", "对话", "インタビュー", "인터뷰",
        "Interview", "Gespräch", "entretien", "entrevista",
    ],
    "documentary": [
        "documentary", "docu", "纪录片", "ドキュメンタリー", "다큐",
        "Dokumentarfilm", "documentaire", "documental",
        "national geographic", "discovery",
    ],
    "daily_life": [
        "vlog", "daily", "routine", "日常", "生活", "ライフ", "일상",
        "Alltag", "quotidien", "diario",
    ],
    "short_video": [
        "tiktok", "reels", "shorts", "short video", "短视频", "短片",
        "ショート", "쇼츠", "viral", "trending",
    ],
}


def detect_content_type(title: str, brief: str) -> str:
    """Detect content type from title and brief text."""
    combined = (title + " " + brief).lower()
    scores: dict[str, int] = {ct: 0 for ct in CONTENT_TYPE_KEYWORDS}
    for ct, keywords in CONTENT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in combined:
                scores[ct] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LANGUAGE PROFILES
#    Per-target-language: grammar patterns, culture triggers, pronunciation,
#    teacher persona, and teaching approach notes.
# ═══════════════════════════════════════════════════════════════════════════════

class GrammarPattern(TypedDict):
    pattern: re.Pattern
    label: str           # short label for the teacher (e.g., "完成时态")
    explanation_hint: str  # what to tell the learner about this pattern


class CultureTrigger(TypedDict):
    pattern: re.Pattern
    note: str            # cultural background explanation


class LanguageProfile(TypedDict):
    display_name: str          # e.g., "英语 (English)"
    display_name_en: str       # e.g., "English"
    teacher_persona: str       # Teacher character description for LLM
    script_note: str           # Writing system overview
    phonology_note: str        # Pronunciation overview
    key_challenges: list[str]  # Main learning challenges for this language
    teaching_principles: list[str]  # Language-specific pedagogical notes
    grammar_patterns: list[GrammarPattern]
    culture_triggers: list[CultureTrigger]
    shadow_notes: str          # Notes on shadowing / pronunciation practice
    common_beginner_mistakes: list[str]


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {

    # ──────────────────────────────────────────────────────────────────────────
    "en": {
        "display_name": "英语 (English)",
        "display_name_en": "English",
        "teacher_persona": (
            "你是 Sarah Chen（陈晓薇），拥有TESOL认证、在上海生活多年的美国华裔英语教师。"
            "你的英语地道、自然，中文流利，能精准感知中文母语者在英语学习中的痛点。"
            "教学风格：热情但不夸张，用真实口语（缩略形式、自然停顿），从不说教科书套话。"
            "你会把学生说的话作为切入点，真诚地对学生感兴趣。"
        ),
        "script_note": "拉丁字母，26个字母，字母与发音对应关系不规则，需大量积累。",
        "phonology_note": (
            "英语有约44个音素（元辅音），重音位置影响词义。"
            "连读、弱读、缩略（gonna/wanna/kinda）在口语中极常见。"
            "语调（升调/降调）承载语用功能（问题/陈述/未完待续）。"
        ),
        "key_challenges": [
            "冠词（a/an/the）——中文无冠词，是持续痛点",
            "时态系统——英语12种时态，中文用时间词表达，无动词变形",
            "介词搭配——无规律可循，需整块记忆",
            "不规则动词变形（go→went, see→saw）",
            "强调句、倒装句等复杂句式",
            "连读/弱读导致听力理解困难",
            "phrasal verbs（短语动词）数量庞大",
        ],
        "teaching_principles": [
            "优先帮学生建立'语感'而非死背规则：用真实语境呈现结构。",
            "冠词错误：频率最高，用 recast 纠正，不要过度解释规则。",
            "时态讲解：配合时间线图示，强调上下文触发而非死背。",
            "phrasal verb：整块输入（chunk），不要拆开解释。",
            "听力：先确保理解，再解析快速语音现象（连读、弱读）。",
            "输出：每句话学完让学生用自己的话复述或回应，落实 Swain 输出假设。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"\b(have|has|had)\s+\w+ed\b|\b(have|has)\s+been\b", re.I),
             "label": "完成时态",
             "explanation_hint": "表示过去发生对现在有影响的事，强调'到目前为止'。"},
            {"pattern": re.compile(r"\b(was|were)\s+\w+ing\b", re.I),
             "label": "过去进行时",
             "explanation_hint": "过去某时刻正在进行的动作，常与简单过去时连用。"},
            {"pattern": re.compile(r"\bif\s+.+?(would|could|might)\b", re.I),
             "label": "条件句",
             "explanation_hint": "虚拟语气条件句，表示假设或与现实相反的情况。"},
            {"pattern": re.compile(r"\baccording to\b|\breportedly\b|\ballegedly\b|\bsupposedly\b", re.I),
             "label": "信息来源/报道语气",
             "explanation_hint": "新闻英语常用：转述信息时表明来源，降低绝对性。"},
            {"pattern": re.compile(r"\b\w+ed\s+by\b", re.I),
             "label": "被动语态",
             "explanation_hint": "强调动作承受者而非执行者，新闻和学术英语中高频。"},
            {"pattern": re.compile(r"\bnot\s+only\b.+?\bbut\s+(also)?\b", re.I),
             "label": "递进关联词",
             "explanation_hint": "强调两个并列重点，语气比 'and' 更强调。"},
            {"pattern": re.compile(r"\b(despite|although|even though|whereas|while)\b", re.I),
             "label": "让步/对比连词",
             "explanation_hint": "表示虽然/尽管，引出与预期相反的信息。"},
            {"pattern": re.compile(r"\b(as long as|provided that|unless)\b", re.I),
             "label": "条件状语",
             "explanation_hint": "表示'只要/除非'的条件关系，构建复杂句。"},
            {"pattern": re.compile(r"\b(used to|would)\s+\w+\b", re.I),
             "label": "过去习惯表达",
             "explanation_hint": "描述过去的规律性行为或习惯，现在已不再做。"},
            {"pattern": re.compile(r"\b(going to|gonna)\b|\bwill\b.{1,20}\bsoon\b", re.I),
             "label": "将来时表达",
             "explanation_hint": "going to表计划/已定意图，will表临时决定或预测。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"\bgrammy\b", re.I),
             "note": "格莱美奖(Grammy Awards)是美国录音艺术与科学学院颁发的最高音乐奖项。"},
            {"pattern": re.compile(r"\bsuper bowl\b", re.I),
             "note": "超级碗(Super Bowl)是美国最受关注的年度橄榄球总决赛，也是美国最重要的文化事件之一。"},
            {"pattern": re.compile(r"\bwall street\b|\bs&p\b|\bdow jones\b", re.I),
             "note": "华尔街是美国金融中心，道琼斯(Dow Jones)和标普500是美国主要股市指数。"},
            {"pattern": re.compile(r"\bar-15\b|\bglock\b|\bgun control\b", re.I),
             "note": "枪支文化是美国社会的敏感议题，第二修正案保障公民持枪权，各州法律不同。"},
            {"pattern": re.compile(r"\bfda\b|\bcdc\b", re.I),
             "note": "FDA(食品药品监督管理局)和CDC(疾控中心)是美国重要的联邦卫生机构。"},
            {"pattern": re.compile(r"\bbillboard\b", re.I),
             "note": "Billboard榜单是美国权威音乐排行榜，Billboard Hot 100和专辑榜是最有影响力的。"},
            {"pattern": re.compile(r"\biv league\b|\bharvard\b|\byale\b|\bstanford\b|\bmit\b", re.I),
             "note": "常青藤联盟(Ivy League)是美国顶尖私立大学联盟，在美国文化中代表精英教育。"},
            {"pattern": re.compile(r"\bthank(s)? ?giving\b", re.I),
             "note": "感恩节(Thanksgiving)是美国重大节日(11月第四个周四)，象征家庭团聚和感谢。"},
            {"pattern": re.compile(r"\bhip.hop\b|\brap\b|\brapper\b", re.I),
             "note": "嘻哈(Hip-hop)文化起源于1970年代美国非裔社区，包含rap、DJ、涂鸦、霹雳舞四大元素。"},
            {"pattern": re.compile(r"\bsuicide\b|\bmental health\b|\btherapy\b", re.I),
             "note": "心理健康在英语文化语境中：寻求治疗师帮助(therapy)在西方文化中正常化程度较高。"},
        ],
        "shadow_notes": (
            "英语跟读重点：①语调（intonation）—— 重读音节要明显；"
            "②连读（linking）—— 'want it' 读成 'wannit'；"
            "③弱读（reduction）—— 'and' → 'n'，'to' → 'tə'；"
            "④节奏（rhythm）—— 英语是重音计时语言，重音与重音之间的间隔相等。"
        ),
        "common_beginner_mistakes": [
            "遗漏冠词：'I have book' → 'I have a book'",
            "时态混淆：'Yesterday I go to school' → 'Yesterday I went'",
            "主谓不一致：'She don't know' → 'She doesn't know'",
            "介词错误：'on Monday' vs. 'in Monday'",
            "中式直译：'very very' → 'extremely' / 'very much'",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "zh": {
        "display_name": "中文 (普通话)",
        "display_name_en": "Mandarin Chinese",
        "teacher_persona": (
            "你是 李伟（Li Wei），普通话教学专家，持有对外汉语教师资格证(HSK考官资质)，"
            "在北京语言大学有十年教学经验。"
            "擅长帮助以英/日/韩/欧洲语言为母语的学习者突破汉语语音和语法难关。"
            "教学风格：耐心细致，善用对比分析，让学生通过真实对话习得汉语。"
        ),
        "script_note": (
            "汉字系统：约3000字覆盖日常阅读，HSK6需掌握5000字。"
            "每个汉字是一个音节，声调是区分意义的关键。"
            "简体字(大陆/新加坡)与繁体字(台湾/香港)并存。"
        ),
        "phonology_note": (
            "普通话有4个声调+1个轻声，声调错误直接影响意义。"
            "拼音是辅助发音工具，但不是真实书写系统。"
            "送气与不送气辅音(p/b, t/d, k/g)是外国学习者常见难点。"
            "儿化音、儿音变调在北方口语中常见。"
        ),
        "key_challenges": [
            "四声声调——尤其是第三声的实际发音(低平调)和变调规则",
            "汉字书写与记忆——部首联想记忆法",
            "量词系统——一本书/一张纸/一条鱼，量词无规律",
            "补语系统——结果补语/方向补语/可能补语复杂",
            "把字句与被字句——与印欧语系的差异",
            "时间表达——无时态变化，靠时间词和语境判断",
            "语气助词——了/啊/嘛/呢/吧 的细微差别",
        ],
        "teaching_principles": [
            "声调先行：任何新词先确保声调准确，之后才关注意义。",
            "汉字教学：先认读再书写，部首帮助记忆字形。",
            "量词输入：配对记忆（不单独讲量词），'一+量词+名词' 整块输入。",
            "语境优先：用真实场景引出结构，不孤立讲语法规则。",
            "适量使用拼音：初级用拼音辅助，中级后逐渐脱离拼音依赖。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"把\s*\S+", re.I),
             "label": "把字句",
             "explanation_hint": "处置式：说明主语如何处置宾语，强调动作结果或影响。"},
            {"pattern": re.compile(r"被\s*\S+", re.I),
             "label": "被字句",
             "explanation_hint": "被动式：强调受事者，通常含有消极含义（受到不好的影响）。"},
            {"pattern": re.compile(r"是.+的$", re.I),
             "label": "是……的句式",
             "explanation_hint": "强调已发生事情的时间/地点/方式，而非事情本身。"},
            {"pattern": re.compile(r"虽然.+但(是)?", re.I),
             "label": "让步关系（虽然…但是）",
             "explanation_hint": "表示虽然前提成立，结论却与预期相反。"},
            {"pattern": re.compile(r"不但.+而且|既.+又", re.I),
             "label": "递进关系",
             "explanation_hint": "表示在前一个条件基础上，进一步强调另一点。"},
            {"pattern": re.compile(r"越来越|越.+越", re.I),
             "label": "越…越…结构",
             "explanation_hint": "表示随着某条件的发展，另一结果也随之变化。"},
            {"pattern": re.compile(r"一.+就", re.I),
             "label": "一……就……",
             "explanation_hint": "表示时序紧接或条件联动：'一……立刻就……'。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"春节|除夕|年夜饭", re.I),
             "note": "春节是中国最重要的传统节日（农历正月初一），家庭团聚和饺子/红包是核心文化元素。"},
            {"pattern": re.compile(r"高考", re.I),
             "note": "高考（全国统一高考）是中国最重要的考试，决定大学录取，对家庭和学生影响巨大。"},
            {"pattern": re.compile(r"面子|丢脸", re.I),
             "note": "面子(面子/mianzi)是中国文化核心概念，关乎社会地位和他人评价，影响许多社会行为。"},
            {"pattern": re.compile(r"微信|支付宝", re.I),
             "note": "微信/支付宝是中国最主流的社交和支付应用，在中国的渗透率和使用频率远超西方同类产品。"},
            {"pattern": re.compile(r"双十一|618", re.I),
             "note": "双十一(11.11)是阿里巴巴发起的网购节日，现已成为全球规模最大的购物节。"},
        ],
        "shadow_notes": (
            "普通话跟读重点：①四声准确性——跟读时夸张声调；"
            "②轻重格局——'北京'重在'京'，'桌子'轻声在'子'；"
            "③语流中的变调规则（三声+三声→二声+三声）；"
            "④语速与节奏——普通话是音节计时语言，每个音节时长相对均等。"
        ),
        "common_beginner_mistakes": [
            "声调错误：'māma mǎ mǎ' 四声不分",
            "量词遗漏：'一书' → '一本书'",
            "语序错误：时间状语位置（印欧语影响）",
            "语气词滥用或遗漏：学生常忘记'了/吧/呢'",
            "把字句与一般主谓宾句混淆",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "ja": {
        "display_name": "日语 (日本語)",
        "display_name_en": "Japanese",
        "teacher_persona": (
            "你是 田中由紀（Tanaka Yuki），日本语言文化学院的日语教师，"
            "持有日本语教育能力检定合格证书(相当于日语教学JLPT权威证书)。"
            "在东京大学留学生日语教育中心任教10年，擅长中文/英文母语学习者的日语指导。"
            "教学风格：温和细腻，注重文化与语言的结合，善用真实情境帮学生体会语感。"
        ),
        "script_note": (
            "日语有三套书写系统：平假名(ひらがな)、片假名(カタカナ)、汉字(漢字)。"
            "平假名和片假名各46个音节，学习者需全部掌握。"
            "常用汉字约2136个(人名用汉字约863个)。"
            "外来语用片假名书写，是现代日语重要组成部分。"
            "对中文母语学习者：汉字字形相似但读音和用法常有差异（要注意'日中同形异义词'）。"
        ),
        "phonology_note": (
            "日语是音节计时语言(mora-timed)，每个拍(モーラ)时长相近。"
            "音调(ピッチアクセント)在标准语中区分词义（雨あめ vs. 飴あめ）。"
            "长音、促音(っ)、拨音(ん)是发音关键。"
            "无辅音群，辅音+元音的CV结构是基础。"
        ),
        "key_challenges": [
            "SOV语序（主-宾-谓）——与英语/中文差异大",
            "格助词体系（は/が/を/に/で/へ/と/から/まで）",
            "动词活用：五段/一段/カ行/サ行 变形规则",
            "敬语体系(敬語)：尊敬语/谦让语/丁宁语三层",
            "平假名→片假名→汉字三套系统同时使用",
            "条件形(～たら/～ば/～と/～なら)的细微差别",
            "自动词与他动词对(開く/開ける)——中文无对应概念",
        ],
        "teaching_principles": [
            "格助词是日语逻辑框架：每次遇到助词，明确解释其功能和为何用此助词而非另一个。",
            "敬语分场合教学：先丁宁体(～です/～ます)，进阶后引入尊敬语/谦让语。",
            "汉字圈母语者优势：利用汉字共同基础建立词汇网络，同时警示'日中同形异义词'。",
            "动词活用：配合图表系统化，不要死记，要通过大量例句建立'感觉'。",
            "敬语文化：教语言的同时解释为什么使用(社会关系、上下级、内外之分)。",
            "语流中的音变：つ→っ、は(topic)发音为wa、へ(direction)发音为e。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"[てでたら]?(います|いる|おります)", re.I),
             "label": "テイル形（动作状态/继续）",
             "explanation_hint": "表示动作正在进行或其结果状态持续。中文'正在'或'已经……了'的对应。"},
            {"pattern": re.compile(r"[^っ](ました|ません|ませんでした)", re.I),
             "label": "丁宁体过去/否定",
             "explanation_hint": "礼貌体(丁宁语)的基础时态，正式场合必备。"},
            {"pattern": re.compile(r"(ので|から)(?=[、。\s])", re.I),
             "label": "原因从句(ので/から)",
             "explanation_hint": "から主观原因/理由，ので客观原因，语气更礼貌委婉。"},
            {"pattern": re.compile(r"(ても|でも)(?=\s*[^、。])", re.I),
             "label": "让步(～ても)",
             "explanation_hint": "即使……也……，表示前提成立结论仍不变。"},
            {"pattern": re.compile(r"(させて|てもらって|ていただいて)ください", re.I),
             "label": "礼貌请求表达",
             "explanation_hint": "高礼貌程度的请求表达，商务和正式场合必用。"},
            {"pattern": re.compile(r"(たら|れば|なら|と)(?=[、、\s])", re.I),
             "label": "条件形",
             "explanation_hint": "日语四种条件表达方式各有细微语用差异。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"敬語|です|ます|様|さん|君|ちゃん", re.I),
             "note": "日语敬语体系(敬語)反映严格的社会层级观念：内(うち)外(そと)、上下关系决定用语选择。"},
            {"pattern": re.compile(r"お疲れ様|よろしくお願い", re.I),
             "note": "这些是日本职场极常用的礼仪性表达，无法直译，体现日本集体协作文化。"},
            {"pattern": re.compile(r"花見|お盆|正月|初詣", re.I),
             "note": "日本重要的季节性习俗：赏花(花見)、盂兰盆节(お盆)、新年参拜(初詣)，都有深厚文化背景。"},
            {"pattern": re.compile(r"カワイイ|kawaii|推し|オタク", re.I),
             "note": "这些词已成为全球流行文化词汇，源自日本流行文化(J-pop/动漫)，反映日本软实力影响。"},
            {"pattern": re.compile(r"一期一会|侘び寂び|間", re.I),
             "note": "日本美学核心概念：一期一会(珍惜每次相遇)、侘び寂び(残缺之美)、間(空间的留白)。"},
        ],
        "shadow_notes": (
            "日语跟读重点：①拍(モーラ)均等——促音(っ)和长音(ー)要完整停顿；"
            "②音调(ピッチアクセント)——标准东京腔音调很重要；"
            "③助词清晰——は/が/を不能吞音；"
            "④语速：日本标准播报约250-300拍/分钟，跟读时先减速。"
        ),
        "common_beginner_mistakes": [
            "格助词混淆：は(主题)和が(主语)用法混淆",
            "动词位置错误(受英/中语序影响)",
            "遗漏丁宁体标记：用普通形在正式场合",
            "テイル形与单纯动词混淆：'食べます'(一次行为) vs. '食べています'(正在/习惯)",
            "汉字同形异义词：日语'手紙'=信件，中文'手纸'=卫生纸",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "ko": {
        "display_name": "韩语 (한국어)",
        "display_name_en": "Korean",
        "teacher_persona": (
            "你是 김지연（金智妍 Kim Jiyeon），首尔大学韩语教育学院毕业，"
            "TOPIK考试专业辅导教师，在北京和上海有大量教中国学生韩语的经验。"
            "对K-pop、K-drama、韩国流行文化深度了解，善用这些资源让学生保持高学习动力。"
            "教学风格：活泼有趣，擅长用文化背景解释语言现象。"
        ),
        "script_note": (
            "韩文(한글/Hangul)由世宗大王于1443年创制，是科学设计的字母表音系统。"
            "40个字母(21元音+19辅音)组合成音节块书写。"
            "通常2-4周可基本掌握读写，是韩语学习中最快克服的障碍。"
            "有大量汉字词(漢字語/한자어)，约60%词汇源于汉字，与中文词汇有相关性。"
        ),
        "phonology_note": (
            "韩语有紧音(ㄲㄸㅃㅆㅉ)、激音(ㅋㅌㅍㅊ)、平音三组对立，是关键发音特征。"
            "音节末尾辅音(받침/Batchim)的发音变化规则复杂。"
            "连音规则(연음)：辅音结尾+元音开头时，辅音移到下一音节发音。"
            "无声调系统（与汉语/日语/越南语的重大差异）。"
        ),
        "key_challenges": [
            "SOV语序（与中英文差异）",
            "格助词系统（이/가、은/는、을/를、에/에서、(으)로...）",
            "尊卑语阶(존댓말 vs. 반말)——决定于社会关系，用错会非常失礼",
            "动词/形容词词尾活用体系（约20种）",
            "连接词尾(连用形)和终止词尾系统",
            "汉字词(약 60%)vs. 固有词 vs. 外来语——三套词汇系统",
            "辅音群发音变化规则（激音化、鼻音化、流音化等）",
        ],
        "teaching_principles": [
            "韩字先行：用2-3节课专门攻克韩字，之后可拼读任何单词。",
            "语阶分场合教：初期教정중체(합쇼체)正式体，了解关系后教해요体，最后普通体。",
            "汉字词利用：中文母语学习者利用汉字词理解词根，但注意发音差异。",
            "K-pop/K-drama素材：利用学习者对韩流的兴趣作为动力资源，歌词/台词是天然输入。",
            "词尾组合：以常用句型为框架，填充不同词，而非孤立记忆词尾。",
            "语用文化：尊卑语阶不只是语法，要解释社会文化背景（年龄、职位、关系的重要性）。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"(은|는|이|가|을|를|에|에서|으?로|과|와|랑|이랑)", re.I),
             "label": "格助词",
             "explanation_hint": "韩语格助词决定名词在句中的语法功能，比日语助词更规律。"},
            {"pattern": re.compile(r"(ㅂ니다|습니다|ㅂ니까|습니까)", re.I),
             "label": "합쇼체（最高敬语体）",
             "explanation_hint": "最正式的语体，用于公开场合、新闻播报、对陌生人/上级的正式表达。"},
            {"pattern": re.compile(r"(아요|어요|여요)(?=$|[.])", re.I),
             "label": "해요체（礼貌体）",
             "explanation_hint": "日常最常用的礼貌语体，既正式又亲切，适合大多数情境。"},
            {"pattern": re.compile(r"(아서|어서)(?=\s)", re.I),
             "label": "原因连接词尾(아서/어서)",
             "explanation_hint": "表示顺序原因：'做了A，所以/然后做B'，前后句主语需一致。"},
            {"pattern": re.compile(r"(으?면)(?=\s)", re.I),
             "label": "条件词尾(으면)",
             "explanation_hint": "表示'如果……就……'，是韩语最基本的条件表达。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"빨리빨리|빠른|신속", re.I),
             "note": "빨리빨리文化是韩国著名的速度文化特征，反映韩国快速现代化的社会节奏和效率价值观。"},
            {"pattern": re.compile(r"눈치|체면|예의", re.I),
             "note": "눈치(读懂场合/察言观色)是韩国重要社交能力，与中文'眼力见'相似但在韩国更被重视。"},
            {"pattern": re.compile(r"치킨|삼겹살|치맥|소주", re.I),
             "note": "치맥(炸鸡+啤酒)、삼겹살(五花肉)配소주(烧酒)是韩国标志性的饮食文化符号和社交仪式。"},
            {"pattern": re.compile(r"K-pop|아이돌|BTS|BLACKPINK|하이브", re.I),
             "note": "K-pop是韩国最成功的文化输出之一，其工业化训练体系(아이돌文化)和全球粉丝经济是独特现象。"},
            {"pattern": re.compile(r"수능|고3|입시", re.I),
             "note": "수능(大学修学能力考试)是韩国高考，类似中国高考，对学生和家庭压力极大，每年11月举行。"},
        ],
        "shadow_notes": (
            "韩语跟读重点：①音节结尾辅音(받침)要清晰，不能吞掉；"
            "②连音变化(연음법칙)要自然；"
            "③激音/紧音对比要明显；"
            "④语调：韩语无声调，但句末语调变化承载语用功能（问句上扬）。"
        ),
        "common_beginner_mistakes": [
            "格助词错误：이/가(主格) vs. 은/는(主题格)混淆",
            "语序错误(受中/英语影响，动词放中间而非句末)",
            "语阶混用：在正式场合用反말(普通体)",
            "동사/형용사 어미活用错误",
            "遗漏辅音结尾发音变化",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "de": {
        "display_name": "德语 (Deutsch)",
        "display_name_en": "German",
        "teacher_persona": (
            "你是 Klaus Müller，歌德学院(Goethe-Institut)认证德语教师，"
            "在上海歌德学院任教多年，专攻面向中文/亚洲母语学习者的德语教学。"
            "持有DaF(Deutsch als Fremdsprache)教学资质。"
            "教学风格：严谨而有条理，善用对比分析，用系统化方式帮学生克服德语格(Kasus)难关。"
        ),
        "script_note": (
            "德语使用拉丁字母，包含4个特殊字符：Ä/ä, Ö/ö, Ü/ü（变音符）和ß(锐音符，等于ss)。"
            "大写规则：所有名词首字母大写（Tisch, Haus, Zeit）——德语独有特征。"
        ),
        "phonology_note": (
            "德语发音相对规律，字母与发音对应较稳定。"
            "关键音素：ch音(wie/ach区别)、r音(小舌r)、Umlauts元音。"
            "词重音多在第一音节（原生词），前缀影响重音位置。"
            "语调较平，句末语调变化弱于英语。"
        ),
        "key_challenges": [
            "四格系统(Nominativ/Akkusativ/Dativ/Genitiv)——名词/代词/冠词/形容词全部格变",
            "三性名词(der/die/das)——无规律，必须跟词一起记忆性别",
            "动词位置规则：主句V2（动词第二位）、从句动词末位",
            "可分动词(Trennbare Verben)：'aufmachen' → 'ich mache auf'",
            "形容词词尾变化(Adjektivdeklination)：根据性/数/格变化",
            "副词式从句(Nebensätze)：因为/当/如果/以便等引导的从句动词末位",
            "虚拟式(Konjunktiv II)：礼貌、假设、间接引语",
        ],
        "teaching_principles": [
            "格先于性：先建立格概念(主/宾/与格)，再叠加性别变化规则。",
            "名词性别：每个名词必须配格记忆(der/die/das Wasser)，养成习惯。",
            "动词框架(Satzklammer)：主句和从句动词位置是德语最核心规则，用颜色/框架可视化。",
            "规律优先：德语比英语规律，强调规律让学生有掌控感。",
            "读报/新闻：德语名词大写使新闻文本结构清晰，利用这点帮助阅读。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"\b(der|die|das|den|dem|des)\b", re.I),
             "label": "冠词格变化",
             "explanation_hint": "德语定冠词根据名词性、数、格变化——是德语格系统的核心标记。"},
            {"pattern": re.compile(r"\b(weil|da|obwohl|wenn|falls|damit|während|nachdem)\b", re.I),
             "label": "从句连词(动词末位)",
             "explanation_hint": "这些连词引导从句，从句中动词必须移至句末——德语最重要的语序规则之一。"},
            {"pattern": re.compile(r"\b\w+te\b|\bwurde\b|\bhatte\b|\bwar\b", re.I),
             "label": "过去时(Präteritum)",
             "explanation_hint": "书面/叙事过去时，sein/haben/情态动词在口语中也常用过去时而非完成时。"},
            {"pattern": re.compile(r"\bhabe\b|\bhast\b|\bhat\b.+\b\w+t\b", re.I),
             "label": "完成时(Perfekt)",
             "explanation_hint": "口语中描述过去事件的主要时态，由haben/sein+过去分词构成。"},
            {"pattern": re.compile(r"\b(würde|könnte|sollte|müsste|dürfte)\b", re.I),
             "label": "虚拟式II(Konjunktiv II)",
             "explanation_hint": "表示礼貌请求、假设或对现实的委婉表达。"},
            {"pattern": re.compile(r"\b\w+(lich|heit|keit|ung|schaft|nis)\b", re.I),
             "label": "名词派生后缀",
             "explanation_hint": "德语常见名词后缀：-heit/-keit(形→名,阴),-ung(动→名,阴),-schaft(集体名,阴)。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"\bWeihnacht\b|\bOktoberfest\b", re.I),
             "note": "圣诞节(Weihnachten)和慕尼黑啤酒节(Oktoberfest)是德国最具代表性的节庆，都有深厚文化仪式感。"},
            {"pattern": re.compile(r"\bGrundgesetz\b|\bBundestag\b|\bBundesrat\b", re.I),
             "note": "德国基本法(Grundgesetz)是德国宪法，联邦议院(Bundestag)和联邦参议院(Bundesrat)构成两院立法体系。"},
            {"pattern": re.compile(r"\bDatenschutz\b|\bDSGVO\b|\bPrivatsphäre\b", re.I),
             "note": "德国对隐私保护(Datenschutz)极为重视，欧盟GDPR很大程度上受德国法律影响。"},
            {"pattern": re.compile(r"\bPünktlichkeit\b", re.I),
             "note": "准时(Pünktlichkeit)是德国重要文化价值观，在商务和社交场合，迟到被视为不礼貌。"},
        ],
        "shadow_notes": (
            "德语跟读重点：①变音符(Umlauts)发音准确：ä/ö/ü不能读成a/o/u；"
            "②ch音区分：ich-Laut(前)vs. ach-Laut(后)；"
            "③词重音通常在第一音节；"
            "④语句节奏：德语语速适中，不像英语那样有强弱重音对比。"
        ),
        "common_beginner_mistakes": [
            "忘记名词大写",
            "从句动词不末位：'Ich weiß dass er kommt' → '...dass er kommt'(已正确)",
            "格混淆：Dativ vs. Akkusativ(尤其与介词连用)",
            "形容词词尾遗漏",
            "可分动词不分离：'Ich aufmache' → 'Ich mache auf'",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "fr": {
        "display_name": "法语 (Français)",
        "display_name_en": "French",
        "teacher_persona": (
            "你是 Marie Dubois，法国里昂高师语言学硕士，持有FLE(法语作为外语教学)资质，"
            "在上海法语联盟(Alliance Française)教学8年，DALF C2水平。"
            "对法语文化、文学、美食和时尚有深入了解，善用法语文化魅力激发学习者兴趣。"
            "教学风格：优雅从容，注重语音和语调的美感，强调法语表达的精确性。"
        ),
        "script_note": (
            "法语使用拉丁字母+多种变音符号：é/è/ê, à/â, î/ï, ô, ù/û/ü, ç。"
            "大小写规则与英语相似，但专有名词形容词不大写(français而非Français)。"
            "书写与发音差异大：很多字母不发音，需专门学习书面与口语的对应关系。"
        ),
        "phonology_note": (
            "法语口语的核心特征：①联诵(Liaison)——单词结尾不发音的辅音在元音开头词前发音；"
            "②省音(Élision)——元音在元音前省略(je+aime=j'aime)；"
            "③鼻音元音(an/en/in/on/un)；"
            "④r音：小舌r是法语特色，需练习；"
            "⑤重音：法语重音规律落在词群最后音节，不像英语有词级重音。"
        ),
        "key_challenges": [
            "语法性(Genre)：名词有阴性/阳性之分，形容词须一致",
            "动词变位(Conjugaison)：按人称、时态、语气变化，不规则动词多",
            "虚拟式(Subjonctif)：触发条件复杂，是B1+的重点难关",
            "过去时：简单过去时(Passé composé) vs. 未完成过去时(Imparfait)的区别",
            "冠词系统：定冠词/不定冠词/部分冠词(du/de la)",
            "代词系统：直接宾语/间接宾语/反身/中性代词(le/la/les/lui/leur/y/en)的位置",
            "联诵和省音：书面与口语差距大",
        ],
        "teaching_principles": [
            "语音优先：法语发音有美感逻辑，早期确立正确音素模型很重要。",
            "动词变位：分组记忆(-er/-ir/-re)，不规则动词用高频句强化。",
            "时态语境化：passé composé(已完成动作) vs. imparfait(描述/习惯/背景)需用叙事场景对比。",
            "性(Genre)：每个名词必须带冠词记忆，如德语。",
            "文化浸入：法语文化的骄傲感是学习动力，多用文化背景丰富课堂。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"\b(ai|as|a|avons|avez|ont)\s+\w+é\b", re.I),
             "label": "复合过去时(Passé composé)",
             "explanation_hint": "描述已完成的过去事件，口语中最常用的过去时态。"},
            {"pattern": re.compile(r"\b(étais|était|avait|faisait|pouvait|allait)\b", re.I),
             "label": "未完成过去时(Imparfait)",
             "explanation_hint": "描述过去持续的状态、习惯或背景动作，与passé composé对比使用。"},
            {"pattern": re.compile(r"\b(bien que|pour que|afin que|quoique|bien qu')\b", re.I),
             "label": "虚拟式触发词(Subjonctif)",
             "explanation_hint": "这些连词后面需要用虚拟式，表示主观性/不确定性/意愿。"},
            {"pattern": re.compile(r"\b(ne\s+pas|ne\s+plus|ne\s+jamais|ne\s+rien)\b", re.I),
             "label": "否定结构",
             "explanation_hint": "法语否定由ne...pas包裹动词，否定副词替换pas表达不同否定含义。"},
            {"pattern": re.compile(r"\b(dont|lequel|laquelle|auquel|duquel)\b", re.I),
             "label": "关系代词",
             "explanation_hint": "dont替代'de+关系词'，lequel等用于介词后的关系从句。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"\bbaguette\b|\bcroissant\b|\bfoie gras\b", re.I),
             "note": "法棍(baguette)是法国饮食文化的标志，2022年入选联合国非物质文化遗产。法国美食文化(gastronomie française)以精致闻名于世。"},
            {"pattern": re.compile(r"\bLaïcité\b|\blaïque\b|\bsécularisme\b", re.I),
             "note": "世俗主义(Laïcité)是法国宪法原则，政教严格分离，是理解法国社会政策的关键概念。"},
            {"pattern": re.compile(r"\bgrève\b|\bsyndicat\b|\bmanifest\b", re.I),
             "note": "罢工(grève)和工会(syndicat)在法国政治文化中地位极高，社会抗议游行(manifestation)是法国公民参与的重要形式。"},
            {"pattern": re.compile(r"\bAcadémie française\b|\bfrancophonie\b", re.I),
             "note": "法兰西学院(Académie française)负责法语规范化，法语世界(La Francophonie)有83个成员国/地区。"},
        ],
        "shadow_notes": (
            "法语跟读重点：①联诵(Liaison)要准确：les enfants→'lezenfants'；"
            "②鼻音元音要到位(an/on/in/un)；"
            "③小舌r(r grasseyé)；"
            "④节奏：法语每个音节几乎等长，重音在词群末尾，不像英语有明显强弱。"
        ),
        "common_beginner_mistakes": [
            "性的错误：le/la混淆，形容词性数不一致",
            "动词变位错误：尤其être/avoir/aller不规则变位",
            "Passé composé vs. Imparfait混淆",
            "联诵遗漏或错误联诵",
            "代词位置错误(应在动词前)",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "es": {
        "display_name": "西班牙语 (Español)",
        "display_name_en": "Spanish",
        "teacher_persona": (
            "你是 Ana García，马德里康普顿斯大学西班牙语教学硕士，"
            "持有DELE考试考官资质，在上海西班牙文化协会任教，DELE C2水平。"
            "热爱拉美和伊比利亚文化，擅长通过音乐、电影和美食激发学习热情。"
            "教学风格：热情活泼，强调口语实践，喜欢用对话情景化教学。"
        ),
        "script_note": (
            "西班牙语使用拉丁字母+特殊字符：ñ, á/é/í/ó/ú(重音符), ü(二音符), ¡¿(倒置标点)。"
            "字母与发音的对应关系高度规律，是西班牙语的一大优势。"
        ),
        "phonology_note": (
            "西班牙语发音规律：每个字母发音固定，几乎没有不发音字母。"
            "关键音素：②ñ(ñ)发音类似'ny'；②ll/y在大多数地区同音；"
            "③c/z区别：欧洲西语的ceceo('s'和'θ'之分)vs.拉美西语；"
            "④r/rr：单r一个弹音，rr是颤音；"
            "⑤重音：规律可预测，重音符号用于标注不规则重音。"
        ),
        "key_challenges": [
            "Ser vs. Estar：两个'是'动词的区别（永久vs.临时特征）",
            "虚拟式(Subjuntivo)：使用条件复杂，是B1+关键难点",
            "过去时对比：简单过去(Pretérito indefinido) vs. 未完成过去(Imperfecto) vs. 完成时(Perfecto)",
            "语法性(Género)：名词阴阳性，形容词一致",
            "动词变位：人称变化丰富，不规则动词众多",
            "代词系统：直接宾语/间接宾语代词(lo/la/le/les)和leísmo/loísmo方言差异",
            "欧洲西语 vs. 拉美西语的差异（vosotros/ustedes，词汇差异）",
        ],
        "teaching_principles": [
            "Ser/Estar早期区分：用具体场景对比(identity vs. state)，这是最关键的概念差异。",
            "过去时对比：用叙事策略——'情节用indefinido，背景用imperfecto'。",
            "虚拟式：先理解概念(主观性/不确定性/意愿)，再记忆形式。",
            "口语优先：西班牙语是拥有5亿母语者的语言，强调实用口语输出。",
            "方言差异：告知学习者欧洲vs.拉美差异，但不要因此制造混乱。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"\b(es|son|era|eran|fue|fueron)\b", re.I),
             "label": "Ser动词",
             "explanation_hint": "永久性特征：身份、来源、职业、固有特质，以及被动句的辅助动词。"},
            {"pattern": re.compile(r"\b(está|están|estaba|estuvo)\b", re.I),
             "label": "Estar动词",
             "explanation_hint": "临时状态、位置、情绪、结果状态。Ser vs. Estar是西语最重要的概念区分。"},
            {"pattern": re.compile(r"\b(haya|sea|esté|tenga|quiera|pueda)\b", re.I),
             "label": "虚拟式(Subjuntivo)",
             "explanation_hint": "在表达意愿、情感、怀疑或从句主语不同的情况下使用。"},
            {"pattern": re.compile(r"\b(aunque|a menos que|para que|sin que)\b", re.I),
             "label": "虚拟式触发连词",
             "explanation_hint": "这些连词通常触发虚拟式（aunque有时用陈述式，含义不同）。"},
            {"pattern": re.compile(r"\b(se\s+\w+[ae]n?)\b", re.I),
             "label": "Se被动/无人称结构",
             "explanation_hint": "se+动词第三人称：表示'有人……'或被动，无需说明行为者。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"\bsiesta\b", re.I),
             "note": "午休(siesta)是西班牙和部分拉丁美洲地区的传统习俗，但在现代都市已逐渐减少。"},
            {"pattern": re.compile(r"\bflamenco\b|\bpasodoble\b|\bsalsa\b|\btango\b", re.I),
             "note": "弗拉门戈(flamenco)是安达卢西亚文化遗产，萨尔萨(salsa)和探戈(tango)源自拉丁美洲，都是西语文化重要标志。"},
            {"pattern": re.compile(r"\bReal Madrid\b|\bBarcelona\b|\bla liga\b", re.I),
             "note": "足球(fútbol)在西班牙和拉丁美洲是最重要的体育文化，皇马vs.巴萨的德比(El Clásico)是全球最受关注的体育赛事之一。"},
            {"pattern": re.compile(r"\bDía de los Muertos\b|\bSemana Santa\b", re.I),
             "note": "亡灵节(Día de los Muertos)是墨西哥重要节日，圣周(Semana Santa)是西班牙最盛大的宗教庆典。"},
        ],
        "shadow_notes": (
            "西班牙语跟读重点：①每个字母发音稳定，比英语好上手；"
            "②r/rr弹音和颤音要练习；"
            "③重音位置要记住(重音符号很有帮助)；"
            "④欧洲vs.拉美口音：注意c/z的发音差异，告诉学习者选一种坚持。"
        ),
        "common_beginner_mistakes": [
            "Ser/Estar混淆：'Estoy feliz'(临时)vs.'Soy feliz'(性格)",
            "遗漏主语代词(但西语动词变位已包含人称，可省略主语)",
            "简单过去vs.未完成过去混淆",
            "形容词性数一致错误",
            "虚拟式遗漏：表达意愿/期望的从句中需用虚拟式",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    "ru": {
        "display_name": "俄语 (Русский)",
        "display_name_en": "Russian",
        "teacher_persona": (
            "你是 Наташа Иванова（娜塔莎·伊万诺娃），圣彼得堡国立大学对外俄语教学系硕士，"
            "持有ТРКИ(俄语等级考试)考官资质，在北京俄罗斯文化中心任教多年。"
            "擅长用俄罗斯文学、历史和文化让俄语学习充满魅力。"
            "教学风格：严谨而富有激情，用系统化方法帮学生攻克格变难关。"
        ),
        "script_note": (
            "俄语使用西里尔字母(Кириллица)，33个字母。"
            "大多数字母可从希腊/拉丁字母类推，约2-3周可学会字母读写。"
            "软硬辅音区分：Ь(软音符)使前一辅音软化，是发音关键。"
            "部分字母外形类似拉丁字母但发音不同（P=R，C=S，Н=N），注意混淆。"
        ),
        "phonology_note": (
            "俄语重音不规律，必须逐词记忆——重音位置直接影响元音的发音(reduction)。"
            "非重读音节的о发音接近а，е接近и。"
            "颤音р，硬辅音ж/ш，软辅音щ/ч，以及ы元音是外语学习者的常见难点。"
            "语调(интонация)有7种IC(интонационная конструкция)结构，决定句子语用功能。"
        ),
        "key_challenges": [
            "六格系统(六格+方位格/第二宾格)：名词/形容词/代词/数词全部格变",
            "动词体(Вид)：完成体/未完成体区分——贯穿俄语所有时态",
            "运动动词：определённые/неопределённые идти/ходить/ехать/ездить等",
            "阳性/阴性/中性三性，加上单复数，形容词有12种结尾",
            "词序灵活：格系统替代词序，但信息结构(主题-焦点)有规律",
            "前缀动词系统：格变+前缀使动词家族庞大(ходить→приходить/уходить/входить...)",
            "重音不规律：格变时重音可能移动",
        ],
        "teaching_principles": [
            "格的概念先行：先用中英对比理解'格'的功能(谁做/做什么/给谁/在哪)，再学变化形式。",
            "动词体(Вид)：每学一个动词，配对记忆两体(писать/написать)。这是俄语最核心的语法概念。",
            "运动动词：早期专门讲解，用图示说明定向/非定向区别。",
            "词序灵活性：格系统决定语法关系，词序决定信息焦点——这是俄语的魅力也是难点。",
            "文化串联：俄罗斯文学(普希金/托尔斯泰/陀思妥耶夫斯基)是激发学习兴趣的最好资源。",
        ],
        "grammar_patterns": [
            {"pattern": re.compile(r"(ого|его|ому|ему|ом|ем|ой|ей)\b", re.I),
             "label": "形容词格变化",
             "explanation_hint": "俄语形容词必须与名词性/数/格一致，有规律性结尾变化。"},
            {"pattern": re.compile(r"\b(пошёл|пошла|пришёл|ушёл|поехал)\b", re.I),
             "label": "完成体过去时(运动动词)",
             "explanation_hint": "完成体表示单次目的性运动，与未完成体(ходил)的语义有重要区别。"},
            {"pattern": re.compile(r"\bчтобы\b", re.I),
             "label": "目的/虚拟连词чтобы",
             "explanation_hint": "引导目的状语从句或虚拟式，后接动词过去时形式。"},
            {"pattern": re.compile(r"\b(если бы|бы)\b", re.I),
             "label": "虚拟语气(бы)",
             "explanation_hint": "бы+过去时形式表示与现实相反的假设，类似英语虚拟语气。"},
            {"pattern": re.compile(r"\b(который|которая|которое|которых)\b", re.I),
             "label": "关系代词который",
             "explanation_hint": "который在格/性/数上与先行词一致，是俄语关系从句的核心。"},
        ],
        "culture_triggers": [
            {"pattern": re.compile(r"Масленица|Пасха|Новый год", re.I),
             "note": "谢肉节(Масленица)是复活节前的煎饼节，复活节(Пасха)是俄罗斯最重要的宗教节日，新年(Новый год)是最重要的世俗节日。"},
            {"pattern": re.compile(r"баня|сауна", re.I),
             "note": "俄式蒸汽浴室(баня)是俄罗斯重要的社交和养生传统，朋友/家人一起去баня是重要的文化仪式。"},
            {"pattern": re.compile(r"душа|тоска|судьба", re.I),
             "note": "俄语灵魂词：душа(灵魂)、тоска(无法言说的忧郁渴望)、судьба(命运)——这些词承载俄罗斯文化的情感核心。"},
            {"pattern": re.compile(r"Кремль|Красная площадь|Эрмитаж", re.I),
             "note": "克里姆林宫(Кремль)和红场(Красная площадь)是俄罗斯政治与历史的核心象征，冬宫/艾尔米塔什(Эрмитаж)是世界最大博物馆之一。"},
        ],
        "shadow_notes": (
            "俄语跟读重点：①重音准确——非重读元音弱化(о→а)；"
            "②软辅音vs.硬辅音区分；"
            "③颤音р练习；"
            "④俄语语速较快，朗读时注意连音和语调(IC)模式。"
        ),
        "common_beginner_mistakes": [
            "格变形式错误（尤其生格/与格混淆）",
            "动词体混用（该用完成体时用了未完成体）",
            "运动动词混淆（идти vs. ходить）",
            "形容词性数格不一致",
            "重音错误导致元音发音不准",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. L1 → TARGET LANGUAGE TRANSFER ERROR PROFILES
#    For the teacher: what typical interference errors to watch for,
#    and how to frame explanations.
# ═══════════════════════════════════════════════════════════════════════════════

class TransferProfile(TypedDict):
    interference_risks: list[str]   # likely errors due to L1 structure
    facilitation_notes: list[str]   # structural similarities that help
    framing_tips: list[str]         # how to explain concepts using L1 contrast


# Keyed as (l1_code, target_lang_code)
L1_TRANSFER_TABLE: dict[tuple[str, str], TransferProfile] = {

    ("zh", "en"): {
        "interference_risks": [
            "冠词(a/an/the)遗漏——中文无冠词",
            "时态标记遗漏——中文用时间词而非动词变形表示时间",
            "主谓一致错误(she don't)——中文动词不变形",
            "介词错误——中文介词用法与英语差异大",
            "直接中文语序迁移：'I very like this' → 'I really like this'",
            "Wh-疑问词语序：中文'你去哪里'→英语'Where are you going?'",
        ],
        "facilitation_notes": [
            "SVO基本语序基本一致",
            "英语字母化拼写系统对中文学习者相对容易入门",
        ],
        "framing_tips": [
            "解释冠词时：'英语名词需要有冠词帽子，中文名词可以光头出现'",
            "解释时态：'中文靠时间词，英语靠动词形式，两种方式都在表达时间'",
            "讲被动语态：'英语被动更接近中文的被字句结构'",
        ],
    },

    ("zh", "ja"): {
        "interference_risks": [
            "汉字同形异义词(日语手紙=信件，中文=卫生纸)",
            "日语SOV语序——动词必须在句末，中文SVO学习者常把动词放中间",
            "助词遗漏——中文无日语式格助词",
            "敬语体系——中文无对应的形态变化，易遗漏",
            "日语存在动词区分(いる vs. ある)——中文只有'有/在'",
        ],
        "facilitation_notes": [
            "汉字认知优势：大量汉字词可直接理解含义(但读音不同)",
            "中日韩词汇共同汉字词基础：例如'電話'在三种语言中意思相同",
        ],
        "framing_tips": [
            "'日语汉字字形与中文相同，但千万不要按中文读音读'——专门建立'同形异义'意识",
            "解释SOV：'日语的动词永远在句末，像列车的尾车；格助词是路标，告诉你谁做什么'",
            "解释いる/ある：'有生命的用いる，没有生命的用ある'",
        ],
    },

    ("zh", "ko"): {
        "interference_risks": [
            "韩语SOV语序——动词必须在句末",
            "助词系统——中文无格助词，需要全新习得",
            "语阶系统——中文无形态变化式的尊卑语",
            "辅音对立(紧音/激音/平音)——中文无此三分对立",
        ],
        "facilitation_notes": [
            "汉字词优势：约60%韩语词汇是汉字词，发音有规律对应",
            "中文母语者理解韩语的Sino-Korean词汇(漢字語)相对容易",
        ],
        "framing_tips": [
            "解释韩语汉字词时：'이것은 한자어로 중국어의 XXX와 관련이 있어요'",
            "解释语阶：'根据对方年龄和关系选择语阶，就像中文的'您'和'你'，但韩语的区别更系统、更重要'",
        ],
    },

    ("zh", "de"): {
        "interference_risks": [
            "格系统——中文无格变化，德语四格是全新概念",
            "名词性别——中文无语法性，需要全新记忆",
            "动词变位——中文动词不变形",
            "从句动词末位——与中文语序直觉相反",
            "形容词词尾——中文形容词无变化",
        ],
        "facilitation_notes": [
            "德语发音相对规律，比英语更容易预测",
            "德语词汇结构清晰，复合词可分解理解",
        ],
        "framing_tips": [
            "解释格：'中文靠词序区分主语/宾语，德语靠冠词变化——同一个词，冠词变了，意思变了'",
            "解释性：'每个名词有自己的性别，必须当名字的一部分一起记——der Tisch，不只是Tisch'",
        ],
    },

    ("zh", "fr"): {
        "interference_risks": [
            "语法性——中文无性别概念",
            "动词变位——中文动词不变形",
            "虚拟式——中文无对应的形态变化",
            "联诵/省音——书面与口语差距大，对中文学习者陌生",
            "时态区分(Passé composé vs. Imparfait)——中文无时态变化",
        ],
        "facilitation_notes": [
            "基本SVO语序与中文一致",
        ],
        "framing_tips": [
            "解释性：'每个名词要配冠词记忆，le/la是固定搭配，不能分开'",
            "解释联诵：'法语口语里，相邻单词的边界会融合——就像中文快速说话时的连读'",
        ],
    },

    ("zh", "es"): {
        "interference_risks": [
            "Ser/Estar混淆——中文只有一个'是'",
            "动词变位——六种人称各有变化",
            "语法性——名词阴阳性",
            "虚拟式(Subjuntivo)——中文无对应形态",
            "时态区分(indefinido vs. imperfecto)",
        ],
        "facilitation_notes": [
            "西语发音规律，字母对应稳定",
            "基本SVO语序",
        ],
        "framing_tips": [
            "解释Ser/Estar：'Ser是本质身份，Estar是当下状态——你是医生(ser)，但你现在感冒了(estar)'",
        ],
    },

    ("zh", "ru"): {
        "interference_risks": [
            "六格系统——中文无格变化",
            "动词体(完成体/未完成体)——中文无对应概念",
            "三性(阳/阴/中)——中文无性别",
            "西里尔字母——全新书写系统",
            "重音不规律——中文重音相对固定",
            "运动动词系统——中文无方向性动词对立",
        ],
        "facilitation_notes": [
            "西里尔字母30天内可学会，之后可拼读任何单词",
            "部分国际词汇(科技/音乐)被俄语借用，发音有规律对应",
        ],
        "framing_tips": [
            "解释格：'俄语靠词尾变化区分角色——不管词序如何，词尾告诉你谁是主语、谁是宾语'",
            "解释动词体：'完成体=动作有结果/终点；未完成体=过程/习惯/反复——每个动词都有这两张面孔'",
        ],
    },

    # English L1 → other languages
    ("en", "zh"): {
        "interference_risks": [
            "声调无意识——英语无声调，中文四声需主动训练",
            "量词遗漏——英语无量词系统",
            "时态思维惯性——想用动词变形表时间",
            "补语结构——无英语对应",
        ],
        "facilitation_notes": [
            "中文无动词变形，比英语的时态系统更简单",
            "中文基本SVO语序与英语一致",
        ],
        "framing_tips": [
            "解释声调：'声调就像音乐的音符，mā/má/mǎ/mà是完全不同的四首音乐'",
            "解释量词：'就像英语的a piece of/a cup of，中文每个名词有自己的量词伙伴'",
        ],
    },

    ("en", "ja"): {
        "interference_risks": [
            "SOV语序——与英语SVO完全相反，动词末位",
            "格助词系统——英语无格助词",
            "敬语体系——英语无形态敬语",
            "三套书写系统——英语只有字母",
        ],
        "facilitation_notes": [
            "大量英语外来词被片假名化借入日语，发音变了但形式可辨认",
        ],
        "framing_tips": [
            "解释SOV：'日语句子里，动词是最后出现的悬念——你要听到句末才知道意思'",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PUBLIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_language_profile(lang: str) -> LanguageProfile:
    """Return the language profile for a target language, with 'en' as fallback."""
    return LANGUAGE_PROFILES.get(lang, LANGUAGE_PROFILES["en"])


def get_content_type_profile(content_type: str) -> dict:
    """Return content type pedagogical profile, with 'unknown' as fallback."""
    return CONTENT_TYPE_PROFILES.get(content_type, CONTENT_TYPE_PROFILES["unknown"])


def get_transfer_profile(l1: str, target: str) -> TransferProfile | None:
    """Return L1→target transfer error profile if available."""
    return L1_TRANSFER_TABLE.get((l1, target))


def get_grammar_patterns_for_lang(lang: str) -> list[GrammarPattern]:
    """Return compiled grammar patterns for a given target language."""
    profile = LANGUAGE_PROFILES.get(lang)
    if profile is None:
        return []
    return profile["grammar_patterns"]


def get_culture_triggers_for_lang(lang: str) -> list[CultureTrigger]:
    """Return culture triggers for a given target language."""
    profile = LANGUAGE_PROFILES.get(lang)
    if profile is None:
        return []
    return profile["culture_triggers"]
