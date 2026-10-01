FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy employee service requirements and install
COPY services/employee/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy employee service app code
COPY services/employee/app /app/services/employee/app

EXPOSE 8002

CMD ["uvicorn", "services.employee.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
