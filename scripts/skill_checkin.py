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
import requests

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
                        self.log('error', f"{func.__name__} 执行失败，已达到最大重试次数: {e}")
                        raise
                    
                    self.log('warning', f"{func.__name__} 执行失败，{attempts}/{max_attempts}，{current_delay}秒后重试: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

def handle_exception(default_return=None, log_level='error'):
    """异常处理装饰器
    Args:
        default_return: 异常发生时的默认返回值
        log_level: 日志级别
    Returns:
        装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                self.log(log_level, f"{func.__name__} 执行失败: {e}")
                return default_return
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
        
        # 日志级别设置
        self.log_level = self.config.get('log', {}).get('level', 'info')  # 默认info级别
        self.log_levels = {
            'debug': 0,
            'info': 1,
            'warning': 2,
            'error': 3
        }
        
        # 清理临时文件
        self.cleanup_temp_files()
        
        # 初始化缓存系统
        self.cache = {
            'ui': {},  # UI层级缓存
            'file': {},  # 文件拉取缓存
            'status': {}  # 状态缓存（如页面状态、设备状态等）
        }
        self.cache_ttl = 15  # 缓存有效期（秒）
        self.cache_stats = {
            'hits': 0,
            'misses': 0
        }
    
    def log(self, level, message):
        """日志输出方法
        Args:
            level: 日志级别，可选值：debug, info, warning, error
            message: 日志消息
        """
        if self.log_levels.get(level, 1) >= self.log_levels.get(self.log_level, 1):
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level.upper()}] {message}")

    def clear_cache(self, cache_type=None):
        """清除缓存
        Args:
            cache_type: 缓存类型，可选值：'ui', 'file', 'status'，默认清除所有缓存
        """
        if cache_type:
            if cache_type in self.cache:
                self.log('info', f"清除{cache_type}缓存...")
                self.cache[cache_type].clear()
                self.log('info', f"{cache_type}缓存已清除")
            else:
                self.log('warning', f"未知的缓存类型: {cache_type}")
        else:
            self.log('info', "清除所有缓存...")
            for cache_name in self.cache:
                self.cache[cache_name].clear()
            self.log('info', "缓存已清除")
    
    @handle_exception(default_return=None, log_level='warning')
    def cleanup_temp_files(self):
        """清理临时文件"""
        self.log('info', "清理临时文件...")
        
        # 清理设备上的临时文件
        temp_files = ["/sdcard/window_dump.xml", "/sdcard/attendance_dump.xml", "/sdcard/screenshot.png"]
        for file_path in temp_files:
            try:
                self.execute_adb_command(["shell", "rm", "-f", file_path], check=False)
                self.log('debug', f"清理设备临时文件: {file_path}")
            except Exception as e:
                self.log('warning', f"清理设备临时文件失败: {file_path}, {e}")
        
        # 清理本地截图目录中的旧文件（保留最近3天的文件）
        if os.path.exists(self.screenshot_dir):
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
                            self.log('info', f"清理旧截图: {filename} ({file_size / 1024:.1f}KB)")
                            cleaned_count += 1
                            cleaned_size += file_size
                        except Exception as e:
                            self.log('warning', f"清理旧截图失败: {filename}, {e}")
            
            # 统计清理后的文件数量和大小
            after_count = before_count - cleaned_count
            after_size = before_size - cleaned_size
            self.log('info', f"截图目录清理完成: 清理前 {before_count} 个文件 ({before_size / 1024:.1f}KB)，清理后 {after_count} 个文件 ({after_size / 1024:.1f}KB)，清理了 {cleaned_count} 个文件 ({cleaned_size / 1024:.1f}KB)")
    
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
    
    def get_config(self, path, default=None):
        """获取配置值
        Args:
            path: 配置路径，如 "general.package_name"
            default: 默认值
        Returns:
            配置值
        """
        keys = path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
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
            },
            "screenshot": {
                "enabled": False,
                "debug": True,
                "compress": True,
                "quality": 50
            }
        }
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def execute_adb_command(self, command, capture_output=True, check=True, verbose=False):
        """执行ADB命令
        Args:
            command: 命令列表，如 ["devices"]
            capture_output: 是否捕获输出
            check: 是否检查返回码
            verbose: 是否输出详细日志
        Returns:
            subprocess.CompletedProcess: 命令执行结果
        """
        full_command = [self.adb_path] + command
        try:
            # 只在verbose模式下输出详细日志
            if verbose:
                self.log('debug', f"执行ADB命令: {' '.join(full_command)}")
            result = subprocess.run(
                full_command,
                capture_output=capture_output,
                text=True,
                check=check
            )
            # 只在verbose模式下输出命令输出
            if verbose and capture_output and result.stdout:
                self.log('debug', f"命令输出: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log('error', f"ADB命令执行失败: {e}")
            if e.stdout:
                self.log('debug', f"命令输出: {e.stdout}")
            if e.stderr:
                self.log('debug', f"错误输出: {e.stderr}")
            raise
        except Exception as e:
            self.log('error', f"执行ADB命令时发生异常: {e}")
            raise
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def clear_ui_cache(self, file_path="/sdcard/window_dump.xml"):
        """清除指定的UI缓存
        Args:
            file_path: 要清除的缓存文件路径
        """
        # 清除UI缓存
        self.cache['ui'].pop(file_path, None)
        # 清除相关的文件缓存
        for key in list(self.cache['file'].keys()):
            if os.path.basename(file_path) in key:
                self.cache['file'].pop(key, None)

    def wait_for_element(self, text, timeout=10, check_interval=1):
        """等待特定UI元素出现
        Args:
            text: 要等待的元素文本
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
        Returns:
            bool: 是否在超时前找到元素
        """
        start_time = time.time()
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        
        while time.time() - start_time < timeout:
            # 导出UI层级
            success, used_cache = self.dump_ui_hierarchy()
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 解析XML并查找元素
            xml_content = self.parse_ui_xml(xml_path)
            if text in xml_content:
                self.log('info', f"找到元素: {text}")
                return True
            
            # 等待一段时间后再次检查
            time.sleep(check_interval)
        
        self.log('warning', f"超时: 未找到元素 {text}")
        return False

    def dump_ui_hierarchy(self, output_file="/sdcard/window_dump.xml"):
        """导出UI层级
        Args:
            output_file: 导出文件路径
        Returns:
            tuple: (bool, bool) - (是否成功, 是否使用了缓存)
        """
        # 检查缓存是否有效
        current_time = time.time()
        if output_file in self.cache['ui']:
            cache_entry = self.cache['ui'][output_file]
            if (current_time - cache_entry['timestamp']) < self.cache_ttl:
                self.log('debug', f"使用缓存的UI层级: {output_file}")
                self.cache_stats['hits'] += 1
                return True, True
        
        # 执行dump操作
        self.log('info', f"导出UI层级到: {output_file}")
        result = self.execute_adb_command(["shell", "uiautomator", "dump", output_file])
        ui_dump_time = self.config['sleep_times'].get('ui_dump', 1)
        time.sleep(ui_dump_time)  # 等待导出完成
        
        # 更新缓存
        if result is not None:
            self.cache['ui'][output_file] = {
                'timestamp': current_time,
                'valid': True
            }
            self.cache_stats['misses'] += 1
        
        return result is not None, False
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def pull_file(self, remote_path, local_path, force_refresh=False):
        """从设备拉取文件
        Args:
            remote_path: 设备上的文件路径
            local_path: 本地保存路径
            force_refresh: 是否强制刷新，不使用缓存
        Returns:
            bool: 是否成功
        """
        # 检查文件缓存
        cache_key = f"{remote_path}:{local_path}"
        current_time = time.time()
        
        if not force_refresh and cache_key in self.cache['file']:
            cache_entry = self.cache['file'][cache_key]
            if (current_time - cache_entry['timestamp']) < self.cache_ttl and os.path.exists(local_path):
                print(f"使用缓存的文件: {local_path}")
                self.cache_stats['hits'] += 1
                return True
        
        try:
            print(f"从设备拉取文件: {remote_path} -> {local_path}")
            result = self.execute_adb_command(["pull", remote_path, local_path])
            if result:
                print(f"文件拉取成功: {local_path}")
                # 更新文件缓存
                self.cache['file'][cache_key] = {
                    'timestamp': current_time,
                    'path': local_path
                }
                self.cache_stats['misses'] += 1
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
            if xml_path in self.cache['ui'] and isinstance(self.cache['ui'][xml_path], dict) and self.cache['ui'][xml_path].get('mtime') == file_mtime:
                print(f"使用缓存的XML内容: {xml_path}")
                self.cache_stats['hits'] += 1
                return self.cache['ui'][xml_path]['content']
            
            # 读取文件内容
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新缓存
            self.cache['ui'][xml_path] = {
                'content': content,
                'mtime': file_mtime,
                'timestamp': time.time()
            }
            self.cache_stats['misses'] += 1
            
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
        if cache_key in self.cache['ui'] and isinstance(self.cache['ui'][cache_key], tuple):
            print(f"使用缓存的元素位置: {text}")
            self.cache_stats['hits'] += 1
            return self.cache['ui'][cache_key]
        
        try:
            pattern = r'text="' + re.escape(text) + r'"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            match = re.search(pattern, xml_content)
            if match:
                bounds = (int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)))
                # 缓存查找结果
                self.cache['ui'][cache_key] = bounds
                self.cache_stats['misses'] += 1
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
    
    def wait_for_condition(self, condition_func, timeout=30, interval=0.5, description="条件"):
        """等待条件满足
        Args:
            condition_func: 条件函数，返回 True 表示条件满足
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            description: 条件描述，用于日志输出
        Returns:
            bool: 是否在超时前条件满足
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if condition_func():
                    self.log('info', f"条件满足: {description}")
                    return True
            except Exception as e:
                self.log('debug', f"检查条件时出错: {e}")
            
            # 动态调整间隔，随着时间增加减少间隔
            elapsed = time.time() - start_time
            if elapsed < timeout * 0.5:
                time.sleep(interval)
            else:
                time.sleep(interval / 2)
        
        self.log('warning', f"超时: 条件 {description} 未满足")
        return False
    
    def wait_for_element(self, text, timeout=30, interval=0.5):
        """等待元素出现
        Args:
            text: 元素文本
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
        Returns:
            tuple: (left, top, right, bottom) 或 None
        """
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        
        def check_element():
            # 导出UI层级（会使用缓存）
            self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 读取并分析XML文件（会使用缓存）
            xml_content = self.parse_ui_xml(xml_path)
            
            # 查找元素
            bounds = self.find_element_by_text(xml_content, text)
            return bounds is not None
        
        if self.wait_for_condition(check_element, timeout, interval, f"元素 '{text}' 出现"):
            # 再次查找元素以返回其边界
            self.dump_ui_hierarchy()
            self.pull_file("/sdcard/window_dump.xml", xml_path)
            xml_content = self.parse_ui_xml(xml_path)
            return self.find_element_by_text(xml_content, text)
        
        print(f"等待元素 '{text}' 超时")
        return None
    
    @handle_exception(default_return=None, log_level='warning')
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
            self.log('debug', f"截图已禁用，跳过: {filename}")
            return None
        
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
                self.log('info', f"截图已压缩并保存: {filepath}")
            except ImportError:
                self.log('warning', "Pillow库未安装，跳过压缩")
            except Exception as e:
                self.log('warning', f"压缩截图失败: {e}")
                # 尝试使用PNG格式保存
                try:
                    if 'img' in locals():
                        # 尝试使用PNG格式保存
                        png_path = filepath.replace('.png', '.png')
                        img.save(png_path, 'PNG')
                        self.log('info', f"使用PNG格式保存截图: {png_path}")
                    else:
                        self.log('warning', "无法使用PNG格式保存，图片对象不存在")
                except Exception as e2:
                    self.log('warning', f"保存PNG格式失败: {e2}")
                    # 尝试不压缩，直接使用原始截图
                    self.log('info', "使用原始截图，跳过压缩")
        else:
            self.log('info', f"截图已保存: {filepath}")
        
        return filepath
    
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
        cache_key = 'device_status'
        current_time = time.time()
        if cache_key in self.cache['status']:
            cache_entry = self.cache['status'][cache_key]
            if (current_time - cache_entry['timestamp']) < 5:
                print(f"使用缓存的设备状态: {cache_entry['devices']}")
                return len(cache_entry['devices']) > 0
        
        result = self.execute_adb_command(["devices"])
        if result:
            devices = result.stdout.strip().split('\n')[1:]
            running_devices = [device.split('\t')[0] for device in devices if 'device' in device]
            
            # 缓存设备状态
            self.cache['status'][cache_key] = {
                'devices': running_devices,
                'timestamp': current_time
            }
            
            if running_devices:
                print(f"发现运行中的设备: {running_devices}")
                return True
            else:
                print("未发现运行中的设备")
                return False
        return False
    
    def find_avdmanager(self):
        """查找avdmanager工具路径"""
        # 从配置中读取ADB路径，avdmanager通常在同一目录的上一级
        common_paths = self.config['adb']['common_paths']
        
        # 尝试从新版cmdline-tools中查找
        cmdline_tools_paths = [
            "~/Library/ANDROID/SDK/cmdline-tools/latest/bin/avdmanager",
            "/Users/tianyong/Library/ANDROID/SDK/cmdline-tools/latest/bin/avdmanager"
        ]
        
        for path in cmdline_tools_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                print(f"找到新版avdmanager工具: {expanded_path}")
                return expanded_path
        
        # 尝试从传统路径中查找
        for path in common_paths:
            # 替换{USERNAME}占位符
            if "{USERNAME}" in path:
                path = path.format(USERNAME=os.getenv("USERNAME", ""))
            
            # 展开~符号
            expanded_path = os.path.expanduser(path)
            try:
                # 检查路径是否存在
                if os.path.exists(expanded_path):
                    # 尝试从新版SDK结构中查找
                    avdmanager_path = os.path.join(os.path.dirname(os.path.dirname(expanded_path)), "cmdline-tools", "latest", "bin", "avdmanager")
                    if not os.path.exists(avdmanager_path):
                        # 传统路径
                        avdmanager_path = os.path.join(os.path.dirname(os.path.dirname(expanded_path)), "tools", "bin", "avdmanager")
                    # 对于Windows系统
                    if platform.system().lower() == "windows":
                        avdmanager_path += ".bat"
                    if os.path.exists(avdmanager_path):
                        print(f"找到avdmanager工具: {avdmanager_path}")
                        return avdmanager_path
            except Exception:
                continue
        
        print("未找到avdmanager工具，请确保Android SDK已安装")
        return None
    
    def check_emulator_exists(self):
        """检查模拟器是否存在"""
        print(f"检查模拟器 {self.emulator_name} 是否存在...")
        
        # 查找avdmanager工具
        avdmanager_path = self.find_avdmanager()
        if not avdmanager_path:
            return False
        
        try:
            # 为新版cmdline-tools设置正确的Java环境
            env = os.environ.copy()
            # 检查是否是新版cmdline-tools
            if "cmdline-tools" in avdmanager_path and "latest" in avdmanager_path:
                # 为新版cmdline-tools设置Java 17
                java_17_path = "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
                if os.path.exists(java_17_path):
                    env["JAVA_HOME"] = java_17_path
                    print("已为新版cmdline-tools设置Java 17环境")
            
            # 执行avdmanager list avd命令
            result = subprocess.run(
                [avdmanager_path, "list", "avd"],
                capture_output=True,
                text=True,
                env=env
            )
            
            # 打印完整输出用于调试
            print(f"avdmanager输出: {result.stdout}")
            if result.stderr:
                print(f"avdmanager错误: {result.stderr}")
            
            # 检查输出中是否包含模拟器名称
            if self.emulator_name in result.stdout:
                print(f"模拟器 {self.emulator_name} 已存在")
                return True
            else:
                print(f"模拟器 {self.emulator_name} 不存在")
                return False
        except Exception as e:
            print(f"检查模拟器失败: {e}")
            return False
    
    def create_emulator(self):
        """创建模拟器"""
        print(f"创建模拟器 {self.emulator_name}...")
        
        # 查找avdmanager工具
        avdmanager_path = self.find_avdmanager()
        if not avdmanager_path:
            return False
        
        try:
            # 获取模拟器创建配置
            creation_config = self.config['emulator'].get('creation', {})
            device = creation_config.get('device', 'pixel')
            system_image = creation_config.get('system_image', 'system-images;android-30;google_apis;x86_64')
            sdcard_size = creation_config.get('sdcard_size', '1024M')
            
            # 检查系统镜像是否存在
            print(f"检查系统镜像 {system_image} 是否存在...")
            sdkmanager_path = os.path.join(os.path.dirname(avdmanager_path), 'sdkmanager')
            if platform.system().lower() == "windows":
                sdkmanager_path += ".bat"
            
            # 为新版cmdline-tools设置正确的Java环境
            env = os.environ.copy()
            # 检查是否是新版cmdline-tools
            if "cmdline-tools" in avdmanager_path and "latest" in avdmanager_path:
                # 为新版cmdline-tools设置Java 17
                java_17_path = "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
                if os.path.exists(java_17_path):
                    env["JAVA_HOME"] = java_17_path
                    print("已为新版cmdline-tools设置Java 17环境")
            
            # 检查系统镜像
            result = subprocess.run(
                [sdkmanager_path, "--list"],
                capture_output=True,
                text=True,
                env=env
            )
            
            if system_image not in result.stdout:
                print(f"系统镜像 {system_image} 不存在，开始安装...")
                # 安装系统镜像
                install_result = subprocess.run(
                    [sdkmanager_path, system_image],
                    capture_output=True,
                    text=True,
                    env=env
                )
                if install_result.returncode != 0:
                    print(f"安装系统镜像失败: {install_result.stderr}")
                    return False
                print("系统镜像安装成功")
            
            # 创建模拟器
            print(f"使用设备 {device} 和系统镜像 {system_image} 创建模拟器...")
            create_result = subprocess.run(
                [avdmanager_path, "create", "avd", "--name", self.emulator_name, "--device", device, "--package", system_image, "--sdcard", sdcard_size, "--force"],
                capture_output=True,
                text=True,
                env=env
            )
            
            if create_result.returncode == 0:
                print(f"模拟器 {self.emulator_name} 创建成功")
                return True
            else:
                print(f"创建模拟器失败: {create_result.stderr}")
                return False
        except Exception as e:
            print(f"创建模拟器失败: {e}")
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
            
            # 智能等待模拟器启动
            max_wait_time = self.config['sleep_times'].get('emulator_start', 30)
            check_interval = 2
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                # 清除设备状态缓存
                self.cache['status'].pop('device_status', None)
                # 检查模拟器状态
                if self.check_emulator_status():
                    print("模拟器启动成功！")
                    return True
                # 等待一段时间后再次检查
                time.sleep(check_interval)
                print(f"等待模拟器启动... {(time.time() - start_time):.1f}s/{max_wait_time}s")
            
            # 超时后再次检查
            print("模拟器启动超时，最终检查...")
            self.cache['status'].pop('device_status', None)
            return self.check_emulator_status()
        except Exception as e:
            print(f"启动模拟器失败: {e}")
            return False
    
    def stop_emulator(self):
        """关闭模拟器"""
        print("关闭模拟器...")
        try:
            # 清除设备状态缓存
            self.cache['status'].pop('device_status', None)
            
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
                print("未找到emulator命令，无法关闭模拟器")
                return False
            
            # 关闭模拟器
            print(f"使用路径: {emulator_path} 关闭模拟器: {self.emulator_name}")
            # 使用adb命令关闭模拟器
            if self.check_adb_available():
                # 首先关闭纷享销客应用
                print(f"关闭纷享销客应用 {self.package_name}...")
                try:
                    self.execute_adb_command(["shell", "am", "force-stop", self.package_name], check=False)
                    print("纷享销客应用已关闭")
                    # 等待应用完全关闭
                    time.sleep(2)
                except Exception as e:
                    print(f"关闭纷享销客应用失败: {e}")
                
                # 首先获取设备列表
                result = self.execute_adb_command(["devices"])
                if result:
                    devices = result.stdout.strip().split('\n')[1:]
                    running_devices = [device.split('\t')[0] for device in devices if 'device' in device]
                    
                    for device in running_devices:
                        print(f"关闭设备: {device}")
                        # 使用adb命令关闭模拟器
                        try:
                            # 对于模拟器，使用 adb emu kill 命令
                            if "emulator" in device:
                                print("使用 adb emu kill 命令关闭模拟器")
                                self.execute_adb_command(["-s", device, "emu", "kill"], check=False)
                            else:
                                # 对于真实设备，使用 reboot -p 命令
                                print("使用 reboot -p 命令关闭设备")
                                self.execute_adb_command(["-s", device, "shell", "reboot", "-p"], check=False)
                            print(f"设备 {device} 关闭命令已发送")
                        except Exception as e:
                            print(f"关闭设备 {device} 失败: {e}")
            
            # 等待模拟器关闭（增加等待时间和轮询间隔）
            print("等待模拟器关闭...")
            max_attempts = 15  # 增加尝试次数
            wait_interval = 3   # 增加等待间隔
            
            for i in range(max_attempts):
                time.sleep(wait_interval)
                # 清除设备状态缓存
                self.cache['status'].pop('device_status', None)
                # 检查模拟器状态
                if not self.check_emulator_status():
                    print("模拟器已成功关闭")
                    return True
                print(f"等待模拟器关闭... {i+1}/{max_attempts}")
            
            # 再次检查模拟器状态
            self.cache['status'].pop('device_status', None)  # 再次清除缓存
            if not self.check_emulator_status():
                print("模拟器已成功关闭")
                return True
            else:
                print("模拟器关闭失败，可能需要手动关闭")
                return False
        except Exception as e:
            print(f"关闭模拟器失败: {e}")
            return False
    
    def check_app_installed(self):
        """检查应用是否已安装"""
        print(f"检查应用 {self.package_name} 是否已安装...")
        
        try:
            # 执行pm list packages命令
            result = self.execute_adb_command(["shell", "pm", "list", "packages", self.package_name])
            
            # 检查输出中是否包含包名
            if result and self.package_name in result.stdout:
                print(f"应用 {self.package_name} 已安装")
                return True
            else:
                print(f"应用 {self.package_name} 未安装")
                return False
        except Exception as e:
            print(f"检查应用安装状态失败: {e}")
            return False
    
    def download_and_install_app(self):
        """下载并安装应用"""
        print(f"下载并安装应用 {self.package_name}...")
        
        try:
            # 首先检查是否有本地APK文件
            app_config = self.config.get('app', {})
            temp_path = app_config.get('temp_path', '../temp/fxiaoke.apk')
            apk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), temp_path)
            
            # 确保临时目录存在
            temp_dir = os.path.dirname(apk_path)
            os.makedirs(temp_dir, exist_ok=True)
            
            # 检查本地是否已有APK文件
            if os.path.exists(apk_path) and os.path.getsize(apk_path) > 100000:
                print(f"使用本地APK文件: {apk_path}")
            else:
                # 下载APK文件
                download_url = app_config.get('download_url', 'https://www.fxiaoke.com/download')
                print(f"从 {download_url} 下载APK...")
                
                # 尝试下载，最多重试3次
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = requests.get(download_url, stream=True, timeout=30)
                        response.raise_for_status()
                        
                        # 保存下载的内容
                        with open(apk_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # 检查文件大小
                        file_size = os.path.getsize(apk_path)
                        print(f"下载文件大小: {file_size} 字节")
                        
                        if file_size > 100000:
                            print(f"APK下载成功，保存到: {apk_path}")
                            break
                        else:
                            print(f"下载的文件太小，重试 {retry+1}/{max_retries}...")
                            time.sleep(2)
                    except Exception as e:
                        print(f"下载失败，重试 {retry+1}/{max_retries}: {e}")
                        time.sleep(2)
                else:
                    print("多次下载失败，尝试使用ADB安装命令")
                    # 提示用户手动下载并安装
                    print("\n===========================================")
                    print("请手动下载纷享销客应用APK并安装到模拟器中：")
                    print("1. 访问 https://www.fxiaoke.com/download 下载APK")
                    print("2. 使用命令安装：adb install /path/to/fxiaoke.apk")
                    print("3. 然后重新运行此脚本")
                    print("===========================================")
                    return False
            
            # 安装APK文件
            print("安装APK文件...")
            install_result = self.execute_adb_command(["install", apk_path])
            
            if install_result:
                print("应用安装成功")
                # 验证安装是否成功
                if self.check_app_installed():
                    return True
                else:
                    print("应用安装失败，验证未通过")
                    return False
            else:
                print("应用安装失败")
                return False
        except Exception as e:
            print(f"下载并安装应用失败: {e}")
            # 提示用户手动安装
            print("\n===========================================")
            print("请手动安装纷享销客应用到模拟器中：")
            print("1. 下载APK文件")
            print("2. 使用命令安装：adb install /path/to/fxiaoke.apk")
            print("3. 然后重新运行此脚本")
            print("===========================================")
            return False
    
    def is_app_running(self):
        """检查应用是否已经在运行"""
        # 缓存应用运行状态，避免重复执行ADB命令
        cache_key = 'app_running_status'
        current_time = time.time()
        if cache_key in self.cache['status']:
            cache_entry = self.cache['status'][cache_key]
            if (current_time - cache_entry['timestamp']) < 3:
                print(f"使用缓存的应用运行状态: {cache_entry['running']}")
                return cache_entry['running']
        
        try:
            result = self.execute_adb_command(["shell", "dumpsys", "activity", "activities"])
            running = False
            if result:
                running = self.package_name in result.stdout
            
            # 缓存应用运行状态
            self.cache['status'][cache_key] = {
                'running': running,
                'timestamp': current_time
            }
            
            return running
        except Exception as e:
            print(f"检查应用运行状态失败: {e}")
            return False
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def start_fxiaoke(self):
        """启动纷享销客应用"""
        print("启动纷享销客应用...")
        
        # 检查应用是否已安装
        if not self.check_app_installed():
            if not self.download_and_install_app():
                print("无法安装应用，流程终止")
                return False
        
        # 检查应用是否已经在运行
        if self.is_app_running():
            print("应用已经在运行，重启应用以确保考勤日期为当天")
            # 停止应用
            self.execute_adb_command(["shell", "am", "force-stop", self.package_name])
            print("应用已停止")
            # 等待一段时间，确保应用完全停止
            time.sleep(2)
        
        # 尝试解锁屏幕（如果锁屏）
        self.execute_adb_command(["shell", "input", "keyevent", "82"])
        time.sleep(1)
        
        # 使用 -a 参数和 -f 参数确保应用在前台启动
        self.execute_adb_command(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-n", f"{self.package_name}/{self.activity_name}", "-f", "0x10000000"])
        
        # 使用基于事件的等待机制，等待应用启动
        print("等待应用启动...")
        timeout = self.config['sleep_times'].get('app_start', 8)  # 减少超时时间
        interval = 0.5  # 减少检查间隔
        
        def check_app_running():
            return self.is_app_running()
        
        if self.wait_for_condition(check_app_running, timeout, interval, "应用启动"):
            print("应用已成功启动")
        else:
            print("应用启动超时")
        
        # 等待应用完全激活（减少等待时间）
        time.sleep(self.config['sleep_times'].get('monkey_activate', 1))
        
        # 只有在应用未成功启动时才使用monkey命令
        if not self.is_app_running():
            print("应用未成功启动，尝试使用monkey命令激活")
            self.execute_adb_command(["shell", "monkey", "-p", self.package_name, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(self.config['sleep_times'].get('monkey_activate', 1))
            
            # 模拟点击屏幕，确保应用在前台
            self.execute_adb_command(["shell", "input", "tap", "720", "2400"])
            time.sleep(self.config['sleep_times'].get('click_wait', 1))
        
        return True
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def navigate_to_attendance(self):
        """导航到考勤页面"""
        print("导航到考勤页面...")
        xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
        
        # 第一步：判断当前页面状态
        page_status = self.check_page_status()
        
        # 如果已经是考勤页面，直接返回
        if page_status == 'attendance':
            print("当前已经是考勤页面")
            return True
        
        # 根据页面状态执行不同操作
        if page_status == 'other':
            # 不是考勤页面也不是首页，先回到首页
            print("当前页面不是考勤页面也不是首页，先回到首页...")
            if not self.go_to_home():
                print("回到首页失败，导航终止")
                return False
            # 回到首页后，重新判断页面状态（强制刷新）
            page_status = self.check_page_status(force_refresh=True)
            if page_status != 'home':
                print("未能回到首页，导航终止")
                return False
        
        # 现在页面状态是 home 或 app_list，尝试导航到考勤页面
        if page_status in ['home', 'app_list']:
            # 使用UIAutomator查找考勤选项
            success, used_cache = self.dump_ui_hierarchy()
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            xml_content = self.parse_ui_xml(xml_path)
            
            # 如果是首页，先点击"应用"按钮
            if page_status == 'home':
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
                        # 清除相关的UI缓存，保留其他缓存
                        self.clear_ui_cache("/sdcard/window_dump.xml")
                        # 减少等待时间
                        time.sleep(self.config['sleep_times'].get('click_wait', 1))
                    else:
                        # 备用方案：使用配置的坐标
                        app_button_coordinates = self.config['coordinates']['app_button']
                        # 只尝试前3个坐标，减少不必要的ADB命令
                        for i, coord in enumerate(app_button_coordinates[:3]):
                            x, y = coord
                            print(f"尝试点击应用按钮，坐标: ({x}, {y}) (尝试 {i+1}/3)")
                            self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                            # 清除相关的UI缓存，保留其他缓存
                            self.clear_ui_cache("/sdcard/window_dump.xml")
                            # 减少等待时间
                            time.sleep(self.config['sleep_times'].get('click_wait', 1))
                            
                            # 检查是否成功进入应用页面
                            if self.wait_for_element(self.config['ui']['texts']['attendance'], timeout=2):
                                print("成功进入应用页面，停止尝试其他坐标")
                                break
                    
                    # 等待应用页面加载，使用条件等待代替固定等待
                    attendance_text = self.config['ui']['texts']['attendance']
                    if not self.wait_for_element(attendance_text, timeout=5):
                        print("未能找到考勤选项，继续执行")
                    
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
                print(f"点击考勤按钮...")
                print(f"找到考勤按钮，坐标: ({x}, {y})")
                self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                # 清除相关的UI缓存，保留其他缓存
                self.clear_ui_cache("/sdcard/window_dump.xml")
                
                # 增加等待时间，确保页面完全加载
                # wait_time = 2
                # print(f"等待{wait_time}秒，确保页面完全加载...")
                # time.sleep(wait_time)
                
                # 检查页面状态（强制刷新）
                current_status = self.check_page_status(force_refresh=True)
                print(f"点击考勤按钮后页面状态: {current_status}")
                if current_status == 'attendance':
                    print("导航到考勤页面成功！")
                    return True
                else:
                    # 尝试使用更精确的坐标点击
                    print("尝试使用更精确的坐标点击...")
                    offsets = self.config['ui']['offsets']
                    for offset in offsets:
                        offset_x = x + offset[0]
                        offset_y = y + offset[1]
                        self.execute_adb_command(["shell", "input", "tap", str(offset_x), str(offset_y)])
                        # 减少等待时间
                        time.sleep(self.config['sleep_times'].get('click_wait', 1))
                    
                    # 所有偏移点击后，再次检查页面状态（强制刷新）
                    current_status = self.check_page_status(force_refresh=True)
                    print(f"尝试偏移点击后页面状态: {current_status}")
                    if current_status == 'attendance':
                        print("导航到考勤页面成功！")
                        return True
            else:
                # 尝试使用更精确的坐标点击，重点点击顶部区域
                print("未找到考勤选项，尝试使用配置的坐标点击...")
                attendance_coords = self.config['ui']['attendance_coordinates']
                x_coords = attendance_coords['x']
                y_coords = attendance_coords['y']
                
                # 记录所有尝试的坐标
                for x in x_coords:
                    for y in y_coords:
                        self.execute_adb_command(["shell", "input", "tap", str(x), str(y)])
                        # 减少等待时间
                        time.sleep(self.config['sleep_times'].get('click_wait', 1))
                
                # 所有坐标尝试后，检查页面状态（强制刷新）
                current_status = self.check_page_status(force_refresh=True)
                if current_status == 'attendance':
                    print("导航到考勤页面成功！")
                    return True
        
        # 最终检查页面状态（强制刷新）
        final_status = self.check_page_status(force_refresh=True)
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
            
            start_time = time.time()
            timeout = 60  # 60秒超时
            
            while time.time() - start_time < timeout:
                # 尝试通过UI元素检查定位状态
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
                elif "正在定位中" in xml_content:
                    print("正在定位中，等待3秒后重新检查...")
                    time.sleep(3)
                else:
                    print("无法确定定位状态，等待3秒后重新检查...")
                    time.sleep(3)
            
            # 超时
            print("定位超时（60秒），返回False")
            return False
        except Exception as e:
            print(f"检查定位状态失败: {e}")
            return False
    
    def parse_time(self, time_str):
        """解析时间字符串
        Args:
            time_str: 时间字符串，格式为 "HH:MM"
        Returns:
            tuple: (小时, 分钟)
        """
        hour, minute = map(int, time_str.split(':'))
        return hour, minute
    
    def is_time_in_range(self, checkin_hour, checkin_minute, start_time, end_time):
        """检查时间是否在指定范围内
        Args:
            checkin_hour: 检查的小时
            checkin_minute: 检查的分钟
            start_time: 开始时间 (小时, 分钟)
            end_time: 结束时间 (小时, 分钟)
        Returns:
            bool: 是否在范围内
        """
        return ((checkin_hour > start_time[0] and checkin_hour < end_time[0]) or \
                (checkin_hour == start_time[0] and checkin_minute >= start_time[1]) or \
                (checkin_hour == end_time[0] and checkin_minute <= end_time[1]))
    
    def check_time_range(self):
        """检查当前时间是否在允许的打卡时间段内"""
        now = datetime.datetime.now()
        current_time = now.time()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        print(f"当前时间: {current_time}")
        
        # 从配置中读取时间范围
        time_ranges = self.config['time_ranges']
        
        # 早上上班签到
        morning_start = self.parse_time(time_ranges['morning_checkin']['start'])
        morning_end = self.parse_time(time_ranges['morning_checkin']['end'])
        if self.is_time_in_range(current_hour, current_minute, morning_start, morning_end):
            return "morning_checkin"
        
        # 中午午休打卡
        noon_start = self.parse_time(time_ranges['noon_checkin']['start'])
        noon_end = self.parse_time(time_ranges['noon_checkin']['end'])
        if self.is_time_in_range(current_hour, current_minute, noon_start, noon_end):
            return "noon_checkin"
        
        # 晚上下班签退
        evening_start = self.parse_time(time_ranges['evening_checkout']['start'])
        evening_end = self.parse_time(time_ranges['evening_checkout']['end'])
        if self.is_time_in_range(current_hour, current_minute, evening_start, evening_end):
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
    
    def check_existing_checkin(self):
        """检查当前时段内是否已经打过卡
        Returns:
            bool: 是否已在当前时段内打卡
        """
        print("开始检查当前时段内是否已经打过卡...")
        try:
            # 获取当前时间范围
            time_range = self.check_time_range()
            if time_range == "out_of_range":
                print("当前时间不在打卡范围内")
                print("检查打卡记录完成")
                return False
            
            # 检测打卡记录
            checkin_records = self.detect_checkin_records()
            
            # 获取当前时段的时间范围
            time_ranges = self.config['time_ranges']
            if time_range == "morning_checkin":
                start_time = self.parse_time(time_ranges['morning_checkin']['start'])
                end_time = self.parse_time(time_ranges['morning_checkin']['end'])
                expected_types = ["智能签到", "签到"]
            elif time_range == "noon_checkin":
                start_time = self.parse_time(time_ranges['noon_checkin']['start'])
                end_time = self.parse_time(time_ranges['noon_checkin']['end'])
                # 中午需要特殊处理，分别检查签退和签到
                result = self.check_noon_checkin(checkin_records, start_time, end_time)
                print("检查打卡记录完成")
                return result
            elif time_range == "evening_checkout":
                start_time = self.parse_time(time_ranges['evening_checkout']['start'])
                end_time = self.parse_time(time_ranges['evening_checkout']['end'])
                expected_types = ["签退"]
            else:
                print("未知的时间范围")
                print("检查打卡记录完成")
                return False
            
            # 检查每条打卡记录
            for record in checkin_records:
                # 提取时间和类型
                time_match = re.search(r'(\d{2}:\d{2})', record)
                type_match = re.search(r'(智能签到|签到|签退)', record)
                
                if time_match and type_match:
                    checkin_time_str = time_match.group(1)
                    checkin_type = type_match.group(1)
                    
                    # 解析打卡时间
                    checkin_hour, checkin_minute = self.parse_time(checkin_time_str)
                    
                    # 检查打卡时间是否在当前时段内
                    is_in_range = self.is_time_in_range(checkin_hour, checkin_minute, start_time, end_time)
                    
                    # 检查打卡类型是否符合当前时段
                    if is_in_range and checkin_type in expected_types:
                        print(f"在当前时段内已找到打卡记录: {record}")
                        print("检查打卡记录完成")
                        return True
            
            print("当前时段内未找到打卡记录")
            print("检查打卡记录完成")
            return False
        except Exception as e:
            print(f"检查打卡记录失败: {e}")
            print("检查打卡记录完成")
            return False
    
    def check_noon_checkin(self, checkin_records, start_time, end_time):
        """检查中午时段的打卡记录
        中午需要打两次卡：签退和签到
        Args:
            checkin_records: 打卡记录列表
            start_time: 开始时间 (小时, 分钟)
            end_time: 结束时间 (小时, 分钟)
        Returns:
            bool: 是否已完成中午的所有打卡
        """
        print("开始检查中午时段的打卡记录...")
        
        # 检查是否有签退记录
        has_checkout = False
        # 检查是否有签到记录
        has_checkin = False
        
        for record in checkin_records:
            # 提取时间和类型
            time_match = re.search(r'(\d{2}:\d{2})', record)
            type_match = re.search(r'(智能签到|签到|签退)', record)
            
            if time_match and type_match:
                checkin_time_str = time_match.group(1)
                checkin_type = type_match.group(1)
                
                # 解析打卡时间
                checkin_hour, checkin_minute = self.parse_time(checkin_time_str)
                
                # 检查打卡时间是否在中午时段内
                is_in_range = self.is_time_in_range(checkin_hour, checkin_minute, start_time, end_time)
                
                if is_in_range:
                    if checkin_type == "签退":
                        print(f"在中午时段内已找到签退记录: {record}")
                        has_checkout = True
                    elif checkin_type in ["智能签到", "签到"]:
                        print(f"在中午时段内已找到签到记录: {record}")
                        has_checkin = True
        
        # 中午需要同时有签退和签到记录才算完成
        if has_checkout and has_checkin:
            print("中午时段已经完成签退和签到，跳过打卡操作")
            print("中午时段打卡记录检查完成")
            return True
        else:
            if not has_checkout:
                print("中午时段尚未签退，需要打卡")
            if not has_checkin:
                print("中午时段尚未签到，需要打卡")
            print("中午时段打卡记录检查完成")
            return False
    
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
    
    def check_page_status(self, force_refresh=False):
        """判断当前页面状态
        Args:
            force_refresh: 是否强制刷新UI层级
        Returns:
            str: 页面状态，可能的值：'attendance', 'home', 'app_list', 'other'
        """
        # 缓存页面状态，避免重复执行ADB命令
        cache_key = 'page_status'
        current_time = time.time()
        if not force_refresh and cache_key in self.cache['status']:
            cache_entry = self.cache['status'][cache_key]
            if (current_time - cache_entry['timestamp']) < 5:
                print(f"使用缓存的页面状态: {cache_entry['status']}")
                return cache_entry['status']
        
        # 直接使用UIAutomator判断页面状态，减少对Activity的依赖
        try:
            # 强制刷新UI层级
            if force_refresh:
                # 只清除相关的UI缓存，保留其他缓存
                self.clear_ui_cache("/sdcard/window_dump.xml")
                print("清除UI缓存...")
                # 重新dump界面层级
                success, used_cache = self.dump_ui_hierarchy()
                print(f"重新dump界面层级: 成功={success}, 使用缓存={used_cache}")
            else:
                # 使用UIAutomator dump界面层级（会使用缓存）
                success, used_cache = self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            # 只有在未使用缓存时才拉取文件
            if not used_cache:
                # 强制从设备拉取最新的XML文件，不使用缓存
                self.pull_file("/sdcard/window_dump.xml", xml_path, force_refresh=force_refresh)
                print(f"从设备拉取最新的XML文件到: {xml_path}")
            else:
                print("使用缓存的XML文件")
            
            # 读取并分析XML文件
            xml_content = self.parse_ui_xml(xml_path)
            print(f"读取XML文件长度: {len(xml_content)} 字符")
            
            # 检查是否是纷享销客应用
            if 'com.facishare.fs' in xml_content:
                # 检查是否包含考勤相关的文本
                has_attendance = '考勤' in xml_content
                has_sign_in = '签到' in xml_content
                has_sign_out = '签退' in xml_content
                has_location = '已进入地点考勤范围' in xml_content
                has_qixin = '企信' in xml_content
                
                # 输出调试信息
                print(f"页面状态检查: 考勤={has_attendance}, 签到={has_sign_in}, 签退={has_sign_out}, 定位={has_location}, 企信={has_qixin}")
                
                # 检查是否是考勤页面（包含"考勤"标题，并且包含打卡记录或考勤状态）
                if has_attendance and (has_sign_in or has_sign_out or has_location):
                    status = 'attendance'
                
                # 检查是否是企信页面（首页）
                elif has_qixin:
                    status = 'home'
                
                # 其他纷享销客页面（包括应用列表页面）
                else:
                    status = 'other'
            else:
                status = 'other'
            
            # 缓存页面状态
            self.cache['status'][cache_key] = {
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
            # 成功回到首页后清除缓存
            self.clear_cache()
            return True
        except Exception as e:
            print(f"回到首页失败: {e}")
            return False
    
    @retry(max_attempts=3, delay=2, backoff=1.5)
    def perform_checkin(self):
        """执行打卡操作"""
        print("执行打卡操作...")
        try:
            # 使用UIAutomator dump界面层级，找到实际的打卡按钮位置
            success, used_cache = self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            if not used_cache:
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
        except Exception as e:
            print(f"执行打卡操作时出错: {e}")
            # 尝试使用默认坐标作为备选方案
            try:
                print("尝试使用默认坐标进行打卡")
                default_checkin = self.config['coordinates']['default_checkin']
                self.execute_adb_command(["shell", "input", "tap", str(default_checkin[0]), str(default_checkin[1])])
                time.sleep(2)
                return True
            except Exception as e2:
                print(f"使用默认坐标打卡也失败: {e2}")
                return False
    
    @retry(max_attempts=3, delay=1, backoff=1.5)
    def check_attendance_date(self):
        """检查考勤页面显示的日期是否为当天
        Returns:
            bool: 是否为当天日期
        """
        print("检查考勤页面日期...")
        try:
            # 使用UIAutomator dump界面层级
            success, used_cache = self.dump_ui_hierarchy()
            
            # 拉取XML文件到本地
            xml_path = os.path.join(self.screenshot_dir, "window_dump.xml")
            if not used_cache:
                self.pull_file("/sdcard/window_dump.xml", xml_path)
            
            # 读取并分析XML文件
            xml_content = self.parse_ui_xml(xml_path)
            
            # 获取当前日期
            today = datetime.datetime.now()
            today_str = today.strftime("%m月%d日")
            # 移除前导零并标准化格式
            today_str = today_str.lstrip('0')
            # 处理日期中的零，例如将"4月01日"转换为"4月1日"
            today_str = re.sub(r'(\d+)月0*(\d+)日', r'\1月\2日', today_str)
            
            print(f"当前日期: {today_str}")
            
            # 查找页面中的日期信息，只匹配日期数字部分
            date_pattern = r'(\d+月\d+日)'
            date_match = re.search(date_pattern, xml_content)
            
            if date_match:
                date_str = date_match.group(1)
                # 标准化页面日期格式，移除可能的前导零
                date_str = re.sub(r'(\d+)月0*(\d+)日', r'\1月\2日', date_str)
                
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
                # 尝试使用其他日期格式查找
                alternative_pattern = r'(\d{4}-\d{2}-\d{2})'
                alternative_match = re.search(alternative_pattern, xml_content)
                if alternative_match:
                    alternative_date = alternative_match.group(1)
                    print(f"找到替代日期格式: {alternative_date}")
                    # 转换为与today_str相同的格式进行比较
                    try:
                        alt_date_obj = datetime.datetime.strptime(alternative_date, "%Y-%m-%d")
                        alt_date_str = alt_date_obj.strftime("%m月%d日")
                        # 标准化格式
                        alt_date_str = re.sub(r'(\d+)月0*(\d+)日', r'\1月\2日', alt_date_str)
                        if alt_date_str == today_str:
                            print("页面显示的是当天日期")
                            return True
                    except Exception as e:
                        print(f"解析替代日期格式时出错: {e}")
                return False
        except Exception as e:
            print(f"检查日期时出错: {e}")
            # 出错时默认认为是当天日期，避免因日期检查失败而中断流程
            print("日期检查失败，默认认为是当天日期")
            return True
    
    def detect_checkin_records(self):
        """检测考勤页面中的打卡记录
        Returns:
            list: 打卡记录列表
        """
        try:
            print("检测打卡记录...")
            
            # 尝试滚动屏幕以获取所有打卡记录
            # 先向下滚动几次，确保能看到上面的记录
            for i in range(3):
                self.execute_adb_command(["shell", "input", "swipe", "720", "500", "720", "1500", "500"])
                time.sleep(1)
            
            # 再向上滚动几次，确保能看到下面的记录
            for i in range(3):
                self.execute_adb_command(["shell", "input", "swipe", "720", "1500", "720", "500", "500"])
                time.sleep(1)
            
            # 最后再向下滚动一次，回到顶部
            self.execute_adb_command(["shell", "input", "swipe", "720", "500", "720", "1500", "500"])
            time.sleep(1)
            
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
            
            # 查找考勤记录列表的容器元素
            # 首先尝试找到考勤记录列表的父容器
            container_pattern = r'<node[^>]+resource-id="com\.facishare\.fs:id/checkin_list"[^>]*>([\s\S]*?)</node>'
            container_match = re.search(container_pattern, xml_content)
            
            if container_match:
                # 如果找到容器，在容器内查找打卡记录
                container_content = container_match.group(1)
                print("找到考勤记录容器，在容器内查找打卡记录")
            else:
                # 如果没有找到容器，使用整个XML内容
                container_content = xml_content
                print("未找到考勤记录容器，在整个页面中查找打卡记录")
            
            # 查找所有包含打卡信息的节点（使用更宽松的匹配）
            checkin_pattern = r'text="(\d{2}:\d{2} (智能签到|签到|签退))"'
            checkin_matches = re.findall(checkin_pattern, container_content)
            
            print(f"找到的打卡记录匹配: {checkin_matches}")
            
            # 处理所有找到的打卡类型
            for match in checkin_matches:
                checkin_text = match[0]
                record_type = match[1]
                
                # 提取时间
                time_match = re.search(r'(\d{2}:\d{2})', checkin_text)
                if time_match:
                    checkin_time = time_match.group(1)
                    
                    # 查找对应的状态（使用更宽松的匹配）
                    status_pattern = r'text="(正常|迟到|早退)"'
                    status_match = re.search(status_pattern, container_content)
                    status = status_match.group(1) if status_match else "未知"
                    
                    # 查找对应的地点（使用更宽松的匹配）
                    location_pattern = r'text="([^"\n]+)"[^>]*check_text'
                    location_match = re.search(location_pattern, container_content)
                    location = location_match.group(1) if location_match else "未知地点"
                    
                    record = f"{checkin_time} {record_type}，状态: {status}，地点: {location}"
                    checkin_records.append(record)
            
            # 去重并保持顺序
            seen = set()
            unique_records = []
            for record in checkin_records:
                if record not in seen:
                    seen.add(record)
                    unique_records.append(record)
            checkin_records = unique_records
            
            print(f"最终打卡记录: {checkin_records}")
            return checkin_records
        except Exception as e:
            print(f"检测打卡记录时出错: {e}")
            return []
    
    def build_message(self, base_message, checkin_records):
        """构建包含打卡记录的消息
        Args:
            base_message: 基础消息
            checkin_records: 打卡记录列表
        Returns:
            str: 包含打卡记录的消息
        """
        message = base_message
        if checkin_records:
            message += "\n最新打卡记录:"
            for i, record in enumerate(checkin_records):
                message += f"\n  {i+1}. {record}"
        return message
    
    def setup_emulator(self):
        """设置模拟器
        Returns:
            tuple: (是否成功, 错误消息)
        """
        # 检查模拟器是否存在，不存在则创建
        if not self.check_emulator_exists():
            if not self.create_emulator():
                return False, "无法创建模拟器，流程终止"
        
        # 检查模拟器状态并启动
        if not self.check_emulator_status():
            if not self.start_emulator():
                return False, "无法启动模拟器，流程终止"
            # 不需要额外等待，因为 start_emulator 已经确保模拟器启动成功
        
        return True, ""
    
    def prepare_checkin(self):
        """准备打卡
        Returns:
            tuple: (是否成功, 错误消息, 打卡记录, 截图路径)
        """
        # 启动纷享销客
        if not self.start_fxiaoke():
            return False, "无法启动纷享销客，流程终止", [], None
        
        # 进入考勤页面
        if not self.navigate_to_attendance():
            return False, "无法进入考勤页面，流程终止", [], None
        
        # 检查考勤页面日期是否为当天
        is_today = self.check_attendance_date()
        if not is_today:
            return False, "考勤页面日期不是当天，流程终止", [], None
        
        # 检测打卡记录
        checkin_records = self.detect_checkin_records()
        
        # 截图
        screenshot_path = self.take_screenshot("before_checkin.png")
        if not screenshot_path:
            print("截图已禁用，跳过截图操作")
        
        return True, "", checkin_records, screenshot_path
    
    def check_checkin_status(self, checkin_records, screenshot_path):
        """检查打卡状态
        Args:
            checkin_records: 打卡记录列表
            screenshot_path: 截图路径
        Returns:
            tuple: (是否可以打卡, 错误消息, 时间范围, 状态信息)
        """
        # 先检查时间范围，避免不必要的定位状态检查
        time_range = self.check_time_range()
        
        # 检查是否在打卡范围内
        if time_range == "out_of_range":
            return False, "当前时间不在打卡范围内，不需要打卡", time_range, None
        
        # 检查当前时段内是否已经打过卡
        if self.check_existing_checkin():
            # 截图当前页面
            screenshot_path = self.take_screenshot("already_checked_in.png")
            return False, "当前时段内已经打过卡，跳过打卡操作", time_range, None
        
        # 检查定位状态和按钮状态
        location_status = self.check_location_status(screenshot_path)
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
        
        # 检查是否可以打卡（定位状态）
        if not location_status:
            return False, "未进入地点考勤范围，无法打卡", time_range, None
        
        return True, "", time_range, status_info
    
    def perform_checkin_operation(self, time_range):
        """执行打卡操作
        Args:
            time_range: 时间范围
        Returns:
            bool: 是否成功
        """
        if time_range == "noon_checkin":
            # 中午需要签退1次+签到1次
            print("执行中午打卡流程: 签退1次 + 签到1次")
            # 第一次点击（签退）
            if not self.perform_checkin():
                return False
            time.sleep(2)
            # 第二次点击（签到）
            if not self.perform_checkin():
                return False
        else:
            # 其他时间只需要打卡1次
            if not self.perform_checkin():
                return False
        
        return True
    
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
        
        try:
            # 第一步：设置模拟器
            success, message = self.setup_emulator()
            if not success:
                result["message"] = message
                print(result["message"])
                return result
            
            # 第二步：准备打卡
            success, message, checkin_records, screenshot_path = self.prepare_checkin()
            if not success:
                result["message"] = message
                print(result["message"])
                return result
            
            result["checkin_records"] = checkin_records
            if screenshot_path:
                result["screenshots"]["before"] = screenshot_path
            
            # 第三步：检查打卡状态
            can_checkin, message, time_range, status_info = self.check_checkin_status(checkin_records, screenshot_path)
            if not can_checkin:
                result["message"] = self.build_message(message, checkin_records)
                print(result["message"])
                if message == "当前时段内已经打过卡，跳过打卡操作" or message == "当前时间不在打卡范围内，不需要打卡":
                    result["success"] = True
                return result
            
            # 第四步：用户确认
            if user_confirm_callback:
                user_confirm = user_confirm_callback(status_info)
            else:
                # 命令行模式
                user_confirm = input("是否执行打卡？(y/n): ")
                user_confirm = user_confirm.lower() == 'y'
            
            if not user_confirm:
                result["message"] = self.build_message("用户取消打卡", checkin_records)
                print(result["message"])
                return result
            
            # 第五步：执行打卡
            if not self.perform_checkin_operation(time_range):
                result["message"] = self.build_message("打卡失败", checkin_records)
                print(result["message"])
                return result
            
            # 第六步：汇报结果
            time.sleep(2)
            result_screenshot = self.take_screenshot("after_checkin.png")
            result["screenshots"]["after"] = result_screenshot
            result["success"] = True
            # 重新检测打卡记录，确保显示最新的
            updated_checkin_records = self.detect_checkin_records()
            if updated_checkin_records:
                checkin_records = updated_checkin_records
            result["message"] = self.build_message(f"打卡完成！结果截图已保存至: {result_screenshot}", checkin_records)
            # 输出缓存统计信息
            total_cache = self.cache_stats['hits'] + self.cache_stats['misses']
            cache_hit_rate = (self.cache_stats['hits'] / total_cache * 100) if total_cache > 0 else 0
            print(f"缓存统计: 命中={self.cache_stats['hits']}, 未命中={self.cache_stats['misses']}, 命中率={cache_hit_rate:.1f}%")
            
            print(result["message"])
        finally:
            # 关闭模拟器
            self.stop_emulator()
            
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
    # 直接执行auto_checkin.py的逻辑
    import subprocess
    import os
    
    # 执行auto_checkin.py脚本
    script_path = os.path.join(os.path.dirname(__file__), "auto_checkin.py")
    # 直接执行并显示输出
    result = subprocess.run(["python3", script_path])
    
    # 构建结果字典
    return_dict = {
        "success": result.returncode == 0,
        "message": "打卡流程执行完成",
        "screenshots": {},
        "checkin_records": []
    }
    
    return return_dict

if __name__ == "__main__":
    run_checkin()