import re 
import os 
import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 

# 👇 DÁN LINK GOOGLE SHEET CỦA BẠN VÀO ĐÂY
SHEET_URL = "https://docs.google.com/spreadsheets/d/xxxxxxxxxxxx/edit" 
SHEET_NAME = "Trang tính1" # Tên cái tab bên dưới (thường là Sheet1 hoặc Trang tính1)

# Tên file key bạn đã up lên GitHub
KEY_FILE = 'google_key.json'

TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'check giúp', 'done', 'thanks']
NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
"""

current_usd_rate = 26.95

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(user_name, amount, rate, total_vnd):
    try:
        # Cấu hình kết nối
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        
        # Mở sheet
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)
        
        # Lấy giờ Việt Nam
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.datetime.now(vn_tz).strftime("%d/%m/%Y %H:%M:%S")
        
        # Dữ liệu cần lưu (Cột A: Ngày giờ, B: Người chốt, C: Số lượng $, D: Tỷ giá, E: Tổng tiền)
        row = [now, user_name, amount, rate, total_vnd]
        
        # Ghi vào dòng cuối cùng
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return False

# --- SERVER ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang chạy ngon lành!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC ---

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chốt đơn vào Sheet: /chot 1000"""
    # Lấy thông tin người chốt
    user_name = update.effective_user.first_name
    
    try:
        # Kiểm tra xem có nhập số tiền không
        if not context.args:
            await update.message.reply_text("⚠️ Vui lòng nhập số tiền đã nhận.\nVí dụ: `/chot 1000`", parse_mode='Markdown')
            return

        # Xử lý số tiền
        amount_str = context.args[0].replace(',', '').replace('.', '')
        amount = int(amount_str)
        
        # Tính toán
        total_vnd = amount * current_usd_rate * 1000
        formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
        
        # Lưu vào Google Sheet
        await update.message.reply_text("⏳ Đang lưu vào Google Sheet...")
        
        success = save_to_sheet(user_name, amount, current_usd_rate, formatted_vnd)
        
        if success:
            msg = (
                f"✅ **ĐÃ LƯU GIAO DỊCH THÀNH CÔNG!**\n"
                f"👤 Người chốt: {user_name}\n"
                f"💵 Số lượng: {amount} $\n"
                f"💰 Tổng tiền: {formatted_vnd} VNĐ\n"
                f"📝 Đã ghi vào file báo cáo."
            )
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Lỗi kết nối Google Sheet! (Kiểm tra lại file Key hoặc quyền truy cập)")
            
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền không hợp lệ.")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Không có quyền!")
        return
    try:
        if not context.args: return
        new_rate = float(context.args[0].replace(',', '.'))
        if new_rate > 1000: new_rate = new_rate / 1000
        current_usd_rate = new_rate
        
        display_rate = "{:,.3f}".format(new_rate).rstrip('0').rstrip('.')
        msg = f"📣 **THÔNG BÁO TỶ GIÁ MỚI: {display_rate}**"
        try:
            m = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
            await m.pin()
            await update.message.reply_text("✅ Đã cập nhật!")
        except: pass
    except: pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    k = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
    await update.message.reply_text("👋 Chào bạn!", reply_markup=InlineKeyboardMarkup(k))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == 'private' and update.effective_user.id != ADMIN_ID:
        k = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
        await update.message.reply_text(f"⛔ Vào nhóm nha: {LINK_NHOM}", reply_markup=InlineKeyboardMarkup(k))
        return 

    text = update.message.text.lower()
    if any(t in text for t in TU_KHOA_BO_QUA): return 

    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text) 
    keywords = ['mua', 'bán', 'đổi', 'check', 'giá', 'usd']
    
    if match and (text.strip().isdigit() or any(w in text for w in keywords)):
        amount = int(match.group())
        vnd = "{:,.0f}".format(amount * current_usd_rate * 1000).replace(',', '.')
        rate_str = "{:,.2f}".format(current_usd_rate).replace('.', ',')
        
        resp = f"💵 **BÁO GIÁ:**\n✅ {amount} $ x {rate_str}\n💰 **{vnd} VNĐ**\n\n{NOI_DUNG_CK}"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(script_dir, 'qr.jpg')
        try:
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as p:
                    await context.bot.send_photo(chat_id=update.message.chat_id, photo=p, caption=resp, parse_mode='Markdown')
            else:
                await update.message.reply_text(resp, parse_mode='Markdown')
        except: pass
    elif any(w in text for w in keywords):
         await update.message.reply_text(f"📈 Tỷ giá: **{current_usd_rate}**", parse_mode='Markdown')

def main():
    keep_alive() 
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tiengviet", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    
    # Thêm lệnh chốt đơn mới
    app.add_handler(CommandHandler("chot", chot_don))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
