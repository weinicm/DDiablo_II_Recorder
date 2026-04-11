from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen

from src.ui.components.delete_icon import DeleteIconLabel
from src.core.session_manager import SceneSessionManager

class MonitorPage(QWidget):
    # 添加一个信号，用于通知主窗口开始监控
    start_requested = pyqtSignal()
    
    def __init__(self, session_manager: SceneSessionManager = None, parent=None):
        super().__init__(parent)
        self.session_manager = session_manager
        self.is_running = False  # 监控状态
        self._init_ui()
        if self.session_manager:
            print("[MonitorPage] 初始化加载历史数据...")
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        
        # 会话选择
        h_sess = QHBoxLayout()
        h_sess.addWidget(QLabel("会话:"))
        self.cmb_session = QComboBox()
        self.cmb_session.setObjectName("cmb_session")
        h_sess.addWidget(self.cmb_session)
        layout.addLayout(h_sess)
        layout.addStretch()
        
        # 运行次数和时长显示
        runs_container = QWidget()
        runs_layout = QHBoxLayout(runs_container)
        runs_layout.setContentsMargins(0, 0, 0, 0)
        runs_layout.setSpacing(12)
        
        runs_layout.addStretch()  # 左弹簧：强制整体水平居中
        
        self.lbl_big_runs = QLabel("0")
        self.lbl_big_runs.setObjectName("lbl_big_runs")
        runs_layout.addWidget(self.lbl_big_runs)
        
        self.lbl_big_duration = QLabel("时长: 0 分钟")
        self.lbl_big_duration.setObjectName("lbl_big_duration")
        runs_layout.addWidget(self.lbl_big_duration)
        
        runs_layout.addStretch()  # 右弹簧：强制整体水平居中
        
        layout.addWidget(runs_container, alignment=Qt.AlignCenter)
        
        # 状态标签
        self.lbl_status = QLabel("状态: 待机")
        self.lbl_status.setObjectName("lbl_status")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)
        layout.addStretch()
        
        # 历史统计
        self.lbl_hist = QLabel("历史: 0局 | 总时长: 0.0s")
        self.lbl_hist.setObjectName("lbl_hist")
        self.lbl_hist.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_hist)
        
        # 最近5局面板
        panel = QFrame()
        panel.setObjectName("recent_panel")
        panel.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.panel_layout = QVBoxLayout(panel)
        self.panel_layout.setSpacing(6)
        
        h_title = QHBoxLayout()
        self.lbl_recent_title = QLabel("最近5局")
        self.lbl_recent_title.setObjectName("lbl_recent_title")
        h_title.addWidget(self.lbl_recent_title)
        h_title.addStretch()
        self.lbl_recent_avg = QLabel("平均时长: 0.0s")
        self.lbl_recent_avg.setObjectName("lbl_recent_avg")
        h_title.addWidget(self.lbl_recent_avg)
        self.panel_layout.addLayout(h_title)
        
        # 最近5局的时间标签和删除按钮
        self.row_widgets, self.time_labels, self.delete_labels = [], [], []
        for i in range(5):
            row_widget = QWidget()
            row_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            row_widget.setFixedHeight(34)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(8)
            
            l_time = QLabel("--")
            l_time.setObjectName("row_time_label")
            l_time.setAlignment(Qt.AlignRight)
            
            btn_del = DeleteIconLabel()
            print(f"[MonitorPage] 🔗 Row {i} 信号绑定 -> _on_delete_clicked")
            btn_del.clicked.connect(self._on_delete_clicked)
            
            row_layout.addStretch()  # 左侧弹簧
            row_layout.addWidget(l_time, 0, Qt.AlignCenter)  # 时间标签居中
            row_layout.addWidget(btn_del)
            row_layout.addStretch()  # 右侧弹簧
            
            self.panel_layout.addWidget(row_widget)
            self.row_widgets.append(row_widget)
            self.time_labels.append(l_time)
            self.delete_labels.append(btn_del)
        
        layout.addWidget(panel)
        
        # 创建蒙版覆盖层
        self.create_overlay()
    
    def create_overlay(self):
        """创建未运行时的蒙版覆盖层"""
        # 蒙版容器
        self.overlay = QWidget(self)
        self.overlay.setObjectName("overlay")
        
        # 蒙版布局
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        
        # 播放按钮容器
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # 播放按钮
        self.btn_start_overlay = QPushButton("▶")
        self.btn_start_overlay.setObjectName("btn_start_overlay")
        
        # 设置固定的方形尺寸，确保是圆形
        self.btn_start_overlay.setFixedSize(120, 120)
        
        # 设置工具提示
        self.btn_start_overlay.setToolTip("开始")
        
        # 设置光标
        self.btn_start_overlay.setCursor(Qt.PointingHandCursor)
        
        # 连接点击事件
        self.btn_start_overlay.clicked.connect(self._on_overlay_start_clicked)
        
        # 将按钮添加到容器中心
        button_layout.addStretch()
        button_layout.addWidget(self.btn_start_overlay, 0, Qt.AlignCenter)
        button_layout.addStretch()
        
        # 提示文字
        self.lbl_overlay_hint = QLabel("点击开始")
        self.lbl_overlay_hint.setObjectName("lbl_overlay_hint")
        self.lbl_overlay_hint.setAlignment(Qt.AlignCenter)
        self.lbl_overlay_hint.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            margin-top: 10px;
        """)
        
        # 主布局
        overlay_layout.addStretch()
        overlay_layout.addWidget(button_container, 0, Qt.AlignCenter)
        overlay_layout.addSpacing(5)
        overlay_layout.addWidget(self.lbl_overlay_hint, 0, Qt.AlignCenter)
        overlay_layout.addStretch()
        
        # 初始显示蒙版
        self.overlay.show()
    
    def _on_overlay_start_clicked(self):
        """蒙版播放按钮点击事件"""
        print("[MonitorPage] 🎯 蒙版播放按钮被点击")
        # 检查是否有会话
        if self.cmb_session.count() == 0:
            self.lbl_overlay_hint.setText("请先添加会话")
            self.lbl_overlay_hint.setStyleSheet("""
                QLabel#lbl_overlay_hint {
                    color: #FF6B6B;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            return
        
        # 检查当前会话
        current_session = self.cmb_session.currentText().strip()
        if not current_session:
            self.lbl_overlay_hint.setText("请选择会话")
            self.lbl_overlay_hint.setStyleSheet("""
                QLabel#lbl_overlay_hint {
                    color: #FF6B6B;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            return
        
        # 发射开始监控信号
        self.start_requested.emit()
    
    def set_running_state(self, is_running: bool):
        """设置监控运行状态"""
        self.is_running = is_running
        if is_running:
            # 隐藏蒙版
            self.overlay.hide()
            # 状态文本由后续的update_stats_display方法更新
        else:
            # 显示蒙版
            self.overlay.show()
            self.lbl_status.setText("状态: 已停止")
            # 重置提示文字
            self.lbl_overlay_hint.setText("点击开始")
            self.lbl_overlay_hint.setStyleSheet("""
                QLabel#lbl_overlay_hint {
                    color: #FFFFFF;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
    
    def resizeEvent(self, event):
        """调整窗口大小事件"""
        super().resizeEvent(event)
        # 调整蒙版大小
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.width(), self.height())
    
    def update_recent_rows(self, rounds_data):
        """🔄 更新最近5局显示（倒序：最新的一局显示在最上方 Row 0）"""
        print(f"[MonitorPage] 🔄 update_recent_rows 开始渲染 | 数据量: {len(rounds_data)}")
        
        # ✅ 修复1：先整体倒序，再取前5条。确保索引0显示最新数据
        display_data = rounds_data[::-1][:5]
        
        for i in range(5):
            if i < len(display_data):
                item = display_data[i]
                rid = item.get("round_id")
                total_time = item.get("total_time", 0.0)
                print(f"[MonitorPage] 📝 Row {i} -> rid={rid}, total_time={total_time}")
                
                self.time_labels[i].setText(f"{total_time:.1f}s")
                self.delete_labels[i].set_round_id(rid)
            else:
                self.time_labels[i].setText("--")
                self.delete_labels[i].set_round_id(None)
    
    def _on_delete_clicked(self, round_id: int):
        """删除单局记录"""
        print(f"[MonitorPage] 🎯 _on_delete_clicked 被调用! round_id={round_id} (type={type(round_id)})")
        if not self.session_manager:
            print("[MonitorPage] ❌ 拦截: session_manager 为空")
            return
        print(f"[MonitorPage] ⚙️ 调用 manager.delete_round({round_id})...")
        try:
            res = self.session_manager.delete_round(round_id)
            print(f"[MonitorPage] ✅ Manager 返回: {res}")
            print(f"[MonitorPage] 🔄 拉取最新列表并刷新 UI...")
            self.update_recent_rows(self.session_manager.get_recent_rounds(5))
            print(f"[MonitorPage] 🏁 刷新完成")
        except Exception as e:
            print(f"[MonitorPage] 💥 删除异常: {e}")
            import traceback
            traceback.print_exc()

    def update_stats_display(self, stats: dict):
        """🎨 刷新统计数据 UI"""
        if not stats or "current_session" not in stats:
            return

        # 1️⃣ 判断当前是否处于对局中（安全访问后端运行时标记）
        in_game = False
        if self.session_manager and hasattr(self.session_manager, "_current_round"):
            current_round = getattr(self.session_manager, "_current_round", {})
            in_game = current_round.get("in_game_start", 0.0) > 0.0

        # 2️⃣ 计算"视觉局数"：已结算局数 + 进行中临时+1
        actual_runs = stats["current_session"]["runs"]
        display_runs = actual_runs + 1 if in_game else actual_runs

        # 3️⃣ 更新大数字与时长
        self.lbl_big_runs.setText(str(display_runs))
        duration_min = stats["current_session"]["duration"] / 60
        self.lbl_big_duration.setText(f"时长: {duration_min:.1f} 分钟")

        # 4️⃣ 更新历史统计
        hist = stats.get("historical", {})
        total_runs = hist.get('total_runs', 0)
        total_secs = hist.get('total_duration', 0.0)
        
        # ✅ 修复2：将秒转换为 小时+分钟 格式
        hours = int(total_secs // 3600)
        minutes = int((total_secs % 3600) // 60)
        duration_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
        
        self.lbl_hist.setText(f"历史: {total_runs}局 | 总时长: {duration_str}")

        # 5️⃣ 更新平均时长 & 最近5局
        self.lbl_recent_avg.setText(f"平均时长: {stats.get('average_duration', 0.0):.1f}s")
        self.update_recent_rows(stats.get("recent_5_rounds", []))

        # 6️⃣ 状态栏动态提示
        if in_game:
            self.lbl_status.setText("状态: 🎮 对局进行中...")
        elif self.session_manager and hasattr(self.session_manager, "_session"):
            session_data = getattr(self.session_manager, "_session", {})
            if session_data and session_data.get("status") == "paused":
                self.lbl_status.setText("状态: ⏸️ 已暂停")
            else:
                self.lbl_status.setText("状态: ⏳ 等待匹配/大厅")
        else:
            self.lbl_status.setText("状态: ⏳ 等待匹配/大厅")
