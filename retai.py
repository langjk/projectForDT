import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout, QComboBox, QLineEdit
)
from PyQt5.QtCore import QTimer


def calculate_checksum(command_type, param_code, addr, value=0):
    """
    根据给定的校验码计算方式计算校验码
    :param command_type: 指令类型（"read" 或 "write"）
    :param param_code: 参数代码
    :param addr: 地址
    :param value: 写入的值（仅对写命令有效）
    :return: 校验和的低字节和高字节
    """
    if command_type == "read":
        checksum = param_code * 256 + 0x52 + addr
    elif command_type == "write":
        checksum = param_code * 256 + 0x43 + value + addr
    else:
        raise ValueError("Invalid command type")
    
    checksum &= 0xFFFF
    return checksum & 0xFF, (checksum >> 8) & 0xFF


class ModbusRTUMaster(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus RTU 温度显示器")
        self.resize(600, 400)

        # 初始化串口
        self.serial_port = serial.Serial()
        self.serial_port.baudrate = 9600
        self.serial_port.timeout = 1

        # 创建界面
        self.init_ui()

        # 定时器读取和发送指令
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_devices)

    def init_ui(self):
        layout = QVBoxLayout()

        # 串口选择
        port_layout = QHBoxLayout()
        self.port_label = QLabel("串口：")
        self.port_combo = QComboBox()
        self.scan_ports()
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.toggle_connection)
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.connect_button)
        layout.addLayout(port_layout)

        # 温度显示
        self.temperature_label_1 = QLabel("设备 0x01 温度：测量值=0.0°C, 设定值=0.0°C")
        self.temperature_label_2 = QLabel("设备 0x02 温度：测量值=0.0°C, 设定值=0.0°C")
        layout.addWidget(self.temperature_label_1)
        layout.addWidget(self.temperature_label_2)

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

    def toggle_connection(self):
        if self.serial_port.is_open:
            self.serial_port.close()
            self.connect_button.setText("连接")
            self.timer.stop()
            self.send_text.append("串口已断开")
        else:
            try:
                self.serial_port.port = self.port_combo.currentText()
                self.serial_port.open()
                self.connect_button.setText("断开")
                self.send_text.append(f"已连接到 {self.serial_port.port}")
                self.timer.start(1000)  # 每秒发送指令
            except Exception as e:
                self.send_text.append(f"连接失败: {str(e)}")

    def poll_devices(self):
        """每秒发送指令并解析返回值"""
        for addr in [0x01, 0x02]:
            self.send_read_command(addr)

    def send_read_command(self, addr):
        """发送读取命令"""
        try:
            param_code = 0x1B
            checksum_low, checksum_high = calculate_checksum("read", param_code, addr)
            frame = [addr + 0x80, addr + 0x80, 0x52, param_code, 0x00, 0x00, checksum_low, checksum_high]
            data = bytes(frame)
            self.serial_port.write(data)
            self.send_text.append(f"发送到设备 0x{addr:02X}: {data.hex().upper()}")
            self.read_response(addr)
        except Exception as e:
            self.send_text.append(f"发送失败: {str(e)}")

    def read_response(self, addr):
        """读取返回数据并解析温度"""
        try:
            data = self.serial_port.read(10)
            if len(data) == 10:
                self.receive_text.append(f"设备 0x{addr:02X} 接收: {data.hex().upper()}")
                # 解析测量值和设定值
                measured_value = (data[1] << 8 | data[0]) / 10.0
                set_value = (data[3] << 8 | data[2]) / 10.0
                if addr == 0x01:
                    self.temperature_label_1.setText(f"设备 0x01 温度：测量值={measured_value:.1f}°C, 设定值={set_value:.1f}°C")
                elif addr == 0x02:
                    self.temperature_label_2.setText(f"设备 0x02 温度：测量值={measured_value:.1f}°C, 设定值={set_value:.1f}°C")
            else:
                self.receive_text.append(f"设备 0x{addr:02X} 接收数据不完整")
        except Exception as e:
            self.receive_text.append(f"接收失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModbusRTUMaster()
    window.show()
    sys.exit(app.exec_())
