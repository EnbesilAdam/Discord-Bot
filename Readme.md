# ❄️ Winter Hyacinth Bott

<p align="center">
  <img src="https://i.imgur.com/jlevP0F.jpeg" alt="Winter Hyacinth Banner" width="600"/>
</p>

Winter Hyacinth is a sleek, automated server assistant designed to bridge the gap between your development workflow and your Discord community.

---

## 🚀 Key Features

* **📦 Smart GitHub Tracker:** Posts instant updates when you push code. Tracks changes down to the exact line counts (Additions / Deletions) and displays file statuses.
* **✍️ Automated Devlog Sync:** Automatically polls your custom JSON feed and formats beautiful community announcements whenever you publish a new article.
* **🎫 Dynamic Support Tickets:** Users can open secure, private ticket channels with a single click. Includes automated chat logs and archiving for your staff.
* **💼 Seamless Career Intake:** Features a one-click button that automatically drafts and formats a job application email for candidates using Gmail.
* **📊 Live Dashboard (!info):** Monitors server statistics, dynamic custom statuses, system uptime, and API latency in real-time.

---

## ⚙️ Quick Installation

Deploying the bot to your local machine or a VPS takes only three simple steps:

### 1. Install Libraries
Run this command in your terminal to install the necessary asynchronous modules:
pip install discord.py python-dotenv aiohttp

### 2. Set Up Credentials
Create a .env file in the bot's root directory and drop your secure bot token inside:
DISCORD_BOT_TOKEN=your_secret_bot_token_here

### 3. Launch System
Fire up the bot's core engine using Python:
python3 bot.py

---

## 📑 Command Reference

| Command | Permission | Description |
| :--- | :--- | :--- |
| !setup | Administrator | Spawns the central Hub embed with the Support and Career dropdown menus. |
| !info | Everyone | Displays system health, live uptime matrix, websocket latency, and sync states. |

---

## 💻 Tech Stack

* **Core Engine:** Python & Discord.py (v2.0+)
* **Data Fetching:** Aiohttp (Asynchronous HTTP Client)
* **Configuration:** Dotenv Architecture

---
<p align="center">
  <i>Developed and maintained by <b>enbest</b> for the Winter Hyacinth Automated System network.</i>
</p>
