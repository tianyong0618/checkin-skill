#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/tianyong/.openclaw/skills/checkin-skill/scripts')
from skill_checkin import CheckinSkill

def auto_confirm_callback(status_info):
    """自动确认打卡"""
    print(f"定位状态: {status_info['location']}")
    print(f"当前时间: {status_info['current_time']}")
    print(f"按钮状态: {status_info['button_status']}")
    print(f"打卡记录数量: {status_info['checkin_records_count']}")
    print("自动确认：执行打卡")
    return True

skill = CheckinSkill()
result = skill.run(auto_confirm_callback)

if result['success']:
    print(f"\n✅ 打卡成功！")
    print(f"消息: {result['message']}")
    if 'after' in result['screenshots']:
        print(f"结果截图: {result['screenshots']['after']}")
else:
    print(f"\n❌ 打卡失败: {result['message']}")

sys.exit(0 if result['success'] else 1)
