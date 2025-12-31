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
TU_KHOA_BO_QUA = ['đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 'đã bank', 'check giúp', 'done']

# --- KẾT NỐI GOOGLE SHEET ---
def save_to_sheet(nguoi_chuyen, gmail_khach, so_usd):
    try:
        # 1. Lấy ngày VN (Chỉ Ngày/Tháng/Năm)
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        ngay_hien_tai = datetime.now(vn_tz).strftime("%d/%m/%Y")

        # 2. Tính toán tiền VNĐ (Số USD * Tỷ giá * 1000)
        val_usd = float(so_usd)
        thanh_tien_vnd = int(val_usd * current_usd_rate * 1000)

        # 3. Kết nối API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)

        # 4. Định dạng khớp công thức (Cột D có đuôi 'usd')
        so_usd_formatted = f"{so_usd}usd"
        row = [ngay_hien_tai, nguoi_chuyen, gmail_khach, so_usd_formatted, thanh_tien_vnd]
        
        # 5. TÌM HÀNG TIẾP THEO (Dựa trên cột A) ĐỂ TRÁNH NHẢY CỘT F
        all_dates = sheet.col_values(1)
        next_row = len(all_dates) + 1
        target_range = f"A{next_row}:E{next_row}"
        
        # Ghi chính xác vào dải A đến E
        sheet.update(target_range, [row], value_input_option='USER_ENTERED')
        
        return ngay_hien_tai, thanh_tien_vnd
    except Exception as e:
        print(f"Lỗi Sheet: {e}")
        return None, None

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động 100%!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC PHẢN HỒI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi nút cài Tiếng Việt và Kênh tin tức"""
    keyboard = [
        [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")],
        [InlineKeyboardButton("📢 KÊNH TIN TỨC CHÍNH THỨC 🇻🇳", url=LINK_CHANNEL)]
    ]
    await update.message.reply_text(
        "👋 Chào mừng bạn! Nhắn số lượng USD để nhận báo giá.\n\n"
        "👉 Sử dụng lệnh `/chot [Số USD] [Gmail]` để ghi sổ.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tự động chào mừng người mới vào nhóm"""
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [[InlineKeyboardButton("📢 THEO DÕI TIN TỨC 🇻🇳", url=LINK_CHANNEL)]]
        await update.message.reply_text(
            f"👋 Chào mừng {member.first_name} đã gia nhập nhóm!\n\n"
            f"Bạn hãy theo dõi kênh tin tức của chúng tôi tại đây nhé 👇", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin cập nhật tỷ giá và ghim"""
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

async def chot_don(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chốt đơn vào Sheet"""
    user_name = update.effective_user.full_name
    try:
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Cú pháp: `/chot [Số USD] [Gmail]`")
            return
        so_usd, gmail = context.args[0], context.args[1]
        time_res, vnd_res = save_to_sheet(user_name, gmail, so_usd)
        if time_res:
            vnd_display = "{:,.0f}".format(vnd_res).replace(',', '.')
            await update.message.reply_text(
                f"✅ **GHI SỔ THÀNH CÔNG**\n"
                f"📅 Ngày: {time_res}\n"
                f"👤 Khách: {user_name}\n"
                f"💵 Số tiền: {so_usd} USD\n"
                f"💰 Thành tiền: {vnd_display} VNĐ", 
                parse_mode='Markdown'
            )
    except: await update.message.reply_text("❌ Lỗi! Hãy gõ: /chot 100 abc@gmail.com")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Báo giá tự động (Nhạy bén cả tin nhắn riêng và nhóm)"""
    text = update.message.text.lower()
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    # Tìm số trong tin nhắn
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
            await update.message.reply_text(resp, parse_mode='Markdown')

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
