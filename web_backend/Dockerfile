FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the keys directory exists
RUN mkdir -p keys

EXPOSE 5000
CMD ["python", "app.py"]
