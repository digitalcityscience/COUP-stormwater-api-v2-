FROM python:3.10

# Tell Python to not generate .pyc
ENV PYTHONDONTWRITEBYTECODE 1

# Turn off buffering
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
RUN pip install --upgrade wheel

WORKDIR /app

# Install regular packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY ./ .