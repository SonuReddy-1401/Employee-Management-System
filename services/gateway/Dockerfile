FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy gateway service requirements and install
COPY services/gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy gateway service app code
COPY services/gateway/app /app/services/gateway/app

EXPOSE 8000

CMD ["uvicorn", "services.gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
