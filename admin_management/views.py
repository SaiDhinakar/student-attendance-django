import subprocess
import os
import logging
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.shortcuts import render
from pathlib import Path

logger = logging.getLogger(__name__)

@staff_member_required
def dashboard(request):
    """
    Admin dashboard for server management.
    """
    return render(request, 'admin_management/dashboard.html')

@staff_member_required
@require_POST
@csrf_exempt
def update_server(request):
    """
    Admin endpoint to update the server from git and restart the application.
    Requires staff privileges.
    """
    try:
        base_dir = Path(settings.BASE_DIR)
        
        # Change to the project directory
        os.chdir(base_dir)
        
        # Step 1: Git fetch
        logger.info("Starting git fetch...")
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            error_msg = f"Git fetch failed: {fetch_result.stderr}"
            logger.error(error_msg)
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'step': 'git_fetch'
            }, status=500)
        
        # Step 2: Git pull
        logger.info("Starting git pull...")
        pull_result = subprocess.run(
            ['git', 'pull', 'origin', 'master'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if pull_result.returncode != 0:
            error_msg = f"Git pull failed: {pull_result.stderr}"
            logger.error(error_msg)
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'step': 'git_pull'
            }, status=500)
        
        # Step 3: Install/update dependencies if requirements changed
        logger.info("Checking for dependency updates...")
        if os.path.exists(base_dir / 'pyproject.toml'):
            uv_result = subprocess.run(
                ['uv', 'sync'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if uv_result.returncode != 0:
                logger.warning(f"UV sync had issues: {uv_result.stderr}")
                # Don't fail the entire update for dependency issues
        
        # Step 4: Collect static files if needed
        logger.info("Collecting static files...")
        collect_static_result = subprocess.run(
            ['python', 'manage.py', 'collectstatic', '--noinput'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if collect_static_result.returncode != 0:
            logger.warning(f"Static files collection had issues: {collect_static_result.stderr}")
            # Don't fail the entire update for static files issues
        
        # Step 5: Run database migrations if needed
        logger.info("Running database migrations...")
        migrate_result = subprocess.run(
            ['python', 'manage.py', 'migrate'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if migrate_result.returncode != 0:
            logger.warning(f"Database migrations had issues: {migrate_result.stderr}")
            # Don't fail the entire update for migration issues
        
        # Step 6: Restart the server using the safer restart script
        logger.info("Restarting server...")
        
        restart_result = subprocess.run(
            ['bash', str(base_dir / 'restart_server.sh')],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if restart_result.returncode != 0:
            error_msg = f"Server restart failed: {restart_result.stderr}"
            logger.error(error_msg)
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'step': 'server_restart'
            }, status=500)
        
        logger.info("Server update completed successfully")
        return JsonResponse({
            'success': True,
            'message': 'Server updated and restarted successfully',
            'git_output': {
                'fetch': fetch_result.stdout,
                'pull': pull_result.stdout
            }
        })
        
    except subprocess.TimeoutExpired as e:
        error_msg = f"Operation timed out: {str(e)}"
        logger.error(error_msg)
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'step': 'timeout'
        }, status=500)
        
    except Exception as e:
        error_msg = f"Unexpected error during update: {str(e)}"
        logger.error(error_msg)
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'step': 'unexpected_error'
        }, status=500)


@staff_member_required
def update_status(request):
    """
    Check the current git status and server status.
    """
    try:
        base_dir = Path(settings.BASE_DIR)
        os.chdir(base_dir)
        
        # Check git status
        git_status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check if there are remote updates available
        git_fetch_result = subprocess.run(
            ['git', 'fetch', 'origin'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        git_log_result = subprocess.run(
            ['git', 'log', 'HEAD..origin/master', '--oneline'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check server status via pm2
        pm2_status_result = subprocess.run(
            ['pm2', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return JsonResponse({
            'success': True,
            'git_status': {
                'local_changes': git_status_result.stdout.strip(),
                'remote_updates': git_log_result.stdout.strip(),
                'updates_available': bool(git_log_result.stdout.strip())
            },
            'server_status': pm2_status_result.stdout
        })
        
    except Exception as e:
        error_msg = f"Error checking status: {str(e)}"
        logger.error(error_msg)
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)
