FROM python:3.9 AS base

RUN apt-get update --allow-releaseinfo-change -y
RUN apt-get upgrade --fix-missing -y
RUN apt-get install -y --fix-missing --no-install-recommends git

RUN cd /tmp && git clone -b dev-k https://github.com/quanted/pram_app.git

FROM continuumio/miniconda3:4.10.3

RUN apt-get update --allow-releaseinfo-change -y
RUN apt-get upgrade --fix-missing -y
RUN apt-get install -y --fix-missing --no-install-recommends \
    python3-pip software-properties-common build-essential \
    cmake git sqlite3 gfortran python-dev && \
    pip install -U pip

COPY uwsgi.ini /etc/uwsgi/
#COPY . /src/pram_flask
RUN mkdir /src && cd /src && git clone -b dev-k https://github.com/quanted/pram_flask.git
RUN cd /src/pram_flask && git submodule update --init && git submodule foreach --recursive git checkout dev && git submodule foreach --recursive git pull origin dev
RUN chmod 755 /src/pram_flask/start_flask.sh
WORKDIR /src/
EXPOSE 8080

COPY --from=base /tmp/pram_app/requirements.txt /src/pram_flask/requirements.txt

RUN conda create --name pyenv python=3.9
RUN conda config --add channels conda-forge
RUN conda run -n pyenv --no-capture-output pip install -r /src/pram_flask/requirements.txt
RUN conda install -n pyenv uwsgi

ENV PYTHONPATH /src:/src/pram_flask/:/src/pram_flask/ubertool/ubertool:$PYTHONPATH
ENV PATH /src:/src/pram_flask/:/src/pram_flask/ubertool/ubertool:$PATH

CMD ["conda", "run", "-n", "pyenv", "--no-capture-output", "sh", "/src/pram_flask/start_flask.sh"]
