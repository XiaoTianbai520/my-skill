---
name: video-probe
description: Probe local video files on this Windows machine without ffmpeg — extract metadata, sample frames, measure motion/cut structure, and detect audio tracks using Python venv + OpenCV. Use when a task needs to know what a video contains (duration, cuts, motion beats, audio presence) before writing video prompts, doing analysis, or selecting clips.
description_zh: "无 ffmpeg 环境下探查本地视频：抽帧、时长/分辨率/运动节奏/剪切点/音轨分析"
description_en: "Probe local videos without ffmpeg: frames, duration, motion beats, cuts, audio detection"
agent_created: true
---

# Video Probe（无 ffmpeg 视频探查）

本机没有 ffmpeg，且 agent 模型可能无法直接读图。此 skill 用 OpenCV 拿到视频的"结构化事实"。

## 环境准备（一次性）

```bash
# 1. Bash 环境 PATH 是坏的，每条命令前必须修：
export PATH="/usr/bin:/bin:$PATH"

# 2. 建 venv（托管 Python 3.13）
C:/Users/c1338/.workbuddy/binaries/python/versions/3.13.12/python.exe -m venv C:/Users/c1338/.workbuddy/binaries/python/envs/default

# 3. 装 OpenCV —— 网络慢/卡死时必须走本地代理
C:/Users/c1338/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install --proxy http://127.0.0.1:7890 opencv-python-headless
```

坑：
- 不要用 PowerShell 工具做这事：stdout 不回显，多行脚本会被 "Encoded commands" 安全策略拦截
- pip 不挂代理会卡 3 分钟以上无输出，先杀掉再带 `--proxy` 重跑
- python 路径用 `C:/...` 正斜杠写法，别用 `/c/...` 传给 Windows 程序参数

## 分析脚本要点

```python
import cv2
cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS)
count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w, h = int(cap.get(3)), int(cap.get(4))
dur = count / fps

# 定点抽帧（供需要时保存 jpg）
cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
ok, frame = cap.read()

# 逐帧运动强度（缩小到 160x284 提速 + 抗噪）
# prev 与当前帧 absdiff().mean() → 得到每秒运动剖面
# 剪切点检测：motion > mean + 3*std 的孤立尖峰
```

- 音轨检测：直接二进制读文件头 4MB，`b"soun" in head and b"mp4a" in head` 即有音轨

## 能产出的事实（可直接写进提示词）

- 时长/分辨率/帧率/画幅比例（竖屏 1080x1920 = 9:16）
- 是否单镜头（无剪切尖峰 = 连续一镜到底）
- 运动节奏剖面：哪些秒段动作强、哪些收；重音时间点（写提示词时用于 timing accent）
- 是否自带音轨（决定 `<Audio 1>` 是否可复用）

## 看图（关键）

主会话的模型**不支持图片输入**：Read 图片会返回 `current model does not support images`。

已验证可行的绕法：**派一个子代理，指定 `model: "reasoning"`**，它读图正常。

```
Agent(
  subagent_type="general-purpose",
  model="reasoning",
  prompt="Read these absolute paths in order and describe: ... 若你的 Read 也拒绝读图，只回 VISION_UNAVAILABLE"
)
```

实测：12 张 1080x1920 抽帧全部读出，人物穿搭、背景、机位、逐帧动作时间线都拿到了。

提示词要点：
- 让子代理**按顺序**读，逐帧描述后再归纳成动作段落（0-3s / 3-7s / ...）
- 明确写「vague words like 'dancing happily' are useless」，要求具体到手位、重心、朝向
- 加一句「看不清就说 unclear，不要猜」，避免编造

## 局限

- 若子代理也不可用，具体动作/外观只能靠用户描述，或让视频模型从参考素材自取（如 H3 Ref2VA 的 `attribute_transfer` 写法）
- 不要凭空编造画面细节
