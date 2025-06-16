FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD sh -c "gunicorn --bind 0.0.0.0:${PORT} wsgi:app --workers 3 --threads 8"
