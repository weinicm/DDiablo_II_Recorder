# main.py
import sys
import os
import traceback
from pathlib import Path

# 🔑 核心修复：强制将当前工作目录锁定为 exe 所在目录（打包后防权限拒绝）
if getattr(sys, 'frozen', False):
    os.chdir(Path(sys.executable).parent)

# 🔧 修复Python路径：确保能正确找到 src 目录和根目录模块
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "src"))

# 🔧 Windows DLL 路径修复（防止 OpenCV/Torch 等库冲突）
if os.name == 'nt':
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    os.environ['MKL_THREADING_LAYER'] = 'GNU'
    if hasattr(os, 'add_dll_directory'):
        for p in sys.path:
            lib_path = Path(p) / "torch" / "lib"
            if lib_path.exists():
                try:
                    os.add_dll_directory(str(lib_path))
                except:
                    pass

# ✅ 新增：PyInstaller 资源路径自适应函数
def get_resource_path(relative_path: str) -> Path:
    """兼容开发环境与 PyInstaller --onefile 打包后的临时目录"""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

def apply_theme(app, theme_filename: str) -> None:
    """安全加载 QSS 主题文件"""
    theme_path = get_resource_path(f"src/ui/themes/{theme_filename}")
    if not theme_path.exists():
        print(f"⚠️ 主题文件未找到: {theme_path} (将使用默认 Fusion 样式)")
        return
    
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        print(f"✅ 主题加载成功: {theme_filename}")
    except Exception as e:
        print(f"❌ 主题加载异常: {e}")

def main():
    print("=" * 60)
    print("D2R监控工具 - 正式启动")
    print("=" * 60)

    try:
        # 1️⃣ 导入 PyQt5 基础组件
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        print("✅ PyQt5 导入成功")

        # 2️⃣ 导入核心业务模块
        from src.core.session_manager import SceneSessionManager
        from src.utils.config import load_config
        print("✅ 核心模块导入成功")

        # 3️⃣ 导入主窗口类
        from src.ui.main_window import D2ROverlay
        print("✅ 主窗口模块导入成功")

        # 4️⃣ 高DPI适配 & 应用初始化
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app = QApplication(sys.argv)
        app.setStyle("Fusion")  # 统一跨平台基础样式
        
        # # 🎨 新增：加载主题（⚠️ 请将 "your_theme.qss" 替换为你的实际文件名）
        # apply_theme(app, "your_theme.qss")
        
        print("✅ QApplication 创建成功")

        # 5️⃣ 加载配置 & 初始化会话管理器
        config = load_config()
        session_mgr = SceneSessionManager()
        print(f"✅ 会话管理器初始化成功 | 配置加载: {config.get('session', 'Default')}")

        # 6️⃣ 创建并显示主窗口
        overlay = D2ROverlay(session_manager=session_mgr)
        overlay.show()
        
        # 🔑 核心修复：强制置顶并激活窗口
        overlay.raise_()
        overlay.activateWindow()
        print("✅ 主窗口已显示并置顶")

        # 7️⃣ 启动主事件循环
        print("🚀 应用程序启动完成，进入主循环...")
        sys.exit(app.exec_())

    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("💡 提示：请确保已安装依赖 `pip install PyQt5 keyboard`")
        print("💡 检查 main_window.py 路径是否与 import 语句一致")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        traceback.print_exc()
        input("按回车键退出...")

if __name__ == "__main__":
    main()