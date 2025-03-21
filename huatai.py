import sys
import serial
import serial.tools.list_ports
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout, 
    QComboBox, QLineEdit, QFormLayout
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIntValidator


# 读取和保存位置到文件
def load_positions():
    try:
        with open('positions.json', 'r') as f:
            data = json.load(f)
            return data.get('feed_position', 0), data.get('unload_position', 0)
    except FileNotFoundError:
        return 0, 0

def save_positions(feed_position, unload_position):
    with open('positions.json', 'w') as f:
        json.dump({'feed_position': feed_position, 'unload_position': unload_position}, f)

class SerialCommunication(QWidget):
    def __init__(self, serial_manager):
        super().__init__()
        self.serial_manager = serial_manager
        self.setWindowTitle("串口控制")
        self.resize(600, 400)

        # 加载位置
        self.feed_position, self.unload_position = load_positions()

        # 创建界面
        self.init_ui()

        self.timer = QTimer()

    def init_ui(self):
        layout = QVBoxLayout()

        # 输入电机地址
        self.motor_address_input = QLineEdit('1')  # 默认值为1
        self.motor_address_input.setValidator(QIntValidator(1, 10))  # 限制输入范围为1到10
        layout.addWidget(QLabel("电机地址："))
        layout.addWidget(self.motor_address_input)

        # 输入进料位置和退料位置
        form_layout = QFormLayout()
        self.feed_position_input = QLineEdit(str(self.feed_position))
        self.unload_position_input = QLineEdit(str(self.unload_position))
        form_layout.addRow("进料位置：", self.feed_position_input)
        form_layout.addRow("退料位置：", self.unload_position_input)
        layout.addLayout(form_layout)

        # 操作按钮
        self.feed_button = QPushButton("送料")
        self.unload_button = QPushButton("退料")
        self.feed_button.clicked.connect(self.send_feed_command)
        self.unload_button.clicked.connect(self.send_unload_command)
        layout.addWidget(self.feed_button)
        layout.addWidget(self.unload_button)

        # 显示发送和接收数据
        self.send_text = QTextEdit()
        self.receive_text = QTextEdit()
        self.send_text.setReadOnly(True)
        self.receive_text.setReadOnly(True)
        layout.addWidget(QLabel("发送数据："))
        layout.addWidget(self.send_text)
        layout.addWidget(QLabel("接收数据："))
        layout.addWidget(self.receive_text)

        self.setLayout(layout)

    def scan_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_combo.clear()
        for port in ports:
            self.port_combo.addItem(port.device)

    def send_feed_command(self):
        feed_position = int(self.feed_position_input.text())
        motor_address = int(self.motor_address_input.text())  # 获取电机地址

        # 假设 feed_position 需要变成 32 位，填充前两个字节并且将其拆分为高位和低位
        high_byte = (feed_position >> 16) & 0xFFFF  # 获取高16位
        low_byte = feed_position & 0xFFFF  # 获取低16位

        # 更新 frame，确保高位和低位的计算
        frame = [
            motor_address, 0xFD, 0x01, 0x01, 0xF4, 0x00, 
            (high_byte >> 8) & 0xFF, high_byte & 0xFF,  # 高位字节
            (low_byte >> 8) & 0xFF, low_byte & 0xFF,  # 低位字节
            0x01, 0x00, 0x6B
        ]
        self.send_command(frame, "送料中")

    def send_unload_command(self):
        unload_position = int(self.unload_position_input.text())
        motor_address = int(self.motor_address_input.text())  # 获取电机地址

        # 假设 unload_position 需要变成 32 位，填充前两个字节并且将其拆分为高位和低位
        high_byte = (unload_position >> 16) & 0xFFFF  # 获取高16位
        low_byte = unload_position & 0xFFFF  # 获取低16位

        # 更新 frame，确保高位和低位的计算
        frame = [
            motor_address, 0xFD, 0x01, 0x01, 0xF4, 0x00, 
            (high_byte >> 8) & 0xFF, high_byte & 0xFF,  # 高位字节
            (low_byte >> 8) & 0xFF, low_byte & 0xFF,  # 低位字节
            0x01, 0x00, 0x6B
        ]
        self.send_command(frame, "退料中")

    def send_command(self, frame, action):
        if self.serial_manager.get_connection_status():
            data = bytes(frame)
            self.serial_manager.send_data(data)
            self.send_text.append(f"发送数据: {data.hex().upper()}")
            self.receive_text.append(f"{action}: {data.hex().upper()}")
            # 保存最新位置
            save_positions(int(self.feed_position_input.text()), int(self.unload_position_input.text()))
        else:
            self.status_label.setText("请先连接串口")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialCommunication()
    window.show()
    sys.exit(app.exec_())
