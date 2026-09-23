# 素材与渲染管线（本轮升级记录）

> 2026-09-23：高清渲染管线 + 真实 NSMB 瓦片素材集成。

## 渲染管线：逻辑分辨率 × RES_SCALE

**核心思想：模拟不变，渲染高清。** 物理与碰撞继续跑在 320×180 艺术像素网格上
（16px 瓦片、60Hz），但渲染缓冲是 `base × RES_SCALE`（默认 2 = 640×360），
窗口再整数放大。精灵在生成时就直接输出高清分辨率（`Canvas.finish(out_scale)`）。

- [engine/res.py](../mario/engine/res.py)：`RES_SCALE = 2`（改成 1 即回到像素风）
- [engine/camera.py](../mario/engine/camera.py)：`to_screen` 含倍率换算
- [core/tilemap.py](../mario/core/tilemap.py)：瓦片条带按高清网格光栅化
- [engine/scene.py](../mario/engine/scene.py)：像素风场景（标题/地图/菜单）自动
  画进 base 离屏再放大；`LevelScene.native = True` 直绘高清
- 磁盘缓存指纹含 RES_SCALE——改倍率后缓存自动重建

性能实测：空闲帧 0.6ms、顶砖帧 0.6ms（预算 16.6ms）。

## 真实 NSMB 素材（程序化回退）

素材目录 `mario/assets/`：
- `atlas.json`——id → 精灵图裁剪矩形（语义由颜色签名锁定，见下）
- `atlas.py`——图集加载器（sheet 缓存 + 裁剪 + 最近邻放大）
- `sheets/`——下载的官方 rip（NSMB DS，来源 The Spriters Resource 经 Wayback Machine）

**加载优先级**：`Assets.sprite()` 先查 atlas（命中→裁剪真实贴图），
未命中→程序化生成器。两条路径共用同一套 asset id，关卡/actor 代码零改动。

已接入真实素材（草原主题）：
| asset id | 来源 | 语义 |
|---|---|---|
| `tile/ow-ground.top/fill/cap` | 0 Grassland [1,7]/[4,8]/[2,13] | 草帽黄土地面 |
| `tile/ow-rock.*` | Jyotyu 行 5 灰石 | 楼梯/岩块 |
| `tile/question.*` | Jyotyu [12,0] | 问号块（2 帧微动） |
| `tile/brick.*` | Jyotyu [5,0] | 砖块 |
| `tile/used.*` | Jyotyu [3,2] | 用过的块 |
| `tile/coin_block.*` | Jyotyu [15,0] | 多币块 |
| `tile/metal.*` | Jyotyu 行 2 灰绿 | 金属块 |

## Mario 姿势表映射（V3 完成，语义由 TSR 2017 年评论 + IoU 闭环分析锁定）

**关键事实**（TSR sheet 31487 评论区 + 像素分析）：这张 436 帧表**全部是超级马里奥**
（没有 fire/mini/mega 独立帧）；fire/ice 用调色板交换实现（`atlas.py remap_frame`，
与 NSMB 原版做法一致）。行带语义：

| 行带 | y 范围 | 语义 | 接入 id |
|---|---|---|---|
| 0 | 10-43 | idle 呼吸循环（79 帧） | hero.super.idle（6 帧） |
| 1 | 50-84 | walk 直立行走（前 25 帧平滑段） | hero.super.walk（8 帧） |
| 2 | 89-129 | 姿势混合（帧 2-7 = skid 急刹） | hero.super.skid |
| 3 | 131-172 | jump（帧 0-17，高 41 手臂高举）+ duck（28-59） | hero.super.jump / fall / crawl |
| 4 | 180-216 | run 奔跑循环（71 帧闭环） | hero.super.run（8 帧） |
| 6 | 357-397 | 朝右姿势行（swim 候选） | hero.super.swim |
| 7-9 | — | 场景物件混入（管道/门，非马里奥） | 不用 |

hero.small/mini/mega 保持程序化生成（表里没有对应帧——33px = Super Mario，
与 mariowiki MariostandingNSMB.png 16x33 吻合；Small 是 15x21）。
`hero.fire.*/hero.ice.*` 由 `hero.super.*` 自动调色派生（原版 NSMBDS 的
PowerupState: Small=0/Super=1/Fire=2/Mega=3/Mini=4/Shell=5，Fire 就是 Super
换白贴图，无独立动画——反编译 PlayerBase.hpp 证实）。

## 原版动画名表（NSMBDS ROM 提取，来自 MvsL 重制版 FBX）

游戏内动画的**原始命名与精确帧数**（任天堂 EAD 日式英语缩写，同人起不出这种名），
映射 TSR 表时对帧数的黄金参照：

| 动画名 | 帧数 | 语义 | 游戏内 ID |
|---|---|---|---|
| wait | 62 | 站立呼吸 | 0 |
| walk | 25 | 行走 | 1 |
| run | 25 | 奔跑 | — |
| b_dash / b_dash2 | 24 | 刹车急停 | — |
| jump / jumped | 5 / 4 | 跳 / 下落 | 5 / 6 |
| 2jump1/2jumped | 5/14 | 二段跳 | — |
| roll_jump | 14 | 三段跳翻滚 | — |
| spin_jump | 2 | 旋转跳 | — |
| wsld | 1 | 贴墙侧移 | — |
| swim / swim_walk | 6 / 24 | 游泳 | — |
| paddle_1/paddle_2 | 8/7 | 划水 | — |
| stoop / low_walk | 2 / 23 | 蹲 / 蹲行 | — |
| fire_at | 6 | 投掷火球 | — |
| carry_throw | 11 | 投掷携带物 | — |
| shell_walk | 24 | 龟壳形态走 | — |
| dead / dead_pose | 65 / 10 | 死亡 | — |
| goal_puton_cap | 51 | 通关戴帽 | 99=win |
| scale_up | 38 | 变身放大 | — |

（Newer-Team hack 代码证实的 ID：0=idle、1=walk、5=jump、6=fall、
105/106=路易吉专属跳/落、141=旗杆、17=矿车、18=挥锤）

**walk 验证修正**（V4.1）：agent 逐帧渲染确认 walk 实际段在 x652-1142
（帧 #25-#42，宽 17-26 呈迈腿循环），V3 误用了 x8-549 段（转身/伸手杂项）。

## 敌人真实帧（V3 完成）

- `enemy/goomba`：GIF 逐列 8 帧 walk（17x18，等距同尺寸=动画序列，语义确定）
- `enemy/koopa` / `enemy/red_koopa`：前 12 帧 walk（30px）+ 绿色小帧段=龟壳
- `enemy/shell` / `enemy/shell_red`：3 帧

## 已下载未映射（后续 agent 可扩展）：
- `nsmbds_spiny.png`（509x302）——刺龟，语义同 koopa（逐列动画）
- `nsmbds_tiles_grassland.png`（2566×2053）——草原全量瓦片（含背景装饰）
- `tilesets_extract/` 雪原/火山/丛林主题尚未接入 atlas

## V4 新增
- `item/bigcoin`：nsmbds_starcoin.png y218-243 行带 27 帧取 8 帧旋转
- `tile/ug-*/castle-*/water-*`：三主题 ground+rock 全 6 变体
  （地下亮灰砖 [10,1]/[12,2]、城堡紫灰 [2,0]/[0,8] 石头 [2,7]/[4,8]、
  水下岩层 [13,0]/[2,1]）

## 素材下载方法（复现）

Wayback Machine 对 TSR 页面开放但 CDN 403，老路径 `resources/sheets/` 有存档：

1. 游戏页快照：`https://web.archive.org/web/2018/https://www.spriters-resource.com/ds_dsi/newsupermariobros/`
   → 提取 `sheet/<id>/` 列表与标题
2. sheet 页快照（任一年份）→ 提取 `resources/sheets/<桶>/<id>.png`
3. CDX 查图片快照：`https://web.archive.org/cdx/search/cdx?url=spriters-resource.com/resources/sheets/<桶>/<id>.png`
4. 下载最大快照：`https://web.archive.org/web/<ts>id_/<原 URL>`
   （或 `/download/<id>/` 端点的快照——有时返回 zip，如 tilesets_multi）

注意：archive.org 偶发 522/离线，脚本需重试（参考 /tmp/fetch_sheets.py 的模式）。

## 版权说明

下载的 NSMB rip 为任天堂版权素材，仅本地个人学习使用（fan project），不随项目分发。
程序化生成路径（mario/art/）无版权问题，可作为发布版唯一素材来源（删掉
mario/assets/ 目录即回退）。
