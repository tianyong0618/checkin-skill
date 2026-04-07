#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/tianyong/skills/checkin-skill/scripts')
from skill_checkin import CheckinSkill
import datetime

# 测试实际的工作日判断功能（从配置文件读取节假日信息）
def test_actual_weekday_check():
    print("=== 测试实际的工作日判断功能 ===")
    
    # 创建 CheckinSkill 实例
    skill = CheckinSkill()
    
    # 测试当前日期
    print("\n测试当前日期:")
    result = skill.is_weekday()
    print(f"结果: {result}")
    
    # 测试清明节（节假日）
    print("\n测试清明节:")
    # 保存原始的 datetime.now
    original_now = datetime.datetime.now
    
    # 模拟清明节
    datetime.datetime.now = lambda: datetime.datetime(2026, 4, 4, 9, 0, 0)  # 清明节
    result = skill.is_weekday()
    print(f"结果: {result}")
    
    # 测试工作日
    print("\n测试工作日:")
    # 模拟工作日
    datetime.datetime.now = lambda: datetime.datetime(2026, 4, 7, 9, 0, 0)  # 周一
    result = skill.is_weekday()
    print(f"结果: {result}")
    
    # 恢复原始的 datetime.now
    datetime.datetime.now = original_now
    
    print("\n✅ 测试完成！")

if __name__ == "__main__":
    test_actual_weekday_check()
