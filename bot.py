import re 
import os 
import json 
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- THƯ VIỆN GOOGLE SHEET ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAH0Frcg3xAFCMYruNUGpsNT79JmOsoYnDA' 
ADMIN_ID = 507318519 
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 
LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"

# CẤU HÌNH SHEET
SHEET_NAME = "Doàng Thu USDT - 2026" 
WORKSHEET_NAME = "Bán SWC"

# --- [QUAN TRỌNG] TỰ TÌM KEY TRONG KÉT SẮT RENDER ---
if os.path.exists('google_key.json'):
    CREDENTIALS_FILE = 'google_key.json'
else:
    CREDENTIALS_FILE = '/etc/secrets/google_key.json' # Đường dẫn bí mật trên Render

# NỘI DUNG CHUYỂN KHOẢN
NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734.838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SỐ ĐIỆN THOẠI CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

DATA_FILE = 'bot_data.json'
default_data = {
    "current_usd_rate": 27.0,
    "last_welcome_message_id": None,
    "last_rate_message_id": None,
    "last_congrats_message_id": None
}
bot_data = default_data.copy()

# --- HÀM LƯU & ĐỌC FILE ---
def load_data():
    global bot_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                bot_data = json.load(f)
                print("✅ Đã tải dữ liệu cũ thành công!")
        except: bot_data = default_data.copy()
    else: bot_data = default_data.copy()

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_data, f, ensure_ascii=False, indent=4)
    except: pass

# --- HÀM GHI SHEET ---
def ghi_google_sheet(user_name, text_content, current_rate):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Kiểm tra file key (Quan trọng)
        if not os.path.exists(CREDENTIALS_FILE): 
            print(f"⚠️ LỖI TO: Không tìm thấy file key tại {CREDENTIALS_FILE}")
            return

        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        
        try: sh = client.open(SHEET_NAME)
        except: 
            print(f"❌ Lỗi: Không mở được file Sheet '{SHEET_NAME}'.")
            return

        try: sheet = sh.worksheet(WORKSHEET_NAME)
        except: sheet = sh.sheet1

        tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
        ngay_thang = datetime.now(tz_vn).strftime("%d/%m/%Y")
        
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', text_content)
        email_kh = email_match.group() if email_match else "Thiếu Email"

        clean = text_content.lower().replace('.', '').replace(',', '')
        tien_match = re.search(r'\d+', clean)
        so_usd = int(tien_match.group()) if tien_match else 0

        col_a = sheet.col_values(1) 
        next_row = len(col_a) + 1
        if next_row < 8: next_row = 8

        range_name = f"A{next_row}:E{next_row}"
        data = [[ngay_thang, user_name, email_kh, so_usd, current_rate]]
        
        sheet.update(range_name=range_name, values=data)
        print(f"✅ Ghi xong dòng {next_row}: {data}")

    except Exception as e:
        print(f"❌ Lỗi Sheet: {e}")

# --- TỪ KHÓA ---
TU_KHOA_BO_QUA = ['đã bank', 'check giúp', 'done', 'ok', 'bill', 'biên lai', 'đã chuyển', 'ck xong', 'đã ck', 'chuyển khoản', 'gmail', 'email', '@', 'gửi rồi', 'đã gửi']
TU_KHOA_NHAN_VIEN = ['nhận được đủ', 'đã nhận đủ', 'nhận đủ usd', 'nhận đủ tiền', 'nhan du', 'đã chuyển đủ', 'da chuyen du', 'đã bắn', 'đã xong']
TU_KHOA_HOI_GIA = ['giá', 'gia', 'rate', 'tỷ giá', 'ty gia', 'bao nhiêu', 'nhiêu', 'đô', 'đô hôm nay', 'gia do', 'xem giá', 'báo giá', 'giá đô']

# --- SERVER ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động 100%!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = bot_data.get("current_usd_rate", 27.0)
    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            await update.message.reply_text(f"🫡 Chào Sếp! Giá hiện tại: **{rate}**.\nSếp nhắn giá mới (VD: `27.5`) em sẽ tự đổi nhé.", parse_mode='Markdown')
        else:
            kb = [[InlineKeyboardButton("👥 VÀO NHÓM NGAY", url=LINK_NHOM)]]
            await update.message.reply_text("👋 Mời Sếp vào nhóm chung ạ:", reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text("Em đã sẵn sàng phục vụ Sếp!")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    old_id = bot_data.get("last_welcome_message_id")
    if old_id:
        try: await context.bot.delete_message(chat_id=update.message.chat_id, message_id=old_id)
        except: pass
    
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        kb = [[InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")], [InlineKeyboardButton("📢 KÊNH TIN TỨC CHÍNH THỨC", url=LINK_CHANNEL)]]
        msg = await update.message.reply_text(f"👋 Chào mừng **Sếp {member.first_name}** đã gia nhập nhóm!\n\n❤️ Kính chúc Sếp luôn dồi dào sức khoẻ và thịnh vượng tài chính.\n\n👉 Sếp hãy ấn nút dưới đây để cài Tiếng Việt cho dễ dùng nhé 👇", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        bot_data["last_welcome_message_id"] = msg.message_id
        save_data()

async def delete_left_member_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await update.message.delete()
    except: pass

async def update_rate_logic(context, new_rate):
    bot_data["current_usd_rate"] = new_rate
    old_id = bot_data.get("last_rate_message_id")
    if old_id:
        try: await context.bot.delete_message(chat_id=GROUP_ID, message_id=old_id)
        except: pass
    
    msg = f"📣 **CẬP NHẬT TỶ GIÁ** \n-----------------\n💵 Giá USD hiện tại: **{new_rate} VNĐ**\n\n👉 Chúc anh chị em sở hữu được thật nhiều cổ phần nha!"
    sent = await context.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode='Markdown')
    try:
        await sent.pin(disable_notification=False)
        bot_data["last_rate_message_id"] = sent.message_id
        save_data()
    except: pass

async def set_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        val = float(context.args[0].replace(',', '.'))
        val = val if val < 1000 else val/1000
        await update_rate_logic(context, val)
        await update.message.reply_text(f"✅ Đã đổi giá: {val}")
    except: pass

async def send_congrats(update, context, text_content):
    old_id = bot_data.get("last_congrats_message_id")
    if old_id:
        try: await context.bot.delete_message(chat_id=update.message.chat_id, message_id=old_id)
        except: pass
    
    msg = await update.message.reply_text("🎉 **Chúc mừng Sếp sở hữu thêm nhiều tài sản nhé!** 🚀", parse_mode='Markdown')
    bot_data["last_congrats_message_id"] = msg.message_id
    save_data()
    
    # GHI SHEET
    user = update.effective_user.first_name
    rate = bot_data.get("current_usd_rate", 27.0)
    Thread(target=ghi_google_sheet, args=(user, text_content, rate)).start()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = bot_data.get("current_usd_rate", 27.0)
    text = update.message.text or update.message.caption or ""
    if not text: return
    text_lower = text.lower()

    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            clean = text_lower.replace(',', '.')
            match = re.search(r'\d+(\.\d+)?', clean)
            if match:
                val = float(match.group())
                if 20 < val < 30: 
                    await update_rate_logic(context, val)
                    await update.message.reply_text(f"✅ Đã cập nhật giá **{val}**!")
                    return
            await update.message.reply_text("Sếp nhắn tỷ giá (ví dụ: `27`) em đổi ngay.")
            return
        kb = [[InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)]]
        await update.message.reply_text("⛔ Mời Sếp vào nhóm chung:", reply_markup=InlineKeyboardMarkup(kb))
        return

    # 1. NHÂN VIÊN/KHÁCH GỬI BILL
    has_photo = bool(update.message.photo)
    has_gmail = ("gmail" in text_lower or "@" in text_lower)
    has_money = re.search(r'\d+', text_lower)
    
    # Gộp điều kiện để gọn code
    if (any(kw in text_lower for kw in TU_KHOA_NHAN_VIEN)) or (has_photo and has_gmail and has_money):
        await send_congrats(update, context, text)
        return

    if any(tk in text_lower for tk in TU_KHOA_BO_QUA): return

    # 3. BÁO GIÁ
    clean = text_lower.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean)
    if match:
        amt = int(match.group())
        if amt <= 0: return
        total = "{:,.0f}".format(amt * rate * 1000).replace(',', '.')
        rate_dis = "{:,.2f}".format(rate).replace('.', ',')
        resp = f"💵 **BÁO GIÁ NHANH:**\n✅ Số lượng: {amt} $\n✅ Tỷ giá: {rate_dis}\n💰 **THÀNH TIỀN: {total} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
        
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qr.jpg')
        try:
            if os.path.exists(path):
                with open(path, 'rb') as p: await context.bot.send_photo(chat_id=update.message.chat_id, photo=p, caption=resp, parse_mode='Markdown')
            else: await update.message.reply_text(resp, parse_mode='Markdown')
        except: await update.message.reply_text(resp, parse_mode='Markdown')
        return

    if any(kw in text_lower for kw in TU_KHOA_HOI_GIA):
        rate_dis = "{:,.2f}".format(rate).replace('.', ',')
        await update.message.reply_text(f"ℹ️ Tỷ giá hiện tại là: **{rate_dis} VNĐ**\n\n👉 Sếp hãy nhắn **Số lượng cần mua** (VD: `1000`) để em tính tiền nhé!", parse_mode='Markdown')

def main():
    load_data()
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("gia", set_rate_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, delete_left_member_message))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
