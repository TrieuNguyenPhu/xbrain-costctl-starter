# sample_output/

These files are **illustrative examples** showing the shape of `costctl`
output. They are NOT real account data.

When you submit, replace each `*_example.txt` with a real output from running
`costctl` against your workshop account. Then delete the example files.

## How to produce real samples

```bash
./costctl.py list ec2 > sample_output/list_ec2_$(date +%F).txt
./costctl.py list ec2 --missing-tag Application > sample_output/list_ec2_missing_app_$(date +%F).txt
./costctl.py cost --tag Application=<your-app> --days 7 > sample_output/cost_<your-app>_$(date +%F).txt
```

The trainer will `git clone` your repo, follow the README, and expect to
reproduce roughly these outputs (allowing for natural drift in timestamps and
resource lists between snapshots).

## Anti-pattern

Don't paste fabricated output. If `costctl list ec2` against your account
returns 0 rows, commit that — it's a valid output. Don't invent fake instance
IDs to make the sample look "interesting".
