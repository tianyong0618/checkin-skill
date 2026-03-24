#!/usr/bin/env python3
# 打卡Skill实现 - 供agent使用
import os
import time
import subprocess
import datetime
import re
import platform
import json
import functools

def retry(max_attempts=3, delay=2, backoff=1.5, exceptions=(Exception,)):
    """重试装饰器
    Args:
        max_attempts: 最大重试次数
        delay: 初始重试间隔（秒）
        backoff: 重试间隔增长因子
        exceptions: 需要捕获并重试的异常类型
    Returns:
        装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(self, *args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        print(f"{func.__name__} 执行失败，已达到最大重试次数: {e}")
                        raise
                    
                    print(f"{func.__name__} 执行失败，{attempts}/{max_attempts}，{current_delay}秒后重试: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

class CheckinSkill:
    def __init__(self):
        # 加载配置文件
        self.config = self.load_config()
        
        # 从配置中读取参数
        self.package_name = self.config['general']['package_name']
        self.activity_name = self.config['general']['activity_name']
        self.emulator_name = self.config['general']['emulator_name']
        
        # 确保截图目录在当前脚本所在目录
        screenshot_dir = self.config['general']['screenshot_dir']
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), screenshot_dir)
        
        self.adb_path = self.find_adb()  # 查找ADB路径
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # 清理临时文件
        self.cleanup_temp_files()
        
        # 初始化UI层级缓存
        self.ui_cache = {}
        self.cache_timestamp = 0
        self.cache_ttl = 15  # 延长缓存有效期到15秒
        self.cache_hits = 0
        self.cache_misses = 0
        self.file_cache = {}  # 文件拉取缓存
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        print("清理临时文件...")
        try:
            # 清理设备上的临时文件
            temp_files = ["/sdcard/window_dump.xml", "/sdcard/attendance_dump.xml", "/sdcard/screenshot.png"]
            for file_path in temp_files:
                try:
                    self.execute_adb_command(["shell", "rm", "-f", file_path], check=False)
                    print(f"清理设备临时文件: {file_path}")
                except Exception as e:
                    print(f"清理设备临时文件失败: {file_path}, {e}")
            
            # 清理本地截图目录中的旧文件（保留最近3天的文件）
            if os.path.exists(self.screenshot_dir):
                import datetime
                three_days_ago = datetime.datetime.now() - datetime.timedelta(days=3)
                
                # 统计清理前的文件数量和大小
                before_count = 0
                before_size = 0
                for filename in os.listdir(self.screenshot_dir):
                    file_path = os.path.join(self.screenshot_dir, filename)
                    if os.path.isfile(file_path):
                        before_count += 1
                        before_size += os.path.getsize(file_path)
                
                # 清理旧文件
                cleaned_count = 0
                cleaned_size = 0
                for filename in os.listdir(self.screenshot_dir):
                    file_path = os.path.join(self.screenshot_dir, filename)
                    if os.path.isfile(file_path):
                        file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_mtime < three_days_ago:
                            try:
                                file_size = os.path.getsize(file_path)
                                os.unlink(file_path)
                                print(f"清理旧截图: {filename} ({file_size / 1024:.1f}KB)")
                                cleaned_count += 1
                                cleaned_size += file_size
                            except Exception as e:
                                print(f"清理旧截图失败: {filename}, {e}")
                
                # 统计清理后的文件数量和大小
                after_count = before_count - cleaned_count
                after_size = before_size - cleaned_size
                print(f"截图目录清理完成: 清理前 {before_count} 个文件 ({before_size / 1024:.1f}KB)，清理后 {after_count} 个文件 ({after_size / 1024:.1f}KB)，清理了 {cleaned_count} 个文件 ({cleaned_size / 1024:.1f}KB)")
        except Exception as e:
            print(f"清理临时文件失败: {e}")
    
    def load_config(self):
        """加载配置文件
        Returns:
            dict: 配置信息
        """
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config/config.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            # 返回默认配置
            return self.get_default_config()
    
    def get_default_config(self):
        """获取默认配置
        Returns:
            dict: 默认配置
        """
        return {
            "general": {
                "package_name": "com.facishare.fs",
                "activity_name": "com.fxiaoke.host.IndexActivity",
                "emulator_name": "daka",
                "screenshot_dir": "../screenshots"
            },
            "adb": {
                "common_paths": [
                    "adb",
                    "/Users/tianyong/Library/Android/sdk/platform-tools/adb",
                    "~/Library/Android/sdk/platform-tools/adb",
                    "C:\\Users\\{USERNAME}\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe",
                    "/usr/local/share/android-sdk/platform-tools/adb"
                ]
            },
            "emulator": {
                "paths": {
                    "darwin": [
                        "~/Library/Android/sdk/emulator/emulator",
                        "/usr/local/share/android-sdk/emulator/emulator",
                        "/opt/android-sdk/emulator/emulator"
                    ],
                    "windows": [
                        "C:\\Users\\{USERNAME}\\AppData\\Local\\Android\\Sdk\\emulator\\emulator.exe",
                        "D:\\Android\\Sdk\\emulator\\emulator.exe"
                    ],
                    "linux": [
                        "~/Android/Sdk/emulator/emulator",
                        "/usr/local/android-sdk/emulator/emulator",
                        "/opt/android-sdk/emulator/emulator"
                    ]
                }
            },
            "coordinates": {
                "app_button": [
                    [900, 2304],
                    [950, 2304],
                    [1000, 2304],
                    [900, 2350],
                    [950, 2350],
                    [1000, 2350]
                ],
                "preset_attendance": [
                    [400, 100],
                    [450, 120],
                    [500, 140],
                    [550, 160],
                    [600, 180],
                    [650, 200],
                    [700, 100],
                    [750, 120],
                    [800, 140]
                ],
                "default_checkin": [720, 1280]
            },
            "time_ranges": {
                "morning_checkin": {
                    "start": "08:30",
                    "end": "09:00"
                },
                "noon_checkin": {
                    "start": "12:00",
                    "end": "13:00"
                },
                "evening_checkout": {
                    "start": "18:00",
                    "end": "19:00"
                }
            },
            "ui": {
                "texts": {
                    "attendance": "考勤",
                    "checkin": "签到",
                    "checkout": "签退",
                    "qixin": "企信",
                    "app": "应用"
                }
            },
            "sleep_times": {
                "emulator_start": 30,
                "app_start": 10,
                "monkey_activate": 5,
                "ui_dump": 1,
                "page_load": 3,
                "click_wait": 2,
                "checkin_wait": 5
            }
        }
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def execute_adb_command(self, command, capture_output=True, check=True):
        """执行ADB命令
        Args:
            command: 命令列表，如 ["devices"]
            capture_output: 是否捕获输出
            check: 是否检查返回码
        Returns:
            subprocess.CompletedProcess: 命令执行结果
        """
        full_command = [self.adb_path] + command
        try:
            print(f"执行ADB命令: {' '.join(full_command)}")
            result = subprocess.run(
                full_command,
                capture_output=capture_output,
                text=True,
                check=check
            )
            if capture_output and result.stdout:
                print(f"命令输出: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"ADB命令执行失败: {e}")
            if e.stdout:
                print(f"命令输出: {e.stdout}")
            if e.stderr:
                print(f"错误输出: {e.stderr}")
            raise
        except Exception as e:
            print(f"执行ADB命令时发生异常: {e}")
            raise
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def dump_ui_hierarchy(self, output_file="/sdcard/window_dump.xml"):
        """导出UI层级
        Args:
            output_file: 导出文件路径
        Returns:
            tuple: (bool, bool) - (是否成功, 是否使用了缓存)
        """
        # 检查缓存是否有效
        current_time = time.time()
        if output_file in self.ui_cache and (current_time - self.cache_timestamp) < self.cache_ttl:
            print(f"使用缓存的UI层级: {output_file}")
            self.cache_hits += 1
            return True, True
        
        # 执行dump操作
        print(f"导出UI层级到: {output_file}")
        result = self.execute_adb_command(["shell", "uiautomator", "dump", output_file])
        ui_dump_time = self.config['sleep_times'].get('ui_dump', 1)
        time.sleep(ui_dump_time)  # 等待导出完成
        
        # 更新缓存
        if result is not None:
            self.ui_cache[output_file] = True
            self.cache_timestamp = current_time
            self.cache_misses += 1
        
        return result is not None, False
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def pull_file(self, remote_path, local_path):
        """从设备拉取文件
        Args:
            remote_path: 设备上的文件路径
            local_path: 本地保存路径
        Returns:
            bool: 是否成功
        """
        # 检查文件缓存
        cache_key = f"file:{remote_path}:{local_path}"
        current_time = time.time()
        
        if cache_key in self.file_cache:
            cache_entry = self.file_cache[cache_key]
            if (current_time - cache_entry['timestamp']) < self.cache_ttl and os.path.exists(local_path):
                print(f"使用缓存的文件: {local_path}")
                self.cache_hits += 1
                return True
        
        try:
            print(f"从设备拉取文件: {remote_path} -> {local_path}")
            result = self.execute_adb_command(["pull", remote_path, local_path])
            if result:
                print(f"文件拉取成功: {local_path}")
                # 更新文件缓存
                self.file_cache[cache_key] = {
                    'timestamp': current_time,
                    'path': local_path
                }
                self.cache_misses += 1
                return True
            else:
                print("文件拉取失败: 命令执行失败")
                return False
        except Exception as e:
            print(f"拉取文件失败: {e}")
            return False
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def push_file(self, local_path, remote_path):
        """推送文件到设备
        Args:
            local_path: 本地文件路径
            remote_path: 设备上的保存路径
        Returns:
            bool: 是否成功
        """
        try:
            print(f"推送文件到设备: {local_path} -> {remote_path}")
            # 检查本地文件是否存在
            if not os.path.exists(local_path):
                print(f"推送文件失败: 本地文件不存在: {local_path}")
                return False
            
            result = self.execute_adb_command(["push", local_path, remote_path])
            if result:
                print(f"文件推送成功: {remote_path}")
                return True
            else:
                print("文件推送失败: 命令执行失败")
                return False
        except Exception as e:
            print(f"推送文件失败: {e}")
            return False
    
    def parse_ui_xml(self, xml_path):
        """解析UI XML文件
        Args:
            xml_path: XML文件路径
        Returns:
            str: XML内容
        """
        # 检查文件是否存在
        if not os.path.exists(xml_path):
            print(f"XML文件不存在: {xml_path}")
            return ""
        
        try:
            # 获取文件修改时间
            file_mtime = os.path.getmtime(xml_path)
            
            # 检查缓存是否有效
            if xml_path in self.ui_cache and isinstance(self.ui_cache[xml_path], dict) and self.ui_cache[xml_path]['mtime'] == file_mtime:
                print(f"使用缓存的XML内容: {xml_path}")
                self.cache_hits += 1
                return self.ui_cache[xml_path]['content']
            
            # 读取文件内容
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新缓存
            self.ui_cache[xml_path] = {
                'content': content,
                'mtime': file_mtime
            }
            self.cache_misses += 1
            
            return content
        except Exception as e:
            print(f"解析XML文件失败: {e}")
            return ""
    
    def find_element_by_text(self, xml_content, text):
        """根据文本查找元素
        Args:
            xml_content: XML内容
            text: 元素文本
        Returns:
            tuple: (left, top, right, bottom) 或 None
        """
        # 缓存查找结果，避免重复查找
        cache_key = f"find_element:{text}"
        if cache_key in self.ui_cache and isinstance(self.ui_cache[cache_key], tuple):
            print(f"使用缓存的元素位置: {text}")
            return self.ui_cache[cache_key]
        
        try:
            pattern = r'text="' + re.escape(text) + r'"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            match = re.search(pattern, xml_content)
            if match:
                bounds = (int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)))
                # 缓存查找结果
                self.ui_cache[cache_key] = bounds
                return bounds
            return None
        except Exception as e:
            print(f"查找元素失败: {e}")
            return None
    
    def find_element_by_pattern(self, xml_content, pattern):
        """根据正则模式查找元素
        Args:
            xml_content: XML内容
            pattern: 正则表达式模式
        Returns:
            list: 匹配结果列表
        """
        try:
            matches = re.findall(pattern, xml_content)
            return matches
        except Exception as e:
            print(f"查找元素失败: {e}")
            return []
    
    def get_element_center(self, bounds):
        """计算元素中心点坐标
        Args:
            bounds: (left, top, right, bottom)
        Returns:
            tuple: (x, y)
        """
        if bounds:
            left, top, right, bottom = bounds
            return ((left + right) // 2, (top + bottom) // 2)
        return None
    
    def wait_for_element(self, text, timeout=30, interval=0.5):
        """等待元素出现
        Args:
            text: 元素文本
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
        Returns:
            tuple: (left, top, right, bottom) 或 None
        """
        start_time = time.time()
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        
        while time.time() - start_time < timeout:
            try:
                # 导出UI层级（会使用缓存）
                self.dump_ui_hierarchy()
                
                # 拉取XML文件到本地
                self.pull_file("/sdcard/window_dump.xml", xml_path)
                
                # 读取并分析XML文件（会使用缓存）
                xml_content = self.parse_ui_xml(xml_path)
                
                # 查找元素
                bounds = self.find_element_by_text(xml_content, text)
                if bounds:
                    return bounds
                
                # 动态调整间隔，随着时间增加减少间隔
                elapsed = time.time() - start_time
                if elapsed < timeout * 0.5:
                    time.sleep(interval)
                else:
                    # 接近超时，减少间隔以提高响应速度
                    time.sleep(interval / 2)
            except Exception as e:
                print(f"等待元素时出错: {e}")
                time.sleep(interval)
        
        print(f"等待元素 '{text}' 超时")
        return None
    
    def take_screenshot(self, filename):
        """截图
        Args:
            filename: 保存文件名
        Returns:
            str: 保存路径或None
        """
        # 检查截图配置
        screenshot_config = self.config.get('screenshot', {})
        enabled = screenshot_config.get('enabled', False)
        debug = screenshot_config.get('debug', True)
        compress = screenshot_config.get('compress', True)
        quality = screenshot_config.get('quality', 50)
        
        # 如果截图未启用且不是debug模式，直接返回
        if not enabled and not debug:
            print(f"截图已禁用，跳过: {filename}")
            return None
        
        try:
            filepath = os.path.join(self.screenshot_dir, filename)
            # 截图到设备
            self.execute_adb_command(["shell", "screencap", "/sdcard/screenshot.png"])
            # 拉取到本地
            self.execute_adb_command(["pull", "/sdcard/screenshot.png", filepath])
            
            # 压缩截图
            if compress:
                try:
                    from PIL import Image
                    img = Image.open(filepath)
                    # 将RGBA转换为RGB格式
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    # 压缩图片
                    img.save(filepath, 'JPEG', quality=quality)
                    print(f"截图已压缩并保存: {filepath}")
                except ImportError:
                    print("Pillow库未安装，跳过压缩")
                except Exception as e:
                    print(f"压缩截图失败: {e}")
                    # 尝试使用PNG格式保存
                    try:
                        if 'img' in locals():
                            # 尝试使用PNG格式保存
                            png_path = filepath.replace('.png', '.png')
                            img.save(png_path, 'PNG')
                            print(f"使用PNG格式保存截图: {png_path}")
                        else:
                            print("无法使用PNG格式保存，图片对象不存在")
                    except Exception as e2:
                        print(f"保存PNG格式失败: {e2}")
                        # 尝试不压缩，直接使用原始截图
                        print("使用原始截图，跳过压缩")
            else:
                print(f"截图已保存: {filepath}")
            
            return filepath
        except Exception as e:
            print(f"截图失败: {e}")
            return None
    
    def find_adb(self):
        """查找ADB工具路径"""
        # 从配置中读取ADB路径列表
        common_paths = self.config['adb']['common_paths']
        
        for path in common_paths:
            # 替换{USERNAME}占位符
            if "{USERNAME}" in path:
                path = path.format(USERNAME=os.getenv("USERNAME", ""))
            
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
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def check_emulator_status(self):
        """检查模拟器状态"""
        print("检查模拟器状态...")
        if not self.check_adb_available():
            print("ADB不可用，请确保ADB已安装")
            return False
        
        # 缓存设备状态，避免重复执行ADB命令
        if hasattr(self, '_device_status') and (time.time() - self._device_status['timestamp']) < 5:
            print(f"使用缓存的设备状态: {self._device_status['devices']}")
            return len(self._device_status['devices']) > 0
        
        result = self.execute_adb_command(["devices"])
        if result:
            devices = result.stdout.strip().split('\n')[1:]
            running_devices = [device.split('\t')[0] for device in devices if 'device' in device]
            
            # 缓存设备状态
            self._device_status = {
                'devices': running_devices,
                'timestamp': time.time()
            }
            
            if running_devices:
                print(f"发现运行中的设备: {running_devices}")
                return True
            else:
                print("未发现运行中的设备")
                return False
        return False
    
    def start_emulator(self):
        """启动模拟器"""
        print("启动模拟器...")
        try:
            # 查找emulator命令路径
            emulator_path = None
            system = platform.system().lower()
            
            # 从配置中获取对应系统的模拟器路径
            possible_paths = self.config['emulator']['paths'].get(system, [])
            
            for path in possible_paths:
                # 替换{USERNAME}占位符
                if "{USERNAME}" in path:
                    path = path.format(USERNAME=os.getenv("USERNAME", ""))
                
                # 展开~符号
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
            emulator_start_time = self.config['sleep_times'].get('emulator_start', 30)
            time.sleep(emulator_start_time)  # 给模拟器足够的启动时间
            
            # 再次检查模拟器状态
            return self.check_emulator_status()
        except Exception as e:
            print(f"启动模拟器失败: {e}")
            return False
    
    def is_app_running(self):
        """检查应用是否已经在运行"""
        # 缓存应用运行状态，避免重复执行ADB命令
        if hasattr(self, '_app_running_status') and (time.time() - self._app_running_status['timestamp']) < 3:
            print(f"使用缓存的应用运行状态: {self._app_running_status['running']}")
            return self._app_running_status['running']
        
        try:
            result = self.execute_adb_command(["shell", "dumpsys", "activity", "activities"])
            running = False
            if result:
                running = self.package_name in result.stdout
            
            # 缓存应用运行状态
            self._app_running_status = {
                'running': running,
                'timestamp': time.time()
            }
            
            return running
        except Exception as e:
            print(f"检查应用运行状态失败: {e}")
            return False
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def start_fxiaoke(self):
        """启动纷享销客应用"""
        print("启动纷享销客应用...")
        
        # 检查应用是否已经在运行
        if self.is_app_running():
            print("应用已经在运行，无需重新启动")
            return True
        
        # 尝试解锁屏幕（如果锁屏）
        self.execute_adb_command(["shell", "input", "keyevent", "82"])
        time.sleep(1)
        
        # 使用 -a 参数和 -f 参数确保应用在前台启动
        self.execute_adb_command(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-n", f"{self.package_name}/{self.activity_name}", "-f", "0x10000000"])
        
        # 使用基于事件的等待机制，等待应用启动
        print("等待应用启动...")
        start_time = time.time()
        timeout = self.config['sleep_times'].get('app_start', 8)  # 减少超时时间
        interval = 0.5  # 减少检查间隔
        
        while time.time() - start_time < timeout:
            if self.is_app_running():
                print("应用已成功启动")
                break
            # 动态调整间隔
            elapsed = time.time() - start_time
            if elapsed < timeout * 0.5:
                time.sleep(interval)
            else:
                time.sleep(interval / 2)
        
        # 尝试使用 monkey 命令激活应用
        self.execute_adb_command(["shell", "monkey", "-p", self.package_name, "-c", "android.intent.category.LAUNCHER", "1"])
        
        # 等待应用完全激活（减少等待时间）
        time.sleep(self.config['sleep_times'].get('monkey_activate', 2))
        
        # 模拟点击屏幕，确保应用在前台
        self.execute_adb_command(["shell", "input", "tap", "500", "500"])
        time.sleep(self.config['sleep_times'].get('click_wait', 1))  # 减少等待时间
        
        return True
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def navigate_to_attendance(self):
        """进入考勤页面"""
        print("进入考勤页面...")
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        
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
            self.execute_adb_command(["shell", "screencap", "/sdcard/app_screenshot.png"])
            self.execute_adb_command(["pull", "/sdcard/app_screenshot.png", app_screenshot])
            
            # 使用UIAutomator查找考勤选项（只dump一次）
            success, used_cache = self.dump_ui_hierarchy()
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            xml_content = self.parse_ui_xml(xml_path)
            
            # 检查是否是企信页面（首页），如果是，先点击"应用"按钮
            qixin_text = self.config['ui']['texts']['qixin']
            if qixin_text in xml_content:
                print(f"当前是{qixin_text}页面，点击应用按钮...")
                # 尝试使用基于UI元素的定位找到应用按钮
                app_text = self.config['ui']['texts']['app']
                app_bounds = self.find_element_by_text(xml_content, app_text)
                
                if app_bounds:
                    # 使用UI元素定位
                    x, y = self.get_element_center(app_bounds)
                    print(f"找到应用按钮，坐标: ({x}, {y})")
                    self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                    time.sleep(3)
                else:
                    # 备用方案：使用配置的坐标
                    app_button_coordinates = self.config['coordinates']['app_button']
                    for coord in app_button_coordinates:
                        x, y = coord
                        print(f"尝试点击应用按钮，坐标: ({x}, {y})")
                        self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                        # 动态等待，根据操作类型调整等待时间
                        time.sleep(self.config['sleep_times'].get('click_wait', 1))
                        
                        # 不立即检查，减少dump次数
            
            # 等待应用页面加载
            time.sleep(self.config['sleep_times'].get('page_load', 3))
            
            # 再次dump界面层级，查找考勤选项
            success, used_cache = self.dump_ui_hierarchy()
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            xml_content = self.parse_ui_xml(xml_path)
            
            # 查找包含"考勤"的元素
            attendance_text = self.config['ui']['texts']['attendance']
            attendance_bounds = self.find_element_by_text(xml_content, attendance_text)
            
            if attendance_bounds:
                # 计算中心点坐标
                x, y = self.get_element_center(attendance_bounds)
                
                # 点击考勤选项
                self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                checkin_wait_time = self.config['sleep_times'].get('checkin_wait', 5)
                time.sleep(checkin_wait_time)
                
                # 再次检查页面状态，看是否已经进入考勤页面
                current_status = self.check_page_status()
                if current_status != 'attendance':
                    # 尝试使用更精确的坐标点击
                    offsets = self.config['ui']['offsets']
                    for offset in offsets:
                        offset_x = x + offset[0]
                        offset_y = y + offset[1]
                        self.execute_adb_command(["shell", "input", "tap", str(offset_x), str(offset_y)])
                        time.sleep(3)
                        
                        # 再次检查页面状态
                        current_status = self.check_page_status()
                        if current_status == 'attendance':
                            break
            else:
                # 尝试使用更精确的坐标点击，重点点击顶部区域
                current_status = 'home'
                attendance_coords = self.config['ui']['attendance_coordinates']
                x_coords = attendance_coords['x']
                y_coords = attendance_coords['y']
                
                for x in x_coords:
                    for y in y_coords:
                        self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                        time.sleep(2)
                        
                        # 再次检查页面状态，看是否已经进入考勤页面
                        current_status = self.check_page_status()
                        if current_status == 'attendance':
                            break
                    if current_status == 'attendance':
                        break
        elif page_status == 'attendance':
            # 已经是考勤页面，直接进行日期检查
            print("当前已经是考勤页面")
        
        # 截图当前页面
        test_screenshot = self.take_screenshot("test_attendance_page.png")
        print(f"截图当前页面到: {test_screenshot}")
        print(f"截图已保存至: {test_screenshot}")
        
        # 再次检查页面状态，确保最终在考勤页面
        final_status = self.check_page_status()
        if final_status == 'attendance':
            print("导航到考勤页面成功！")
            return True
        else:
            print(f"最终页面状态不是考勤页面，导航失败: {final_status}")
            return False
    
    def check_location_status(self, screenshot_path):
        """检查定位状态
        Args:
            screenshot_path: 截图路径
        Returns:
            bool: 是否已进入地点考勤范围
        """
        print("检查定位状态...")
        try:
            # 尝试通过ADB获取定位信息
            result = self.execute_adb_command(["shell", "settings", "get", "secure", "location_providers_allowed"])
            if result and "gps" in result.stdout.lower():
                print("定位服务已开启")
            else:
                print("定位服务未开启")
            
            # 尝试通过UI元素检查是否显示「已进入地点考勤范围」
            self.dump_ui_hierarchy()
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            self.pull_file("/sdcard/window_dump.xml", xml_path)
            xml_content = self.parse_ui_xml(xml_path)
            
            location_in_range = self.config['ui']['texts']['location_in_range']
            location_out_of_range = self.config['ui']['texts']['location_out_of_range']
            
            if location_in_range in xml_content:
                print(location_in_range)
                return True
            elif location_out_of_range in xml_content:
                print(location_out_of_range)
                return False
            else:
                print("无法确定定位状态，默认返回True")
                return True
        except Exception as e:
            print(f"检查定位状态失败: {e}")
            return True
    
    def check_time_range(self):
        """检查当前时间是否在允许的打卡时间段内"""
        now = datetime.datetime.now()
        current_time = now.time()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        print(f"当前时间: {current_time}")
        
        # 从配置中读取时间范围
        time_ranges = self.config['time_ranges']
        
        # 解析时间范围
        def parse_time(time_str):
            hour, minute = map(int, time_str.split(':'))
            return hour, minute
        
        # 早上上班签到
        morning_start = parse_time(time_ranges['morning_checkin']['start'])
        morning_end = parse_time(time_ranges['morning_checkin']['end'])
        if (current_hour == morning_start[0] and current_minute >= morning_start[1]) or \
           (current_hour == morning_end[0] and current_minute == morning_end[1]):
            return "morning_checkin"
        
        # 中午午休打卡
        noon_start = parse_time(time_ranges['noon_checkin']['start'])
        noon_end = parse_time(time_ranges['noon_checkin']['end'])
        if (current_hour == noon_start[0] and current_minute >= noon_start[1]) or \
           (current_hour == noon_end[0] and current_minute == noon_end[1]):
            return "noon_checkin"
        
        # 晚上下班签退
        evening_start = parse_time(time_ranges['evening_checkout']['start'])
        evening_end = parse_time(time_ranges['evening_checkout']['end'])
        if (current_hour == evening_start[0] and current_minute >= evening_start[1]) or \
           (current_hour == evening_end[0] and current_minute == evening_end[1]):
            return "evening_checkout"
        
        else:
            return "out_of_range"
    
    def check_button_status(self):
        """检查打卡按钮状态"""
        print("检查打卡按钮状态...")
        try:
            # 使用UIAutomator dump界面层级
            self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 读取并分析XML文件
            xml_content = self.parse_ui_xml(xml_path)
            
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
            result = self.execute_adb_command(["shell", "dumpsys", "activity", "top"])
            if result:
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
            result = self.execute_adb_command(["shell", "dumpsys", "activity", "activities"])
            if result:
                # 查找最新的Activity
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if 'Running activities' in line:
                        # 查找第一个Activity
                        for j in range(i+1, len(lines)):
                            if 'ActivityRecord' in lines[j]:
                                match = re.search(r'ActivityRecord\{[^\}]+\} ([^\s]+)', lines[j])
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
        # 缓存页面状态，避免重复执行ADB命令
        if hasattr(self, '_page_status') and (time.time() - self._page_status['timestamp']) < 5:
            print(f"使用缓存的页面状态: {self._page_status['status']}")
            return self._page_status['status']
        
        # 直接使用UIAutomator判断页面状态，减少对Activity的依赖
        try:
            # 使用UIAutomator dump界面层级（会使用缓存）
            success, used_cache = self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地（如果没有使用缓存）
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 读取并分析XML文件（会使用缓存）
            xml_content = self.parse_ui_xml(xml_path)
            
            # 检查是否是纷享销客应用
            if 'com.facishare.fs' in xml_content:
                # 检查是否包含考勤相关的文本，并且包含打卡时间、状态等考勤页面特有的元素
                if '考勤' in xml_content and ('智能签到' in xml_content or '签退' in xml_content or '已进入地点考勤范围' in xml_content):
                    status = 'attendance'
                
                # 检查是否是应用页面
                elif '应用' in xml_content and '考勤' in xml_content:
                    status = 'home'
                
                # 检查是否是企信页面（首页）
                elif '企信' in xml_content:
                    status = 'home'
                
                # 其他纷享销客页面
                else:
                    status = 'other'
            else:
                status = 'other'
            
            # 缓存页面状态
            self._page_status = {
                'status': status,
                'timestamp': time.time()
            }
            
            return status
        except Exception as e:
            print(f"检查页面状态失败: {e}")
            return 'other'
    
    def go_to_home(self):
        """回到首页"""
        print("回到首页...")
        try:
            # 使用am start命令启动首页Activity
            self.execute_adb_command(["shell", "am", "start", "-n", f"{self.package_name}/{self.activity_name}"])
            time.sleep(3)  # 等待页面加载
            print("成功回到首页")
            return True
        except Exception as e:
            print(f"回到首页失败: {e}")
            return False
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def perform_checkin(self):
        """执行打卡操作"""
        print("执行打卡操作...")
        # 使用UIAutomator dump界面层级，找到实际的打卡按钮位置
        self.dump_ui_hierarchy()
        
        # 拉取XML文件到本地
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        self.pull_file("/sdcard/window_dump.xml", xml_path)
        
        # 读取并分析XML文件，查找打卡按钮
        xml_content = self.parse_ui_xml(xml_path)
        
        # 查找包含"签到"或"签退"的按钮
        match = re.search(r'text="(签到|签退)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml_content)
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
            self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
            time.sleep(2)
            return True
        else:
            # 如果没有找到按钮，使用默认坐标
            print("未找到打卡按钮，使用默认坐标")
            default_checkin = self.config['coordinates']['default_checkin']
            self.execute_adb_command(["shell", "input", "tap", str(default_checkin[0]), str(default_checkin[1])])
            click_wait_time = self.config['sleep_times'].get('click_wait', 2)
            time.sleep(click_wait_time)
            return True
    
    def check_attendance_date(self):
        """检查考勤页面显示的日期是否为当天
        Returns:
            bool: 是否为当天日期
        """
        print("检查考勤页面日期...")
        try:
            # 使用UIAutomator dump界面层级
            self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 读取并分析XML文件
            xml_content = self.parse_ui_xml(xml_path)
            
            # 获取当前日期
            today = datetime.datetime.now()
            today_str = today.strftime("%m月%d日")
            # 移除前导零
            today_str = today_str.lstrip('0')
            
            print(f"当前日期: {today_str}")
            
            # 查找页面中的日期信息，只匹配日期数字部分
            date_pattern = r'(\d+月\d+日)'
            date_match = re.search(date_pattern, xml_content)
            
            if date_match:
                date_str = date_match.group(1)
                
                print(f"页面显示日期: {date_str}")
                
                # 检查是否为当天日期
                if date_str == today_str:
                    print("页面显示的是当天日期")
                    return True
                else:
                    print("页面显示的不是当天日期")
                    return False
            else:
                print("未找到日期信息")
                return False
        except Exception as e:
            print(f"检查日期时出错: {e}")
            return False
    
    def detect_checkin_records(self):
        """检测考勤页面中的打卡记录
        Returns:
            list: 打卡记录列表
        """
        try:
            # 直接使用当前页面，不滚动避免影响内容
            print("检测打卡记录...")
            
            # 使用UIAutomator dump界面层级
            success, used_cache = self.dump_ui_hierarchy("/sdcard/attendance_dump.xml")
            
            # 拉取XML文件到本地（如果没有使用缓存）
            xml_path = os.path.join(self.screenshot_dir, "attendance_dump.xml")
            if not used_cache:
                self.pull_file("/sdcard/attendance_dump.xml", xml_path)
            
            # 读取并分析XML文件
            xml_content = self.parse_ui_xml(xml_path)
            
            # 查找打卡记录
            import re
            
            checkin_records = []
            
            # 查找所有包含打卡信息的节点（使用更精确的匹配）
            checkin_pattern = r'text="(\d{2}:\d{2} (智能签到|签到|签退))"[^>]+resource-id="com\.facishare\.fs:id/check_time"'
            checkin_matches = re.findall(checkin_pattern, xml_content)
            
            print(f"找到的打卡记录匹配: {checkin_matches}")
            
            # 处理所有找到的打卡类型
            for match in checkin_matches:
                checkin_text = match[0]
                record_type = match[1]
                
                # 提取时间
                time_match = re.search(r'(\d{2}:\d{2})', checkin_text)
                if time_match:
                    checkin_time = time_match.group(1)
                    
                    # 查找对应的状态（在同一父节点中查找）
                    status_pattern = r'text="(正常|迟到|早退)"[^>]+resource-id="com\.facishare\.fs:id/check_status_1"'
                    status_match = re.search(status_pattern, xml_content)
                    status = status_match.group(1) if status_match else "未知"
                    
                    # 查找对应的地点
                    location_pattern = r'text="([^"\n]+)"[^>]+resource-id="com\.facishare\.fs:id/check_text"'
                    location_match = re.search(location_pattern, xml_content)
                    location = location_match.group(1) if location_match else "未知地点"
                    
                    record = f"{checkin_time} {record_type}，状态: {status}，地点: {location}"
                    checkin_records.append(record)
            
            # 去重
            checkin_records = list(set(checkin_records))
            
            print(f"最终打卡记录: {checkin_records}")
            return checkin_records
        except Exception as e:
            print(f"检测打卡记录时出错: {e}")
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
        
        # 检查考勤页面日期是否为当天
        max_retries = 3
        retry_count = 0
        is_today = False
        
        while retry_count < max_retries and not is_today:
            is_today = self.check_attendance_date()
            if not is_today:
                print("页面显示的不是当天日期，尝试切换到当天...")
                # 尝试下拉刷新
                self.execute_adb_command(["shell", "input", "swipe", "720", "500", "720", "1500", "1000"])
                time.sleep(3)
                
                # 查找并点击"下一天"按钮
                self.dump_ui_hierarchy()
                xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
                self.pull_file("/sdcard/window_dump.xml", xml_path)
                xml_content = self.parse_ui_xml(xml_path)
                
                # 查找"the_next_day"按钮
                next_day_pattern = r'resource-id="com\.facishare\.fs:id/the_next_day"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                next_day_match = re.search(next_day_pattern, xml_content)
                
                if next_day_match:
                    left = int(next_day_match.group(1))
                    top = int(next_day_match.group(2))
                    right = int(next_day_match.group(3))
                    bottom = int(next_day_match.group(4))
                    # 点击下一天按钮
                    x = (left + right) // 2
                    y = (top + bottom) // 2
                    print(f"点击下一天按钮，坐标: ({x}, {y})")
                    self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                    time.sleep(3)
                else:
                    # 如果没有找到下一天按钮，尝试点击日期文本区域
                    date_text_pattern = r'resource-id="com\.facishare\.fs:id/date_text"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                    date_text_match = re.search(date_text_pattern, xml_content)
                    if date_text_match:
                        left = int(date_text_match.group(1))
                        top = int(date_text_match.group(2))
                        right = int(date_text_match.group(3))
                        bottom = int(date_text_match.group(4))
                        # 点击日期文本
                        x = (left + right) // 2
                        y = (top + bottom) // 2
                        print(f"点击日期文本，坐标: ({x}, {y})")
                        self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                        time.sleep(2)
                        
                        # 尝试点击"今天"选项
                        self.dump_ui_hierarchy()
                        self.pull_file("/sdcard/window_dump.xml", xml_path)
                        xml_content = self.parse_ui_xml(xml_path)
                        
                        today_bounds = self.find_element_by_text(xml_content, "今天")
                        if today_bounds:
                            x, y = self.get_element_center(today_bounds)
                            print(f"点击今天选项，坐标: ({x}, {y})")
                            self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                            time.sleep(3)
                
                retry_count += 1
        
        if not is_today:
            result["message"] = "无法切换到当天日期，流程终止"
            print(result["message"])
            return result
        
        # 检测打卡记录
        checkin_records = self.detect_checkin_records()
        result["checkin_records"] = checkin_records
        
        # 第四步：检查打卡状态
        screenshot_path = self.take_screenshot("before_checkin.png")
        if screenshot_path:
            result["screenshots"]["before"] = screenshot_path
        else:
            print("截图已禁用，跳过截图操作")
        
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
        # 只在需要时输出打卡记录，避免与消息中的记录重复
        if time_range != "out_of_range" and checkin_records:
            print("打卡记录:")
            for i, record in enumerate(checkin_records):
                print(f"  {i+1}. {record}")
        
        # 检查是否可以打卡
        if not location_status:
            result["message"] = "未进入地点考勤范围，无法打卡"
            print(result["message"])
            return result
        
        # 构建包含打卡记录的消息
        def build_message(base_message):
            """构建包含打卡记录的消息"""
            message = base_message
            if checkin_records:
                message += "\n最新打卡记录:"
                for i, record in enumerate(checkin_records):
                    message += f"\n  {i+1}. {record}"
            return message
        
        if time_range == "out_of_range":
            result["success"] = True
            result["message"] = build_message("当前时间不在打卡范围内，只汇报情况，不补签")
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
            result["message"] = build_message("用户取消打卡")
            print(result["message"])
            return result
        
        # 第六步：执行打卡
        if time_range == "noon_checkin":
            # 中午需要签退1次+签到1次
            print("执行中午打卡流程: 签退1次 + 签到1次")
            # 第一次点击（签退）
            if not self.perform_checkin():
                result["message"] = build_message("签退失败")
                print(result["message"])
                return result
            time.sleep(2)
            # 第二次点击（签到）
            if not self.perform_checkin():
                result["message"] = build_message("签到失败")
                print(result["message"])
                return result
        else:
            # 其他时间只需要打卡1次
            if not self.perform_checkin():
                result["message"] = build_message("打卡失败")
                print(result["message"])
                return result
        
        # 第七步：汇报结果
        time.sleep(2)
        result_screenshot = self.take_screenshot("after_checkin.png")
        result["screenshots"]["after"] = result_screenshot
        result["success"] = True
        # 重新检测打卡记录，确保显示最新的
        updated_checkin_records = self.detect_checkin_records()
        if updated_checkin_records:
            checkin_records = updated_checkin_records
        result["message"] = build_message(f"打卡完成！结果截图已保存至: {result_screenshot}")
        # 输出缓存统计信息
        total_cache = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache * 100) if total_cache > 0 else 0
        print(f"缓存统计: 命中={self.cache_hits}, 未命中={self.cache_misses}, 命中率={cache_hit_rate:.1f}%")
        
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