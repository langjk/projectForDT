# homepage.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QComboBox, QLabel
from serial_manager import SerialManager  # 确保你已经有 SerialManager 类
import serial.tools.list_ports  # 导入串口工具库

class HomePage(QWidget):
    def __init__(self, serial_manager):
        super().__init__()
        self.serial_manager = serial_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 串口连接选择
        self.port_combo = QComboBox()

        # 扫描串口按钮
        self.scan_button = QPushButton("扫描串口")
        self.scan_button.clicked.connect(self.scan_ports)

        # 连接按钮
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.toggle_connection)

        # 显示连接状态
        self.status_label = QLabel("状态：未连接")

        # 初始扫描并填充串口列表
        self.scan_ports()

        layout.addWidget(self.scan_button)
        layout.addWidget(self.port_combo)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def scan_ports(self):
        """扫描并填充可用的串口"""
        ports = serial.tools.list_ports.comports()
        self.port_combo.clear()  # 清空之前的串口列表
        for port in ports:
            self.port_combo.addItem(port.device)

        if not ports:
            self.status_label.setText("没有找到可用的串口")
        else:
            self.status_label.setText(f"找到 {len(ports)} 个可用串口")

    def toggle_connection(self):
        """切换串口连接或断开"""
        port = self.port_combo.currentText()
        
        if not self.serial_manager.get_connection_status():  # 当前没有连接
            success = self.serial_manager.connect(port)
            if success:
                self.status_label.setText(f"已连接到 {port}")
                self.connect_button.setText("断开")
            else:
                self.status_label.setText(f"无法连接到 {port}")
        else:  # 当前已连接
            self.serial_manager.disconnect()
            self.status_label.setText("已断开连接")
            self.connect_button.setText("连接")
