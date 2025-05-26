import unittest
import json
import os

class TestPterodactylEgg(unittest.TestCase):
    def setUp(self):
        self.egg_path = os.path.join('..', 'pterodactyl', 'egg', 'egg-universal-modloader-egg.json')
        with open(self.egg_path, 'r') as f:
            self.egg_data = json.load(f)

    def test_egg_structure(self):
        """Test if egg JSON has all required fields"""
        required_fields = ['meta', 'name', 'author', 'description', 'variables']
        for field in required_fields:
            self.assertIn(field, self.egg_data)

    def test_minecraft_version_variable(self):
        """Test Minecraft version variable configuration"""
        mc_var = next(v for v in self.egg_data['variables'] if v['env_variable'] == 'MINECRAFT_VERSION')
        self.assertEqual(mc_var['default_value'], 'latest')
        self.assertTrue(mc_var['user_editable'])

    def test_modloader_type_variable(self):
        """Test modloader type variable configuration"""
        mod_var = next(v for v in self.egg_data['variables'] if v['env_variable'] == 'MOD_LOADER_TYPE')
        self.assertIn('rules', mod_var)
        self.assertIn('vanilla', mod_var['rules'])
        self.assertIn('forge', mod_var['rules'])
        self.assertIn('fabric', mod_var['rules'])
        self.assertIn('neoforge', mod_var['rules'])
