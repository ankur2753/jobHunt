"""
Telegram Bot Sample Handler for Automated Resume Tailoring

Prerequisites:
  pip install python-telegram-bot

Usage:
  export TELEGRAM_BOT_TOKEN="your_bot_token_here"
  python3 telegram_bot_sample.py
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_resume_bot")

CLI_TAILOR_PATH = "/home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py"
CLI_REFERRAL_PATH = "/home/ankurkumar/ankur_code/agent/scripts/cli_referral.py"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Welcome to the Automated Resume Tailoring Bot!*\n\n"
        "Send me a **Job Posting URL** (e.g. `https://company.com/job/123`) or a **Job Description text**.\n"
        "I will tailor your 1-page A4 Resume, Cover Letter, and LinkedIn Outreach message instantly!\n\n"
        "You can also seek referrals using:\n"
        "`/referral <Company> | <Role>`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_text = " ".join(args).strip()
    
    if not user_text:
        await update.message.reply_text(
            "❌ *Please provide a Job URL and/or Company & Role.*\n"
            "Usage: `/referal <job_url>|<target_position_company>`\n"
            "Example: `/referal https://company.com/jobs/123 | QA Engineer at Google`",
            parse_mode="Markdown"
        )
        return

    company, role = "", ""
    
    await update.message.reply_text("🔄 *Parsing job details...*", parse_mode="Markdown")
    try:
        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.cli_tailor import fetch_job_details
        
        job_details = {}
        target_details = {}
        
        if "|" in user_text:
            part1, part2 = [x.strip() for x in user_text.split("|", 1)]
            if part1.startswith("http"):
                job_details = await fetch_job_details(url=part1)
                target_details = await fetch_job_details(jd_text=part2)
            elif part2.startswith("http"):
                job_details = await fetch_job_details(url=part2)
                target_details = await fetch_job_details(jd_text=part1)
            else:
                target_details = await fetch_job_details(jd_text=user_text)
        elif user_text.startswith("http"):
            job_details = await fetch_job_details(url=user_text)
        else:
            target_details = await fetch_job_details(jd_text=user_text)
            
        company = target_details.get("company") or job_details.get("company")
        role = target_details.get("title") or job_details.get("title")
        
        if not company or not role:
            await update.message.reply_text("❌ *Failed to extract company and role from input.*", parse_mode="Markdown")
            return
            
    except Exception as e:
        logger.exception("Failed to parse input for referral")
        await update.message.reply_text(f"❌ *Failed to parse input:* `{e}`", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 *Searching for referral candidates for {role} at {company}...*", parse_mode="Markdown")

    cmd = [sys.executable, CLI_REFERRAL_PATH, "--company", company, "--role", role]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if proc.returncode != 0:
            logger.error(f"CLI Error: {proc.stderr}")
            await update.message.reply_text(f"❌ *Error fetching referrals.* `{proc.stderr}`", parse_mode="Markdown")
            return
            
        data = json.loads(proc.stdout)
        
        candidates = data.get("candidates", [])
        if not candidates:
            await update.message.reply_text(f"⚠️ No suitable referral candidates found for {company}.", parse_mode="Markdown")
            return
            
        response_text = f"🎯 *Referral Candidates for {role} at {company}*\n\n"
        
        for idx, cand in enumerate(candidates, 1):
            name = cand.get("name")
            headline = cand.get("headline")
            profile_url = cand.get("profile_url")
            draft = cand.get("drafted_message")
            score = cand.get("score")
            
            response_text += (
                f"*{idx}. [{name}]({profile_url})*\n"
                f"_{headline}_\n"
                f"*(Score: {score})*\n"
                f"```text\n{draft}\n```\n\n"
            )
            
        await update.message.reply_text(response_text, parse_mode="Markdown", disable_web_page_preview=True)

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏳ *Request timed out.* The search took too long.")
    except Exception as e:
        logger.exception("Exception in referral command")
        await update.message.reply_text(f"❌ *An unexpected error occurred:* `{e}`", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.reply_text("🔄 *Analyzing job posting & tailoring your application documents...*", parse_mode="Markdown")

    # Determine if input is a URL or raw text
    is_url = user_text.startswith("http://") or user_text.startswith("https://")
    
    cmd = [sys.executable, CLI_TAILOR_PATH, "--json"]
    if is_url:
        cmd.extend(["--url", user_text])
    else:
        cmd.extend(["--jd-text", user_text])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if proc.returncode != 0:
            logger.error(f"CLI Error: {proc.stderr}")
            await update.message.reply_text("❌ *Error tailoring resume.* Please check server logs.", parse_mode="Markdown")
            return

        data = json.loads(proc.stdout)
        company = data.get("company", "Target Company")
        role = data.get("role", "Target Role")
        resume_pdf = data.get("resume_pdf")
        cover_letter_pdf = data.get("cover_letter_pdf")
        linkedin_dm = data.get("linkedin_dm", "")

        # 1. Send Resume PDF
        if resume_pdf and Path(resume_pdf).exists():
            with open(resume_pdf, "rb") as doc:
                await update.message.reply_document(document=doc, filename=f"Ankur_Kumar_{company}_Resume.pdf", caption="📄 *Tailored 1-Page A4 Resume*")

        # 2. Send Cover Letter PDF
        if cover_letter_pdf and Path(cover_letter_pdf).exists():
            with open(cover_letter_pdf, "rb") as doc:
                await update.message.reply_document(document=doc, filename=f"Ankur_Kumar_{company}_Cover_Letter.pdf", caption="✉️ *Tailored 1-Page A4 Cover Letter*")

        # 3. Send LinkedIn DM text
        if linkedin_dm:
            dm_msg = (
                f"🟢 *Tailoring Complete for {role} at {company}!*\n\n"
                f"💬 *LinkedIn Recruiter DM:*\n"
                f"```text\n{linkedin_dm}\n```"
            )
            await update.message.reply_text(dm_msg, parse_mode="Markdown")

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏳ *Request timed out.* The job posting page took too long to load.")
    except Exception as e:
        logger.exception("Exception in Telegram bot handler")
        await update.message.reply_text(f"❌ *An unexpected error occurred:* `{e}`", parse_mode="Markdown")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        print("Usage: export TELEGRAM_BOT_TOKEN='your_bot_token_here' && python3 telegram_bot_sample.py")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("referal", referral_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 Telegram Resume Bot started... Listening for job links!")
    app.run_polling()


if __name__ == "__main__":
    main()
