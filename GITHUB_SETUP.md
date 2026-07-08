# GitHub setup

This project is intended to be pushed as a normal Git repository.

## Recommended repository name

`poe-market-analyser`

## First push from local project

Open PyCharm Terminal in the project root:

```powershell
cd C:\POE_Market\poe_market_analyser_mvp
```

Initialize Git and commit the current project:

```powershell
git init -b main
git add .
git commit -m "Initial POE Market Analyser MVP"
```

Create a new empty repository on GitHub under `ludozyad`, without README, license, or `.gitignore`, then connect and push:

```powershell
git remote add origin https://github.com/ludozyad/poe-market-analyser.git
git push -u origin main
```

If the repo was created with a README on GitHub, pull first:

```powershell
git pull origin main --allow-unrelated-histories
git push -u origin main
```

## Normal update workflow after future zip updates

After replacing files from a new generated package:

```powershell
python -m pytest
git status
git add .
git commit -m "Describe the implemented iteration"
git push
```

## Do not commit

The `.gitignore` excludes local virtualenv, runtime database and exported reports:

- `.venv/`
- `poe_market.db`
- `.pytest_cache/`
- `exports/`
