# ใช้ Python runtime อย่างเป็นทางการเป็น base image
FROM python:3.11-slim

# ตั้งค่าตัวแปรสภาพแวดล้อม
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ตั้งค่าไดเร็กทอรีทำงานในคอนเทนเนอร์
WORKDIR /app

# คัดลอกไฟล์ requirements.txt ไปยังคอนเทนเนอร์
COPY requirements.txt /app/

# ติดตั้ง dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดที่เหลือของแอปพลิเคชันไปยังคอนเทนเนอร์
COPY . /app/

# ติดตั้ง Tesseract OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libopencv-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# คำสั่งสำหรับรันแอปพลิเคชัน FastAPI ด้วย Uvicorn
CMD ["uvicorn", "app.main_3:app", "--host", "0.0.0.0", "--port", "8000"]
