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

当 `headless=true` 时，资源就绪后自动开始播放，不等待点击、音频授权或 `audio.play()`。配置、字幕或必要素材加载失败时报告具体路径，不要把错误页当作已就绪。

### 2. 播放开始信号

动画开始播放的瞬间，设置全局变量：

```javascript
window.__playbackStartedMs = performance.now();
```

构建器用片尾校准帧把此起点映射到录像时间戳；校准帧不进成片。启动失败时设置 `window.__playbackError = String(error)`，不要发成功信号。
**这是最关键的约定，必须实现。**

先画首帧，再用同一个 `performance.now()` 值初始化播放起点和信号。每一帧按 `performance.now() - 起点` 计算镜头、动作和字幕；不要在绘制回调内重置起点，也不要靠帧数或未播放的 `audio.currentTime` 计时。若提供 `?at=毫秒`，让它调用同一个绘制函数一次且不启动时钟。定点预览用于检查构图，不能替代实际录制。

Three.js 页面遵守同一合约。参见[三维手册与可执行样例](THREEJS.md)。

### 3. 字幕显示

页面必须包含一个字幕容器元素：

```html
<div id="subtitle-bar">
    <span id="subtitle-text"></span>
</div>
```

并实现以下逻辑：

1. 只为有旁白的镜头从 `../assets/audio/scene_N.srt` 加载字幕；缺失或任何一条格式错误都报告文件路径并停止启动。静默镜头不加载、不播音，进入时清空上一镜字幕。
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

自定义字段供作者的 HTML/JS 读取，见[配置参考](CONFIG-SCHEMA.md)。构建器检查逐段时长和可选的全片上限 `maxDurationMs`；它不要求每段旁白创建或替换一页 DOM。

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

把 [captions.js](../assets/prism/src/captions.js) 复制到项目 `src/`，与下面的入口放在一起。以下代码展示录制时钟和字幕，不提供美术模板。
**不要照搬其页面结构和场景切换方式。**
AI 应自行设计场景的 DOM 结构、布局方式、切换动画。

> `index` 用于定位旁白段和字幕，`local` 用于安排段内动作，`elapsed` 可驱动跨段连续动作。何时切镜取决于下一条证据出现在哪里，不取决于字幕文件何时换号。例如调试演示可保持同一个编辑器，让观众看见一次修改怎样改变运行结果。无需给两段之间添加过场效果。

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

    <script type="module">
    (async function() {
        // === 约定 1：headless 检测 ===
        const headless = new URLSearchParams(location.search).get('headless') === 'true';

        // === 加载配置（必须） ===
        const response = await fetch('../video-config.json');
        if (!response.ok) throw new Error(`../video-config.json: HTTP ${response.status}`);
        const config = await response.json();
        const durations = config.scenes.map(s => s.duration);

        // === 约定 3：加载字幕（必须） ===
        const { loadCaptions } = await import('./captions.js');
        const tracks = await loadCaptions(config.scenes);
        await document.fonts.ready;
        const total = durations.reduce((sum, duration) => sum + duration, 0);
        function renderAt(elapsed) {
            let index = 0, local = elapsed;
            while (index + 1 < durations.length && local >= durations[index]) local -= durations[index++];
            const cue = tracks[index].find(cue => cue.start <= local && local < cue.end);
            document.querySelector('#subtitle-text').textContent = cue?.text ?? '';
            // 在此用同一 index、local 绘制主体和动作。
        }
        renderAt(0);
        if (headless) {
            const origin = window.__playbackStartedMs = performance.now();
            function tick() {
                const elapsed = performance.now() - origin;
                renderAt(Math.min(elapsed, total));
                if (elapsed < total) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        }
    })().catch(error => {
        window.__playbackError = document.querySelector('#subtitle-text').textContent = String(error);
        console.error(error);
    });
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
