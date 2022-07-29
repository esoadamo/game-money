FROM python:3.7-buster
ENV DIR_BE /opt/app
ENV DIR_DATA /opt/app/data

RUN mkdir $DIR_BE && mkdir $DIR_DATA
RUN apt-get update \
    && apt-get install -y iptables \
    && apt-get clean
WORKDIR $DIR_BE
EXPOSE 8926

RUN python3 -m venv venv 

ADD . $DIR_BE/

RUN bash -c 'source venv/bin/activate && pip install --no-cache-dir -r requirements.txt'

RUN useradd -Mr --uid 901 app

ENTRYPOINT ["/bin/bash"]
CMD ["./docker/entrypoint.sh"]

