#FROM python:3
FROM quanted/qed_py3

# Install Python Dependencies
# COPY requirements.txt /tmp/
# RUN pip install --requirement /tmp/requirements.txt

# Install uWSGI
RUN pip install uwsgi

# Overwrite the uWSGI config
COPY uwsgi.ini /etc/uwsgi/

COPY . /src/
WORKDIR /src
EXPOSE 7777

#CMD ["uwsgi", "/etc/uwsgi/uwsgi.ini"]
#RUN celery worker -A tasks -c 1 -Q sam --loglevel=DEBUG -n sam_worker
CMD ["sh", "/src/start_flask.sh"]