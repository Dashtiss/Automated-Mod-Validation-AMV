import unittest
import subprocess
import os
import shutil

class TestModLoaderInstallation(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_server'
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_vanilla_installation(self):
        """Test vanilla Minecraft server installation"""
        env = {
            'MINECRAFT_VERSION': 'latest',
            'MOD_LOADER_TYPE': 'vanilla',
            'SERVER_JARFILE': 'server.jar'
        }
        self._run_installation(env)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'server.jar')))

    def test_fabric_installation(self):
        """Test Fabric server installation"""
        env = {
            'MINECRAFT_VERSION': 'latest',
            'MOD_LOADER_TYPE': 'fabric',
            'MODLOADER_VERSION': 'latest',
            'FABRIC_INSTALLER_VERSION': 'latest',
            'SERVER_JARFILE': 'server.jar'
        }
        self._run_installation(env)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'server.jar')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'fabric-server-launcher.properties')))

    def _run_installation(self, env):
        """Helper method to run installation script"""
        script_path = os.path.join('..', 'pterodactyl', 'egg', 'install.sh')
        process = subprocess.run(['bash', script_path], 
                               env={**os.environ, **env},
                               cwd=self.test_dir,
                               capture_output=True,
                               text=True)
        self.assertEqual(process.returncode, 0, f"Installation failed: {process.stderr}")
