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
    
    def start_fxiaoke(self):
        """启动纷享销客应用"""
        print("启动纷享销客应用...")
        try:
            subprocess.run([self.adb_path, "shell", "am", "start", "-n", f"{self.package_name}/{self.activity_name}"], check=True)
            time.sleep(5)  # 等待应用启动
            return True
        except Exception as e:
            print(f"启动应用失败: {e}")
            return False
    
    def navigate_to_attendance(self):
        """进入考勤页面"""
        print("进入考勤页面...")
        try:
            # 点击底部导航栏的「应用」按钮（适配1440*2560分辨率）
            print("点击底部导航栏的「应用」按钮...")
            subprocess.run([self.adb_path, "shell", "input", "tap", "720", "2304"], check=True)
            time.sleep(2)
            
            # 截图应用页面，确认当前状态
            app_screenshot = os.path.join(self.screenshot_dir, "app_page.png")
            print(f"截图应用页面到: {app_screenshot}")
            subprocess.run([self.adb_path, "shell", "screencap", "/sdcard/app_screenshot.png"], check=True)
            subprocess.run([self.adb_path, "pull", "/sdcard/app_screenshot.png", app_screenshot], check=True)
            print(f"应用页面截图已保存至: {app_screenshot}")
            
            # 使用UIAutomator查找考勤选项
            print("使用UIAutomator查找考勤选项...")
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], check=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/window_dump.xml", xml_path], check=True)
            print(f"UIAutomator dump已保存至: {xml_path}")
            
            # 读取并分析XML文件
            try:
                with open(xml_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # 查找包含"考勤"的元素
                import re
                match = re.search(r'text=\"考勤\"[^>]+bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml_content)
                if match:
                    left = int(match.group(1))
                    top = int(match.group(2))
                    right = int(match.group(3))
                    bottom = int(match.group(4))
                    # 计算中心点坐标
                    x = (left + right) // 2
                    y = (top + bottom) // 2
                    print(f"找到考勤选项，坐标: ({x}, {y})")
                    
                    # 点击考勤选项
                    print(f"点击考勤选项，坐标: ({x}, {y})")
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True)
                    time.sleep(5)
                    
                    # 检查当前页面的Activity
                    print("检查当前页面的Activity...")
                    result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "top"], capture_output=True, text=True)
                    activity_lines = [line for line in result.stdout.split('\n') if 'ACTIVITY' in line]
                    print(f"当前Activity: {activity_lines}")
                    
                    # 检查是否成功进入考勤页面
                    if any('AttendanceActivity' in line for line in activity_lines):
                        print("成功进入考勤页面！")
                    else:
                        print("未成功进入考勤页面，尝试其他方法...")
                        # 尝试使用更精确的坐标点击
                        for offset in [(-20, -10), (0, -10), (20, -10), (-20, 0), (0, 0), (20, 0), (-20, 10), (0, 10), (20, 10)]:
                            offset_x = x + offset[0]
                            offset_y = y + offset[1]
                            print(f"尝试点击坐标: ({offset_x}, {offset_y})")
                            subprocess.run([self.adb_path, "shell", "input", "tap", str(offset_x), str(offset_y)], check=True)
                            time.sleep(3)
                            
                            # 检查当前页面的Activity
                            result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "top"], capture_output=True, text=True)
                            activity_lines = [line for line in result.stdout.split('\n') if 'ACTIVITY' in line]
                            print(f"当前Activity: {activity_lines}")
                            
                            if any('AttendanceActivity' in line for line in activity_lines):
                                print("成功进入考勤页面！")
                                break
                else:
                    print("未找到考勤选项，尝试直接使用坐标点击")
                    # 尝试使用更精确的坐标点击
                    for x in [480, 500, 520]:
                        for y in [180, 190, 200]:
                            print(f"尝试点击坐标: ({x}, {y})")
                            subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)], check=True)
                            time.sleep(2)
                            
                            # 检查当前页面的Activity
                            result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "top"], capture_output=True, text=True)
                            activity_lines = [line for line in result.stdout.split('\n') if 'ACTIVITY' in line]
                            print(f"当前Activity: {activity_lines}")
                            
                            if any('AttendanceActivity' in line for line in activity_lines):
                                print("成功进入考勤页面！")
                                break
                        if any('AttendanceActivity' in line for line in activity_lines):
                            break
            except Exception as xml_error:
                print(f"分析XML文件失败: {xml_error}")
                # 尝试使用预设坐标点击
                print("尝试使用预设坐标点击考勤选项...")
                preset_coordinates = [(480, 180), (500, 180), (520, 180), (480, 190), (500, 190), (520, 190), (480, 200), (500, 200), (520, 200)]
                for coord in preset_coordinates:
                    print(f"尝试点击坐标: ({coord[0]}, {coord[1]})")
                    subprocess.run([self.adb_path, "shell", "input", "tap", str(coord[0]), str(coord[1])], check=True)
                    time.sleep(2)
                    
                    # 检查当前页面的Activity
                    result = subprocess.run([self.adb_path, "shell", "dumpsys", "activity", "top"], capture_output=True, text=True)
                    activity_lines = [line for line in result.stdout.split('\n') if 'ACTIVITY' in line]
                    print(f"当前Activity: {activity_lines}")
                    
                    if any('AttendanceActivity' in line for line in activity_lines):
                        print("成功进入考勤页面！")
                        break
            
            # 截图当前页面
            test_screenshot = os.path.join(self.screenshot_dir, "test_attendance_page.png")
            print(f"截图当前页面到: {test_screenshot}")
            subprocess.run([self.adb_path, "shell", "screencap", "/sdcard/test_screenshot.png"], check=True)
            subprocess.run([self.adb_path, "pull", "/sdcard/test_screenshot.png", test_screenshot], check=True)
            print(f"截图已保存至: {test_screenshot}")
            
            return True
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
        # 这里需要实现UI元素识别，检查按钮状态
        # 暂时返回"签到"，实际使用时需要实现
        print("检查打卡按钮状态...")
        return "签到"
    
    def perform_checkin(self):
        """执行打卡操作"""
        print("执行打卡操作...")
        try:
            # 点击打卡按钮（适配1440*2560分辨率）
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
        print("检测考勤页面中的打卡记录...")
        try:
            # 使用UIAutomator dump界面层级
            subprocess.run([self.adb_path, "shell", "uiautomator", "dump", "/sdcard/attendance_dump.xml"], check=True)
            time.sleep(1)
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "attendance_dump.xml")
            subprocess.run([self.adb_path, "pull", "/sdcard/attendance_dump.xml", xml_path], check=True)
            
            # 读取并分析XML文件
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # 查找打卡记录
            import re
            # 查找包含打卡时间的元素
            time_patterns = [
                r'\d{2}:\d{2}',  # 时间格式，如 12:02
                r'\d{4}-\d{2}-\d{2}',  # 日期格式，如 2024-03-20
                r'签到',  # 签到
                r'签退',  # 签退
                r'正常',  # 正常状态
                r'迟到',  # 迟到状态
                r'早退'   # 早退状态
            ]
            
            checkin_records = []
            # 查找包含时间和状态的元素
            lines = xml_content.split('\n')
            for i, line in enumerate(lines):
                for pattern in time_patterns:
                    if re.search(pattern, line):
                        # 提取包含打卡信息的行
                        record = line.strip()
                        # 查找相邻的行，获取更多信息
                        if i > 0:
                            record += " " + lines[i-1].strip()
                        if i < len(lines) - 1:
                            record += " " + lines[i+1].strip()
                        checkin_records.append(record)
                        break
            
            # 去重
            checkin_records = list(set(checkin_records))
            
            print(f"检测到 {len(checkin_records)} 条打卡记录:")
            for i, record in enumerate(checkin_records):
                print(f"  {i+1}. {record}")
            
            return checkin_records
        except Exception as e:
            print(f"检测打卡记录失败: {e}")
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
        
        # 检查是否可以打卡
        if not location_status:
            result["message"] = "未进入地点考勤范围，无法打卡"
            print(result["message"])
            return result
        
        if time_range == "out_of_range":
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