import re 
import os 
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

# 👇 KIỂM TRA LẠI LINK GOOGLE SHEET CỦA BẠN TẠI ĐÂY
SHEET_URL = "https://docs.google.com/spreadsheets/d/1X_T8p46p5Yh_Q0v2S6vY7Y_o2E7_L8Z8Z8Z8Z8Z8Z8/edit" 
SHEET_NAME = "Trang tính1" 

KEY_FILE = 'google_key.json'

TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'xong rồi', 'done']

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

# Giá mặc định (Bạn có thể sửa số này thành giá thị trường hiện tại)
current_usd_rate = 26.95

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)
        # Ghi vào: Cột A(Trống), B(Người chuyển), C(Gmail), D(Số USD)
        row = ["", nguoi_chuyen, gmail_khach, so_usd]
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return False

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC CÁC LỆNH ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start hoặc /tiengviet"""
    keyboard = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Chào mừng bạn! Bấm nút dưới để cài Tiếng Việt cho Telegram nhé 👇", reply_markup=reply_markup)

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chào mừng người mới vào nhóm"""
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
        await update.message.reply_text(f"👋 Chào {member.first_name}! Chào mừng bạn đã vào nhóm.\nBấm nút dưới để cài giao diện Tiếng Việt nhé 👇", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /gia dành cho Admin"""
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền!")
        return
    try:
        if not context.args: return
        new_val = float(context.args[0].replace(',', '.'))
        if new_val > 1000: new_val = new_val / 1000
        current_usd_rate = new_val
        display = "{:,.3f}".format(new_val).rstrip('0').rstrip('.')
        
        announcement = f"📣 **THÔNG BÁO CẬP NHẬT TỶ GIÁ**\n--------------------------------\n💵 Giá USD hiện tại: **{display}** VNĐ\n👉 Mời anh em lên đơn!"
        sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=announcement, parse_mode='Markdown')
        await sent_msg.pin()
        await update.message.reply_text(f"✅ Đã cập nhật giá {display} và ghim lên nhóm!")
    except:
        await update.message.reply_text("⚠️ Sai cú pháp. VD: /gia 27")

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /chot [Số USD] [Gmail]"""
    user_name = update.effective_user.first_name
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Cú pháp: `/chot [Số USD] [Gmail]`\nVí dụ: `/chot 500 abc@gmail.com`", parse_mode='Markdown')
            return
        
        so_usd = context.args[0]
        gmail = context.args[1]
        await update.message.reply_text("⏳ Đang ghi vào Google Sheet...")
        
        if save_to_sheet(user_name, gmail, so_usd):
            await update.message.reply_text(f"✅ **ĐÃ GHI SỔ THÀNH CÔNG**\n👤 Telegram: {user_name}\n📧 Gmail: {gmail}\n💵 Số tiền: {so_usd} USD", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Lỗi kết nối Google Sheet!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý báo giá tự động"""
    chat_type = update.message.chat.type
    user_id = update.effective_user.id
    text = update.message.text.lower()

    # Nhắn tin riêng
    if chat_type == 'private' and user_id != ADMIN_ID:
        keyboard = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
        await update.message.reply_text(f"⛔ Vui lòng vào nhóm để xem giá: {LINK_NHOM}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Lọc từ khóa bỏ qua
    if any(tk in text for tk in TU_KHOA_BO_QUA): return

    # Tính tiền
    keywords = ['mua', 'bán', 'đổi', 'giá', 'usd', '$', 'check']
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')

    if match and (text.strip().isdigit() or any(w in text for w in keywords)):
        amount = int(match.group())
        total_vnd = "{:,.0f}".format(amount * current_usd_rate * 1000).replace(',', '.')
        resp = f"💵 **BÁO GIÁ:**\n✅ Số lượng: {amount} $\n✅ Tỷ giá: {rate_display}\n💰 **THÀNH TIỀN: {total_vnd} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
        
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
        await update.message.reply_text(f"📈 Tỷ giá hiện tại: **{rate_display}** VNĐ", parse_mode='Markdown')

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tiengviet", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(CommandHandler("chot", chot_don))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
