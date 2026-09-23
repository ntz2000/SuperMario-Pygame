# 架构与交接文档

> 项目：NSMB 风格超级马里奥（Python + pygame-ce）
> 位置：`/home/ntz/workspace/game`（所有开发限定在此目录）
> 运行：`python3.12 main.py`（注意：必须用 anaconda 的 python3.12，`/usr/bin/python3` 没有 pygame）

## 一图流

```
main.py                     入口：CLI 参数、场景选择、headless 截图、Bot 自动玩
└─ mario/
   ├─ engine/               引擎层（与马里奥无关的通用设施）
   │   ├─ app.py            窗口、60Hz 固定步长主循环、SFX/音乐播放、headless
   │   ├─ scene.py          场景栈 + 黑屏淡入淡出过渡（push=暂停菜单、fade_to=换关）
   │   ├─ input.py          动作制输入：按键边沿、跳跃预输入缓冲、土狼时间配合
   │   │                    Input（键盘）/ VirtualInput（测试与 Bot 驱动）双实现
   │   ├─ camera.py         死区跟随 + 跑动前瞻 + 屏震
   │   ├─ assets.py         资产注册表 + 内容哈希磁盘缓存（改美术自动失效）
   │   ├─ ink.py             像素画光栅器：PIL 超采样画形 → 盒滤波缩小 → 描边/受光
   │   └─ audio.py          chiptune 渲染器（音符表 → WAV 字节，numpy）
   ├─ core/                 核心层（物理与网格）
   │   ├─ physics.py        轴分离扫掠 AABB；_hit() 浮点过滤是关键（见"历史 bug"）
   │   ├─ tiles.py          字符 → Tile 定义表 + 五套主题调色（overworld 等）
   │   ├─ tilemap.py        瓦片网格：碰撞查询、分块渲染缓存、顶砖动画
   │   ├─ tuning.py         所有手感数值（重力/跳跃/速度/连击表）
   │   └─ actor.py          Actor 基类：Body + 动画状态 + update/draw
   ├─ game/                 玩法层
   │   ├─ player.py         玩家：走跑跳/墙跳/旋转跳/下砸/形态/搬龟壳/死亡动画
   │   ├─ enemies.py        敌人：龟壳状态机（walk→shell→slide）、Bowser、火苗
   │   ├─ objects.py        道具/机关：蘑菇、弹簧、移动平台、旗杆、大金币…
   │   └─ registry.py       对象类型名 → 类（关卡数据加载用）
   ├─ scenes/               场景层
   │   ├─ level.py          ★ 关卡场景=world 对象：阶段状态机 + 全部交互规则
   │   ├─ title.py          标题（选关 + 大金币收集显示）
   │   ├─ worldmap.py       世界地图（节点 + 大金币进度）
   │   └─ menu.py           暂停菜单（压栈）+ GameOver
   ├─ art/                  美术与音效（全部程序化生成，零外部文件）
   │   ├─ hero.py           玩家骨骼姿势系统（跑/跳/滑/游/转…按形态×动画注册）
   │   ├─ props.py          敌人/道具/特效贴图
   │   ├─ tiles.py          地形块贴图（fill/top/cap 三变体 × 主题配色）
   │   └─ sound.py          SFX 与 BGM 音符表
   ├─ data/
   │   ├─ levels.py         关卡 DSL（Builder）→ 世界 1 全部 5 关
   │   └─ art_cache/        生成资源缓存（PNG/WAV + manifest.json，可随时删）
   └─ debug.py              Bot 自动玩（smoke 测试/截图用）
tests/                      pytest：物理/资产一致性/关卡数据/玩法集成（80 个）
```

## 核心概念

### 1. 关卡场景即 world
[scenes/level.py](../mario/scenes/level.py) 的 `LevelScene` 同时是 actors 拿到的 `world`：
提供 `spawn/sfx/fx/shake/fluid_at/note_check/pound_impact` 等动词。交互规则
（踩敌、顶砖、连击计分）集中在这里，actor 保持小。

### 2. 阶段状态机
`phase ∈ {play, death, win, pipe}`：
- `play → death`：掉坑/受伤/超时（`on_death`，只触发一次 `_death_fired` 防重入）
- `death →` 2 秒后扣命 → 复活（带 checkpoint）或 GameOverScene
- `play → win`：旗杆 `finish()` 或 Boss 倒下 `on_boss_dead()`；旗杆滑落→跳离→烟花→`advance()`
- `play → pipe`：站管道口按"下" `enter_pipe()`；下沉 0.6 秒后 `_goto(关卡@出生点)`

### 3. 资产系统
所有贴图/音效是 Python 生成器（`mario/art/`），经 `@asset`/`register` 注册，
`Assets.sprite(id, **配色覆盖)` 按需生成并写 `data/art_cache/`。指纹 = 生成器源码哈希
+ 参数，**改美术代码自动重生成**。主题换色（overworld/castle/…）通过 `body/lip/grit`
参数覆盖实现，不复制代码。

### 4. 物理（core/physics.py）
- 位置=底部中心（脚），`y` 是脚；16px 瓦片；60Hz 固定步长。
- `move_x/move_y` 各自积分，产出接触列表（墙/顶/地）。
- **`_hit()` 浮点过滤**：`solid_cells()` 是宽容探测（±1 格），但 `move_x/move_y`
  用 `_hit()` 做真实重叠判断（EPS=0.05）。历史 bug 就出在缺这层。
- 单程平台：只在下落且上一帧脚在平台顶之上时阻挡。

### 5. 输入（engine/input.py）
动作名（left/right/run/jump/spin/action/down…）而非键码。关键语义：
- `buffered("jump", 7)`：按下后 7 帧内落地仍算跳（跳跃缓冲）
- `released()` 边沿：新按下会清除旧的释放边沿（同帧 up+down 的正确语义）
- `VirtualInput.press/release` 是测试与 Bot 的驱动接口

## 历史上出过的大 bug（新接手者必读）

这几个都是接手时存在、被测试逼出来的根本性问题，重新引入会毁掉整个游戏：

1. **关卡行塌缩**：Builder 用 `""` 填空格子，`"".join()` 后整行宽度塌掉、
   内容错位。→ 空格子必须是 `" "`（空格）。
2. **地面被当墙**：`solid_cells` 的 ±1 宽容边距把脚下 0.001px 的贴面吸附也当成
   横向墙，玩家在平地上完全走不动。→ `move_x/move_y` 必须经 `_hit()` 过滤。
3. **生成器真值陷阱**：`solid_cells` 是生成器函数，`bool(gen)` 恒为 True，
   导致墙滑永远成立、Bot 的坑检测永远失效。→ 一律 `any(... for ... in ...)`。
4. **跳跃够不着方块**：原数值升力仅 2 格，而 ? 块在 4 格高处，永远顶不到。
   → 见 tuning.py 现注释（满跳 4.5 格）。
5. **主题资源 id 拼错**：`terrain()` 曾把 art 改写成不存在的 `tile/{theme}/...`。
   → art id 不带主题前缀，主题只换配色参数。

## 关卡 DSL（data/levels.py）

字符含义见 [core/tiles.py](../mario/core/tiles.py) 的 `default_table()`。
常用：`G`地面 `D`岩 `B`币砖 `b`碎砖 `?`币块 `!`火花块 `C`多币块 `N`音符块
`H`隐藏块 `X`用过的块 `=`单程平台 `M`金属 `S`尖刺 `p|`管道 `w~`水。

对象用 `b.add(类型, x, y, **kw)`，类型对照 [game/registry.py](../mario/game/registry.py)。
**约定**：瓦片坐标 `(x, y)` → 像素中心 `(x*16+8, y*16+16)`（脚底）；
两格宽的管道 warp 对象放在 `x=管左+0.5, y=帽行-0.5`。

关卡列表（世界 1）：
| id | 主题 | 特色 |
|---|---|---|
| 1-1 | 草原 | 教学关；36 号管可进隐藏房；大金币②在隐藏房 |
| 1-2 | 地下 | 墙跳竖井拿大金币②；移动平台 |
| 1-3 | 水 | 游泳、泡泡金币、鱼 |
| 1-castle | 城堡 | 尖刺坑、音符块、Bowser（踩3次） |
| 1-1b | 地下(secret) | 隐藏金币房，`secret=True` 不进关卡列表 |

## 测试与验证

- `python3.12 -m pytest tests/ -q` —— 80 个测试（物理/资产一致性/关卡数据/玩法集成）
- headless 截图：`python3.12 main.py --scene level --level 1-1 --frames 300 --capture out.png --headless`
- Bot 自动玩：`python3.12 main.py --level 1-1 --bot --headless`
- 交互运行：`python3.12 main.py`（窗口 1280×720，4 倍最近邻放大）

按键：←→/AD 移动、Shift/Z 跑、Space/K 跳、X/J 旋转跳、C/V 动作（搬/扔/火球）、
↓ 蹲/下砸(空中)/进管道、Enter 暂停、Esc 暂停菜单。

## 后续路线（建议优先级）

1. **进度存档**：`app.progress` 目前只在内存（done/stars/lives），落盘 JSON 即可持久化。
2. **世界 2+**：照 `levels.py` 的 DSL 扩展；新主题在 `tiles.py` 的 THEMES 加调色即可。
3. **更多机制**：冰面打滑（tile 加 friction 字段）、伸缩管、Yoshi 类坐骑、
   对战模式（本地双人 pygame 有 joystick 支持）。
4. **手感微调**：tuning.py 单文件可调；改后跑 pytest 里 gameplay 测试防回归。
5. **音量/键位设置界面**：App.volume/input.bindings 已有钩子。
