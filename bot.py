import re 
import os 
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

# NỘI DUNG CHUYỂN KHOẢN (Đính kèm trong ảnh báo giá)
NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734.838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

current_usd_rate = 27.0

# --- DANH SÁCH TỪ KHÓA BỎ QUA (IGNORE LIST) ---
# (Lưu ý: Đã xóa các từ liên quan đến 'nhận đủ' để Bot bắt được tin nhắn của nhân viên)
TU_KHOA_BO_QUA = [
    'đã bank', 'check giúp', 'done', 'ok',
    'bill', 'biên lai', 'đã chuyển', 'ck xong', 'đã ck', 'chuyển khoản', 
    'gmail', 'email', '@', 'gửi rồi', 'đã gửi'
]

# Từ khóa xác nhận của nhân viên (Để bot chúc mừng)
TU_KHOA_NHAN_VIEN = ['nhận được đủ', 'đã nhận đủ', 'nhận đủ usd', 'nhận đủ tiền', 'nhan du']

# Từ khóa khách hỏi giá (ĐÃ SỬA LỖI CÚ PHÁP Ở ĐÂY)
TU_KHOA_HOI_GIA = [
    'giá', 'gia', 'rate', 'tỷ giá', 'ty gia', 'bao nhiêu', 'nhiêu',
    'đô', 'đô hôm nay', 'gia do', 'xem giá', 'báo giá', 'giá đô'
]

# --- CÁC BIẾN LƯU ID TIN NHẮN (ĐỂ TỰ XÓA TIN CŨ) ---
last_welcome_message_id = None  # Lưu tin chào mừng
last_rate_message_id = None     # Lưu tin báo giá ghim
last_congrats_message_id = None # Lưu tin chúc mừng

# --- SERVER ẢO GIỮ BOT ONLINE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot đang hoạt động 100%!"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- LOGIC PHẢN HỒI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            await update.message.reply_text(f"🫡 Chào Sếp! Giá hiện tại: **{current_usd_rate}**.\nSếp cứ nhắn giá mới (VD: `27.5`) em sẽ tự đổi, tự xóa giá cũ và ghim giá mới nhé.", parse_mode='Markdown')
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
    global last_welcome_message_id
    
    # Xóa tin chào cũ
    if last_welcome_message_id:
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=last_welcome_message_id)
        except: pass

    for member in update.message.new_chat_members:
        if member.is_bot: continue
        keyboard = [
            [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")],
            [InlineKeyboardButton("📢 KÊNH TIN TỨC CHÍNH THỨC", url=LINK_CHANNEL)]
        ]
        # Chào mừng theo phong cách mới
        msg = await update.message.reply_text(
            f"👋 Chào mừng **Sếp {member.first_name}** đã gia nhập nhóm!\n\n"
            f"❤️ Kính chúc Sếp luôn dồi dào sức khoẻ và thịnh vượng tài chính.\n\n"
            f"👉 Sếp hãy ấn nút dưới đây để cài Tiếng Việt cho dễ dùng trên ứng dụng nhé 👇", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        last_welcome_message_id = msg.message_id

# --- HÀM CẬP NHẬT GIÁ (TỰ XÓA GIÁ CŨ) ---
async def update_rate_logic(context, new_rate):
    global current_usd_rate, last_rate_message_id
    current_usd_rate = new_rate
    
    # 1. Xóa tin báo giá cũ (nếu có)
    if last_rate_message_id:
        try:
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=last_rate_message_id)
        except: pass

    # 2. Gửi tin mới
    msg_text = (
        f"📣 **THÔNG BÁO CẬP NHẬT TỶ GIÁ** \n"
        f"-----------------\n"
        f"💵 Giá USD hiện tại: **{current_usd_rate} VNĐ**\n\n"
        f"✅ Áp dụng cho mọi giao dịch kể từ thời điểm này.\n\n"
        f"👉 Chúc anh chị em sở hữu được thật nhiều cổ phần nha!"
    )
    
    sent_msg = await context.bot.send_message(chat_id=GROUP_ID, text=msg_text, parse_mode='Markdown')
    
    # 3. Ghim tin mới và lưu ID lại
    try:
        await sent_msg.pin(disable_notification=False)
        last_rate_message_id = sent_msg.message_id
    except: pass
    
    return sent_msg

async def set_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        new_val = float(context.args[0].replace(',', '.'))
        new_val = new_val if new_val < 1000 else new_val/1000
        await update_rate_logic(context, new_val)
        await update.message.reply_text(f"✅ Đã đổi giá và xóa tin cũ: {current_usd_rate}")
    except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_congrats_message_id
    text = update.message.text.lower()

    # --- 1. ADMIN NHẮN RIÊNG -> CẬP NHẬT GIÁ ---
    if update.message.chat.type == "private":
        if update.effective_user.id == ADMIN_ID:
            clean_text = text.replace(',', '.')
            match = re.search(r'\d+(\.\d+)?', clean_text)
            if match:
                val = float(match.group())
                if 20 < val < 30: 
                    await update_rate_logic(context, val)
                    await update.message.reply_text(f"✅ Đã cập nhật giá **{val}** (đã xóa giá cũ và ghim giá mới) rồi Sếp nhé!")
                    return
                elif val > 1000:
                    await update.message.reply_text("⚠️ Số to quá Sếp ơi, có phải tỷ giá không ạ?")
                    return
            await update.message.reply_text("Sếp nhắn tỷ giá (ví dụ: `27` hoặc `26.95`) em đổi ngay.", parse_mode='Markdown')
            return
        
        # KHÁCH NHẮN RIÊNG -> ĐUỔI VỀ NHÓM
        keyboard = [
            [InlineKeyboardButton("👥 VÀO NHÓM GIAO DỊCH NGAY", url=LINK_NHOM)],
            [InlineKeyboardButton("🇻🇳 CÀI TIẾNG VIỆT NGAY", url="https://t.me/setlanguage/vi-beta")],
            [InlineKeyboardButton("📢 KÊNH TIN TỨC", url=LINK_CHANNEL)]
        ]
        await update.message.reply_text(
            "⛔ **THÔNG BÁO VỚI SẾP**\n\nĐể đảm bảo an toàn và uy tín,em **KHÔNG** làm việc qua tin nhắn riêng ạ.\nào nhóm chung để giao dịch Sêp nhé. 👇 👇 👇  Tham gia ngay:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # --- 2. XỬ LÝ TRONG NHÓM ---

    # A. CHECK TIN NHẮN NHÂN VIÊN (CHÚC MỪNG)
    if any(kw in text for kw in TU_KHOA_NHAN_VIEN):
        # Xóa tin chúc mừng cũ (nếu có)
        if last_congrats_message_id:
            try:
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=last_congrats_message_id)
            except: pass
        
        # Gửi tin chúc mừng mới
        msg = await update.message.reply_text(
            "🎉 **Chúc mừng Sếp sở hữu thêm nhiều tài sản nhé!** 🚀",
            parse_mode='Markdown'
        )
        last_congrats_message_id = msg.message_id
        return # Dừng lại, không xử lý tiếp

    # B. BỎ QUA CÁC TỪ KHÓA KHÁC (Bill, Gmail...)
    if any(tk in text for tk in TU_KHOA_BO_QUA): return
    
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text)
    
    # C. LOGIC TÍNH TIỀN (BÁO GIÁ)
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
        return

    # D. KHÁCH HỎI GIÁ
    if any(kw in text for kw in TU_KHOA_HOI_GIA):
        rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')
        msg = (
            f"ℹ️ Tỷ giá hiện tại là: **{rate_display} VNĐ**\n\n"
            f"👉 Sếp hãy nhắn **Số lượng cần mua** (VD: `1000`) để em tính tiền nhé!"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("gia", set_rate_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
