import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QDesktopWidget
from retai import ModbusRTUMaster
from qibeng import ModbusScannerApp
from huatai import SerialCommunication  
from home import HomePage
from serial_manager import SerialManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 创建一个串口管理器实例
        self.serial_manager = SerialManager()
        
        # 创建 QTabWidget
        self.tab_widget = QTabWidget()
        
        # 首页（串口管理）
        self.home_page = HomePage(self.serial_manager)
        
        self.qibeng = ModbusScannerApp(self.serial_manager)
        self.huatai = SerialCommunication(self.serial_manager)
        # 创建页面并将它们添加到 QTabWidget
        self.tab_widget.addTab(self.home_page, "首页")
        self.tab_widget.addTab(ModbusRTUMaster(), "热台")
        self.tab_widget.addTab(self.qibeng, "气泵")
        self.tab_widget.addTab(self.huatai, "滑台")
        
        # 设置主窗口的中央小部件
        self.setCentralWidget(self.tab_widget)

        # 设置窗口标题
        self.setWindowTitle("PyQt Tab Widget Example")
        
        # 设置窗口大小并居中
        self.resize(800, 600)  # 设置窗口大小
        self.center()          # 调用居中方法

    def center(self):
        """让窗口显示在屏幕中央"""
        # 获取屏幕的矩形对象
        screen_geometry = QDesktopWidget().availableGeometry()
        # 获取窗口的矩形对象
        window_geometry = self.frameGeometry()
        # 将窗口的中心点移动到屏幕中心
        window_geometry.moveCenter(screen_geometry.center())
        # 将窗口的左上角移动到正确位置
        self.move(window_geometry.topLeft())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
