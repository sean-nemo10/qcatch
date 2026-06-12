FROM python:3.12-slim

# naive datetime.now()/date.today() を JST 基準にする（「今日」「期日超過」の
# 日付境界が UTC のままだと日本時間より9時間遅れる）
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Tokyo

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

# data/ はボリュームマウントで上書きされる。空ディレクトリだけ用意
RUN mkdir -p /app/data

ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD ["python", "qcatch.py"]
