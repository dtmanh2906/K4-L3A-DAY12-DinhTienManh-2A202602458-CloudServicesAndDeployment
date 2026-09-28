# Thông Tin Deploy — Checkpoint 5

> Thông tin triển khai thực tế của service. `pytest tests/test_cp5.py` đọc file này
> để tìm địa chỉ service của bạn và gọi thử.
>
> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị API key vào đây.**
> Repo này công khai — dán khóa vào là mất khóa.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Dinh Tien Manh |
| Mã học viên | 2A202602458 |
| Repo | https://github.com/dtmanh2906/K4-L3A-DAY12-DinhTienManh-2A202602458-CloudServicesAndDeployment.git |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://day12-agent-production-ed26.up.railway.app |
| Platform | Railway |
| Ngày deploy | 2026-09-28 |

## Biến Môi Trường Đã Set Trên Cloud

Chỉ ghi tên biến và nguồn, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | Railway platform cung cấp khi chạy service |
| `AGENT_API_KEY` | Railway Variables; secret được cấu hình trong dashboard |
| `REDIS_URL` | Railway Redis service `day12-redis`; connection do Railway cung cấp |
| `RATE_LIMIT_PER_MINUTE` | Railway Variables |
| `MONTHLY_BUDGET_USD` | Railway Variables |
| `LOG_LEVEL` | Railway Variables |

## Lệnh Kiểm Tra

Các lệnh dưới đây gọi trực tiếp Public URL đã deploy:

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i https://day12-agent-production-ed26.up.railway.app/health

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i https://day12-agent-production-ed26.up.railway.app/ready

# 3. Không có API key — mong đợi 401
curl -i -X POST https://day12-agent-production-ed26.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Có API key — mong đợi 200 kèm câu trả lời
curl -i -X POST https://day12-agent-production-ed26.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "X-User-Id: sv-test" \
  -d '{"question":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://day12-agent-production-ed26.up.railway.app/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-test" \
    -d '{"question":"test"}'
done; echo
```

## Kết Quả Đã Xác Minh

- `GET /health` → HTTP 200, `status=ok`, `service=day12-agent`, `version=1.0.0`.
- `GET /ready` → HTTP 200, `status=ready`, `redis=true`.
- `POST /ask` không có `X-API-Key` → HTTP 401, `detail="invalid or missing API key"`.
- `POST /ask` với key hợp lệ và `X-User-Id=sv-test` → HTTP 200, `user_id=sv-test`, `cost_usd=2.22E-05`.

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

- `screenshots/dashboard.png` — trang quản lý service trên platform
- `screenshots/health.png` — kết quả gọi `/health` từ trình duyệt hoặc curl

