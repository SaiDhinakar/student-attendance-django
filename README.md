# Student Attendance Django System

An AI-powered facial recognition attendance management system built with Django.

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd student-attendance-django
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Install and run
pip install -r requirements.txt
python manage.py migrate
python manage.py load_sample_data
python setup_complete_groups.py
python manage.py runserver

# Access at http://127.0.0.1:8000
# Login: staff_user/staff123, advisor_user/advisor123, admin/admin123
```

## 📚 Complete Documentation

For comprehensive documentation including:
- Detailed installation instructions
- API documentation
- System architecture
- Recent updates and project status
- Testing procedures

**See: [`readmeai.md`](./readmeai.md)** - Our AI-maintained documentation that stays current with all project changes.

## 🎯 Key Features

- **Facial Recognition**: Automated student attendance using ML
- **Multi-Role System**: Staff, Advisor, and Admin dashboards
- **Real-time Processing**: Camera capture and image upload
- **Comprehensive Reporting**: Attendance analytics and tracking

## 🔧 Tech Stack

- **Backend**: Django 5.2.5, Python 3.12+
- **ML**: YOLO 11, LightCNN, PyTorch
- **Frontend**: HTML5/CSS3/JS, TailwindCSS
- **Database**: SQLite (dev), PostgreSQL (prod)

## 📊 Current Status

- ✅ 459 students in database
- ✅ 5 departments with real data
- ✅ Gallery-database synchronization complete
- ✅ Full API integration working
- 🔄 UI enhancement in progress

---

**For detailed documentation and latest updates**: [`readmeai.md`](./readmeai.md)