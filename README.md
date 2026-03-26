# 打卡技能使用文档

## 功能介绍

打卡技能是一个自动化考勤打卡工具，通过ADB命令控制Android设备或模拟器，实现自动签到和签退功能。

## 主要功能

- 自动启动模拟器（如果未运行）
- 自动启动纷享销客应用
- 自动导航到考勤页面
- 自动检测打卡状态（定位、时间范围）
- 自动执行打卡操作
- 支持智能签到、签到和签退
- 生成打卡报告和截图

## 环境要求

- Python 3.7+
- Android SDK（包含ADB工具）
- Android模拟器或实际Android设备
- 纷享销客应用已安装

## 模拟器配置

| 配置项     | 值                            |
| ------- | ---------------------------- |
| 名称      | daka                         |
| 分辨率     | 1440 × 2560: 560dpi          |
| API版本   | Android API 36 (Google APIs) |
| CPU/ABI | arm64                        |
| 磁盘大小    | 6.9 GB                       |

## 定位设置

安装完模拟器后，需要设置模拟器的定位。可以使用项目中的GPX文件来设置经纬度：

1. 启动模拟器
2. 在Android Studio的Device Manager中，选择对应的模拟器
3. 点击"Extended controls"按钮
4. 选择"Location"选项卡
5. 点击"Load GPX"按钮，选择项目中的 `/Users/tianyong/skills/checkin-skill/temp/location.gpx` 文件
6. 点击"Play"按钮，模拟器的定位将被设置为GPX文件中指定的位置

## 安装步骤

1. 克隆或下载本项目到本地
2. 确保Android SDK已安装并配置好环境变量
3. 确保模拟器已创建（名称默认为"daka"）
4. 安装纷享销客应用到模拟器或设备

## 配置说明

配置文件位于 `config/config.json`，包含以下配置项：

### 基本配置

- `package_name`: 应用包名，默认为 "com.facishare.fs"
- `activity_name`: 应用主Activity，默认为 "com.fxiaoke.host.IndexActivity"
- `emulator_name`: 模拟器名称，默认为 "daka"
- `screenshot_dir`: 截图保存目录，默认为 "../screenshots"

### ADB配置

- `common_paths`: ADB工具的可能路径列表

### 模拟器配置

- `paths`: 不同操作系统下的模拟器路径

### 坐标配置

- `app_button`: 应用按钮的可能坐标
- `preset_attendance`: 考勤选项的可能坐标
- `default_checkin`: 默认打卡坐标

### 时间范围

- `morning_checkin`: 早上签到时间范围
- `noon_checkin`: 中午打卡时间范围
- `evening_checkout`: 晚上签退时间范围

### UI文本

- 各种UI元素的文本，用于定位元素

### 等待时间

- 各种操作的等待时间配置

## 使用方法

### 命令行运行

```bash
python3 scripts/skill_checkin.py
```

### 作为模块调用

```python
from scripts.skill_checkin import run_checkin

# 运行打卡流程
result = run_checkin()
print(result)
```

### 回调函数

可以提供一个回调函数来获取用户确认：

```python
def user_confirm_callback(status_info):
    print(f"定位状态: {status_info['location']}")
    print(f"当前时间: {status_info['current_time']}")
    print(f"按钮状态: {status_info['button_status']}")
    print(f"打卡记录数量: {status_info['checkin_records_count']}")
    # 返回True表示确认打卡，False表示取消
    return True

result = run_checkin(user_confirm_callback)
```

## 运行流程

1. 检查模拟器状态
2. 启动模拟器（如果未运行）
3. 启动纷享销客应用
4. 导航到考勤页面
5. 检测打卡记录
6. 检查定位状态和时间范围
7. 获取用户确认
8. 执行打卡操作
9. 生成打卡报告

## 故障排除

### 模拟器启动失败

- 检查模拟器名称是否正确
- 检查Android SDK是否正确安装
- 检查模拟器是否能够正常启动

### 应用启动失败

- 检查应用是否已安装
- 检查包名和Activity名称是否正确

### 导航失败

- 检查UI文本配置是否正确
- 检查坐标配置是否适合当前设备分辨率

### 打卡失败

- 检查定位服务是否开启
- 检查是否在允许的时间范围内
- 检查网络连接是否正常

## 日志和截图

- 运行过程中的日志会输出到控制台
- 截图会保存在 `screenshots` 目录下
- 可以通过截图查看运行状态和打卡结果

## 注意事项

- 确保模拟器或设备已登录纷享销客账号
- 确保定位服务已开启
- 确保在允许的时间范围内运行
- 定期清理截图目录，避免占用过多磁盘空间

## 安全考虑

- ADB工具来源要可信
- 避免在不安全的网络环境中使用
- 不要在日志中记录敏感信息
- 定期清理可能包含敏感信息的截图文件

