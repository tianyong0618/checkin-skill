#!/usr/bin/env python3
# 打卡技能测试文件
import unittest
import os
import sys
import tempfile

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.skill_checkin import CheckinSkill

class TestCheckinSkill(unittest.TestCase):
    """测试打卡技能"""
    
    def setUp(self):
        """设置测试环境"""
        self.skill = CheckinSkill()
    
    def test_load_config(self):
        """测试加载配置文件"""
        config = self.skill.load_config()
        self.assertIsInstance(config, dict)
        self.assertIn('general', config)
        self.assertIn('adb', config)
        self.assertIn('coordinates', config)
    
    def test_get_default_config(self):
        """测试获取默认配置"""
        config = self.skill.get_default_config()
        self.assertIsInstance(config, dict)
        self.assertIn('general', config)
        self.assertEqual(config['general']['package_name'], 'com.facishare.fs')
    
    def test_find_adb(self):
        """测试查找ADB工具"""
        adb_path = self.skill.find_adb()
        if adb_path:
            self.assertTrue(os.path.exists(adb_path))
    
    def test_parse_ui_xml(self):
        """测试解析UI XML文件"""
        # 创建临时XML文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><hierarchy><node text="测试" bounds="[0,0][100,100]"/></hierarchy>')
            temp_xml_path = f.name
        
        try:
            xml_content = self.skill.parse_ui_xml(temp_xml_path)
            self.assertIn('测试', xml_content)
        finally:
            if os.path.exists(temp_xml_path):
                os.unlink(temp_xml_path)
    
    def test_find_element_by_text(self):
        """测试根据文本查找元素"""
        xml_content = '<?xml version="1.0" encoding="UTF-8"?><hierarchy><node text="考勤" bounds="[100,200][300,400]"/></hierarchy>'
        bounds = self.skill.find_element_by_text(xml_content, '考勤')
        self.assertEqual(bounds, (100, 200, 300, 400))
    
    def test_get_element_center(self):
        """测试计算元素中心点坐标"""
        bounds = (100, 200, 300, 400)
        center = self.skill.get_element_center(bounds)
        self.assertEqual(center, (200, 300))
    
    def test_check_time_range(self):
        """测试检查时间范围"""
        # 这里可以根据实际时间进行测试
        time_range = self.skill.check_time_range()
        self.assertIn(time_range, ['morning_checkin', 'noon_checkin', 'evening_checkout', 'out_of_range'])
    
    def test_wait_for_element(self):
        """测试等待元素出现"""
        # 这个测试可能需要实际的设备环境
        # 这里只做简单的测试，确保方法能够正常调用
        result = self.skill.wait_for_element('测试', timeout=1)
        self.assertIsNone(result)  # 因为没有实际的元素，应该返回None

if __name__ == '__main__':
    unittest.main()