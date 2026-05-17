FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 8001

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8001", "--headless"]
