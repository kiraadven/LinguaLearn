/**
 * Theme Mapper — maps styleId to element style properties
 * 22 aesthetic themes with optional background overlay colors
 */

export const STYLE_THEMES = {
  neon_cyberpunk: {
    name: '赛博霓虹',
    desc: '黑底荧光青粉，数字朋克科技感，高对比度霓虹发光',
    preview_colors: { bg: '#000000', src: '#00ffff', tgt: '#ff0080', box_bg: '#0a0a15' },
    backgroundColor: 'rgba(0,0,0,0.50)',
    defaultAnimation: 'pop',
    subtitle: {
      bgColor: 'rgba(10,10,21,0.92)', bgStyle: 'dark',
      textColor: '#00ffff', translationColor: '#ff0080',
      borderRadius: 4,
    },
    wordbox: {
      bgColor: 'rgba(10,10,21,0.95)',
      wordColor: '#00ffff', phoneticColor: '#ff00ff', translationColor: '#ffffff',
      accentColor: '#00ffff', headerColor: '#ff0080',
      borderRadius: 4,
    },
    exprbox: {
      bgColor: 'rgba(10,10,21,0.95)',
      expressionColor: '#ff0080', translationColor: '#ffffff',
      accentColor: '#ff0080', headerColor: '#00ffff',
      borderRadius: 4,
    },
    effects: {
      textShadow: '0 0 12px rgba(0,255,255,0.8), 0 0 20px rgba(255,0,128,0.5)',
      textHighlightColor: 'rgba(0,255,255,0.15)',
      textGlow: 'drop-shadow(0 0 8px #00ffff)',
    },
  },

  forest_ink: {
    name: '森林水墨',
    desc: '深绿毛笔感，米白文字，东方水墨意蕴',
    preview_colors: { bg: '#1b3d2a', src: '#e8f5e9', tgt: '#81c784', box_bg: '#0d261a' },
    backgroundColor: 'rgba(27,61,42,0.45)',
    defaultAnimation: 'slide_up',
    subtitle: {
      bgColor: 'rgba(27,61,42,0.88)', bgStyle: 'dark',
      textColor: '#e8f5e9', translationColor: '#81c784',
      borderRadius: 6,
    },
    wordbox: {
      bgColor: 'rgba(13,38,26,0.92)',
      wordColor: '#ffffff', phoneticColor: '#a5d6a7', translationColor: '#e8f5e9',
      accentColor: '#81c784', headerColor: '#a5d6a7',
      borderRadius: 6,
    },
    exprbox: {
      bgColor: 'rgba(13,38,26,0.92)',
      expressionColor: '#ffeb3b', translationColor: '#e8f5e9',
      accentColor: '#ffeb3b', headerColor: '#81c784',
      borderRadius: 6,
    },
    effects: {
      textShadow: '0 1px 3px rgba(0,0,0,0.7)',
      textHighlightColor: 'rgba(129,199,132,0.2)',
    },
  },

  sunset_gradient: {
    name: '日落渐变',
    desc: '橙红渐变背景，温暖高饱和，傍晚学习氛围',
    preview_colors: { bg: '#5a2d1f', src: '#ffb74d', tgt: '#ff8a65', box_bg: '#6d3d2f' },
    backgroundColor: 'rgba(90,45,31,0.45)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(90,45,31,0.88)', bgStyle: 'dark',
      textColor: '#ffb74d', translationColor: '#ff8a65',
      borderRadius: 8,
    },
    wordbox: {
      bgColor: 'rgba(109,61,47,0.92)',
      wordColor: '#ffb74d', phoneticColor: '#ff8a65', translationColor: '#ffebcd',
      accentColor: '#ffb74d', headerColor: '#ff8a65',
      borderRadius: 8,
    },
    exprbox: {
      bgColor: 'rgba(109,61,47,0.92)',
      expressionColor: '#ff6f00', translationColor: '#ffebcd',
      accentColor: '#ff6f00', headerColor: '#ffb74d',
      borderRadius: 8,
    },
    effects: {
      textShadow: '0 0 8px rgba(255,183,77,0.4)',
      textHighlightColor: 'rgba(255,138,101,0.25)',
      textGlow: 'drop-shadow(0 0 6px rgba(255,183,77,0.6))',
    },
  },

  arctic_minimal: {
    name: '极地简约',
    desc: '纯白冰蓝，极简设计，清冷专注的高效学习',
    preview_colors: { bg: '#f0f4ff', src: '#1976d2', tgt: '#5c6bc0', box_bg: '#e8eef7' },
    backgroundColor: 'rgba(232,238,247,0.40)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(232,238,247,0.92)', bgStyle: 'light',
      textColor: '#1976d2', translationColor: '#5c6bc0',
      borderRadius: 6,
    },
    wordbox: {
      bgColor: 'rgba(240,244,255,0.95)',
      wordColor: '#1565c0', phoneticColor: '#5c6bc0', translationColor: '#37474f',
      accentColor: '#1976d2', headerColor: '#5c6bc0',
      borderRadius: 6,
    },
    exprbox: {
      bgColor: 'rgba(240,244,255,0.95)',
      expressionColor: '#0d47a1', translationColor: '#37474f',
      accentColor: '#0d47a1', headerColor: '#1976d2',
      borderRadius: 6,
    },
    effects: {
      textShadow: '0 0.5px 2px rgba(0,0,0,0.1)',
      textHighlightColor: 'rgba(25,118,210,0.1)',
    },
  },

  royal_purple: {
    name: '皇家紫',
    desc: '深紫金色，奢华尊贵，精英品质学习体验',
    preview_colors: { bg: '#2d1b4e', src: '#d4a5d4', tgt: '#ffd700', box_bg: '#3f2765' },
    backgroundColor: 'rgba(45,27,78,0.45)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(45,27,78,0.88)', bgStyle: 'dark',
      textColor: '#d4a5d4', translationColor: '#ffd700',
      borderRadius: 8,
    },
    wordbox: {
      bgColor: 'rgba(63,39,101,0.92)',
      wordColor: '#d4a5d4', phoneticColor: '#ffd700', translationColor: '#f3e5f5',
      accentColor: '#d4a5d4', headerColor: '#ffd700',
      borderRadius: 8,
    },
    exprbox: {
      bgColor: 'rgba(63,39,101,0.92)',
      expressionColor: '#ffd700', translationColor: '#f3e5f5',
      accentColor: '#ffd700', headerColor: '#d4a5d4',
      borderRadius: 8,
    },
    effects: {
      textShadow: '0 0 12px rgba(255,215,0,0.4)',
      textHighlightColor: 'rgba(212,165,212,0.2)',
    },
  },

  retro_terminal: {
    name: '复古终端',
    desc: '磷光绿CRT风格，扫描线，80年代计算机美学',
    preview_colors: { bg: '#001100', src: '#00ff00', tgt: '#88ff88', box_bg: '#0a2a0a' },
    backgroundColor: 'rgba(0,17,0,0.50)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(0,17,0,0.92)', bgStyle: 'dark',
      textColor: '#00ff00', translationColor: '#88ff88',
      borderRadius: 0,
    },
    wordbox: {
      bgColor: 'rgba(10,42,10,0.95)',
      wordColor: '#00ff00', phoneticColor: '#88ff88', translationColor: '#00ff00',
      accentColor: '#00ff00', headerColor: '#88ff88',
      borderRadius: 0,
    },
    exprbox: {
      bgColor: 'rgba(10,42,10,0.95)',
      expressionColor: '#00ff00', translationColor: '#00ff00',
      accentColor: '#00ff00', headerColor: '#88ff88',
      borderRadius: 0,
    },
    effects: {
      textShadow: '0 0 10px rgba(0,255,0,0.8)',
      textHighlightColor: 'rgba(0,255,0,0.15)',
      textGlow: 'drop-shadow(0 0 10px #00ff00)',
    },
  },

  aurora_night: {
    name: '极光暗夜',
    desc: '深紫背景，紫粉渐变高亮，沉浸式暗色学习体验',
    preview_colors: { bg: '#0f0f1e', src: '#a78bfa', tgt: '#94a3b8', box_bg: '#1a1a2e' },
    backgroundColor: 'rgba(15,15,30,0.45)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(26,26,46,0.85)', bgStyle: 'dark',
      textColor: '#a78bfa', translationColor: '#94a3b8',
      borderRadius: 10,
    },
    wordbox: {
      bgColor: 'rgba(15,15,30,0.9)',
      wordColor: '#bfa8ff', phoneticColor: '#94a3b8', translationColor: '#f1f5f9',
      accentColor: '#a78bfa', headerColor: '#94a3b8',
      borderRadius: 10,
    },
    exprbox: {
      bgColor: 'rgba(15,15,30,0.9)',
      expressionColor: '#f472b6', translationColor: '#f1f5f9',
      accentColor: '#f472b6', headerColor: '#94a3b8',
      borderRadius: 10,
    },
    effects: {
      textShadow: '0 0 12px rgba(167,139,250,0.4)',
    },
  },

  cherry_blossom: {
    name: '樱花物语',
    desc: '浅粉樱花配色，圆角柔和，日系温柔学习风格',
    preview_colors: { bg: '#fff5f9', src: '#c2185b', tgt: '#f06292', box_bg: '#fce4f3' },
    backgroundColor: 'rgba(252,228,243,0.40)',
    defaultAnimation: 'pop',
    subtitle: {
      bgColor: 'rgba(252,228,243,0.92)', bgStyle: 'light',
      textColor: '#c2185b', translationColor: '#f06292',
      borderRadius: 16,
    },
    wordbox: {
      bgColor: 'rgba(255,245,249,0.95)',
      wordColor: '#c2185b', phoneticColor: '#f06292', translationColor: '#212121',
      accentColor: '#ec407a', headerColor: '#c2185b',
      borderRadius: 16,
    },
    exprbox: {
      bgColor: 'rgba(255,245,249,0.95)',
      expressionColor: '#ec407a', translationColor: '#212121',
      accentColor: '#ec407a', headerColor: '#c2185b',
      borderRadius: 16,
    },
    effects: {
      textShadow: '0 0 6px rgba(194,24,91,0.15)',
      textHighlightColor: 'rgba(240,98,146,0.2)',
    },
  },

  midnight_ocean: {
    name: '深海午夜',
    desc: '深蓝流光，青色脉动，深邃神秘的海洋意象',
    preview_colors: { bg: '#0a1929', src: '#29b6f6', tgt: '#80deea', box_bg: '#0d2d4a' },
    backgroundColor: 'rgba(10,25,41,0.50)',
    defaultAnimation: 'slide_up',
    subtitle: {
      bgColor: 'rgba(10,25,41,0.88)', bgStyle: 'dark',
      textColor: '#29b6f6', translationColor: '#80deea',
      borderRadius: 10,
    },
    wordbox: {
      bgColor: 'rgba(13,45,74,0.92)',
      wordColor: '#29b6f6', phoneticColor: '#80deea', translationColor: '#e0f7ff',
      accentColor: '#29b6f6', headerColor: '#80deea',
      borderRadius: 10,
    },
    exprbox: {
      bgColor: 'rgba(13,45,74,0.92)',
      expressionColor: '#00bcd4', translationColor: '#e0f7ff',
      accentColor: '#00bcd4', headerColor: '#29b6f6',
      borderRadius: 10,
    },
    effects: {
      textShadow: '0 0 12px rgba(41,182,246,0.4)',
      textHighlightColor: 'rgba(0,188,212,0.2)',
      textGlow: 'drop-shadow(0 0 8px rgba(41,182,246,0.5))',
    },
  },

  golden_age: {
    name: '黄金时代',
    desc: '深棕金色，复古纸张质感，经典怀旧学习氛围',
    preview_colors: { bg: '#3e2723', src: '#daa520', tgt: '#cd7f32', box_bg: '#4e342e' },
    backgroundColor: 'rgba(62,39,35,0.45)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(62,39,35,0.88)', bgStyle: 'dark',
      textColor: '#daa520', translationColor: '#cd7f32',
      borderRadius: 8,
    },
    wordbox: {
      bgColor: 'rgba(78,52,46,0.92)',
      wordColor: '#daa520', phoneticColor: '#cd7f32', translationColor: '#f5deb3',
      accentColor: '#daa520', headerColor: '#cd7f32',
      borderRadius: 8,
    },
    exprbox: {
      bgColor: 'rgba(78,52,46,0.92)',
      expressionColor: '#ffb923', translationColor: '#f5deb3',
      accentColor: '#ffb923', headerColor: '#daa520',
      borderRadius: 8,
    },
    effects: {
      textShadow: '0 1px 3px rgba(0,0,0,0.6)',
      textHighlightColor: 'rgba(218,165,32,0.2)',
    },
  },

  volcanic_ash: {
    name: '火山灰烬',
    desc: '深灰橙红，熔岩质感，炽热激情的能量学习',
    preview_colors: { bg: '#2c2416', src: '#ff6e40', tgt: '#e64a19', box_bg: '#3d322a' },
    backgroundColor: 'rgba(44,36,22,0.45)',
    defaultAnimation: 'pop',
    subtitle: {
      bgColor: 'rgba(44,36,22,0.88)', bgStyle: 'dark',
      textColor: '#ff6e40', translationColor: '#e64a19',
      borderRadius: 6,
    },
    wordbox: {
      bgColor: 'rgba(61,50,42,0.92)',
      wordColor: '#ff6e40', phoneticColor: '#e64a19', translationColor: '#fff8e1',
      accentColor: '#ff6e40', headerColor: '#e64a19',
      borderRadius: 6,
    },
    exprbox: {
      bgColor: 'rgba(61,50,42,0.92)',
      expressionColor: '#ff5722', translationColor: '#fff8e1',
      accentColor: '#ff5722', headerColor: '#ff6e40',
      borderRadius: 6,
    },
    effects: {
      textShadow: '0 0 10px rgba(255,110,64,0.4)',
      textHighlightColor: 'rgba(255,87,34,0.25)',
      textGlow: 'drop-shadow(0 0 8px rgba(255,110,64,0.6))',
    },
  },

  spring_meadow: {
    name: '春日草原',
    desc: '浅绿白底，翠绿文字，清新自然的绿色草原气息',
    preview_colors: { bg: '#f0fdf4', src: '#15803d', tgt: '#16a34a', box_bg: '#dcfce7' },
    backgroundColor: null,
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(220,252,231,0.93)', bgStyle: 'light',
      textColor: '#15803d', translationColor: '#16a34a',
      borderRadius: 10,
    },
    wordbox: {
      bgColor: 'rgba(240,253,244,0.96)',
      wordColor: '#15803d', phoneticColor: '#16a34a', translationColor: '#166534',
      accentColor: '#22c55e', headerColor: '#16a34a',
      borderRadius: 10,
    },
    exprbox: {
      bgColor: 'rgba(240,253,244,0.96)',
      expressionColor: '#15803d', translationColor: '#166534',
      accentColor: '#22c55e', headerColor: '#15803d',
      borderRadius: 10,
    },
  },

  ink_wash: {
    name: '写意水墨',
    desc: '米色宣纸，墨黑文字，传统水墨书法意蕴',
    preview_colors: { bg: '#fffbf0', src: '#3f3f3f', tgt: '#5a5a5a', box_bg: '#f5f1ed' },
    backgroundColor: 'rgba(245,241,237,0.35)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(245,241,237,0.92)', bgStyle: 'light',
      textColor: '#3f3f3f', translationColor: '#5a5a5a',
      borderRadius: 4,
    },
    wordbox: {
      bgColor: 'rgba(255,251,240,0.95)',
      wordColor: '#2c2c2c', phoneticColor: '#5a5a5a', translationColor: '#3f3f3f',
      accentColor: '#3f3f3f', headerColor: '#5a5a5a',
      borderRadius: 4,
    },
    exprbox: {
      bgColor: 'rgba(255,251,240,0.95)',
      expressionColor: '#2c2c2c', translationColor: '#3f3f3f',
      accentColor: '#2c2c2c', headerColor: '#5a5a5a',
      borderRadius: 4,
    },
    effects: {
      textShadow: '0 0.5px 1px rgba(0,0,0,0.2)',
      textHighlightColor: 'rgba(100,100,100,0.1)',
    },
  },

  // ── 9 New Themes ──

  coral_reef: {
    name: '珊瑚礁石',
    desc: '暖奶油白底，橙红珊瑚文字，温润明朗的热带气息',
    preview_colors: { bg: '#fff8f2', src: '#c2410c', tgt: '#ea580c', box_bg: '#fff1e8' },
    backgroundColor: null,
    defaultAnimation: 'slide_up',
    subtitle: {
      bgColor: 'rgba(255,241,232,0.93)', bgStyle: 'light',
      textColor: '#c2410c', translationColor: '#ea580c',
      borderRadius: 10,
    },
    wordbox: {
      bgColor: 'rgba(255,248,242,0.96)',
      wordColor: '#c2410c', phoneticColor: '#ea580c', translationColor: '#9a3412',
      accentColor: '#f97316', headerColor: '#ea580c',
      borderRadius: 10,
    },
    exprbox: {
      bgColor: 'rgba(255,248,242,0.96)',
      expressionColor: '#c2410c', translationColor: '#9a3412',
      accentColor: '#f97316', headerColor: '#c2410c',
      borderRadius: 10,
    },
  },

  lavender_dream: {
    name: '薰衣草梦境',
    desc: '柔和薰衣草与奶油白，宁静治愈的梦幻空间',
    preview_colors: { bg: '#f3e8ff', src: '#6b21a8', tgt: '#9333ea', box_bg: '#ede3fb' },
    backgroundColor: 'rgba(243,232,255,0.40)',
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(237,227,251,0.93)', bgStyle: 'light',
      textColor: '#6b21a8', translationColor: '#9333ea',
      borderRadius: 14,
    },
    wordbox: {
      bgColor: 'rgba(243,232,255,0.95)',
      wordColor: '#6b21a8', phoneticColor: '#9333ea', translationColor: '#1f2937',
      accentColor: '#7c3aed', headerColor: '#9333ea',
      borderRadius: 14,
    },
    exprbox: {
      bgColor: 'rgba(243,232,255,0.95)',
      expressionColor: '#7c3aed', translationColor: '#1f2937',
      accentColor: '#7c3aed', headerColor: '#6b21a8',
      borderRadius: 14,
    },
    effects: {
      textShadow: '0 0 6px rgba(107,33,168,0.15)',
      textHighlightColor: 'rgba(147,51,234,0.12)',
    },
  },

  nordic_frost: {
    name: '北欧霜雪',
    desc: '浅蓝灰白底，深海军蓝文字，斯堪的纳维亚极简清朗',
    preview_colors: { bg: '#f0f4f8', src: '#1e3a5f', tgt: '#2563eb', box_bg: '#e2eaf4' },
    backgroundColor: null,
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(226,234,244,0.93)', bgStyle: 'light',
      textColor: '#1e3a5f', translationColor: '#2563eb',
      borderRadius: 6,
    },
    wordbox: {
      bgColor: 'rgba(240,244,248,0.96)',
      wordColor: '#1e3a5f', phoneticColor: '#2563eb', translationColor: '#1e40af',
      accentColor: '#3b82f6', headerColor: '#2563eb',
      borderRadius: 6,
    },
    exprbox: {
      bgColor: 'rgba(240,244,248,0.96)',
      expressionColor: '#1e3a5f', translationColor: '#1e40af',
      accentColor: '#3b82f6', headerColor: '#1e3a5f',
      borderRadius: 6,
    },
  },

  candy_pop: {
    name: '糖果泡泡',
    desc: '亮粉荧蓝搭暗底，活力四射的少女电竞风',
    preview_colors: { bg: '#1e1030', src: '#ff6bcc', tgt: '#36d1dc', box_bg: '#2a1842' },
    backgroundColor: 'rgba(30,16,48,0.45)',
    defaultAnimation: 'pop',
    subtitle: {
      bgColor: 'rgba(42,24,66,0.90)', bgStyle: 'dark',
      textColor: '#ff6bcc', translationColor: '#36d1dc',
      borderRadius: 20,
    },
    wordbox: {
      bgColor: 'rgba(30,16,48,0.93)',
      wordColor: '#ff6bcc', phoneticColor: '#36d1dc', translationColor: '#fce4ec',
      accentColor: '#ff6bcc', headerColor: '#36d1dc',
      borderRadius: 20,
    },
    exprbox: {
      bgColor: 'rgba(30,16,48,0.93)',
      expressionColor: '#36d1dc', translationColor: '#fce4ec',
      accentColor: '#36d1dc', headerColor: '#ff6bcc',
      borderRadius: 20,
    },
    effects: {
      textShadow: '0 0 14px rgba(255,107,204,0.5), 0 0 14px rgba(54,209,220,0.3)',
      textHighlightColor: 'rgba(255,107,204,0.15)',
      textGlow: 'drop-shadow(0 0 6px rgba(255,107,204,0.5))',
    },
  },

  desert_sand: {
    name: '沙漠象牙',
    desc: '象牙米色底，赭褐文字，温暖大地质感的浅色学习空间',
    preview_colors: { bg: '#fdf9f0', src: '#92400e', tgt: '#b45309', box_bg: '#fef3c7' },
    backgroundColor: null,
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(254,243,199,0.93)', bgStyle: 'light',
      textColor: '#92400e', translationColor: '#b45309',
      borderRadius: 8,
    },
    wordbox: {
      bgColor: 'rgba(253,249,240,0.96)',
      wordColor: '#92400e', phoneticColor: '#b45309', translationColor: '#78350f',
      accentColor: '#d97706', headerColor: '#b45309',
      borderRadius: 8,
    },
    exprbox: {
      bgColor: 'rgba(253,249,240,0.96)',
      expressionColor: '#92400e', translationColor: '#78350f',
      accentColor: '#d97706', headerColor: '#92400e',
      borderRadius: 8,
    },
  },

  electric_indigo: {
    name: '靛紫晴空',
    desc: '淡紫白底，深靛蓝文字，现代简约的浅色科技感',
    preview_colors: { bg: '#f5f3ff', src: '#4c1d95', tgt: '#7c3aed', box_bg: '#ede9fe' },
    backgroundColor: null,
    defaultAnimation: 'slide_left',
    subtitle: {
      bgColor: 'rgba(237,233,254,0.93)', bgStyle: 'light',
      textColor: '#4c1d95', translationColor: '#7c3aed',
      borderRadius: 6,
    },
    wordbox: {
      bgColor: 'rgba(245,243,255,0.96)',
      wordColor: '#4c1d95', phoneticColor: '#7c3aed', translationColor: '#3730a3',
      accentColor: '#8b5cf6', headerColor: '#7c3aed',
      borderRadius: 6,
    },
    exprbox: {
      bgColor: 'rgba(245,243,255,0.96)',
      expressionColor: '#4c1d95', translationColor: '#3730a3',
      accentColor: '#8b5cf6', headerColor: '#4c1d95',
      borderRadius: 6,
    },
  },

  rose_gold: {
    name: '玫瑰胭脂',
    desc: '浅玫粉底，深玫红文字，精致温柔的浅色优雅学习',
    preview_colors: { bg: '#fef7f7', src: '#9f1239', tgt: '#be185d', box_bg: '#fde8ef' },
    backgroundColor: null,
    defaultAnimation: 'fade',
    subtitle: {
      bgColor: 'rgba(253,232,239,0.93)', bgStyle: 'light',
      textColor: '#9f1239', translationColor: '#be185d',
      borderRadius: 10,
    },
    wordbox: {
      bgColor: 'rgba(254,247,247,0.96)',
      wordColor: '#9f1239', phoneticColor: '#be185d', translationColor: '#881337',
      accentColor: '#e11d48', headerColor: '#be185d',
      borderRadius: 10,
    },
    exprbox: {
      bgColor: 'rgba(254,247,247,0.96)',
      expressionColor: '#9f1239', translationColor: '#881337',
      accentColor: '#e11d48', headerColor: '#9f1239',
      borderRadius: 10,
    },
  },

  mint_fresh: {
    name: '薄荷清新',
    desc: '浅薄荷绿配翠绿点缀，清爽洁净的自然学习',
    preview_colors: { bg: '#f0fdf4', src: '#047857', tgt: '#10b981', box_bg: '#e6f9ed' },
    backgroundColor: 'rgba(240,253,244,0.40)',
    defaultAnimation: 'slide_up',
    subtitle: {
      bgColor: 'rgba(230,249,237,0.93)', bgStyle: 'light',
      textColor: '#047857', translationColor: '#10b981',
      borderRadius: 12,
    },
    wordbox: {
      bgColor: 'rgba(240,253,244,0.95)',
      wordColor: '#047857', phoneticColor: '#10b981', translationColor: '#1f2937',
      accentColor: '#059669', headerColor: '#10b981',
      borderRadius: 12,
    },
    exprbox: {
      bgColor: 'rgba(240,253,244,0.95)',
      expressionColor: '#059669', translationColor: '#1f2937',
      accentColor: '#059669', headerColor: '#047857',
      borderRadius: 12,
    },
    effects: {
      textShadow: '0 0 6px rgba(4,120,87,0.12)',
      textHighlightColor: 'rgba(16,185,129,0.12)',
    },
  },

  obsidian_ember: {
    name: '黑曜余烬',
    desc: '近黑底配深红琥珀，戏剧感十足的暗夜学习',
    preview_colors: { bg: '#1a1110', src: '#dc2626', tgt: '#f59e0b', box_bg: '#2d1a18' },
    backgroundColor: 'rgba(26,17,16,0.55)',
    defaultAnimation: 'pop',
    subtitle: {
      bgColor: 'rgba(45,26,24,0.92)', bgStyle: 'dark',
      textColor: '#dc2626', translationColor: '#f59e0b',
      borderRadius: 4,
    },
    wordbox: {
      bgColor: 'rgba(26,17,16,0.95)',
      wordColor: '#dc2626', phoneticColor: '#f59e0b', translationColor: '#fef3c7',
      accentColor: '#dc2626', headerColor: '#f59e0b',
      borderRadius: 4,
    },
    exprbox: {
      bgColor: 'rgba(26,17,16,0.95)',
      expressionColor: '#f59e0b', translationColor: '#fef3c7',
      accentColor: '#f59e0b', headerColor: '#dc2626',
      borderRadius: 4,
    },
    effects: {
      textShadow: '0 0 12px rgba(220,38,38,0.4), 0 0 12px rgba(245,158,11,0.3)',
      textHighlightColor: 'rgba(220,38,38,0.2)',
      textGlow: 'drop-shadow(0 0 8px rgba(220,38,38,0.5))',
    },
  },
}

/** Default style theme ID */
export const DEFAULT_STYLE_ID = 'neon_cyberpunk'

/**
 * Apply a style theme to timeline elements.
 * Updates each element's style properties based on the theme.
 *
 * @param {string} styleId - Theme key from STYLE_THEMES
 * @param {Array} elements - Timeline elements array (mutated in place)
 * @returns {string} defaultAnimation type for the theme
 */
export function applyThemeToElements(styleId, elements) {
  const theme = STYLE_THEMES[styleId]
  if (!theme) return 'fade'

  for (const el of elements) {
    const themeSection = theme[el.type]
    if (!themeSection) continue

    // Merge theme styles into element style (preserving fontFamily and fontScale)
    const keepProps = { fontFamily: el.style.fontFamily, fontScale: el.style.fontScale }
    Object.assign(el.style, themeSection, keepProps)

    // Set default animation from theme if element currently has 'fade'
    if (el.animation && el.animation.enter) {
      el.animation.enter.type = theme.defaultAnimation
    }
  }

  return theme.defaultAnimation
}

/**
 * Get all theme IDs and their display info for the style gallery
 */
export function getThemeList() {
  return Object.entries(STYLE_THEMES).map(([id, t]) => ({
    id,
    name: t.name,
    desc: t.desc,
    preview_colors: t.preview_colors,
    backgroundColor: t.backgroundColor,
    defaultAnimation: t.defaultAnimation,
  }))
}
