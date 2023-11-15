FROM python:3.10-slim

# Set the timezone to Asia/Jakarta
RUN apt install -y tzdata
ENV TZ=Asia/Jakarta
ENV LANG id_ID.UTF-8
ENV LANGUAGE ${LANG}
ENV LC_ALL ${LANG}

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN apt update && apt install -y libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx
RUN apt-get -y install tesseract-ocr
# RUN apk update && apk add -y libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx
# RUN echo "http://dl-8.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories
# RUN apk --no-cache --update-cache add gcc gfortran build-base wget freetype-dev libpng-dev openblas-dev --repository=http://dl-8.alpinelinux.org/alpine/edge/community
# RUN apk add make automake gcc g++ subversion python3-dev
# RUN apk add tesseract-ocr

RUN python -m pip install --upgrade pip
RUN pip install -U opencv-python
RUN pip install numpy


RUN pip install -r requirements.txt

COPY . /app

ENTRYPOINT [ "python" ]

CMD ["main.py"]