FROM python:3.10

WORKDIR /app
COPY . .

RUN pip install flask flask-cors prometheus_client

CMD ["python", "app.py"]