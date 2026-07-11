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

## 🧰 OCR deployment note
Image uploads use Tesseract through `pytesseract`. The native Tesseract executable must
also be installed on every development and production machine; installing Python
dependencies alone is not enough. Install the English (`eng`) and Filipino (`fil`)
trained-data files.

Optional environment variables:

- `TESSERACT_CMD`: full executable path when `tesseract` is not on `PATH`
- `OCR_TESSDATA_DIR`: trained-data directory when it is outside the system path
- `OCR_LANGUAGES`: language combination, default `eng+fil`
- `OCR_TIMEOUT_SECONDS`: per-image-candidate timeout, default `15`

On Debian/Ubuntu, install `tesseract-ocr`, `tesseract-ocr-eng`, and
`tesseract-ocr-fil`. For container deployments, install these system packages in the
container image.

### DigitalOcean deployment

**App Platform:** Pabasa includes a root `Dockerfile` that installs the native OCR
engine and both language models. App Platform detects a root Dockerfile automatically.
Redeploy the component after pushing it, and remove any custom Run Command so the
Dockerfile `CMD` is used. No `TESSERACT_CMD` value is needed because the executable
is on `PATH`. If you use an `ondigitalocean.app` hostname, add that hostname to the
`ALLOWED_HOSTS` environment variable and its full HTTPS URL to
`CSRF_TRUSTED_ORIGINS`.

For an existing App Platform component pinned to the Python buildpack, the root
`Aptfile` installs Tesseract plus the English and Filipino models without changing
the component or database configuration. Push the `Aptfile`, then use **Force Rebuild
and Deploy** and confirm the build logs detect the Aptfile buildpack.
The `Procfile` also exposes DigitalOcean's Apt-layer executable and trained-data
paths to the running Gunicorn process.

**Droplet:** If Pabasa runs directly on Ubuntu instead of in Docker, install the
engine with `sudo apt update && sudo apt install tesseract-ocr tesseract-ocr-eng
tesseract-ocr-fil`, then restart Gunicorn or the Pabasa systemd service.

## 📬 Contact
For any inquiries about this repository, please contact any of the team members listed above.

## ⭐ Acknowledgment
> “Once you learn to read, you will be forever free.”  
> — Frederick Douglass

This project is a product of our dedication and shared vision to help young learners grow through reading. We extend our sincere gratitude to the Technological University of the Philippines – Cavite Campus, our mentors, and the teachers and students of Salawag Elementary School for their guidance and inspiration. To our families and team members, thank you for your unwavering support and strength. May this system contribute, even in the smallest way, to a future where every child learns to read with confidence and purpose.
