# HTML 动画合约

AI 为每个视频生成 `src/index.html`（HTML/CSS/JS 动画），必须遵守以下合约，
以确保构建脚本（`build_video.py`）能正确录制和合成视频。

## 文件结构

```
project-dir/
├── video-config.json          # 内容 + 时间配置
├── src/
│   └── index.html             # AI 生成的 HTML（可内联 CSS/JS 或引用外部文件）
├── assets/
│   └── audio/                 # generate_tts.py 生成的音频和字幕
│       ├── scene_1.mp3
│       ├── scene_1.srt
│       ├── scene_2.mp3
│       ├── scene_2.srt
│       └── manifest.json
└── output/                    # build_video.py 生成的视频
```

## 必须实现的约定

### 1. URL 参数

HTML 页面必须检查 URL 参数：

```javascript
const params = new URLSearchParams(window.location.search);
const headless = params.get('headless') === 'true';
```

当 `headless=true` 时，**立即自动开始播放**（不显示任何"点击开始"按钮）。

### 2. 播放开始信号

动画开始播放的瞬间，设置全局变量：

```javascript
window.__playbackStartedMs = performance.now();
```

构建脚本通过此信号测量页面启动延迟并裁剪视频开头。
**这是最关键的约定，必须实现。**

### 3. 字幕显示

页面必须包含一个字幕容器元素：

```html
<div id="subtitle-bar">
    <span id="subtitle-text"></span>
</div>
```

并实现以下逻辑：

1. 从 `../assets/audio/scene_N.srt` 加载每个场景的 SRT 字幕文件
2. 解析 SRT 时间码
3. 根据当前播放时间显示对应的字幕文本
4. **在 headless 模式下使用 wall-clock 时间驱动字幕**（headless 模式下音频不会播放）

### 4. 音频路径

音频文件由 `generate_tts.py` 生成，路径固定为：

```
../assets/audio/scene_1.mp3
../assets/audio/scene_1.srt
../assets/audio/scene_2.mp3
...
```

注意：HTML 在 `src/index.html`，所以路径以 `../` 开头。

### 5. 分辨率

固定 **1920 × 1080**，所有元素按此分辨率布局。

### 6. 场景时长

从 `video-config.json` 的 `scenes[].duration` 读取每个场景的时长（毫秒）。
总播放时间 = 所有场景 duration 之和。

## video-config.json 最小 Schema

AI 生成自定义 HTML 时，`video-config.json` 只需包含以下字段：

```json
{
    "title": "视频标题",
    "language": "zh-CN",
    "voice": "zh-CN-YunxiNeural",
    "voiceRate": "-5%",
    "voiceVolume": "+0%",
    "scenes": [
        {
            "narration": "这个场景的旁白文字",
            "duration": 10000
        }
    ]
}
```

### 必须字段

| 字段                 | 类型   | 说明                     |
| -------------------- | ------ | ------------------------ |
| `title`              | string | 视频标题                 |
| `voice`              | string | edge-tts 声音名称        |
| `scenes`             | array  | 场景数组                 |
| `scenes[].narration` | string | 场景旁白文本（用于 TTS） |
| `scenes[].duration`  | number | 场景时长（毫秒）         |

### 可选字段

其他所有字段（如 `language`、`voiceRate`、`voiceVolume`）都有默认值。

AI 可以在 scenes 里添加任意自定义字段（如 `heading`、`type`、`items` 等），
供自己生成的 HTML/JS 读取。**构建脚本只关心 `narration` 和 `duration`。**

## 推荐模式

```javascript
// AI 生成的 index.html 推荐的启动模式
(async function () {
    const params = new URLSearchParams(window.location.search);
    const headless = params.get('headless') === 'true';

    // 1. 加载配置
    const config = await fetch('../video-config.json').then(r => r.json());

    // 2. 构建场景 DOM（AI 自由发挥）
    buildScenes(config);

    // 3. 加载字幕
    const subtitles = await loadSubtitles(config.scenes.length);

    // 4. 开始播放
    if (headless) {
        startAutoPlay(config, subtitles);
    } else {
        document.getElementById('start-btn').addEventListener('click', () => {
            startAutoPlay(config, subtitles);
        });
    }

    function startAutoPlay(config, subtitles) {
        window.__playbackStartedMs = performance.now();  // ← 关键信号
        // ... 按 duration 依次切换场景，同步字幕
    }
})();
```

## 字幕样式参考

```css
#subtitle-bar {
    position: fixed;
    bottom: 60px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
}

#subtitle-text {
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 10px 30px;
    border-radius: 8px;
    font-size: 28px;
}
```

## 完整参考实现（仅供理解合约逻辑）

以下代码**仅展示 4 个约定的最小技术实现**。
**不要照搬其页面结构和场景切换方式。**
AI 应自行设计场景的 DOM 结构、布局方式、切换动画。

> 注意：下面用 `display:none/block` 做场景切换只是最简单的示例。
> 实际生成时应使用更丰富的方式：CSS transform 过渡、opacity 渐变、
> 滑动/缩放/3D翻转、Canvas 重绘、甚至同屏多区域并行展示等。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080">
    <title>视频标题</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { width: 1920px; height: 1080px; overflow: hidden; }
        #subtitle-bar { position: fixed; bottom: 60px; left: 50%; transform: translateX(-50%); z-index: 1000; pointer-events: none; }
        #subtitle-text { background: rgba(0,0,0,0.75); color: #fff; padding: 10px 30px; border-radius: 8px; font-size: 28px; }
        /* ⬆ 以上是约定必须的。以下场景样式完全自由设计 ⬇ */
    </style>
</head>
<body>
    <!-- 约定必须：字幕容器 -->
    <div id="subtitle-bar"><span id="subtitle-text"></span></div>

    <!-- 场景容器：结构完全自由，不必是 section 列表 -->

    <script>
    (async function() {
        // === 约定 1：headless 检测 ===
        const headless = new URLSearchParams(location.search).get('headless') === 'true';

        // === 加载配置（必须） ===
        const config = await fetch('../video-config.json').then(r => r.json());
        const durations = config.scenes.map(s => s.duration);

        // === 约定 3：加载字幕（必须） ===
        const subs = {};
        for (let i = 0; i < config.scenes.length; i++) {
            try {
                const r = await fetch('../assets/audio/scene_' + (i+1) + '.srt');
                if (r.ok) subs[i+1] = parseSRT(await r.text());
            } catch(e) {}
        }

        let globalStart = 0, subTimer = null;

        // === 约定 3：字幕同步（必须） ===
        function syncSubs(sceneId) {
            if (subTimer) clearInterval(subTimer);
            const cues = subs[sceneId];
            if (!cues) return;
            let offset = 0;
            for (let i = 0; i < sceneId - 1; i++) offset += durations[i];
            subTimer = setInterval(() => {
                const t = Math.max(0, (performance.now() - globalStart - offset) / 1000);
                const c = cues.find(c => t >= c.start && t <= c.end);
                document.getElementById('subtitle-text').textContent = c ? c.text : '';
            }, 100);
        }

        function parseSRT(srt) {
            const cues = [];
            for (const block of srt.replace(/\r\n/g,'\n').trim().split(/\n\n+/)) {
                const lines = block.split('\n');
                if (lines.length < 3) continue;
                const m = lines[1].match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})/);
                if (!m) continue;
                cues.push({ start: +m[1]*3600+ +m[2]*60+ +m[3]+ +m[4]/1000, end: +m[5]*3600+ +m[6]*60+ +m[7]+ +m[8]/1000, text: lines.slice(2).join(' ') });
            }
            return cues;
        }

        // === 场景切换（AI 自由实现）===
        // 下面只是最简示例。实际应使用丰富的过渡动画。
        function showScene(idx) {
            syncSubs(idx + 1);
            // AI 在这里实现自己的场景切换逻辑
            // 可以是 CSS transform、Canvas 重绘、DOM 替换、opacity 过渡等任何方式
        }

        // === 约定 2：播放信号（必须） ===
        function startAutoPlay() {
            globalStart = performance.now();
            window.__playbackStartedMs = globalStart;
            showScene(0);
            let cum = 0;
            durations.forEach((d, i) => { if (i > 0) { const c = cum; setTimeout(() => showScene(i), c); } cum += d; });
        }

        if (headless) startAutoPlay();
        else startAutoPlay();
    })();
    </script>
</body>
</html>
```

### 约定 vs 自由区域

| 部分                  | 约定必须？ | 说明                                    |
| --------------------- | ---------- | --------------------------------------- |
| headless 检测         | 是         | 必须检测 `?headless=true`               |
| `__playbackStartedMs` | 是         | 播放开始瞬间必须设置                    |
| 字幕容器              | 是         | 必须有 `#subtitle-bar > #subtitle-text` |
| SRT 加载解析          | 是         | 必须从 `../assets/audio/` 加载          |
| 全局时间线字幕同步    | 是         | headless 下用 wall-clock 驱动           |
| 场景 DOM 结构         | **否**     | 自由设计，不必是 section 列表           |
| 场景切换方式          | **否**     | 自由实现，不必是 display 切换           |
| 布局方式              | **否**     | 自由选择 flex/grid/绝对定位/Canvas      |
| CSS/动画              | **否**     | 完全自由                                |
| 背景效果              | **否**     | 完全自由                                |

AI 生成 HTML 时，应保留上述代码中标注「必须」的部分，
其余全部自由设计，创造独特的视觉体验。
