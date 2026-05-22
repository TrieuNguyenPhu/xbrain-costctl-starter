# REFLECTIONS — G2 costctl (XBrain W6 Side Challenge)

---

## 1. Multi-account: Chạy `costctl` trên 100 AWS accounts

Nếu cần mở rộng `costctl` để quản lý 100 AWS accounts thay vì chỉ một account:

**Thách thức chính:**
- Mỗi account có credential khác nhau — không thể dùng một credential tĩnh duy nhất.
- Gọi API tuần tự qua 100 accounts sẽ rất chậm (~vài phút).

**Hướng giải quyết:**
1. **Cross-account IAM Roles**: Tạo một "management role" ở account trung tâm, mỗi child account tạo một role `CostCtlReader` trust management account. `costctl` sẽ `sts.assume_role()` từng account → lấy temporary credentials → tạo boto3 session tương ứng.

   ```python
   sts = boto3.client("sts")
   creds = sts.assume_role(
       RoleArn=f"arn:aws:iam::{account_id}:role/CostCtlReader",
       RoleSessionName="costctl"
   )["Credentials"]
   session = boto3.Session(
       aws_access_key_id=creds["AccessKeyId"],
       aws_secret_access_key=creds["SecretAccessKey"],
       aws_session_token=creds["SessionToken"],
   )
   ```

2. **Concurrent execution**: Dùng `concurrent.futures.ThreadPoolExecutor` để assume role và query song song nhiều accounts cùng lúc — giảm từ ~5 phút xuống còn ~30 giây.

3. **Output**: Xuất kết quả dạng CSV per-account hoặc aggregated report, kèm `account_id` ở mỗi dòng để phân biệt nguồn dữ liệu.

4. **AWS Organizations alternative**: Dùng AWS Cost Explorer ở management account với `GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}]` để lấy chi phí toàn bộ accounts trong một lần gọi API — hiệu quả hơn nhiều cho lệnh `cost`.

---

## 2. `idle` vs Trusted Advisor: Khi nào tin cái nào hơn?

Lệnh `idle` của chúng ta dùng cửa sổ **24 giờ**, Trusted Advisor dùng **14 ngày**.

**Khi tin `idle` (24h) hơn:**
- Cần phát hiện **spike bất thường**: một instance vừa tắt workload lúc tối qua, Trusted Advisor chưa cập nhật vì vẫn còn dữ liệu 13 ngày trước đó.
- Môi trường **dev/test**: các instance thường chỉ chạy theo giờ hành chính, 24h là khoảng thời gian phản ánh thực tế nhất.
- Khi cần **phản ứng nhanh** để tiết kiệm chi phí trong ngày.

**Khi tin Trusted Advisor (14 ngày) hơn:**
- **Workload có chu kỳ**: server batch chạy mỗi cuối tuần sẽ hiện idle trong cửa sổ 24h của ngày thường, nhưng Trusted Advisor thấy đúng pattern tuần hoàn → không đề xuất terminate.
- **Production instances**: cần thời gian quan sát đủ dài trước khi đưa ra quyết định terminate.
- Khi cần **báo cáo chính thức** cho management — Trusted Advisor có độ tin cậy được AWS bảo chứng.

**Kết luận thực tế**: Dùng `idle --hours 168` (7 ngày) thay vì 24h để cân bằng giữa tốc độ phản ứng và độ chính xác. Kết hợp cả hai: Trusted Advisor làm baseline tuần, `idle` để check nhanh hàng ngày.

---

## 3. Blast radius của `clean --apply`: Phòng vệ nếu chạy nhầm

Giả sử vô tình chạy `clean --tag Environment=dev --apply` trong một account dùng chung với team khác:

**Những gì sẽ xảy ra:** Toàn bộ EC2 instances và EBS volumes có tag `Environment=dev` bị terminate ngay lập tức — bao gồm cả resources của các team khác cùng dùng tag đó.

**Những gì nên có để giới hạn thiệt hại:**

1. **Tag ownership prefix**: Quy ước tag riêng theo team — `g2:purpose=practice` thay vì `purpose=practice`. Không team nào vô tình dùng trùng namespace.

2. **Dry-run bắt buộc + approval gate**: Thay vì `--apply` một bước, nên tách thành 2 bước:
   - `clean --tag ... --plan` → xuất ra file kế hoạch với danh sách IDs
   - `clean --apply --plan-file <file>` → require confirm số lượng resources trước khi thực thi

3. **AWS SCPs (Service Control Policies)**: Chặn `terminate_instances` trừ khi request đi kèm tag `g2:managed=true` → buộc resources phải có tag ownership trước khi có thể bị delete.

4. **CloudTrail + SNS alert**: Mọi `terminate_instances` call đều tạo CloudTrail event → trigger SNS notification tới Slack trong vòng 1 phút → team có cơ hội phản ứng trước khi resources mất hoàn toàn.

5. **Deletion protection**: Bật `Termination Protection` cho production instances — `clean` sẽ nhận `OperationNotPermitted` error và skip instance đó thay vì terminate.

---

## 4. AI assistance trong dự án này

Phần lớn logic command được sinh ra với sự hỗ trợ của AI (Antigravity / Claude). Tỷ lệ ước tính:

- **~80% code** được AI generate dựa trên docstring spec có sẵn trong project.
- **~20% chúng tôi chủ động hiểu và kiểm tra**: đọc docstring từng lệnh, đối chiếu với test cases trong `test_list.py` / `test_terminate.py` / `test_clean.py`, verify logic S3 merge tag, verify filter `TERMINAL_STATES` trong `clean_cmd.py`.

**Phần chúng tôi hiểu sâu nhất:**
- Tại sao S3 cần merge tag thay vì replace (destructive `put_bucket_tagging`).
- Tại sao `_list_rds` cần 2 API calls (RDS không trả tag trong `describe_db_instances`).
- Tại sao `clean` dùng server-side filter `tag:key=value` thay vì client-side — hiệu quả hơn nhiều ở scale lớn.

**Lesson learned**: AI tools tốt nhất khi bạn đã đọc spec và hiểu kỳ vọng — để có thể validate output thay vì accept mù quáng.

---

## 5. W7 carry-over: Lệnh nào giữ, lệnh nào bỏ?

**Giữ và mở rộng:**
- **`list`** → Thêm output format `--format json/csv` để dễ pipe vào các tool khác.
- **`cost`** → Thêm `--group-by account` khi mở rộng multi-account; thêm cảnh báo khi chi phí vượt ngưỡng.
- **`idle`** → Tăng `--hours` mặc định lên 168 (7 ngày); thêm auto-suggest terminate command.
- **`tag`** → Thêm `--file tags.yaml` để bulk tag nhiều resources từ một file cấu hình.

**Bỏ hoặc refactor:**
- **`terminate` standalone** → W7 production environment không nên có CLI terminate tự do; thay bằng workflow có approval (Slack bot → approve → terminate).
- **`clean --apply` không có thêm guard** → Cần thêm `--max-count N` (từ chối nếu số resources vượt N) và mandatory dry-run review trước khi apply.
- **`migrate-gp3`** → Migrate vào pipeline tự động (Lambda scheduled) thay vì CLI thủ công — không ai nhớ chạy tay.
