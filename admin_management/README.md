# Admin Server Update Management

This module provides an admin interface to update the server from git and restart the application safely.

## Features

- **Git Update**: Automatically fetches and pulls latest changes from the git repository
- **Dependency Management**: Updates Python dependencies using `uv sync`
- **Static Files**: Collects static files for production
- **Database Migrations**: Runs any pending database migrations
- **Safe Restart**: Gracefully restarts the server using PM2
- **Status Monitoring**: Check current git and server status
- **Web Dashboard**: User-friendly web interface for updates

## Endpoints

### API Endpoints

- `POST /admin/update/` - Trigger server update and restart
- `GET /admin/status/` - Get current git and server status
- `GET /admin/dashboard/` - Web dashboard interface

### Security

- All endpoints require staff privileges (`@staff_member_required`)
- Only authenticated staff users can access these endpoints
- CSRF protection is disabled for API endpoints to allow programmatic access

## Web Dashboard

Visit `/admin/dashboard/` to access the web interface:

1. **Status Check**: View current git status and check for available updates
2. **Update Server**: Trigger the full update process with live feedback
3. **Logs**: View real-time update progress and any error messages

## API Usage

### Check Status
```bash
curl -X GET http://your-domain/admin/status/ \
  -H "Cookie: sessionid=your-session-id"
```

### Trigger Update
```bash
curl -X POST http://your-domain/admin/update/ \
  -H "Cookie: sessionid=your-session-id" \
  -H "Content-Type: application/json"
```

## Update Process

The update process follows these steps:

1. **Git Fetch**: Fetch latest changes from origin
2. **Git Pull**: Pull changes to local repository
3. **Dependencies**: Update Python packages with `uv sync`
4. **Static Files**: Collect static files with `collectstatic`
5. **Migrations**: Run database migrations
6. **Restart**: Gracefully restart the server using PM2

## Error Handling

- Each step is individually tracked for error reporting
- Process stops at first failure and reports the failing step
- Timeouts are set for each operation to prevent hanging
- Detailed error messages and logs are provided

## Files Created

- `admin_management/` - Django app directory
- `admin_management/views.py` - API endpoints and dashboard
- `admin_management/urls.py` - URL routing
- `admin_management/templates/admin_management/dashboard.html` - Web interface
- `admin_management/tests.py` - Unit tests
- `restart_server.sh` - Safe server restart script

## Configuration

The update system uses the following:

- Git repository: Assumes origin/master branch
- PM2 process name: `student-attendance-django`
- Python package manager: `uv`
- Restart script: `restart_server.sh`

## Logging

All operations are logged using Django's logging system. Check your application logs for detailed information about update operations.

## Safety Features

- Staff-only access
- Graceful PM2 restarts
- Individual step error reporting
- Timeout protection
- Rollback-safe operations
