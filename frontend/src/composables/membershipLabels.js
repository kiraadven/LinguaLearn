const SUPPORTED = new Set(['en', 'zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es', 'ru'])

function normalizeUiLang(lang) {
  const v = String(lang || '').trim()
  if (!v) return 'en'
  const low = v.toLowerCase()
  if (low === 'zh') return 'zh-Hans'
  if (low === 'zh-hans' || low === 'zh-cn' || low === 'zh-sg') return 'zh-Hans'
  if (low === 'zh-hant' || low === 'zh-tw' || low === 'zh-hk' || low === 'zh-mo') return 'zh-Hant'
  return SUPPORTED.has(v) ? v : 'en'
}

function pick(dict, lang, fallback = '') {
  const n = normalizeUiLang(lang)
  return dict?.[n] || dict?.en || fallback
}

const PERIOD_LABELS = {
  day: {
    en: 'day',
    'zh-Hans': '天',
    'zh-Hant': '天',
    ja: '日',
    ko: '일',
    de: 'Tag',
    fr: 'jour',
    es: 'día',
    ru: 'день',
  },
  week: {
    en: 'week',
    'zh-Hans': '周',
    'zh-Hant': '週',
    ja: '週',
    ko: '주',
    de: 'Woche',
    fr: 'semaine',
    es: 'semana',
    ru: 'неделя',
  },
  month: {
    en: 'month',
    'zh-Hans': '月',
    'zh-Hant': '月',
    ja: '月',
    ko: '월',
    de: 'Monat',
    fr: 'mois',
    es: 'mes',
    ru: 'месяц',
  },
  year: {
    en: 'year',
    'zh-Hans': '年',
    'zh-Hant': '年',
    ja: '年',
    ko: '년',
    de: 'Jahr',
    fr: 'an',
    es: 'año',
    ru: 'год',
  },
}

const PLAN_LABELS = {
  cn_day: {
    en: '1-day trial',
    'zh-Hans': '1天体验价',
    'zh-Hant': '1天體驗價',
    ja: '1日体験',
    ko: '1일 체험',
    de: '1-Tages-Test',
    fr: 'Essai 1 jour',
    es: 'Prueba de 1 día',
    ru: 'Пробный 1 день',
  },
  cn_week: {
    en: 'Weekly subscription',
    'zh-Hans': '连续包周',
    'zh-Hant': '連續包週',
    ja: '週額プラン',
    ko: '주간 정기권',
    de: 'Wöchentliches Abo',
    fr: 'Abonnement hebdomadaire',
    es: 'Suscripción semanal',
    ru: 'Еженедельная подписка',
  },
  cn_month: {
    en: 'Monthly subscription',
    'zh-Hans': '连续包月',
    'zh-Hant': '連續包月',
    ja: '月額プラン',
    ko: '월간 정기권',
    de: 'Monatliches Abo',
    fr: 'Abonnement mensuel',
    es: 'Suscripción mensual',
    ru: 'Ежемесячная подписка',
  },
  cn_year: {
    en: 'Yearly subscription',
    'zh-Hans': '连续包年',
    'zh-Hant': '連續包年',
    ja: '年額プラン',
    ko: '연간 정기권',
    de: 'Jährliches Abo',
    fr: 'Abonnement annuel',
    es: 'Suscripción anual',
    ru: 'Годовая подписка',
  },
  intl_day: {
    en: '1-day trial',
    'zh-Hans': '1天试用',
    'zh-Hant': '1天試用',
    ja: '1日トライアル',
    ko: '1일 체험',
    de: '1-Tages-Test',
    fr: 'Essai 1 jour',
    es: 'Prueba de 1 día',
    ru: 'Пробный 1 день',
  },
  intl_week: {
    en: 'Weekly subscription',
    'zh-Hans': '每周订阅',
    'zh-Hant': '每週訂閱',
    ja: '週額プラン',
    ko: '주간 구독',
    de: 'Wöchentliches Abo',
    fr: 'Abonnement hebdomadaire',
    es: 'Suscripción semanal',
    ru: 'Еженедельная подписка',
  },
  intl_month: {
    en: 'Monthly subscription',
    'zh-Hans': '每月订阅',
    'zh-Hant': '每月訂閱',
    ja: '月額プラン',
    ko: '월간 구독',
    de: 'Monatliches Abo',
    fr: 'Abonnement mensuel',
    es: 'Suscripción mensual',
    ru: 'Ежемесячная подписка',
  },
  intl_year: {
    en: 'Yearly subscription',
    'zh-Hans': '每年订阅',
    'zh-Hant': '每年訂閱',
    ja: '年額プラン',
    ko: '연간 구독',
    de: 'Jährliches Abo',
    fr: 'Abonnement annuel',
    es: 'Suscripción anual',
    ru: 'Годовая подписка',
  },
}

export function formatMembershipPeriod(period, lang, fallback = '') {
  const key = String(period || '').trim()
  return pick(PERIOD_LABELS[key], lang, fallback || key)
}

export function formatMembershipPlanLabel(planCode, fallbackLabel, lang) {
  const code = String(planCode || '').trim()
  if (code && PLAN_LABELS[code]) return pick(PLAN_LABELS[code], lang, fallbackLabel || code)
  return fallbackLabel || code
}

