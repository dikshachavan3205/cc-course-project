# Run the ChronoNet live migration demo from your laptop

What you will show: your laptop launches a real Spot instance in your AWS account. The instance runs a workload and serves a **VIT placement stats web page** that shows its own **instance ID** and the **current step**. You trigger a migration. A NEW instance takes over from the saved checkpoint, and the same page now shows the new instance ID and keeps counting from where it stopped.

Time: about 20 minutes the first time. Cost: a few paise (t3.micro Spot). Every instance also shuts itself down after 3 hours, so nothing can keep billing you.

Everything you need is in the `feature/sample-data-migration` branch. There is no zip file to extract.

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

## 2. Get the project (one clone, the right branch)

```powershell
cd $HOME\Downloads
git clone -b feature/sample-data-migration https://github.com/dikshachavan3205/cc-course-project.git
cd cc-course-project
```

The `-b feature/sample-data-migration` part picks the demo branch. It already has the sample-data code, the web page (`app/web_server.py`, `app/site_default/`) and the helper scripts (`upload_overlay.py`, `trigger_migration.py`).

Already cloned earlier? Run `git fetch origin` and `git checkout feature/sample-data-migration`, then `git pull`.

## 3. Install the Python dependencies

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r app\requirements.txt -r data_backend\requirements.txt -r monitoring\requirements.txt -r orchestration\requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run this once and retry:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 4. Put AWS credentials on the laptop

1. Sign in to the AWS console > **IAM** > **Users** > **chrononet-nayan** > **Security credentials** > **Create access key** > choose "Command Line Interface" > create. Copy the **Access key ID** and **Secret access key**. The secret is shown only once. Keep it private and never send it to anyone.
2. In the same PowerShell window:

```powershell
$env:AWS_ACCESS_KEY_ID="paste-access-key-id-here"
$env:AWS_SECRET_ACCESS_KEY="paste-secret-key-here"
$env:AWS_DEFAULT_REGION="ap-south-1"
```

Do not create a `.env` file. The project does not read it for AWS. These PowerShell variables are what it uses, and they only live in the window you set them in, so do everything in ONE window.

## 5. Set the run settings (same window)

```powershell
$env:CHRONONET_ALLOW_REAL_EC2="true"
$env:CHRONONET_AMI="ami-085e29be1a3508e43"
$env:CHRONONET_SECURITY_GROUP_IDS="sg-05b8dbc55fd82161e"
$env:CHRONONET_SUBNET_ID="subnet-02ed9018ca236ff1a"
$RUN_ID="run-laptop-"+(Get-Date -Format "yyyyMMdd-HHmmss")
```

The security group `chrononet-demo` (the `sg-05b8...` id above) already allows **port 80 inbound**, so the web page is reachable from your browser. You do not need to change anything in AWS for that.

## 6. Practice run (no instance, no cost)

```powershell
python -m orchestration.migrate test-migration
```

It should end with `[test-migration] PASS`. This simulates a migration with the real S3 and DynamoDB tables and cleans up after itself. Good for checking your credentials before the live demo.

## 7. Launch the live demo

```powershell
python upload_overlay.py --run-id $RUN_ID
python -m orchestration.launch_primary --run-id $RUN_ID --repo-ref feature/sample-data-migration
```

- `upload_overlay.py` copies the demo files to S3 for your run. The instance downloads them on boot as a safety copy.
- `--repo-ref feature/sample-data-migration` tells the instance which branch to clone. Without it, the instance clones `main`, which does not have the web page code. (The S3 safety copy would still cover it, but always pass the flag.)

The launch prints your instance id (`i-...`) - copy it. Wait about 3-4 minutes for the instance to boot and start.

## 8. Watch the web page

Find the public IP: **EC2** > Instances > click your instance > **Public IPv4 address**. Open this in your browser (use `http`, not `https`):

```
http://<instance public IP>/
```

You will see the VIT Placement Stats page. The part that matters for the demo is the box showing the **instance ID** and the **current step**. The page refreshes itself every 5 seconds, so the step keeps going up.

If the page does not load in the first 4 minutes, wait a bit more - the instance is still installing things. Check you typed `http://` and not `https://`.

## 9. Watch the sample data in your AWS console

- **S3** > chrononet-checkpoints > `checkpoints/<your-run-id>/` - a new checkpoint JSON every 10 seconds. The `sample_data/` folder has `sample_output.log` and the web page files in `site/`. Open the log: every line says which instance wrote it (`vm=i-...`).
- **DynamoDB** > Tables > `chrononet-vm-state` > Explore items - your instance's row shows `sample_log_path`, `sample_log_lines`, `sample_log_tail`.

## 10. Trigger the migration (the demo moment)

Keep the web page open in a browser tab, then run:

```powershell
python trigger_migration.py --run-id $RUN_ID --vm-id <paste-the-instance-id>
```

You will see the migration run: forced checkpoint, new Spot instance launched, resume from S3, old instance terminated, SNS alert. It ends with `"status": "completed"` and the downtime in seconds.

Now show:
- **The web page**: the old IP stops answering. Open `http://<new instance public IP>/` (EC2 > Instances > the new instance). It is the SAME page, but the **instance ID is different** and the **step continues** from where the old one stopped. That is the migration, visible.
- **S3** `sample_output.log` continues with the NEW instance's id right after the old one's lines.
- **DynamoDB** `chrononet-vm-state` has a row for the new instance, and `chrononet-migrations` has the migration record (from/to instance, downtime, resumed step).

## 11. Clean up (important)

- **EC2** > Instances > select the new instance > Instance state > **Terminate**. (The old one is already terminated by the migration.)
- Safety net: every instance shuts itself down 3 hours after launch, so nothing can bill you overnight.
- Keep the S3 bucket and DynamoDB tables. That data is your demo evidence.

## Optional: put a static copy of the page on Vercel

The live page changes with the instance. If you also want a permanent public link for your slides, you can host a **static copy** of the same page on Vercel. It will not show a live instance ID. It is just the same design with sample values.

1. Make a small folder and copy the page into it:

```powershell
mkdir $HOME\placement-site
copy app\site_default\index.html $HOME\placement-site\index.html
copy app\site_default\style.css $HOME\placement-site\style.css
```

2. Open `index.html` in Notepad and replace the `{{...}}` placeholders (for example `{{VM_ID}}` and `{{STEP}}`) with plain text such as `i-demo` and `100`. Remove the line `<meta http-equiv="refresh" content="5">` if you like.
3. Install Node.js from https://nodejs.org, then:

```powershell
cd $HOME\placement-site
npx vercel
```

Log in when asked, accept the defaults, and Vercel prints a public link. Run `npx vercel --prod` to get the final production link.

## If something fails

- "not recognized" -> you missed the PATH tick in step 1, or open a NEW PowerShell after installing.
- AccessDenied / NoCredentialsError -> the step 4 variables are missing or wrong in THIS window.
- "CHRONONET_ALLOW_REAL_EC2" complaint -> run the step 5 lines in the same window.
- Web page does not open -> wait 4 minutes after launch, use `http://` and the instance's public IP, and check the instance is still running in EC2.
- Spot capacity error -> the system falls back to On-Demand automatically; still fine for a demo.
