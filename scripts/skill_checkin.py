#!/usr/bin/env python3
# 打卡Skill实现 - 供agent使用
import os
import time
import subprocess
import datetime
import re
import platform

class CheckinSkill:
    def __init__(self):
        self.package_name = "com.facishare.fs"  # 纷享销客包名
        self.activity_name = "com.fxiaoke.host.IndexActivity"  # 主Activity
        # 确保截图目录在当前脚本所在目录
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../screenshots")
        self.emulator_name = "daka"  # 模拟器名称
        self.adb_path = self.find_adb()  # 查找ADB路径
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def find_adb(self):
        """查找ADB工具路径"""
        # 常见的ADB路径
        common_paths = [
            "adb",  # 环境变量中的ADB
            "/Users/tianyong/Library/Android/sdk/platform-tools/adb",  # macOS常见路径
            "~/Library/Android/sdk/platform-tools/adb",  # 相对路径
            "C:\\Users\\{}\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe".format(os.getenv("USERNAME", "")),  # Windows路径
            "/usr/local/share/android-sdk/platform-tools/adb",  # Linux路径
        ]
        
        for path in common_paths:
            # 展开~符号
            expanded_path = os.path.expanduser(path)
            try:
                # 检查路径是否存在
                if os.path.exists(expanded_path):
                    # 测试ADB是否可用
                    subprocess.run([expanded_path, "--version"], capture_output=True, text=True, check=True)
                    print(f"找到ADB工具: {expanded_path}")
                    return expanded_path
            except Exception:
                continue
        
        print("未找到ADB工具，请确保Android SDK已安装")
        return None
    
    def check_adb_available(self):
        """检查ADB是否可用"""
        return self.adb_path is not None
    
    def check_emulator_status(self):
        """检查模拟器状态"""
        print("检查模拟器状态...")
        if not self.check_adb_available():
            print("ADB不可用，请确保ADB已安装")
            return False
        
        try:
            result = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True)
            devices = result.stdout.strip().split('\n')[1:]
            running_devices = [device.split('\t')[0] for device in devices if 'device' in device]
            
            if running_devices:
                print(f"发现运行中的设备: {running_devices}")
                return True
            else:
                print("未发现运行中的设备")
                return False
        except Exception as e:
            print(f"检查模拟器状态失败: {e}")
            return False
    
    def start_emulator(self):
        """启动模拟器"""
        print("启动模拟器...")
        try:
            # 查找emulator命令路径
            emulator_path = None
            if platform.system() == "Darwin":  # macOS
                # 尝试常见的Android SDK路径
                possible_paths = [
                    "~/Library/Android/sdk/emulator/emulator",
                    "/usr/local/share/android-sdk/emulator/emulator",
                    "/opt/android-sdk/emulator/emulator"
                ]
                for path in possible_paths:
                    expanded_path = os.path.expanduser(path)
                    if os.path.exists(expanded_path):
                        emulator_path = expanded_path
                        break
            elif platform.system() == "Windows":
                # Windows路径
                possible_paths = [
                    "C:\\Users\\{}\\AppData\\Local\\Android\\Sdk\\emulator\\emulator.exe".format(os.getenv("USERNAME")),
                    "D:\\Android\\Sdk\\emulator\\emulator.exe"
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        emulator_path = path
                        break
            else:  # Linux
                possible_paths = [
                    "~/Android/Sdk/emulator/emulator",
                    "/usr/local/android-sdk/emulator/emulator",
                    "/opt/android-sdk/emulator/emulator"
                ]
                for path in possible_paths:
                    expanded_path = os.path.expanduser(path)
                    if os.path.exists(expanded_path):
                        emulator_path = expanded_path
                        break
            
            if not emulator_path:
                print("未找到emulator命令，请确保Android SDK已安装")
                return False
            
            # 启动模拟器
            print(f"使用路径: {emulator_path} 启动模拟器: {self.emulator_name}")
            # 非阻塞方式启动模拟器
            subprocess.Popen([emulator_path, "-avd", self.emulator_name])
            print("模拟器启动中...")
            # 等待模拟器启动
            time.sleep(30)  # 给模拟器足够的启动时间
            
            # 再次检查模拟器状态
            return self.check_emulator_status()
        except Exception as e:
            print(f"启动模拟器失败: {e}")
            return False
    
    def is_app_running(self):
        """检查应用是否已经在运行"""
        try:
            result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "activities"], capture_output=True, text=True)
            return self.package_name in result.stdout
        except Exception as e:
            print(f"检查应用运行状态失败: {e}")
            return False
    
    def start_fxiaoke(self):
        """启动纷享销客应用"""
        print("启动纷享销客应用...")
        
        # 检查应用是否已经在运行
        if self.is_app_running():
            print("应用已经在运行，无需重新启动")
            return True
        
        try:
            # 尝试解锁屏幕（如果锁屏）
            subprocess.run([self.adb_path, "shell", "input", "keyevent", "82"], check=True)  # 82是解锁键
            time.sleep(1)
            
            # 使用 -a 参数和 -f 参数确保应用在前台启动
            subprocess.run([self.adb_path, "shell", "am", "start", "-a", "android.intent.action.MAIN", "-n", f"{self.package_name}/{self.activity_name}", "-f", "0x10000000"], check=True)
            time.sleep(10)  # 增加等待时间
            
            # 尝试使用 monkey 命令激活应用
            subprocess.run([self.adb_path, "shell", "monkey", "-p", self.package_name, "-c", "android.intent.category.LAUNCHER", "1"], check=True)
            time.sleep(5)  # 增加等待时间
            
            # 模拟点击屏幕，确保应用在前台
            subprocess.run([self.adb_path, "shell", "input", "tap", "500", "500"], check=True)
            time.sleep(2)
            
            return True
        except Exception as e:
            print(f"启动应用失败: {e}")
            return False
    
    def navigate_to_attendance(self):
        """进入考勤页面"""
        print("进入考勤页面...")
        try:
            # 第一步：判断当前页面状态
            page_status = self.check_page_status()
            
            # 根据页面状态执行不同操作
            if page_status == 'other':
                # 不是考勤页面也不是首页，先回到首页
                print("当前页面不是考勤页面也不是首页，先回到首页...")
                if not self.go_to_home():
                    print("回到首页失败，导航终止")
                    return False
                # 回到首页后，重新判断页面状态
                page_status = self.check_page_status()
                if page_status != 'home':
                    print("未能回到首页，导航终止")
                    return False
            
            if page_status == 'home':
                # 是首页，导航到考勤页面
                print("当前页面是首页，导航到考勤页面...")
                
                # 截图应用页面，确认当前状态
                app_screenshot = os.path.join(self.screenshot_dir, "app_page.png")
                subprocess.run([self.adb_path, "shell", "screencap", "/sdcard/app_screenshot.png"], check=True, capture_output=True)
                subprocess.run([self.adb_path, "pull", "/sdcard/app_screenshot.png", app_screenshot], check=True, capture_output=True)
                
                # 使用UIAutomator查找考勤选项
                subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True, capture_output=True)
                time.sleep(1)
                
                # 拉取XML文件到本地
                xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
                subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True, capture_output=True)
                
                # 读取并分析XML文件
                try:
                    with open(xml_path, 'r', encoding='utf-8') as f:
                        xml_content = f.read()
                    
                    # 检查是否是企信页面（首页），如果是，先点击"应用"按钮
                    if '企信' in xml_content:
                        print("当前是企信页面，点击应用按钮...")
                        # 点击底部导航栏的"应用"按钮（适配1440*2560分辨率）
                        # 应用按钮在第三个位置，坐标应该在中间偏右
                        app_button_coordinates = [(900, 2304), (950, 2304), (1000, 2304), (900, 2350), (950, 2350), (1000, 2350)]
                        
                        for coord in app_button_coordinates:
                            x, y = coord
                            print(f"尝试点击应用按钮，坐标: ({x}, {y})")
                            subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True, capture_output=True)
                            time.sleep(3)
                            
                            # 再次dump界面层级
                            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True, capture_output=True)
                            time.sleep(1)
                            subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True, capture_output=True)
                            
                            # 重新读取XML文件
                            with open(xml_path, 'r', encoding='utf-8') as f:
                                xml_content = f.read()
                            
                            # 检查是否成功进入应用页面
                            if '应用' in xml_content and '考勤' in xml_content:
                                print("成功进入应用页面！")
                                break
                    
                    # 查找包含"考勤"的元素
                    match = re.search(r'text=\"考勤\"[^>]+bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml_content)
                    if match:
                        left = int(match.group(1))
                        top = int(match.group(2))
                        right = int(match.group(3))
                        bottom = int(match.group(4))
                        # 计算中心点坐标
                        x = (left + right) // 2
                        y = (top + bottom) // 2
                        
                        # 点击考勤选项
                        subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True, capture_output=True)
                        time.sleep(5)
                        
                        # 再次检查页面状态，看是否已经进入考勤页面
                        current_status = self.check_page_status()
                        if current_status != 'attendance':
                            # 尝试使用更精确的坐标点击
                            for offset in [(-20, -10), (0, -10), (20, -10), (-20, 0), (0, 0), (20, 0), (-20, 10), (0, 10), (20, 10)]:
                                offset_x = x + offset[0]
                                offset_y = y + offset[1]
                                subprocess.run([self.adb_path, "shell", "input", "tap", str(offset_x), str(offset_y)], check=True, capture_output=True)
                                time.sleep(3)
                                
                                # 再次检查页面状态
                                current_status = self.check_page_status()
                                if current_status == 'attendance':
                                    break
                    else:
                        # 尝试使用更精确的坐标点击，重点点击顶部区域
                        current_status = 'home'
                        for x in [400, 450, 500, 550, 600, 650, 700, 750, 800]:
                            for y in [100, 120, 140, 160, 180, 200]:
                                subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True, capture_output=True)
                                time.sleep(2)
                                
                                # 再次检查页面状态，看是否已经进入考勤页面
                                current_status = self.check_page_status()
                                if current_status == 'attendance':
                                    break
                            if current_status == 'attendance':
                                break
                except Exception as xml_error:
                    # 尝试使用预设坐标点击
                    preset_coordinates = [(400, 100), (450, 120), (500, 140), (550, 160), (600, 180), (650, 200), (700, 100), (750, 120), (800, 140)]
                    current_status = 'home'
                    for coord in preset_coordinates:
                        subprocess.run([self.adb_path, "shell", "input", "tap", str(coord[0]), str(coord[1])], check=True, capture_output=True)
                        time.sleep(2)
                        
                        # 再次检查页面状态，看是否已经进入考勤页面
                        current_status = self.check_page_status()
                        if current_status == 'attendance':
                            break
            elif page_status == 'attendance':
                # 已经是考勤页面，刷新一下当前页
                print("当前已经是考勤页面，刷新页面...")
                # 可以通过点击页面空白处或下拉刷新来刷新页面
                # 这里使用下拉刷新的方式
                subprocess.run([self.adb_path, "shell", "input", "swipe", "720", "500", "720", "1500", "1000"], check=True, capture_output=True)
                time.sleep(2)
            
            # 截图当前页面
            test_screenshot = os.path.join(self.screenshot_dir, "test_attendance_page.png")
            print(f"截图当前页面到: {test_screenshot}")
            subprocess.run([self.adb_path, "shell", "screencap", "/sdcard/test_screenshot.png"], check=True)
            subprocess.run([self.adb_path, "pull", "/sdcard/test_screenshot.png", test_screenshot], check=True)
            print(f"截图已保存至: {test_screenshot}")
            
            # 再次检查页面状态，确保最终在考勤页面
            final_status = self.check_page_status()
            if final_status == 'attendance':
                print("导航到考勤页面成功！")
                return True
            else:
                print(f"最终页面状态不是考勤页面，导航失败: {final_status}")
                return False
        except Exception as e:
            print(f"导航到考勤页面失败: {e}")
            return False
    
    def take_screenshot(self, filename):
        """截图"""
        try:
            filepath = os.path.join(self.screenshot_dir, filename)
            subprocess.run([self.adb_path, "shell", "screencap", "/sdcard/screenshot.png"], check=True)
            subprocess.run([self.adb_path, "pull", "/sdcard/screenshot.png", filepath], check=True)
            return filepath
        except Exception as e:
            print(f"截图失败: {e}")
            return None
    
    def check_location_status(self, screenshot_path):
        """检查定位状态"""
        # 这里需要实现图像识别，检查是否显示「已进入地点考勤范围」
        # 暂时返回True，实际使用时需要实现
        print("检查定位状态...")
        return True
    
    def check_time_range(self):
        """检查当前时间是否在允许的打卡时间段内"""
        now = datetime.datetime.now()
        current_time = now.time()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        print(f"当前时间: {current_time}")
        
        # 早上上班签到: 08:30 - 09:00
        if (current_hour == 8 and current_minute >= 30) or (current_hour == 9 and current_minute == 0):
            return "morning_checkin"
        # 中午午休打卡: 12:00 - 13:00
        elif current_hour == 12 or (current_hour == 13 and current_minute == 0):
            return "noon_checkin"
        # 晚上下班签退: 18:00 - 19:00
        elif current_hour == 18 or (current_hour == 19 and current_minute == 0):
            return "evening_checkout"
        else:
            return "out_of_range"
    
    def check_button_status(self):
        """检查打卡按钮状态"""
        print("检查打卡按钮状态...")
        try:
            # 使用UIAutomator dump界面层级
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True)
            
            # 读取并分析XML文件
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 查找包含"签到"或"签退"的按钮
            if '签退' in xml_content:
                print("检测到签退按钮")
                return "签退"
            elif '签到' in xml_content:
                print("检测到签到按钮")
                return "签到"
            else:
                print("未检测到打卡按钮")
                return "未知"
        except Exception as e:
            print(f"检查按钮状态失败: {e}")
            return "签到"
    
    def get_current_activity(self):
        """获取当前页面的Activity名称"""
        try:
            # 尝试使用不同的命令获取当前Activity
            # 命令1: dumpsys activity top
            result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "top"], capture_output=True, text=True)
            activity_lines = [line for line in result.stdout.split('\n') if 'ACTIVITY' in line]
            if activity_lines:
                # 解析Activity名称，格式通常为：ACTIVITY com.package.name/.ActivityName ...
                activity_info = activity_lines[0].strip()
                # 提取Activity名称部分
                match = re.search(r'ACTIVITY\s+([^\s]+)', activity_info)
                if match:
                    activity_name = match.group(1)
                    print(f"当前Activity (dumpsys top): {activity_name}")
                    return activity_name
            
            # 命令2: dumpsys activity activities
            result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "activities"], capture_output=True, text=True)
            # 查找最新的Activity
            lines = result.stdout.split('\n')
            for i, line in enumerate(lines):
                if 'Running activities' in line:
                    # 查找第一个Activity
                    for j in range(i+1, len(lines)):
                        if 'ActivityRecord' in lines[j]:
                            match = re.search(r'ActivityRecord\{[^}]+\} ([^\s]+)', lines[j])
                            if match:
                                activity_name = match.group(1)
                                print(f"当前Activity (dumpsys activities): {activity_name}")
                                return activity_name
                            break
            
            return None
        except Exception as e:
            print(f"获取当前Activity失败: {e}")
            return None
    
    def check_page_status(self):
        """判断当前页面状态
        Returns:
            str: 页面状态，可能的值：'attendance', 'home', 'other'
        """
        # 直接使用UIAutomator判断页面状态，减少对Activity的依赖
        try:
            # 使用UIAutomator dump界面层级
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True, capture_output=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True, capture_output=True)
            
            # 读取并分析XML文件
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 检查是否是纷享销客应用
            if 'com.facishare.fs' in xml_content:
                # 检查是否包含考勤相关的文本，并且包含打卡时间、状态等考勤页面特有的元素
                if '考勤' in xml_content and ('智能签到' in xml_content or '签退' in xml_content or '已进入地点考勤范围' in xml_content):
                    return 'attendance'
                
                # 检查是否是应用页面
                elif '应用' in xml_content and '考勤' in xml_content:
                    return 'home'
                
                # 检查是否是企信页面（首页）
                elif '企信' in xml_content:
                    return 'home'
                
                # 其他纷享销客页面
                else:
                    return 'other'
        except Exception as e:
            pass
        
        # 其他页面
        return 'other'
    
    def go_to_home(self):
        """回到首页"""
        print("回到首页...")
        try:
            # 使用am start命令启动首页Activity
            subprocess.run([self.adb_path, "shell", "am", "start", "-n", f"{self.package_name}/{self.activity_name}"], check=True)
            time.sleep(3)  # 等待页面加载
            print("成功回到首页")
            return True
        except Exception as e:
            print(f"回到首页失败: {e}")
            return False
    
    def perform_checkin(self):
        """执行打卡操作"""
        print("执行打卡操作...")
        try:
            # 使用UIAutomator dump界面层级，找到实际的打卡按钮位置
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True)
            
            # 读取并分析XML文件，查找打卡按钮
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 查找包含"签到"或"签退"的按钮
            import re
            match = re.search(r'text=\"(签到|签退)\"[^>]+bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml_content)
            if match:
                left = int(match.group(2))
                top = int(match.group(3))
                right = int(match.group(4))
                bottom = int(match.group(5))
                # 计算中心点坐标
                x = (left + right) // 2
                y = (top + bottom) // 2
                print(f"找到打卡按钮，坐标: ({x}, {y})")
                
                # 点击打卡按钮
                subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True)
                time.sleep(2)
                return True
            else:
                # 如果没有找到按钮，使用默认坐标
                print("未找到打卡按钮，使用默认坐标")
                subprocess.run([self.adb_path, "shell", "input", "tap", "720", "1280"], check=True)
                time.sleep(2)
                return True
        except Exception as e:
            print(f"打卡操作失败: {e}")
            return False
    
    def detect_checkin_records(self):
        """检测考勤页面中的打卡记录
        Returns:
            list: 打卡记录列表
        """
        try:
            # 使用UIAutomator dump界面层级
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/attendance_dump.xml"], check=True, capture_output=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "attendance_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/attendance_dump.xml", xml_path], check=True, capture_output=True)
            
            # 读取并分析XML文件
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 查找打卡记录
            import re
            
            # 查找包含"智能签到"的记录
            smart_checkin_pattern = r'text="(\d{2}:\d{2} 智能签到)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            smart_checkin_matches = re.findall(smart_checkin_pattern, xml_content)
            
            checkin_records = []
            
            # 处理智能签到记录
            for match in smart_checkin_matches:
                checkin_time = match[0]
                # 查找对应的状态
                status_pattern = r'text="(正常|迟到|早退)"[^>]+bounds="\[\d+,\d+\]\[\d+,\d+\]"'
                status_match = re.search(status_pattern, xml_content)
                status = status_match.group(1) if status_match else "未知"
                
                # 查找对应的地点
                location_pattern = r'text="([^"\n]+)"[^>]+resource-id="com\.facishare\.fs:id/check_text"'
                location_match = re.search(location_pattern, xml_content)
                location = location_match.group(1) if location_match else "未知地点"
                
                record = f"{checkin_time}，状态: {status}，地点: {location}"
                checkin_records.append(record)
            
            # 如果没有找到智能签到记录，尝试查找其他打卡记录
            if not checkin_records:
                # 查找包含时间和签到/签退的记录
                time_check_pattern = r'text="(\d{2}:\d{2})"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                time_matches = re.findall(time_check_pattern, xml_content)
                
                for match in time_matches:
                    checkin_time = match[0]
                    # 查找附近的签到/签退文本
                    context_start = max(0, xml_content.find(match[0]) - 500)
                    context_end = min(len(xml_content), xml_content.find(match[0]) + 500)
                    context = xml_content[context_start:context_end]
                    
                    if '签到' in context:
                        record_type = "签到"
                    elif '签退' in context:
                        record_type = "签退"
                    else:
                        record_type = "打卡"
                    
                    record = f"{checkin_time} {record_type}"
                    checkin_records.append(record)
            
            # 去重
            checkin_records = list(set(checkin_records))
            
            return checkin_records
        except Exception as e:
            return []
    
    def run(self, user_confirm_callback=None):
        """运行打卡流程
        Args:
            user_confirm_callback: 回调函数，用于获取用户确认
        Returns:
            dict: 打卡结果
        """
        print("=== 开始打卡流程 ===")
        result = {
            "success": False,
            "message": "",
            "screenshots": {},
            "checkin_records": []
        }
        
        # 第一步：检查模拟器状态并启动
        if not self.check_emulator_status():
            if not self.start_emulator():
                result["message"] = "无法启动模拟器，流程终止"
                print(result["message"])
                return result
            time.sleep(10)  # 等待模拟器启动
        
        # 第二步：启动纷享销客
        if not self.start_fxiaoke():
            result["message"] = "无法启动纷享销客，流程终止"
            print(result["message"])
            return result
        
        # 第三步：进入考勤页面
        if not self.navigate_to_attendance():
            result["message"] = "无法进入考勤页面，流程终止"
            print(result["message"])
            return result
        
        # 检测打卡记录
        checkin_records = self.detect_checkin_records()
        result["checkin_records"] = checkin_records
        
        # 第四步：检查打卡状态
        screenshot_path = self.take_screenshot("before_checkin.png")
        if not screenshot_path:
            result["message"] = "无法截图，流程终止"
            print(result["message"])
            return result
        result["screenshots"]["before"] = screenshot_path
        
        location_status = self.check_location_status(screenshot_path)
        time_range = self.check_time_range()
        button_status = self.check_button_status()
        
        status_info = {
            "location": "已进入地点考勤范围" if location_status else "未进入地点考勤范围",
            "current_time": str(datetime.datetime.now().time()),
            "button_status": button_status,
            "checkin_records_count": len(checkin_records)
        }
        
        print(f"定位状态: {status_info['location']}")
        print(f"当前时间: {status_info['current_time']}")
        print(f"按钮状态: {status_info['button_status']}")
        print(f"打卡记录数量: {status_info['checkin_records_count']}")
        # 输出具体的打卡记录
        if checkin_records:
            print("打卡记录:")
            for i, record in enumerate(checkin_records):
                print(f"  {i+1}. {record}")
        
        # 检查是否可以打卡
        if not location_status:
            result["message"] = "未进入地点考勤范围，无法打卡"
            print(result["message"])
            return result
        
        if time_range == "out_of_range":
            result["success"] = True
            result["message"] = "当前时间不在打卡范围内，只汇报情况，不补签"
            print(result["message"])
            return result
        
        # 第五步：用户确认
        if user_confirm_callback:
            user_confirm = user_confirm_callback(status_info)
        else:
            # 命令行模式
            user_confirm = input("是否执行打卡？(y/n): ")
            user_confirm = user_confirm.lower() == 'y'
        
        if not user_confirm:
            result["message"] = "用户取消打卡"
            print(result["message"])
            return result
        
        # 第六步：执行打卡
        if time_range == "noon_checkin":
            # 中午需要签退1次+签到1次
            print("执行中午打卡流程: 签退1次 + 签到1次")
            # 第一次点击（签退）
            if not self.perform_checkin():
                result["message"] = "签退失败"
                print(result["message"])
                return result
            time.sleep(2)
            # 第二次点击（签到）
            if not self.perform_checkin():
                result["message"] = "签到失败"
                print(result["message"])
                return result
        else:
            # 其他时间只需要打卡1次
            if not self.perform_checkin():
                result["message"] = "打卡失败"
                print(result["message"])
                return result
        
        # 第七步：汇报结果
        time.sleep(2)
        result_screenshot = self.take_screenshot("after_checkin.png")
        result["screenshots"]["after"] = result_screenshot
        result["success"] = True
        result["message"] = f"打卡完成！结果截图已保存至: {result_screenshot}"
        print(result["message"])
        print("=== 打卡流程结束 ===")
        return result

# 供agent调用的接口
def run_checkin(user_confirm_callback=None):
    """运行打卡流程的入口函数
    Args:
        user_confirm_callback: 回调函数，用于获取用户确认
    Returns:
        dict: 打卡结果
    """
    skill = CheckinSkill()
    return skill.run(user_confirm_callback)

if __name__ == "__main__":
    run_checkin()