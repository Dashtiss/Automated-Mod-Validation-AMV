import unittest
import httpx
import os
import time
import asyncio

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.panel_url = os.getenv('PTERODACTYL_URL', 'http://localhost')
        self.api_key = os.getenv('PTERODACTYL_API_KEY', '')
        
    async def async_test_server_creation(self):
        """Test server creation via Pterodactyl API"""
        if not self.api_key:
            self.skipTest("No API key provided")
            
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        server_data = {
            "name": "Test MC Server",
            "user": 1,
            "egg": 1,
            "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
            "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
            "environment": {
                "MINECRAFT_VERSION": "latest",
                "MOD_LOADER_TYPE": "vanilla",
                "SERVER_JARFILE": "server.jar"
            },
            "limits": {
                "memory": 2048,
                "swap": 0,
                "disk": 5120,
                "io": 500,
                "cpu": 100
            }
        }

        async with httpx.AsyncClient() as client:
            # Create server
            response = await client.post(
                f"{self.panel_url}/api/application/servers",
                headers=headers,
                json=server_data
            )
            
            self.assertEqual(response.status_code, 201)
            server_id = response.json()['attributes']['id']
            
            # Wait for installation
            await asyncio.sleep(5)
            
            # Verify server status
            response = await client.get(
                f"{self.panel_url}/api/application/servers/{server_id}",
                headers=headers
            )
            self.assertEqual(response.status_code, 200)
            
            # Cleanup
            response = await client.delete(
                f"{self.panel_url}/api/application/servers/{server_id}",
                headers=headers
            )
            
    def test_server_creation(self):
        """Synchronous wrapper for async test"""
        asyncio.run(self.async_test_server_creation())
