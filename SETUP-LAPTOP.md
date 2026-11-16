# Run the ChronoNet live migration demo on your laptop

What this does: your laptop launches a real Spot instance in your AWS account, the instance runs the workload and saves a visible sample file into S3, then you trigger a migration and watch a NEW instance pick up the SAME file and continue it. Exactly the demo we ran last night.

Time: about 20 minutes the first time. Cost: a few paise (t3.micro Spot, and it self-terminates after 3 hours as a safety net).

---

## 1. Install Python and Git (one time)

- Python: https://www.python.org/downloads/ - during install, tick **"Add python.exe to PATH"**.
- Git: https://git-scm.com/download/win - default options are fine.

Open **PowerShell** and check:

```powershell
python --version
git --version
```

Both should print a version. If `python` is not recognized, reinstall and tick the PATH box (or use `py` instead of `python` everywhere below).

## 2. Get the project

```powershell
cd $HOME\Downloads
git clone https://github.com/dikshachavan3205/cc-course-project.git
cd cc-course-project
```

## 3. Add the sample-data files (the patch zip)

Extract **chrononet-patch.zip** into the repo folder so its `app`, `monitoring`, `data_backend`, `orchestration` folders land on top of the repo's own folders - **choose "Replace" when Windows asks**. The zip has:

- `app/sample_data_generator.py` (new) - the visible sample script
- `app/sample_artifact.py` (new) - saves/restores the sample log to S3
- `app/main.py`, `monitoring/instance_agent.py`, `data_backend/aws/dynamodb_client.py`, `orchestration/user_data.py` (patched versions - replace the repo's)
- `upload_overlay.py`, `trigger_migration.py` (helper scripts you will run)

Why the zip exists: the GitHub repo is unchanged. Before launch you upload these patched files to S3 (`bootstrap/<your-run-id>/`), and each new instance downloads them on boot. That is how the sample-data code reaches instances you launch from your laptop.

## 4. Install the Python dependencies

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r app\requirements.txt -r data_backend\requirements.txt -r monitoring\requirements.txt -r orchestration\requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run this once and retry:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 5. Put AWS credentials on the laptop

1. Sign in to the AWS console > **IAM** > **Users** > **chrononet-nayan** > **Security credentials** > **Create access key** > choose "Command Line Interface" > create. Copy the **Access key ID** and **Secret access key** (the secret is shown only once - keep it private, never send it to anyone).
2. In the same PowerShell window:

```powershell
$env:AWS_ACCESS_KEY_ID="paste-access-key-id-here"
$env:AWS_SECRET_ACCESS_KEY="paste-secret-key-here"
$env:AWS_DEFAULT_REGION="ap-south-1"
```

Note: the repo does not read `.env` files by itself - these PowerShell variables are the real mechanism. They only live in the window you set them in, so do everything in ONE window.

## 6. Set the run settings (same window)

```powershell
$env:CHRONONET_ALLOW_REAL_EC2="true"
$env:CHRONONET_AMI="ami-085e29be1a3508e43"
$env:CHRONONET_SECURITY_GROUP_IDS="sg-05b8dbc55fd82161e"
$env:CHRONONET_SUBNET_ID="subnet-02ed9018ca236ff1a"
$RUN_ID="run-laptop-"+(Get-Date -Format "yyyyMMdd-HHmmss")
```

## 7. Optional practice run (no instance, no cost)

```powershell
python -m orchestration.migrate test-migration
```

Should end with `[test-migration] PASS`. It simulates a migration using real S3/DynamoDB and cleans up after itself. You can also watch the workload locally: `cd app; python main.py` (Ctrl+C to stop, `cd ..` after).

## 8. Launch the live demo

```powershell
python upload_overlay.py --run-id $RUN_ID
python -m orchestration.launch_primary --run-id $RUN_ID
```

The launch prints your instance id (`i-...`) - copy it. Wait about 3-4 minutes for the instance to boot and start checkpointing.

## 9. Watch the sample data appear in your AWS console

- **S3** > chrononet-checkpoints > `checkpoints/<your-run-id>/` - a new checkpoint JSON every 10 seconds, plus a `sample_data/` folder with `sample_data_generator.py` and `sample_output.log`. Open the log: every line says which instance wrote it (`vm=i-...`).
- **DynamoDB** > Tables > `chrononet-vm-state` > Explore items - your instance's row shows `sample_log_path`, `sample_log_lines`, `sample_log_tail`.

## 10. Trigger the migration

```powershell
python trigger_migration.py --run-id $RUN_ID --vm-id <paste-the-instance-id>
```

You will see the full migration run: forced checkpoint > new Spot instance launched > resume from S3 > old instance terminated > SNS alert, ending with `"status": "completed"` and the downtime in seconds.

Now refresh the console - this is the demo moment:
- **S3** `sample_output.log` continues with the NEW instance's id appended right after the old one's lines.
- **DynamoDB** `chrononet-vm-state` has a row for the new instance with the sample log tail; `chrononet-migrations` has the migration record (from/to instance, downtime, resumed step).

## 11. Clean up (important)

- **EC2** > Instances > select the new instance > Instance state > **Terminate**. (The old one is already terminated by the migration itself.)
- Safety net: any instance self-terminates 3 hours after launch, so nothing can bill you overnight.
- Keep the S3 bucket and DynamoDB tables - that data IS your demo evidence.

## Optional: the dashboard during the demo

Second window: `python -m uvicorn data_backend.main:app --port 8000`
Third window: `cd dashboard; npm install; npm run dev` (needs Node.js from nodejs.org), then open http://localhost:5173

## If something fails

- "not recognized" -> you missed step 1's PATH tick, or open a NEW PowerShell after installing.
- AccessDenied / NoCredentialsError -> step 5's variables are missing or wrong in THIS window.
- "CHRONONET_ALLOW_REAL_EC2" complaint -> run step 6's line in the same window.
- Spot capacity error -> the system falls back to On-Demand automatically; still fine for a demo.
