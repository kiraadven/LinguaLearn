"""
ContentConnector + ContentPrefetcher

ContentConnector: 从离线 content pack / web 搜索解析节点内容。
ContentPrefetcher: runtime 提前 2 步预测 graph 走向，按需调用 LLM
                   生成深度教学内容并注入节点 content_pack。

设计原则：
- 离线 content pack 只有技能元数据（见 markdown_exporter.export_content_pack）
- 深度内容（例句、纠错、语法、教学脚本）在 runtime 按需生成
- Prefetcher 在每次 graph advance 后自动触发，对前方 2 步的节点预取
- 已生成的内容缓存在 _cache 中，不重复调用 LLM
"""

from __future__ import annotations
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .schema import normalize_content_pack

if TYPE_CHECKING:
    from .graph_engine import LessonGraph
    from .schema import LiveNode

logger = logging.getLogger(__name__)


class ContentConnector:

    def __init__(
        self,
        content_packs_dir: Optional[Path] = None,
        policy_packs_dir: Optional[Path] = None,
        web_search_client=None,
    ):
        self._packs_dir = content_packs_dir
        self._policy_dir = policy_packs_dir
        self._web_search = web_search_client
        self._cache: dict[str, dict] = {}

    def resolve(
        self,
        skill: str,
        node_type: str,
        lang_level: str = "B1",
    ) -> dict:
        """Find and assemble content for a node.

        Returns:
            {
                "script_outline": [...],
                "examples": [...],
                "common_mistakes": [...],
                "media_anchors": [...],
                "supplementary_links": [...],
            }
        """
        cache_key = f"{skill}:{node_type}:{lang_level}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Priority 1: offline content pack
        content = self._resolve_from_pack(skill, node_type, lang_level)
        if content:
            normalized = normalize_content_pack(
                content,
                node_type=node_type,
                lang_level=lang_level,
            )
            self._cache[cache_key] = normalized
            return normalized

        # Priority 2: cached web search (already in self._cache, checked above)

        # Priority 3: live web search
        if self._web_search:
            content = self._resolve_from_web(skill, node_type, lang_level)
            if content:
                normalized = normalize_content_pack(
                    content,
                    node_type=node_type,
                    lang_level=lang_level,
                )
                self._cache[cache_key] = normalized
                return normalized

        # Fallback: minimal content
        content = {
            "script_outline": [f"Teach {skill} at {lang_level} level"],
            "examples": [],
            "common_mistakes": [],
            "media_anchors": [],
            "supplementary_links": [],
        }
        normalized = normalize_content_pack(content, node_type=node_type, lang_level=lang_level)
        self._cache[cache_key] = normalized
        return normalized

    def resolve_policy(self, situation: str) -> dict:
        """Retrieve teaching policy for a specific situation."""
        if self._policy_dir is None:
            return {"action": "escalate_to_supervisor", "notes": "No policy pack available"}

        policy_file = self._policy_dir / f"{situation}.json"
        if policy_file.exists():
            with open(policy_file, "r", encoding="utf-8") as f:
                return json.load(f)

        policy_file_yaml = self._policy_dir / f"{situation}.yaml"
        if policy_file_yaml.exists():
            import yaml
            with open(policy_file_yaml, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        return {"action": "escalate_to_supervisor", "notes": f"No policy for: {situation}"}

    def bind_to_node(self, node, content: dict):
        """Attach resolved content to a LiveNode content_pack field."""
        node.content_pack = normalize_content_pack(
            content,
            node_type=getattr(node, "node_type", ""),
            source_lang=getattr(node, "source_language", ""),
            target_lang=getattr(node, "target_language", ""),
        )
        return node

    # ------------------------------------------------------------------
    # Private resolvers
    # ------------------------------------------------------------------

    def _resolve_from_pack(self, skill: str, node_type: str,
                           lang_level: str) -> Optional[dict]:
        if self._packs_dir is None:
            return None

        for ext in ("json", "md", "yaml"):
            pack_file = self._packs_dir / f"{skill}.{ext}"
            if pack_file.exists():
                return self._parse_pack_file(pack_file, node_type, lang_level)

        skill_dir = self._packs_dir / skill
        if skill_dir.is_dir():
            for ext in ("json", "md", "yaml"):
                pack_file = skill_dir / f"{node_type}.{ext}"
                if pack_file.exists():
                    return self._parse_pack_file(pack_file, node_type, lang_level)

        return None

    def _parse_pack_file(self, path: Path, node_type: str,
                         lang_level: str) -> Optional[dict]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._normalize_content(data, node_type, lang_level)
            elif suffix == ".yaml":
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return self._normalize_content(data, node_type, lang_level)
            elif suffix == ".md":
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                return self._normalize_content({
                    "script_outline": [text],
                    "examples": [],
                    "common_mistakes": [],
                    "media_anchors": [],
                    "supplementary_links": [],
                }, node_type, lang_level)
        except Exception:
            return None
        return None

    @staticmethod
    def _normalize_content(data: dict, node_type: str, lang_level: str) -> dict:
        return normalize_content_pack(data, node_type=node_type, lang_level=lang_level)

    def _resolve_from_web(self, skill: str, node_type: str,
                          lang_level: str) -> Optional[dict]:
        if self._web_search is None:
            return None
        try:
            query = f"{skill} {node_type} teaching material {lang_level}"
            results = self._web_search.search(query, max_results=3)
            if results:
                return normalize_content_pack({
                    "script_outline": [],
                    "examples": [],
                    "common_mistakes": [],
                    "media_anchors": [],
                    "supplementary_links": [
                        {"title": r.get("title", ""), "url": r.get("url", "")}
                        for r in results
                    ],
                }, node_type=node_type, lang_level=lang_level)
        except Exception:
            pass
        return None


# =====================================================================
# ContentPrefetcher — Runtime look-ahead 2 步 LLM 内容生成
# =====================================================================

class ContentPrefetcher:
    """根据 graph 当前位置，预测前方 2 步节点并按需生成深度教学内容。

    工作方式：
    1. SessionOrchestrator 每次 advance 后调用 prefetch()
    2. prefetch() 沿 graph 的 on_success 边往前看 2 步
    3. 对 content_pack 为空的节点，异步调用 LLM 生成内容
    4. 生成结果写入节点的 content_pack 字段

    不会重复生成：已有 content_pack 的节点直接跳过。
    """

    def __init__(
        self,
        llm_client=None,
        model: str = "deepseek-reasoner",
        source_lang: str = "en",
        target_lang: str = "zh-Hans",
        content_pack_data: Optional[dict] = None,
        max_workers: int = 2,
    ):
        self._client = llm_client
        self._model = model
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._pack = content_pack_data or {}  # 离线 content pack JSON
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._generating: set[str] = set()  # 正在生成中的 node_id
        self._lock = threading.Lock()

    def prefetch(self, graph: LessonGraph, current_node_id: str) -> None:
        """从 current_node_id 往前看 2 步，异步预取内容。"""
        nodes_to_prefetch = self._look_ahead(graph, current_node_id, steps=2)

        for node in nodes_to_prefetch:
            if node.content_pack:
                continue  # 已有内容
            with self._lock:
                if node.node_id in self._generating:
                    continue  # 正在生成
                self._generating.add(node.node_id)

            self._executor.submit(self._generate_and_fill, graph, node)

    def prefetch_sync(self, graph: LessonGraph, current_node_id: str) -> None:
        """同步版 prefetch — 阻塞直到前方节点内容全部就绪。
        用于 session 初始化时确保前几个节点有内容。"""
        nodes_to_prefetch = self._look_ahead(graph, current_node_id, steps=2)
        for node in nodes_to_prefetch:
            if node.content_pack:
                continue
            self._generate_and_fill(graph, node)

    # ------------------------------------------------------------------
    # Look-ahead: 沿 on_success / auto_advance 边往前探 N 步
    # ------------------------------------------------------------------

    @staticmethod
    def _look_ahead(graph: LessonGraph, start_id: str,
                    steps: int = 2) -> list[LiveNode]:
        """BFS 沿主干边往前看 N 步，收集所有可能到达的节点。"""
        result = []
        visited = {start_id}
        frontier = [start_id]
        advance_events = {"on_success", "auto_advance", "on_minor_error"}

        for _ in range(steps):
            next_frontier = []
            for nid in frontier:
                for edge in graph.get_outgoing_edges(nid):
                    target = edge["target"]
                    event = edge.get("event", "")
                    if target not in visited and event in advance_events:
                        visited.add(target)
                        next_frontier.append(target)
                        try:
                            result.append(graph.get_node(target))
                        except KeyError:
                            pass
            frontier = next_frontier
            if not frontier:
                break

        return result

    # ------------------------------------------------------------------
    # LLM 内容生成（按单个节点粒度）
    # ------------------------------------------------------------------

    def _generate_and_fill(self, graph: LessonGraph, node: LiveNode) -> None:
        """对单个节点调用 LLM 生成教学内容，写入 node.content_pack。"""
        try:
            skill_id = node.learning_targets[0] if node.learning_targets else ''
            skill_data = self._pack.get('skills', {}).get(skill_id, {})
            target_item = skill_data.get('target_item', {})

            content = self._call_llm(node, target_item, skill_data)
            if content:
                if "target_item" not in content and isinstance(target_item, dict):
                    content["target_item"] = target_item
                node.content_pack = normalize_content_pack(
                    content,
                    node_type=node.node_type,
                    source_lang=self._source_lang,
                    target_lang=self._target_lang,
                )
                logger.info(f"[prefetch] Generated content for {node.node_id} "
                            f"({node.node_type}:{skill_id})")
            else:
                # fallback: 最小内容
                node.content_pack = normalize_content_pack(
                    self._minimal_content(node, target_item),
                    node_type=node.node_type,
                    source_lang=self._source_lang,
                    target_lang=self._target_lang,
                )
                logger.warning(f"[prefetch] LLM failed for {node.node_id}, "
                               f"using minimal content")
        except Exception as e:
            logger.error(f"[prefetch] Error generating {node.node_id}: {e}")
            node.content_pack = normalize_content_pack(
                {"error": str(e)},
                node_type=node.node_type,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
            )
        finally:
            with self._lock:
                self._generating.discard(node.node_id)

    def _call_llm(self, node: LiveNode, target_item: dict,
                  skill_data: dict) -> Optional[dict]:
        """调用 deepseek-reasoner 生成单个节点的教学内容。"""
        if not self._client:
            return None

        prompt = self._build_node_prompt(node, target_item, skill_data)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
            )
            text = response.choices[0].message.content.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            logger.warning("[prefetch] LLM returned non-dict JSON for node %s", node.node_id)
            return None
        except Exception as e:
            logger.error(f"[prefetch] LLM call failed: {e}")
            return None

    def _build_node_prompt(self, node: LiveNode, target_item: dict,
                           skill_data: dict) -> str:
        """根据节点类型构建不同粒度的 LLM 提示词。

        核心思想：不同 node_type 需要的内容完全不同。
        explain 需要讲解脚本 + 例句；practice 需要练习题；
        check 需要测验题；repair 需要简化版讲解 + 纠错。
        """
        src = self._source_lang
        tgt = self._target_lang
        nt = node.node_type
        skill_type = skill_data.get('skill_type', 'vocabulary')

        # 目标项描述
        if skill_type == 'vocabulary':
            item_desc = (f"词汇: {target_item.get('word', '')}\n"
                         f"音标: {target_item.get('phonetic', '')}\n"
                         f"释义: {target_item.get('translation', '')}")
        else:
            item_desc = (f"表达: {target_item.get('expression', '')}\n"
                         f"释义: {target_item.get('translation', '')}")

        context = (f"原句: {target_item.get('in_context', '')}\n"
                   f"译文: {target_item.get('context_translation', '')}")

        # 按 node_type 分发不同提示词
        if nt == "explain":
            return self._prompt_explain(item_desc, context, skill_type, src, tgt)
        elif nt == "warm_up":
            return self._prompt_warm_up(item_desc, context, skill_type, src, tgt)
        elif nt == "vocabulary_focus":
            return self._prompt_vocabulary_focus(item_desc, context, skill_type, src, tgt)
        elif nt == "pronunciation_drill":
            return self._prompt_pronunciation_drill(item_desc, context, skill_type, src, tgt)
        elif nt == "listening_comprehension":
            return self._prompt_listening_comprehension(item_desc, context, skill_type, src, tgt)
        elif nt == "reading_comprehension":
            return self._prompt_reading_comprehension(item_desc, context, skill_type, src, tgt)
        elif nt == "dialogue_practice":
            return self._prompt_dialogue_practice(item_desc, context, skill_type, src, tgt)
        elif nt == "dictation":
            return self._prompt_dictation(item_desc, context, skill_type, src, tgt)
        elif nt == "error_analysis":
            return self._prompt_error_analysis(item_desc, context, skill_type, src, tgt)
        elif nt == "cultural_note":
            return self._prompt_cultural_note(item_desc, context, skill_type, src, tgt)
        elif nt in ("guided_practice", "free_practice"):
            return self._prompt_practice(item_desc, context, skill_type, src, tgt, nt)
        elif nt == "check_understanding":
            return self._prompt_check(item_desc, context, skill_type, src, tgt)
        elif nt == "repair":
            return self._prompt_repair(item_desc, context, skill_type, src, tgt)
        elif nt == "worked_example":
            return self._prompt_worked_example(item_desc, context, skill_type, src, tgt)
        elif nt == "review":
            return self._prompt_review(item_desc, context, skill_type, src, tgt)
        else:
            # hook, transition, wrap_up 等不需要深度内容
            return self._prompt_generic(item_desc, context, nt, src, tgt)

    # ------------------------------------------------------------------
    # 按 node_type 的提示词模板
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt_warm_up(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**warm-up 破冰激活**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["破冰提问", "激活旧知识", "连接到本课目标"],
  "recall_prompt": "{src}回忆性提问（引导学生回想上节课）",
  "quick_summary": "{tgt}一句话承接，说明今天重点",
  "retrieval_exercise": {{
    "type": "short_recall",
    "prompt": "1个简短回忆题",
    "answer": "参考答案"
  }},
  "teacher_line": "老师开场白（{src}）"
}}

要求：语气轻松，问题简短，重点是激活已有知识。只返回JSON。"""

    @staticmethod
    def _prompt_vocabulary_focus(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**词汇聚焦教学**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["词义辨析", "高频搭配", "词形变化/词根词缀", "快速巩固"],
  "examples": [
    {{"source": "{src}例句1", "target": "{tgt}翻译"}},
    {{"source": "{src}例句2", "target": "{tgt}翻译"}},
    {{"source": "{src}例句3", "target": "{tgt}翻译"}}
  ],
  "collocations": ["搭配1", "搭配2", "搭配3"],
  "mnemonic": "记忆线索",
  "common_mistakes": {{
    "l1_transfer": "该词常见母语迁移误用",
    "error_examples": [
      {{"wrong": "错误搭配", "correct": "正确搭配", "explanation": "解释"}}
    ]
  }},
  "exercises": [
    {{"type": "collocation_match", "prompt": "搭配匹配题", "answer": "答案"}},
    {{"type": "word_form", "prompt": "词形变化题", "answer": "答案"}}
  ],
  "scaffolding_hints": [
    {{"level": 1, "hint": "轻提示"}},
    {{"level": 2, "hint": "中提示"}},
    {{"level": 3, "hint": "强提示"}}
  ]
}}

要求：内容要体现词汇教学方法，不是泛化语法讲解。只返回JSON。"""

    @staticmethod
    def _prompt_pronunciation_drill(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}发音教练。请为以下{skill_type}生成**发音操练节点**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["目标音讲解", "示范跟读", "最小对立对比", "句级连读/语调练习"],
  "exercises": [
    {{
      "type": "phoneme_repeat",
      "prompt": "跟读目标音或单词",
      "answer": "标准发音文本",
      "target_phoneme": "目标音素"
    }},
    {{
      "type": "minimal_pairs",
      "prompt": "最小对立词辨别或朗读",
      "pairs": ["ship/sheep", "live/leave"],
      "answer": "正确区分说明"
    }},
    {{
      "type": "shadowing",
      "prompt": "按语调跟读短句",
      "answer": "参考朗读文本"
    }}
  ],
  "scaffolding_hints": [
    {{"level": 1, "hint": "口型/重音轻提示"}},
    {{"level": 2, "hint": "给节奏和停顿标记"}},
    {{"level": 3, "hint": "分音节慢速示范"}}
  ],
  "common_mistakes": {{
    "l1_transfer": "{tgt}母语者常见发音迁移",
    "correction_strategy": "逐步纠音策略"
  }},
  "teacher_line": "发音练习引导语（{src}）"
}}

要求：练习可用于音频比对与音素级反馈。只返回JSON。"""

    @staticmethod
    def _prompt_listening_comprehension(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**听力理解节点**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["听前预测", "播放音频任务", "听后核对与纠错"],
  "media_anchors": [
    {{"type": "audio", "start_ms": 0, "end_ms": 8000}}
  ],
  "quiz_items": [
    {{
      "type": "gist_question",
      "prompt": "主旨理解题",
      "answer": "标准答案"
    }},
    {{
      "type": "detail_question",
      "prompt": "细节理解题",
      "answer": "标准答案"
    }},
    {{
      "type": "dictation_chunk",
      "prompt": "听写短语",
      "answer": "标准文本"
    }}
  ],
  "follow_up_on_error": "学生听错时的分层纠正话术",
  "scaffolding_hints": [
    {{"level": 1, "hint": "先抓关键词"}},
    {{"level": 2, "hint": "给出选项范围"}},
    {{"level": 3, "hint": "提供关键词转写"}}
  ]
}}

要求：题目必须贴合音频内容，难度递进。只返回JSON。"""

    @staticmethod
    def _prompt_reading_comprehension(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**阅读理解节点**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["读前预测", "阅读任务", "读后核对与讲解"],
  "examples": [
    {{"source": "{src}阅读材料（80-140词）", "target": "{tgt}辅助译文"}}
  ],
  "quiz_items": [
    {{"type": "main_idea", "prompt": "主旨题", "answer": "标准答案"}},
    {{"type": "detail", "prompt": "细节题", "answer": "标准答案"}},
    {{"type": "inference", "prompt": "推断题", "answer": "标准答案"}}
  ],
  "follow_up_on_error": "学生读错或答错后的分层讲解",
  "scaffolding_hints": [
    {{"level": 1, "hint": "先看标题与首句"}},
    {{"level": 2, "hint": "定位关键词所在句"}},
    {{"level": 3, "hint": "给出关键句改写"}}
  ]
}}

要求：问题必须可由文本证据支持。只返回JSON。"""

    @staticmethod
    def _prompt_dialogue_practice(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**对话模拟/角色扮演**节点内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["设定场景与角色", "多轮对话目标", "复盘反馈"],
  "exercises": [
    {{
      "type": "role_play",
      "scenario": "真实场景（如点餐/面试/就医）",
      "student_role": "学生角色",
      "ai_role": "教师/对话者角色",
      "goal": "本轮交际目标",
      "success_criteria": ["目标1", "目标2"]
    }},
    {{
      "type": "repair_turn",
      "prompt": "若学生表达不清，请重述并澄清",
      "answer": "参考重述"
    }}
  ],
  "scaffolding_hints": [
    {{"level": 1, "hint": "给开场句模板"}},
    {{"level": 2, "hint": "给关键词或句型"}},
    {{"level": 3, "hint": "给完整示例回复"}}
  ],
  "follow_up_on_error": "对话中断时的引导策略",
  "teacher_line": "开始角色扮演的引导语（{src}）"
}}

要求：强调真实交际，不要变成单句填空。只返回JSON。"""

    @staticmethod
    def _prompt_dictation(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**听写节点**内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["整体听一遍", "分块听写", "核对与纠错"],
  "media_anchors": [
    {{"type": "audio", "start_ms": 0, "end_ms": 10000}}
  ],
  "exercises": [
    {{
      "type": "dictation",
      "prompt": "听写句子或短段",
      "answer": "标准文本",
      "chunks": ["chunk1", "chunk2", "chunk3"]
    }},
    {{
      "type": "dictation_correction",
      "prompt": "对比你的版本与标准版本，找出差异",
      "answer": "关键差异点"
    }}
  ],
  "common_mistakes": {{
    "l1_transfer": "易错音/弱读/连读导致的拼写误差",
    "correction_strategy": "先听节奏再补细节"
  }},
  "scaffolding_hints": [
    {{"level": 1, "hint": "先写关键词"}},
    {{"level": 2, "hint": "给出词数与标点提示"}},
    {{"level": 3, "hint": "给出首字母/词块提示"}}
  ]
}}

要求：听写内容应可分块重复播放。只返回JSON。"""

    @staticmethod
    def _prompt_error_analysis(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**错误分析（元认知）**节点内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["回放错误", "学生自我解释", "归因与策略", "再尝试"],
  "common_mistakes": {{
    "l1_transfer": "该类错误常见诱因",
    "error_examples": [
      {{"wrong": "学生常犯错误", "correct": "正确表达", "explanation": "为什么错"}}
    ],
    "correction_strategy": "下一次如何避免"
  }},
  "exercises": [
    {{
      "type": "self_explain_error",
      "prompt": "请你解释为什么这句错了、错在哪里",
      "answer": "参考元认知回答"
    }},
    {{
      "type": "rewrite_after_analysis",
      "prompt": "根据你的分析重写正确句子",
      "answer": "标准答案"
    }}
  ],
  "retrieval_exercise": {{
    "type": "error_pattern_recall",
    "prompt": "下次遇到类似句子你会先检查什么？",
    "answer": "参考检查清单"
  }}
}}

要求：强调学生自己分析错误，不是老师直接给结论。只返回JSON。"""

    @staticmethod
    def _prompt_cultural_note(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**文化背景知识**节点内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["文化背景导入", "语言点与文化关联", "跨文化对比提醒"],
  "quick_summary": "{tgt}2-3句文化说明",
  "examples": [
    {{"source": "{src}地道表达例句", "target": "{tgt}译文"}},
    {{"source": "{src}可能失礼/误解的表达", "target": "{tgt}说明"}}
  ],
  "teaching_tip": "课堂中如何避免文化误读",
  "quiz_items": [
    {{"type": "culture_check", "prompt": "这个场景下更合适的表达是？", "answer": "标准答案"}}
  ],
  "teacher_line": "文化说明引导语（{src}）"
}}

要求：信息准确、不过度刻板化。只返回JSON。"""

    @staticmethod
    def _prompt_explain(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**讲解节点**的教学内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "script_outline": ["讲解步骤1", "讲解步骤2", "讲解步骤3"],
  "examples": [
    {{"source": "{src}例句1", "target": "{tgt}翻译"}},
    {{"source": "{src}例句2", "target": "{tgt}翻译"}},
    {{"source": "{src}例句3", "target": "{tgt}翻译"}}
  ],
  "collocations": ["常见搭配1", "常见搭配2"],
  "common_mistakes": {{
    "l1_transfer": "{tgt}母语者的典型错误",
    "error_examples": [
      {{"wrong": "错误用法", "correct": "正确用法", "explanation": "解释"}}
    ]
  }},
  "mnemonic": "记忆技巧",
  "teaching_tip": "教学建议"
}}

要求：例句必须自然实用，common_mistakes 基于{tgt}母语者的真实L1迁移错误。只返回JSON。"""

    @staticmethod
    def _prompt_practice(item, ctx, skill_type, src, tgt, practice_type) -> str:
        free = practice_type == "free_practice"
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**{"自由练习" if free else "引导练习"}**的内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "exercises": [
    {{
      "type": "fill_blank",
      "prompt": "含空格的新造练习句 _______（不要用原句）",
      "answer": "答案",
      "hint": "{tgt}提示",
      "difficulty": 3
    }},
    {{
      "type": "error_correction",
      "prompt": "含有典型{tgt}母语者错误的{src}句子",
      "answer": "正确句子",
      "error_type": "错误类型",
      "explanation": "{tgt}解释"
    }},
    {{
      "type": "translation",
      "prompt": "{tgt}句子（让学生翻译成{src}）",
      "answer": "正确{src}翻译",
      "acceptable_variations": ["其他可接受翻译"]
    }}{', {"type": "use_in_sentence", "prompt": "造句指令", "example_answer": "参考答案"}' if free else ''}
  ],
  "scaffolding_hints": [
    {{"level": 1, "hint": "最轻提示"}},
    {{"level": 2, "hint": "中等提示"}},
    {{"level": 3, "hint": "直接给答案"}}
  ]
}}

要求：fill_blank 至少2题用新造句（非原句），error_correction 至少1题基于{tgt}母语者真实错误。只返回JSON。"""

    @staticmethod
    def _prompt_check(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**理解检查**的快速测验。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "quiz_items": [
    {{
      "type": "multiple_choice",
      "prompt": "题目",
      "options": ["选项A", "选项B", "选项C", "选项D"],
      "correct_index": 0
    }},
    {{
      "type": "fill_blank",
      "prompt": "快速填空题 _______",
      "answer": "答案"
    }}
  ],
  "follow_up_on_error": "学生答错后的简要纠正话术"
}}

要求：multiple_choice 的干扰项要有迷惑性但不能太离谱。只返回JSON。"""

    @staticmethod
    def _prompt_repair(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名耐心的{src}教学专家。学生在这个知识点上反复出错，请生成**修复节点**的简化教学内容。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "simplified_explanation": "用更简单的方式重新解释（{tgt}）",
  "analogy": "类比或直觉性解释",
  "minimal_examples": [
    {{"source": "最简单的例句", "target": "{tgt}翻译"}}
  ],
  "common_mistakes": {{
    "l1_transfer": "这个错误为什么会发生（母语迁移分析）",
    "correction_strategy": "具体怎么纠正这个错误"
  }},
  "micro_exercise": {{
    "type": "fill_blank",
    "prompt": "一道最简单的练习 _______",
    "answer": "答案",
    "hint": "提示"
  }}
}}

要求：一切从简，降低认知负荷。只返回JSON。"""

    @staticmethod
    def _prompt_worked_example(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为以下{skill_type}生成**示范例题**的内容（worked example）。

{item}

出现语境：
{ctx}

请返回JSON：
{{
  "problem": "呈现给学生的问题",
  "step_by_step": [
    {{"step": 1, "action": "第一步做什么", "explanation": "为什么这样做"}},
    {{"step": 2, "action": "第二步", "explanation": "解释"}},
    {{"step": 3, "action": "得出答案", "explanation": "总结"}}
  ],
  "key_insight": "这个例题想让学生学到的核心要点"
}}

只返回JSON。"""

    @staticmethod
    def _prompt_review(item, ctx, skill_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。学生之前学过这个知识点，请生成**复习节点**的快速回顾内容。

{item}

请返回JSON：
{{
  "recall_prompt": "一句话唤起学生记忆（{src}提问）",
  "quick_summary": "简短回顾（{tgt}，1-2句）",
  "retrieval_exercise": {{
    "type": "fill_blank",
    "prompt": "复习填空 _______",
    "answer": "答案"
  }}
}}

只返回JSON。"""

    @staticmethod
    def _prompt_generic(item, ctx, node_type, src, tgt) -> str:
        return f"""你是一名{src}教学专家。请为 {node_type} 类型的教学节点生成简短内容。

{item}

请返回JSON：
{{
  "script_outline": ["一句话描述这个节点要做什么"],
  "teacher_line": "老师在这个节点要说的一句话（{src}）"
}}

只返回JSON。"""

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _minimal_content(node: LiveNode, target_item: dict) -> dict:
        """LLM 失败时的最小 fallback 内容。"""
        word = target_item.get('word', '') or target_item.get('expression', '')
        trans = target_item.get('translation', '')
        return {
            "script_outline": [f"Teach '{word}' ({trans})"],
            "examples": [],
            "common_mistakes": {},
            "media_anchors": [],
        }
