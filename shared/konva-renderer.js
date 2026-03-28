/**
 * Konva Renderer — isomorphic rendering engine
 * Used by both browser (vue-konva preview) and Node.js (konva-node export)
 *
 * This module takes Timeline JSON + content data and produces Konva node configurations.
 * In browser: configs are used to create vue-konva components
 * In Node.js: configs are used to create konva-node nodes → PNG export
 */

import { createSubtitleNodes } from './element-renderers/subtitle.js'
import { createWordboxNodes } from './element-renderers/wordbox.js'
import { createExprboxNodes } from './element-renderers/exprbox.js'
import { createWatermarkNodes } from './element-renderers/watermark.js'
import { STYLE_THEMES } from './theme-mapper.js'

/** Element type → renderer function mapping */
const RENDERERS = {
  subtitle:  createSubtitleNodes,
  wordbox:   createWordboxNodes,
  exprbox:   createExprboxNodes,
  watermark: createWatermarkNodes,
}

/**
 * PREVIEW_DATA — example content for editor preview (8 languages)
 */
export const PREVIEW_DATA = {
  en: {
    sentence: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
    translations: {
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
      ja: "毎日新しい言語を学ぶことは、自信を育み、記憶力を高め、異文化理解を広げ、友情・旅行・仕事・成長のための数え切れない機会を開きます。",
      ko: "매일 새로운 언어를 배우면 자신감이 높아지고 기억력이 향상되며 문화적 이해가 넓어지고, 우정·여행·일·성장을 위한 수많은 기회가 열립니다.",
      de: "Jeden Tag eine neue Sprache zu lernen stärkt das Selbstvertrauen, schärft das Gedächtnis, erweitert das kulturelle Verständnis und eröffnet unzählige Möglichkeiten für Freundschaft, Reisen, Arbeit und persönliches Wachstum.",
      fr: "Apprendre une nouvelle langue chaque jour renforce la confiance en soi, affine la mémoire, élargit la compréhension culturelle et ouvre d'innombrables possibilités d'amitié, de voyage, de travail et d'épanouissement.",
      es: "Aprender un nuevo idioma cada día fortalece la confianza, agudiza la memoria, amplía la comprensión cultural y abre incontables oportunidades para la amistad, los viajes, el trabajo y el crecimiento personal.",
      ru: "Ежедневное изучение нового языка укрепляет уверенность в себе, улучшает память, расширяет культурное понимание и открывает бесчисленные возможности для дружбы, путешествий, работы и личностного роста.",
    },
    words: [
      { word: "acquisition", phonetic: "/ˌækwɪˈzɪʃən/", translation: "习得；获取" },
      { word: "remarkable", phonetic: "/rɪˈmɑːrkəbl/", translation: "非凡的；显著的" },
      { word: "phenomenon", phonetic: "/fɪˈnɒmɪnən/", translation: "现象；奇迹" },
      { word: "cognitive", phonetic: "/ˈkɒɡnɪtɪv/", translation: "认知的" },
      { word: "capability", phonetic: "/ˌkeɪpəˈbɪlɪti/", translation: "能力；才能" },
      { word: "incredible", phonetic: "/ɪnˈkredɪbl/", translation: "难以置信的" },
      { word: "neuroplasticity", phonetic: "/ˌnjʊəroʊplæˈstɪsəti/", translation: "神经可塑性" },
      { word: "adaptability", phonetic: "/əˌdæptəˈbɪləti/", translation: "适应能力" },
      { word: "linguistic", phonetic: "/lɪŋˈɡwɪstɪk/", translation: "语言学的" },
      { word: "mechanism", phonetic: "/ˈmekənɪzəm/", translation: "机制；机理" },
      { word: "comprehension", phonetic: "/ˌkɒmprɪˈhenʃən/", translation: "理解；领会" },
      { word: "proficiency", phonetic: "/prəˈfɪʃənsi/", translation: "熟练；精通" },
    ],
    expressions: [
      { english: "in the long run", chinese: "从长远来看" },
      { english: "on the other hand", chinese: "另一方面" },
      { english: "as a result of", chinese: "由于…的结果" },
      { english: "play a crucial role in", chinese: "在…中起关键作用" },
      { english: "be indicative of", chinese: "表明；显示出" },
      { english: "at the core of", chinese: "处于…核心" },
      { english: "shed light on", chinese: "阐明；解释" },
      { english: "be associated with", chinese: "与…相关" },
    ],
  },
  zh: {
    sentence: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      ja: "毎日新しい言語を学ぶことは、自信を育て、記憶力を高め、異文化理解を広げ、友情・旅行・仕事・成長のための数多くの機会を開きます。",
    },
    words: [
      { word: "认知", phonetic: "rèn zhī", translation: "cognition" },
      { word: "非凡", phonetic: "fēi fán", translation: "extraordinary" },
      { word: "可塑性", phonetic: "kě sù xìng", translation: "plasticity" },
      { word: "习得", phonetic: "xí dé", translation: "acquisition" },
      { word: "展示", phonetic: "zhǎn shì", translation: "demonstrate" },
      { word: "现象", phonetic: "xiàn xiàng", translation: "phenomenon" },
      { word: "适应性", phonetic: "shì yìng xìng", translation: "adaptability" },
      { word: "神经", phonetic: "shén jīng", translation: "neural" },
      { word: "机制", phonetic: "jī zhì", translation: "mechanism" },
      { word: "潜能", phonetic: "qián néng", translation: "potential" },
      { word: "语境", phonetic: "yǔ jìng", translation: "context" },
      { word: "迁移", phonetic: "qiān yí", translation: "learning transfer" },
    ],
    expressions: [
      { english: "令人难以置信", chinese: "incredibly hard to believe" },
      { english: "展示了…能力", chinese: "demonstrates the ability" },
      { english: "一种…现象", chinese: "a kind of phenomenon" },
      { english: "在长期过程中", chinese: "in the long-term process" },
      { english: "从认知角度看", chinese: "from a cognitive perspective" },
      { english: "与…密切相关", chinese: "be closely related to" },
      { english: "起到关键作用", chinese: "play a key role" },
      { english: "有助于理解", chinese: "help with understanding" },
    ],
  },
  ja: {
    sentence: "毎日新しい言語を学ぶことは、自信を育て、記憶力を高め、異文化理解を広げ、友情・旅行・仕事・成長のための数多くの機会を開きます。",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "習得", phonetic: "しゅうとく", translation: "acquisition" },
      { word: "認知", phonetic: "にんち", translation: "cognition" },
      { word: "驚くべき", phonetic: "おどろくべき", translation: "remarkable" },
      { word: "適応力", phonetic: "てきおうりょく", translation: "adaptability" },
      { word: "可塑性", phonetic: "かそせい", translation: "plasticity" },
      { word: "側面", phonetic: "そくめん", translation: "aspect" },
      { word: "言語能力", phonetic: "げんごのうりょく", translation: "linguistic ability" },
      { word: "神経", phonetic: "しんけい", translation: "neural" },
      { word: "機構", phonetic: "きこう", translation: "mechanism" },
      { word: "文脈", phonetic: "ぶんみゃく", translation: "context" },
      { word: "処理", phonetic: "しょり", translation: "processing" },
      { word: "熟達", phonetic: "じゅくたつ", translation: "proficiency" },
    ],
    expressions: [
      { english: "〜を示している", chinese: "demonstrates ~" },
      { english: "驚くべき〜", chinese: "remarkable ~" },
      { english: "〜の側面", chinese: "aspect of ~" },
      { english: "長い目で見ると", chinese: "in the long run" },
      { english: "〜に関係している", chinese: "be related to ~" },
      { english: "〜に役立つ", chinese: "be useful for ~" },
      { english: "〜の中心にある", chinese: "be at the core of ~" },
      { english: "〜を明らかにする", chinese: "shed light on ~" },
    ],
  },
  ko: {
    sentence: "매일 새로운 언어를 배우면 자신감이 커지고 기억력이 좋아지며 문화적 이해가 넓어지고, 우정·여행·일·성장을 위한 수많은 기회가 열립니다.",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "습득", phonetic: "seub-deug", translation: "acquisition" },
      { word: "인지", phonetic: "in-ji", translation: "cognition" },
      { word: "놀라운", phonetic: "nol-la-un", translation: "remarkable" },
      { word: "적응력", phonetic: "jeog-eung-lyeog", translation: "adaptability" },
      { word: "가소성", phonetic: "ga-so-seong", translation: "plasticity" },
      { word: "측면", phonetic: "cheug-myeon", translation: "aspect" },
      { word: "언어능력", phonetic: "eon-eo-neung-lyeog", translation: "linguistic ability" },
      { word: "신경", phonetic: "sin-gyeong", translation: "neural" },
      { word: "기제", phonetic: "gi-je", translation: "mechanism" },
      { word: "맥락", phonetic: "maeg-lag", translation: "context" },
      { word: "처리", phonetic: "cheo-ri", translation: "processing" },
      { word: "숙련도", phonetic: "sug-lyeon-do", translation: "proficiency" },
    ],
    expressions: [
      { english: "보여줍니다", chinese: "demonstrates" },
      { english: "놀라운 측면", chinese: "remarkable aspect" },
      { english: "믿기 어려운", chinese: "hard to believe" },
      { english: "장기적으로 보면", chinese: "in the long run" },
      { english: "밀접하게 관련되다", chinese: "be closely related" },
      { english: "핵심 역할을 하다", chinese: "play a key role" },
      { english: "이해에 도움이 되다", chinese: "help with understanding" },
      { english: "중심에 있다", chinese: "be at the core of" },
    ],
  },
  de: {
    sentence: "Jeden Tag eine neue Sprache zu lernen stärkt das Selbstvertrauen, verbessert das Gedächtnis, erweitert das kulturelle Verständnis und eröffnet unzählige Chancen für Freundschaft, Reisen, Arbeit und persönliches Wachstum.",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "Spracherwerb", phonetic: "/ˈʃpraːxɛɐ̯ˌvɛrp/", translation: "language acquisition" },
      { word: "bemerkenswert", phonetic: "/bəˈmɛrkənsvɛrt/", translation: "remarkable" },
      { word: "Plastizität", phonetic: "/plastiˈtsɪtɛːt/", translation: "plasticity" },
      { word: "demonstriert", phonetic: "/demoːnˈstriːrt/", translation: "demonstrates" },
      { word: "kognitiv", phonetic: "/kɔɡniˈtiːf/", translation: "cognitive" },
      { word: "unglaublich", phonetic: "/ʊnˈɡlaʊ̯plɪç/", translation: "incredible" },
      { word: "Anpassungsfähigkeit", phonetic: "/anˈpasʊŋsˌfɛːhɪçkaɪt/", translation: "adaptability" },
      { word: "neuronal", phonetic: "/nɔʏroˈnaːl/", translation: "neural" },
      { word: "Mechanismus", phonetic: "/meçaˈnɪsmʊs/", translation: "mechanism" },
      { word: "Kontext", phonetic: "/kɔnˈtɛkst/", translation: "context" },
      { word: "Verarbeitung", phonetic: "/fɛɐ̯ˈʔaʁbaɪtʊŋ/", translation: "processing" },
      { word: "Kompetenz", phonetic: "/kɔmpeˈtɛnts/", translation: "proficiency" },
    ],
    expressions: [
      { english: "das...demonstriert", chinese: "which demonstrates" },
      { english: "ein...Phänomen", chinese: "a phenomenon" },
      { english: "des menschlichen", chinese: "of the human" },
      { english: "auf lange Sicht", chinese: "in the long run" },
      { english: "eine zentrale Rolle spielen", chinese: "play a crucial role" },
      { english: "mit ... verbunden sein", chinese: "be associated with" },
      { english: "im Kern von", chinese: "at the core of" },
      { english: "Licht auf ... werfen", chinese: "shed light on" },
    ],
  },
  fr: {
    sentence: "Apprendre une nouvelle langue chaque jour renforce la confiance en soi, améliore la mémoire, élargit la compréhension culturelle et ouvre d'innombrables possibilités d'amitié, de voyage, de travail et d'épanouissement personnel.",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "acquisition", phonetic: "/akizisjɔ̃/", translation: "acquisition" },
      { word: "remarquable", phonetic: "/ʁəmaʁkabl/", translation: "remarkable" },
      { word: "plasticité", phonetic: "/plastisite/", translation: "plasticity" },
      { word: "adaptabilité", phonetic: "/adaptabilite/", translation: "adaptability" },
      { word: "démontre", phonetic: "/demɔ̃tʁ/", translation: "demonstrates" },
      { word: "incroyable", phonetic: "/ɛ̃kʁwajabl/", translation: "incredible" },
      { word: "cognitif", phonetic: "/kɔɡnitif/", translation: "cognitive" },
      { word: "neuronal", phonetic: "/nœʁɔnal/", translation: "neural" },
      { word: "mécanisme", phonetic: "/mekanism/", translation: "mechanism" },
      { word: "contexte", phonetic: "/kɔ̃tɛkst/", translation: "context" },
      { word: "traitement", phonetic: "/tʁɛtmɑ̃/", translation: "processing" },
      { word: "maîtrise", phonetic: "/metʁiz/", translation: "proficiency" },
    ],
    expressions: [
      { english: "qui démontre", chinese: "which demonstrates" },
      { english: "un phénomène remarquable", chinese: "a remarkable phenomenon" },
      { english: "du cerveau humain", chinese: "of the human brain" },
      { english: "à long terme", chinese: "in the long run" },
      { english: "jouer un rôle clé", chinese: "play a key role" },
      { english: "être lié à", chinese: "be linked to" },
      { english: "au cœur de", chinese: "at the core of" },
      { english: "éclairer", chinese: "shed light on" },
    ],
  },
  es: {
    sentence: "Aprender un nuevo idioma cada día fortalece la confianza, mejora la memoria, amplía la comprensión cultural y abre incontables oportunidades de amistad, viajes, trabajo y crecimiento personal.",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "adquisición", phonetic: "/adkiˈsjon/", translation: "acquisition" },
      { word: "notable", phonetic: "/noˈtaβle/", translation: "remarkable" },
      { word: "plasticidad", phonetic: "/plastiθiˈðað/", translation: "plasticity" },
      { word: "adaptabilidad", phonetic: "/adaptaβiliˈðað/", translation: "adaptability" },
      { word: "demuestra", phonetic: "/deˈmwestra/", translation: "demonstrates" },
      { word: "increíble", phonetic: "/iŋkɾeˈiβle/", translation: "incredible" },
      { word: "cognitivo", phonetic: "/koɣniˈtiβo/", translation: "cognitive" },
      { word: "neuronal", phonetic: "/newɾoˈnal/", translation: "neural" },
      { word: "mecanismo", phonetic: "/mekaˈnismo/", translation: "mechanism" },
      { word: "contexto", phonetic: "/konˈteksto/", translation: "context" },
      { word: "procesamiento", phonetic: "/pɾosesaˈmjento/", translation: "processing" },
      { word: "dominio", phonetic: "/doˈminjo/", translation: "proficiency/mastery" },
    ],
    expressions: [
      { english: "que demuestra", chinese: "which demonstrates" },
      { english: "un fenómeno notable", chinese: "a remarkable phenomenon" },
      { english: "del cerebro humano", chinese: "of the human brain" },
      { english: "a largo plazo", chinese: "in the long run" },
      { english: "desempeñar un papel clave", chinese: "play a key role" },
      { english: "estar asociado con", chinese: "be associated with" },
      { english: "en el núcleo de", chinese: "at the core of" },
      { english: "arrojar luz sobre", chinese: "shed light on" },
    ],
  },
  ru: {
    sentence: "Ежедневное изучение нового языка укрепляет уверенность в себе, улучшает память, расширяет культурное понимание и открывает бесчисленные возможности для дружбы, путешествий, работы и личностного роста.",
    translations: {
      en: "Learning a new language every day builds confidence, sharpens memory, broadens cultural understanding, and opens countless opportunities for friendship, travel, work, and growth.",
      zh: "每天学习一门新语言能够增强自信、提升记忆力、拓宽文化理解，并为友谊、旅行、工作和个人成长打开无数机会。",
    },
    words: [
      { word: "освоение", phonetic: "/əsˈvoːɪnɪjə/", translation: "acquisition" },
      { word: "замечательный", phonetic: "/zəmɪˈtʃætəlnɪj/", translation: "remarkable" },
      { word: "феномен", phonetic: "/fɪˈnɔːmɪn/", translation: "phenomenon" },
      { word: "демонстрирует", phonetic: "/dɪˈmɒnstreɪts/", translation: "demonstrates" },
      { word: "адаптивность", phonetic: "/ədˈæptɪvnəs/", translation: "adaptability" },
      { word: "нейропластичность", phonetic: "/ˈnjʊroʊˈplæstɪsɪti/", translation: "neural plasticity" },
      { word: "когнитивный", phonetic: "/kɐɡnʲɪˈtʲivnɨj/", translation: "cognitive" },
      { word: "нейронный", phonetic: "/nʲɪjˈronnɨj/", translation: "neural" },
      { word: "механизм", phonetic: "/mʲɪxɐˈnʲizm/", translation: "mechanism" },
      { word: "контекст", phonetic: "/kɐnˈtʲekst/", translation: "context" },
      { word: "обработка", phonetic: "/ɐˈbrabotkə/", translation: "processing" },
      { word: "владение", phonetic: "/vlɐˈdʲenʲɪje/", translation: "proficiency/mastery" },
    ],
    expressions: [
      { english: "замечательный феномен", chinese: "remarkable phenomenon" },
      { english: "демонстрирует способность", chinese: "demonstrates ability" },
      { english: "человеческого мозга", chinese: "of the human brain" },
      { english: "в долгосрочной перспективе", chinese: "in the long run" },
      { english: "играть ключевую роль", chinese: "play a key role" },
      { english: "быть связанным с", chinese: "be associated with" },
      { english: "в основе", chinese: "at the core of" },
      { english: "проливать свет на", chinese: "shed light on" },
    ],
  },
}

/**
 * Extra stress-test fixtures to reproduce extreme layout cases in editor preview.
 * These are merged in getPreviewContent so we can test long subtitle lines,
 * long translations, long vocabulary items, and long phrase cards.
 */
const PREVIEW_STRESS_DATA = {
  en: {
    sentence:
      "Building a daily language-learning habit steadily increases confidence, strengthens memory recall, deepens cultural awareness, and creates practical opportunities for friendship, travel, career development, and personal growth.",
    translation:
      "把学习语言变成日常习惯，会稳步增强自信、强化记忆、加深文化理解，并带来友谊、旅行、职业发展与个人成长机会。",
    words: [
      { word: "electroencephalographically", phonetic: "/ɪˌlɛk.troʊ.ɛnˌsɛf.əˌloʊˈɡræf.ɪ.kli/", translation: "以脑电图记录方式地；用于测试超长词排版" },
      { word: "institutionalization", phonetic: "/ˌɪnstɪˌtjuːʃənəlaɪˈzeɪʃən/", translation: "制度化过程；长期形成并被组织体系固化的实践机制" },
      { word: "counterintuitiveness", phonetic: "/ˌkaʊntərɪnˈtuːɪtɪvnəs/", translation: "反直觉性；与常识预期明显不一致的认知特征" },
    ],
    expressions: [
      { english: "to make sense of highly context-dependent pragmatic implications", chinese: "在高度依赖语境的语用含义中建立可解释框架" },
      { english: "be disproportionately influenced by seemingly negligible phonetic variation", chinese: "被看似微不足道的语音差异不成比例地影响" },
      { english: "under tightly constrained yet semantically overloaded communicative conditions", chinese: "在强约束且语义负载过高的交际条件下" },
    ],
  },
  zh: {
    sentence:
      "把学习新语言变成每天的习惯，可以稳定提升自信心、强化记忆提取能力、加深跨文化理解，并持续带来友谊、旅行、职业发展与个人成长机会。",
    translation:
      "Making new-language learning a daily habit can steadily build confidence, strengthen memory recall, deepen cross-cultural understanding, and continuously create opportunities for friendship, travel, career growth, and personal development.",
    words: [
      { word: "跨语境迁移能力", phonetic: "kuà yǔ jìng qiān yí néng lì", translation: "cross-context transfer competence in language processing and learning" },
      { word: "高负荷信息整合", phonetic: "gāo fù hè xìn xī zhěng hé", translation: "high-load information integration under constrained cognitive resources" },
      { word: "语义歧义消解机制", phonetic: "yǔ yì qí yì xiāo jiě jī zhì", translation: "mechanism for semantic disambiguation in complex discourse streams" },
    ],
    expressions: [
      { english: "在信息严重过载的条件下保持理解稳定性", chinese: "maintain interpretive stability under severe informational overload" },
      { english: "通过多轮回看逐步修正先前建立的错误假设", chinese: "iteratively revise previously formed but inaccurate assumptions through repeated review" },
      { english: "在不完整线索中重建最可能的语义结构", chinese: "reconstruct the most plausible semantic structure from incomplete cues" },
    ],
  },
  ja: {
    sentence:
      "新しい言語を毎日学ぶ習慣は、自信を着実に高め、記憶力を強化し、異文化理解を深め、友情・旅行・仕事・自己成長の機会を広げます。",
    translation:
      "每天坚持学习新语言，能够稳定增强自信、提升记忆力、加深文化理解，并拓展友谊、旅行、工作与成长机会。",
    words: [
      { word: "文脈依存的解釈可能性", phonetic: "ぶんみゃくいぞんてきかいしゃくかのうせい", translation: "context-dependent interpretive possibility in discourse comprehension" },
      { word: "認知負荷最適化戦略", phonetic: "にんちふかさいてきかせんりゃく", translation: "strategy for optimizing cognitive load during language processing" },
      { word: "意味曖昧性解消過程", phonetic: "いみあいまいせいかいしょうかてい", translation: "process of resolving semantic ambiguity across multi-clause input" },
    ],
    expressions: [
      { english: "断片的な手掛かりから意味ネットワークを再構築する", chinese: "从碎片化线索中重建语义网络" },
      { english: "一見些細な韻律差が解釈全体を大きく左右する", chinese: "看似细微的韵律差异会显著左右整体理解" },
      { english: "高密度入力下でも推論の一貫性を維持する", chinese: "在高密度输入下仍维持推理一致性" },
    ],
  },
  ko: {
    sentence:
      "새로운 언어를 매일 배우는 습관은 자신감을 높이고 기억력을 강화하며 문화적 이해를 넓혀, 우정·여행·일·성장을 위한 실제 기회를 꾸준히 만들어 줍니다.",
    translation:
      "每天学习新语言的习惯会提升自信、强化记忆、拓宽文化理解，并持续带来友谊、旅行、工作和成长机会。",
    words: [
      { word: "문맥의존적해석가능성", phonetic: "mun-maeg-ui-jon-jeog-hae-seog-ga-neung-seong", translation: "context-dependent interpretive possibility in language comprehension" },
      { word: "인지부하최적화전략", phonetic: "in-ji-bu-ha-choe-jeog-hwa-jeon-lyag", translation: "cognitive-load optimization strategy for sustained understanding" },
      { word: "의미모호성해소과정", phonetic: "ui-mi-mo-ho-seong-hae-so-gwa-jeong", translation: "semantic ambiguity resolution process in complex discourse" },
    ],
    expressions: [
      { english: "단편적인 단서만으로도 의미 구조를 재구성하다", chinese: "仅凭碎片化线索重建语义结构" },
      { english: "미세한 억양 차이가 해석 결과를 크게 바꾸다", chinese: "细微语调差异会显著改变理解结果" },
      { english: "고밀도 입력에서도 추론의 일관성을 유지하다", chinese: "在高密度输入下维持推理一致性" },
    ],
  },
  de: {
    sentence:
      "Die tägliche Gewohnheit, eine neue Sprache zu lernen, stärkt Schritt für Schritt das Selbstvertrauen, verbessert die Gedächtnisleistung, vertieft das kulturelle Verständnis und eröffnet konkrete Chancen für Freundschaft, Reisen, Beruf und persönliche Entwicklung.",
    translation:
      "把学习新语言作为每日习惯，能够逐步增强自信、提升记忆表现、深化文化理解，并为友谊、旅行、职业与个人发展打开真实机会。",
    words: [
      { word: "Kontextualisierungsmechanismus", phonetic: "/kɔntɛkstu̯aliˈziːʁʊŋsmexaˌnɪsmʊs/", translation: "mechanism of contextualization in meaning negotiation and inference" },
      { word: "Informationsverarbeitungsdichte", phonetic: "/ɪnfɔʁmaˈtsi̯oːnsfɛɐ̯ˌaʁbaɪtʊŋsˌdɪçtə/", translation: "density of information processing under constrained comprehension windows" },
      { word: "Mehrdeutigkeitsauflösung", phonetic: "/meːɐ̯ˈdɔʏtɪçkaɪtsˌaʊ̯fløːzʊŋ/", translation: "disambiguation of competing semantic interpretations" },
    ],
    expressions: [
      { english: "unter stark schwankenden prosodischen Rahmenbedingungen", chinese: "在韵律条件显著波动的框架下" },
      { english: "aus fragmentarischen Signalen belastbare Hypothesen ableiten", chinese: "从碎片化信号中推导出可检验的稳健假设" },
      { english: "die Interpretationskonsistenz trotz Überlastung aufrechterhalten", chinese: "在过载状态下保持解释一致性" },
    ],
  },
  fr: {
    sentence:
      "Prendre l'habitude d'apprendre une nouvelle langue chaque jour renforce progressivement la confiance, améliore la mémoire, approfondit la compréhension culturelle et crée des opportunités concrètes d'amitié, de voyage, de carrière et d'épanouissement personnel.",
    translation:
      "把每天学习新语言变成习惯，会逐步提升自信、优化记忆、加深文化理解，并创造友谊、旅行、职业与成长的实际机会。",
    words: [
      { word: "recontextualisation", phonetic: "/ʁəkɔ̃tɛkstɥalizasjɔ̃/", translation: "recontextualization process for meaning recovery across shifting discourse" },
      { word: "surdétermination", phonetic: "/syʁdetɛʁminasjɔ̃/", translation: "over-determination in interpretive pathways with competing cues" },
      { word: "interprétabilité", phonetic: "/ɛ̃tɛʁpʁetabilite/", translation: "interpretability under high-density and low-redundancy input" },
    ],
    expressions: [
      { english: "maintenir la cohérence interprétative sous surcharge informationnelle", chinese: "在信息过载下维持解释连贯性" },
      { english: "déduire une structure de sens à partir d'indices incomplets", chinese: "从不完整线索中推断意义结构" },
      { english: "réviser progressivement des hypothèses initialement erronées", chinese: "逐步修正最初建立但不准确的假设" },
    ],
  },
  es: {
    sentence:
      "Convertir el aprendizaje diario de un nuevo idioma en un hábito fortalece la confianza, mejora la memoria, amplía la comprensión cultural y abre oportunidades reales de amistad, viajes, desarrollo profesional y crecimiento personal.",
    translation:
      "把每天学习新语言变成习惯，能够增强自信、提升记忆、拓宽文化理解，并打开友谊、旅行、职业发展与个人成长机会。",
    words: [
      { word: "recontextualización", phonetic: "/rekontekstwalisaˈθjon/", translation: "recontextualization process for recovering intended meaning" },
      { word: "sobrecognitivización", phonetic: "/soβɾekognitiβiθaˈθjon/", translation: "overloading of cognitive resources during interpretation" },
      { word: "interpretabilidad", phonetic: "/inteɾpɾetaβiliˈðað/", translation: "degree of interpretability under constrained discourse conditions" },
    ],
    expressions: [
      { english: "mantener la coherencia inferencial bajo sobrecarga informativa", chinese: "在信息过载下维持推断连贯性" },
      { english: "reconstruir estructuras semánticas desde señales fragmentarias", chinese: "从碎片化信号重建语义结构" },
      { english: "ajustar hipótesis previas mediante revisiones sucesivas", chinese: "通过连续修正调整先前假设" },
    ],
  },
  ru: {
    sentence:
      "Ежедневная привычка изучать новый язык постепенно укрепляет уверенность в себе, улучшает память, углубляет культурное понимание и открывает реальные возможности для дружбы, путешествий, профессионального развития и личностного роста.",
    translation:
      "把每天学习新语言作为习惯，会逐步增强自信、提升记忆、深化文化理解，并带来友谊、旅行、职业发展与个人成长机会。",
    words: [
      { word: "контекстуализация", phonetic: "/kənʲtʲɪkstʊəlʲɪˈzat͡sɨjə/", translation: "contextualization process in dynamic discourse interpretation" },
      { word: "гиперинтерпретируемость", phonetic: "/ɡʲɪpʲɪrʲɪntʲɪrprʲɪtʲɪˈrujɪməstʲ/", translation: "hyper-interpretability under dense semantic pressure" },
      { word: "смыслоструктурирование", phonetic: "/smɨsləstrʊktʊˈrʲirəvənʲɪje/", translation: "structuring of meaning across multilayered communicative input" },
    ],
    expressions: [
      { english: "сохранять целостность интерпретации при перегрузке", chinese: "在过载条件下保持解释整体性" },
      { english: "восстанавливать смысл по неполным контекстным сигналам", chinese: "通过不完整语境信号恢复意义" },
      { english: "поэтапно корректировать ранее принятые гипотезы", chinese: "分阶段修正先前采纳的假设" },
    ],
  },
}

/**
 * Get preview content for a given source/target language pair.
 *
 * @param {string} srcLang - Source language code
 * @param {string} tgtLang - Target language code
 * @param {number} numWords - Number of words to show (0 = all)
 * @param {number} numExprs - Number of expressions to show (0 = all)
 * @returns {{ text, translation, words, expressions }}
 */
export function getPreviewContent(srcLang, tgtLang, numWords = 6, numExprs = 4) {
  const data = PREVIEW_DATA[srcLang] || PREVIEW_DATA.en
  const stress = PREVIEW_STRESS_DATA[srcLang] || PREVIEW_STRESS_DATA.en
  const baseTranslation = data.translations?.[tgtLang] || data.translations?.en || '翻译文本'

  const text = data.sentence || stress?.sentence || ''
  const translation = baseTranslation || stress?.translation || '翻译文本'
  const mergedWords = [...(data.words || []), ...(stress?.words || [])]
  const mergedExprs = [...(data.expressions || []), ...(stress?.expressions || [])]
  const words = numWords > 0 ? mergedWords.slice(0, numWords) : mergedWords
  const expressions = numExprs > 0 ? mergedExprs.slice(0, numExprs) : mergedExprs

  // If UI asks for more than built-in preview fixtures, duplicate with index suffix
  // so range expansion in the editor still has visible feedback.
  if (numWords > 0 && words.length < numWords && data.words.length > 0) {
    for (let i = words.length; i < numWords; i++) {
      const base = data.words[i % data.words.length]
      words.push({
        ...base,
        word: `${base.word} ${i + 1}`,
      })
    }
  }
  if (numExprs > 0 && expressions.length < numExprs && data.expressions.length > 0) {
    for (let i = expressions.length; i < numExprs; i++) {
      const base = data.expressions[i % data.expressions.length]
      expressions.push({
        ...base,
        english: `${base.english} ${i + 1}`,
      })
    }
  }

  return {
    text,
    translation,
    words,
    expressions,
  }
}

/**
 * Render a single element to Konva node configs.
 *
 * @param {object} element - Timeline element object
 * @param {object} content - Content data (sentence-specific or preview)
 * @param {{ width: number, height: number }} containerSize - pixel dimensions
 * @returns {{ x, y, w, h, nodes: Array }|null}
 */
/**
 * Merge theme style into element style, preserving per-element overrides like fontFamily/fontScale.
 */
export function getEffectiveStyle(element, styleId) {
  if (!styleId) return element.style
  const theme = STYLE_THEMES[styleId]
  const section = theme?.[element.type]
  if (!section) return element.style
  return {
    ...element.style,
    ...section,
    fontFamily: element.style.fontFamily,
    fontScale: element.style.fontScale,
    lineHeight: element.style.lineHeight,
    sourceLineHeight: element.style.sourceLineHeight,
    targetLineHeight: element.style.targetLineHeight,
    wordSpacing: element.style.wordSpacing,
    bgOpacity: element.style.bgOpacity,
  }
}

export function renderElement(element, content, containerSize, styleId) {
  const renderer = RENDERERS[element.type]
  if (!renderer) {
    console.warn(`[konva-renderer] Unknown element type: ${element.type}`)
    return null
  }
  const effectiveElement = styleId
    ? { ...element, style: getEffectiveStyle(element, styleId) }
    : element
  return renderer(effectiveElement, content, containerSize)
}

/**
 * Render all visible elements for a given part.
 *
 * @param {object} timeline - Complete Timeline JSON
 * @param {string} partId - Part ID to render
 * @param {object} content - Content data
 * @param {{ width: number, height: number }} containerSize - pixel dimensions
 * @returns {Array<{ elementId, x, y, w, h, nodes, zIndex }>}
 */
export function renderPart(timeline, partId, content, containerSize) {
  const part = timeline.parts.find(p => p.id === partId)
  if (!part) return []

  const results = []
  // Sort elements by zIndex
  const sortedElements = [...timeline.elements].sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0))

  for (const element of sortedElements) {
    // Check visibility in this part
    const isVisible = part.elementVisibility?.[element.id]
    if (!isVisible) continue
    if (element.visible === false) continue

    // Merge part-level overrides into global element so each part can have
    // independent position/size/style/animation.
    const overrides = part.elementConfigs?.[element.id] || {}
    const mergedElement = {
      ...element,
      ...overrides,
      position: { ...(element.position || {}), ...(overrides.position || {}) },
      size: { ...(element.size || {}), ...(overrides.size || {}) },
      style: { ...(element.style || {}), ...(overrides.style || {}) },
      animation: {
        ...(element.animation || {}),
        ...(overrides.animation || {}),
        enter: {
          ...(element.animation?.enter || {}),
          ...(overrides.animation?.enter || {}),
        },
        exit: {
          ...(element.animation?.exit || {}),
          ...(overrides.animation?.exit || {}),
        },
      },
    }

    // Prepare content based on element type
    let elementContent = content
    if (mergedElement.type === 'subtitle') {
      elementContent = { text: content?.text, translation: content?.translation }
    } else if (mergedElement.type === 'wordbox') {
      elementContent = { words: content?.words }
    } else if (mergedElement.type === 'exprbox') {
      elementContent = { expressions: content?.expressions }
    }

    const effectiveStyleId = part.styleId || timeline.styleId || null
    const result = renderElement(mergedElement, elementContent, containerSize, effectiveStyleId)
    if (result) {
      results.push({
        elementId: element.id,
        elementType: mergedElement.type,
        zIndex: mergedElement.zIndex || 0,
        animation: mergedElement.animation,
        ...result,
      })
    }
  }

  return results
}

/**
 * Create a default Timeline JSON with standard elements.
 *
 * @param {object} opts - { sourceLang, targetLang, resolution, styleId }
 * @returns {object} Complete Timeline JSON
 */
export function createDefaultTimeline(opts = {}) {
  const {
    sourceLang = 'en',
    targetLang = 'zh',
    resolution = { width: 1920, height: 1080 },
    styleId = 'ink_wash',
  } = opts

  return {
    version: 1,
    resolution,
    defaultFont: 'quicksand',
    styleId,
    sourceLang,
    targetLang,
    numWords: 6,
    numExprs: 4,

    elements: [
      {
        id: 'subtitle_1',
        type: 'subtitle',
        visible: true,
        position: { x: 0.011, y: 0.704 },
        size: { w: 0.961, h: 0.346 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 10,
        style: {
          bgColor: 'rgba(10,10,21,1)',
          bgOpacity: 0.85,
          bgStyle: 'dark',
          textColor: '#00ffff',
          translationColor: '#ff0080',
          fontFamily: 'quicksand',
          fontScale: 1.15,
          lineHeight: 1.0,
          sourceLineHeight: 1.0,
          targetLineHeight: 1.3,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'slide_up', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
      {
        id: 'wordbox_1',
        type: 'wordbox',
        visible: true,
        position: { x: 0.761, y: 0.008 },
        size: { w: 0.222, h: 0.689 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 8,
        style: {
          bgColor: 'rgba(10,10,21,1)',
          bgOpacity: 0.85,
          wordColor: '#00ffff',
          phoneticColor: '#ff00ff',
          translationColor: '#ffffff',
          accentColor: '#00ffff',
          headerColor: '#ff0080',
          fontFamily: 'quicksand',
          fontScale: 0.9,
          wordSpacing: 1.0,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'pop', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
      {
        id: 'exprbox_1',
        type: 'exprbox',
        visible: true,
        position: { x: 0.002, y: 0.005 },
        size: { w: 0.275, h: 0.483 },
        rotation: 0,
        opacity: 1.0,
        zIndex: 8,
        style: {
          bgColor: 'rgba(10,10,21,1)',
          bgOpacity: 0.85,
          expressionColor: '#ff0080',
          translationColor: '#ffffff',
          accentColor: '#ff0080',
          headerColor: '#00ffff',
          fontFamily: 'quicksand',
          fontScale: 1.0,
          wordSpacing: 1.0,
          borderRadius: 4,
        },
        animation: {
          enter: { type: 'pop', duration: 300, easing: 'easeOutCubic' },
          exit: { type: 'fade', duration: 200, easing: 'easeInCubic' },
        },
      },
    ],

    parts: [
      {
        id: 'p_1',
        repeat: 1,
        speed: 1.0,
        styleId: null,
        elementVisibility: {
          subtitle_1: false,
          wordbox_1: false,
          exprbox_1: false,
        },
      },
    ],
  }
}
