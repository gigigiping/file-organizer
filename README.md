# 文件整理工具 file-organizer

一个用 Python 写的命令行小工具：把「下载」文件夹里堆成山的文件，按类型自动归类到对应子文件夹里，顺手还能查重、清空目录，并且**支持一键撤销**。

> 只依赖 Python 标准库，不需要 `pip install` 任何东西。

## 为什么写这个

每次下载完资料，下载文件夹就变成这样：

```
Downloads/
├── 实验报告.docx
├── 分析化学笔记.pdf
├── 检测数据.xlsx
├── 屏幕截图_01.png
├── 安装包.exe
├── 录音.m4a
├── 论文(1).pdf
├── 论文(1) - 副本.pdf
└── ... 还有 60 多个文件
```

手动一张张拖进文件夹，几十个文件要拖十几分钟，还容易拖错、拖漏。这个脚本把这件事压到一条命令。

跑完之后：

```
Downloads/
├── 文档/      ← docx / pdf / xlsx / pptx / txt / md ...
├── 图片/      ← jpg / png / gif / webp / heic ...
├── 视频/      ← mp4 / mov / mkv ...
├── 音频/      ← mp3 / wav / m4a / flac ...
├── 压缩包/    ← zip / rar / 7z / tar.gz ...
├── 安装包/    ← exe / msi / dmg / apk ...
├── 代码/      ← py / js / html / json / ipynb ...
└── 其他/      ← 识别不了的类型
```

## 功能

| 功能 | 参数 | 说明 |
|---|---|---|
| 按类型归档 | 默认行为 | 按扩展名把文件移进 7 大分类文件夹 |
| 预览模式 | `--dry-run` | 只打印「准备做什么」，一个文件都不动 |
| 重复文件检测 | `--duplicates` | 先比大小、再比 SHA-256，找出内容完全相同的文件 |
| 清理空文件夹 | `--clean-empty` | 整理完顺手删掉空目录 |
| 一键撤销 | `--undo <日志>` | 按日志把文件全部还原回原位 |

### 几个设计上的取舍

- **绝不覆盖同名文件**：目标目录已有同名文件时，自动加 `(1)`、`(2)` 后缀，不会悄悄覆盖你原来的资料
- **只处理第一层**：默认只整理目标文件夹里的散落文件，不会递归进子文件夹乱搬东西
- **先预览再动手**：`--dry-run` 把所有操作先打印一遍，确认没问题再正式执行
- **每一步都有记录**：正式执行会生成 `organize_时间戳_log.json`，随时能 `--undo` 回退
- **查重用哈希**：不做「文件名相同就算重复」这种粗暴判断，而是比对内容哈希，同内容改名也能揪出来

## 环境要求

- Python 3.8 及以上（Windows / macOS / Linux 都可以）
- 无第三方依赖

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/gigigiping/file-organizer.git
cd file-organizer
```

```bash
# 2. 先预览，看看会怎么整理（强烈建议第一步就跑这个）
python organize.py "C:\Users\你的用户名\Downloads" --dry-run

# 3. 确认没问题，正式整理（不写路径则默认整理「下载」目录）
python organize.py

# 4. 整理并顺手清理空文件夹
python organize.py --clean-empty

# 5. 只查重复文件
python organize.py --duplicates

# 6. 后悔了，按日志全部还原
python organize.py --undo "organize_20261119_220000_log.json"
```

### 参数说明

```
usage: organize.py [路径] [--dry-run] [--duplicates] [--clean-empty] [--undo LOG]

路径              要整理的文件夹，默认是系统的「下载」目录
--dry-run         预览模式，只打印不执行
--duplicates      只做重复文件检测，重复文件移入 _重复文件/
--clean-empty     整理完成后清理空文件夹
--undo LOG        撤销，传入之前生成的日志文件路径
```

## 运行示例

```text
$ python organize.py D:\test --dry-run
目标目录：D:\test
当前为预览模式，不会移动任何文件。

[预览] 实验报告.docx  ->  文档
[预览] 检测数据.xlsx  ->  文档
[预览] 屏幕截图.png  ->  图片
[预览] 录音.m4a  ->  音频
预览完成：共 4 个文件待整理，未做任何改动。
```

```text
$ python organize.py D:\test
目标目录：D:\test
[移动] 实验报告.docx  ->  文档/实验报告.docx
[移动] 检测数据.xlsx  ->  文档/检测数据.xlsx
[移动] 屏幕截图.png  ->  图片/屏幕截图.png
[移动] 录音.m4a  ->  音频/录音.m4a
整理完成：共移动 4 个文件。
操作日志已保存：D:\test\organize_20261119_220315_log.json
如需回退，执行：python organize.py --undo <日志文件>
```

```text
$ python organize.py D:\test --duplicates
目标目录：D:\test
发现 1 组重复文件。
保留：文档/实验报告.docx
   重复：下载/实验报告 - 副本.docx
```

## 项目结构

```
file-organizer/
├── organize.py     # 全部逻辑：分类、查重、清空目录、撤销、命令行解析
├── README.md
├── LICENSE         # MIT
└── .gitignore
```

`organize.py` 内部按职责拆成三层：

1. **工具函数**：`classify()` 判类型、`unique_target()` 防覆盖、`file_hash()` 算哈希
2. **核心功能**：`organize()` / `find_duplicates()` / `clean_empty_dirs()` / `undo()`
3. **命令行入口**：`build_parser()` + `main()`

## 注意事项

- 第一次在大目录上跑，**一定先加 `--dry-run`**
- 脚本只移动文件、不会删除文件内容；删除的只有空文件夹
- 隐藏文件（以 `.` 开头）会被跳过，避免动到系统文件
- 整理日志本身就是这个工具产生的，会被跳过，不会自己整理自己

## 后续计划

- [ ] 支持 `config.json` 自定义分类规则和目录名
- [ ] 支持按文件修改时间分年/月归档
- [ ] 加一个 `--watch` 模式，定时自动整理
- [ ] 打包成单文件 exe，不装 Python 也能用

## License

MIT © 2026 孙鑫
