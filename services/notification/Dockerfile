FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy notification service requirements and install
COPY services/notification/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy notification service app code
COPY services/notification/app /app/services/notification/app

EXPOSE 8005

CMD ["uvicorn", "services.notification.app.main:app", "--host", "0.0.0.0", "--port", "8005"]
