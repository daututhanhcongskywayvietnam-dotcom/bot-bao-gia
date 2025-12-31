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
GROUP_ID = -1002946689229 
LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"

# THÔNG TIN GOOGLE SHEET
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UOej4p1opA-6E3Zn7cn-ktQqum-RYJUyWHTuu-_tWV4/edit" 
SHEET_NAME = "Bán SWC" 
KEY_FILE = 'google_key.json'

TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'done']

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
📝 **Nội dung:** GHI SĐT CỦA BẠN
"""

current_usd_rate = 27.0

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        # 1. Lấy ngày VN (Chỉ Ngày/Tháng/Năm để khớp công thức lọc)
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        ngay_hien_tai = datetime.now(vn_tz).strftime("%d/%m/%Y")

        # 2. Tính toán Giá Bán (VNĐ)
        val_usd = float(so_usd)
        thanh_tien_vnd = int(val_usd * current_usd_rate * 1000)

        # 3. Kết nối API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)

        # 4. Định dạng khớp công thức Sheet (Cột D có đuôi 'usd')
        so_usd_kem_don_vi = f"{so_usd}usd"
        row = [ngay_hien_tai, nguoi_chuyen, gmail_khach, so_usd_kem_don_vi, thanh_tien_vnd]
        
        # 5. ÉP GHI VÀO CỘT A ĐẾN E (Tránh nhảy cột F)
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

# --- LOGIC PHẢN HỒI ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")],
                [InlineKeyboardButton("📢 XEM KÊNH TIN TỨC 🇻🇳", url=LINK_CHANNEL)]]
    await update.message.reply_text("👋 Chào mừng bạn! Nhắn số lượng USD để nhận báo giá.", 
                                   reply_markup=InlineKeyboardMarkup(keyboard))

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID: return
    try:
        new_val = float(context.args[0].replace(',', '.'))
        current_usd_rate = new_val if new_val < 1000 else new_val/1000
        msg = f"📣 **CẬP NHẬT TỶ GIÁ**\n---------------\n💵 Giá USD hiện tại: **{current_usd_rate}** VNĐ"
        sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
        await sent_msg.pin()
        await update.message.reply_text(f"✅ Tỷ giá mới: {current_usd_rate}")
    except: pass

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    try:
        so_usd, gmail = context.args[0], context.args[1]
        time_res, vnd_res = save_to_sheet(user_name, gmail, so_usd)
        if time_res:
            vnd_display = "{:,.0f}".format(vnd_res).replace(',', '.')
            await update.message.reply_text(f"✅ **GHI SỔ THÀNH CÔNG**\n📅 {time_res}\n👤 {user_name}\n💵 {so_usd} USD\n💰 {vnd_display} VNĐ", parse_mode='Markdown')
    except: await update.message.reply_text("⚠️ Cú pháp: /chot [Số USD] [Gmail]")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    # Tìm số trong tin nhắn
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    
    # Chỉ cần có số là báo giá (Phản hồi cả tin nhắn riêng và nhóm)
    if match:
        amount = int(match.group())
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
            await update.message.reply_text(resp, parse_mode='Markdown')

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(CommandHandler("chot", chot_don))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
