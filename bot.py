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
TOKEN = '8442263369:AAFuWJk6yM98q8wIZWxkEMzvZ7-hKw9Be_Y'
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 

# THÔNG TIN GOOGLE SHEET
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UOej4p1opA-6E3Zn7cn-ktQqum-RYJUyWHTuu-_tWV4/edit" 
SHEET_NAME = "Bán SWC" 
KEY_FILE = 'google_key.json'

LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"
TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'xong rồi', 'done']

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734.838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

current_usd_rate = 26.95

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        # 1. Lấy ngày VN (Chỉ Ngày/Tháng/Năm)
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

        # 4. Định dạng dữ liệu chuẩn để khớp công thức Sheet
        so_usd_kem_don_vi = f"{so_usd}usd"
        row = [ngay_hien_tai, nguoi_chuyen, gmail_khach, so_usd_kem_don_vi, thanh_tien_vnd]
        
        # 5. TÌM HÀNG TIẾP THEO (Dựa trên cột A) ĐỂ GHI DỮ LIỆU
        # Thay vì dùng append_row (dễ nhảy cột), ta dùng update vào range A:E
        all_dates = sheet.col_values(1)  # Lấy tất cả dữ liệu cột A
        next_row = len(all_dates) + 1    # Hàng trống tiếp theo
        
        # Chỉ định rõ phạm vi cập nhật từ A đến E ở hàng tiếp theo
        target_range = f"A{next_row}:E{next_row}"
        sheet.update(target_range, [row], value_input_option='USER_ENTERED')
        
        return ngay_hien_tai, thanh_tien_vnd
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return None, None

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC CÁC LỆNH ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇻🇳 CÀI ĐẶT TIẾNG VIỆT NGAY ", url="https://t.me/setlanguage/vi-beta")],
                [InlineKeyboardButton("📢 XEM KÊNH TIN TỨC🇻🇳", url=LINK_CHANNEL)]]
    await update.message.reply_text("👋 Hệ thống ghi sổ tự động.\nSử dụng lệnh /chot [Số USD] [Gmail] để ghi sổ.", 
                                   reply_markup=InlineKeyboardMarkup(keyboard))

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id != ADMIN_ID: return
    try:
        new_val = float(context.args[0].replace(',', '.'))
        if new_val > 1000: new_val = new_val / 1000
        current_usd_rate = new_val
        display = "{:,.3f}".format(new_val).rstrip('0').rstrip('.')
        msg = f"📣 **CẬP NHẬT TỶ GIÁ**\n---------------\n💵 Giá USD hiện tại: **{display}** VNĐ"
        sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
        await sent_msg.pin()
        await update.message.reply_text(f"✅ Đã cập nhật tỷ giá: {display}")
    except:
        await update.message.reply_text("⚠️ Sai cú pháp. Ví dụ: /gia 26.95")

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
            await update.message.reply_text(
                f"✅ **GHI SỔ THÀNH CÔNG**\n"
                f"-----------------------------\n"
                f"📅 Ngày: {time_res}\n"
                f"👤 Khách: {user_name}\n"
                f"📧 Gmail: {gmail}\n"
                f"💵 Số lượng: {so_usd} USD\n"
                f"💰 Thành tiền: {vnd_display} VNĐ", 
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Lỗi kết nối Google Sheet!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi hệ thống: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    keywords = ['mua', 'bán', 'đổi', 'giá', 'usd', '$']
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    
    if match and (text.strip().isdigit() or any(w in text for w in keywords)):
        amount = int(match.group())
        total_vnd = "{:,.0f}".format(amount * current_usd_rate * 1000).replace(',', '.')
        resp = f"💵 **BÁO GIÁ NHANH:**\n✅ {amount} $ = **{total_vnd} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(script_dir, 'qr.jpg')
        try:
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as p:
                    await context.bot.send_photo(chat_id=update.message.chat_id, photo=p, caption=resp, parse_mode='Markdown')
            else:
                await update.message.reply_text(resp, parse_mode='Markdown')
        except: pass

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
