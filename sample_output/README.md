# Sample outputs — G2

Các file này chứa output thực từ tài khoản AWS của nhóm 2.
Chạy các lệnh sau để tái tạo:

```bash
./costctl.py list ec2                                      > sample_output/list_ec2.txt
./costctl.py list ec2 --missing-tag Application            > sample_output/list_ec2_missing_app.txt
./costctl.py cost --tag Application=HealthBot --days 7     > sample_output/cost.txt
./costctl.py idle --threshold 5 --hours 24                 > sample_output/idle.txt
./costctl.py migrate-gp3                                   > sample_output/migrate_gp3_dryrun.txt
./costctl.py clean --tag purpose=practice                  > sample_output/clean_dryrun.txt
```
