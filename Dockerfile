# Dockerfile

# Pythonの公式イメージを使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /usr/src/app

# requirements.txtをコンテナにコピーし、ライブラリをインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# bot.pyと、もしあれば他のファイルをコンテナにコピー
COPY bot.py .

# BOTを起動するコマンドを設定
CMD [ "python", "bot.py" ]
