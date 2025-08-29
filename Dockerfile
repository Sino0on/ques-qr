FROM python:3.10

ENV APP_HOME /app

WORKDIR $APP_HOME

COPY req.txt .
RUN pip install --upgrade pip
RUN pip install -r req.txt

COPY . .

CMD ["python", "bot.py"]