from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
import json


class AdminManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username='admin',
            password='testpass',
            is_staff=True
        )
        # Create a regular user
        self.regular_user = User.objects.create_user(
            username='user',
            password='testpass',
            is_staff=False
        )
    
    def test_update_server_requires_staff(self):
        """Test that update endpoint requires staff privileges"""
        # Test unauthenticated access
        response = self.client.post(reverse('admin_management:update_server'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test regular user access
        self.client.login(username='user', password='testpass')
        response = self.client.post(reverse('admin_management:update_server'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_status_requires_staff(self):
        """Test that status endpoint requires staff privileges"""
        # Test unauthenticated access
        response = self.client.get(reverse('admin_management:update_status'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test regular user access
        self.client.login(username='user', password='testpass')
        response = self.client.get(reverse('admin_management:update_status'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_requires_staff(self):
        """Test that dashboard requires staff privileges"""
        # Test unauthenticated access
        response = self.client.get(reverse('admin_management:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test regular user access
        self.client.login(username='user', password='testpass')
        response = self.client.get(reverse('admin_management:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test staff user access
        self.client.login(username='admin', password='testpass')
        response = self.client.get(reverse('admin_management:dashboard'))
        self.assertEqual(response.status_code, 200)
    
    @patch('admin_management.views.subprocess.run')
    def test_update_server_success(self, mock_run):
        """Test successful server update"""
        # Mock successful subprocess calls
        mock_run.return_value = MagicMock(returncode=0, stdout='Success', stderr='')
        
        self.client.login(username='admin', password='testpass')
        response = self.client.post(reverse('admin_management:update_server'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
    
    @patch('admin_management.views.subprocess.run')
    def test_update_server_git_failure(self, mock_run):
        """Test server update with git failure"""
        # Mock failed git fetch
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Git error')
        
        self.client.login(username='admin', password='testpass')
        response = self.client.post(reverse('admin_management:update_server'))
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['step'], 'git_fetch')
    
    @patch('admin_management.views.subprocess.run')
    def test_status_check(self, mock_run):
        """Test status check functionality"""
        # Mock successful subprocess calls
        mock_run.return_value = MagicMock(returncode=0, stdout='Clean status', stderr='')
        
        self.client.login(username='admin', password='testpass')
        response = self.client.get(reverse('admin_management:update_status'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
