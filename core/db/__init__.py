"""Composed database API split from the legacy monolithic DB module."""

from .connection import DB_FILE, get_db
from .schema import init_db
from .users import (
    user_exists, create_user, get_user, update_user_password,
    user_exists_by_phone, get_user_by_phone, create_user_with_phone, update_user_phone,
)
from .verification import (
    save_verification_code, get_verification_code, verify_code, delete_verification_code,
)
from .tokens import save_token, get_token_email, delete_token
from .configs import (
    save_user_config, get_user_config, save_config_preset, get_config_presets, delete_config_preset,
)
from .jobs import (
    save_job, update_job_status, get_job, get_user_jobs, delete_job, update_user_avatar, bind_email,
)
from .review_words import (
    add_review_words, get_review_words, update_review_word, delete_review_word,
)
from .review_sentences import (
    upsert_review_sentences, list_review_sentences, get_review_sentence_item,
    record_review_sentence_result, get_review_sentence_stats,
)
from .review_items import (
    ensure_review_settings, get_review_settings, update_review_settings,
    upsert_review_items, list_candidate_review_items, get_review_item,
    set_review_item_mastered, list_mastered_review_items, record_review_item_result,
    log_mastered_skip, get_today_review_count,
)
from .membership import (
    ensure_user_membership, get_user_membership, update_user_membership, mark_trial_used,
    get_today_usage, increment_daily_video_usage, save_membership_order, update_membership_order,
    get_membership_order, get_membership_order_by_subscription,
)

# Keep import side-effect same as legacy module.
init_db()
