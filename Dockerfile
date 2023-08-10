FROM python:3.11-slim

LABEL org.opencontainers.image.base.name python:3.11-slim
LABEL org.opencontainers.image.version 1.0


WORKDIR /python

COPY ./source /python

RUN pip install --no-cache-dir -r requirements.txt

ENV Token='' \
    ADusername='' \
    ADps='' \
    GitlabHost='' \
    ADdomain='' \
    DryRun=''

RUN ln -sf /dev/stdout app.log

CMD [ "/usr/local/bin/python", "main.py"]
