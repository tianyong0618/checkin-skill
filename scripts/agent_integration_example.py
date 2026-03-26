#!/usr/bin/env python3
# Agent集成打卡Skill示例
import sys
import os

# 添加当前目录到路径，以便导入skill_checkin
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from skill_checkin import run_checkin

def main():
    """Agent主函数"""
    print("Agent: 开始执行打卡任务")
    
    # 调用打卡Skill
    # 注意：现在run_checkin会直接执行auto_checkin.py的逻辑，包括自动确认打卡
    result = run_checkin()
    
    # 处理打卡结果
    if result['success']:
        print(f"Agent: 打卡成功！{result['message']}")
    else:
        print(f"Agent: 打卡失败: {result['message']}")
    
    print("Agent: 打卡任务完成")

if __name__ == "__main__":
    main()