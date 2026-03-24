<template>
  <div class="create-page page-inner">
    <div class="page-header">
      <h1>生成学习视频</h1>
      <p>上传视频，配置布局与样式，AI 自动生成逐句精听视频</p>
    </div>

    <div v-if="!isLoggedIn" class="empty-state">
      <div style="font-size:64px">🔒</div>
      <p style="font-size:18px;font-weight:700">请先登录</p>
      <button class="btn-primary" @click="openAuth()">登录 / 注册</button>
    </div>

    <div v-else>
      <!-- Preset bar -->
      <div class="preset-bar" v-if="presets.length>0||showPresetSave">
        <template v-if="!showPresetSave">
          <select class="input" v-model="selectedPresetId" style="flex:1;max-width:240px;margin-bottom:0;font-size:13px">
            <option value="">— 选择预设 —</option>
            <option v-for="p in presets" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <button class="btn-ghost" style="padding:7px 12px;font-size:12px" @click="applyPreset">加载</button>
          <button class="btn-ghost" style="padding:7px 10px;font-size:12px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="deletePreset">删除</button>
        </template>
        <template v-else>
          <input class="input" v-model="presetName" placeholder="预设名称..." style="flex:1;max-width:240px;margin-bottom:0;font-size:13px" @keyup.enter="savePreset">
          <button class="btn-primary" style="padding:7px 14px;font-size:12px" @click="savePreset">💾 保存</button>
          <button class="btn-ghost" style="padding:7px 10px;font-size:12px" @click="showPresetSave=false">取消</button>
        </template>
      </div>

      <div v-if="!jobRunning || jobDone">
        <!-- ── SECTION 1: Basic Config ── -->
        <div class="section-label">基础配置</div>
        <div class="config-grid">
          <!-- Upload -->
          <div class="card config-card">
            <div class="card-title">📁 上传视频</div>
            <div :class="['upload-zone',{over:dragOver}]"
                 @click="$refs.fileInput.click()"
                 @dragover.prevent="dragOver=true"
                 @dragleave="dragOver=false"
                 @drop.prevent="onDrop">
              <input ref="fileInput" type="file" accept="video/*" style="display:none" @change="onFileChange">
            <div v-if="!selectedFile" style="text-align:center">
                <div style="font-size:44px;margin-bottom:10px">📹</div>
                <div style="font-weight:600;margin-bottom:4px">点击或拖拽视频文件</div>
                <div style="font-size:12px;color:var(--text3)">MP4、MOV、AVI 等格式</div>
              </div>
              <div v-else style="width:100%">
                <video v-if="videoPreviewUrl" :src="videoPreviewUrl" controls muted playsinline
                  style="width:100%;border-radius:8px;max-height:180px;object-fit:contain;background:#000;display:block;margin-bottom:8px"
                  @click.stop></video>
                <div style="display:flex;align-items:center;gap:8px;padding:0 4px">
                  <div style="font-size:22px">✅</div>
                  <div style="flex:1;min-width:0">
                    <div style="font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ selectedFile.name }}</div>
                    <div style="font-size:11px;color:var(--text3)">{{ fmtSize(selectedFile.size) }}</div>
                  </div>
                  <button style="font-size:12px;color:var(--err);background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:6px;padding:4px 8px;cursor:pointer"
                    @click.stop="clearFile">✕ 移除</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Language -->
          <div class="card config-card">
            <div class="card-title">🌐 语言 & 分辨率</div>
            <label class="label">源语言（视频语言）</label>
            <select class="input" v-model="srcLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">目标语言（你的母语）</label>
            <select class="input" v-model="tgtLang" style="margin-bottom:12px">
              <option v-for="l in langs" :key="l.code" :value="l.code">{{ l.flag }} {{ l.native_name }}</option>
            </select>
            <label class="label">视频分辨率</label>
            <select class="input" v-model="resolution">
              <option value="1080p">1080p（推荐，更清晰）</option>
              <option value="720p">720p（更快，省空间）</option>
            </select>
          </div>

          <!-- Words -->
          <div class="card config-card">
            <div class="card-title">📚 词汇 & 表达</div>
            <label class="label">关键词：{{ numWords===0?'不限制':numWords+' 个/句' }}</label>
            <input type="range" class="slider" v-model.number="numWords" min="0" max="6" style="margin-bottom:20px">
            <label class="label">实用表达：{{ numExprs===0?'不限制':numExprs+' 个/句' }}</label>
            <input type="range" class="slider" v-model.number="numExprs" min="0" max="3">
          </div>
        </div>

        <!-- ── SECTION 2: Canvas Layout Editor ── -->
        <div class="section-label">布局编辑器
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">从上方拖拽框类型到画布，或点击框选中后调整属性</span>
        </div>
        <div class="card canvas-card">
          <div class="canvas-editor-wrap">

            <!-- Left: Parts list -->
            <div class="parts-sidebar">
              <div class="sidebar-hdr">Part 列表</div>
              <div v-for="(p,i) in parts" :key="p.id"
                   :class="['part-chip',{active:currentPartIdx===i}]"
                   @click="currentPartIdx=i;selectedBoxKey=null">
                <div style="display:flex;align-items:flex-start;justify-content:space-between">
                  <div class="part-chip-title">Part {{ i+1 }}
                    <span style="font-size:10px;color:var(--text3);font-weight:400">
                      {{ p.boxes.join(', ')||'空' }}
                    </span>
                  </div>
                  <div style="display:flex;gap:2px;flex-shrink:0">
                    <button class="part-action-btn" @click.stop="copyPart(i)" title="复制此 Part">⿻</button>
                    <button v-if="parts.length>1" class="del-part" @click.stop="removePart(i)" title="删除">✕</button>
                  </div>
                </div>
                <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;align-items:center">
                  <label style="font-size:11px;color:var(--text2);display:flex;align-items:center;gap:3px;cursor:pointer">
                    重复
                    <input type="number" class="input" v-model.number="p.repeat" min="1" max="5"
                           style="width:40px;padding:3px 6px;font-size:11px;margin-bottom:0;text-align:center"
                           @click.stop>
                  </label>
                </div>
                <div style="margin-top:6px" @click.stop>
                  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
                    <span style="font-size:11px;color:var(--text2)">速度</span>
                    <span style="font-size:11px;font-weight:700;color:var(--accent)">{{ Number(p.speed||1).toFixed(2) }}×</span>
                  </div>
                  <input type="range" v-model.number="p.speed" min="0.25" max="2.0" step="0.05"
                         style="width:100%;accent-color:var(--accent);cursor:pointer" @click.stop>
                  <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--text3)">
                    <span>0.25×</span><span>1×</span><span>2×</span>
                  </div>
                </div>
                <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap">
                  <label v-for="bt in BOX_DEFS" :key="bt.key"
                    style="font-size:11px;display:flex;align-items:center;gap:3px;cursor:pointer"
                    :style="{color: p.boxes.includes(bt.key)?bt.color:'var(--text3)'}"
                    @click.stop>
                    <input type="checkbox"
                           :checked="p.boxes.includes(bt.key)"
                           @change="togglePartBox(p,bt.key)"
                           :style="`accent-color:${bt.color}`">
                    {{ bt.label }}
                  </label>
                </div>
              </div>
              <button class="add-part" @click="addPart" :disabled="parts.length>=4">
                + 添加 Part
              </button>
            </div>

            <!-- Center: Canvas -->
            <div class="canvas-center">
              <div class="canvas-toolbar">
                <div style="font-size:11px;color:var(--text3);margin-right:8px">拖拽到画布：</div>
                <div v-for="bt in BOX_DEFS" :key="bt.key"
                     class="drag-chip"
                     :style="{background:bt.bgChip,border:`1.5px solid ${bt.color}`,color:bt.color}"
                     draggable="true"
                     @dragstart="dragBoxKey=$event.dataTransfer.setData('boxKey',bt.key)||bt.key">
                  {{ bt.icon }} {{ bt.label }}
                </div>
                <div style="margin-left:auto;display:flex;align-items:center;gap:6px">
                  <button class="zoom-btn" @click="canvasZoom=Math.max(0.4,canvasZoom-.1)">−</button>
                  <span style="font-size:11px;color:var(--text3);min-width:36px;text-align:center">{{ Math.round(canvasZoom*100) }}%</span>
                  <button class="zoom-btn" @click="canvasZoom=Math.min(2,canvasZoom+.1)">+</button>
                  <button class="zoom-btn" @click="canvasZoom=1" title="重置缩放">⟳</button>
                </div>
              </div>

              <!-- Canvas frame -->
              <div class="canvas-outer">
                <div class="canvas-scroll-area"
                     @dragover.prevent
                     @drop="onCanvasDrop"
                     @mousedown="onCanvasBg"
                     style="user-select:none">
                  <div ref="canvasEl" class="canvas-frame"
                       :style="{transform:`scale(${canvasZoom})`,transformOrigin:'top left',
                                width:'100%',aspectRatio:'16/9',position:'relative',
                                background:'#080818',borderRadius:'8px',
                                border: selectedBoxKey?'1.5px solid rgba(167,139,250,.3)':'1.5px solid rgba(255,255,255,.06)',
                                overflow:'hidden',cursor:'crosshair'}">
                    <!-- Video bg hint -->
                    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0">
                      <span style="color:#1e1e3a;font-size:clamp(12px,2vw,18px);font-weight:700;letter-spacing:4px">16 : 9</span>
                    </div>
                    <!-- Grid lines -->
                    <div style="position:absolute;inset:0;pointer-events:none;z-index:0;
                                background-image:linear-gradient(rgba(167,139,250,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(167,139,250,.04) 1px,transparent 1px);
                                background-size:10% 10%"></div>

                    <!-- Placed boxes -->
                    <div v-for="bk in currentPart.boxes" :key="bk"
                         :class="['cv-box', `cv-box-${bk}`, {selected: selectedBoxKey===bk}]"
                         :style="cvBoxStyle(bk)"
                         @mousedown.stop="startDrag($event, bk)">
                      <!-- Preview image or CSS-based fallback -->
                      <img v-if="previews[bk]" :src="previews[bk]"
                           style="width:100%;height:100%;object-fit:fill;border-radius:3px;display:block;pointer-events:none">
                      <div v-else class="cv-box-preview" :style="{background: BOX_MAP[bk]?.previewBg||'rgba(0,0,0,.6)', padding:'6px 8px', height:'100%', boxSizing:'border-box', overflow:'hidden'}">
                        <template v-if="bk==='subtitle'">
                          <div :style="{color:style.subtitle_text_color, fontSize:(11*boxLayouts['subtitle'].font_scale).toFixed(1)+'px', fontWeight:700, lineHeight:1.3, fontFamily: FONTS.find(f=>f.val===style.font_family)?.css||'system-ui'}">{{ PREVIEW_DATA[srcLang]?.sentence || 'Text' }}</div>
                          <div :style="{color:'#94a3b8', fontSize:(9*boxLayouts['subtitle'].font_scale).toFixed(1)+'px', marginTop:'3px'}">{{ PREVIEW_DATA[srcLang]?.translations?.[tgtLang] || 'Translation' }}</div>
                        </template>
                        <template v-else-if="bk==='wordbox'">
                          <div v-for="w in (PREVIEW_DATA[srcLang]?.words||[]).slice(0, numWords)" :key="w.word" style="margin-bottom:5px;line-height:1.3">
                            <span :style="{color:style.wordbox_word_color, fontSize:(11*boxLayouts['wordbox'].font_scale).toFixed(1)+'px', fontWeight:700, fontFamily: FONTS.find(f=>f.val===style.font_family)?.css||'system-ui'}">{{ w.word }}</span>
                            <span :style="{color:style.wordbox_phonetic_color, fontSize:(8*boxLayouts['wordbox'].font_scale).toFixed(1)+'px', marginLeft:'5px'}">{{ w.phonetic }}</span>
                            <div :style="{color:style.wordbox_trans_color, fontSize:(9*boxLayouts['wordbox'].font_scale).toFixed(1)+'px', marginTop:'1px'}">{{ w.translation }}</div>
                          </div>
                        </template>
                        <template v-else-if="bk==='expressionbox'">
                          <div v-for="e in (PREVIEW_DATA[srcLang]?.expressions||[]).slice(0, numExprs)" :key="e.english" style="margin-bottom:5px;line-height:1.3">
                            <div :style="{color:style.exprbox_en_color, fontSize:(10*boxLayouts['expressionbox'].font_scale).toFixed(1)+'px', fontWeight:700, fontFamily: FONTS.find(f=>f.val===style.font_family)?.css||'system-ui'}">{{ e.english }}</div>
                            <div :style="{color:'#94a3b8', fontSize:(9*boxLayouts['expressionbox'].font_scale).toFixed(1)+'px', marginTop:'1px'}">{{ e.chinese }}</div>
                          </div>
                        </template>
                        <div v-else class="cv-box-label" :style="{color:BOX_MAP[bk]?.color||'#fff',height:'100%'}">
                          {{ BOX_MAP[bk]?.icon }} {{ BOX_MAP[bk]?.label }}
                        </div>
                      </div>
                      <!-- Resize handle -->
                      <div class="cv-resize" @mousedown.stop="startResize($event, bk)"></div>
                      <!-- Delete button -->
                      <button class="cv-delete" @click.stop="removeBoxFromCanvas(bk)">✕</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Right: Properties -->
            <div class="props-sidebar">
              <div class="sidebar-hdr">{{ selectedBoxKey ? BOX_MAP[selectedBoxKey]?.label+'框属性' : '框属性' }}</div>
              <div v-if="!selectedBoxKey" style="color:var(--text3);font-size:12px;text-align:center;padding:20px 0;line-height:1.7">
                点击画布中的框<br>以编辑位置 / 大小 / 样式
              </div>
              <div v-else class="props-form">
                <div class="prop-row2">
                  <div><label class="label">X %</label><input type="number" class="input input-sm" v-model.number="boxLayouts[selectedBoxKey].x" min="0" max="99" step="0.5" @input="schedulePreview(selectedBoxKey)"></div>
                  <div><label class="label">Y %</label><input type="number" class="input input-sm" v-model.number="boxLayouts[selectedBoxKey].y" min="0" max="99" step="0.5" @input="schedulePreview(selectedBoxKey)"></div>
                  <div><label class="label">宽 %</label><input type="number" class="input input-sm" v-model.number="boxLayouts[selectedBoxKey].w" min="5" max="100" step="0.5" @input="schedulePreview(selectedBoxKey)"></div>
                  <div><label class="label">高 %</label><input type="number" class="input input-sm" v-model.number="boxLayouts[selectedBoxKey].h" min="3" max="100" step="0.5" @input="schedulePreview(selectedBoxKey)"></div>
                </div>
                <label class="label" style="margin-top:8px">字号倍率：{{ boxLayouts[selectedBoxKey].font_scale.toFixed(1) }}x</label>
                <input type="range" class="slider" v-model.number="boxLayouts[selectedBoxKey].font_scale" min="0.5" max="2.5" step="0.1" style="margin-bottom:10px" @input="schedulePreview(selectedBoxKey)">

                <!-- Box-specific colors -->
                <div style="font-size:11px;font-weight:700;color:var(--text3);margin:8px 0 6px;text-transform:uppercase;letter-spacing:.5px">颜色</div>
                <template v-if="selectedBoxKey==='subtitle'">
                  <ColorRow label="背景色" v-model="style.subtitle_bg_color" @change="schedulePreview('subtitle')"/>
                  <ColorRow label="文字色" v-model="style.subtitle_text_color" @change="schedulePreview('subtitle')"/>
                  <div style="margin-bottom:8px">
                    <label class="label">背景风格</label>
                    <select class="input input-sm" v-model="style.subtitle_bg_style" @change="schedulePreview('subtitle')">
                      <option value="light">浅色</option>
                      <option value="dark">深色</option>
                      <option value="gradient">渐变</option>
                      <option value="none">无背景</option>
                    </select>
                  </div>
                </template>
                <template v-else-if="selectedBoxKey==='wordbox'">
                  <ColorRow label="背景色" v-model="style.wordbox_bg" @change="schedulePreview('wordbox')"/>
                  <ColorRow label="单词色" v-model="style.wordbox_word_color" @change="schedulePreview('wordbox')"/>
                  <ColorRow label="音标色" v-model="style.wordbox_phonetic_color" @change="schedulePreview('wordbox')"/>
                  <ColorRow label="释义色" v-model="style.wordbox_trans_color" @change="schedulePreview('wordbox')"/>
                </template>
                <template v-else-if="selectedBoxKey==='expressionbox'">
                  <ColorRow label="背景色" v-model="style.exprbox_bg" @change="schedulePreview('expressionbox')"/>
                  <ColorRow label="表达色" v-model="style.exprbox_en_color" @change="schedulePreview('expressionbox')"/>
                </template>

                <button style="width:100%;margin-top:10px;padding:7px;border-radius:6px;background:transparent;border:1px solid rgba(248,113,113,.3);color:var(--err);font-size:12px;cursor:pointer;transition:all .15s"
                        @click="removeBoxFromCanvas(selectedBoxKey)"
                        onmouseover="this.style.background='rgba(248,113,113,.1)'" onmouseout="this.style.background='transparent'">
                  🗑️ 从画布移除此框
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── SECTION 3: Style Theme ── -->
        <div class="section-label">字幕样式主题
          <span style="font-size:11px;color:var(--text3);font-weight:400;margin-left:8px">选择视频字幕的视觉风格模版（10 款）</span>
        </div>
        <div class="card style-card">
          <!-- Style gallery -->
          <div style="margin-bottom:20px">
            <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:12px">视觉风格</div>
            <div v-if="Object.keys(styles).length===0" style="color:var(--text3);font-size:13px;padding:12px 0">
              加载样式中...
            </div>
            <div class="style-gallery">
              <div v-for="(s, sid) in styles" :key="sid"
                   :class="['style-card-item', {active: selectedStyleId===sid}]"
                   @click="applyStyleTheme(sid, s)"
                   :title="s.desc">
                <div class="style-swatch-bg" :style="{background: s.preview_colors?.bg||'#111'}">
                  <span class="style-swatch-src" :style="{color: s.preview_colors?.src||'#fff'}">Aa</span>
                  <span class="style-swatch-tgt" :style="{color: s.preview_colors?.tgt||'#aaa'}">译</span>
                  <div class="style-swatch-box" :style="{background: s.preview_colors?.box_bg||'#222', borderRadius:'3px', marginTop:'4px', padding:'2px 5px'}">
                    <span :style="{color: s.preview_colors?.src||'#fff', fontSize:'8px', fontWeight:600}">KEY</span>
                  </div>
                </div>
                <div class="style-card-name">{{ s.name }}</div>
                <div v-if="selectedStyleId===sid" class="style-check">✓</div>
              </div>
            </div>
          </div>

          <!-- Animation picker -->
          <div style="margin-bottom:20px">
            <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:8px">入场动画</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button v-for="[val, label, icon] in [['fade','淡入淡出','✨'],['slide_up','向上滑入','↑'],['pop','弹出放大','⚡']]"
                      :key="val"
                      :class="['anim-btn', {active: selectedAnimation===val}]"
                      @click="selectedAnimation=val">
                {{ icon }} {{ label }}
              </button>
            </div>
          </div>

          <!-- Font selection -->
          <div>
            <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:10px">字体选择</div>
            <div class="font-grid">
              <div v-for="f in FONTS" :key="f.val"
                   :class="['font-chip', {active: style.font_family===f.val}]"
                   :style="{fontFamily: f.css||'inherit'}"
                   @click="style.font_family=f.val; ['subtitle','wordbox','expressionbox'].forEach(k => schedulePreview(k))">
                <div style="font-size:15px;margin-bottom:2px">{{ f.sample }}</div>
                <div style="font-size:10px;color:var(--text3)">{{ f.label }}</div>
              </div>
            </div>
            <!-- Font preview area -->
            <div v-if="fontPreviewImg" style="margin-top:12px;text-align:center">
              <img :src="fontPreviewImg" style="max-width:100%;border-radius:6px;border:1px solid var(--border)">
            </div>
          </div>
        </div>

        <!-- ── SUBMIT ── -->
        <div class="submit-row">
          <button class="btn-primary" style="font-size:15px;padding:14px 40px" :disabled="submitting" @click="submit">
            {{ submitting?'提交中...':'🚀 开始生成学习视频' }}
          </button>
          <button class="btn-ghost" style="padding:13px 18px;font-size:13px" @click="showPresetSave=true;loadPresets()">
            💾 保存为预设
          </button>
        </div>
      </div>

      <!-- Naming Dialog -->
      <Teleport to="body">
        <div v-if="showNameDialog" class="modal-overlay" @click.self="onNameCancel" style="z-index:300">
          <div class="modal-box" style="max-width:420px">
            <button class="modal-close" @click="onNameCancel">✕</button>
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;color:var(--text)">为视频命名</div>
            <div style="font-size:13px;color:var(--text3);margin-bottom:20px">给这个学习视频起个名字，便于之后查找。留空时 AI 将自动生成名称。</div>
            <label class="label">视频名称（选填）</label>
            <input class="input" v-model="videoName" placeholder="例如：TED演讲·科技改变未来" @keyup.enter="onNameConfirm" style="margin-bottom:20px">
            <div style="display:flex;gap:10px">
              <button class="btn-primary" style="flex:1;padding:12px" @click="onNameConfirm">确认开始生成 →</button>
              <button class="btn-ghost" style="padding:12px 20px" @click="onNameCancel">取消</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Progress -->
      <div v-if="jobRunning && !jobDone" class="card progress-card">
        <div class="card-title">⚡ 处理进度</div>
        <div class="step-bar">
          <template v-for="i in 5" :key="i">
            <div :class="['step-dot', i<currentStep?'done':i===currentStep?'active':'']">{{ i }}</div>
            <div v-if="i<5" :class="['step-ln', i<currentStep?'done':'']"></div>
          </template>
        </div>
        <div class="cur-step"><span class="pulse-dot"></span><span>{{ stepName }}</span></div>
        <div v-if="currentStep>=5" style="margin-top:14px">
          <PBar label="片段渲染" :pct="clipsPct" color="linear-gradient(90deg,var(--accent),var(--accent2))"/>
          <PBar label="视频写入" :pct="writePct" color="linear-gradient(90deg,var(--accent3),var(--accent4))" style="margin-top:10px"/>
        </div>
        <div class="log-box" ref="logBox">
          <div v-for="(l,i) in logs" :key="i" :class="['log-line',logClass(l)]">{{ l }}</div>
        </div>
        <div style="margin-top:14px">
          <button class="btn-ghost" style="padding:8px 18px;font-size:13px;color:var(--err);border-color:rgba(248,113,113,.3)" @click="cancelJob">取消任务</button>
        </div>
      </div>

      <!-- Done -->
      <div v-if="jobDone" class="card" style="padding:36px;text-align:center;margin-top:20px">
        <div style="font-size:52px;margin-bottom:12px">🎉</div>
        <div style="font-size:18px;font-weight:700;margin-bottom:8px">视频生成完成！</div>
        <button class="btn-primary" @click="$router.push('/results')">查看学习结果 →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { apiFetch } from '../composables/useApi.js'

const { isLoggedIn } = useAuth()
const openAuth = inject('openAuth')
const toast    = inject('toast')

// ── Inline sub-components ──
const ColorRow = {
  props: ['label','modelValue'],
  emits: ['update:modelValue','change'],
  template: `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <span style="font-size:12px;color:var(--text2)">{{ label }}</span>
    <div style="display:flex;align-items:center;gap:6px">
      <input type="color" :value="modelValue" @input="$emit('update:modelValue',$event.target.value);$emit('change')"
             style="width:32px;height:28px;border-radius:4px;border:none;cursor:pointer;background:transparent">
      <span style="font-size:11px;color:var(--text3);font-variant-numeric:tabular-nums">{{ modelValue }}</span>
    </div>
  </div>`
}
const PBar = {
  props: ['label','pct','color'],
  template: `<div>
    <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text2);margin-bottom:6px;font-weight:600">
      <span>{{ label }}</span><span>{{ pct }}%</span>
    </div>
    <div style="height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden">
      <div :style="{width:pct+'%',height:'100%',borderRadius:'3px',background:color,transition:'width .5s',boxShadow:'0 0 8px rgba(167,139,250,.4)'}"></div>
    </div>
  </div>`
}

// ── Constants ──
const BOX_DEFS = [
  { key:'subtitle',      label:'字幕', icon:'📝', color:'#34d399', bgChip:'rgba(52,211,153,.1)',   previewBg:'rgba(0,0,0,.65)'  },
  { key:'wordbox',       label:'单词', icon:'📚', color:'#a78bfa', bgChip:'rgba(167,139,250,.1)', previewBg:'rgba(20,10,50,.8)' },
  { key:'expressionbox', label:'表达', icon:'💬', color:'#f472b6', bgChip:'rgba(244,114,182,.1)', previewBg:'rgba(30,5,25,.8)'  },
]
const BOX_MAP = Object.fromEntries(BOX_DEFS.map(b=>[b.key,b]))

const FONTS = [
  { val:'system',       label:'系统默认',   css:'system-ui',           sample:'Aa 文字' },
  { val:'noto-sans',    label:'Noto Sans',  css:"'Noto Sans SC'",       sample:'Aa 文字' },
  { val:'source-han',   label:'思源黑体',   css:"'Source Han Sans CN'", sample:'Aa 文字' },
  { val:'yahei',        label:'微软雅黑',   css:"'Microsoft YaHei'",    sample:'Aa 文字' },
  { val:'noto-serif',   label:'Noto Serif SC', css:"'Noto Serif SC'",   sample:'Aa 文字' },
  { val:'xiaowei',      label:'小薇体',    css:"'ZCOOL XiaoWei'",      sample:'Aa 文字' },
  { val:'ma-shan',      label:'马善政楷书', css:"'Ma Shan Zheng'",      sample:'Aa 文字' },
  { val:'long-cang',    label:'龙藏体',    css:"'Long Cang'",          sample:'Aa 文字' },
  { val:'zhi-mang',     label:'志莽行书',  css:"'Zhi Mang Xing'",      sample:'Aa 文字' },
  { val:'qingke',       label:'清客黄油体', css:"'ZCOOL QingKe HuangYou'", sample:'Aa 文字' },
  { val:'noto-jp',      label:'Noto Sans JP', css:"'Noto Sans JP'",     sample:'あア文字' },
  { val:'noto-kr',      label:'Noto Sans KR', css:"'Noto Sans KR'",     sample:'가나文字' },
  { val:'dancing',      label:'Dancing Script', css:"'Dancing Script'",  sample:'Aa Text' },
  { val:'playfair',     label:'Playfair Display', css:"'Playfair Display'", sample:'Aa Text' },
  { val:'roboto',       label:'Roboto',    css:"'Roboto'",             sample:'Aa Text' },
  { val:'source-serif', label:'思源宋体',   css:"'Source Han Serif CN'", sample:'Aa 文字' },
]

const COLOR_PRESETS = [
  {
    name:'暗夜极光', swatches:['#0f0f1e','#a78bfa','#f472b6','#38bdf8'],
    style:{subtitle_bg_color:'#000000',subtitle_text_color:'#ffffff',subtitle_bg_style:'dark',
           wordbox_bg:'#1a1a2e',wordbox_word_color:'#a78bfa',wordbox_phonetic_color:'#94a3b8',wordbox_trans_color:'#f1f5f9',
           exprbox_bg:'#0f172a',exprbox_en_color:'#f472b6'}
  },
  {
    name:'学院白板', swatches:['#f8f9fa','#6366f1','#374151','#db2777'],
    style:{subtitle_bg_color:'#f8f9fa',subtitle_text_color:'#1f2937',subtitle_bg_style:'light',
           wordbox_bg:'#f1f5f9',wordbox_word_color:'#6366f1',wordbox_phonetic_color:'#6b7280',wordbox_trans_color:'#1f2937',
           exprbox_bg:'#fdf2f8',exprbox_en_color:'#db2777'}
  },
  {
    name:'霓虹未来', swatches:['#000000','#00ffff','#ff0080','#ffff00'],
    style:{subtitle_bg_color:'#000000',subtitle_text_color:'#00ffff',subtitle_bg_style:'dark',
           wordbox_bg:'#050510',wordbox_word_color:'#00ffff',wordbox_phonetic_color:'#888888',wordbox_trans_color:'#ffffff',
           exprbox_bg:'#050510',exprbox_en_color:'#ff0080'}
  },
  {
    name:'暖光温柔', swatches:['#2d1b0e','#f4a460','#d2b48c','#ff9562'],
    style:{subtitle_bg_color:'#2d1b0e',subtitle_text_color:'#fff9f0',subtitle_bg_style:'dark',
           wordbox_bg:'#3d2515',wordbox_word_color:'#f4a460',wordbox_phonetic_color:'#d2b48c',wordbox_trans_color:'#fff8dc',
           exprbox_bg:'#4a3728',exprbox_en_color:'#ff9562'}
  },
  {
    name:'海洋深邃', swatches:['#0a2040','#4db8ff','#80c4e9','#40dfb8'],
    style:{subtitle_bg_color:'#0a2040',subtitle_text_color:'#e2f0fb',subtitle_bg_style:'dark',
           wordbox_bg:'#0d2b4a',wordbox_word_color:'#4db8ff',wordbox_phonetic_color:'#80c4e9',wordbox_trans_color:'#e8f4fd',
           exprbox_bg:'#0a1a30',exprbox_en_color:'#40dfb8'}
  },
]

const PREVIEW_DATA = {
  en: {
    sentence: "The acquisition of language is a remarkable phenomenon that reveals the incredible cognitive capabilities of the human mind.",
    translations: {
      zh: "语言习得是一种非凡的现象，揭示了人类心智令人难以置信的认知能力。",
      ja: "言語習得は、人間の心の驚くべき認知能力を明らかにする注目すべき現象です。",
      ko: "언어 습득은 인간 마음의 놀라운 인지 능력을 드러내는 주목할 만한 현象입니다。",
      de: "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitiven Fähigkeiten des menschlichen Geistes offenbart.",
      fr: "L'acquisition du langage révèle les incroyables capacités cognitives de l'esprit humain.",
      es: "La adquisición del lenguaje revela las increíbles capacidades cognitivas de la mente humana.",
      ru: "Освоение языка — это замечательный феномен, который демонстрирует когнитивную адаптивность человеческого мозга.",
    },
    words: [
      { word: "acquisition", phonetic: "/ˌækwɪˈzɪʃən/", translation: "习得；获取", difficulty: 4 },
      { word: "remarkable", phonetic: "/rɪˈmɑːrkəbl/", translation: "非凡的；显著的", difficulty: 3 },
      { word: "phenomenon", phonetic: "/fɪˈnɒmɪnən/", translation: "现象；奇迹", difficulty: 4 },
      { word: "cognitive", phonetic: "/ˈkɒɡnɪtɪv/", translation: "认知的", difficulty: 3 },
      { word: "capability", phonetic: "/ˌkeɪpəˈbɪlɪti/", translation: "能力；才能", difficulty: 3 },
      { word: "incredible", phonetic: "/ɪnˈkredɪbl/", translation: "难以置信的", difficulty: 2 },
    ],
    expressions: [
      { english: "in the long run", chinese: "从长远来看", difficulty: 3 },
      { english: "on the other hand", chinese: "另一方面", difficulty: 2 },
      { english: "as a result of", chinese: "由于…的结果", difficulty: 2 },
    ],
  },
  zh: {
    sentence: "人类语言的习得是一种非凡的认知现象，展示了大脑令人难以置信的神经可塑性和学习能力。",
    translations: {
      en: "The acquisition of human language is an extraordinary cognitive phenomenon demonstrating the brain's incredible neuroplasticity.",
      ja: "人間の言語習得は脳の神経可塑性と学習能力を示す認知現象です。",
      ko: "인간 언어의 습득은 뇌의 신경 가소성과 학습 능력을 보여주는 인지 현상입니다.",
      de: "Der menschliche Spracherwerb ist ein außergewöhnliches kognitives Phänomen, das die unglaubliche Neuroplastizität des Gehirns zeigt.",
      fr: "L'acquisition du langage humain est un phénomène cognitif extraordinaire démontrant la neuroplasticité incroyable du cerveau.",
      es: "La adquisición del lenguaje humano es un fenómeno cognitivo extraordinario que demuestra la neuroplasticidad increíble del cerebro.",
      ru: "Освоение человеческого языка — это необычайный когнитивный феномен, демонстрирующий невероятную нейропластичность мозга.",
    },
    words: [
      { word: "认知", phonetic: "rèn zhī", translation: "cognition", difficulty: 3 },
      { word: "非凡", phonetic: "fēi fán", translation: "extraordinary", difficulty: 3 },
      { word: "可塑性", phonetic: "kě sù xìng", translation: "plasticity", difficulty: 4 },
      { word: "习得", phonetic: "xí dé", translation: "acquisition", difficulty: 3 },
      { word: "展示", phonetic: "zhǎn shì", translation: "demonstrate", difficulty: 2 },
      { word: "现象", phonetic: "xiàn xiàng", translation: "phenomenon", difficulty: 2 },
    ],
    expressions: [
      { english: "令人难以置信", chinese: "incredibly hard to believe", difficulty: 3 },
      { english: "展示了…能力", chinese: "demonstrates the ability", difficulty: 3 },
      { english: "一种…现象", chinese: "a kind of phenomenon", difficulty: 2 },
    ],
  },
  ja: {
    sentence: "言語習得は人間の認知能力の驚くべき側面であり、脳の信じられないほどの適応力と可塑性を示しています。",
    translations: {
      en: "Language acquisition is a remarkable aspect of human cognitive ability, demonstrating the brain's plasticity.",
      zh: "语言习得是人类认知能力的显著方面，展示了大脑的适应性和可塑性。",
      ko: "언어 습득은 인간 인지 능력의 놀라운 측면으로, 뇌의 적응력과 가소성을 보여줍니다.",
      de: "Der Spracherwerb ist ein bemerkenswerter Aspekt der menschlichen kognitiven Fähigkeit und zeigt die Plastizität des Gehirns.",
      fr: "L'acquisition du langage est un aspect remarquable de la capacité cognitive humaine, démontrant la plasticité du cerveau.",
      es: "La adquisición del lenguaje es un aspecto notable de la capacidad cognitiva humana, demostrando la plasticidad del cerebro.",
      ru: "Освоение языка — это замечательный аспект человеческой когнитивной способности, демонстрирующий пластичность мозга.",
    },
    words: [
      { word: "習得", phonetic: "しゅうとく", translation: "acquisition", difficulty: 3 },
      { word: "認知", phonetic: "にんち", translation: "cognition", difficulty: 3 },
      { word: "驚くべき", phonetic: "おどろくべき", translation: "remarkable", difficulty: 3 },
      { word: "適応力", phonetic: "てきおうりょく", translation: "adaptability", difficulty: 4 },
      { word: "可塑性", phonetic: "かそせい", translation: "plasticity", difficulty: 5 },
      { word: "側面", phonetic: "そくめん", translation: "aspect", difficulty: 2 },
    ],
    expressions: [
      { english: "〜を示している", chinese: "demonstrates ~", difficulty: 3 },
      { english: "驚くべき〜", chinese: "remarkable ~", difficulty: 2 },
      { english: "〜の側面", chinese: "aspect of ~", difficulty: 2 },
    ],
  },
  ko: {
    sentence: "언어 습득은 인간 인지 능력의 놀라운 측면으로, 뇌의 적응력과 가소성을 보여줍니다.",
    translations: {
      en: "Language acquisition is a remarkable aspect of human cognitive ability.",
      zh: "语言习得是人类认知能力的显著方面。",
      ja: "言語習得は人間の認知能力の驚くべき側面です。",
      de: "Der Spracherwerb ist ein bemerkenswerter Aspekt der menschlichen kognitiven Fähigkeit.",
      fr: "L'acquisition du langage est un aspect remarquable de la capacité cognitive humaine.",
      es: "La adquisición del lenguaje es un aspecto notable de la capacidad cognitiva humana.",
      ru: "Освоение языка — это замечательный аспект человеческой когнитивной способности.",
    },
    words: [
      { word: "습득", phonetic: "seub-deug", translation: "acquisition", difficulty: 3 },
      { word: "인지", phonetic: "in-ji", translation: "cognition", difficulty: 3 },
      { word: "놀라운", phonetic: "nol-la-un", translation: "remarkable", difficulty: 2 },
      { word: "적응력", phonetic: "jeog-eung-lyeog", translation: "adaptability", difficulty: 4 },
      { word: "가소성", phonetic: "ga-so-seong", translation: "plasticity", difficulty: 5 },
      { word: "측면", phonetic: "cheug-myeon", translation: "aspect", difficulty: 2 },
    ],
    expressions: [
      { english: "보여줍니다", chinese: "demonstrates", difficulty: 2 },
      { english: "놀라운 측면", chinese: "remarkable aspect", difficulty: 2 },
      { english: "믿기 어려운", chinese: "hard to believe", difficulty: 3 },
    ],
  },
  de: {
    sentence: "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitive Anpassungsfähigkeit und neuronale Plastizität des menschlichen Gehirns demonstriert.",
    translations: {
      en: "Language acquisition is a remarkable phenomenon demonstrating the cognitive adaptability of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
      ja: "言語習得は、人間の脳の認知的適応能力と神経可塑性を示す注目すべき現象です。",
      ko: "언어 습득은 인간 뇌의 인지적 적응성과 신경 가소성을 보여주는 주목할 만한 현상입니다.",
      fr: "L'acquisition du langage est un phénomène remarquable démontrant l'adaptabilité cognitive du cerveau humain.",
      es: "La adquisición del lenguaje es un fenómeno notable que demuestra la adaptabilidad cognitiva del cerebro humano.",
      ru: "Освоение языка — это замечательный феномен, демонстрирующий когнитивную адаптивность и нейропластичность человеческого мозга.",
    },
    words: [
      { word: "Spracherwerb", phonetic: "/ˈʃpraːxɛɐ̯ˌvɛrp/", translation: "language acquisition", difficulty: 3 },
      { word: "bemerkenswert", phonetic: "/bəˈmɛrkənsvɛrt/", translation: "remarkable", difficulty: 3 },
      { word: "Plastizität", phonetic: "/plastiˈtsɪtɛːt/", translation: "plasticity", difficulty: 5 },
      { word: "demonstriert", phonetic: "/demoːnˈstriːrt/", translation: "demonstrates", difficulty: 3 },
      { word: "kognitiv", phonetic: "/kɔɡniˈtiːf/", translation: "cognitive", difficulty: 4 },
      { word: "unglaublich", phonetic: "/ʊnˈɡlaʊ̯plɪç/", translation: "incredible", difficulty: 2 },
    ],
    expressions: [
      { english: "das...demonstriert", chinese: "which demonstrates", difficulty: 3 },
      { english: "ein...Phänomen", chinese: "a phenomenon", difficulty: 2 },
      { english: "des menschlichen", chinese: "of the human", difficulty: 2 },
    ],
  },
  fr: {
    sentence: "L'acquisition du langage est un phénomène remarquable qui démontre l'adaptabilité cognitive et la plasticité neuronale du cerveau humain.",
    translations: {
      en: "Language acquisition demonstrates the incredible cognitive adaptability and neural plasticity of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
      ja: "言語習得は、人間の脳の信じられないほどの認知的適応性と神経可塑性を示しています。",
      ko: "언어 습득은 인간 뇌의 믿기 어려운 인지적 적응성과 신경 가소성을 보여줍니다.",
      de: "Der Spracherwerb demonstriert die unglaubliche kognitive Anpassungsfähigkeit und neuronale Plastizität des menschlichen Gehirns.",
      es: "La adquisición del lenguaje demuestra la adaptabilidad cognitiva increíble y la plasticidad neuronal del cerebro humano.",
      ru: "Освоение языка демонстрирует невероятную когнитивную адаптивность и нейропластичность человеческого мозга.",
    },
    words: [
      { word: "acquisition", phonetic: "/akizisjɔ̃/", translation: "acquisition", difficulty: 3 },
      { word: "remarquable", phonetic: "/ʁəmaʁkabl/", translation: "remarkable", difficulty: 3 },
      { word: "plasticité", phonetic: "/plastisite/", translation: "plasticity", difficulty: 5 },
      { word: "adaptabilité", phonetic: "/adaptabilite/", translation: "adaptability", difficulty: 4 },
      { word: "démontre", phonetic: "/demɔ̃tʁ/", translation: "demonstrates", difficulty: 3 },
      { word: "incroyable", phonetic: "/ɛ̃kʁwajabl/", translation: "incredible", difficulty: 2 },
    ],
    expressions: [
      { english: "qui démontre", chinese: "which demonstrates", difficulty: 2 },
      { english: "un phénomène remarquable", chinese: "a remarkable phenomenon", difficulty: 3 },
      { english: "du cerveau humain", chinese: "of the human brain", difficulty: 2 },
    ],
  },
  es: {
    sentence: "La adquisición del lenguaje es un fenómeno notable que demuestra la adaptabilidad cognitiva y la plasticidad neuronal del cerebro humano.",
    translations: {
      en: "Language acquisition demonstrates the incredible cognitive adaptability and neural plasticity of the human brain.",
      zh: "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
      ja: "言語習得は、人間の脳の信じられないほどの認知的適応性と神経可塑性を示しています。",
      ko: "언어 습득은 인간 뇌의 믿기 어려운 인지적 적응성과 신경 가소성을 보여줍니다.",
      de: "Der Spracherwerb demonstriert die unglaubliche kognitive Anpassungsfähigkeit und neuronale Plastizität des menschlichen Gehirns.",
      fr: "L'acquisition du langage démontre l'adaptabilité cognitive incroyable et la plasticité neuronale du cerveau humain.",
      ru: "Освоение языка демонстрирует невероятную когнитивную адаптивность и нейропластичность человеческого мозга.",
    },
    words: [
      { word: "adquisición", phonetic: "/adkiˈsjon/", translation: "acquisition", difficulty: 3 },
      { word: "notable", phonetic: "/noˈtaβle/", translation: "remarkable", difficulty: 3 },
      { word: "plasticidad", phonetic: "/plastiθiˈðað/", translation: "plasticity", difficulty: 5 },
      { word: "adaptabilidad", phonetic: "/adaptaβiliˈðað/", translation: "adaptability", difficulty: 4 },
      { word: "demuestra", phonetic: "/deˈmwestra/", translation: "demonstrates", difficulty: 3 },
      { word: "increíble", phonetic: "/iŋkɾeˈiβle/", translation: "incredible", difficulty: 2 },
    ],
    expressions: [
      { english: "que demuestra", chinese: "which demonstrates", difficulty: 2 },
      { english: "un fenómeno notable", chinese: "a remarkable phenomenon", difficulty: 3 },
      { english: "del cerebro humano", chinese: "of the human brain", difficulty: 2 },
    ],
  },
  ru: {
    sentence: "Освоение языка — это замечательный феномен, который демонстрирует когнитивную адаптивность и нейропластичность человеческого мозга.",
    translations: {
      en: "Language acquisition is a remarkable phenomenon that demonstrates cognitive adaptability and neural plasticity of the human brain.",
      zh: "语言习得是一种非凡的现象，展示了人类大脑的认知适应性和神经可塑性。",
      ja: "言語習得は、人間の脳の認知的適応性と神経可塑性を示す注目すべき現象です。",
      ko: "언어 습득은 인간 뇌의 인지적 적응성과 신경 가소성을 보여주는 주목할 만한 현象입니다.",
      de: "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitive Anpassungsfähigkeit und neuronale Plastizität des menschlichen Gehirns zeigt.",
      fr: "L'acquisition du langage est un phénomène remarquable qui démontre l'adaptabilité cognitive et la plasticité neuronale du cerveau humain.",
      es: "La adquisición del lenguaje es un fenómeno notable que demuestra la adaptabilidad cognitiva y la plasticidad neuronal del cerebro humano.",
    },
    words: [
      { word: "освоение", phonetic: "/əsˈvoːɪnɪjə/", translation: "acquisition", difficulty: 3 },
      { word: "замечательный", phonetic: "/zəmɪˈtʃætəlnɪj/", translation: "remarkable", difficulty: 3 },
      { word: "феномен", phonetic: "/fɪˈnɔːmɪn/", translation: "phenomenon", difficulty: 4 },
      { word: "демонстрирует", phonetic: "/dɪˈmɒnstreɪts/", translation: "demonstrates", difficulty: 3 },
      { word: "адаптивность", phonetic: "/ədˈæptɪvnəs/", translation: "adaptability", difficulty: 4 },
      { word: "нейропластичность", phonetic: "/ˈnjʊroʊˈplæstɪsɪti/", translation: "neural plasticity", difficulty: 5 },
    ],
    expressions: [
      { english: "замечательный феномен", chinese: "remarkable phenomenon", difficulty: 3 },
      { english: "демонстрирует способность", chinese: "demonstrates ability", difficulty: 3 },
      { english: "человеческого мозга", chinese: "of the human brain", difficulty: 2 },
    ],
  },
}

// ── State ──
const fileInput   = ref(null)
const selectedFile= ref(null)
const videoPreviewUrl = ref('')
const dragOver    = ref(false)
const langs       = ref([])
const srcLang     = ref('en')
const tgtLang     = ref('zh')
const resolution  = ref('1080p')
const numWords    = ref(3)
const numExprs    = ref(2)

// Global box layouts (position/size for each box type)
const boxLayouts = reactive({
  subtitle:      { x:5, y:76, w:90, h:14, font_scale:1.0 },
  wordbox:       { x:5, y:48, w:44, h:32, font_scale:1.0 },
  expressionbox: { x:53,y:48, w:42, h:32, font_scale:1.0 },
})

// Style (colors, fonts)
const style = reactive({
  font_family:'system',
  subtitle_bg_color:'#000000',subtitle_text_color:'#ffffff',subtitle_bg_style:'dark',
  wordbox_bg:'#1a1a2e',wordbox_word_color:'#a78bfa',wordbox_phonetic_color:'#94a3b8',wordbox_trans_color:'#f1f5f9',
  exprbox_bg:'#0f172a',exprbox_en_color:'#f472b6',
})
const activeColorPreset = ref('暗夜极光')
const selectedStyleId  = ref('aurora_dark')
const selectedAnimation = ref('fade')
const styles = ref({})

// Parts
const parts = ref([
  { id:`p_${Date.now()}`, repeat:1, speed:1.0, boxes:['subtitle'] }
])
const currentPartIdx = ref(0)
const currentPart = computed(() => parts.value[currentPartIdx.value] || parts.value[0])

function addPart() {
  parts.value.push({ id:`p_${Date.now()}`, repeat:1, speed:1.0, boxes:[] })
}
function copyPart(i) {
  const src = parts.value[i]
  const copy = JSON.parse(JSON.stringify(src))
  copy.id = `p_${Date.now()}`
  parts.value.splice(i+1, 0, copy)
}
function removePart(i) {
  parts.value.splice(i,1)
  if (currentPartIdx.value >= parts.value.length) currentPartIdx.value = parts.value.length-1
}
function togglePartBox(p, key) {
  const i = p.boxes.indexOf(key)
  if (i===-1) p.boxes.push(key); else p.boxes.splice(i,1)
}

// Canvas
const canvasEl   = ref(null)
const canvasZoom = ref(1)
const selectedBoxKey = ref(null)
let dragState = null

function cvBoxStyle(bk) {
  const bl = boxLayouts[bk]
  return {
    position:'absolute',
    left:bl.x+'%', top:bl.y+'%',
    width:bl.w+'%', height:bl.h+'%',
    cursor:'move', zIndex: selectedBoxKey.value===bk?10:5,
    borderRadius:'4px',
    border: selectedBoxKey.value===bk
      ? `2px solid ${BOX_MAP[bk]?.color||'#fff'}`
      : `1.5px dashed ${BOX_MAP[bk]?.color||'#fff'}44`,
    boxShadow: selectedBoxKey.value===bk ? `0 0 0 3px ${BOX_MAP[bk]?.color||'#fff'}22` : 'none',
    background: previews.value[bk] ? 'transparent' : `${BOX_MAP[bk]?.color||'#888'}12`,
    overflow:'hidden',
  }
}

function getCanvasPct(clientX, clientY) {
  const rect = canvasEl.value.getBoundingClientRect()
  return {
    x: (clientX - rect.left) / rect.width  / canvasZoom.value * 100,
    y: (clientY - rect.top)  / rect.height / canvasZoom.value * 100,
  }
}

function startDrag(e, bk) {
  selectedBoxKey.value = bk
  const pct = getCanvasPct(e.clientX, e.clientY)
  const bl = boxLayouts[bk]
  dragState = { type:'move', bk, ox: pct.x-bl.x, oy: pct.y-bl.y }
  window.addEventListener('mousemove', onWinMove)
  window.addEventListener('mouseup',   onWinUp)
}

function startResize(e, bk) {
  e.stopPropagation()
  selectedBoxKey.value = bk
  const pct = getCanvasPct(e.clientX, e.clientY)
  const bl = boxLayouts[bk]
  dragState = { type:'resize', bk, ox: pct.x - (bl.x+bl.w), oy: pct.y - (bl.y+bl.h) }
  window.addEventListener('mousemove', onWinMove)
  window.addEventListener('mouseup',   onWinUp)
}

function onWinMove(e) {
  if (!dragState) return
  const pct = getCanvasPct(e.clientX, e.clientY)
  const bl  = boxLayouts[dragState.bk]
  if (dragState.type === 'move') {
    bl.x = Math.max(0, Math.min(100-bl.w, pct.x - dragState.ox))
    bl.y = Math.max(0, Math.min(100-bl.h, pct.y - dragState.oy))
  } else {
    bl.w = Math.max(5,  Math.min(100-bl.x, pct.x - dragState.ox - bl.x))
    bl.h = Math.max(3,  Math.min(100-bl.y, pct.y - dragState.oy - bl.y))
  }
  schedulePreview(dragState.bk)
}

function onWinUp() {
  dragState = null
  window.removeEventListener('mousemove', onWinMove)
  window.removeEventListener('mouseup',   onWinUp)
}

function onCanvasBg(e) {
  if (e.target === canvasEl.value) selectedBoxKey.value = null
}

function onCanvasDrop(e) {
  const bk = e.dataTransfer.getData('boxKey')
  if (!bk || !BOX_MAP[bk]) return
  if (!currentPart.value.boxes.includes(bk)) currentPart.value.boxes.push(bk)
  selectedBoxKey.value = bk
  // Position at drop point
  const pct = getCanvasPct(e.clientX, e.clientY)
  const bl  = boxLayouts[bk]
  bl.x = Math.max(0, Math.min(100-bl.w, pct.x - bl.w/2))
  bl.y = Math.max(0, Math.min(100-bl.h, pct.y - bl.h/2))
  schedulePreview(bk)
}

function removeBoxFromCanvas(bk) {
  currentPart.value.boxes = currentPart.value.boxes.filter(b=>b!==bk)
  if (selectedBoxKey.value === bk) selectedBoxKey.value = null
}

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onWinMove)
  window.removeEventListener('mouseup',   onWinUp)
})

// ── Previews ──
const previews      = ref({})
const fontPreviewImg= ref('')
const previewTimers = {}

function schedulePreview(bk) {
  if (!bk) return
  clearTimeout(previewTimers[bk])
  previewTimers[bk] = setTimeout(() => renderPreview(bk), 600)
}

async function renderPreview(bk) {
  if (!isLoggedIn.value || !bk) return
  const bl = boxLayouts[bk]
  const fd = new FormData()
  fd.append('box_type',      bk)
  fd.append('width_pct',     (bl.w/100).toFixed(3))
  fd.append('height_pct',    (bl.h/100).toFixed(3))
  fd.append('source_lang',   srcLang.value)
  fd.append('target_lang',   tgtLang.value)
  fd.append('resolution',    resolution.value)
  fd.append('num_words',     numWords.value)
  fd.append('num_expressions', numExprs.value)
  fd.append('style', JSON.stringify({
    ...style,
    [`${bk==='expressionbox'?'exprbox':bk}_font_size_scale`]: bl.font_scale,
  }))
  try {
    const r = await fetch('/api/render-box', {
      method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') },
      body: fd
    })
    const d = await r.json()
    if (d.image) {
      previews.value[bk] = d.image
      if (bk === currentPart.value.boxes[0]) fontPreviewImg.value = d.image
    }
  } catch {}
}

// ── Color presets (legacy – kept for preset compatibility) ──
function applyColorPreset(cp) {
  activeColorPreset.value = cp.name
  Object.assign(style, cp.style)
  for (const bk of ['subtitle','wordbox','expressionbox']) {
    schedulePreview(bk)
  }
}

// ── Style theme (new ASS-based) ──
function applyStyleTheme(sid, s) {
  selectedStyleId.value = sid
  selectedAnimation.value = s.animation || 'fade'
  activeColorPreset.value = s.name
  // Sync CSS preview colors to match the selected ASS style
  if (s.css) {
    Object.assign(style, {
      subtitle_bg_color:     s.preview_colors?.bg    || '#000000',
      subtitle_text_color:   s.css.subtitle_src_color || '#ffffff',
      subtitle_bg_style:     (s.preview_colors?.bg||'').startsWith('#f') ? 'light' : 'dark',
      wordbox_bg:            s.preview_colors?.box_bg || '#111111',
      wordbox_word_color:    s.css.word_color         || '#ffffff',
      wordbox_phonetic_color:s.css.phonetic_color     || '#888888',
      wordbox_trans_color:   s.css.trans_color        || '#cccccc',
      exprbox_bg:            s.preview_colors?.box_bg || '#111111',
      exprbox_en_color:      s.css.expr_color         || '#f43f5e',
    })
  }
  for (const bk of ['subtitle','wordbox','expressionbox']) schedulePreview(bk)
}

// ── Presets ──
const presets = ref([])
const selectedPresetId = ref('')
const showPresetSave   = ref(false)
const presetName       = ref('')

async function loadPresets() {
  if (!isLoggedIn.value) return
  try {
    const d = await apiFetch('/api/config/presets')
    presets.value = d.presets||[]
  } catch {}
}

async function savePreset() {
  if (!presetName.value.trim()) { toast('请输入预设名称','warn'); return }
  const cfg = { source_lang:srcLang.value, target_lang:tgtLang.value,
    resolution:resolution.value, num_words:numWords.value, num_exprs:numExprs.value,
    style:{ ...style }, boxLayouts:{ ...boxLayouts }, parts:JSON.parse(JSON.stringify(parts.value)),
    style_id: selectedStyleId.value, animation: selectedAnimation.value }
  const fd = new FormData()
  fd.append('name', presetName.value)
  fd.append('config_json', JSON.stringify(cfg))
  try {
    await fetch('/api/config/presets', { method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') }, body:fd })
    toast(`预设「${presetName.value}」已保存`, 'ok')
    presetName.value = ''; showPresetSave.value = false
    await loadPresets()
  } catch(e) { toast('保存失败','err') }
}

function applyPreset() {
  const id = parseInt(selectedPresetId.value)
  const p = presets.value.find(p=>p.id===id)
  if (!p) { toast('请先选择预设','warn'); return }
  try {
    const cfg = JSON.parse(p.config_json)
    if (cfg.source_lang)  srcLang.value = cfg.source_lang
    if (cfg.target_lang)  tgtLang.value = cfg.target_lang
    if (cfg.resolution)   resolution.value = cfg.resolution
    if (cfg.num_words)    numWords.value = cfg.num_words
    if (cfg.num_exprs)    numExprs.value = cfg.num_exprs
    if (cfg.style)        Object.assign(style, cfg.style)
    if (cfg.boxLayouts)   Object.keys(cfg.boxLayouts).forEach(k=>Object.assign(boxLayouts[k]||{},cfg.boxLayouts[k]))
    if (cfg.parts?.length) parts.value = cfg.parts.map(p => ({
      ...p, speed: p.speed ?? (p.slow ? 0.75 : 1.0)
    }))
    if (cfg.style_id)     selectedStyleId.value = cfg.style_id
    if (cfg.animation)    selectedAnimation.value = cfg.animation
    toast(`已加载「${p.name}」`,'ok')
    for (const bk of ['subtitle','wordbox','expressionbox']) schedulePreview(bk)
  } catch { toast('加载失败','err') }
}

async function deletePreset() {
  const id = parseInt(selectedPresetId.value)
  if (!id) { toast('请先选择预设','warn'); return }
  const p = presets.value.find(p=>p.id===id)
  if (!confirm(`确定删除「${p?.name}」？`)) return
  try {
    await fetch(`/api/config/presets/${id}`, { method:'DELETE',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') } })
    selectedPresetId.value = ''; toast('已删除','ok'); await loadPresets()
  } catch { toast('删除失败','err') }
}

// ── Submit & Progress ──
const jobRunning  = ref(false)
const jobDone     = ref(false)
const submitting  = ref(false)
const currentJobId= ref(null)
const currentStep = ref(0)
const stepName    = ref('准备中...')
const clipsPct    = ref(0)
const writePct    = ref(0)
const logs        = ref([])
const logBox      = ref(null)
const showNameDialog = ref(false)
const videoName   = ref('')
let ws = null

async function submit() {
  if (!selectedFile.value) { toast('请先选择视频文件','warn'); return }
  if (srcLang.value===tgtLang.value) { toast('源语言和目标语言不能相同','warn'); return }
  if (parts.value.length===0) { toast('请至少添加一个 Part','warn'); return }
  videoName.value = ''
  showNameDialog.value = true
}

function onNameCancel() {
  showNameDialog.value = false
}

async function onNameConfirm() {
  showNameDialog.value = false
  await doSubmit(videoName.value.trim())
}

async function doSubmit(name) {
  submitting.value = true
  const fd = new FormData()
  fd.append('video', selectedFile.value)
  fd.append('source_lang', srcLang.value)
  fd.append('target_lang', tgtLang.value)
  fd.append('resolution',  resolution.value)
  fd.append('num_words',   numWords.value)
  fd.append('num_expressions', numExprs.value)

  // Build layout
  const layoutObj = {}
  for (const [bk, bl] of Object.entries(boxLayouts)) {
    const pfx = bk==='expressionbox'?'exprbox':bk
    layoutObj[`${pfx}_x_pct`]          = bl.x
    layoutObj[`${pfx}_y_pct`]          = bl.y
    layoutObj[`${pfx}_width_pct`]      = bl.w
    layoutObj[`${pfx}_height_pct`]     = bl.h
    layoutObj[`${pfx}_font_size_scale`]= bl.font_scale
  }
  fd.append('layout', JSON.stringify(layoutObj))
  fd.append('style',  JSON.stringify({ ...style }))

  // Parts with box type lists + speed
  const partsForApi = parts.value.map(p => ({
    id: p.id, repeat: p.repeat, speed: Number(p.speed||1.0),
    slow: Number(p.speed||1.0) !== 1.0,
    boxes: p.boxes.map(bk => ({ type: bk, ...boxLayouts[bk] }))
  }))
  fd.append('parts_json', JSON.stringify(partsForApi))
  fd.append('style_id',  selectedStyleId.value || 'aurora_dark')
  fd.append('animation', selectedAnimation.value || 'fade')
  if (name) fd.append('name', name)

  try {
    const r = await fetch('/api/jobs', {
      method:'POST',
      headers:{ Authorization:'Bearer '+localStorage.getItem('ll_token') },
      body: fd
    })
    const d = await r.json()
    if (!r.ok) throw new Error(d.detail||'提交失败')
    // If name provided, PATCH it immediately
    if (name && d.job_id) {
      const nfd = new FormData(); nfd.append('name', name)
      fetch(`/api/jobs/${d.job_id}`, { method:'PATCH',
        headers:{Authorization:'Bearer '+localStorage.getItem('ll_token')}, body:nfd }).catch(()=>{})
    }
    currentJobId.value = d.job_id
    jobRunning.value = true; jobDone.value = false
    currentStep.value = 0; clipsPct.value = 0; writePct.value = 0
    logs.value = []; stepName.value = '等待处理...'
    toast('任务已提交 🚀','ok')
    connectWS(d.job_id)
  } catch(e) { toast(e.message,'err') }
  finally { submitting.value = false }
}

function connectWS(jobId) {
  if (ws) { try{ws.close()}catch{} }
  const proto = location.protocol==='https:'?'wss':'ws'
  ws = new WebSocket(`${proto}://${location.host}/api/ws/${jobId}`)
  ws.onmessage = async e => {
    const msg = JSON.parse(e.data)
    switch (msg.type) {
      case 'log':
        logs.value.push(msg.data)
        await nextTick()
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
        break
      case 'step':  currentStep.value=msg.data.step; stepName.value=msg.data.name; break
      case 'video_clips': clipsPct.value=msg.data.pct||0; break
      case 'video_write': writePct.value=msg.data.pct||0; break
      case 'done':  clipsPct.value=100; writePct.value=100; jobDone.value=true; toast('视频生成完成！🎉','ok'); break
      case 'error': toast('处理失败: '+msg.data,'err'); jobRunning.value=false; break
      case 'cancelled': toast('任务已取消','warn'); jobRunning.value=false; break
    }
  }
  ws.onerror = () => pollJob(jobId)
}

function pollJob(jobId) {
  const iv = setInterval(async () => {
    try {
      const d = await apiFetch('/api/jobs/'+jobId)
      if (d.step_name) stepName.value=d.step_name
      if (d.video_clips_pct) clipsPct.value=d.video_clips_pct
      if (d.video_write_pct) writePct.value=d.video_write_pct
      if (d.status==='done'){clearInterval(iv);clipsPct.value=100;writePct.value=100;jobDone.value=true}
      if (d.status==='error'||d.status==='cancelled'){clearInterval(iv);jobRunning.value=false}
    } catch {}
  }, 3000)
}

async function cancelJob() {
  if (!currentJobId.value||!confirm('确定取消？')) return
  await fetch(`/api/jobs/${currentJobId.value}`, {
    method:'DELETE', headers:{Authorization:'Bearer '+localStorage.getItem('ll_token')}
  }).catch(()=>{})
}

function logClass(l) {
  if (l.includes('❌')||l.toLowerCase().includes('error')) return 'err'
  if (l.includes('✓')||l.includes('完成')) return 'ok'
  return ''
}
function setFile(f) {
  if (!f) return
  selectedFile.value = f
  if (videoPreviewUrl.value) URL.revokeObjectURL(videoPreviewUrl.value)
  videoPreviewUrl.value = URL.createObjectURL(f)
}
function clearFile() {
  selectedFile.value = null
  if (videoPreviewUrl.value) { URL.revokeObjectURL(videoPreviewUrl.value); videoPreviewUrl.value = '' }
}
function onFileChange(e) { const f=e.target.files[0]; if(f) setFile(f) }
function onDrop(e) { dragOver.value=false; const f=e.dataTransfer.files[0]; if(f&&f.type.startsWith('video/')) setFile(f) }
function fmtSize(b) { return b>1e9?(b/1e9).toFixed(1)+' GB':b>1e6?(b/1e6).toFixed(1)+' MB':(b/1e3).toFixed(0)+' KB' }

onMounted(async () => {
  if (!isLoggedIn.value) return
  try {
    const d = await apiFetch('/api/languages')
    if (d.languages?.length) langs.value=d.languages
  } catch {}
  if (!langs.value.length) langs.value=[
    {code:'en',native_name:'English',flag:'🇺🇸'},{code:'zh',native_name:'中文',flag:'🇨🇳'},
    {code:'ja',native_name:'日本語',flag:'🇯🇵'},{code:'ko',native_name:'한국어',flag:'🇰🇷'},
    {code:'de',native_name:'Deutsch',flag:'🇩🇪'},{code:'fr',native_name:'Français',flag:'🇫🇷'},
    {code:'es',native_name:'Español',flag:'🇪🇸'},
  ]
  // Fetch style templates
  try {
    const sd = await apiFetch('/api/styles')
    if (sd && typeof sd === 'object') styles.value = sd
  } catch {}
  await loadPresets()
})
</script>

<style scoped>
.create-page{padding:28px 24px 80px;max-width:1200px;margin:0 auto;}
.page-header{margin-bottom:24px;}
.page-header h1{font-size:30px;font-weight:800;letter-spacing:-0.5px;margin-bottom:4px;color:var(--text);}
.page-header p{color:var(--text2);font-size:14px;}
.empty-state{text-align:center;padding:80px 24px;display:flex;flex-direction:column;align-items:center;gap:12px;}

.section-label{font-size:11px;font-weight:800;letter-spacing:3px;color:var(--accent);text-transform:uppercase;margin:24px 0 12px;}

.preset-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 14px;margin-bottom:20px;background:rgba(99,102,241,.04);border:1px solid rgba(99,102,241,.15);border-radius:12px;}

.config-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:0;}
.config-card{padding:20px;}
.upload-zone{border:2px dashed var(--border);border-radius:12px;padding:28px 20px;cursor:pointer;transition:all .2s;min-height:150px;display:flex;align-items:center;justify-content:center;background:var(--bg);}
.upload-zone:hover,.upload-zone.over{border-color:var(--accent);background:rgba(99,102,241,.04);}
.slider{width:100%;accent-color:var(--accent);cursor:pointer;}

/* CANVAS EDITOR */
.canvas-card{padding:0;overflow:hidden;margin-bottom:0;}
.canvas-editor-wrap{display:grid;grid-template-columns:180px 1fr 180px;min-height:440px;}
@media(max-width:900px){.canvas-editor-wrap{grid-template-columns:1fr;}}

.parts-sidebar{border-right:1px solid var(--border);padding:14px;display:flex;flex-direction:column;gap:8px;overflow-y:auto;max-height:560px;background:var(--bg3);}
.sidebar-hdr{font-size:11px;font-weight:800;letter-spacing:1px;color:var(--text3);text-transform:uppercase;margin-bottom:4px;}

.part-chip{padding:10px;border-radius:8px;border:1.5px solid var(--border);background:var(--bg2);cursor:pointer;transition:all .15s;position:relative;}
.part-chip:hover{background:var(--bg3);box-shadow:var(--shadow);}
.part-chip.active{border-color:rgba(99,102,241,.4);background:rgba(99,102,241,.06);}
.part-chip-title{font-size:12px;font-weight:700;color:var(--text);margin-bottom:4px;}
.del-part{font-size:10px;color:var(--err);background:transparent;border:none;cursor:pointer;padding:2px 4px;border-radius:4px;flex-shrink:0;}
.del-part:hover{background:rgba(239,68,68,.1);}
.part-action-btn{font-size:11px;color:var(--text3);background:transparent;border:none;cursor:pointer;padding:2px 4px;border-radius:4px;flex-shrink:0;}
.part-action-btn:hover{background:rgba(99,102,241,.1);color:var(--accent);}
.add-part{margin-top:4px;padding:8px;border-radius:8px;background:rgba(99,102,241,.06);border:1.5px dashed rgba(99,102,241,.3);color:var(--accent);font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;}
.add-part:hover:not(:disabled){background:rgba(99,102,241,.12);}
.add-part:disabled{opacity:.4;cursor:not-allowed;}

.canvas-center{display:flex;flex-direction:column;padding:10px;}
.canvas-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 4px;border-bottom:1px solid var(--border);margin-bottom:10px;}
.drag-chip{padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;cursor:move;user-select:none;transition:all .15s;}
.drag-chip:hover{transform:scale(1.05);}
.zoom-btn{padding:4px 10px;border-radius:6px;background:var(--bg3);border:1px solid var(--border);color:var(--text2);font-size:13px;cursor:pointer;transition:all .15s;}
.zoom-btn:hover{background:var(--border);color:var(--text);}
.canvas-outer{flex:1;overflow:auto;}
.canvas-scroll-area{min-height:320px;cursor:default;}

.cv-box{transition:border .1s,box-shadow .1s;}
.cv-box-preview{border-radius:3px;display:block;}
.cv-box-label{display:flex;align-items:center;justify-content:center;height:100%;font-size:12px;font-weight:700;gap:4px;pointer-events:none;}
.cv-resize{position:absolute;bottom:0;right:0;width:12px;height:12px;cursor:se-resize;background:rgba(255,255,255,.3);border-radius:2px 0 3px 0;}
.cv-delete{position:absolute;top:2px;right:2px;width:16px;height:16px;border-radius:3px;background:rgba(239,68,68,.7);border:none;color:#fff;font-size:9px;cursor:pointer;opacity:0;transition:opacity .15s;display:flex;align-items:center;justify-content:center;padding:0;}
.cv-box:hover .cv-delete{opacity:1;}

.props-sidebar{border-left:1px solid var(--border);padding:14px;overflow-y:auto;max-height:560px;background:var(--bg3);}
.props-form{display:flex;flex-direction:column;}
.prop-row2{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:4px;}
.input-sm{padding:6px 8px;font-size:12px;}

/* STYLE GALLERY */
.style-card{padding:20px;margin-bottom:0;}
.style-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:10px;}
.style-card-item{
  border-radius:12px;border:2px solid var(--border);cursor:pointer;
  transition:all .2s cubic-bezier(0.34,1.56,0.64,1);
  text-align:center;padding-bottom:8px;overflow:hidden;position:relative;
  background:var(--bg2);
}
.style-card-item:hover{border-color:var(--accent);transform:scale(1.04);box-shadow:var(--shadow2);}
.style-card-item.active{border-color:var(--accent);box-shadow:0 0 0 3px rgba(99,102,241,.15);}
.style-swatch-bg{padding:12px 8px 8px;display:flex;flex-direction:column;align-items:center;gap:2px;}
.style-swatch-src{font-size:18px;font-weight:900;line-height:1;}
.style-swatch-tgt{font-size:11px;font-weight:500;opacity:.8;}
.style-card-name{font-size:10px;font-weight:700;color:var(--text2);padding:0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.style-check{position:absolute;top:4px;right:4px;background:var(--accent);color:#fff;border-radius:50%;width:16px;height:16px;font-size:9px;display:flex;align-items:center;justify-content:center;font-weight:700;}

/* ANIMATION BUTTONS */
.anim-btn{padding:8px 18px;border-radius:20px;font-size:13px;font-weight:600;cursor:pointer;
  background:var(--bg3);border:1.5px solid var(--border);color:var(--text2);transition:all .2s;}
.anim-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(99,102,241,.05);}
.anim-btn.active{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent;color:#fff;box-shadow:0 4px 12px rgba(99,102,241,.25);}

.font-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;}
.font-chip{padding:10px 8px;border-radius:8px;border:1.5px solid var(--border);cursor:pointer;text-align:center;transition:all .2s;background:var(--bg);}
.font-chip:hover{border-color:rgba(99,102,241,.4);background:rgba(99,102,241,.03);}
.font-chip.active{border-color:var(--accent);background:rgba(99,102,241,.08);}

/* SUBMIT ROW */
.submit-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px;}

/* PROGRESS */
.progress-card{padding:28px;margin-top:20px;}
.step-bar{display:flex;align-items:center;margin-bottom:16px;}
.step-dot{width:34px;height:34px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:var(--bg3);border:2px solid var(--border);color:var(--text3);transition:all .3s;}
.step-dot.active{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent;color:#fff;box-shadow:0 0 16px rgba(99,102,241,.35);}
.step-dot.done{background:rgba(16,185,129,.1);border-color:rgba(16,185,129,.4);color:var(--ok);}
.step-ln{flex:1;height:2px;background:var(--border);transition:background .3s;}
.step-ln.done{background:linear-gradient(90deg,var(--ok),rgba(16,185,129,.3));}
.cur-step{display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;color:var(--text2);margin-bottom:4px;}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.5s infinite;flex-shrink:0;}
.log-box{max-height:220px;overflow-y:auto;margin-top:14px;padding:12px;background:#1e1e2e;border-radius:8px;border:1px solid #2d2d3e;font-size:12px;line-height:1.7;}
.log-line{color:#94a3b8;}
.log-line.ok{color:#10b981;}
.log-line.err{color:#ef4444;}
</style>
