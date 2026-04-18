"""Review words operations."""
from datetime import datetime

from .connection import get_db

def add_review_words(email: str, job_id: str, words: list) -> int:
    """批量添加错误单词到复习本，返回新增数量"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    added = 0
    for w in words:
        word_text = w.get("word", "").strip()
        if not word_text:
            continue
        c.execute("SELECT id FROM review_words WHERE email = ? AND job_id = ? AND word = ?",
                  (email, job_id, word_text))
        if c.fetchone():
            c.execute("UPDATE review_words SET review_count = review_count + 1, updated_at = ? WHERE email = ? AND job_id = ? AND word = ?",
                      (now, email, job_id, word_text))
        else:
            c.execute('''INSERT INTO review_words (email, job_id, word, meaning, source_lang, target_lang, word_type, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (email, job_id, word_text, w.get("meaning", ""),
                       w.get("source_lang", ""), w.get("target_lang", ""),
                       w.get("word_type", "word"), now, now))
            added += 1
    conn.commit()
    conn.close()
    return added

def get_review_words(email: str, job_id: str = None, mastered: int = None) -> list:
    """获取复习单词列表"""
    conn = get_db()
    c = conn.cursor()
    sql = "SELECT * FROM review_words WHERE email = ?"
    params = [email]
    if job_id:
        sql += " AND job_id = ?"
        params.append(job_id)
    if mastered is not None:
        sql += " AND mastered = ?"
        params.append(mastered)
    sql += " ORDER BY created_at DESC"
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_review_word(word_id: int, email: str, mastered: int) -> bool:
    """标记单词为已掌握/未掌握"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE review_words SET mastered = ?, updated_at = ? WHERE id = ? AND email = ?",
              (mastered, now, word_id, email))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

def delete_review_word(word_id: int, email: str) -> bool:
    """删除复习单词"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM review_words WHERE id = ? AND email = ?", (word_id, email))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

