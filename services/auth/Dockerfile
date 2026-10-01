FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy auth service requirements and install
COPY services/auth/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy auth service app code
COPY services/auth/app /app/services/auth/app

EXPOSE 8001

CMD ["uvicorn", "services.auth.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
