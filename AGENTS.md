# AGENTS.md

给在本仓库工作的 AI 代理的约定。人类读者看 [README.md](README.md)。

## 这个仓库是什么

一条通用管线：把视频逐帧映射成 PCB 焊盘阵列，在嘉立创EDA 里渲染后截图合成。当前样例是《Bad Apple!!》，但**管线本身不绑定任何特定片源**。

**一次全量渲染 = 94 分钟 + EDA 客户端必须在前台**。任何会触发重渲的改动，先说明影响范围再动手。

## 先看现成的

`easyeda-api` 是嘉立创官方 skill（`metadata.author: JLCEDA`），自带桥接服务、完整 API 参考和 `easyeda-pro` CLI。

动手写之前先翻 `references/classes/`。自己造轮子之前，至少确认官方没有对应能力。

## 不要直接提交

**未经确认不要 `git commit` 或 `git push`。** 改完先让用户看 diff。

## 不能动的东西

| 路径 | 原因 |
|---|---|
| `frames/` | 3.82 GB 母版帧，重渲要 94 分钟 |
| `deliverables/` | 成片，重新编码会改变码流 |
| `ext/` 与 `*.eext` | 扩展已装在 EDA 里，换了要重装 |

`.gitignore` 已排除上述大件。不要用 `git add -f` 绕过。

## 关键不变量

改 `layout.py` 或 `driver.py` 里这几项会让已有帧与新帧不一致，**必须重渲全片**才成立：

- `COLS, ROWS` — 栅格密度
- `MARGIN` — 板框内缩，需大于安装孔最远半径，否则孔压点阵
- `THRESH` 与极性 — 取 `a > THRESH` 还是 `<`，决定白场还是黑场点亮
- 坐标式 `y = oytop − 行号 × 栅距` — **EDA 的 y 向上增大，不翻转就整幅颠倒**

## 起跑前检查

1. 桥接在跑：`node "$USERPROFILE/.workbuddy/skills/easyeda-api/scripts/bridge-server.mjs"`
2. EDA 里 PCB 文档处于**激活**状态——只剩 Start Page 时所有 `pcb_*` 接口返回 `null`
3. 进程已声明 DPI 感知，否则 `GetWindowRect` 返回虚拟化尺寸，右侧面板会被裁掉
4. 窗口未最小化；机器上可能同时开着多个 EDA 窗口，**按标题挑，别取第一个**

## 常见故障

| 现象 | 原因 | 处置 |
|---|---|---|
| `Cannot read properties of null (reading 'map')` | PCB 文档没激活 | `dmt_EditorControl.activateDocument(tabId)` |
| 截图为纯白 | 窗口被最小化或 DWM 停止绘制 | 最小化再还原强制重绘 |
| 整窗偏暗 | EDA 失焦，叠了 ×0.803 蒙版 | `driver/fix_dim.py` 按比例还原 |
| 建盘请求超时 | 桥接单请求 30 s 上限 | 分批，`render_one.render` 已按 1200/批 |
| 安装孔消失 | 建孔在 `render()` 之前，被整体清空删掉 | 先渲染点阵，后建孔 |

## 验证顺序

不要一上来就跑全片。每步都能独立证伪：

1. 单帧：`python driver/render_one.py 120 smd` → 看截图
2. 十帧：`run_frames.py -n 10` → 看是否稳定、有无漂移
3. 抽样：跑 100 帧，确认板框位置恒定
4. 全量

## 提交

- 提交信息写清楚「改了什么物理量」，例如「栅距 25.98 → 28.19（内缩 250 → 110）」，而不是「优化布局」。
- 改了渲染参数又没重渲，在提交信息里显式写明「现有帧已过期」。
