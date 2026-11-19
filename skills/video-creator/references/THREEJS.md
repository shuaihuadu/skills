# Three.js 镜头与试录

## 先定镜头，再定特效

把分镜写成「对象 → 变化 → 观众能得出的结论」。选 3D 的理由应当能在一张前后对照图里看出来。

| 题材       | 镜头设计                                                                                     | 避免的问题                                                 |
| ---------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 产品拆解   | 斜侧光照出轮廓；正交相机保持零件比例；沿同一装配轴逐件拉开，最后定格标注。                   | 一边旋转一边拆，观众分不清前后关系。                       |
| 建筑、地形 | 先俯视定位，再沿已标出的路径压低视角；用掠射光揭示高差。模型太大就只加载镜头经过的范围。     | 用飞行相机不停绕圈，却不给方向或尺度参照。                 |
| 光学、流动 | 先跟随单条路径，再揭示分叉或实例化的整体流向；在转折处停一下。明确是示意还是按物理模型计算。 | 用随机粒子、眩光遮住关键边界，或用不准确模型声称定量结果。 |
| 抽象流程   | 只有拓扑、队列或空间路径确实有用时才建三维。用一个可辨认的对象贯穿多个镜头，结果用平面标注。 | 普通用户需要一个生活类比，却看到一串悬浮术语。             |

给每镜指定一个主体、一种主运动。主光交代体积，轮廓光区分背景；控制透明材质叠层，先用几何、材质和构图取得辨识度，再考虑局部辉光。字幕独立于 WebGL 以 DOM 绘制，保留下方安全区；信息密集处让镜头停稳。

## 从一个能录的镜头开始

[样例项目](../assets/prism/video-config.json)是两镜的原创棱镜示意：先从斜面看见棱镜的厚度与入射白光，再在第二段旁白开始时拉出可见光谱。颜色和角度用于定性讲解，不是光学仿真。只需 Three.js，无远程模型、字体或运行时 CDN。

在 **PowerShell** 运行以下命令。将第一行换成自己的技能目录；假设已按主文档准备好 Python 环境和 Chromium。样例复制到新目录，依赖、配音和视频都不写入技能源目录。

```powershell
$skill = (Resolve-Path 'D:\Github\shuaihuadu\skills\skills\video-creator').Path
$project = Join-Path ([IO.Path]::GetTempPath()) ('prism-' + [guid]::NewGuid().ToString('N'))
Copy-Item -Recurse -LiteralPath "$skill/assets/prism" -Destination $project
npm.cmd install --prefix $project --ignore-scripts --no-audit --no-fund
python -X utf8 "$skill/scripts/generate_tts.py" "$project/video-config.json"
python -X utf8 "$skill/scripts/build_video.py" --check "$project/video-config.json"
if ($LASTEXITCODE -ne 0) { throw 'Check measured narration and subtitle durations before recording.' }
python -X utf8 "$skill/scripts/build_video.py" "$project/video-config.json"
```

macOS/Linux 同样复制整个 `assets/prism/` 到项目目录，在副本运行 `npm install --ignore-scripts`，再用虚拟环境解释器调用上述两个脚本并传入配置的绝对路径。从 `output/<timestamp>/video.mp4` 取成片。要预览，在副本根目录执行 `python -m http.server 8000 --bind 127.0.0.1`，访问 `http://127.0.0.1:8000/src/index.html`。点击播放含旁白；加 `?at=1700` 看入射光，`?at=6800` 看光谱，`?headless=true` 自动播放无声画面供录制。

## 换成自己的题材

1. 保留[样例入口](../assets/prism/src/index.html)的资源检查、SRT 加载、单一起点和 `renderAt`。样例只编排了两个镜头；增减镜头时按所有 `duration` 做累计边界，用镜头内时间驱动各自的动作。
2. 替换 `makeOptics`。先用简单几何体定构图；已有授权的实物模型适合用 glTF/GLB。用同版本的 Three.js 与 addons，加载器/解码器也放进项目并检查请求成功。不要关浏览器安全设置来解决跨域。
3. 摄像机、实例位置、着色器时间和关键帧都从传入的毫秒数推导；要随机纹理或粒子时固定种子。手动拖动的相机不会出现在无人操作的录制里，要把机位变化写进时间线。
4. 录制输出仍为 1920×1080。样例以 1280×720 内部缓冲区换取余量，字幕以输出分辨率绘制。按机器实测试阴影、透明层和后处理；画面卡顿时依次减像素比、关后处理、用实例化减少绘制调用。别用提高输出帧率掩盖卡顿。

## 没有 WebGL 或录出来不对怎么办

- 先在**用于录制的无头 Chromium** 里试最复杂的 3–5 秒，检查模块、纹理、浏览器异常和画布内容。未渲染前不发 `__playbackStartedMs`；缺资源先修路径。渲染器不可用则将同一镜头改成预渲染序列或 Canvas/SVG 剖面，保留相同语义、时钟和字幕，明确标记降级，不能交付黑画布。
- 用 FFmpeg 从**编码后的 MP4** 取两个有判别力的时刻。例如此样例在 1.7 秒只有白光，6.8 秒右侧必须有分开的彩色光束；字幕分别来自两段 SRT。两帧字幕不同而光路相同，仍然算失败。

```bash
ffmpeg -v error -ss 1.7 -i video.mp4 -frames:v 1 before.png
ffmpeg -v error -ss 6.8 -i video.mp4 -frames:v 1 after.png
```

定点预览正常而成片冻结，先查录制路径是否真的启动了计时，是否等了无声浏览器永远不会触发的音频事件。成片只在切镜处串音，则先复核每段 MP3 的实测长度、SRT 末尾和 `duration` 的毫秒/秒换算。