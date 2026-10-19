# Cấu hình Gunicorn. Chạy: gunicorn -c deploy/gunicorn.conf.py config.wsgi
bind = "unix:/run/mamnon/gunicorn.sock"
workers = 3  # gợi ý: 2 x số nhân CPU + 1, điều chỉnh theo RAM
timeout = 120  # yêu cầu AI/xuất PDF có thể lâu hơn bình thường
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
