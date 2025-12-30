import re 
import os 
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 

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

# --- PHẦN SERVER ẢO (GIÚP BOT ONLINE 24/7 TRÊN RENDER) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot đang chạy ngon lành!"

def run_http():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- PHẦN LOGIC BOT ---

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chỉnh giá: /gia 26,95"""
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
        await update.message.reply_text(f"✅ Đã cập nhật giá mới: {display_rate} k")
    except:
        await update.message.reply_text("⚠️ Lỗi! Hãy nhập đúng. Ví dụ: /gia 27")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra tin nhắn riêng
    chat_type = update.message.chat.type 
    user_id = update.effective_user.id   
    
    if chat_type == 'private' and user_id != ADMIN_ID:
        msg = (
            f"⛔ **BOT KHÔNG BÁO GIÁ RIÊNG!**\n\n"
            f"Để đảm bảo an toàn và uy tín, mời bạn vào nhóm chung để giao dịch:\n"
            f"👉 **Tham gia ngay:** {LINK_NHOM}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return 
    
    # Xử lý tính tiền
    text = update.message.text.lower()
    keywords = ['mua', 'bán', 'đổi', 'check', 'giá', 'usd', 'đô', '$', 'rate']
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text) 
    rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')

    # Trường hợp 1: Có số lượng -> Tính tiền + Gửi QR
    if match:
        amount = int(match.group()) 
        should_reply = False
        if text.strip().replace('.', '').replace(',', '').replace('$', '').isdigit(): should_reply = True
        elif any(word in text for word in keywords): should_reply = True

        if should_reply:
            total_vnd = amount * current_usd_rate * 1000 
            formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
            
            response = (
                f"💵 **BÁO GIÁ:**\n"
                f"✅ Số lượng: {amount} $\n"
                f"✅ Tỷ giá: {rate_display}\n"
                f"💰 **THÀNH TIỀN: {formatted_vnd} VNĐ**\n"
                f"-----------------------------\n"
                f"{NOI_DUNG_CK}"
            )
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            photo_path = os.path.join(script_dir, 'qr.jpg') 

            try:
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo:
                        await update.message.reply_photo(photo=photo, caption=response, parse_mode='Markdown')
                else:
                    await update.message.reply_text(response, parse_mode='Markdown')
            except:
                await update.message.reply_text(response, parse_mode='Markdown')

    # Trường hợp 2: Hỏi giá chơi
    elif any(word in text for word in keywords):
        response_rate = (
            f"📈 **CẬP NHẬT TỶ GIÁ HÔM NAY:**\n"
            f"-----------------------------\n"
            f"💵 Giá USD: **{rate_display}** VNĐ\n"
            f"*(Nhập số lượng cụ thể để nhận báo giá chi tiết)*"
        )
        await update.message.reply_text(response_rate, parse_mode='Markdown')

def main():
    keep_alive() # Chạy server ảo trước
    print("Bot đang chạy...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
