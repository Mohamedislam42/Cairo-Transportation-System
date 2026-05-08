# Cairo Transport Lab — Flask + sklearn (bonus: runs the same everywhere)
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Render / Railway / Fly often inject PORT at runtime (default keeps local.docker simple)
ENV PORT=8080
ENV TRANSPORT_LAB_HOST=0.0.0.0
ENV TRANSPORT_LAB_PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD exec gunicorn --bind "0.0.0.0:${PORT}" --workers 2 app:app
