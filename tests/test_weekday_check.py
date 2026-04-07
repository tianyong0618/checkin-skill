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
            # 模拟配置文件中的节假日信息（根据中国政府网官方通知）
            self.config = {
                "holidays": {
                    "2026": [
                        {"name": "元旦", "date": "2026-01-01"},
                        {"name": "元旦", "date": "2026-01-02"},
                        {"name": "元旦", "date": "2026-01-03"},
                        {"name": "春节", "date": "2026-02-15"},
                        {"name": "春节", "date": "2026-02-16"},  # 除夕
                        {"name": "春节", "date": "2026-02-17"},
                        {"name": "春节", "date": "2026-02-18"},
                        {"name": "春节", "date": "2026-02-19"},
                        {"name": "春节", "date": "2026-02-20"},
                        {"name": "春节", "date": "2026-02-21"},
                        {"name": "春节", "date": "2026-02-22"},
                        {"name": "春节", "date": "2026-02-23"},
                        {"name": "清明节", "date": "2026-04-04"},
                        {"name": "劳动节", "date": "2026-05-01"},
                        {"name": "劳动节", "date": "2026-05-02"},
                        {"name": "劳动节", "date": "2026-05-03"},
                        {"name": "劳动节", "date": "2026-05-04"},
                        {"name": "劳动节", "date": "2026-05-05"},
                        {"name": "端午节", "date": "2026-06-19"},
                        {"name": "端午节", "date": "2026-06-20"},
                        {"name": "端午节", "date": "2026-06-21"},
                        {"name": "中秋节", "date": "2026-09-25"},
                        {"name": "中秋节", "date": "2026-09-26"},
                        {"name": "中秋节", "date": "2026-09-27"},
                        {"name": "国庆节", "date": "2026-10-01"},
                        {"name": "国庆节", "date": "2026-10-02"},
                        {"name": "国庆节", "date": "2026-10-03"},
                        {"name": "国庆节", "date": "2026-10-04"},
                        {"name": "国庆节", "date": "2026-10-05"},
                        {"name": "国庆节", "date": "2026-10-06"},
                        {"name": "国庆节", "date": "2026-10-07"}
                    ]
                },
                "workdays": {
                    "2026": ["2026-01-04", "2026-02-14"]  # 调休上班日
                }
            }
        
        def is_weekday(self, test_date):
            """判断指定日期是否为工作日（非周末且非节假日，或调休上班）
            Args:
                test_date: 测试日期，格式为 datetime.date
            Returns:
                bool: 是否为工作日
            """
            test_date_str = test_date.strftime("%Y-%m-%d")
            current_year = str(test_date.year)
            
            # 检查是否为调休上班日
            workdays_config = self.config.get('workdays', {})
            year_workdays = workdays_config.get(current_year, [])
            if test_date_str in year_workdays:
                print(f"日期: {test_date} 是调休上班日，需要打卡")
                return True
            
            # 检查是否为周末
            if test_date.weekday() >= 5:  # 5=周六, 6=周日
                print(f"日期: {test_date} 是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][test_date.weekday()]}, 属于周末，不需要打卡")
                return False
            
            # 检查是否为节假日
            # 从配置文件中读取节假日信息
            holidays_config = self.config.get('holidays', {})
            year_holidays = holidays_config.get(current_year, [])
            
            for holiday in year_holidays:
                if 'date' in holiday:
                    holiday_date = holiday['date']
                    if holiday_date == test_date_str:
                        print(f"日期: {test_date} 是{holiday['name']}，属于节假日，不需要打卡")
                        return False
            
            print(f"日期: {test_date} 是工作日，需要打卡")
            return True
    
    test_skill = TestCheckinSkill()
    
    # 测试周末
    print("=== 测试周末 ===")
    # 测试周六
    test_date = datetime.date(2026, 4, 4)  # 清明节（周六）
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "清明节应该返回False"
    
    # 测试周日
    test_date = datetime.date(2026, 4, 5)  # 周日
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "周日应该返回False"
    
    # 测试工作日
    test_date = datetime.date(2026, 4, 6)  # 周一
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert result, "工作日应该返回True"
    
    # 测试节假日
    print("\n=== 测试节假日 ===")
    
    # 测试劳动节
    test_date = datetime.date(2026, 5, 1)  # 劳动节
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "劳动节应该返回False"
    
    # 测试除夕
    test_date = datetime.date(2026, 2, 16)  # 除夕
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert not result, "除夕应该返回False"
    
    # 测试调休上班日
    print("\n=== 测试调休上班日 ===")
    # 测试调休上班日
    test_date = datetime.date(2026, 1, 4)  # 调休上班日
    result = test_skill.is_weekday(test_date)
    print(f"结果: {result}")
    assert result, "调休上班日应该返回True"
    
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
