import os
import shutil
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QLineEdit, 
                             QSlider, QFileDialog, QMessageBox, QSizePolicy,
                             QGridLayout, QSpacerItem)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator

class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.themes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
        os.makedirs(self.themes_dir, exist_ok=True)
        self._init_ui()
        self._load_available_themes()

    def _init_ui(self):
        # 主布局：严格顶部左对齐
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # ================= 返回按钮 =================
        self.btn_back = QPushButton("← 返回")
        self.btn_back.setObjectName("btn_back")  # 添加对象名以便主题应用
        self.btn_back.setFixedSize(60, 24)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_back, alignment=Qt.AlignLeft)
        layout.addSpacing(8)

        # ================= 会话管理 =================
        lbl_session = QLabel("会话管理")
        lbl_session.setObjectName("settings_label")  # 添加对象名以便主题应用
        layout.addWidget(lbl_session, alignment=Qt.AlignLeft)
        layout.addSpacing(4)

        # 会话选择行
        h_session_row = QHBoxLayout()
        h_session_row.setContentsMargins(0, 0, 0, 0)
        h_session_row.setSpacing(8)
        h_session_row.setAlignment(Qt.AlignLeft)
        
        self.cmb_session = QComboBox()
        self.cmb_session.setObjectName("settings_combo")  # 添加对象名以便主题应用
        self.cmb_session.setFixedSize(120, 28)
        
        self.btn_del = QPushButton("🗑️ 删除")
        self.btn_del.setObjectName("btn_del")  # 添加对象名以便主题应用
        self.btn_del.setFixedSize(60, 28)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        
        h_session_row.addWidget(self.cmb_session)
        h_session_row.addWidget(self.btn_del)
        layout.addLayout(h_session_row)

        # 新会话名称行
        h_new_session_row = QHBoxLayout()
        h_new_session_row.setContentsMargins(0, 0, 0, 0)
        h_new_session_row.setSpacing(8)
        h_new_session_row.setAlignment(Qt.AlignLeft)
        
        self.edit_new = QLineEdit()
        self.edit_new.setObjectName("settings_input")  # 添加对象名以便主题应用
        self.edit_new.setPlaceholderText("新会话名称")
        self.edit_new.setFixedSize(120, 28)
        
        self.btn_add = QPushButton("➕ 添加")
        self.btn_add.setObjectName("btn_add")  # 添加对象名以便主题应用
        self.btn_add.setFixedSize(60, 28)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        
        h_new_session_row.addWidget(self.edit_new)
        h_new_session_row.addWidget(self.btn_add)
        layout.addLayout(h_new_session_row)
        layout.addSpacing(12)

        # ================= 主题设置 =================
        lbl_theme = QLabel("主题设置")
        lbl_theme.setObjectName("settings_label")  # 添加对象名以便主题应用
        layout.addWidget(lbl_theme, alignment=Qt.AlignLeft)
        layout.addSpacing(4)

        # 主题选择行
        h_theme_row = QHBoxLayout()
        h_theme_row.setContentsMargins(0, 0, 0, 0)
        h_theme_row.setSpacing(8)
        h_theme_row.setAlignment(Qt.AlignLeft)
        
        lbl_cur = QLabel("当前:")
        lbl_cur.setFixedSize(40, 24)
        
        self.cmb_theme = QComboBox()
        self.cmb_theme.setObjectName("settings_combo")  # 添加对象名以便主题应用
        self.cmb_theme.setFixedSize(140, 28)
        self.cmb_theme.currentTextChanged.connect(self._on_theme_changed)
        
        self.btn_import_theme = QPushButton("📂 导入")
        self.btn_import_theme.setObjectName("btn_import_theme")  # 添加对象名以便主题应用
        self.btn_import_theme.setFixedSize(60, 28)
        self.btn_import_theme.setCursor(Qt.PointingHandCursor)
        self.btn_import_theme.clicked.connect(self._import_custom_theme)
        
        h_theme_row.addWidget(lbl_cur)
        h_theme_row.addWidget(self.cmb_theme)
        h_theme_row.addWidget(self.btn_import_theme)
        layout.addLayout(h_theme_row)
        layout.addSpacing(12)

        # ================= 过滤设置 =================
        lbl_filter = QLabel("过滤设置 (0=不过滤)")
        lbl_filter.setObjectName("settings_label")
        layout.addWidget(lbl_filter, alignment=Qt.AlignLeft)
        layout.addSpacing(4)

        # 等待时间大于行
        h_wait_greater_row = QHBoxLayout()
        h_wait_greater_row.setContentsMargins(0, 0, 0, 0)
        h_wait_greater_row.setSpacing(8)
        h_wait_greater_row.setAlignment(Qt.AlignLeft)

        lbl_wait_greater = QLabel("等待时间大于")
        lbl_wait_greater.setFixedSize(80, 24)

        self.spin_wait_max = QLineEdit()
        self.spin_wait_max.setObjectName("settings_input")
        self.spin_wait_max.setFixedSize(60, 28)
        self.spin_wait_max.setAlignment(Qt.AlignCenter)
        self.spin_wait_max.setValidator(QIntValidator(0, 0))
        self.spin_wait_max.setPlaceholderText("0")

        lbl_sec1 = QLabel("秒不计算")
        lbl_sec1.setFixedSize(50, 24)

        h_wait_greater_row.addWidget(lbl_wait_greater)
        h_wait_greater_row.addWidget(self.spin_wait_max)
        h_wait_greater_row.addWidget(lbl_sec1)
        layout.addLayout(h_wait_greater_row)

        # 局内时间少于行
        h_ig_less_row = QHBoxLayout()
        h_ig_less_row.setContentsMargins(0, 0, 0, 0)
        h_ig_less_row.setSpacing(8)
        h_ig_less_row.setAlignment(Qt.AlignLeft)

        lbl_ig_less = QLabel("局内时间少于")
        lbl_ig_less.setFixedSize(80, 24)

        self.spin_ig_min = QLineEdit()
        self.spin_ig_min.setObjectName("settings_input")
        self.spin_ig_min.setFixedSize(60, 28)
        self.spin_ig_min.setAlignment(Qt.AlignCenter)
        self.spin_ig_min.setValidator(QIntValidator(0, 0))
        self.spin_ig_min.setPlaceholderText("0")

        lbl_sec2 = QLabel("秒不计算")
        lbl_sec2.setFixedSize(50, 24)

        h_ig_less_row.addWidget(lbl_ig_less)
        h_ig_less_row.addWidget(self.spin_ig_min)
        h_ig_less_row.addWidget(lbl_sec2)
        layout.addLayout(h_ig_less_row)

        # 局内时间大于行
        h_ig_greater_row = QHBoxLayout()
        h_ig_greater_row.setContentsMargins(0, 0, 0, 0)
        h_ig_greater_row.setSpacing(8)
        h_ig_greater_row.setAlignment(Qt.AlignLeft)

        lbl_ig_greater = QLabel("局内时间大于")
        lbl_ig_greater.setFixedSize(80, 24)

        self.spin_ig_max = QLineEdit()
        self.spin_ig_max.setObjectName("settings_input")
        self.spin_ig_max.setFixedSize(60, 28)
        self.spin_ig_max.setAlignment(Qt.AlignCenter)
        self.spin_ig_max.setValidator(QIntValidator(0, 0))
        self.spin_ig_max.setPlaceholderText("0")

        lbl_sec3 = QLabel("秒不计算")
        lbl_sec3.setFixedSize(50, 24)

        h_ig_greater_row.addWidget(lbl_ig_greater)
        h_ig_greater_row.addWidget(self.spin_ig_max)
        h_ig_greater_row.addWidget(lbl_sec3)
        layout.addLayout(h_ig_greater_row)
        layout.addSpacing(12)

        # ================= 透明度 =================
        h_opacity_row = QHBoxLayout()
        h_opacity_row.setContentsMargins(0, 0, 0, 0)
        h_opacity_row.setSpacing(8)
        h_opacity_row.setAlignment(Qt.AlignLeft)
        
        lbl_opa = QLabel("透明度:")
        lbl_opa.setObjectName("settings_label")  # 添加对象名以便主题应用
        lbl_opa.setFixedSize(50, 24)
        
        self.slider_opa = QSlider(Qt.Horizontal)
        self.slider_opa.setObjectName("settings_slider")  # 添加对象名以便主题应用
        self.slider_opa.setRange(20, 100)
        self.slider_opa.setValue(85)
        self.slider_opa.setFixedSize(150, 20)
        
        h_opacity_row.addWidget(lbl_opa)
        h_opacity_row.addWidget(self.slider_opa)
        layout.addLayout(h_opacity_row)

        # 底部占位，确保所有控件都在顶部左对齐
        layout.addStretch()

    def _load_available_themes(self):
        self.cmb_theme.clear()
        if not os.path.isdir(self.themes_dir): 
            return
        for fname in sorted(os.listdir(self.themes_dir)):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self.themes_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    display_name = data.get("name", fname.replace(".json", ""))
                    self.cmb_theme.addItem(display_name, fname.replace(".json", ""))
                except:
                    self.cmb_theme.addItem(fname.replace(".json", ""), fname.replace(".json", ""))

    def _on_theme_changed(self, theme_name: str):
        if theme_name:
            idx = self.cmb_theme.currentIndex()
            theme_file_name = self.cmb_theme.itemData(idx)
            if theme_file_name:
                self.theme_changed.emit(theme_file_name)

    def _import_custom_theme(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择主题文件", "", "JSON 主题文件 (*.json)")
        if not file_path: 
            return
        theme_name = os.path.splitext(os.path.basename(file_path))[0]
        dest_path = os.path.join(self.themes_dir, f"{theme_name}.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json.load(f)
            shutil.copy(file_path, dest_path)
            self._load_available_themes()
            idx = self.cmb_theme.findData(theme_name)
            if idx >= 0: 
                self.cmb_theme.setCurrentIndex(idx)
            QMessageBox.information(self, "成功", f"主题 '{theme_name}' 已导入！")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "导入失败", "文件格式错误：不是有效的 JSON 文件。")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
