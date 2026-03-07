import os
import subprocess
import tempfile
import time
from typing import Dict, List, Optional
import config


class HTMLRenderer:
    """使用 Headless Chrome 渲染 HTML 为 PNG"""
    
    def __init__(self, templates_dir: str = None):
        """
        初始化渲染器
        
        Args:
            templates_dir: 模板目录路径
        """
        if templates_dir is None:
            # 默认使用当前文件所在目录的 templates 文件夹
            current_dir = os.path.dirname(os.path.abspath(__file__))
            templates_dir = os.path.join(current_dir, 'templates')
        
        self.templates_dir = templates_dir
        
        # 检查 Chrome 是否可用
        self.chrome_path = self._find_chrome()
        if not self.chrome_path:
            raise RuntimeError("未找到 Chrome 浏览器，请安装 Google Chrome")
    
    def _find_chrome(self) -> Optional[str]:
        """查找 Chrome 浏览器路径"""
        possible_paths = [
            # macOS
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            # Linux
            '/usr/bin/google-chrome',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            # Windows
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 尝试通过 which 命令查找
        try:
            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return None
    
    def _read_template(self, template_name: str) -> str:
        """读取 HTML 模板"""
        template_path = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _render_html_to_png(self, html_content: str, output_path: str, width: int, height: int) -> bool:
        """
        使用 Chrome 渲染 HTML 为 PNG
        
        Args:
            html_content: HTML 内容
            output_path: 输出 PNG 路径
            width: 宽度
            height: 高度
            
        Returns:
            是否成功
        """
        # 重试配置
        max_retries = 3
        base_timeout = 60  # 基础超时时间 60 秒
        
        for attempt in range(max_retries):
            # 创建临时 HTML 文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                html_path = f.name
            
            # 添加额外边距确保内容不被截断
            extra_margin = 0
            render_width = width + extra_margin
            render_height = height + extra_margin
            
            try:
                # Chrome 命令 - 优化参数提高渲染速度
                cmd = [
                    self.chrome_path,
                    '--headless=new',
                    '--disable-gpu',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--metrics-recording-only',
                    '--mute-audio',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                    f'--window-size={render_width},{render_height}',
                    '--screenshot=' + output_path,
                    '--hide-scrollbars',
                    '--force-clock-backwards',
                    '--disable-features=TranslateUI',
                    '--virtual-time-budget=10000',
                    html_path
                ]
                
                # 使用递增超时时间（每次重试增加时间）
                timeout = base_timeout + (attempt * 30)
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
                    print(f"Chrome 渲染失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # 重试前等待
                        continue
                    return False
                
                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return True
                else:
                    print(f"Chrome 渲染失败：输出文件不存在或为空 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return False
                    
            except subprocess.TimeoutExpired:
                print(f"Chrome 渲染超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(3)  # 超时后等待更久
                    continue
                return False
            except Exception as e:
                print(f"Chrome 渲染异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return False
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(html_path):
                        os.unlink(html_path)
                except:
                    pass
        
        return False
    
    def render_subtitle(self, english_text: str, chinese_text: str, 
                       width: int, height: int, output_path: str) -> bool:
        """
        渲染字幕框
        
        Args:
            english_text: 英文文本
            chinese_text: 中文文本
            width: 宽度
            height: 高度
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        # 动态计算字体大小 - 根据高度（1080p适配，整体放大）
        # 调大字体，方便学习和阅读
        base_font_size_en = int(height * 0.19)
        base_font_size_cn = int(height * 0.13)
        
        # 根据文本长度调整（文本越长，字体越小）
        en_len = len(english_text)
        cn_len = len(chinese_text)
        
        # 英文文本长度调整
        if en_len > 80:
            scale_factor = 0.14
        elif en_len > 60:
            scale_factor = 0.20
        elif en_len > 50:
            scale_factor = 0.30
        elif en_len > 40:
            scale_factor = 0.40
        elif en_len > 30:
            scale_factor = 0.60
        elif en_len > 20:
            scale_factor = 0.80
        else:
            scale_factor = 1.0
        
        # 调大字体上限，方便学习和阅读
        font_size_en = min(55, int(base_font_size_en * scale_factor))
        font_size_cn = min(45, int(base_font_size_cn * scale_factor))
        
        # 确保字体不会太小（1080p适配）- 调大最小值方便阅读
        font_size_en = max(font_size_en, 16)
        font_size_cn = max(font_size_cn, 12)
        
        # 读取模板并替换变量
        template = self._read_template('subtitle_template.html')
        html = template.replace('{{width}}', str(width))
        html = html.replace('{{height}}', str(height))
        html = html.replace('{{font_size_en}}', str(font_size_en))
        html = html.replace('{{font_size_cn}}', str(font_size_cn))
        html = html.replace('{{english_text}}', english_text)
        html = html.replace('{{chinese_text}}', chinese_text)
        # 颜色配置
        html = html.replace('{{bg_color}}', config.SUBTITLE_BOX_BG_COLOR)
        html = html.replace('{{en_color}}', config.SUBTITLE_BOX_ENGLISH_COLOR)
        html = html.replace('{{cn_color}}', config.SUBTITLE_BOX_CHINESE_COLOR)
        
        return self._render_html_to_png(html, output_path, width, height)
    
    def render_wordbox(self, words: List[Dict], 
                      width: int, height: int, output_path: str) -> bool:
        """
        渲染单词框
        
        Args:
            words: 单词列表
            width: 宽度
            height: 高度
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        # 根据单词数量动态调整字体大小（支持4-6个单词）
        num_words = min(len(words), 6)
        
        # 基于高度的计算 - 1080p适配，整体放大
        base_font_word = int(height * 0.07)
        base_font_phonetic = int(height * 0.045)
        base_font_trans = int(height * 0.05)
        
        # 根据单词数量动态调整 - 单词越多，字体越小
        height_factor = 1.0
        if num_words >= 6:
            height_factor = 0.10
        elif num_words >= 5:
            height_factor = 0.20
        elif num_words >= 4:
            height_factor = 0.45
        elif num_words >= 3:
            height_factor = 0.8
        elif num_words >= 2:
            height_factor = 0.9
        
        # 设置字号范围（1080p适配）
        font_size_word = max(16, min(44, int(base_font_word * height_factor)))
        font_size_phonetic = max(12, min(28, int(base_font_phonetic * height_factor)))
        font_size_trans = max(14, min(32, int(base_font_trans * height_factor)))
        
        # 读取模板
        template = self._read_template('wordbox_template.html')
        
        # 替换基础变量
        html = template.replace('{{width}}', str(width))
        html = html.replace('{{h}}', str(height))
        html = html.replace('{{font_size_word}}', str(font_size_word))
        html = html.replace('{{font_size_phonetic}}', str(font_size_phonetic))
        html = html.replace('{{font_size_trans}}', str(font_size_trans))
        # 颜色配置
        html = html.replace('{{bg_color}}', config.WORD_BOX_BG_COLOR)
        html = html.replace('{{word_color}}', config.WORD_BOX_WORD_COLOR)
        html = html.replace('{{phonetic_color}}', config.WORD_BOX_PHONETIC_COLOR)
        html = html.replace('{{trans_color}}', config.WORD_BOX_TRANS_COLOR)
        
        # 生成单词列表 HTML - 使用新的 .word-item 结构
        words_html = ""
        for word_info in words[:6]:  # 最多显示6个单词
            word = word_info.get('word', '')
            phonetic = word_info.get('phonetic', '')
            translation = word_info.get('translation', '')
            
            word_html = '<div class="word-item">'                 '<div class="word-row">'                     '<div class="word">' + word + '</div>'                     '<div class="phonetic">' + phonetic + '</div>'                 '</div>'                 '<div class="translation">' + translation + '</div>'             '</div>'
            words_html += word_html
        
        # 替换模板中的单词列表
        html = html.replace('{{words_html}}', words_html)
        
        return self._render_html_to_png(html, output_path, width, height)
    
    def render_expressionbox(self, expressions: List[Dict], 
                             width: int, height: int, output_path: str) -> bool:
        """
        渲染表达框
        
        Args:
            expressions: 表达列表
            width: 宽度
            height: 高度
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        # 根据表达数量动态调整字体大小（支持1-3个表达）
        num_exprs = min(len(expressions), 3)
        
        # 基于高度的计算 - 1080p适配，整体放大
        # 调大字体，方便学习和阅读
        base_font_en = int(height * 0.10)
        base_font_cn = int(height * 0.07)
        
        # 根据表达数量动态调整
        height_factor = 1.0
        if num_exprs >= 3:
            height_factor = 0.30
        elif num_exprs >= 2:
            height_factor = 0.65
        
        # 设置字号范围（1080p适配）- 调大方便阅读
        font_size_en = max(16, min(36, int(base_font_en * height_factor)))
        font_size_cn = max(14, min(28, int(base_font_cn * height_factor)))
        
        # 读取模板
        template = self._read_template('expressionbox_template.html')
        
        # 替换基础变量
        html = template.replace('{{width}}', str(width))
        html = html.replace('{{h}}', str(height))
        html = html.replace('{{font_size_en}}', str(font_size_en))
        html = html.replace('{{font_size_cn}}', str(font_size_cn))
        # 颜色配置
        html = html.replace('{{bg_color}}', config.EXPR_BOX_BG_COLOR)
        html = html.replace('{{en_color}}', config.EXPR_BOX_ENGLISH_COLOR)
        html = html.replace('{{cn_color}}', config.EXPR_BOX_CHINESE_COLOR)
        
        # 生成表达列表 HTML
        expressions_html = ""
        for expr_info in expressions[:3]:  # 最多显示3个表达
            english = expr_info.get('english', '')
            chinese = expr_info.get('chinese', '')
            
            expr_html = '<div class="expr-item">' \
                        '<div class="expr-english">' + english + '</div>' \
                        '<div class="expr-chinese">' + chinese + '</div>' \
                        '</div>'
            expressions_html += expr_html
        
        # 替换模板中的表达列表
        html = html.replace('{{expressions_html}}', expressions_html)
        
        return self._render_html_to_png(html, output_path, width, height)
