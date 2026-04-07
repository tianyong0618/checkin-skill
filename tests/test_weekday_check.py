#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/tianyong/skills/checkin-skill/scripts')
from skill_checkin import CheckinSkill
import datetime

# 测试工作日判断功能
def test_weekday_check():
    # 创建一个测试类来模拟工作日判断（从配置文件读取节假日信息）
    class TestCheckinSkill:
        def __init__(self):
            # 模拟配置文件中的节假日信息
            self.config = {
                "holidays": {
                    "2026": [
                        {
                            "name": "元旦",
                            "start": "2026-01-01",
                            "end": "2026-01-01"
                        },
                        {
                            "name": "春节",
                            "start": "2026-01-28",
                            "end": "2026-02-03"
                        },
                        {
                            "name": "清明节",
                            "start": "2026-04-04",
                            "end": "2026-04-06"
                        },
                        {
                            "name": "劳动节",
                            "start": "2026-05-01",
                            "end": "2026-05-03"
                        },
                        {
                            "name": "端午节",
                            "start": "2026-06-10",
                            "end": "2026-06-12"
                        },
                        {
                            "name": "中秋节",
                            "start": "2026-09-15",
                            "end": "2026-09-17"
                        },
                        {
                            "name": "国庆节",
                            "start": "2026-10-01",
                            "end": "2026-10-07"
                        }
                    ]
                }
            }
        
        def is_weekday(self, test_date):
            """判断指定日期是否为工作日（非周末且非节假日）
            Args:
                test_date: 测试日期，格式为 datetime.date
            Returns:
                bool: 是否为工作日
            """
            # 检查是否为周末
            if test_date.weekday() >= 5:  # 5=周六, 6=周日
                print(f"日期: {test_date} 是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][test_date.weekday()]}, 属于周末，不需要打卡")
                return False
            
            # 检查是否为节假日
            # 从配置文件中读取节假日信息
            holidays_config = self.config.get('holidays', {})
            current_year = str(test_date.year)
            year_holidays = holidays_config.get(current_year, [])
            
            for holiday in year_holidays:
                start_date = datetime.datetime.strptime(holiday['start'], "%Y-%m-%d").date()
                end_date = datetime.datetime.strptime(holiday['end'], "%Y-%m-%d").date()
                
                if start_date <= test_date <= end_date:
                    print(f"日期: {test_date} 是{holiday['name']}，属于节假日，不需要打卡")
                    return False
            
            print(f"日期: {test_date} 是工作日，需要打卡")
            return True
    
    test_skill = TestCheckinSkill()
    
    # 测试周末
    print("=== 测试周末 ===")
    # 测试周六
    test_date = datetime.date(2026, 4, 5)  # 周六
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "周六应该返回False"
    
    # 测试周日
    test_date = datetime.date(2026, 4, 6)  # 周日
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "周日应该返回False"
    
    # 测试节假日
    print("\n=== 测试节假日 ===")
    # 测试清明节
    test_date = datetime.date(2026, 4, 4)  # 清明节
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "清明节应该返回False"
    
    # 测试劳动节
    test_date = datetime.date(2026, 5, 1)  # 劳动节
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "劳动节应该返回False"
    
    # 测试工作日
    print("\n=== 测试工作日 ===")
    # 测试周一
    test_date = datetime.date(2026, 4, 7)  # 周一
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert result, "工作日应该返回True"
    
    print("\n✅ 所有测试通过！")

if __name__ == "__main__":
    test_weekday_check()
