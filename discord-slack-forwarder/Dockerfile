# Pythonの公式イメージを使用
FROM python:3.11-slim

# タイムゾーン設定に必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
  tzdata && \
  ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
  echo "Asia/Tokyo" > /etc/timezone && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /usr/src/app

# requirements.txtをコピーしてライブラリをインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# bot.pyなどをコピー
COPY bot.py .

# BOTを起動するコマンド
CMD ["python", "bot.py"]
