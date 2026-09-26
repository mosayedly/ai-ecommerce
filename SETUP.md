# SETUP.md — Environment Setup Guide

> **Follow this guide top-to-bottom before opening any other file.**
> Takes about 15 minutes. Works on Windows, Linux, and macOS.

---

## 1. Choose Your Operating System

Jump to the section that matches your OS:

- **[Windows 10/11](#2-windows-setup)** → §2
- **[Linux (Ubuntu / Debian / Arch / Fedora)](#3-linux-setup)** → §3
- **[macOS](#4-macos-setup)** → §4

"The project folder" below always means the folder that contains `manage.py`.

---

## 2. Windows Setup

### 2.1 Install Python 3.12

1. Go to <https://www.python.org/downloads/release/python-3127/>
2. Download the **Windows installer (64-bit)**.
3. Run the installer. **IMPORTANT:** on the first screen, check:

   - ☑ **Add python.exe to PATH**
   - ☑ **Install launcher for all users (recommended)**

4. Click **Install Now**.

Verify: open **PowerShell** and run

```powershell
python --version
```

Expected: `Python 3.12.7` (or similar 3.12.x).

> If Windows opens the Microsoft Store when you type `python`, see §6.1.

### 2.2 Install PostgreSQL 16

1. Go to <https://www.enterprisedb.com/downloads/postgres-postgresql-downloads>
2. Download the **Windows x86-64** installer for **version 16**.
3. During install:

   - **Password for `postgres` superuser:** pick a strong password and REMEMBER IT.
   - **Port:** keep the default `5432`.

4. Finish. Skip **Stack Builder**.

### 2.3 Create the database

Open **SQL Shell (psql)** from the Start Menu. Press Enter 4 times to accept
defaults. Enter your `postgres` password. Then paste:

```sql
CREATE DATABASE ecommerce_db;
CREATE USER ecommerce_user WITH ENCRYPTED PASSWORD 'ecommerce_pass';
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;
\c ecommerce_db
GRANT ALL ON SCHEMA public TO ecommerce_user;
ALTER SCHEMA public OWNER TO ecommerce_user;
\q
```

### 2.4 Prepare the project

Open **PowerShell** in the project folder (the folder containing `manage.py`):

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

In `.env`, set at minimum:

```dotenv
DJANGO_SECRET_KEY=some-long-random-string
DEBUG=True
DB_PASSWORD=ecommerce_pass
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
```

(Or use `AI_PROVIDER=gemini` and fill in `GEMINI_API_KEY` — see §5)

### 2.5 Run

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>

---

## 3. Linux Setup

### 3.1 Install Python and PostgreSQL

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv postgresql postgresql-contrib
```

**Arch / CachyOS:**

```bash
sudo pacman -S python postgresql
sudo -u postgres initdb -D /var/lib/postgres/data    # first time only
sudo systemctl enable --now postgresql
```

**Fedora / RHEL:**

```bash
sudo dnf install python3.12 postgresql-server
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

### 3.2 Create the database

```bash
sudo -u postgres psql
```

Paste the same SQL block as §2.3, then `\q`.

### 3.3 Prepare the project

```bash
cd /path/to/ai_ecommerce
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Fill `.env` with the same keys as §2.4: `AI_PROVIDER=deepseek` plus
`DEEPSEEK_API_KEY`, or `AI_PROVIDER=gemini` plus `GEMINI_API_KEY` if you chose
Gemini (see §5).

### 3.4 Run

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>

---

## 4. macOS Setup

### 4.1 Install Homebrew (if missing)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 4.2 Install Python and PostgreSQL

```bash
brew install python@3.12 postgresql@16
brew services start postgresql@16
```

### 4.3 Create the database

```bash
psql postgres
```

Paste the same SQL block as §2.3, then `\q`.

### 4.4 Prepare the project

Same as §3.3.

### 4.5 Run

Same as §3.4.

---

## 5. Choosing Your AI Provider

The AI recommendation feature (FR-6) requires an API key from one of two
providers. You can also skip this entirely — the store works without AI; it just
falls back to simpler recommendations.

Both providers are OpenAI-compatible, so switching only means changing
`AI_PROVIDER` in `.env` — no code changes at all.

### Option A — Google Gemini (FREE tier, recommended for students)

1. Go to <https://aistudio.google.com/app/apikey>
2. Sign in with any Google account.
3. Click **Create API key**. Copy the key (it starts with `AIza...`).
4. In `.env`, set:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...your-key-here
```

No credit card required. Free tier allows ~1500 requests/day.

### Option B — DeepSeek (paid, extremely cheap)

1. Go to <https://platform.deepseek.com/>
2. Sign up and top up your account ($1 goes a very long way).
3. Create an API key under **"API Keys"**. Copy it (it starts with `sk-...`).
4. In `.env`, set:

```dotenv
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...your-key-here
```

Cost: roughly $0.50 per million tokens. A typical student project uses <100k tokens.

### No key? The store still works

Leave both keys empty. The homepage will show generic recommendations instead
of AI-generated ones. Everything else (cart, orders, admin) works normally.

> If a key is present but invalid, the console prints `gemini call failed` or
> `deepseek call failed` and the app falls back automatically — see §6.6.

---

## 6. Troubleshooting

### 6.1 Windows: `python` opens Microsoft Store

1. **Settings → Apps → Advanced app settings → App execution aliases**
2. Turn OFF both `python.exe` and `python3.exe`
3. Restart **PowerShell**

### 6.2 Windows: `Activate.ps1` cannot be loaded

You skipped `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

### 6.3 Windows: `psql` is not recognized

- Use **SQL Shell (psql)** from the Start Menu, OR
- Add `C:\Program Files\PostgreSQL\16\bin` to `PATH`, then open a new
  **PowerShell** window.

### 6.4 `psycopg2-binary` fails to install

You are on Python 3.13+ or 3.14. Install Python 3.12 and recreate the venv:

```powershell
py -3.12 -m venv venv
```

### 6.5 `connection to server at "127.0.0.1", port 5432 failed`

- Is PostgreSQL running? (Windows: **Services**; Linux:
  `systemctl status postgresql`; macOS: `brew services list`)
- Do the `DB_*` values in `.env` match what you created in §2.3?

### 6.6 AI recommendations show without reasons

Your API key is missing or invalid. Check the server console for messages like
`gemini call failed` or `deepseek call failed`. See §5 to get a key.

---

## 7. Verify Everything Works

After `runserver`, open these URLs and confirm each loads:

| URL | Expected |
| --- | --- |
| <http://127.0.0.1:8000/> | Home page: "Welcome to AI Shop" |
| <http://127.0.0.1:8000/products/> | Product list |
| <http://127.0.0.1:8000/accounts/register/> | Registration form |
| <http://127.0.0.1:8000/admin/> | Admin login (superuser) |

If all four load, your environment is ready. Move on to `GUIDE.md`.

---

## 8. Next Steps

- **`GUIDE.md`** — explains how the app is organized (models, views, services).
- **`CUSTOMIZATION.md`** — recipes for adding fields, pages, and themes.
- **`README.md`** — full technical reference.
- **`docs/API.md`** — every HTTP endpoint documented.

Happy hacking!


