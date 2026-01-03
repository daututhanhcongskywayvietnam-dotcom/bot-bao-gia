import re 
import os 
import json 
import time
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
SHEET_NAME = "Dòng Thu USDT - 2026" 
WORKSHEET_NAME = "Bán SWC"
CELL_LUU_GIA = 'K1' 

# --- [QUAN TRỌNG] BỘ NHỚ TẠM THÔNG MINH ---
# Cấu trúc: { user_id: { 'email': '...', 'money': 1000, 'timestamp': ... } }
user_info_cache = {} 

# --- TỰ ĐỘNG TÌM KEY ---
if os.path.exists('/etc/secrets/google_key.json'):
    CREDENTIALS_FILE = '/etc/secrets/google_key.json'
elif os.path.exists('google_key.json'):
    CREDENTIALS_FILE = 'google_key.json'
else:
    CREDENTIALS_FILE = None

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

# --- HÀM KẾT NỐI SHEET ---
def get_sheet():
    try:
        if not CREDENTIALS_FILE or not os.path.exists(CREDENTIALS_FILE): return None
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sh = client.open(SHEET_NAME)
        try: return sh.worksheet(WORKSHEET_NAME)
        except: return sh.sheet1
    except: return None

# --- HÀM LƯU & ĐỌC DỮ LIỆU ---
def load_data():
    global bot_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                bot_data = json.load(f)
        except: bot_data = default_data.copy()
    else: bot_data = default_data.copy()

    # Cưỡng chế đọc giá K1 (5 lần)
    for i in range(5):
        try:
            sheet = get_sheet()
            if sheet:
                saved_rate = sheet.acell(CELL_LUU_GIA).value
                if saved_rate:
                    clean_rate = float(saved_rate.replace(',', '.'))
                    bot_data["current_usd_rate"] = clean_rate
                    print(f"✅ Đã khôi phục tỷ giá: {clean_rate}")
                    return 
        except:
            time.sleep(2)

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_data, f, ensure_ascii=False, indent=4)
    except: pass

# --- HÀM LƯU GIÁ VÀO SHEET (K1) ---
def save_rate_to_sheet_cell(new_rate):
    try:
        sheet = get_sheet()
        if sheet: sheet.update_acell(CELL_LUU_GIA, str(new_rate).replace('.', ','))
    except: pass

# --- HÀM GHI GIAO DỊCH VÀO SHEET (FULL CACHE) ---
def ghi_google_sheet(user_name, text_content, current_rate, cached_email=None, cached_money=None):
    for i in range(3): 
        try:
            sheet = get_sheet()
            if not sheet: return

            tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
            ngay_thang = datetime.now(tz_vn).strftime("%d/%m/%Y")
            
            # --- LOGIC TỔNG HỢP THÔNG TIN ---
            # 1. Tìm Email (Ưu tiên trong Cache -> Tin nhắn hiện tại)
            # Lý do: Cache thường chứa thông tin chuẩn xác nhất mà khách đã nhập trước đó
            email_kh = "Thiếu Email"
            if cached_email: 
                email_kh = cached_email
            else:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', text_content)
                if email_match: email_kh = email_match.group()

            # 2. Tìm Tiền (Ưu tiên Cache -> Tin nhắn hiện tại)
            so_usd = 0
            if cached_money and cached_money > 0:
                so_usd = cached_money
            else:
                clean = text_content.lower().replace('.', '').replace(',', '')
                tien_match = re.search(r'\d+', clean)
                if tien_match and int(tien_match.group()) > 10:
                    so_usd = int(tien_match.group())

            # 3. Tính tiền Việt
            rate_vnd = current_rate * 1000

            # 4. Ghi vào Sheet
            col_a = sheet.col_values(1) 
            next_row = len(col_a) + 1
            if next_row < 8: next_row = 8

            range_name = f"A{next_row}:E{next_row}"
            data = [[ngay_thang, user_name, email_kh, so_usd, rate_vnd]]
            
            sheet.update(range_name=range_name, values=data)
            print(f"✅ Ghi xong dòng {next_row}: {user_name} | {so_usd}$ | {email_kh}")
            return
        except Exception as e:
            print(f"⚠️ Lỗi ghi Sheet: {e}")
            time.sleep(2)

# --- TỪ KHÓA ---
TU_KHOA_BO_QUA = ['đã bank', 'check giúp', 'done', 'ok', 'bill', 'biên lai', 'đã chuyển', 'ck xong', 'đã ck', 'chuyển khoản', 'gmail', 'email', '@', 'gửi rồi', 'đã gửi']
TU_KHOA_NHAN_VIEN = ['nhận được đủ', 'đã nhận đủ', 'nhận đủ usd', 'nhận đủ tiền', 'nhan du', 'đã chuyển đủ', 'da chuyen du', 'da chuyen du', 'đã bắn', 'đã xong']
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
            kb = [[InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)], [InlineKeyboardButton("🇻🇳 CÀI ĐẶT TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
            await update.message.reply_text("👋 **Em chào Sếp!**\n\n🔒 Để bảo mật, em **CHỈ BÁO GIÁ VÀ GIAO DỊCH TRONG NHÓM**.\n👉 Mời Sếp bấm nút bên dưới để tham gia ạ:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        await update.message.reply_text("Em đã sẵn sàng phục vụ Sếp!")

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
    Thread(target=save_rate_to_sheet_cell, args=(new_rate,)).start()
    
    old_rate_id = bot_data.get("last_rate_message_id")
    if old_rate_id:
        try: await context.bot.delete_message(chat_id=GROUP_ID, message_id=old_rate_id)
        except: pass

    msg_text = f"📣 **CẬP NHẬT TỶ GIÁ** \n-----------------\n💵 Giá USD hiện tại: **{new_rate} VNĐ**\n✅ Áp dụng cho mọi giao dịch kể từ thời điểm này.\n👉 Chúc anh chị em sở hữu được thật nhiều cổ phần nha!"
    sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg_text, parse_mode='Markdown')
    try:
        await sent_msg.pin(disable_notification=False)
        bot_data["last_rate_message_id"] = sent_msg.message_id
        save_data()
    except: pass
    return sent_msg

async def set_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        new_val = float(context.args[0].replace(',', '.'))
        new_val = new_val if new_val < 1000 else new_val/1000
        await update_rate_logic(context, new_val)
        await update.message.reply_text(f"✅ Đã đổi giá: {new_val}")
    except: pass

async def send_congrats(update, context, text_content):
    # 1. Xác định Khách hàng
    customer_name = "Khách hàng"
    customer_id = None
    customer_msg = "" # Nội dung tin nhắn của khách
    
    if update.message.reply_to_message:
        # Nếu Reply -> Lấy ID của người được Reply (Khách)
        original = update.message.reply_to_message
        customer_name = original.from_user.first_name
        customer_id = original.from_user.id
        customer_msg = original.text or original.caption or ""
    else:
        # Nếu tự gửi -> Lấy ID người gửi
        customer_name = update.effective_user.first_name
        customer_id = update.effective_user.id
        customer_msg = text_content

    # 2. Truy xuất bộ nhớ Cache của khách hàng này
    cached_email = None
    cached_money = None
    
    if customer_id and customer_id in user_info_cache:
        # Lấy thông tin đã lưu từ các tin nhắn trước
        cached_email = user_info_cache[customer_id].get('email')
        cached_money = user_info_cache[customer_id].get('money')

    # 3. Tổng hợp thông tin (Ưu tiên Cache -> Tin nhắn hiện tại)
    # Tìm Email
    combined_text = f"{text_content} {customer_msg}".lower()
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', combined_text)
    
    if cached_email:
        final_email = cached_email
    elif email_match:
        final_email = email_match.group()
    else:
        final_email = "..."

    # Tìm Tiền
    clean_msg = combined_text.replace('.', '').replace(',', '')
    money_match = re.search(r'\d+', clean_msg)
    
    final_money = "..."
    if cached_money and cached_money > 0:
        final_money = str(cached_money)
    elif money_match and int(money_match.group()) > 10:
        final_money = money_match.group()

    # 4. Gửi Báo Cáo
    tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
    time_str = datetime.now(tz_vn).strftime("%H:%M - %d/%m/%Y")

    congrats_text = (
        f"🎉 **GIAO DỊCH THÀNH CÔNG!** 🚀\n"
        f"--------------------------\n"
        f"⏰ **Thời gian:** {time_str}\n"
        f"👤 **Người nhận:** {customer_name}\n"
        f"💵 **Số lượng:** {final_money} USD\n"
        f"📧 **Email:** {final_email}\n"
        f"--------------------------\n"
        f"❤️ Chúc mừng Sếp {customer_name} đã sở hữu thêm nhiều tài sản giá trị! 💎"
    )

    old_id = bot_data.get("last_congrats_message_id")
    if old_id:
        try: await context.bot.delete_message(chat_id=update.message.chat_id, message_id=old_id)
        except: pass
    
    msg = await update.message.reply_text(congrats_text, parse_mode='Markdown')
    bot_data["last_congrats_message_id"] = msg.message_id
    save_data()
    
    # 5. GHI SHEET (Quan trọng: Truyền Cache vào để hàm ghi sheet sử dụng)
    rate = bot_data.get("current_usd_rate", 27.0)
    
    # Ép kiểu tiền về số nguyên để ghi Sheet (nếu có)
    money_int = 0
    if final_money != "...": money_int = int(final_money)
    
    Thread(target=ghi_google_sheet, args=(customer_name, text_content, rate, final_email, money_int)).start()

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
        else:
            kb = [[InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)], [InlineKeyboardButton("🇻🇳 CÀI ĐẶT TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
            await update.message.reply_text("⛔ **EM KHÔNG BÁO GIÁ RIÊNG SẾP Ạ!**\nEm mời Sếp vào nhóm chung để đảm bảo an toàn và uy tín giao dịch:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
            return

    # --- XỬ LÝ TRONG NHÓM ---

    # [CỰC QUAN TRỌNG] THU THẬP THÔNG TIN VÀO CACHE TÍCH LŨY
    user_id = update.effective_user.id
    if user_id not in user_info_cache: 
        user_info_cache[user_id] = {'email': None, 'money': 0}
    
    # 1. Quét Email trong tin nhắn này (Nếu có thì cập nhật vào Cache)
    email_found = re.search(r'[\w\.-]+@[\w\.-]+', text_lower)
    if email_found: 
        user_info_cache[user_id]['email'] = email_found.group()
        print(f"💾 Đã lưu Email cho {user_id}: {email_found.group()}")
        
    # 2. Quét Tiền trong tin nhắn này (Nếu có thì cập nhật vào Cache)
    clean_money = text_lower.replace('.', '').replace(',', '')
    money_found = re.search(r'\d+', clean_money)
    if money_found:
        money_val = int(money_found.group())
        if money_val > 10: # Chỉ lưu nếu > 10$ để tránh nhầm số khác
            user_info_cache[user_id]['money'] = money_val
            print(f"💾 Đã lưu Tiền cho {user_id}: {money_val}")

    # --- PHÂN LOẠI XỬ LÝ ---

    # 1. BILL / NHÂN VIÊN XÁC NHẬN -> GHI SHEET
    is_confirm = any(kw in text_lower for kw in TU_KHOA_NHAN_VIEN)
    is_bill = bool(update.message.photo) and ("gmail" in text_lower or "@" in text_lower) and re.search(r'\d+', text_lower)

    if is_confirm or is_bill:
        await send_congrats(update, context, text)
        return

    if any(tk in text_lower for tk in TU_KHOA_BO_QUA): return

    # 2. BÁO GIÁ & GỬI QR
    clean = text_lower.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean)
    if match:
        amt = int(match.group())
        if amt < 10: return 
        
        total_vnd = "{:,.0f}".format(amt * rate * 1000).replace(',', '.')
        rate_dis = "{:,.2f}".format(rate).replace('.', ',')
        
        resp = f"💵 **BÁO GIÁ NHANH:**\n✅ Số lượng: {amt} $\n✅ Tỷ giá: {rate_dis}\n💰 **THÀNH TIỀN: {total_vnd} VNĐ**\n-----------------------------\n{NOI_DUNG_CK}"
        
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qr.jpg')
        try:
            if os.path.exists(path):
                with open(path, 'rb') as p: await context.bot.send_photo(chat_id=update.message.chat_id, photo=p, caption=resp, parse_mode='Markdown')
            else: await update.message.reply_text(resp, parse_mode='Markdown')
        except: await update.message.reply_text(resp, parse_mode='Markdown')
        return

    # 3. HỎI GIÁ
    if any(kw in text_lower for kw in TU_KHOA_HOI_GIA):
        rate_dis = "{:,.2f}".format(rate).replace('.', ',')
        await update.message.reply_text(f"ℹ️ Tỷ giá hiện tại là: **{rate_dis} VNĐ**\n👉 Sếp hãy nhắn **Số lượng cần mua** (VD: `1000`) để em tính tiền nhé!", parse_mode='Markdown')

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
