# Remotion 密码判断讲解

这是 PY1176「密码判断」的 Python 讲解视频项目。

## 生成语音

```bash
npm run voiceover
```

## 预览

```bash
npm run studio
```

## 分镜和字幕

分镜源文件是 `storyboard.json`。每条分镜都有稳定 `id`，并记录画面说明、旁白脚本、字幕文本、预计时长和检查点，方便后续只改某个分镜和对应字幕。

查看分镜：

```bash
python3 -m http.server 8765
```

然后打开 `http://127.0.0.1:8765/remotion_password_judgement/storyboard_viewer.html`。

校验分镜：

```bash
python3 scripts/video_workflow.py storyboard remotion_password_judgement
```

## 渲染

```bash
npm run render
```
