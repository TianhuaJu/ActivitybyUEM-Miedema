import sys
import os
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QSplitter, QVBoxLayout, QGroupBox, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QHBoxLayout, QComboBox,
                             QTableWidget, QFileDialog, QMessageBox, QTableWidgetItem,
                             QApplication, QMainWindow, QProgressBar, QTextEdit)

# 尝试导入pycalphad，如果失败则TDB功能不可用
try:
	from pycalphad import Database
	
	PYCALPHAD_AVAILABLE = True
except ImportError:
	PYCALPHAD_AVAILABLE = False
	print("警告: pycalphad 库未安装，TDB数据库功能将不可用。请使用 'pip install pycalphad' 安装。")


# === 数据连接与操作核心类 ===
class DatabaseConnector:
	"""
	一个统一的数据连接器，用于处理SQLite和TDB数据库。
	它封装了所有数据库的底层操作。
	"""
	
	def __init__ (self, db_path: str):
		if not os.path.exists(db_path):
			raise FileNotFoundError(f"数据库文件不存在: {db_path}")
		
		self.db_path = db_path
		self.conn = None
		self.db_type = 'Unknown'
		
		if db_path.lower().endswith('.db'):
			self.db_type = 'SQLite'
			self.conn = sqlite3.connect(db_path)
			# 启用外键约束
			self.conn.execute("PRAGMA foreign_keys = ON")
		elif db_path.lower().endswith('.tdb'):
			self.db_type = 'TDB'
			if PYCALPHAD_AVAILABLE:
				self.conn = Database(db_path)  # pycalphad的Database对象
			else:
				raise ImportError("pycalphad库未安装，无法处理TDB文件。")
		else:
			raise ValueError(f"不支持的数据库文件格式: {os.path.basename(db_path)}")
	
	def get_tables_or_phases (self) -> List[str]:
		"""获取数据库中所有表名或相名"""
		try:
			if self.db_type == 'SQLite':
				cursor = self.conn.cursor()
				cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
				return sorted([table[0] for table in cursor.fetchall()
				               if not table[0].startswith('sqlite_')])
			elif self.db_type == 'TDB':
				return sorted(self.conn.phases.keys())
		except Exception as e:
			print(f"获取表名/相名时出错: {e}")
		return []
	
	def get_table_data (self, table_name: str) -> Tuple[List[str], List[List[Any]]]:
		"""获取指定表或相的所有数据"""
		try:
			if self.db_type == 'SQLite':
				cursor = self.conn.cursor()
				cursor.execute(f'SELECT * FROM "{table_name}"')
				headers = [description[0] for description in cursor.description]
				rows = cursor.fetchall()
				return headers, rows
			elif self.db_type == 'TDB':
				headers = ["Parameter_Type", "Constituents", "Order", "Symbol", "Value_Expression"]
				rows = []
				if table_name in self.conn.phases:
					for param in self.conn.search(self.conn.model.parameters.all, phase_name=table_name):
						try:
							constituents = str(param.constituents)
							order = param.order
							symbol = f"L({table_name},{constituents};{order})"
							value_expr = str(param.expr)
							rows.append(["G", constituents, order, symbol, value_expr])
						except Exception as e:
							print(f"解析TDB参数时出错: {e}")
				return headers, rows
		except Exception as e:
			print(f"获取表数据时出错: {e}")
		return [], []
	
	def find_record (self, table_name: str, symbol_query: str) -> Tuple[List[str], List[List[Any]]]:
		"""根据Symbol查找记录"""
		try:
			if self.db_type == 'SQLite':
				cursor = self.conn.cursor()
				try:
					cursor.execute(f"SELECT * FROM \"{table_name}\" WHERE Symbol LIKE ?",
					               (f'%{symbol_query}%',))
					headers = [description[0] for description in cursor.description]
					rows = cursor.fetchall()
					return headers, rows
				except sqlite3.OperationalError:  # 如果没有Symbol列
					QMessageBox.warning(None, "查找错误", f"表 '{table_name}' 中没有 'Symbol' 列。")
					return self.get_table_data(table_name)
			elif self.db_type == 'TDB':
				headers, all_rows = self.get_table_data(table_name)
				filtered_rows = [row for row in all_rows
				                 if symbol_query.upper() in str(row[1]).upper()]
				return headers, filtered_rows
		except Exception as e:
			print(f"查找记录时出错: {e}")
		return [], []
	
	def update_record (self, table_name: str, primary_key_value: str, new_data: Dict[str, Any]):
		"""更新记录"""
		if self.db_type != 'SQLite':
			raise NotImplementedError("TDB文件是只读的，不支持写入操作。")
		
		try:
			set_clause = ", ".join([f'"{key}" = ?' for key in new_data.keys()])
			values = list(new_data.values()) + [primary_key_value]
			query = f'UPDATE "{table_name}" SET {set_clause} WHERE Symbol = ?'
			cursor = self.conn.cursor()
			cursor.execute(query, tuple(values))
			self.conn.commit()
		except Exception as e:
			self.conn.rollback()
			raise e
	
	def insert_record (self, table_name: str, data: Dict[str, Any]):
		"""插入新记录"""
		if self.db_type != 'SQLite':
			raise NotImplementedError("TDB文件是只读的，不支持写入操作。")
		
		try:
			columns = '(' + ', '.join(f'"{k}"' for k in data.keys()) + ')'
			placeholders = f"({', '.join(['?'] * len(data))})"
			query = f'INSERT INTO "{table_name}" {columns} VALUES {placeholders}'
			cursor = self.conn.cursor()
			cursor.execute(query, tuple(data.values()))
			self.conn.commit()
		except Exception as e:
			self.conn.rollback()
			raise e
	
	def delete_record (self, table_name: str, primary_key_value: str):
		"""删除记录"""
		if self.db_type != 'SQLite':
			raise NotImplementedError("TDB文件是只读的，不支持写入操作。")
		
		try:
			query = f'DELETE FROM "{table_name}" WHERE Symbol = ?'
			cursor = self.conn.cursor()
			cursor.execute(query, (primary_key_value,))
			self.conn.commit()
		except Exception as e:
			self.conn.rollback()
			raise e
	
	def get_table_info (self, table_name: str) -> Dict[str, Any]:
		"""获取表的详细信息"""
		if self.db_type == 'SQLite':
			cursor = self.conn.cursor()
			cursor.execute(f'PRAGMA table_info("{table_name}")')
			columns = cursor.fetchall()
			cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
			row_count = cursor.fetchone()[0]
			return {
				'columns': columns,
				'row_count': row_count,
				'type': 'SQLite Table'
			}
		elif self.db_type == 'TDB':
			if table_name in self.conn.phases:
				headers, rows = self.get_table_data(table_name)
				return {
					'columns': headers,
					'row_count': len(rows),
					'type': 'TDB Phase'
				}
		return {}
	
	def close (self):
		"""关闭数据库连接"""
		if self.conn and self.db_type == 'SQLite':
			self.conn.close()


# === 数据库管理标签页 ===
class DatabaseManagerTab(QWidget):
	"""现代化的数据库管理界面"""
	
	def __init__ (self, parent_app):
		super().__init__()
		self.parent_app = parent_app
		self.current_headers = []
		self.edit_widgets = {}
		self.db_path = ""  # 初始化db_path属性
		self.db_type = "未知"  # 初始化db_type属性
		self.quick_status_label = None  # 初始化快速状态标签
		self.init_ui()
	
	def init_ui (self):
		"""初始化用户界面"""
		top_layout = QVBoxLayout(self)
		top_layout.setContentsMargins(8, 8, 8, 8)
		top_layout.setSpacing(8)
		
		# 紧凑型标题栏
		title_widget = QWidget()
		title_widget.setFixedHeight(50)  # 增加高度
		title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                          stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 6px;
            }
        """)
		title_layout = QHBoxLayout(title_widget)
		title_layout.setContentsMargins(12, 0, 12, 0)
		
		title_label = QLabel("🗃️ 数据库管理")
		title_label.setStyleSheet("""
            font-size: 20px;
            color: white;
            font-weight: bold;
        """)
		
		# 快速状态显示
		self.quick_status_label = QLabel("未连接")
		self.quick_status_label.setStyleSheet("""
            color: #fbbf24;
            font-size: 15px;
            font-weight: bold;
            background: rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 4px;
        """)
		
		title_layout.addWidget(title_label)
		title_layout.addStretch()
		title_layout.addWidget(self.quick_status_label)
		
		top_layout.addWidget(title_widget)
		
		# 主分割器
		main_splitter = QSplitter(Qt.Horizontal)
		
		# 左侧面板
		left_widget = self.create_left_panel()
		# 右侧面板
		right_widget = self.create_right_panel()
		
		main_splitter.addWidget(left_widget)
		main_splitter.addWidget(right_widget)
		main_splitter.setStretchFactor(0, 3)
		main_splitter.setStretchFactor(1, 2)
		
		top_layout.addWidget(main_splitter)
	
	def create_left_panel (self) -> QWidget:
		"""创建左侧控制面板"""
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		left_layout.setSpacing(8)
		left_layout.setContentsMargins(0, 0, 0, 0)
		
		# 1. 数据库连接组 - 紧凑型
		control_group = QGroupBox("数据库连接")
		control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                padding: 0 8px;
                color: #6366f1;
            }
        """)
		control_layout = QVBoxLayout()  # 改为垂直布局，更紧凑
		control_layout.setSpacing(6)
		
		# 文件选择行
		file_row = QHBoxLayout()
		file_label = QLabel("数据库:")
		file_label.setStyleSheet("font-size: 14px; font-weight: bold;")
		file_row.addWidget(file_label)
		
		self.db_path_label = QLineEdit("尚未选择数据库文件")
		self.db_path_label.setReadOnly(True)
		self.db_path_label.setFixedHeight(32)  # 增加高度
		self.db_path_label.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
            }
        """)
		file_row.addWidget(self.db_path_label, 1)
		
		browse_btn = QPushButton("📂")
		browse_btn.setFixedSize(36, 32)  # 增加大小
		browse_btn.setToolTip("浏览数据库文件")
		browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #5856eb; }
            QPushButton:pressed { background-color: #4f46e5; }
        """)
		browse_btn.clicked.connect(self.browse_database_file)
		file_row.addWidget(browse_btn)
		
		control_layout.addLayout(file_row)
		
		# 状态和操作行
		status_row = QHBoxLayout()
		status_label = QLabel("状态:")
		status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
		status_row.addWidget(status_label)
		
		self.status_label = QLabel("未连接")
		self.status_label.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 14px;")
		status_row.addWidget(self.status_label)
		status_row.addStretch()
		
		self.load_db_btn = QPushButton("✔️ 加载")
		self.load_db_btn.setEnabled(False)
		self.load_db_btn.setFixedHeight(32)  # 增加高度
		self.load_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
		self.load_db_btn.clicked.connect(self.load_and_apply_database)
		status_row.addWidget(self.load_db_btn)
		
		control_layout.addLayout(status_row)
		control_group.setLayout(control_layout)
		left_layout.addWidget(control_group)
		
		# 2. 数据预览组 - 优化布局
		preview_group = QGroupBox("数据预览")
		preview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                padding: 0 8px;
                color: #6366f1;
            }
        """)
		preview_layout = QVBoxLayout()
		preview_layout.setSpacing(6)
		
		# 表选择 - 紧凑布局
		table_select_layout = QHBoxLayout()
		table_label = QLabel("表/相:")
		table_label.setStyleSheet("font-size: 14px; font-weight: bold;")
		table_select_layout.addWidget(table_label)
		
		self.table_selector_combo = QComboBox()
		self.table_selector_combo.setFixedHeight(32)  # 增加高度
		self.table_selector_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: white;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
		self.table_selector_combo.currentTextChanged.connect(self.on_table_selected)
		table_select_layout.addWidget(self.table_selector_combo, 1)
		
		preview_layout.addLayout(table_select_layout)
		
		# 数据表格
		self.data_preview_table = QTableWidget()
		self.data_preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
		self.data_preview_table.setAlternatingRowColors(True)
		self.data_preview_table.setSelectionBehavior(QTableWidget.SelectRows)
		self.data_preview_table.verticalHeader().setDefaultSectionSize(28)  # 增加行高
		self.data_preview_table.horizontalHeader().setDefaultSectionSize(120)  # 增加默认列宽
		self.data_preview_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e5e7eb;
                background-color: white;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                padding: 6px 8px;
                border: 1px solid #e5e7eb;
                font-weight: bold;
                font-size: 13px;
            }
        """)
		self.data_preview_table.itemSelectionChanged.connect(self.on_record_selected)
		preview_layout.addWidget(self.data_preview_table)
		
		preview_group.setLayout(preview_layout)
		left_layout.addWidget(preview_group)
		
		return left_widget
	
	def create_right_panel (self) -> QWidget:
		"""创建右侧操作面板"""
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		right_layout.setSpacing(8)
		right_layout.setContentsMargins(0, 0, 0, 0)
		
		# 3. 查找记录组 - 紧凑型
		search_group = QGroupBox("查找记录")
		search_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                padding: 0 8px;
                color: #f59e0b;
            }
        """)
		search_layout = QHBoxLayout()
		search_layout.setSpacing(6)
		
		symbol_label = QLabel("符号:")
		symbol_label.setStyleSheet("font-size: 14px; font-weight: bold;")
		search_layout.addWidget(symbol_label)
		
		self.search_input = QLineEdit()
		self.search_input.setPlaceholderText("例如: Ni-Cr 或 LIQUID")
		self.search_input.setFixedHeight(32)  # 增加高度
		self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)
		self.search_input.returnPressed.connect(self.find_record)
		search_layout.addWidget(self.search_input, 1)
		
		search_btn = QPushButton("🔍")
		search_btn.setFixedSize(36, 32)  # 增加大小
		search_btn.setToolTip("查找记录")
		search_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #d97706; }
        """)
		search_btn.clicked.connect(self.find_record)
		search_layout.addWidget(search_btn)
		
		search_group.setLayout(search_layout)
		right_layout.addWidget(search_group)
		
		# 4. 编辑/添加记录组 - 更紧凑
		self.edit_group = QGroupBox("编辑记录")
		self.edit_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                padding: 0 8px;
                color: #3b82f6;
            }
        """)
		self.edit_form_layout = QGridLayout()  # 使用网格布局
		self.edit_form_layout.setSpacing(4)
		
		self.edit_placeholder = QLabel("请先选择一条记录进行编辑\n或点击添加新记录")
		self.edit_placeholder.setAlignment(Qt.AlignCenter)
		self.edit_placeholder.setStyleSheet("""
            color: #6b7280;
            font-style: italic;
            font-size: 14px;
            padding: 16px;
            background-color: #f9fafb;
            border-radius: 4px;
            border: 1px dashed #d1d5db;
        """)
		self.edit_form_layout.addWidget(self.edit_placeholder)
		
		self.edit_group.setLayout(self.edit_form_layout)
		right_layout.addWidget(self.edit_group)
		
		# 操作按钮 - 紧凑布局
		action_widget = QWidget()
		action_widget.setFixedHeight(45)  # 增加高度
		action_button_layout = QHBoxLayout(action_widget)
		action_button_layout.setContentsMargins(0, 8, 0, 0)
		action_button_layout.setSpacing(6)
		
		self.add_new_btn = QPushButton("➕ 新增")
		self.add_new_btn.setEnabled(False)
		self.add_new_btn.setFixedHeight(36)  # 增加高度
		self.add_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
		self.add_new_btn.clicked.connect(self.prepare_add_new)
		
		self.save_btn = QPushButton("💾 保存")
		self.save_btn.setEnabled(False)
		self.save_btn.setFixedHeight(36)  # 增加高度
		self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
		self.save_btn.clicked.connect(self.save_changes)
		
		self.delete_btn = QPushButton("❌ 删除")
		self.delete_btn.setEnabled(False)
		self.delete_btn.setFixedHeight(36)  # 增加高度
		self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
		self.delete_btn.clicked.connect(self.delete_record)
		
		action_button_layout.addWidget(self.add_new_btn)
		action_button_layout.addWidget(self.save_btn)
		action_button_layout.addWidget(self.delete_btn)
		
		right_layout.addWidget(action_widget)
		right_layout.addStretch()
		
		return right_widget
	
	def browse_database_file (self):
		"""浏览并选择数据库文件"""
		# 设置默认路径为软件工作目录下的database文件夹
		default_path = os.path.join(os.getcwd(), "database/data")
		if not os.path.exists(default_path):
			default_path = os.getcwd()  # 如果database文件夹不存在，则使用当前工作目录
		
		filepath, _ = QFileDialog.getOpenFileName(
				self, "选择数据库文件", default_path,
				"支持的数据库 (*.db *.tdb);;SQLite数据库 (*.db);;热力学数据库 (*.tdb);;所有文件 (*.*)"
		)
		if filepath:
			self.db_path = filepath
			self.db_path_label.setText(os.path.basename(filepath))  # 只显示文件名，节省空间
			
			if filepath.lower().endswith('.db'):
				self.db_type = "SQLite"
			elif filepath.lower().endswith('.tdb'):
				self.db_type = "TDB"
			else:
				self.db_type = "未知"
			
			self.status_label.setText(f"已选择 {self.db_type}")
			self.status_label.setStyleSheet("font-weight: bold; color: #f59e0b; font-size: 14px;")
			
			# 更新快速状态
			self.quick_status_label.setText(f"⏳ {self.db_type}")
			self.quick_status_label.setStyleSheet("""
                color: #f59e0b;
                font-size: 15px;
                font-weight: bold;
                background: rgba(255,255,255,0.3);
                padding: 4px 8px;
                border-radius: 4px;
            """)
			
			self.load_db_btn.setEnabled(True)
	
	def load_and_apply_database (self):
		"""加载并应用数据库"""
		if not self.db_path:
			return
		
		try:
			# 关闭现有连接
			if hasattr(self.parent_app, 'db_connector') and self.parent_app.db_connector:
				self.parent_app.db_connector.close()
			
			# 创建新连接
			self.parent_app.db_connector = DatabaseConnector(self.db_path)
			
			# 更新状态
			db_name = os.path.basename(self.db_path)
			self.status_label.setText(f"已加载: {db_name}")
			self.status_label.setStyleSheet("font-weight: bold; color: #10b981; font-size: 14px;")
			
			# 更新快速状态
			self.quick_status_label.setText(f"✅ {self.parent_app.db_connector.db_type}")
			self.quick_status_label.setStyleSheet("""
                color: #10b981;
                font-size: 15px;
                font-weight: bold;
                background: rgba(255,255,255,0.3);
                padding: 4px 8px;
                border-radius: 4px;
            """)
			
			if hasattr(self.parent_app, 'statusBar'):
				self.parent_app.statusBar().showMessage(
						f"数据库 {db_name} 已加载", 5000)
			
			# 更新表列表
			self.table_selector_combo.clear()
			tables = self.parent_app.db_connector.get_tables_or_phases()
			self.table_selector_combo.addItems(tables)
			
			# 根据数据库类型启用/禁用功能
			is_sqlite = self.parent_app.db_connector.db_type == 'SQLite'
			self.add_new_btn.setEnabled(is_sqlite)
			
			if not is_sqlite:
				QMessageBox.information(self, "提示",
				                        "TDB数据库为只读模式，仅支持查看和搜索功能。")
		
		except Exception as e:
			QMessageBox.critical(self, "加载失败", f"加载数据库时发生错误:\n\n{str(e)}")
			self.status_label.setText("加载失败")
			self.status_label.setStyleSheet("font-weight: bold; color: #ef4444; font-size: 14px;")
			self.quick_status_label.setText("❌ 失败")
			self.quick_status_label.setStyleSheet("""
                color: #ef4444;
                font-size: 15px;
                font-weight: bold;
                background: rgba(255,255,255,0.3);
                padding: 4px 8px;
                border-radius: 4px;
            """)
	
	def on_table_selected (self, table_name: str):
		"""当选择表时更新预览"""
		if not table_name or not hasattr(self.parent_app, 'db_connector') or not self.parent_app.db_connector:
			return
		
		try:
			headers, rows = self.parent_app.db_connector.get_table_data(table_name)
			self.update_table_view(headers, rows)
			
			# 显示表信息
			if hasattr(self.parent_app, 'statusBar'):
				self.parent_app.statusBar().showMessage(
						f"已加载表 '{table_name}' - {len(rows)} 条记录", 3000)
		
		except Exception as e:
			QMessageBox.critical(self, "预览失败",
			                     f"读取数据表 '{table_name}' 时发生错误:\n\n{str(e)}")
	
	def on_record_selected (self):
		"""当选择记录时更新编辑表单"""
		selected_items = self.data_preview_table.selectedItems()
		if not selected_items:
			self.delete_btn.setEnabled(False)
			self.save_btn.setEnabled(False)
			return
		
		# 检查是否为SQLite数据库
		is_sqlite = (hasattr(self.parent_app, 'db_connector') and
		             self.parent_app.db_connector and
		             self.parent_app.db_connector.db_type == 'SQLite')
		
		self.delete_btn.setEnabled(is_sqlite)
		self.save_btn.setEnabled(is_sqlite)
		self.edit_group.setTitle("4. 编辑选中记录")
		
		# 清除现有表单
		self.clear_edit_form(add_placeholder=False)
		
		# 填充编辑表单
		row = self.data_preview_table.currentRow()
		for col_idx, header in enumerate(self.current_headers):
			label = QLabel(f"{header}:")
			label.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
			
			item = self.data_preview_table.item(row, col_idx)
			text = item.text() if item else ""
			
			line_edit = QLineEdit(text)
			line_edit.setFixedHeight(32)  # 增加高度
			line_edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: white;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border-color: #3b82f6;
                }
                QLineEdit:read-only {
                    background-color: #f3f4f6;
                    color: #6b7280;
                }
            """)
			
			# Symbol列和TDB文件设为只读
			if header.lower() == 'symbol' or not is_sqlite:
				line_edit.setReadOnly(True)
			
			self.edit_form_layout.addWidget(label, col_idx, 0)
			self.edit_form_layout.addWidget(line_edit, col_idx, 1)
			self.edit_widgets[header] = line_edit
	
	def find_record (self):
		"""查找记录"""
		if not hasattr(self.parent_app, 'db_connector') or not self.parent_app.db_connector:
			QMessageBox.warning(self, "操作无效", "请先加载一个数据库。")
			return
		
		symbol = self.search_input.text().strip()
		table_name = self.table_selector_combo.currentText()
		
		if not table_name:
			QMessageBox.warning(self, "操作无效", "请先选择一个数据表或相。")
			return
		
		if not symbol:
			# 如果搜索内容为空，则显示全表
			self.on_table_selected(table_name)
			return
		
		try:
			headers, rows = self.parent_app.db_connector.find_record(table_name, symbol)
			self.update_table_view(headers, rows)
			
			if hasattr(self.parent_app, 'statusBar'):
				self.parent_app.statusBar().showMessage(
						f"在 '{table_name}' 中找到 {len(rows)} 条记录", 5000)
		
		except Exception as e:
			QMessageBox.critical(self, "查找失败", f"查找记录时发生错误:\n\n{str(e)}")
	
	def prepare_add_new (self):
		"""准备添加新记录"""
		if (not hasattr(self.parent_app, 'db_connector') or
				not self.parent_app.db_connector or
				self.parent_app.db_connector.db_type != 'SQLite'):
			QMessageBox.warning(self, "操作无效", "只有SQLite数据库支持添加新记录。")
			return
		
		if not self.current_headers:
			QMessageBox.warning(self, "操作无效", "请先选择一个数据表。")
			return
		
		# 清除选择并设置模式
		self.data_preview_table.clearSelection()
		self.edit_group.setTitle("4. 添加新记录")
		self.clear_edit_form(add_placeholder=False)
		
		# 创建空的编辑表单
		for row_idx, header in enumerate(self.current_headers):
			label = QLabel(f"{header}:")
			label.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
			
			line_edit = QLineEdit()
			line_edit.setFixedHeight(32)  # 增加高度
			line_edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: white;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border-color: #3b82f6;
                }
            """)
			
			self.edit_form_layout.addWidget(label, row_idx, 0)
			self.edit_form_layout.addWidget(line_edit, row_idx, 1)
			self.edit_widgets[header] = line_edit
		
		self.save_btn.setEnabled(True)
		self.delete_btn.setEnabled(False)
	
	def save_changes (self):
		"""保存更改"""
		if not self.edit_widgets or not hasattr(self.parent_app, 'db_connector') or not self.parent_app.db_connector:
			return
		
		try:
			# 收集数据
			new_data = {header: widget.text().strip() for header, widget in self.edit_widgets.items()}
			table_name = self.table_selector_combo.currentText()
			
			# 验证必填字段 - 只有Symbol字段必须填写
			if 'Symbol' not in new_data or not new_data['Symbol'].strip():
				QMessageBox.warning(self, "保存失败", "Symbol字段必须填写。")
				return
			
			if self.data_preview_table.selectedItems():  # 编辑模式
				symbol = self.edit_widgets.get('Symbol')
				if not symbol or not symbol.text().strip():
					QMessageBox.warning(self, "保存失败", "主键 'Symbol' 不能为空。")
					return
				
				symbol_value = symbol.text().strip()
				self.parent_app.db_connector.update_record(table_name, symbol_value, new_data)
				
				if hasattr(self.parent_app, 'statusBar'):
					self.parent_app.statusBar().showMessage(f"记录 '{symbol_value}' 已更新", 3000)
			
			else:  # 添加模式
				self.parent_app.db_connector.insert_record(table_name, new_data)
				
				if hasattr(self.parent_app, 'statusBar'):
					self.parent_app.statusBar().showMessage(f"新记录已添加", 3000)
			
			# 刷新表格
			self.on_table_selected(table_name)
		
		except Exception as e:
			QMessageBox.critical(self, "保存失败", f"保存数据时发生错误:\n\n{str(e)}")
	
	def delete_record (self):
		"""删除记录"""
		selected_items = self.data_preview_table.selectedItems()
		if not selected_items:
			QMessageBox.warning(self, "操作无效", "请先选择要删除的记录。")
			return
		
		row = self.data_preview_table.currentRow()
		
		try:
			# 查找Symbol列
			if 'Symbol' not in self.current_headers:
				QMessageBox.critical(self, "删除失败", "无法确定主键'Symbol'列。")
				return
			
			pk_col_index = self.current_headers.index('Symbol')
			symbol_item = self.data_preview_table.item(row, pk_col_index)
			
			if not symbol_item:
				QMessageBox.warning(self, "删除失败", "无法获取记录标识。")
				return
			
			symbol_value = symbol_item.text()
			
			# 确认删除
			reply = QMessageBox.question(
					self, "确认删除",
					f"您确定要删除记录 '{symbol_value}' 吗？\n\n此操作不可恢复。",
					QMessageBox.Yes | QMessageBox.No,
					QMessageBox.No
			)
			
			if reply == QMessageBox.Yes:
				table_name = self.table_selector_combo.currentText()
				self.parent_app.db_connector.delete_record(table_name, symbol_value)
				
				# 从表格中移除行
				self.data_preview_table.removeRow(row)
				
				if hasattr(self.parent_app, 'statusBar'):
					self.parent_app.statusBar().showMessage(f"记录 '{symbol_value}' 已删除", 3000)
				
				# 清除编辑表单
				self.clear_edit_form()
		
		except Exception as e:
			QMessageBox.critical(self, "删除失败", f"删除记录时发生错误:\n\n{str(e)}")
	
	def clear_edit_form (self, add_placeholder: bool = True):
		"""清除编辑表单"""
		# 移除所有控件
		for i in reversed(range(self.edit_form_layout.count())):
			item = self.edit_form_layout.itemAt(i)
			if item and item.widget():
				item.widget().setParent(None)
		
		# 清空编辑控件字典
		self.edit_widgets.clear()
		
		# 添加占位符
		if add_placeholder:
			self.edit_placeholder = QLabel("请先在左侧表格中选择一条记录进行编辑，\n或点击添加新记录。")
			self.edit_placeholder.setAlignment(Qt.AlignCenter)
			self.edit_placeholder.setStyleSheet("""
                color: #6b7280;
                font-style: italic;
                font-size: 14px;
                padding: 20px;
                background-color: #f9fafb;
                border-radius: 6px;
            """)
			self.edit_form_layout.addWidget(self.edit_placeholder, 0, 0, 1, 2)
	
	def update_table_view (self, headers: List[str], rows: List[List[Any]]):
		"""更新表格视图"""
		self.current_headers = headers
		
		# 设置表格尺寸
		self.data_preview_table.clearContents()
		self.data_preview_table.setRowCount(len(rows))
		self.data_preview_table.setColumnCount(len(headers))
		self.data_preview_table.setHorizontalHeaderLabels(headers)
		
		# 填充数据
		for row_idx, row_data in enumerate(rows):
			for col_idx, cell_data in enumerate(row_data):
				item = QTableWidgetItem(str(cell_data) if cell_data is not None else "")
				self.data_preview_table.setItem(row_idx, col_idx, item)
		
		# 调整列宽
		self.data_preview_table.resizeColumnsToContents()
		
		# 清除编辑表单
		self.clear_edit_form()


# === 主窗口集成代码 ===
def add_database_tab_to_main_window (main_window):
	"""
	将数据库管理标签页添加到主窗口

	使用方法:
	在你的ModernMainWindow.__init__方法中调用此函数
	"""
	if not hasattr(main_window, 'tabs'):
		raise AttributeError("主窗口必须有tabs属性（QTabWidget）")
	
	# 初始化数据库连接器
	main_window.db_connector = None
	
	# 创建数据库管理标签页
	db_manager_tab = DatabaseManagerTab(main_window)
	
	# 添加到标签页
	main_window.tabs.addTab(db_manager_tab, "🗃️ 数据库管理")
	
	return db_manager_tab