FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USER=calitp

RUN useradd --create-home --shell /bin/bash $USER && \
    chown -R $USER /home/$USER

USER $USER
ENV PATH "$PATH:/home/$USER/.local/bin"
WORKDIR /home/$USER/app

RUN python -m pip install --upgrade pip

WORKDIR /home/$USER/customer-success

COPY docs/requirements.txt docs/requirements.txt
RUN pip install -r docs/requirements.txt

COPY qr_codes/requirements.txt qr_codes/requirements.txt
RUN pip install -r qr_codes/requirements.txt
