# serial_manager.py
import serial

class SerialManager:
    def __init__(self):
        self.serial_port = None
        self.is_connected = False

    def connect(self, port, baudrate=9600):
        if self.is_connected:
            return False  # 如果已经连接，返回False

        self.serial_port = serial.Serial(port, baudrate, timeout=0.2)
        if self.serial_port.is_open:
            self.is_connected = True
            return True
        return False

    def disconnect(self):
        if self.is_connected:
            self.serial_port.close()
            self.is_connected = False
            return True
        return False

    def get_connection_status(self):
        return self.is_connected  # 返回连接状态

    def send_data(self, data):
        if self.is_connected:
            self.serial_port.write(data)
            return True
        return False

    def receive_data(self, num_bytes):
        if self.is_connected:
            return self.serial_port.read(num_bytes)
        return None
