FROM python:3.13-slim
WORKDIR /parky
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
CMD ["python","manage.py","runserver","0.0.0.0:8000"]