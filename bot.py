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

# THÔNG TIN GOOGLE SHEET
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UOej4p1opA-6E3Zn7cn-ktQqum-RYJUyWHTuu-_tWV4/edit" 
SHEET_NAME = "Bán SWC" 
KEY_FILE = 'google_key.json'

# --- TỪ KHÓA BỎ QUA ---
TU_KHOA_BO_QUA = [
    'đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 
    'đã bank', 'đã chuyển', 'check giúp', 'kiểm tra giúp',
    'done', 'xong rồi', 'uy tín', 'cảm ơn', 'thanks'
]

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

# Giá mặc định
current_usd_rate = 27.0

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        # 1. Lấy ngày giờ Việt Nam
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        ngay_hien_tai = datetime.now(vn_tz).strftime("%d/%m/%Y")

        # 2. Tính toán tiền VNĐ
        val_usd = float(so_usd)
        thanh_tien_vnd = int(val_usd * current_usd_rate * 1000)

        # 3. Kết nối API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)

        # 4. Định dạng dữ liệu (Cột D có đuôi 'usd' để khớp công thức Sheet)
        so_usd_kem_don_vi = f"{so_usd}usd"
        row = [ngay_hien_tai, nguoi_chuyen, gmail_khach, so_usd_kem_don_vi, thanh_tien_vnd]
        
        # 5. TÌM HÀNG TIẾP THEO (Dựa trên cột A) để ép vào cột A:E
        all_dates = sheet.col_values(1)
        next_row = len(all_dates) + 1
        target_range = f"A{next_row}:E{next_row}"
        
        # Ghi dữ liệu vào chính xác phạm vi A:E
        sheet.update(target_range, [row], value_input_option='USER_ENTERED')
        
        return ngay_hien_tai, thanh_tien_vnd
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return None, None

# --- SERVER ẢO ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang chạy ngon lành!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [[InlineKeyboardButton("🇻🇳 BẤM VÀO ĐÂY ĐỂ CÀI TIẾNG VIỆT 🇻🇳", url="https://t.me/setlanguage/vi-beta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f"👋 Chào {user_name}!\n\nNếu chưa có Tiếng Việt, hãy bấm vào nút bên dưới 👇"
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền đổi giá!")
        return
    try:
        if not context.args:
            await update.message.reply_text(f"ℹ️ Giá hiện tại: {current_usd_rate}. Gõ /gia 26,95 để đổi.")
            return
        raw_input = context.args[0].replace(',', '.')
        new_rate = float(raw_input)
        if new_rate > 1000: new_rate = new_rate / 1000
        current_usd_rate = new_rate
        display_rate = "{:,.3f}".format(new_rate).rstrip('0').rstrip('.')
        announcement = (
            f"📣 **THÔNG BÁO CẬP NHẬT TỶ GIÁ**\n--------------------------------\n"
            f"💵 Giá USD hiện tại: **{display_rate}** VNĐ\n👉 Mời anh em lên đơn!"
        )
        sent_message = await context.bot.send_message(chat_id=GROUP_ID, text=announcement, parse_mode='Markdown')
        await sent_message.pin()
        await update.message.reply_text(f"✅ Đã đăng bài và ghim giá **{display_rate}** thành công!")
    except:
        await update.message.reply_text("⚠️ Lỗi! Nhập số ví dụ: /gia 27")

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chốt đơn: /chot [Số USD] [Gmail]"""
    user_name = update.effective_user.full_name
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Cú pháp: `/chot [Số USD] [Gmail]`")
            return
        
        so_usd = context.args[0].replace(',', '.')
        gmail = context.args[1]
        
        time_res, vnd_res = save_to_sheet(user_name, gmail, so_usd)
        
        if time_res:
            vnd_display = "{:,.0f}".format(vnd_res).replace(',', '.')
            await update.message.reply_text(
                f"✅ **GHI SỔ THÀNH CÔNG**\n"
                f"📅 Ngày: {time_res}\n"
                f"👤 Khách: {user_name}\n"
                f"💵 Số lượng: {so_usd} USD\n"
                f"💰 Thành tiền: {vnd_display} VNĐ", 
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Lỗi kết nối Google Sheet!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi hệ thống: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type 
    user_id = update.effective_user.id   
    text = update.message.text.lower()
    
    if chat_type == 'private' and user_id != ADMIN_ID:
        keyboard = [[InlineKeyboardButton("🇻🇳 BẤM ĐỂ CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
        msg = f"⛔ **BOT KHÔNG BÁO GIÁ RIÊNG!**\n\nMời bạn vào nhóm chung để giao dịch:\n👉 {LINK_NHOM}"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return 
    
    if any(tu_khoa in text for tu_khoa in TU_KHOA_BO_QUA): return 

    keywords = ['mua', 'bán', 'đổi', 'check', 'giá', 'usd', 'đô', '$', 'rate']
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text) 
    rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')

    if match:
        amount = int(match.group()) 
        should_reply = False
        if text.strip().replace('.', '').replace(',', '').replace('$', '').isdigit(): should_reply = True
        elif any(word in text for word in keywords): should_reply = True

        if should_reply:
            total_vnd = amount * current_usd_rate * 1000 
            formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
            response = f"💵 **BÁO GIÁ:**\n✅ Số lượng: {amount} $\n✅ Tỷ giá: {rate_display}\n💰 **THÀNH TIỀN: {formatted_vnd} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            photo_path = os.path.join(script_dir, 'qr.jpg') 
            try:
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=update.message.chat_id, photo=photo, caption=response, parse_mode='Markdown')
                else:
                    await update.message.reply_text(response, parse_mode='Markdown')
            except:
                await update.message.reply_text(response, parse_mode='Markdown')

    elif any(word in text for word in keywords):
        response_rate = f"📈 **TỶ GIÁ HÔM NAY:**\n💵 Giá USD: **{rate_display}** VNĐ"
        await update.message.reply_text(response_rate, parse_mode='Markdown')

def main():
    keep_alive() 
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tiengviet", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(CommandHandler("chot", chot_don))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
