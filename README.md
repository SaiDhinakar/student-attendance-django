<div align="center">
	<h1>🎓 Student Attendance Django</h1>
	<p>
		<img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python 3.12">
		<img src="https://img.shields.io/badge/Django-5.x-green?logo=django" alt="Django 5.x">
		<img src="https://img.shields.io/badge/MySQL-8.x-blue?logo=mysql" alt="MySQL 8.x">
		<img src="https://img.shields.io/github/license/SaiDhinakar/student-attendance-django" alt="License">
	</p>
	<p><b>An AI-powered facial recognition attendance management system built with Django.</b></p>
</div>

---

## ✨ Overview

Student Attendance Django is a robust, AI-driven attendance management platform for educational institutions. It features facial recognition, real-time analytics, and multi-role dashboards for advisors, staff, and admins.

---

## 📋 Prerequisites

- 🐍 Python 3.12
- 🐬 MySQL
- 🧠 Checkpoints (URL: <>)

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/SaiDhinakar/student-attendance-django.git
cd student-attendance-django

# 2. Configure environment
cp .env.example .env  # Edit .env with your settings

# 3. Make scripts executable
chmod +x setup.sh run_server.sh stop_server.sh

# 4. Download the checkpoints from the provided link and place them in the prediction_backend folder
#    (Checkpoints URL: <>)

# 5. Setup project
./setup.sh

# 6. Start the server
./run_server.sh

# 7. Stop the server
./stop_server.sh
```

📂 **Logs:** See the `logs/` directory for server and prediction logs.

---

## 🏗️ Project Structure

```text
student-attendance-django/
├── advisor_dashboard/
├── attendance_dashboard/
├── Authentication/
├── backend/
├── core/
├── docs/
├── Frontend/
├── gallery/
├── logs/
├── prediction_backend/
├── static/
├── StudentAttendance/
├── main.py
├── manage.py
├── setup.sh
├── run_server.sh
├── stop_server.sh
└── README.md
```

---

## 👨‍💻 Authors

<table>
	<tr>
		<td align="center">
			<a href="https://github.com/SaiDhinakar">
				<img src="https://github.com/SaiDhinakar.png" width="80" style="border-radius: 50%" alt="SaiDhinakar"/>
				<br/>
				<sub><b>SaiDhinakar</b></sub>
			</a>
		</td>
		<td align="center">
			<a href="https://github.com/sudo-sidd">
				<img src="https://github.com/sudo-sidd.png" width="80" style="border-radius: 50%" alt="sudo-sidd"/>
				<br/>
				<sub><b>sudo-sidd</b></sub>
			</a>
		</td>
		<td align="center">
			<a href="https://github.com/mithrajith">
				<img src="https://github.com/mithrajith.png" width="80" style="border-radius: 50%" alt="mithrajith"/>
				<br/>
				<sub><b>mithrajith</b></sub>
			</a>
		</td>
	</tr>
</table>

---

📝 TODO

- [ ] Daily attendance report automation to send it to WhatsApp for daily student report to the parent group.
- [ ] Some more improvements coming soon!

---

## 📚 Documentation

- 📐 [Architecture](docs/ARCHITECTURE.md)
- 📖 [References](docs/REFERENCES.md)q

<div align="center">
	<br><br>
	<a href="https://github.com/SaiDhinakar/student-attendance-django/issues" target="_blank">
		<img src="https://img.shields.io/badge/Create%20Issue-EC4899?style=for-the-badge&logo=github" alt="Create Issue"/>
	</a>
	<a href="https://github.com/SaiDhinakar/student-attendance-django/pulls" target="_blank">
		<img src="https://img.shields.io/badge/Give%20PR-6366F1?style=for-the-badge&logo=github" alt="Give PR"/>
	</a>
	<a href="https://github.com/SaiDhinakar/student-attendance-django/fork" target="_blank">
		<img src="https://img.shields.io/badge/Fork%20Repo-22D3EE?style=for-the-badge&logo=github" alt="Fork Repo"/>
	</a>
	<a href="https://github.com/SaiDhinakar/student-attendance-django/stargazers" target="_blank">
		<img src="https://img.shields.io/github/stars/SaiDhinakar/student-attendance-django?style=for-the-badge&label=Star&color=F59E42&logo=github" alt="Star Repo"/>
	</a>
</div>
