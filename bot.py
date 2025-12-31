import re 
import os 
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAFuWJk6yM98q8wIZWxkEMzvZ7-hKw9Be_Y' # Token chuẩn của bạn
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 
LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"

# NỘI DUNG CHUYỂN KHOẢN
NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

current_usd_rate = 27.0
# Những từ khóa Bot sẽ bỏ qua (không trả lời)
TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'done', 'ok']
# Những từ khóa khách hỏi giá (Bot sẽ trả lời tỷ giá)
TU_KHOA_HOI_GIA = ['giá', 'gia', 'rate', 'tỷ giá', 'ty gia', 'bao nhiêu', 'nhiêu']

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động 100%!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC PHẢN HỒI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")],
        [InlineKeyboardButton("📢 KÊNH TIN TỨC CHÍNH THỨC 🇻🇳", url=LINK_CHANNEL)]
    ]
    await update.message.reply_text(
        "👋 Chào mừng bạn! Nhắn số lượng USD để nhận báo giá.\n\n"
        "👉 Ví dụ: Nhắn `1000` hoặc `500` Bot sẽ tính tiền ngay.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [[InlineKeyboardButton("📢 THEO DÕI TIN TỨC 🇻🇳", url=LINK_CHANNEL)]]
        await update.message.reply_text(
            f"👋 Chào mừng {member.first_name} đã gia nhập nhóm!\n\n"
            f"Bạn hãy theo dõi kênh tin tức của chúng tôi tại đây nhé 👇", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID: return
    try:
        new_val = float(context.args[0].replace(',', '.'))
        current_usd_rate = new_val if new_val < 1000 else new_val/1000
        msg = f"📣 **CẬP NHẬT TỶ GIÁ**\n---------------\n💵 Giá USD hiện tại: **{current_usd_rate}** VNĐ"
        sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
        await sent_msg.pin()
        await update.message.reply_text(f"✅ Đã ghim giá mới: {current_usd_rate}")
    except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    # 1. Nếu gặp từ khóa bỏ qua -> Im lặng
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    # 2. ƯU TIÊN: Tìm số trong tin nhắn để tính tiền
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    
    if match:
        amount = int(match.group())
        if amount <= 0: return
        total_vnd = "{:,.0f}".format(amount * current_usd_rate * 1000).replace(',', '.')
        rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')
        resp = f"💵 **BÁO GIÁ NHANH:**\n✅ Số lượng: {amount} $\n✅ Tỷ giá: {rate_display}\n💰 **THÀNH TIỀN: {total_vnd} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(script_dir, 'qr.jpg')
        try:
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as p:
                    await context.bot.send_photo(chat_id=update.message.chat_id, photo=p, caption=resp, parse_mode='Markdown')
            else:
                await update.message.reply_text(resp, parse_mode='Markdown')
        except:
