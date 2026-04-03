"""Database schema initialization."""
from .connection import get_db

def init_db():
    """初始化数据库表"""
    conn = get_db()
    c = conn.cursor()

    # 用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # 添加 phone 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT UNIQUE")
    except Exception:
        pass

    # 添加 avatar_url 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass

    # 验证码表
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Token 表（用于登录）
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 用户配置表（保存样式和布局配置）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 命名配置预设表（每个用户可保存多个命名配置）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_config_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # Jobs 表（保存视频处理历史）
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            step INTEGER,
            step_name TEXT,
            source_lang TEXT,
            target_lang TEXT,
            video_filename TEXT,
            result_json TEXT,
            error TEXT,
            video_clips_pct INTEGER DEFAULT 0,
            video_write_pct INTEGER DEFAULT 0,
            name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')
    # 为旧表添加 name 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN name TEXT")
    except Exception:
        pass

    # 复习单词本
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            job_id TEXT NOT NULL,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            source_lang TEXT,
            target_lang TEXT,
            word_type TEXT DEFAULT 'word',
            mastered INTEGER DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 句子复习本（类 FSRS 调度参数）
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_sentences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            job_id TEXT NOT NULL,
            sentence_index INTEGER NOT NULL,
            sentence_text TEXT NOT NULL,
            audio_file TEXT,
            source_lang TEXT,
            target_lang TEXT,
            due_at TEXT,
            last_reviewed_at TEXT,
            reps INTEGER DEFAULT 0,
            lapses INTEGER DEFAULT 0,
            state TEXT DEFAULT 'new',
            stability REAL DEFAULT 0.6,
            difficulty REAL DEFAULT 5.0,
            last_score REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(email, job_id, sentence_index),
            FOREIGN KEY (email) REFERENCES users(email),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_sentence_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            job_id TEXT NOT NULL,
            sentence_index INTEGER NOT NULL,
            score REAL NOT NULL,
            accuracy REAL NOT NULL,
            coverage REAL NOT NULL,
            passed INTEGER NOT NULL DEFAULT 0,
            elapsed_ms INTEGER DEFAULT 0,
            mask_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            interval_days REAL DEFAULT 0,
            stability REAL DEFAULT 0.6,
            difficulty REAL DEFAULT 5.0,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES review_sentences(id),
            FOREIGN KEY (email) REFERENCES users(email),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')
    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_sentences_email_due ON review_sentences(email, due_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_sentences_email_job ON review_sentences(email, job_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_sentence_logs_email_time ON review_sentence_logs(email, reviewed_at)")

    # 统一复习题库（单词/词组/句子）
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            item_type TEXT NOT NULL,                 -- word / expression / sentence
            content_key TEXT NOT NULL,               -- 归一化去重键
            display_text TEXT NOT NULL,              -- 展示文本（答案词或完整句）
            prompt_text TEXT DEFAULT '',             -- 题面（如词义）
            answer_text TEXT DEFAULT '',             -- 标准答案（词/词组）
            audio_file TEXT DEFAULT '',              -- 句子原声切片文件名（在某个 job 下）
            source_lang TEXT DEFAULT '',
            target_lang TEXT DEFAULT '',
            mastered INTEGER DEFAULT 0,
            due_at TEXT,
            last_reviewed_at TEXT,
            reps INTEGER DEFAULT 0,
            lapses INTEGER DEFAULT 0,
            state TEXT DEFAULT 'new',
            stability REAL DEFAULT 0.6,
            difficulty REAL DEFAULT 5.0,
            last_score REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(email, item_type, content_key),
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 题库与视频关联（用于“单视频复习”过滤和句子音频定位）
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_item_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_item_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            job_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(review_item_id, job_id),
            FOREIGN KEY (review_item_id) REFERENCES review_items(id),
            FOREIGN KEY (email) REFERENCES users(email),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    # 统一复习日志（评分与排程轨迹；含 exam 中“即时加入熟词本”的 skip）
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_item_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_item_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            job_id TEXT,
            item_type TEXT NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'graded',  -- graded / mastered_skip
            score REAL NOT NULL DEFAULT 0,
            accuracy REAL NOT NULL DEFAULT 0,
            coverage REAL NOT NULL DEFAULT 0,
            passed INTEGER NOT NULL DEFAULT 0,
            elapsed_ms INTEGER DEFAULT 0,
            mask_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            interval_days REAL DEFAULT 0,
            stability REAL DEFAULT 0.6,
            difficulty REAL DEFAULT 5.0,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY (review_item_id) REFERENCES review_items(id),
            FOREIGN KEY (email) REFERENCES users(email),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    ''')

    # 复习设置（先支持全局每日最大复习量）
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_settings (
            email TEXT PRIMARY KEY,
            daily_global_max INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_items_email_due ON review_items(email, due_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_items_email_mastered ON review_items(email, mastered)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_items_email_type ON review_items(email, item_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_item_jobs_email_job ON review_item_jobs(email, job_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_review_item_logs_email_time ON review_item_logs(email, reviewed_at)")

    # 会员信息（每个用户一行）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            tier TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'inactive',
            provider TEXT,
            plan_code TEXT,
            plan_name TEXT,
            subscription_id TEXT,
            customer_id TEXT,
            country_code TEXT DEFAULT 'CN',
            started_at TEXT,
            expires_at TEXT,
            auto_renew INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            badge_unlocked INTEGER DEFAULT 0,
            doc_watermark_text TEXT DEFAULT '',
            doc_watermark_enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 会员订单流水（Stripe/支付宝）
    c.execute('''
        CREATE TABLE IF NOT EXISTS membership_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            provider TEXT NOT NULL,
            plan_code TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            checkout_url TEXT,
            subscription_id TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 每日生成统计（用于免费用户限额）
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            day TEXT NOT NULL,
            videos_generated INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(email, day),
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 旧库增量字段（忽略已存在异常）
    for _sql in [
        "ALTER TABLE user_memberships ADD COLUMN plan_name TEXT",
        "ALTER TABLE user_memberships ADD COLUMN subscription_id TEXT",
        "ALTER TABLE user_memberships ADD COLUMN customer_id TEXT",
        "ALTER TABLE user_memberships ADD COLUMN country_code TEXT DEFAULT 'CN'",
        "ALTER TABLE user_memberships ADD COLUMN auto_renew INTEGER DEFAULT 0",
        "ALTER TABLE user_memberships ADD COLUMN trial_used INTEGER DEFAULT 0",
        "ALTER TABLE user_memberships ADD COLUMN badge_unlocked INTEGER DEFAULT 0",
        "ALTER TABLE user_memberships ADD COLUMN doc_watermark_text TEXT DEFAULT ''",
        "ALTER TABLE user_memberships ADD COLUMN doc_watermark_enabled INTEGER DEFAULT 1",
    ]:
        try:
            c.execute(_sql)
        except Exception:
            pass

    conn.commit()
    conn.close()
