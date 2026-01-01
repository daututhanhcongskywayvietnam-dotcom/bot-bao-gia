import re 
import os 
import json # Thư viện để lưu file
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAFuWJk6yM98q8wIZWxkEMzvZ7-hKw9Be_Y' # Token của bạn
ADMIN_ID = 507318519  # ID của bạn
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 
LINK_CHANNEL = "https://t.me/unitsky_group_viet_nam"

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

# Tên file để lưu dữ liệu (Bộ nhớ vĩnh viễn)
DATA_FILE = 'bot_data.json'

# Dữ liệu mặc định (Nếu chưa có file thì dùng cái này)
default_data = {
    "current_usd_rate": 27.0,
    "last_welcome_message_id": None,
    "last_rate_message_id": None,
    "last_congrats_message_id": None
}

# Biến toàn cục chứa dữ liệu
bot_data = default_data.copy()

# --- HÀM LƯU & ĐỌC FILE (QUAN TRỌNG) ---
def load_data():
    """Đọc dữ liệu từ file khi Bot khởi động"""
    global bot_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                bot_data = json.load(f)
                print("✅ Đã tải dữ liệu cũ thành công!")
        except Exception as e:
            print(f"⚠️ Lỗi đọc file: {e}. Dùng mặc định.")
            bot_data = default_data.copy()
    else:
        bot_data = default_data.copy()

def save_data():
    """Lưu dữ liệu vào file ngay lập tức"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Không lưu được file: {e}")

# --- DANH SÁCH TỪ KHÓA BỎ QUA ---
TU_KHOA_BO_QUA = [
    'đã bank', 'check giúp', 'done', 'ok',
    'bill', 'biên lai', 'đã chuyển', 'ck xong', 'đã ck', 'chuyển khoản', 
    'gmail', 'email', '@', 'gửi rồi', 'đã gửi'
]

# Từ khóa xác nhận của nhân viên (Backup)
TU_KHOA_NHAN_VIEN = ['nhận được đủ', 'đã nhận đủ', 'nhận đủ usd', 'nhận đủ tiền', 'nhan du']

# Từ khóa khách hỏi giá
TU_KHOA_HOI_GIA = [
    'giá', 'gia', 'rate', 'tỷ giá', 'ty gia', 'bao nhiêu', 'nhiêu',
    'đô', 'đô hôm nay', 'gia do', 'xem giá', 'báo giá', 'giá đô'
]

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động 100%!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC PHẢN HỒI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = bot_data.get("current_usd_rate", 27.0)
    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            await update.message.reply_text(f"🫡 Chào Sếp! Giá hiện tại: **{rate}**.\nSếp cứ nhắn giá mới (VD: `27.5`) em sẽ tự đổi, tự xóa giá cũ và ghim giá mới nhé.", parse_mode='Markdown')
        else:
            keyboard = [
                [InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)],
                [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")],
                [InlineKeyboardButton("📢 KÊNH TIN TỨC", url=LINK_CHANNEL)]
            ]
            await update.message.reply_text(
                "👋 **Em chào Sếp!**\n\n"
                "🔒 Để bảo mật, em **CHỈ BÁO GIÁ VÀ GIAO DỊCH TRONG NHÓM**.\n"
                "👉 Mời Sếp bấm nút bên dưới để tham gia ạ:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text("Em đã sẵn sàng phục vụ Sếp!")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Xóa tin chào cũ (Lấy ID từ bộ nhớ file)
    old_welcome_id = bot_data.get("last_welcome_message_id")
    if old_welcome_id:
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=old_welcome_id)
        except: pass

    # 2. Gửi tin chào mới
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [
            [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")],
            [InlineKeyboardButton("📢 KÊNH TIN TỨC CHÍNH THỨC", url=LINK_CHANNEL)]
        ]
        msg = await update.message.reply_text(
            f"👋 Chào mừng **Sếp {member.first_name}** đã gia nhập nhóm!\n\n"
            f"❤️ Kính chúc Sếp luôn dồi dào sức khoẻ và thịnh vượng tài chính.\n\n"
            f"👉 Sếp hãy ấn nút dưới đây để cài Tiếng Việt cho dễ dùng nhé 👇", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        # 3. Lưu ID mới vào bộ nhớ và GHI RA FILE
        bot_data["last_welcome_message_id"] = msg.message_id
        save_data()

# --- TÍNH NĂNG: TỰ ĐỘNG XÓA THÔNG BÁO RỜI NHÓM ---
async def delete_left_member_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except:
        pass

async def update_rate_logic(context, new_rate):
    # Cập nhật giá vào bộ nhớ
    bot_data["current_usd_rate"] = new_rate
    
    # Xóa tin báo giá cũ (Lấy ID từ file)
    old_rate_id = bot_data.get("last_rate_message_id")
    if old_rate_id:
        try:
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=old_rate_id)
        except: pass

    msg_text = (
        f"📣 **CẬP NHẬT TỶ GIÁ** \n"
        f"-----------------\n"
        f"💵 Giá USD hiện tại: **{new_rate} VNĐ**\n\n"
        f"✅ Áp dụng cho mọi giao dịch kể từ thời điểm này.\n\n"
        f"👉 Chúc anh chị em sở hữu được thật nhiều cổ phần nha!"
    )
    sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg_text, parse_mode='Markdown')
    try:
        await sent_msg.pin(disable_notification=False)
        # Lưu ID tin nhắn ghim mới và GHI RA FILE
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
        await update.message.reply_text(f"✅ Đã đổi giá và lưu vào hệ thống: {new_val}")
    except: pass

async def send_congrats(update, context):
    old_congrats_id = bot_data.get("last_congrats_message_id")
    if old_congrats_id:
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=old_congrats_id)
        except: pass
    msg = await update.message.reply_text("🎉 **Chúc mừng Sếp sở hữu thêm nhiều tài sản nhé!** 🚀", parse_mode='Markdown')
    
    # Lưu ID chúc mừng và GHI RA FILE
    bot_data["last_congrats_message_id"] = msg.message_id
    save_data()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = bot_data.get("current_usd_rate", 27.0)
    text = ""
    if update.message.text:
        text = update.message.text
    elif update.message.caption:
        text = update.message.caption
    
    if not text: return 
    text = text.lower()

    # 1. ADMIN NHẮN RIÊNG
    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            clean_text = text.replace(',', '.')
            match = re.search(r'\d+(\.\d+)?', clean_text)
            if match:
                val = float(match.group())
                if 20 < val < 30: 
                    await update_rate_logic(context, val)
                    await update.message.reply_text(f"✅ Đã cập nhật giá **{val}** rồi Sếp nhé!")
                    return
            await update.message.reply_text("Sếp nhắn tỷ giá (ví dụ: `27`) em đổi ngay.", parse_mode='Markdown')
            return
        keyboard = [[InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)]]
        await update.message.reply_text("⛔ **EM KHÔNG BÁO GIÁ RIÊNG SẾP Ạ!**\nEm mời Sếp vào nhóm chung để đảm bảo an toàn và uy tín giao dịch:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    # --- XỬ LÝ TRONG NHÓM ---

    # 2. KHÁCH GỬI ẢNH BILL + GMAIL + TIỀN
    has_photo = bool(update.message.photo)
    has_gmail = ("gmail" in text or "@" in text)
    has_money = re.search(r'\d+', text)

    if has_photo and has_gmail and has_money:
        await send_congrats(update, context)
        return

    # 3. NHÂN VIÊN XÁC NHẬN
    if any(kw in text for kw in TU_KHOA_NHAN_VIEN):
        await send_congrats(update, context)
        return

    # 4. BỎ QUA CÁC TỪ KHÓA KHÁC
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    # 5. BÁO GIÁ
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    
    if match:
        amount = int(match.group())
        if amount <= 0: return
        total_vnd = "{:,.0f}".format(amount * rate * 1000).replace(',', '.')
        rate_display = "{:,.2f}".format(rate).replace('.', ',')
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
        return

    # 6. HỎI GIÁ
    if any(kw in text for kw in TU_KHOA_HOI_GIA):
        rate_display = "{:,.2f}".format(rate).replace('.', ',')
        msg = (f"ℹ️ Tỷ giá hiện tại là: **{rate_display} VNĐ**\n\n👉 Sếp hãy nhắn **Số lượng cần mua** (VD: `1000`) để em tính tiền nhé!")
        await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    # Load dữ liệu từ file trước khi bật Bot
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
