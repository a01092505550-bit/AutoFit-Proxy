from flask import Flask, send_from_directory, jsonify
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

@app.route("/")
def home():
    return """
    <html>
    <head>
        <meta charset="utf-8">
        <title>AutoFit Platform</title>
        <style>
            body{font-family:Arial;background:#f5f7fb;margin:0;padding:40px;}
            .box{max-width:900px;margin:auto;background:white;padding:30px;border-radius:18px;box-shadow:0 10px 30px rgba(0,0,0,.08);}
            h1{margin-top:0;color:#0f172a;}
            a{display:block;margin:12px 0;padding:14px 18px;background:#0f172a;color:white;text-decoration:none;border-radius:10px;}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>AutoFit Platform</h1>
            <p>Render 외부 배포용 서버가 실행 중입니다.</p>
            <a href="/health">서버 상태 확인</a>
            <a href="/platform">오토피트 플랫폼</a>
        </div>
    </body>
    </html>
    """

@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "AutoFit Platform Render",
        "base_dir": BASE_DIR
    })

@app.route("/platform")
def platform():
    web_dir = os.path.join(BASE_DIR, "templates")
    target = "autofit_platform.html"

    if os.path.exists(os.path.join(web_dir, target)):
        return send_from_directory(web_dir, target)

    return """
    <h2>autofit_platform.html 파일이 아직 없습니다.</h2>
    <p>기존 파일을 아래 위치에 복사하세요.</p>
    <pre>오토피트플랫폼_RENDER/templates/autofit_platform.html</pre>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8790))
    app.run(host="0.0.0.0", port=port)
