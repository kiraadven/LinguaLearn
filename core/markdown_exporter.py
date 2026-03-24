import os
import json
from typing import List, Dict
from datetime import datetime
from openai import OpenAI
import config


class MarkdownExporter:
    def __init__(self, output_dir: str = 'output', source_lang: str = None, target_lang: str = None):
        """
        初始化Markdown导出器

        Args:
            output_dir: 输出目录
            source_lang: 源语言代码
            target_lang: 目标语言代码（用于翻译）
        """
        self.output_dir = output_dir
        self.source_lang = source_lang or getattr(config, 'SOURCE_LANGUAGE', 'en')
        self.target_lang = target_lang or getattr(config, 'TARGET_LANGUAGE', 'zh')
        os.makedirs(output_dir, exist_ok=True)

        # 语言显示名称
        display_names = getattr(config, 'LANGUAGE_DISPLAY_NAMES', {})
        self.src_name = display_names.get(self.source_lang, {}).get(self.target_lang, self.source_lang)
        self.tgt_name = getattr(config, 'LANGUAGE_NATIVE_NAMES', {}).get(self.target_lang, self.target_lang)

        # 初始化 OpenAI 客户端
        self.api_key = config.OPENAI_API_KEY
        self.base_url = config.OPENAI_BASE_URL
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 多语言UI文本
        self._ui = self._build_ui_texts()

    def _build_ui_texts(self) -> dict:
        """构建界面文本（根据目标语言）"""
        texts = {
            'zh': {
                'title': '语言学习文字稿',
                'intro': '内容简介',
                'original': f'{self.src_name}原文',
                'sentence': '句子',
                'source_text': f'📝 {self.src_name}原文',
                'translation': f'🌐 {self.tgt_name}翻译',
                'keywords': '📚 重难点词汇',
                'expressions': '💬 有用表达',
                'word_table': '📖 词汇汇总表',
                'word_col1': '词汇', 'word_col2': '发音', 'word_col3': f'{self.tgt_name}释义',
                'dictation': '✍️ 词汇听写练习',
                'dictation_intro': '**根据翻译提示，写出对应的词汇：**',
                'expr_table': '📝 表达汇总表',
                'expr_col1': f'{self.src_name}表达', 'expr_col2': f'{self.tgt_name}释义',
                'expr_dictation': '✍️ 表达默写练习',
                'expr_dictation_intro': f'**根据{self.tgt_name}提示，写出对应的{self.src_name}表达：**',
                'footer': '本文档由LinguaLearn制作完成',
                'footer2': '坚持每天学习，语言进步！',
                'intro_prompt': f'请阅读以下{self.src_name}学习视频的文字稿内容，然后生成一段简洁的{self.tgt_name}概括性介绍（100-200字）：',
                'intro_note': f'说明这个视频的主题，涵盖主要内容要点，语言简洁明了，适合{self.src_name}学习者阅读',
                'word_hint_col1': '词汇1', 'word_hint_col2': '词汇2', 'word_hint_col3': '词汇3',
                'expr_hint_col1': '表达1', 'expr_hint_col2': '表达2',
            },
            'en': {
                'title': 'Language Learning Transcript',
                'intro': 'Introduction',
                'original': f'{self.src_name} Original',
                'sentence': 'Sentence',
                'source_text': f'📝 {self.src_name} Text',
                'translation': f'🌐 {self.tgt_name} Translation',
                'keywords': '📚 Key Vocabulary',
                'expressions': '💬 Useful Expressions',
                'word_table': '📖 Vocabulary Summary',
                'word_col1': 'Word', 'word_col2': 'Pronunciation', 'word_col3': 'Meaning',
                'dictation': '✍️ Vocabulary Practice',
                'dictation_intro': '**Write the word based on the translation hint:**',
                'expr_table': '📝 Expressions Summary',
                'expr_col1': f'{self.src_name} Expression', 'expr_col2': 'Meaning',
                'expr_dictation': '✍️ Expression Practice',
                'expr_dictation_intro': '**Write the expression based on the translation hint:**',
                'footer': 'Made by LinguaLearn',
                'footer2': 'Keep learning every day!',
                'intro_prompt': f'Read the following transcript from a {self.src_name} learning video and generate a concise English summary (100-200 words):',
                'intro_note': 'Describe the topic, cover main points, write in simple language for language learners',
                'word_hint_col1': 'Word 1', 'word_hint_col2': 'Word 2', 'word_hint_col3': 'Word 3',
                'expr_hint_col1': 'Expression 1', 'expr_hint_col2': 'Expression 2',
            },
            'ja': {
                'title': '語学学習トランスクリプト',
                'intro': '内容概要',
                'original': f'{self.src_name}原文',
                'sentence': '文',
                'source_text': f'📝 {self.src_name}テキスト',
                'translation': f'🌐 {self.tgt_name}翻訳',
                'keywords': '📚 重要語彙',
                'expressions': '💬 役立つ表現',
                'word_table': '📖 語彙まとめ',
                'word_col1': '語彙', 'word_col2': '発音', 'word_col3': '意味',
                'dictation': '✍️ 語彙練習',
                'dictation_intro': '**翻訳ヒントに基づいて語彙を書いてください：**',
                'expr_table': '📝 表現まとめ',
                'expr_col1': f'{self.src_name}表現', 'expr_col2': '意味',
                'expr_dictation': '✍️ 表現練習',
                'expr_dictation_intro': '**翻訳ヒントに基づいて表現を書いてください：**',
                'footer': 'LinguaLearnが作成',
                'footer2': '毎日学習を続けましょう！',
                'intro_prompt': f'以下の{self.src_name}学習動画のトランスクリプトを読んで、簡潔な{self.tgt_name}の概要を生成してください（100-200文字）：',
                'intro_note': '動画のテーマ、主なポイントを含め、学習者に適した言葉で',
                'word_hint_col1': '語彙1', 'word_hint_col2': '語彙2', 'word_hint_col3': '語彙3',
                'expr_hint_col1': '表現1', 'expr_hint_col2': '表現2',
            },
            'ko': {
                'title': '언어 학습 스크립트',
                'intro': '내용 소개',
                'original': f'{self.src_name} 원문',
                'sentence': '문장',
                'source_text': f'📝 {self.src_name} 텍스트',
                'translation': f'🌐 {self.tgt_name} 번역',
                'keywords': '📚 핵심 어휘',
                'expressions': '💬 유용한 표현',
                'word_table': '📖 어휘 정리',
                'word_col1': '어휘', 'word_col2': '발음', 'word_col3': '뜻',
                'dictation': '✍️ 어휘 연습',
                'dictation_intro': '**번역 힌트를 보고 어휘를 써보세요:**',
                'expr_table': '📝 표현 정리',
                'expr_col1': f'{self.src_name} 표현', 'expr_col2': '뜻',
                'expr_dictation': '✍️ 표현 연습',
                'expr_dictation_intro': '**번역 힌트를 보고 표현을 써보세요:**',
                'footer': 'LinguaLearn가 제작',
                'footer2': '매일 꾸준히 학습하세요!',
                'intro_prompt': f'다음 {self.src_name} 학습 영상의 스크립트를 읽고 간결한 {self.tgt_name} 소개(100-200자)를 작성해 주세요:',
                'intro_note': '영상의 주제, 주요 내용을 포함하고 학습자에게 적합한 언어로 작성',
                'word_hint_col1': '어휘1', 'word_hint_col2': '어휘2', 'word_hint_col3': '어휘3',
                'expr_hint_col1': '표현1', 'expr_hint_col2': '표현2',
            },
            'de': {
                'title': 'Sprachlern-Transkript',
                'intro': 'Zusammenfassung',
                'original': f'{self.src_name} Original',
                'sentence': 'Satz',
                'source_text': f'📝 {self.src_name} Text',
                'translation': f'🌐 {self.tgt_name} Übersetzung',
                'keywords': '📚 Wortschatz',
                'expressions': '💬 Nützliche Ausdrücke',
                'word_table': '📖 Vokabeln Zusammenfassung',
                'word_col1': 'Wort', 'word_col2': 'Aussprache', 'word_col3': 'Bedeutung',
                'dictation': '✍️ Wortschatz Übung',
                'dictation_intro': '**Schreiben Sie das Wort basierend auf dem Hinweis:**',
                'expr_table': '📝 Ausdrücke Zusammenfassung',
                'expr_col1': f'{self.src_name} Ausdruck', 'expr_col2': 'Bedeutung',
                'expr_dictation': '✍️ Ausdrücke Übung',
                'expr_dictation_intro': '**Schreiben Sie den Ausdruck basierend auf dem Hinweis:**',
                'footer': 'Erstellt von LinguaLearn',
                'footer2': 'Lernen Sie jeden Tag!',
                'intro_prompt': f'Lesen Sie das folgende Transkript des {self.src_name} Lernvideos und erstellen Sie eine prägnante {self.tgt_name} Zusammenfassung (100-200 Wörter):',
                'intro_note': 'Beschreiben Sie das Thema, decken Sie die wichtigsten Punkte ab, schreiben Sie in einfacher Sprache',
                'word_hint_col1': 'Wort 1', 'word_hint_col2': 'Wort 2', 'word_hint_col3': 'Wort 3',
                'expr_hint_col1': 'Ausdruck 1', 'expr_hint_col2': 'Ausdruck 2',
            },
            'fr': {
                'title': 'Transcription d\'apprentissage des langues',
                'intro': 'Introduction',
                'original': f'{self.src_name} Original',
                'sentence': 'Phrase',
                'source_text': f'📝 Texte {self.src_name}',
                'translation': f'🌐 Traduction {self.tgt_name}',
                'keywords': '📚 Vocabulaire clé',
                'expressions': '💬 Expressions utiles',
                'word_table': '📖 Résumé du vocabulaire',
                'word_col1': 'Mot', 'word_col2': 'Prononciation', 'word_col3': 'Signification',
                'dictation': '✍️ Pratique du vocabulaire',
                'dictation_intro': '**Écrivez le mot en fonction de l\'indice de traduction:**',
                'expr_table': '📝 Résumé des expressions',
                'expr_col1': f'Expression {self.src_name}', 'expr_col2': 'Signification',
                'expr_dictation': '✍️ Pratique des expressions',
                'expr_dictation_intro': '**Écrivez l\'expression en fonction de l\'indice de traduction:**',
                'footer': 'Créé par LinguaLearn',
                'footer2': 'Apprenez chaque jour!',
                'intro_prompt': f'Lisez la transcription suivante de la vidéo d\'apprentissage {self.src_name} et générez un résumé concis en {self.tgt_name} (100-200 mots):',
                'intro_note': 'Décrivez le sujet, couvrez les points principaux, écrivez dans un langage simple pour les apprenants',
                'word_hint_col1': 'Mot 1', 'word_hint_col2': 'Mot 2', 'word_hint_col3': 'Mot 3',
                'expr_hint_col1': 'Expression 1', 'expr_hint_col2': 'Expression 2',
            },
            'es': {
                'title': 'Transcripción de aprendizaje de idiomas',
                'intro': 'Introducción',
                'original': f'Original {self.src_name}',
                'sentence': 'Oración',
                'source_text': f'📝 Texto {self.src_name}',
                'translation': f'🌐 Traducción {self.tgt_name}',
                'keywords': '📚 Vocabulario clave',
                'expressions': '💬 Expresiones útiles',
                'word_table': '📖 Resumen de vocabulario',
                'word_col1': 'Palabra', 'word_col2': 'Pronunciación', 'word_col3': 'Significado',
                'dictation': '✍️ Práctica de vocabulario',
                'dictation_intro': '**Escribe la palabra según la pista de traducción:**',
                'expr_table': '📝 Resumen de expresiones',
                'expr_col1': f'Expresión {self.src_name}', 'expr_col2': 'Significado',
                'expr_dictation': '✍️ Práctica de expresiones',
                'expr_dictation_intro': '**Escribe la expresión según la pista de traducción:**',
                'footer': 'Creado por LinguaLearn',
                'footer2': '¡Aprende cada día!',
                'intro_prompt': f'Lee la siguiente transcripción del video de aprendizaje {self.src_name} y genera un resumen conciso en {self.tgt_name} (100-200 palabras):',
                'intro_note': 'Describe el tema, cubre los puntos principales, escribe en lenguaje simple para aprendices',
                'word_hint_col1': 'Palabra 1', 'word_hint_col2': 'Palabra 2', 'word_hint_col3': 'Palabra 3',
                'expr_hint_col1': 'Expresión 1', 'expr_hint_col2': 'Expresión 2',
            },
            'ru': {
                'title': 'Транскрипция для изучения языка',
                'intro': 'Введение',
                'original': f'Оригинал на {self.src_name}',
                'sentence': 'Предложение',
                'source_text': f'📝 Текст на {self.src_name}',
                'translation': f'🌐 Перевод на {self.tgt_name}',
                'keywords': '📚 Ключевой словарь',
                'expressions': '💬 Полезные выражения',
                'word_table': '📖 Итоговый словарь',
                'word_col1': 'Слово', 'word_col2': 'Произношение', 'word_col3': 'Значение',
                'dictation': '✍️ Практика словаря',
                'dictation_intro': '**Напишите слово на основе подсказки перевода:**',
                'expr_table': '📝 Итоговые выражения',
                'expr_col1': f'Выражение на {self.src_name}', 'expr_col2': 'Значение',
                'expr_dictation': '✍️ Практика выражений',
                'expr_dictation_intro': '**Напишите выражение на основе подсказки перевода:**',
                'footer': 'Создано LinguaLearn',
                'footer2': 'Учитесь каждый день!',
                'intro_prompt': f'Прочитайте следующую транскрипцию видео {self.src_name} и создайте краткое резюме на {self.tgt_name} (100-200 слов):',
                'intro_note': 'Опишите тему, охватите основные моменты, пишите простым языком для изучающих',
                'word_hint_col1': 'Слово 1', 'word_hint_col2': 'Слово 2', 'word_hint_col3': 'Слово 3',
                'expr_hint_col1': 'Выражение 1', 'expr_hint_col2': 'Выражение 2',
            },
        }
        return texts.get(self.target_lang, texts['en'])

    def _generate_introduction(self, sentences_data: List[Dict]) -> str:
        if not self.client:
            return "（请配置 OPENAI_API_KEY 以生成简介）"

        all_sentences = [s.get('original_text', '') for s in sentences_data]
        sentences_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(all_sentences[:10]))

        ui = self._ui
        prompt = f"""{ui['intro_prompt']}

{sentences_text}

请直接返回介绍内容，不要添加任何格式或前缀。介绍应该：
1. {ui['intro_note']}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的语言教学助手，擅长概括文章主旨。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"生成简介时出错: {e}")
            return "（生成简介失败）"

    def export(self, sentences_data: List[Dict], output_filename: str = None) -> str:
        """
        导出Markdown格式的文字稿

        Args:
            sentences_data: 句子数据列表
            output_filename: 输出文件名

        Returns:
            输出文件路径
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"transcript_{timestamp}.md"

        output_path = os.path.join(self.output_dir, output_filename)
        ui = self._ui

        total_sentences = len(sentences_data)
        total_words = sum(len(s.get('key_words', [])) for s in sentences_data)

        print("正在生成内容简介...")
        introduction = self._generate_introduction(sentences_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            # 头部信息
            f.write("---\nlayout: default\n")
            f.write(f"title: {ui['title']}\n---\n\n")

            # 主标题
            f.write(f"# 🌟 {ui['title']}\n\n")

            # 简介
            f.write("---\n\n")
            f.write(f"## 📖 {ui['intro']}\n\n")
            f.write(f"> *{introduction}*\n\n---\n\n")

            # 原文整合
            f.write(f"## 📄 {ui['original']}\n\n")
            for i, sentence_data in enumerate(sentences_data, 1):
                original_text = sentence_data['original_text']
                original_text = original_text.rstrip('.!?。！？')
                f.write(f"*{original_text}.* ")
            f.write("\n\n---\n\n")

            # 每个句子的详细内容
            for i, sentence_data in enumerate(sentences_data, 1):
                f.write(f'<div class="sentence-card" id="句子-{i}">\n\n')
                f.write(f"## 🔹 {ui['sentence']} {i}\n\n")

                original_text = sentence_data['original_text']

                f.write(f"### {ui['source_text']}\n\n")
                f.write(f"> **{original_text}**\n\n")

                f.write(f"### {ui['translation']}\n\n")
                f.write(f"> *{sentence_data['chinese_translation']}*")

                # 重难点词汇
                keywords = sentence_data.get('key_words', [])
                if keywords:
                    f.write(f"\n\n### {ui['keywords']}\n\n")
                    f.write(f"| 序号 | {ui['word_col1']} | {ui['word_col2']} | {ui['word_col3']} |\n")
                    f.write("|:---:|:---:|:---:|:---:|\n")
                    for j, word_info in enumerate(keywords, 1):
                        word = word_info.get('word', '')
                        phonetic = word_info.get('phonetic', '')
                        translation = word_info.get('translation', '')
                        f.write(f"| {j} | **{word}** | {phonetic} | {translation} |\n")
                    f.write("\n")

                # 有用表达
                expressions = sentence_data.get('useful_expressions', [])
                if expressions:
                    f.write(f"### {ui['expressions']}\n\n")
                    for expr in expressions:
                        english = expr.get('english', '')
                        chinese = expr.get('chinese', '')
                        if english and chinese:
                            f.write(f"- **{english}** — {chinese}\n")
                    f.write("\n")

                f.write("</div>\n\n---\n\n")

            # 词汇汇总表
            f.write(f"## {ui['word_table']}\n\n")
            all_words = []
            seen_words = set()
            for sentence_data in sentences_data:
                for word_info in sentence_data.get('key_words', []):
                    word = word_info.get('word', '').lower()
                    if word and word not in seen_words:
                        seen_words.add(word)
                        all_words.append(word_info)

            import random
            random.seed(42)
            shuffled_words = all_words.copy()
            random.shuffle(shuffled_words)

            if shuffled_words:
                f.write(f"| {ui['word_col1']} | {ui['word_col2']} | {ui['word_col3']} |\n")
                f.write("|:---:|:---:|:---:|\n")
                for word_info in shuffled_words:
                    word = word_info.get('word', '')
                    phonetic = word_info.get('phonetic', '')
                    translation = word_info.get('translation', '')
                    f.write(f"| **{word}** | {phonetic} | {translation} |\n")

            f.write("\n---\n\n")

            # 词汇听写练习
            f.write(f"## {ui['dictation']}\n\n")
            f.write(f"{ui['dictation_intro']}\n\n")

            if shuffled_words:
                f.write("<table style='width:100%; table-layout:fixed; text-align:center;'>\n")
                f.write(f"<tr><th style='width:33%'>{ui['word_hint_col1']}</th>"
                        f"<th style='width:33%'>{ui['word_hint_col2']}</th>"
                        f"<th style='width:33%'>{ui['word_hint_col3']}</th></tr>\n")
                for i in range(0, len(shuffled_words), 3):
                    row = shuffled_words[i:i+3]
                    while len(row) < 3:
                        row.append({'translation': '', 'word': ''})
                    f.write(f"<tr><td>{row[0]['translation']} __________ </td>"
                            f"<td>{row[1]['translation']} __________ </td>"
                            f"<td>{row[2]['translation']} __________ </td></tr>\n")
                f.write("</table>\n")

            f.write("\n---\n\n")

            # 表达汇总表
            f.write(f"## {ui['expr_table']}\n\n")
            all_expressions = []
            seen_expressions = set()
            for sentence_data in sentences_data:
                for expr in sentence_data.get('useful_expressions', []):
                    english = expr.get('english', '').lower()
                    if english and english not in seen_expressions:
                        seen_expressions.add(english)
                        all_expressions.append(expr)

            if all_expressions:
                f.write(f"| {ui['expr_col1']} | {ui['expr_col2']} |\n")
                f.write("|:---|:---|\n")
                for expr in all_expressions:
                    english = expr.get('english', '')
                    chinese = expr.get('chinese', '')
                    f.write(f"| **{english}** | {chinese} |\n")

            f.write("\n---\n\n")

            # 表达默写练习
            f.write(f"## {ui['expr_dictation']}\n\n")
            f.write(f"{ui['expr_dictation_intro']}\n\n")

            if all_expressions:
                import random
                random.seed(42)
                shuffled_exprs = all_expressions.copy()
                random.shuffle(shuffled_exprs)

                f.write("<table style='width:100%; table-layout:fixed; text-align:center;'>\n")
                f.write(f"<tr><th style='width:50%'>{ui['expr_hint_col1']}</th>"
                        f"<th style='width:50%'>{ui['expr_hint_col2']}</th></tr>\n")
                for i in range(0, len(shuffled_exprs), 2):
                    row = shuffled_exprs[i:i+2]
                    while len(row) < 2:
                        row.append({'chinese': '', 'english': ''})
                    f.write(f"<tr><td>{row[0]['chinese']} ____________________ </td>"
                            f"<td>{row[1]['chinese']} ____________________ </td></tr>\n")
                f.write("</table>\n")

            f.write("\n---\n\n")

            # 页脚
            f.write('<div align="center">\n\n')
            f.write(f"*📚 {ui['footer']}*\n\n")
            f.write(f"*{ui['footer2']}* 🚀\n\n")
            f.write("</div>\n")

        print(f"Markdown文字稿已导出到: {output_path}")
        return output_path
