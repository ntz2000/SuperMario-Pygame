# Super Plumbros 🍄

NSMB（《新超级马里奥兄弟》）风格的横版平台跳跃游戏，纯 Python + pygame-ce，
**所有美术与音效均由代码程序化生成**（零外部资源文件）。

## 运行

```bash
python3.12 main.py            # 1280×720 窗口，4 倍最近邻放大
python3.12 main.py --scale 6  # 更大的窗口
```

> 需要 pygame-ce、numpy、Pillow（资源光栅化用）。无显示环境自动 headless。

## 操作

| 键 | 动作 |
|---|---|
| ← → / A D | 移动 |
| Shift / Z | 跑 |
| Space / K | 跳（按住跳更高；贴墙=墙跳） |
| X / J | 旋转跳（空中） |
| C / V | 动作：拿/扔龟壳、火形态扔火球 |
| ↓ / S | 蹲；空中 ↓+跳=下砸；站管口=进管道 |
| Enter | 暂停 |
| Esc | 暂停菜单 |

## 玩法

- **世界 1**：草原 1-1（藏着个秘密管道！）、地下 1-2、水关 1-3、城堡 Boss。
- 每关 **3 枚大金币**，藏在刁钻的位置（隐藏房、墙跳井、Boss 头顶）。
- 形态：小 → 大（蘑菇）→ 火（火花扔火球）；迷你蘑菇轻快跳得高；
  巨大蘑菇 8 秒无敌拆迁模式。
- 龟壳可以搬起来砸敌人；踩踏不落地连击 100→8000→1UP。
- 100 枚金币 = 1UP；中途小旗是检查点；超时也会死。

## 开发

```bash
python3.12 -m pytest tests/ -q      # 80 个测试
python3.12 main.py --headless --bot --level 1-1   # Bot 自动玩（smoke）
python3.12 main.py --headless --frames 300 --capture shot.png  # 截图
```

架构与交接文档见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，
玩法对照表见 [docs/GAMEPLAY.md](docs/GAMEPLAY.md)，
进度记录见 [docs/PROGRESS.md](docs/PROGRESS.md)。
