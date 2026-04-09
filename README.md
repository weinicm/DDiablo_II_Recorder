# 🎮 暗黑小记｜DDiablo_II_Recorder

> 🌟 每一个场景，都有你的足迹。让小记，帮你记住每一刻高光！

![GitHub License](https://img.shields.io/github/license/weinicm/DDiablo_II_Recorder?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![ONNX](https://img.shields.io/badge/Inference-ONNX_Runtime-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-🧪_Beta-orange?style=flat-square)

---

## ✨ 这是什么？

**暗黑小记** 是一款专为《暗黑破坏神 2：重制版》打造的智能场景记录工具 🎯  
它采用 YOLO 视觉模型自动识别游戏场景，无需手动截图，无需担心分辨率切换，轻松记录你的每一局冒险！

> 💡 灵感来源：玩得太投入，回头发现「刚才那局打了多久来着？」→ 小记帮你记！

## 🚀 核心特性

| 特性 | 说明 | 效果 |
|------|------|------|
| 🤖 **智能识别** | 基于 YOLOv8 分类模型 + ONNX 推理，自动判断当前场景 | 无需手动操作，识别快、准、稳 |
| 📁 **会话分类** | 支持多场景独立记录（牛场 / 崔凡克 / Bug 超市...） | 切换会话，数据自动隔离，统计更清晰 |
| 🎚️ **智能过滤** | 可设置等待时间 / 游戏时长阈值，自动过滤异常对局 | 防止「挂机半小时」污染统计数据 |
| ⏸️ **最小化暂停** | 游戏最小化自动暂停计时，恢复后无缝续计 | 切屏回消息？不怕，计时不丢！ |
| 📸 **战利品截图** | 一键截图 + 自动添加对局信息水印（可选） | 出货瞬间，轻松记录 + 分享 |

---

## 🎯 快速开始

### 1️⃣ 下载
- 前往 [Releases](https://github.com/weinicm/DDiablo_II_Recorder/releases) 下载最新版
- 或加入 QQ 群 **1087174701**，群文件获取最新安装包 + 使用指南
- 百度网盘 

### 2️⃣ 运行
```bash
# 双击 exe 即可！无需安装 Python，无需配置环境
# 首次运行会在同级目录自动生成：
#   ├── config.json      # 配置文件（可自定义）
#   ├── data/sessions/   # 会话记录
#   └── Loot/            # 截图保存目录

{
  "session": "默认场景",
  "filters": {
    "wait_min": 0,      // 等待最短时间（秒），0=不限制
    "wait_max": 0,      // 等待最长时间（秒），0=不限制
    "ig_min": 0,        // 游戏内最短时间（秒），0=不限制
    "ig_max": 0         // 游戏内最长时间（秒），0=不限制
  },
  "opacity": 85,        // 界面透明度（10~100）
  "shortcuts": {
    "lock_unlock": "Ctrl+Shift+L",      // 锁定/解锁界面
    "capture_screenshot": "Ctrl+Shift+C" // 手动截图
  }
}


#### 🔹 第 3 块：开发者 + 许可证 + 页脚
```markdown
## 🛠️ 开发者看这里

### 环境准备
```bash
# 1. 克隆仓库
git clone https://github.com/weinicm/DDiablo_II_Recorder.git
cd DDiablo_II_Recorder

# 2. 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows
# 3. 安装依赖
pip install --upgrade pip setuptools wheel
pip install onnxruntime==1.18.0          # ONNX 推理
pip install numpy==1.26.4                # 数组计算
pip install dxcam==0.3.0                 # 屏幕截图
pip install keyboard==0.13.5             # 键盘监听
pip install pywin32==306                 # Windows API 封装
pip install PyQt5==5.15.10               # GUI 界面
pip install mss==9.0.1                   # 备用截图方案
pip install Pillow==10.3.0               # 图像处理（替代 opencv）
pip install requests==2.31.0             # 网络请求（如果需要）
pip install PyYAML==6.0.1                # 配置文件解析
pip install filelock==3.14.0             # 文件锁
pip install typing_extensions==4.12.2    # 类型扩展
pip install psutil
pip install opencv-python==4.9.0.80
pip install ultralytics==8.2.34 --no-deps

当前使用 best.onnx（YOLOv8n-cls 导出，2.8MB）
训练数据有限，仅支持基础场景分类（dating / in_game / login）
未来计划：支持崔凡克 / 牛场 / 超市等细分场景识别 🎯

📜 非商业使用许可证｜Non-Commercial License

✅ 你可以：
   • 自由查看、修改、学习本代码
   • 个人使用、分享给朋友
   • 提交改进建议或代码

❌ 你不可以：
   • 将本软件用于任何商业目的
   • 销售、出租、许可本软件或其衍生作品
   • 将本软件集成至付费产品 / SaaS 服务中

📧 商业合作请联系：weinicm@gmail.com