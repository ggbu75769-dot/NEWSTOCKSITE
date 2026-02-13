# Git LFS setup for stock CSV backups

Run these commands in the repository root.

## 1) Install Git LFS

### Debian/Ubuntu
```bash
sudo apt-get update
sudo apt-get install -y git-lfs
```

### macOS (Homebrew)
```bash
brew install git-lfs
```

### Windows (Chocolatey)
```powershell
choco install git-lfs -y
```

## 2) Initialize Git LFS in this repository
```bash
git lfs install
git lfs track "*.csv"
git add .gitattributes
git commit -m "chore: enable git lfs for csv files"
```

## 3) Run KOSPI/KOSDAQ 2026 backup automation
```bash
python stock_data_lfs_backup.py \
  --krx-markets KOSPI KOSDAQ \
  --start-date 2026-01-01 \
  --end-date "$(date +%F)" \
  --commit-message "Backup 2026 KOSPI/KOSDAQ data" \
  --push
```

What this does:
1. Loads all KOSPI and KOSDAQ symbols via `pykrx`.
2. Fetches daily candles from `2026-01-01` through today.
3. Writes each symbol into `data/<SYMBOL>.csv`.
4. Tracks all CSV files with Git LFS.
5. Commits and pushes to the current remote branch.
