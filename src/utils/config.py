import json
import os
import sys
from pathlib import Path

# 🔑 核心修复：动态解析路径。打包后指向 exe 同级目录，开发环境保持相对路径
# 模块级常量必须在导入时立即计算，避免受 os.chdir() 执行时机影响
if getattr(sys, 'frozen', False):
    CONFIG_FILE = Path(sys.executable).parent / "config.json"
else:
    CONFIG_FILE = Path("config.json")

DEFAULT_CONFIG = {
    "session": "崔凡克",
    "filters": {"wait_min": 0, "wait_max": 0, "ig_min": 0, "ig_max": 0},
    "opacity": 85,
    "sessions": ["崔凡克", "牛场", "bug超市","巴尔"],
    "shortcuts": {
        "lock_unlock": "Ctrl+Shift+L",
        "capture_screenshot": "Ctrl+Shift+C"
    }
}

def load_config() -> dict:
    """加载配置文件，如果不存在则创建默认配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                # 确保所有必需的字段都存在
                cfg.setdefault("sessions", DEFAULT_CONFIG["sessions"])
                cfg.setdefault("shortcuts", DEFAULT_CONFIG["shortcuts"])
                return cfg
        except Exception as e:
            print(f"[警告] 配置加载失败: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        # 如果配置文件不存在，创建默认配置
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

def save_config(data: dict):
    """保存配置到文件"""
    try:
        # 如果文件已存在，先加载现有配置
        existing_config = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            except:
                pass
        
        # 合并配置：新数据覆盖现有数据，但保留不在新数据中的原有字段
        merged_config = existing_config.copy()  # 从现有配置开始
        merged_config.update(data)  # 用新数据更新
        
        # 确保必要的字段存在
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in merged_config:
                merged_config[key] = default_value
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged_config, f, ensure_ascii=False, indent=2)
            
        print(f"[Config] ✅ 配置已保存")
    except Exception as e:
        print(f"[Config] ❌ 配置保存失败: {e}")

def get_shortcut(action: str) -> str:
    """获取指定动作的快捷键"""
    config = load_config()
    shortcuts = config.get("shortcuts", DEFAULT_CONFIG["shortcuts"])
    return shortcuts.get(action, "")

def get_all_shortcuts() -> dict:
    """获取所有快捷键配置"""
    config = load_config()
    return config.get("shortcuts", DEFAULT_CONFIG["shortcuts"]).copy()