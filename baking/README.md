# 烘焙工具链

把 thcrap 汉化补丁的贴图/对话/音乐素材按移植语义直接烘进 th15.dat 供 web 端单文件加载

## 文件

| 文件 | 用途 |
|---|---|
| bake_all.py | 全量烘焙主脚本 THA1 重打包 ANM 贴图替换 MSG 对话 音乐 |
| tha1.py | THA1 归档解包器 XOR + LZSS |
| run-lz.mjs | LZSS 压缩 node 版供 python 子进程调用 |
| logo-slot-chars-600.png | 标题 logo 槽位的字区合成素材 白卡区已透明 |
| th15_full.dat | 烘焙产物 站点 packages/th15/th15.data 的 th15.dat 段来源 |

## 依赖与路径

bake_all.py 顶部常量为本机绝对路径 部署到新机器需要改：

- SRC 源 dat = MOD 整合包的原版 th15.dat
- DST 输出路径
- PATCH thcrap 补丁目录 lang_zh-hans/th15 含贴图与 jdiff
- RUN_LZ run-lz.mjs 路径

另需 python 3 带 numpy pillow 与 node 20+

## 环境变量

- BAKE_NO_TEX=1 跳过贴图替换
- BAKE_NO_MSG=1 跳过对话替换
- BAKE_LOGO_MODE=chars 默认 logo 字区方案 其余值 transparent/mod/calibrated 为调试用

## 输出对接

烘焙完成后把 th15_full.dat 拷到 th15_web 构建输入的 dat 路径再跑 th15_web/scripts/package-release.mjs 生成站点 packages/th15/th15.data
