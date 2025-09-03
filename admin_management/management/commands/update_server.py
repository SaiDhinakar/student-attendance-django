from django.core.management.base import BaseCommand, CommandError
import subprocess
import os
import sys
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = 'Update server from git and restart the application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-restart',
            action='store_true',
            help='Skip server restart after update',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even with local changes',
        )
        parser.add_argument(
            '--branch',
            type=str,
            default='master',
            help='Git branch to pull from (default: master)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting server update process...')
        )
        
        try:
            base_dir = Path(settings.BASE_DIR)
            os.chdir(base_dir)
            
            # Check git status first
            self.stdout.write('🔍 Checking git status...')
            git_status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if git_status_result.stdout.strip() and not options['force']:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️  Local changes detected:\n' + git_status_result.stdout
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        'Use --force to update anyway, or commit/stash your changes first.'
                    )
                )
                return
            
            # Step 1: Git fetch
            self.stdout.write('📡 Fetching from git origin...')
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if fetch_result.returncode != 0:
                raise CommandError(f'Git fetch failed: {fetch_result.stderr}')
            
            self.stdout.write(self.style.SUCCESS('✓ Git fetch completed'))
            
            # Step 2: Git pull
            self.stdout.write(f'⬇️  Pulling changes from origin/{options["branch"]}...')
            pull_result = subprocess.run(
                ['git', 'pull', 'origin', options['branch']],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if pull_result.returncode != 0:
                raise CommandError(f'Git pull failed: {pull_result.stderr}')
            
            if 'Already up to date' in pull_result.stdout:
                self.stdout.write(self.style.SUCCESS('✓ Already up to date'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Git pull completed'))
                self.stdout.write(f'Changes: {pull_result.stdout.strip()}')
            
            # Step 3: Update dependencies
            if os.path.exists(base_dir / 'pyproject.toml'):
                self.stdout.write('📦 Updating dependencies...')
                uv_result = subprocess.run(
                    ['uv', 'sync'],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if uv_result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS('✓ Dependencies updated'))
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Dependency update issues: {uv_result.stderr}')
                    )
            
            # Step 4: Collect static files
            self.stdout.write('🎨 Collecting static files...')
            collect_static_result = subprocess.run(
                [sys.executable, 'manage.py', 'collectstatic', '--noinput'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if collect_static_result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✓ Static files collected'))
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Static files issues: {collect_static_result.stderr}')
                )
            
            # Step 5: Run migrations
            self.stdout.write('🗄️  Running database migrations...')
            migrate_result = subprocess.run(
                [sys.executable, 'manage.py', 'migrate'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if migrate_result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✓ Migrations completed'))
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Migration issues: {migrate_result.stderr}')
                )
            
            # Step 6: Restart server (if not skipped)
            if not options['skip_restart']:
                self.stdout.write('🔄 Restarting server...')
                restart_result = subprocess.run(
                    ['bash', str(base_dir / 'restart_server.sh')],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if restart_result.returncode != 0:
                    raise CommandError(f'Server restart failed: {restart_result.stderr}')
                
                self.stdout.write(self.style.SUCCESS('✓ Server restarted successfully'))
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️  Server restart skipped (--skip-restart used)')
                )
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Server update completed successfully!')
            )
            
        except subprocess.TimeoutExpired as e:
            raise CommandError(f'Operation timed out: {str(e)}')
        except KeyboardInterrupt:
            raise CommandError('Update interrupted by user')
        except Exception as e:
            raise CommandError(f'Unexpected error: {str(e)}')
