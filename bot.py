import re 
import os 
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 # ID nhóm để ghim giá
LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"

# THÔNG TIN GOOGLE SHEET
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UOej4p1opA-6E3Zn7cn-ktQqum-RYJUyWHTuu-_tWV4/edit" 
SHEET_NAME = "Bán SWC" 
KEY_FILE = 'google_key.json'

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
TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'xong rồi', 'done']

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        ngay_hien_tai = datetime.now(vn_tz).strftime("%d/%m/%Y")
        
        val_usd = float(so_usd)
        thanh_tien_vnd = int(val_usd * current_usd_rate * 1000)

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)

        # Định dạng cột D có chữ 'usd' để khớp công thức Sheet của bạn
        usd_formatted = f"{so_usd}usd"
        row = [ngay_hien_tai, nguoi_chuyen, gmail_khach, usd_formatted, thanh_tien_vnd]
        
        # Tìm hàng trống dựa trên cột A để tránh nhảy cột F
        all_dates = sheet.col_values(1)
        next_row = len(all_dates) + 1
        target_range = f"A{next_row}:E{next_row}"
        sheet.update(target_range, [row], value_input_option='USER_ENTERED')
        
        return ngay_hien_tai, thanh_tien_vnd
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return None, None

# --- SERVER ẢO ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot Live!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")],
        [InlineKeyboardButton("📢 XEM KÊNH TIN TỨC 🇻🇳", url=LINK_CHANNEL)]
    ]
    await update.message.reply_text(
        "👋 Chào mừng bạn! Tôi hỗ trợ báo giá và chốt đơn tự động.\n\n"
        "👉 Nhắn số tiền (VD: 100) để xem báo giá.\n"
        "👉 Dùng lệnh `/chot [Số USD] [Gmail]` để ghi sổ.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [[InlineKeyboardButton("📢 XEM KÊNH TIN TỨC 🇻🇳", url=LINK_CHANNEL)]]
        await update.message.reply_text(
            f"👋 Chào {member.first_name}! Chào mừng bạn đã vào nhóm.\n\n"
            f"Bạn hãy theo dõi Kênh tin tức chính thức bên dưới nhé 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID: return
    try:
        raw_input = context.args[0].replace(',', '.')
        new_rate = float(raw_input)
        if new_rate > 1000: new_rate = new_rate / 1000
        current_usd_rate = new_rate
        display_rate = "{:,.2f}".format(new_rate).replace('.', ',')
        
        # Thông báo và Ghim vào nhóm
        msg = f"📣 **CẬP NHẬT TỶ GIÁ**\n---------------\n💵 Giá USD hiện tại: **{display_rate}** VNĐ"
        sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
        await sent_msg.pin()
        await update.message.reply_text(f"✅ Đã cập nhật giá: {display_rate}")
    except: pass

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Cú pháp: `/chot [Số USD] [Gmail]`")
            return
        so_usd = context.args[0]
        gmail = context.args[1]
        
        time_res, vnd_res = save_to_sheet(user_name, gmail, so_usd)
        if time_res:
            vnd_display = "{:,.0f}".format(vnd_res).replace(',', '.')
            await update.message.reply_text(f"✅ **GHI SỔ THÀNH CÔNG**\n📅 {time_res}\n👤 {user_name}\n💵 {so_usd} USD\n💰 {vnd_display} VNĐ")
        else:
            await update.message.reply_text("❌ Lỗi kết nối Google Sheet!")
    except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(tk in text for tk in TU_KHOA_BO_QUA): return

    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')

    if match:
        amount = int(match.group())
        total_vnd = amount * current_usd_rate * 1000
        formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
        
        response = (
            f"💵 **BÁO GIÁ:**\n"
            f"✅ Số lượng: {amount} $\n"
            f"✅ Tỷ giá: {rate_display}\n"
            f"💰 **THÀNH TIỀN: {formatted_vnd} VNĐ**\n"
            f"-----------------------------\n"
            f"{NOI_DUNG_CK}"
        )
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(script_dir, 'qr.jpg') 
        try:
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as photo:
                    await update.message.reply_photo(photo=photo, caption=response, parse_mode='Markdown')
            else:
                await update.message.reply_text(response, parse_mode='Markdown')
        except:
            await update.message.reply_text(response, parse_mode='Markdown')

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(CommandHandler("chot", chot_don))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
