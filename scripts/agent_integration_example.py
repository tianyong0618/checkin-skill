#!/usr/bin/env python3
# Agent集成打卡Skill示例
import sys
import os

# 添加当前目录到路径，以便导入skill_checkin
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from skill_checkin import run_checkin

def user_confirm_callback(status_info):
    """用户确认回调函数
    Args:
        status_info: 打卡状态信息
    Returns:
        bool: 用户是否确认打卡
    """
    print("\n=== 打卡状态确认 ===")
    print(f"定位状态: {status_info['location']}")
    print(f"当前时间: {status_info['current_time']}")
    print(f"按钮状态: {status_info['button_status']}")
    
    # 这里可以实现agent的确认逻辑
    # 例如通过对话接口询问用户
    user_input = input("是否执行打卡？(y/n): ")
    return user_input.lower() == 'y'

def main():
    """Agent主函数"""
    print("Agent: 开始执行打卡任务")
    
    # 调用打卡Skill
    result = run_checkin(user_confirm_callback)
    
    # 处理打卡结果
    if result['success']:
        print(f"Agent: 打卡成功！{result['message']}")
        print(f"Agent: 打卡前截图: {result['screenshots'].get('before')}")
        print(f"Agent: 打卡后截图: {result['screenshots'].get('after')}")
    else:
        print(f"Agent: 打卡失败: {result['message']}")
    
    print("Agent: 打卡任务完成")

if __name__ == "__main__":
    main()