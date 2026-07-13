![TUP](https://img.shields.io/badge/TUP-Cavite-red?style=for-the-badge)
![BET-COET](https://img.shields.io/badge/BET--COET-green?style=for-the-badge)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)

# 📖 P.A.B.A.S.A
Platform for Automated Basic Reading and Speech Assessment

## 📝 Research Title
Development of Guide Reading Evaluation System for Grade 2 Students in Salawag Elementary School

## 📚 About
P.A.B.A.S.A is a web-based reading evaluation system designed to assist teachers in assessing and monitoring the reading literacy of Grade 2 students.
The system utilizes speech recognition technology to evaluate:  
- 📊 Pronunciation Accuracy  
- ⏱️ Reading Speed  
- 🔍 Reading Clarity

It provides automated feedback and performance reports, enabling data-driven decisions for remedial instruction.

## 👥 Team Members
- 👨‍💻 Leonardo Basco III
- 👩‍💻 Lady Caroline Dorongon
- 👨‍💻 Amiel John Padasay
- 👩‍💻 Dona Palacios
- 👩‍💻 Reyna Marie Santos
- 👨‍💻 Maeven Tapa

## 🎯 Course Details
- Course Code: BET3
- Course Title: Technical Research
- Institution: TUP Cavite

## 🧰 Technology Stack

P.A.B.A.S.A uses a server-rendered Django architecture enhanced with responsive
frontend components, browser media features, and cloud speech processing.

### Backend
- **Python 3.13** and **Django 6.0.3** handle routing, authentication, forms,
  application logic, and database access through the Django ORM.
- **Gunicorn** runs the Django WSGI application in production.
- **WhiteNoise** serves collected CSS, JavaScript, images, and other static assets.

### Frontend
- **Django templates**, **HTML5**, **CSS3**, and **vanilla JavaScript** build the
  server-rendered and interactive user interface.
- **Bootstrap 5.3.3** and **Bootstrap Icons** provide responsive layouts and reusable
  interface components.
- **Chart.js** displays dashboard analytics, while **PDF.js** provides in-browser PDF
  previews.
- The browser **MediaRecorder** and **Web Audio APIs** capture learners' reading audio.

### Database
- **SQLite 3** stores users, classes, learning materials, assessments, attempts, and
  progress data through Django models and migrations.

### Speech and Document Processing
- **Google Cloud Speech-to-Text** transcribes reading activities for automated
  assessment, while Google Cloud text-to-speech services support read-aloud audio.
- **Tesseract OCR**, **pytesseract**, and **Pillow** extract and prepare text from
  uploaded images.
- **pypdf** extracts text from PDF learning materials, and **ReportLab** generates PDF
  reports.

### Deployment
- **Docker** packages the application with Python and its native system dependencies.
- **Gunicorn** serves the application, Django migrations run during container startup,
  and **WhiteNoise** handles production static files.
- The repository's `Dockerfile`, `Procfile`, and `Aptfile` support DigitalOcean and
  compatible Linux deployment environments.

## 📬 Contact
For any inquiries about this repository, please contact any of the team members listed above.

## ⭐ Acknowledgment
> “Once you learn to read, you will be forever free.”  
> — Frederick Douglass

This project is a product of our dedication and shared vision to help young learners grow through reading. We extend our sincere gratitude to the Technological University of the Philippines – Cavite Campus, our mentors, and the teachers and students of Salawag Elementary School for their guidance and inspiration. To our families and team members, thank you for your unwavering support and strength. May this system contribute, even in the smallest way, to a future where every child learns to read with confidence and purpose.
