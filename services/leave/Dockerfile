FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy leave service requirements and install
COPY services/leave/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy leave service app code
COPY services/leave/app /app/services/leave/app

EXPOSE 8003

CMD ["uvicorn", "services.leave.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
